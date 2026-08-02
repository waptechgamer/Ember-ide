"""Tabbed editor — multi-file editing on top of QScintilla.

VS Code-inspired tabbed interface with modern styling.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from app.editor.code_editor import CodeEditor
from app.theme.dark_theme import PALETTE
from app.theme import icons as ico
from app.utils.file_utils import normalize, safe_write
from app.utils.terminal import RunRequest

from PyQt5.QtGui import QIcon


def _icon(pm) -> QIcon:
    """Wrap a QPixmap in a QIcon."""
    return QIcon(pm)

# Lazy import for search functionality
def _get_qscintilla():
    from PyQt5.Qsci import QsciScintilla
    return QsciScintilla


@dataclass
class _Tab:
    editor: CodeEditor
    file_path: Optional[Path]
    is_new: bool  # True for "Untitled" tabs not yet saved


# Maps file extension to a runnable command template.
# The literal token ``{path}`` is replaced with the absolute file path.
_RUNNERS = {
    ".py":   'python -u "{path}"',
    ".pyw":  'pythonw "{path}"',
    ".js":   'node "{path}"',
    ".mjs":  'node "{path}"',
    ".ts":   'npx ts-node "{path}"',
    ".rb":   'ruby "{path}"',
    ".sh":   'bash "{path}"',
    ".ps1":  'powershell -NoProfile -ExecutionPolicy Bypass -File "{path}"',
    ".bat":  '"{path}"',
    ".cmd":  '"{path}"',
}


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert a hex color string to an (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class TabbedEditor(QWidget):
    """A QTabWidget hosting CodeEditor instances."""

    current_file_changed = pyqtSignal(object)  # Path or None
    dirty_state_changed = pyqtSignal(bool)     # any tab dirty?
    cursor_moved = pyqtSignal(int, int)        # line, column (1-based)
    content_loaded = pyqtSignal(str)           # text of newly opened file

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        
        # VS Code-inspired tab styling
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {PALETTE['bg']};
            }}
            QTabBar {{
                background: {PALETTE['bg_alt']};
                border-bottom: 1px solid {PALETTE['border']};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {PALETTE['fg_dim']};
                padding: 8px 16px;
                border: none;
                border-bottom: 2px solid transparent;
                margin: 0;
                min-width: 80px;
                max-width: 200px;
            }}
            QTabBar::tab:selected {{
                background: {PALETTE['bg']};
                color: {PALETTE['fg']};
                border-bottom: 2px solid {PALETTE['accent']};
            }}
            QTabBar::tab:!selected:hover {{
                background: {PALETTE['panel']};
                color: {PALETTE['fg']};
            }}
            QTabBar::close-button {{
                image: none;
                subcontrol-position: right;
                padding: 2px;
            }}
        """)
        
        self._tabs.tabCloseRequested.connect(self._on_close_requested)
        self._tabs.currentChanged.connect(self._on_current_changed)

        # Search/Replace bar (hidden by default)
        self._search_bar = self._build_search_bar()

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self._search_bar)
        v.addWidget(self._tabs)

        self._items: list[_Tab] = []
        self.new_file()  # start with one empty tab

        # Welcome panel overlay — shown when the only tab is empty/untitled
        self._welcome = self._build_welcome_panel()
        self._welcome.setParent(self)
        self._welcome.resize(self.size())
        self._welcome.hide()
        self._update_welcome_visibility()
        # Reposition on resize
        self._tabs.currentChanged.connect(lambda _: self._update_welcome_visibility())

    # ----------------------------------------------------------------- public

    def current_editor(self) -> Optional[CodeEditor]:
        item = self._current_item()
        return item.editor if item else None

    def current_path(self) -> Optional[Path]:
        item = self._current_item()
        return item.file_path if item else None

    def count(self) -> int:
        return self._tabs.count()

    def has_unsaved(self) -> bool:
        return any(t.editor.is_modified() for t in self._items)

    def new_file(self) -> None:
        self._add_tab(file_path=None, text="")

    def _build_welcome_panel(self) -> QWidget:
        """Build a centered welcome panel overlay for the empty editor state."""
        panel = QWidget(self)
        panel.setObjectName("welcome_panel")
        panel.setStyleSheet(f"""
            QWidget#welcome_panel {{
                background: {PALETTE['bg']};
            }}
        """)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        v = QVBoxLayout(panel)
        v.setAlignment(Qt.AlignCenter)
        v.setSpacing(8)

        # Logo text — clean, no emoji
        logo = QLabel("Ember IDE")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(f"""
            font-size: 32px;
            font-weight: 300;
            color: {PALETTE['fg']};
            letter-spacing: 2px;
            background: transparent;
        """)
        v.addWidget(logo)

        # Tagline
        tagline = QLabel("A lightweight, cross-platform code editor")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet(f"""
            font-size: 13px;
            color: {PALETTE['fg_dim']};
            background: transparent;
            margin-bottom: 20px;
        """)
        v.addWidget(tagline)

        v.addSpacing(16)

        # Shortcut hints
        shortcuts = [
            ("Ctrl+N", "New File"),
            ("Ctrl+O", "Open File"),
            ("Ctrl+Shift+O", "Open Folder"),
            ("Ctrl+S", "Save"),
            ("Ctrl+F", "Find"),
            ("Ctrl+`", "Toggle Terminal"),
            ("Ctrl+F5", "Run"),
        ]

        table = QWidget()
        table.setStyleSheet("background: transparent;")
        table_layout = QVBoxLayout(table)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.setAlignment(Qt.AlignCenter)

        for key, desc in shortcuts:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 1, 0, 1)
            row_layout.setAlignment(Qt.AlignCenter)
            key_lbl = QLabel(key)
            key_lbl.setStyleSheet(f"""
                color: {PALETTE['fg']};
                font-size: 12px;
                font-family: "Consolas", "Monospace";
                background: transparent;
                min-width: 110px;
                padding: 3px 8px;
                background-color: {PALETTE['bg_alt']};
                border: 1px solid {PALETTE['border']};
                border-radius: 3px;
            """)
            key_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            desc_lbl = QLabel(f"  {desc}")
            desc_lbl.setStyleSheet(f"""
                color: {PALETTE['fg_dim']};
                font-size: 12px;
                background: transparent;
                min-width: 120px;
            """)
            row_layout.addWidget(key_lbl)
            row_layout.addWidget(desc_lbl)
            table_layout.addWidget(row)

        v.addWidget(table)

        v.addSpacing(28)

        # Quick action buttons
        actions = QWidget()
        actions.setStyleSheet("background: transparent;")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setAlignment(Qt.AlignCenter)
        actions_layout.setSpacing(10)

        btn_open = QPushButton("Open File")
        btn_open.setObjectName("welcomeBtnPrimary")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.setFixedHeight(32)
        btn_open.setMinimumWidth(130)

        btn_folder = QPushButton("Open Folder")
        btn_folder.setObjectName("welcomeBtnSecondary")
        btn_folder.setCursor(Qt.PointingHandCursor)
        btn_folder.setFixedHeight(32)
        btn_folder.setMinimumWidth(130)

        actions_layout.addWidget(btn_open)
        actions_layout.addWidget(btn_folder)
        v.addWidget(actions)

        panel._btn_open_file = btn_open
        panel._btn_open_folder = btn_folder

        return panel

    def _update_welcome_visibility(self) -> None:
        """Show welcome panel only when there's a single empty untitled tab."""
        if not hasattr(self, '_welcome'):
            return
        # Re-position to cover the tab area
        self._welcome.resize(self._tabs.size())
        self._welcome.move(0, 0)
        show = (
            len(self._items) == 1
            and self._items[0].file_path is None
            and self._items[0].is_new
            and not self._items[0].editor.is_modified()
            and self._items[0].editor.text.strip() == ""
        )
        if show:
            self._welcome.raise_()
            self._welcome.show()
        else:
            self._welcome.hide()

    def _build_search_bar(self) -> QWidget:
        """Build a VS Code-style search/replace bar."""
        bar = QWidget()
        bar.setObjectName("search_bar")
        bar.setStyleSheet(f"""
            QWidget#search_bar {{
                background: {PALETTE['bg_alt']};
                border-bottom: 1px solid {PALETTE['border']};
            }}
        """)
        bar.setFixedHeight(60)
        bar.hide()

        layout = QVBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # Find row
        find_row = QHBoxLayout()
        find_row.setSpacing(4)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Find")
        self._search_input.setFixedHeight(24)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {PALETTE['bg_sunken']};
                color: {PALETTE['fg']};
                border: 1px solid {PALETTE['border']};
                border-radius: 3px;
                padding: 0 6px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {PALETTE['accent']};
            }}
        """)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        find_row.addWidget(self._search_input, 1)

        btn_prev = QPushButton()
        btn_prev.setIcon(_icon(ico.icon_arrow_up()))
        btn_prev.setFixedSize(24, 24)
        btn_prev.setToolTip("Previous match (Shift+Enter)")
        btn_prev.clicked.connect(lambda: self._search_move(-1))
        find_row.addWidget(btn_prev)

        btn_next = QPushButton()
        btn_next.setIcon(_icon(ico.icon_arrow_down()))
        btn_next.setFixedSize(24, 24)
        btn_next.setToolTip("Next match (Enter)")
        btn_next.clicked.connect(lambda: self._search_move(1))
        find_row.addWidget(btn_next)

        self._search_count = QLabel("")
        self._search_count.setStyleSheet(f"color: {PALETTE['fg_dim']}; font-size: 11px; padding: 0 4px;")
        find_row.addWidget(self._search_count)

        btn_close = QPushButton()
        btn_close.setIcon(_icon(ico.icon_close(12, "#858585")))
        btn_close.setFixedSize(24, 24)
        btn_close.setToolTip("Close (Esc)")
        btn_close.clicked.connect(self.toggle_search)
        find_row.addWidget(btn_close)

        layout.addLayout(find_row)

        # Replace row
        replace_row = QHBoxLayout()
        replace_row.setSpacing(4)

        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Replace")
        self._replace_input.setFixedHeight(24)
        self._replace_input.setStyleSheet(f"""
            QLineEdit {{
                background: {PALETTE['bg_sunken']};
                color: {PALETTE['fg']};
                border: 1px solid {PALETTE['border']};
                border-radius: 3px;
                padding: 0 6px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {PALETTE['accent']};
            }}
        """)
        replace_row.addWidget(self._replace_input, 1)

        btn_replace = QPushButton("Replace")
        btn_replace.setFixedHeight(24)
        btn_replace.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['panel']};
                color: {PALETTE['fg']};
                border: 1px solid {PALETTE['border']};
                border-radius: 3px;
                padding: 0 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {PALETTE['border']};
            }}
        """)
        btn_replace.clicked.connect(self._replace_current)
        replace_row.addWidget(btn_replace)

        btn_replace_all = QPushButton("All")
        btn_replace_all.setFixedHeight(24)
        btn_replace_all.setStyleSheet(f"""
            QPushButton {{
                background: {PALETTE['panel']};
                color: {PALETTE['fg']};
                border: 1px solid {PALETTE['border']};
                border-radius: 3px;
                padding: 0 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {PALETTE['border']};
            }}
        """)
        btn_replace_all.clicked.connect(self._replace_all)
        replace_row.addWidget(btn_replace_all)

        layout.addLayout(replace_row)

        self._search_matches: list = []
        self._search_index: int = -1

        return bar

    def toggle_search(self) -> None:
        """Toggle the search/replace bar visibility."""
        if self._search_bar.isVisible():
            self._search_bar.hide()
            editor = self.current_editor()
            if editor:
                editor.widget.setFocus()
        else:
            self._search_bar.show()
            self._search_input.setFocus()
            self._search_input.selectAll()

    def _on_search_text_changed(self, text: str) -> None:
        """Handle search text changes — highlight all matches."""
        editor = self.current_editor()
        if not editor:
            return
        scintilla = editor.widget
        QsciScintilla = _get_qscintilla()
        scintilla.clearHighlights()

        if not text:
            self._search_count.setText("")
            self._search_matches = []
            self._search_index = -1
            return

        # Find all matches
        scintilla.setSearchFlags(0)
        scintilla.setCursorPosition(0, 0)
        self._search_matches = []
        self._search_index = -1

        pos = 0
        text_len = len(scintilla.text())
        while pos < text_len:
            found = scintilla.findFirst(text, False, False, False, True, pos)
            if not found:
                break
            match_pos = scintilla.getCursorPosition()
            self._search_matches.append(match_pos)
            pos = match_pos[1] + 1
            if pos >= text_len:
                break

        if self._search_matches:
            self._search_index = 0
            self._search_count.setText(f"1 of {len(self._search_matches)}")
            self._search_move_to(0)
        else:
            self._search_count.setText("No results")
            self._search_index = -1

    def _search_move(self, delta: int) -> None:
        """Move to the next/previous search match."""
        if not self._search_matches:
            return
        self._search_index = (self._search_index + delta) % len(self._search_matches)
        self._search_count.setText(f"{self._search_index + 1} of {len(self._search_matches)}")
        self._search_move_to(self._search_index)

    def _search_move_to(self, index: int) -> None:
        """Move cursor to the search match at the given index."""
        editor = self.current_editor()
        if not editor or index < 0 or index >= len(self._search_matches):
            return
        line, col = self._search_matches[index]
        editor.widget.setCursorPosition(line, col)
        editor.widget.ensureCursorVisible()

    def _replace_current(self) -> None:
        """Replace the current match."""
        editor = self.current_editor()
        if not editor or self._search_index < 0:
            return
        find_text = self._search_input.text()
        replace_text = self._replace_input.text()
        if not find_text:
            return

        line, col = self._search_matches[self._search_index]
        editor.widget.setCursorPosition(line, col)
        editor.widget.setSelection(line, col, line, col + len(find_text))
        editor.widget.replace(replace_text)
        self._on_search_text_changed(find_text)

    def _replace_all(self) -> None:
        """Replace all matches."""
        editor = self.current_editor()
        if not editor:
            return
        find_text = self._search_input.text()
        replace_text = self._replace_input.text()
        if not find_text:
            return

        count = editor.widget.replaceAll(find_text, replace_text, True)
        self._on_search_text_changed(find_text)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, '_welcome'):
            self._welcome.resize(self._tabs.size())
            self._welcome.move(0, 0)
            if self._welcome.isVisible():
                self._welcome.raise_()

    def open_file(self, path: str | Path) -> bool:
        """Open ``path``. Returns True if a tab now shows the file."""
        path = normalize(path)
        if not path.is_file():
            QMessageBox.warning(self, "Open file", f"Not a file:\n{path}")
            return False
        # Reuse existing tab for the same path
        for t in self._items:
            if t.file_path == path and not t.is_new:
                self._focus_tab(t)
                return True
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            QMessageBox.warning(self, "Open file", f"Could not decode as UTF-8:\n{path}")
            return False
        except OSError as exc:
            QMessageBox.warning(self, "Open file", f"Read error:\n{exc}")
            return False
        self._add_tab(file_path=path, text=text, is_new=False)
        self.content_loaded.emit(text)
        return True

    def open_files(self, paths) -> int:
        count = 0
        for p in paths:
            if self.open_file(p):
                count += 1
        return count

    def save_current(self) -> bool:
        item = self._current_item()
        if item is None:
            return False
        if item.file_path is None or item.is_new:
            return self.save_current_as()
        return self._write(item)

    def save_current_as(self) -> bool:
        item = self._current_item()
        if item is None:
            return False
        start_dir = str(item.file_path.parent) if item.file_path else ""
        suggested = item.file_path.name if item.file_path else "untitled.txt"
        chosen, _ = QFileDialog.getSaveFileName(self, "Save As", f"{start_dir}/{suggested}")
        if not chosen:
            return False
        new_path = normalize(chosen)
        item.file_path = new_path
        item.is_new = False
        self._refresh_tab_title(item)
        return self._write(item)

    def save_all(self) -> bool:
        ok = True
        current = self._tabs.currentIndex()
        for i, item in enumerate(self._items):
            if item.editor.is_modified():
                self._tabs.setCurrentIndex(i)
                if item.file_path is None or item.is_new:
                    if not self.save_current_as():
                        ok = False
                else:
                    if not self._write(item):
                        ok = False
        self._tabs.setCurrentIndex(current)
        return ok

    def run_current(self) -> Optional[RunRequest]:
        """Return a :class:`RunRequest` for the current tab, or None.

        Returns None if the file is unsaved (no path yet) or the
        extension is not in the runnable map.
        """
        item = self._current_item()
        if item is None or item.file_path is None:
            return None
        suffix = item.file_path.suffix.lower()
        template = _RUNNERS.get(suffix)
        if not template:
            return None
        command = template.replace("{path}", str(item.file_path))
        return RunRequest(command=command, cwd=item.file_path.parent)

    def runnable_for(self, path: Optional[Path]) -> bool:
        if path is None:
            return False
        return path.suffix.lower() in _RUNNERS

    def close_current(self) -> bool:
        idx = self._tabs.currentIndex()
        if idx < 0:
            return True
        return self._close_index(idx)

    def close_all(self) -> bool:
        # iterate over a copy because _close_index mutates _items
        for i in reversed(range(len(self._items))):
            if not self._close_index(i):
                return False
        return True

    # ---------------------------------------------------------------- private

    def _current_item(self) -> Optional[_Tab]:
        idx = self._tabs.currentIndex()
        if 0 <= idx < len(self._items):
            return self._items[idx]
        return None

    def _add_tab(self, file_path: Optional[Path], text: str, is_new: bool = True) -> None:
        editor = CodeEditor(file_path=file_path, parent=self)
        editor.text = text
        editor.modification_changed.connect(lambda *_: self._on_modified_changed())
        editor.cursor_position_changed.connect(self.cursor_moved)

        idx = self._tabs.addTab(editor.widget, self._tab_title(file_path, False))
        self._tabs.setTabToolTip(idx, str(file_path) if file_path else "Unsaved")
        self._tabs.setCurrentIndex(idx)
        self._items.append(_Tab(editor=editor, file_path=file_path, is_new=is_new))
        self._emit_dirty()

    def _focus_tab(self, item: _Tab) -> None:
        try:
            idx = self._items.index(item)
        except ValueError:
            return
        self._tabs.setCurrentIndex(idx)

    def _tab_title(self, file_path: Optional[Path], dirty: bool) -> str:
        name = file_path.name if file_path else "Untitled"
        # Elide long filenames to keep tabs readable
        if len(name) > 28:
            base, ext = "", ""
            if "." in name:
                base, ext = name.rsplit(".", 1)
                ext = f".{ext}"
            if base and len(base) > 20:
                name = base[:18] + "…" + ext if ext else base[:25] + "…"
            elif not base:
                name = name[:25] + "…"
        if dirty:
            # Use a small colored dot indicator (VS Code style)
            return f"● {name}"
        return name

    def _refresh_tab_title(self, item: _Tab) -> None:
        try:
            idx = self._items.index(item)
        except ValueError:
            return
        self._tabs.setTabText(idx, self._tab_title(item.file_path, item.editor.is_modified()))
        self._tabs.setTabToolTip(idx, str(item.file_path) if item.file_path else "Unsaved")

    def _on_modified_changed(self) -> None:
        item = self._current_item()
        if item:
            self._refresh_tab_title(item)
        self._emit_dirty()
        self._update_welcome_visibility()

    def _on_current_changed(self, _index: int) -> None:
        item = self._current_item()
        self.current_file_changed.emit(item.file_path if item else None)
        self._emit_dirty()
        if item:
            line, col = 1, 1
            self.cursor_moved.emit(line, col)

    def _on_close_requested(self, index: int) -> None:
        self._close_index(index)

    def _close_index(self, index: int) -> bool:
        if not (0 <= index < len(self._items)):
            return True
        item = self._items[index]
        if item.editor.is_modified():
            name = item.file_path.name if item.file_path else "Untitled"
            choice = QMessageBox.question(
                self, "Unsaved changes",
                f"Save changes to {name}?",
                QMessageBox.Save |
                QMessageBox.Discard |
                QMessageBox.Cancel,
            )
            if choice == QMessageBox.Cancel:
                return False
            if choice == QMessageBox.Save:
                self._tabs.setCurrentIndex(index)
                if not self.save_current():
                    return False
        widget = item.editor.widget
        self._tabs.removeTab(index)
        self._items.pop(index)
        widget.deleteLater()
        self._emit_dirty()
        if not self._items:
            self.new_file()
        self._update_welcome_visibility()
        return True

    def _write(self, item: _Tab) -> bool:
        try:
            safe_write(item.file_path, item.editor.text)
        except OSError as exc:
            QMessageBox.warning(self, "Save file", f"Could not save:\n{exc}")
            return False
        item.editor.set_modified(False)
        self._refresh_tab_title(item)
        return True

    def _emit_dirty(self) -> None:
        self.dirty_state_changed.emit(self.has_unsaved())
