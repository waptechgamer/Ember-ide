"""Main window — assembles the editor + explorer + terminal, wires menu/toolbar/statusbar."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QSplitter, QStatusBar, QTabWidget, QToolBar,
    QVBoxLayout, QWidget, QDialog, QTextEdit,
)

from app.editor.tabbed_editor import TabbedEditor
from app.explorer.explorer_actions import ExplorerActions
from app.explorer.file_explorer import FileExplorer
from app.theme.dark_theme import PALETTE
from app.theme import icons as ico
from app.utils.file_utils import normalize
from app.utils.terminal import TerminalWidget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _icon(pm) -> QIcon:
    """Wrap a QPixmap in a QIcon for QAction / QToolButton."""
    return QIcon(pm)


_ACTIVITY_SIZE = 48
_ICON_SIZE = 20


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Ember IDE")
        self.resize(1280, 800)
        self.setMinimumSize(800, 500)

        # --- widgets ---------------------------------------------------------
        self.explorer = FileExplorer()
        self.editor = TabbedEditor()
        self.terminal_panel = TerminalPanel(explorer=self.explorer)

        # Build the explorer panel
        explorer_panel = self._build_explorer_panel(self.explorer)

        # Activity bar
        activity_bar = self._build_activity_bar()

        # Wrap explorer + activity bar
        explorer_container = QWidget()
        explorer_container.setObjectName("explorer_container")
        explorer_container.setStyleSheet(
            f"QWidget#explorer_container {{ background: {PALETTE['bg_alt']}; border: none; }}"
        )
        ec_layout = QHBoxLayout(explorer_container)
        ec_layout.setContentsMargins(0, 0, 0, 0)
        ec_layout.setSpacing(0)
        ec_layout.addWidget(activity_bar)
        ec_layout.addWidget(explorer_panel, 1)

        # Right: editor + terminal
        right = QSplitter(Qt.Vertical)
        right.addWidget(self.editor)
        right.addWidget(self.terminal_panel)
        right.setStretchFactor(0, 1)
        right.setStretchFactor(1, 0)
        right.setSizes([560, 240])
        right.setChildrenCollapsible(False)

        # Main horizontal splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(explorer_container)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1020])
        splitter.setChildrenCollapsible(False)
        self.setCentralWidget(splitter)

        # --- status bar ------------------------------------------------------
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._build_status_bar()
        self._status.showMessage("Ready")

        # --- actions + menus + toolbar --------------------------------------
        self._build_actions()
        self._build_menu()
        self._build_toolbar()

        # --- signals ---------------------------------------------------------
        self.explorer.file_activated.connect(self._open_path)
        self.explorer.context_action.connect(self._on_explorer_action)
        self.explorer.open_file_requested.connect(self._action_open_file)
        self.explorer.open_folder_requested.connect(self._action_open_folder)
        self.editor.current_file_changed.connect(self._on_current_file_changed)
        self.editor.dirty_state_changed.connect(self._on_dirty_changed)
        self.editor.cursor_moved.connect(self._on_cursor_moved)
        self.editor.content_loaded.connect(lambda _t: self._refresh_window_title())

        self._explorer_actions = ExplorerActions(self, on_after=self.explorer.refresh)

    # ------------------------------------------------------------------ panels

    def _build_explorer_panel(self, explorer: FileExplorer) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {PALETTE['bg_alt']}; border: none;")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("EXPLORER")
        header.setStyleSheet(f"""
            QLabel {{
                background: {PALETTE['bg_alt']};
                color: {PALETTE['fg_dim']};
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
                border-bottom: 1px solid {PALETTE['border']};
            }}
        """)
        header.setFixedHeight(35)
        layout.addWidget(header)
        layout.addWidget(explorer)
        return panel

    def _build_activity_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedWidth(_ACTIVITY_SIZE)
        bar.setStyleSheet(f"""
            QWidget {{
                background: {PALETTE['bg_sunken']};
                border-right: 1px solid {PALETTE['border']};
            }}
        """)

        layout = QVBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)

        # --- Explorer (active) ---
        self._act_btn_explorer = _ActivityButton(
            ico.icon_files(_ICON_SIZE, "#ffffff"),
            ico.icon_files(_ICON_SIZE, "#858585"),
            "Explorer", active=True,
        )
        self._act_btn_explorer.clicked.connect(lambda: None)
        layout.addWidget(self._act_btn_explorer)

        # --- Search ---
        self._act_btn_search = _ActivityButton(
            ico.icon_search(_ICON_SIZE, "#ffffff"),
            ico.icon_search(_ICON_SIZE, "#858585"),
            "Search (Ctrl+F)",
        )
        self._act_btn_search.clicked.connect(self._action_find)
        layout.addWidget(self._act_btn_search)

        # --- Source Control ---
        self._act_btn_git = _ActivityButton(
            ico.icon_git(_ICON_SIZE, "#ffffff"),
            ico.icon_git(_ICON_SIZE, "#5a5a5a"),
            "Source Control (coming soon)",
        )
        self._act_btn_git.setEnabled(False)
        layout.addWidget(self._act_btn_git)

        layout.addStretch(1)

        # --- Settings (bottom) ---
        self._act_btn_settings = _ActivityButton(
            ico.icon_gear(_ICON_SIZE, "#ffffff"),
            ico.icon_gear(_ICON_SIZE, "#5a5a5a"),
            "Settings (coming soon)",
        )
        self._act_btn_settings.setEnabled(False)
        layout.addWidget(self._act_btn_settings)

        return bar

    # ---------------------------------------------------------------- status bar

    def _build_status_bar(self) -> None:
        self._status_label = QLabel("Ln 1, Col 1")
        self._status_label.setStyleSheet(
            f"QLabel {{ color: white; padding: 0 8px; font-size: 12px; }}"
        )
        self._status.addWidget(self._status_label, 1)

        self._status_lang = QLabel("Plain Text")
        self._status_lang.setStyleSheet(
            f"QLabel {{ color: white; padding: 0 8px; font-size: 12px; }}"
        )
        self._status.addPermanentWidget(self._status_lang)

        self._status_encoding = QLabel("UTF-8")
        self._status_encoding.setStyleSheet(
            f"QLabel {{ color: white; padding: 0 8px; font-size: 12px; }}"
        )
        self._status.addPermanentWidget(self._status_encoding)

        self._status_eol = QLabel("LF")
        self._status_eol.setStyleSheet(
            f"QLabel {{ color: white; padding: 0 8px; font-size: 12px; }}"
        )
        self._status.addPermanentWidget(self._status_eol)

    # ------------------------------------------------------------------ build

    def _build_actions(self) -> None:
        s = self.style()
        self.a_new = QAction(s.standardIcon(s.StandardPixmap.SP_FileIcon), "New File", self)
        self.a_new.setShortcut(QKeySequence.New)
        self.a_new.triggered.connect(self._action_new)

        self.a_open = QAction(s.standardIcon(s.StandardPixmap.SP_DirOpenIcon), "Open File...", self)
        self.a_open.setShortcut(QKeySequence.Open)
        self.a_open.triggered.connect(self._action_open_file)

        self.a_open_folder = QAction(s.standardIcon(s.StandardPixmap.SP_DirOpenIcon), "Open Folder...", self)
        self.a_open_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.a_open_folder.triggered.connect(self._action_open_folder)

        self.a_save = QAction(s.standardIcon(s.StandardPixmap.SP_DialogSaveButton), "Save", self)
        self.a_save.setShortcut(QKeySequence.Save)
        self.a_save.triggered.connect(self._action_save)

        self.a_save_as = QAction("Save As...", self)
        self.a_save_as.setShortcut(QKeySequence.SaveAs)
        self.a_save_as.triggered.connect(self._action_save_as)

        self.a_save_all = QAction("Save All", self)
        self.a_save_all.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.a_save_all.triggered.connect(self._action_save_all)

        self.a_close = QAction("Close Tab", self)
        self.a_close.setShortcut(QKeySequence.Close)
        self.a_close.triggered.connect(self._action_close_tab)

        self.a_quit = QAction("Quit", self)
        self.a_quit.setShortcut(QKeySequence.Quit)
        self.a_quit.triggered.connect(self.close)

        self.a_run = QAction(s.standardIcon(s.StandardPixmap.SP_MediaPlay), "Run", self)
        self.a_run.setShortcut(QKeySequence("Ctrl+F5"))
        self.a_run.triggered.connect(self._action_run)

        self.a_toggle_terminal = QAction("Toggle Terminal", self)
        self.a_toggle_terminal.setShortcut(QKeySequence("Ctrl+`"))
        self.a_toggle_terminal.setCheckable(True)
        self.a_toggle_terminal.setChecked(True)
        self.a_toggle_terminal.triggered.connect(self._action_toggle_terminal)

        self.a_new_terminal = QAction("New Terminal", self)
        self.a_new_terminal.setShortcut(QKeySequence("Ctrl+Shift+`"))
        self.a_new_terminal.triggered.connect(self._action_new_terminal)

        self.a_find = QAction("Find", self)
        self.a_find.setShortcut(QKeySequence("Ctrl+F"))
        self.a_find.triggered.connect(self._action_find)

        self.a_find_replace = QAction("Find and Replace", self)
        self.a_find_replace.setShortcut(QKeySequence("Ctrl+H"))
        self.a_find_replace.triggered.connect(self._action_find_replace)

    def _build_menu(self) -> None:
        mb = self.menuBar()

        m_file = mb.addMenu("&File")
        m_file.addAction(self.a_new)
        m_file.addAction(self.a_open)
        m_file.addAction(self.a_open_folder)
        m_file.addSeparator()
        m_file.addAction(self.a_save)
        m_file.addAction(self.a_save_as)
        m_file.addAction(self.a_save_all)
        m_file.addSeparator()
        m_file.addAction(self.a_close)
        m_file.addSeparator()
        m_file.addAction(self.a_quit)

        m_edit = mb.addMenu("&Edit")
        undo = self.editor.findChildren(QAction)
        if not any(a.text() == "Undo" for a in undo):
            a = QAction("Undo", self); a.setShortcut(QKeySequence.Undo); m_edit.addAction(a)
        if not any(a.text() == "Redo" for a in undo):
            a = QAction("Redo", self); a.setShortcut(QKeySequence.Redo); m_edit.addAction(a)
        m_edit.addSeparator()
        cut = QAction("Cut", self); cut.setShortcut(QKeySequence.Cut); m_edit.addAction(cut)
        copy = QAction("Copy", self); copy.setShortcut(QKeySequence.Copy); m_edit.addAction(copy)
        paste = QAction("Paste", self); paste.setShortcut(QKeySequence.Paste); m_edit.addAction(paste)
        m_edit.addSeparator()
        sel = QAction("Select All", self); sel.setShortcut(QKeySequence.SelectAll); m_edit.addAction(sel)
        m_edit.addSeparator()
        m_edit.addAction(self.a_find)
        m_edit.addAction(self.a_find_replace)

        m_run = mb.addMenu("&Run")
        m_run.addAction(self.a_run)
        m_run.addSeparator()
        m_run.addAction(self.a_new_terminal)

        m_view = mb.addMenu("&View")
        m_view.addAction(self.explorer.toggleViewAction() if hasattr(self.explorer, "toggleViewAction") else QAction("Explorer", self))
        m_view.addAction(self.a_toggle_terminal)
        m_view.addSeparator()
        m_view.addAction(self.a_find)
        m_view.addAction(self.a_find_replace)

        m_help = mb.addMenu("&Help")
        about = QAction("About Ember IDE", self)
        about.triggered.connect(self._action_about)
        m_help.addAction(about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self.addToolBar(tb)
        tb.addAction(self.a_new)
        tb.addAction(self.a_open)
        tb.addAction(self.a_open_folder)
        tb.addSeparator()
        tb.addAction(self.a_save)
        tb.addAction(self.a_save_all)
        tb.addSeparator()
        tb.addAction(self.a_run)
        tb.addAction(self.a_toggle_terminal)
        tb.addSeparator()
        tb.addAction(self.a_find)
        tb.addSeparator()
        tb.addAction(self.a_close)

    # ------------------------------------------------------------- behaviour

    def _action_new(self) -> None:
        self.editor.new_file()
        self.editor.current_editor().widget.setFocus()

    def _action_open_file(self) -> None:
        start = str(self.explorer.root()) if self.explorer.root() else ""
        files, _ = QFileDialog.getOpenFileNames(self, "Open File", start)
        self.editor.open_files(files)

    def _action_open_folder(self) -> None:
        start = str(self.explorer.root()) if self.explorer.root() else ""
        chosen = QFileDialog.getExistingDirectory(self, "Open Folder", start)
        if chosen:
            self._open_folder_silently(chosen)

    def _action_save(self) -> None:
        if self.editor.save_current():
            self._status.showMessage("Saved", 2000)

    def _action_save_as(self) -> None:
        if self.editor.save_current_as():
            self._status.showMessage("Saved", 2000)

    def _action_save_all(self) -> None:
        if self.editor.save_all():
            self._status.showMessage("All saved", 2000)

    def _action_close_tab(self) -> None:
        self.editor.close_current()

    def _action_run(self) -> None:
        path = self.editor.current_path()
        if path and path.suffix.lower() == ".flame":
            self._status.showMessage("Running Flame AI Conversion Engine...", 5000)
            try:
                content = path.read_text(encoding="utf-8")
                from app.utils.flame_engine import detect_target_lang, get_target_path, call_ai_for_conversion, validate_and_clean_code
                target_lang = detect_target_lang(content)
                default_target_path = get_target_path(path, target_lang)

                generated_raw = call_ai_for_conversion(content, target_lang)
                code = validate_and_clean_code(generated_raw, target_lang)

                dialog = FlamePreviewDialog(
                    parent=self,
                    filename=path.name,
                    detected_lang=target_lang,
                    initial_code=code,
                    default_export_path=default_target_path
                )

                if dialog.exec() == QDialog.Accepted:
                    final_path = dialog.exported_path or default_target_path
                    self._status.showMessage(f"Flame saved/exported to {final_path.name}", 5000)
                    self.editor.open_file(final_path)

                    if dialog.run_after_export:
                        QTimer.singleShot(500, self._action_run)
                else:
                    self._status.showMessage("Flame conversion cancelled", 3000)
                return
            except Exception as exc:
                QMessageBox.warning(self, "Flame AI Engine", f"Conversion failed: {exc}")
                return

        request = self.editor.run_current()
        if request is None:
            self._status.showMessage("Nothing to run for the current file", 3000)
            return
        if not self.terminal_panel.isVisible():
            self.terminal_panel.setVisible(True)
            self.a_toggle_terminal.setChecked(True)
        self.terminal_panel.run_on_active(request)

    def _action_toggle_terminal(self) -> None:
        visible = not self.terminal_panel.isVisible()
        self.terminal_panel.setVisible(visible)
        self.a_toggle_terminal.setChecked(visible)
        if visible:
            self.terminal_panel.restart_if_needed()

    def _action_new_terminal(self) -> None:
        self.terminal_panel.new_tab()
        if not self.terminal_panel.isVisible():
            self.terminal_panel.setVisible(True)
            self.a_toggle_terminal.setChecked(True)

    def _action_find(self) -> None:
        self.editor.toggle_search()
        if self.editor._search_bar.isVisible():
            self.editor._search_input.setFocus()

    def _action_find_replace(self) -> None:
        self.editor.toggle_search()
        if self.editor._search_bar.isVisible():
            self.editor._replace_input.setFocus()

    def _action_about(self) -> None:
        QMessageBox.about(
            self, "About Ember IDE",
            "<b>Ember IDE</b> v0.1.0<br><br>"
            "A lightweight, cross-platform code editor.<br><br>"
            "Built with Python, PyQt5, and QScintilla.",
        )

    def _open_path(self, path: Path) -> None:
        if self.editor.open_file(path):
            self._status.showMessage(f"Opened {path.name}", 2000)

    def _open_folder_silently(self, path: str) -> None:
        p = normalize(path)
        self.explorer.set_root(p)
        self._status.showMessage(f"Folder: {p}", 2000)

    def _on_explorer_action(self, action: str, path: Path) -> None:
        if action == "new_file":
            created = self._explorer_actions.new_file(path if path.is_dir() else path.parent)
            if created:
                self.explorer.select(created)
        elif action == "new_folder":
            created = self._explorer_actions.new_folder(path if path.is_dir() else path.parent)
            if created:
                self.explorer.select(created)
        elif action == "rename":
            new_path = self._explorer_actions.rename(path)
            if new_path:
                self.explorer.select(new_path)
        elif action == "delete":
            self._explorer_actions.delete(path)

    def _on_current_file_changed(self, path) -> None:
        self._refresh_window_title()

    def _on_dirty_changed(self, dirty: bool) -> None:
        self._refresh_window_title()

    def _on_cursor_moved(self, line: int, col: int) -> None:
        editor = self.editor.current_editor()
        lexer = editor.lexer_name() if editor else "—"
        self._status_label.setText(f"Ln {line}, Col {col}")
        lang = lexer.replace("QsciLexer", "") if editor else "Plain Text"
        self._status_lang.setText(lang)

    def _refresh_window_title(self) -> None:
        path = self.editor.current_path()
        dirty = self.editor.has_unsaved()
        name = path.name if path else "Untitled"
        prefix = "● " if dirty else ""
        self.setWindowTitle(f"{prefix}{name} — Ember IDE")

    # ------------------------------------------------------------ close hook

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.editor.has_unsaved():
            choice = QMessageBox.question(
                self, "Unsaved changes",
                "You have unsaved changes. Quit anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice != QMessageBox.Yes:
                event.ignore()
                return
        if not self.editor.close_all():
            event.ignore()
            return
        self.terminal_panel.shutdown()
        event.accept()


# ---------------------------------------------------------------------------
# Activity bar button — painted icon, left-border active indicator
# ---------------------------------------------------------------------------

class _ActivityButton(QPushButton):
    """A single activity-bar button with an icon and active/inactive state."""

    def __init__(self, active_pixmap, inactive_pixmap,
                 tooltip: str, active: bool = False) -> None:
        super().__init__()
        self.setFixedSize(_ACTIVITY_SIZE, _ACTIVITY_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setChecked(active)
        self._active_icon = QIcon(active_pixmap)
        self._inactive_icon = QIcon(inactive_pixmap)
        self._active = active
        self._update_visual()
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self._active = self.isChecked()
        self._update_visual()

    def _update_visual(self) -> None:
        if self._active:
            self.setIcon(self._active_icon)
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {PALETTE['accent']};
                    border: none;
                    border-left: 2px solid {PALETTE['accent']};
                    border-radius: 0;
                    padding: 0;
                    margin: 0;
                }}
            """)
        else:
            self.setIcon(self._inactive_icon)
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-left: 2px solid transparent;
                    border-radius: 0;
                    padding: 0;
                    margin: 0;
                }}
                QPushButton:hover {{
                    background: {PALETTE['panel']};
                }}
            """)


# ---------------------------------------------------------------------------
# TerminalPanel — multi-tab terminal container
# ---------------------------------------------------------------------------

class TerminalPanel(QWidget):
    """A multi-tab container for :class:`TerminalWidget` instances."""

    def __init__(self, explorer: "FileExplorer | None" = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._explorer = explorer

        self.setStyleSheet(f"""
            QWidget {{ background: {PALETTE['bg_sunken']}; border: none; }}
            QTabWidget::pane {{ border: none; background: {PALETTE['bg_sunken']}; }}
        """)

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setStyleSheet(f"""
            QTabBar {{
                background: {PALETTE['bg_alt']};
                border-bottom: 1px solid {PALETTE['border']};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {PALETTE['fg_dim']};
                padding: 6px 12px;
                border: none;
                border-bottom: 2px solid transparent;
                min-width: 80px;
            }}
            QTabBar::tab:selected {{
                background: {PALETTE['bg_sunken']};
                color: {PALETTE['fg']};
                border-bottom: 2px solid {PALETTE['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                background: {PALETTE['panel']};
                color: {PALETTE['fg']};
            }}
        """)
        self._tabs.tabCloseRequested.connect(self._on_close)
        self._tabs.currentChanged.connect(lambda _i: self._focus_active())

        plus = QToolBar()
        plus.setMovable(False)
        plus.setFloatable(False)
        plus.setIconSize(QSize(14, 14))
        plus.setStyleSheet(f"""
            QToolBar {{
                background: {PALETTE['bg_alt']};
                border-bottom: 1px solid {PALETTE['border']};
                spacing: 0; padding: 0;
            }}
            QToolButton {{
                background: transparent;
                color: {PALETTE['fg_dim']};
                padding: 4px 8px;
                border-radius: 3px;
            }}
            QToolButton:hover {{
                background: {PALETTE['panel']};
                color: {PALETTE['fg']};
            }}
        """)
        a_new = QAction(_icon(ico.icon_plus(14, "#858585")), "New Terminal", self)
        a_new.triggered.connect(self.new_tab)
        plus.addAction(a_new)
        self._tabs.setCornerWidget(plus, Qt.TopRightCorner)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self._tabs)

        self.new_tab()

    def _default_cwd(self) -> Path:
        if self._explorer is not None:
            root = self._explorer.root()
            if root is not None:
                return root
        return Path.home()

    def new_tab(self) -> TerminalWidget:
        cwd = self._default_cwd()
        widget = TerminalWidget(cwd=cwd)
        idx = self._tabs.addTab(widget, f"Terminal {self._tabs.count() + 1}")
        self._tabs.setCurrentIndex(idx)
        widget.closed.connect(lambda w: self._close_widget(w))
        widget.focus_input()
        return widget

    def _focus_active(self) -> None:
        w = self.current_widget()
        if w is not None:
            w.focus_input()

    def current_widget(self) -> TerminalWidget | None:
        w = self._tabs.currentWidget()
        return w if isinstance(w, TerminalWidget) else None

    def run_on_active(self, request) -> None:
        widget = self.current_widget() or self.new_tab()
        idx = self._tabs.indexOf(widget)

        import re
        cmd = request.command.strip()
        matches = re.findall(r'["\']?([^"\'\s]+\.[a-zA-Z0-9]+)["\']?', cmd)
        file_name = Path(matches[-1]).name if matches else (cmd.split()[-1] if cmd.split() else "process")

        if idx >= 0:
            self._tabs.setTabText(idx, f"Terminal {idx + 1} — {file_name}")
            self._tabs.setTabToolTip(idx, f"Running: {request.command}\nCWD: {request.cwd}")

        widget.run(request)
        widget.focus_input()

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        super().setVisible(visible)
        if not visible:
            for i in range(self._tabs.count()):
                w = self._tabs.widget(i)
                if isinstance(w, TerminalWidget):
                    w.stop()

    def restart_if_needed(self) -> None:
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, TerminalWidget) and not w.is_running():
                w.run_shell()

    def shutdown(self) -> None:
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, TerminalWidget):
                w.stop()

    def _on_close(self, index: int) -> None:
        w = self._tabs.widget(index)
        if isinstance(w, TerminalWidget):
            w.stop()
        self._tabs.removeTab(index)
        w.deleteLater() if w else None
        if self._tabs.count() == 0:
            self.new_tab()

    def _close_widget(self, widget: TerminalWidget) -> None:
        idx = self._tabs.indexOf(widget)
        if idx >= 0:
            self._on_close(idx)


# ---------------------------------------------------------------------------
# FlamePreviewDialog — VS Code-inspired AI generated code review & edit
# ---------------------------------------------------------------------------

class FlamePreviewDialog(QDialog):
    """Modern VS Code-inspired interactive dialog for reviewing, editing, and exporting AI generated code."""

    def __init__(self, parent: QWidget | None, filename: str, detected_lang: str, initial_code: str, default_export_path: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Flame AI Conversion Preview — {filename}")
        self.resize(750, 550)
        self.setMinimumSize(500, 400)

        self.default_export_path = default_export_path
        self.exported_path = None
        self.run_after_export = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Detected language line
        info_layout = QHBoxLayout()
        info_label = QLabel(f"<b>Target Language:</b> <span style='color: {PALETTE['success']};'>{detected_lang.upper()}</span>")
        info_label.setStyleSheet(f"font-size: 13px; color: {PALETTE['fg']};")
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Subtitle instructions
        sub_label = QLabel("Preview and edit the AI-generated code. Use 'Export' to save elsewhere, or 'Save & Run' to execute.")
        sub_label.setWordWrap(True)
        sub_label.setStyleSheet(f"color: {PALETTE['fg_dim']}; font-size: 11px;")
        layout.addWidget(sub_label)

        # Edit text widget (preview & edit)
        self.editor = QTextEdit()
        self.editor.setPlainText(initial_code)
        self.editor.setLineWrapMode(QTextEdit.NoWrap)
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                background: {PALETTE['bg_sunken']};
                color: {PALETTE['fg']};
                border: 1px solid {PALETTE['border']};
                border-radius: 4px;
                font-family: 'Cascadia Code', 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monospace';
                font-size: 12px;
                padding: 8px;
            }}
            QTextEdit:focus {{
                border-color: {PALETTE['accent']};
            }}
        """)
        layout.addWidget(self.editor, 1)

        # Buttons layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("welcomeBtnSecondary")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_export = QPushButton("Export...")
        self.btn_export.setObjectName("welcomeBtnSecondary")
        self.btn_export.clicked.connect(self._on_export)

        self.btn_run = QPushButton("Save & Run")
        self.btn_run.setObjectName("welcomeBtnPrimary")
        self.btn_run.clicked.connect(self._on_run)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_run)

        layout.addLayout(btn_layout)

    def _on_export(self) -> None:
        start_dir = str(self.default_export_path.parent)
        suggested = self.default_export_path.name
        chosen, _ = QFileDialog.getSaveFileName(self, "Export Flame Generated Code", f"{start_dir}/{suggested}")
        if chosen:
            self.default_export_path = Path(chosen)
            self._save_to_path()
            QMessageBox.information(self, "Flame AI Engine", f"Code exported and saved successfully to:\n{chosen}")
            self.exported_path = self.default_export_path
            self.accept()

    def _on_run(self) -> None:
        self._save_to_path()
        self.exported_path = self.default_export_path
        self.run_after_export = True
        self.accept()

    def _save_to_path(self) -> None:
        edited_code = self.editor.toPlainText()
        from app.utils.file_utils import safe_write
        safe_write(self.default_export_path, edited_code)
