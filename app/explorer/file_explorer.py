"""File explorer — a QTreeView backed by QFileSystemModel.

VS Code-inspired file explorer with clean dark theme styling.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QDir, QModelIndex, Qt, pyqtSignal, QFileInfo
from PyQt5.QtGui import QBrush, QColor, QIcon
from PyQt5.QtWidgets import (
    QAbstractItemView, QHeaderView, QTreeView, QWidget, QFileIconProvider,
)
from app.theme.icons import icon_flame


class FlameFileIconProvider(QFileIconProvider):
    def __init__(self) -> None:
        super().__init__()
        self._flame_icon = icon_flame(16)

    def icon(self, info: QFileInfo) -> QIcon:
        if isinstance(info, QFileInfo):
            if info.suffix().lower() == "flame":
                return self._flame_icon
        return super().icon(info)

from app.theme.dark_theme import PALETTE
from app.utils.file_utils import is_hidden, normalize


class FileExplorer(QWidget):
    file_activated = pyqtSignal(Path)        # double-click / Enter on a file
    folder_changed = pyqtSignal(Path)        # root changed
    context_action = pyqtSignal(str, Path)   # ("new_file" | "new_folder" | "rename" | "delete", path)
    open_file_requested = pyqtSignal()       # placeholder button: Open File
    open_folder_requested = pyqtSignal()     # placeholder button: Open Folder

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PyQt5.QtWidgets import QFileSystemModel, QVBoxLayout  # local import

        self._model = QFileSystemModel(self)
        self._icon_provider = FlameFileIconProvider()
        self._model.setIconProvider(self._icon_provider)
        self._model.setReadOnly(False)
        # show all files (we grey out hidden ones visually)
        self._model.setNameFilterDisables(False)
        self._model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)

        self._view = QTreeView()
        self._view.setModel(self._model)
        # Use a modest icon size similar to VS Code's file explorer
        from PyQt5.QtCore import QSize
        self._view.setIconSize(QSize(16, 16))
        # uniform row heights = faster, predictable layout, no half-drawn rows
        self._view.setUniformRowHeights(True)
        
        self._view.setStyleSheet(f"""
            QTreeView {{
                background: {PALETTE['bg_alt']};
                color: {PALETTE['fg']};
                border: none;
                outline: none;
                font-family: \"Consolas\", \"Courier New\", monospace;
                font-size: 13px;
                padding: 4px 0;
            }}
            QTreeView::item {{
                padding: 4px 8px;
                border-radius: 4px;
                margin: 1px 4px;
                min-height: 24px;
            }}
            QTreeView::item:selected {{
                background: {PALETTE['selection']};
                color: white;
            }}
            QTreeView::item:hover:!selected {{
                background: {PALETTE['panel']};
            }}
            QTreeView::branch {{
                background: {PALETTE['bg_alt']};
            }}
            QTreeView::branch:has-children:closed {{
                border-image: none;
            }}
            QTreeView::branch:has-children:open {{
                border-image: none;
            }}
        """)
        
        # Hide the column header — IDEs don't show "Name / Size / Type" labels
        # above the tree. Saves vertical space and matches VS Code.
        self._view.setHeaderHidden(True)
        self._view.setRootIsDecorated(True)
        self._view.setAlternatingRowColors(False)
        self._view.setSelectionMode(QAbstractItemView.SingleSelection)
        self._view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._view.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._view.setExpandsOnDoubleClick(True)
        self._view.customContextMenuRequested.connect(self._on_context_menu)
        self._view.doubleClicked.connect(self._on_double_clicked)
        self._view.activated.connect(self._on_double_clicked)
        
        # Grey out hidden items via stylesheet

        header = self._view.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        header.hideSection(1)  # Size
        header.hideSection(2)  # Type
        header.hideSection(3)  # Modified

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # "PROJECT FILES" collapsible section header
        self._section_header = self._build_section_header()
        layout.addWidget(self._section_header)

        layout.addWidget(self._view)
        # Empty-state placeholder (created last so it sits on top)
        self._placeholder = self._build_placeholder()
        self._placeholder.hide()

        self._root: Optional[Path] = None
        self._section_collapsed = False

    # ------------------------------------------------------------------ public

    def _build_placeholder(self) -> QWidget:
        """Build a centered 'no folder open' placeholder widget."""
        from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QSizePolicy

        outer = QWidget(self)
        outer.setObjectName("explorer_placeholder")
        outer.setStyleSheet(f"""
            QWidget#explorer_placeholder {{
                background: {PALETTE['bg_alt']};
                border: none;
            }}
        """)
        outer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        v = QVBoxLayout(outer)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)
        v.addStretch(1)

        # Folder icon
        from PyQt5.QtGui import QPixmap
        from app.theme import icons as ico
        icon = QLabel()
        icon.setPixmap(ico.icon_folder(56, PALETTE['accent']))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background: transparent;")
        v.addWidget(icon)

        title = QLabel("No Folder Open")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            color: {PALETTE['fg']};
            font-size: 14px;
            font-weight: 600;
            margin-top: 8px;
        """)
        v.addWidget(title)

        sub = QLabel("Open a folder to start exploring your project.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"""
            color: {PALETTE['fg_dim']};
            font-size: 12px;
            margin-bottom: 16px;
        """)
        v.addWidget(sub)

        btn_open_folder = QPushButton("Open Folder...")
        btn_open_folder.setObjectName("explorerBtnPrimary")
        btn_open_folder.setCursor(Qt.PointingHandCursor)
        btn_open_folder.setFixedHeight(36)
        btn_open_folder.setMinimumWidth(160)
        btn_open_folder.clicked.connect(self.open_folder_requested.emit)
        v.addWidget(btn_open_folder, 0, Qt.AlignCenter)

        btn_open_file = QPushButton("Open File...")
        btn_open_file.setObjectName("explorerBtnLink")
        btn_open_file.setCursor(Qt.PointingHandCursor)
        btn_open_file.clicked.connect(self.open_file_requested.emit)
        v.addWidget(btn_open_file, 0, Qt.AlignCenter)

        v.addStretch(1)
        return outer

    def _build_section_header(self) -> QWidget:
        """Build a VS Code-style collapsible section header ('PROJECT FILES')."""
        from PyQt5.QtWidgets import QLabel, QPushButton, QHBoxLayout, QSizePolicy

        header = QWidget(self)
        header.setFixedHeight(30)
        header.setCursor(Qt.PointingHandCursor)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header.setStyleSheet(f"""
            QWidget {{
                background: transparent;
                border: none;
            }}
        """)

        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 8, 0)
        h_layout.setSpacing(6)

        # Chevron + title
        from PyQt5.QtGui import QPixmap
        from app.theme import icons as ico
        self._section_chevron = QLabel()
        self._section_chevron.setPixmap(ico.icon_chevron_down())
        self._section_chevron.setStyleSheet("background: transparent;")
        self._section_chevron.setFixedSize(12, 12)
        h_layout.addWidget(self._section_chevron)

        title = QLabel("PROJECT FILES")
        title.setStyleSheet(f"""
            color: {PALETTE['fg_dim']};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.5px;
            background: transparent;
        """)
        h_layout.addWidget(title)
        h_layout.addStretch()

        # Toggle on click
        header.mousePressEvent = self._toggle_section  # noqa: N802

        return header

    def _toggle_section(self, event) -> None:
        """Toggle the tree view collapse/expand on the root."""
        from app.theme import icons as ico
        self._section_collapsed = not self._section_collapsed
        if self._section_collapsed:
            self._section_chevron.setPixmap(ico.icon_chevron_right())
        else:
            self._section_chevron.setPixmap(ico.icon_chevron_down())
        if self._root is not None:
            idx = self._model.index(str(self._root))
            if self._section_collapsed:
                self._view.collapseAll()
            else:
                self._view.expandAll()

    def _show_placeholder(self) -> None:
        """Show the empty-state placeholder and hide the tree view."""
        if hasattr(self, "_placeholder"):
            self._placeholder.setVisible(True)
            self._view.setVisible(False)

    def _hide_placeholder(self) -> None:
        if hasattr(self, "_placeholder"):
            self._placeholder.setVisible(False)
            self._view.setVisible(True)

    # ------------------------------------------------------------------ public

    def root(self) -> Optional[Path]:
        return self._root

    def set_root(self, path: str | Path) -> None:
        path = normalize(path)
        if not path.is_dir():
            return
        self._root = path
        idx = self._model.setRootPath(str(path))
        self._view.setRootIndex(idx)
        # Expand the root so the first level of files is immediately visible.
        self._view.expand(idx)
        # Toggle placeholder visibility.
        if hasattr(self, "_placeholder"):
            self._placeholder.setVisible(False)
            self._view.setVisible(True)
        self.folder_changed.emit(path)

    def current_path(self) -> Optional[Path]:
        idx = self._view.currentIndex()
        if not idx.isValid():
            return None
        p = self._model.filePath(idx)
        return normalize(p) if p else None

    def select(self, path: Path) -> None:
        idx = self._model.index(str(path))
        if idx.isValid():
            self._view.setCurrentIndex(idx)
            self._view.scrollTo(idx)

    def refresh(self) -> None:
        if self._root:
            self._model.refresh()

    # ---------------------------------------------------------------- private

    def _on_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        path = normalize(self._model.filePath(index))
        if path.is_file():
            self.file_activated.emit(path)

    def _on_context_menu(self, pos) -> None:
        from PyQt5.QtWidgets import QMenu  # local import

        idx = self._view.indexAt(pos)
        target = (
            normalize(self._model.filePath(idx))
            if idx.isValid() and self._model.filePath(idx)
            else (self._root or Path.cwd())
        )

        menu = QMenu(self)
        a_new_file = menu.addAction("New File")
        a_new_dir = menu.addAction("New Folder")
        menu.addSeparator()
        a_rename = menu.addAction("Rename")
        a_delete = menu.addAction("Delete")
        if not idx.isValid():
            a_rename.setEnabled(False)
            a_delete.setEnabled(False)

        chosen = menu.exec(self._view.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == a_new_file:
            self.context_action.emit("new_file", target if target.is_dir() else target.parent)
        elif chosen == a_new_dir:
            self.context_action.emit("new_folder", target if target.is_dir() else target.parent)
        elif chosen == a_rename:
            self.context_action.emit("rename", target)
        elif chosen == a_delete:
            self.context_action.emit("delete", target)

    # ------------------------------------------------------------- lifecycle

    def showEvent(self, event) -> None:  # noqa: N802
        # Show the placeholder on first show if no folder is open yet.
        if self._root is None and hasattr(self, "_placeholder"):
            self._show_placeholder()
        super().showEvent(event)
