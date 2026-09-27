"""Main window — assembles the editor + explorer + terminal, wires menu/toolbar/statusbar."""
from __future__ import annotations

from pathlib import Path
import re
import sys

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QIcon, QKeySequence, QFont
from PyQt5.QtWidgets import (
    QAction, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QSplitter, QStatusBar, QTabWidget, QToolBar,
    QToolButton, QVBoxLayout, QWidget, QDialog, QTextEdit, QInputDialog,
)
from PyQt5.QtCore import QSettings

from app.editor.tabbed_editor import TabbedEditor
from app.explorer.explorer_actions import ExplorerActions
from app.explorer.file_explorer import FileExplorer
from app.theme.dark_theme import PALETTE
from app.theme import icons as ico
from app.utils.file_utils import normalize
from app.utils.terminal import RunRequest, TerminalWidget, detect_shell
from app.services import (
    ExtensionManager, GitService, LanguageTools, PackageService, TaskService,
    TestService, WorkspaceSearch, run_command,
)
from app.feature_dialogs import (
    GitDialog, PackageDialog, ProblemsDialog, SettingsDialog,
    WorkspaceSearchDialog, CommandListDialog, command_string,
)
from app.lsp.bridge import LspBridge, uri_path


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
        self.settings = QSettings()
        self._extension_manager = ExtensionManager(None)
        self.lsp_bridge = LspBridge(self)
        self._lsp_diagnostics: dict[str, list] = {}

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
        self.lsp_bridge.completion_ready.connect(self._on_lsp_completion)
        self.lsp_bridge.diagnostics_ready.connect(self._on_lsp_diagnostics)
        self.lsp_bridge.definition_ready.connect(self._on_lsp_definition)
        self.lsp_bridge.status_changed.connect(lambda text: self._status.showMessage(text, 3000))

        self._explorer_actions = ExplorerActions(self, on_after=self.explorer.refresh)
        self._apply_settings()

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
            ico.icon_git(_ICON_SIZE, "#858585"),
            "Source Control",
        )
        self._act_btn_git.clicked.connect(self._action_git)
        layout.addWidget(self._act_btn_git)

        layout.addStretch(1)

        # --- Settings (bottom) ---
        self._act_btn_settings = _ActivityButton(
            ico.icon_gear(_ICON_SIZE, "#ffffff"),
            ico.icon_gear(_ICON_SIZE, "#858585"),
            "Settings",
        )
        self._act_btn_settings.clicked.connect(self._action_settings)
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

        self.a_workspace_search = QAction("Search Workspace...", self)
        self.a_workspace_search.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.a_workspace_search.triggered.connect(self._action_workspace_search)

        self.a_go_definition = QAction("Go to Definition", self)
        self.a_go_definition.setShortcut(QKeySequence("F12"))
        self.a_go_definition.triggered.connect(self._action_go_definition)

        self.a_rename_symbol = QAction("Rename Symbol...", self)
        self.a_rename_symbol.setShortcut(QKeySequence("F2"))
        self.a_rename_symbol.triggered.connect(self._action_rename_symbol)

        self.a_complete = QAction("Trigger Suggestion", self)
        self.a_complete.setShortcut(QKeySequence("Ctrl+Space"))
        self.a_complete.triggered.connect(self._action_complete)

        self.a_problems = QAction("Check File", self)
        self.a_problems.setShortcut(QKeySequence("F8"))
        self.a_problems.triggered.connect(self._action_problems)

        self.a_toggle_breakpoint = QAction("Toggle Breakpoint", self)
        self.a_toggle_breakpoint.setShortcut(QKeySequence("F9"))
        self.a_toggle_breakpoint.triggered.connect(self._action_toggle_breakpoint)

        self.a_debug = QAction("Debug Current File", self)
        self.a_debug.setShortcut(QKeySequence("Ctrl+F9"))
        self.a_debug.triggered.connect(self._action_debug)

        self.a_task = QAction("Run Task...", self)
        self.a_task.triggered.connect(self._action_task)

        self.a_test = QAction("Run Tests", self)
        self.a_test.triggered.connect(self._action_test)

        self.a_package = QAction("Package Manager...", self)
        self.a_package.triggered.connect(self._action_package)

        self.a_git = QAction("Source Control...", self)
        self.a_git.triggered.connect(self._action_git)

        self.a_settings = QAction("Settings...", self)
        self.a_settings.triggered.connect(self._action_settings)

        self.a_extensions = QAction("Extensions...", self)
        self.a_extensions.triggered.connect(self._action_extensions)

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
        m_edit.addAction(self.a_workspace_search)
        m_edit.addSeparator()
        m_edit.addAction(self.a_complete)
        m_edit.addAction(self.a_go_definition)
        m_edit.addAction(self.a_rename_symbol)

        m_run = mb.addMenu("&Run")
        m_run.addAction(self.a_run)
        m_run.addAction(self.a_debug)
        m_run.addAction(self.a_test)
        m_run.addAction(self.a_task)
        m_run.addSeparator()
        m_run.addAction(self.a_new_terminal)

        m_view = mb.addMenu("&View")
        m_view.addAction(self.explorer.toggleViewAction() if hasattr(self.explorer, "toggleViewAction") else QAction("Explorer", self))
        m_view.addAction(self.a_toggle_terminal)
        m_view.addSeparator()
        m_view.addAction(self.a_find)
        m_view.addAction(self.a_find_replace)

        m_tools = mb.addMenu("&Tools")
        m_tools.addAction(self.a_problems)
        m_tools.addAction(self.a_toggle_breakpoint)
        m_tools.addSeparator()
        m_tools.addAction(self.a_package)
        m_tools.addAction(self.a_extensions)
        m_tools.addSeparator()
        m_tools.addAction(self.a_git)
        m_tools.addAction(self.a_settings)

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
        tb.addAction(self.a_workspace_search)
        tb.addAction(self.a_problems)
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

    def _project_root(self) -> Path | None:
        return self.explorer.root() or (
            self.editor.current_path().parent if self.editor.current_path() else None
        )

    def _run_in_terminal(self, argv: list[str], cwd: Path | None = None) -> None:
        root = cwd or self._project_root() or Path.home()
        if not self.terminal_panel.isVisible():
            self.terminal_panel.setVisible(True)
            self.a_toggle_terminal.setChecked(True)
        self.terminal_panel.run_on_active(
            RunRequest(command=command_string(argv), cwd=root)
        )

    def _action_git(self) -> None:
        service = GitService(self._project_root())
        if not service.available:
            QMessageBox.information(
                self, "Source Control",
                "Open a folder inside a Git repository to use Source Control.",
            )
            return
        GitDialog(service, self, on_changed=self.explorer.refresh).exec()

    def _action_settings(self) -> None:
        SettingsDialog(self.settings, self, on_apply=self._apply_settings).exec()

    def _apply_settings(self) -> None:
        try:
            size = int(self.settings.value("editor/font_size", 10))
            tab_width = int(self.settings.value("editor/tab_width", 4))
            autocomplete = self.settings.value("editor/autocomplete", True, type=bool)
        except (TypeError, ValueError):
            size, tab_width, autocomplete = 10, 4, True
        for item in getattr(self.editor, "_items", []):
            widget = item.editor.widget
            widget.setTabWidth(tab_width)
            font = QFont(widget.font())
            font.setPointSize(size)
            widget.setFont(font)
            widget.setAutoCompletionSource(
                widget.AcsAll if autocomplete else widget.AcsNone
            )

    def _action_workspace_search(self) -> None:
        WorkspaceSearchDialog(
            self._project_root(), self, on_open=self._open_search_match
        ).exec()

    def _open_search_match(self, match) -> None:
        if self.editor.open_file(match.path):
            self.editor.goto_line(match.line, max(0, match.column - 1))

    def _action_problems(self) -> None:
        path = self.editor.current_path()
        editor = self.editor.current_editor()
        if path is None or editor is None:
            QMessageBox.information(self, "Problems", "Open a saved source file first.")
            return
        problems = LanguageTools.python_diagnostics(path, editor.text)
        for diagnostic in self._lsp_diagnostics.get(path.resolve().as_uri(), []):
            problems.append((diagnostic.range.start.line + 1, diagnostic.message))
        ProblemsDialog(problems, self).exec()

    def _current_word(self) -> str:
        editor = self.editor.current_editor()
        if editor is None:
            return ""
        line, col = editor.widget.getCursorPosition()
        try:
            return editor.widget.wordAtLineIndex(line, col)
        except AttributeError:
            text = editor.widget.text(line)
            match = re.search(r"[A-Za-z_][A-Za-z0-9_]*", text[:col] + " ")
            return match.group(0) if match else ""

    def _action_go_definition(self) -> None:
        word = self._current_word()
        editor = self.editor.current_editor()
        if not word or editor is None:
            return
        path = self.editor.current_path()
        if path is not None:
            line0, column0 = editor.widget.getCursorPosition()
            self.lsp_bridge.definition(path, line0, column0)
        line = LanguageTools.definition(editor.text, word)
        if line:
            self.editor.goto_line(line)
            return
        root = self._project_root()
        if root:
            pattern = rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(word)}\b"
            matches = WorkspaceSearch(root).search(pattern, regex=True)
            if matches:
                self._open_search_match(matches[0])
                return
        QMessageBox.information(self, "Go to Definition", f"No definition found for '{word}'.")

    def _action_rename_symbol(self) -> None:
        editor = self.editor.current_editor()
        old = self._current_word()
        if editor is None or not old:
            return
        new, accepted = QInputDialog.getText(self, "Rename Symbol", f"Rename '{old}' to:")
        new = new.strip()
        if not accepted or not new or new == old or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", new):
            return
        root = self._project_root()
        scope = QMessageBox.question(
            self, "Rename Symbol",
            f"Replace '{old}' throughout the workspace?\nChoose No to change only the current file.",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if scope == QMessageBox.Cancel:
            return
        from app.utils.file_utils import safe_write
        pattern = re.compile(rf"\b{re.escape(old)}\b")
        if scope == QMessageBox.Yes and root:
            for path in WorkspaceSearch(root).iter_files() or ():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    replaced = pattern.sub(new, text)
                    if replaced != text:
                        safe_write(path, replaced)
                        if path == self.editor.current_path():
                            editor.text = replaced
                except OSError:
                    continue
        else:
            editor.text = pattern.sub(new, editor.text)
        self._status.showMessage(f"Renamed {old} to {new}", 3000)

    def _action_complete(self) -> None:
        editor = self.editor.current_editor()
        if editor is not None:
            editor.show_local_completion()
            path = self.editor.current_path()
            if path is not None:
                line, column = editor.widget.getCursorPosition()
                self.lsp_bridge.complete(path, line, column)

    def _on_lsp_completion(self, items) -> None:
        editor = self.editor.current_editor()
        if editor is None or not items:
            return
        labels = [item.insert_text or item.label for item in items if item.label]
        if labels:
            editor.widget.showUserList(2, labels[:200])

    def _on_lsp_diagnostics(self, uri: str, diagnostics) -> None:
        self._lsp_diagnostics[uri] = diagnostics
        if diagnostics:
            self._status.showMessage(f"{len(diagnostics)} language-server problem(s)", 4000)

    def _on_lsp_definition(self, locations) -> None:
        if not locations:
            return
        location = locations[0]
        path = uri_path(location.uri)
        if path and self.editor.open_file(path):
            self.editor.goto_line(location.range.start.line + 1, location.range.start.character)

    def _action_toggle_breakpoint(self) -> None:
        editor = self.editor.current_editor()
        if editor is not None:
            editor.toggle_breakpoint_current()

    def _action_debug(self) -> None:
        path = self.editor.current_path()
        if path is None:
            QMessageBox.information(self, "Debugger", "Save the current file before debugging.")
            return
        if path.suffix.lower() == ".py":
            self._run_in_terminal([sys.executable, "-m", "pdb", str(path)], path.parent)
        else:
            QMessageBox.information(
                self, "Debugger",
                "The interactive debugger currently supports Python files. "
                "Use Toggle Breakpoint and Debug Current File to start pdb.",
            )

    def _action_task(self) -> None:
        tasks = TaskService(self._project_root()).discover()
        if not tasks:
            QMessageBox.information(
                self, "Tasks",
                "No tasks found. Add commands to .ember/tasks.json, package.json scripts, or a Makefile.",
            )
            return
        dialog = CommandListDialog("Run Task", tasks, self)
        if dialog.exec() == QDialog.Accepted and dialog.selected():
            _name, command = dialog.selected()
            self._run_in_terminal(["sh", "-c", command] if sys.platform != "win32" else ["cmd", "/c", command])

    def _action_test(self) -> None:
        command = TestService.command(self._project_root(), self.editor.current_path())
        if not command:
            QMessageBox.information(self, "Tests", "No Python or npm test setup was detected.")
            return
        self._run_in_terminal(command)

    def _action_package(self) -> None:
        root = self._project_root()
        ecosystem = PackageService.ecosystem(root)
        dialog = PackageDialog(ecosystem, self)
        if dialog.exec() == QDialog.Accepted:
            action, package = dialog.request()
            if action != "list" and not package:
                QMessageBox.information(self, "Package Manager", "Enter a package name.")
                return
            self._run_in_terminal(PackageService.command(ecosystem, action, package), root)

    def _action_extensions(self) -> None:
        root = self._project_root()
        self._extension_manager = ExtensionManager(root)
        extensions = self._extension_manager.load()
        if not extensions:
            QMessageBox.information(
                self, "Extensions",
                "No extensions found. Put Python extensions in .ember/extensions/.",
            )
            return
        CommandListDialog("Installed Extensions", extensions, self).exec()

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
        self._extension_manager = ExtensionManager(p)
        self._extension_manager.load()
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
        if path:
            editor = self.editor.current_editor()
            if editor:
                self.lsp_bridge.open_document(path, editor.text)

    def _on_dirty_changed(self, dirty: bool) -> None:
        self._refresh_window_title()
        path = self.editor.current_path()
        editor = self.editor.current_editor()
        if path and editor:
            self.lsp_bridge.open_document(path, editor.text)

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
        self.lsp_bridge.shutdown()
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
                    background: {PALETTE['panel']};
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
        self.setObjectName("terminal_panel")

        self.setStyleSheet(f"""
            QWidget#terminal_panel {{
                background: {PALETTE['bg_sunken']};
                border: none;
            }}
            QTabWidget::pane {{
                border: none;
                background: {PALETTE['bg_sunken']};
            }}
        """)

        # VS Code's panel header: the panel type is separate from the
        # individual terminal sessions shown in the tab row below it.
        panel_header = QWidget()
        panel_header.setObjectName("terminal_panel_header")
        panel_header.setFixedHeight(35)
        panel_header.setStyleSheet(f"""
            QWidget#terminal_panel_header {{
                background: {PALETTE['bg_alt']};
                border-bottom: 1px solid {PALETTE['border']};
            }}
            QLabel#terminal_panel_title {{
                color: {PALETTE['fg']};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.7px;
            }}
            QLabel#terminal_panel_mode {{
                color: {PALETTE['fg_dim']};
                font-size: 11px;
                padding: 9px 10px 8px;
            }}
            QToolButton#terminal_panel_control {{
                background: transparent;
                color: {PALETTE['fg_dim']};
                border: none;
                padding: 5px;
                min-width: 26px;
                min-height: 26px;
            }}
            QToolButton#terminal_panel_control:hover {{
                color: {PALETTE['fg']};
                background: {PALETTE['panel']};
            }}
        """)
        header_layout = QHBoxLayout(panel_header)
        header_layout.setContentsMargins(12, 0, 6, 0)
        header_layout.setSpacing(0)

        title = QLabel("TERMINAL")
        title.setObjectName("terminal_panel_title")
        header_layout.addWidget(title)
        mode = QLabel("  ")
        mode.setObjectName("terminal_panel_mode")
        header_layout.addStretch(1)

        self._stop_control = QToolButton()
        self._stop_control.setObjectName("terminal_panel_control")
        self._stop_control.setIcon(_icon(ico.icon_stop(14, PALETTE["fg_dim"])))
        self._stop_control.setToolTip("Interrupt the active terminal process")
        self._stop_control.clicked.connect(self._stop_active)
        header_layout.addWidget(self._stop_control)

        new_control = QToolButton()
        new_control.setObjectName("terminal_panel_control")
        new_control.setIcon(_icon(ico.icon_plus(14, PALETTE["fg_dim"])))
        new_control.setToolTip("New terminal")
        new_control.clicked.connect(self.new_tab)
        header_layout.addWidget(new_control)

        close_control = QToolButton()
        close_control.setObjectName("terminal_panel_control")
        close_control.setIcon(_icon(ico.icon_close(12, PALETTE["fg_dim"])))
        close_control.setToolTip("Close panel")
        close_control.clicked.connect(lambda: self.setVisible(False))
        header_layout.addWidget(close_control)

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.setUsesScrollButtons(False)
        self._tabs.setStyleSheet(f"""
            QTabWidget {{
                background: {PALETTE['bg_sunken']};
            }}
            QTabBar {{
                background: {PALETTE['bg_alt']};
                border-bottom: 1px solid {PALETTE['border']};
            }}
            QTabBar::tab {{
                background: transparent;
                color: {PALETTE['fg_dim']};
                padding: 7px 12px;
                border: none;
                border-bottom: 2px solid transparent;
                min-width: 76px;
                max-width: 240px;
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
            QTabBar::close-button {{
                image: none;
                subcontrol-position: right;
                padding: 2px;
                width: 14px;
                height: 14px;
            }}
            QTabBar::close-button:hover {{
                background: {PALETTE['panel']};
                border-radius: 3px;
            }}
        """)
        self._tabs.tabCloseRequested.connect(self._on_close)
        self._tabs.currentChanged.connect(lambda _i: self._focus_active())

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(panel_header)
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
        shell_name = Path(detect_shell()[0]).stem or "shell"
        idx = self._tabs.addTab(widget, shell_name)
        self._tabs.setCurrentIndex(idx)
        widget.closed.connect(lambda w: self._close_widget(w))
        widget.focus_input()
        return widget

    def _focus_active(self) -> None:
        w = self.current_widget()
        if w is not None:
            w.focus_input()

    def _stop_active(self) -> None:
        widget = self.current_widget()
        if widget is not None:
            widget.interrupt()

    def current_widget(self) -> TerminalWidget | None:
        w = self._tabs.currentWidget()
        return w if isinstance(w, TerminalWidget) else None

    def run_on_active(self, request) -> None:
        widget = self.current_widget() or self.new_tab()
        idx = self._tabs.indexOf(widget)

        import re
        cmd = (request.command if hasattr(request, "command") else str(request)).strip()
        matches = re.findall(r'["\']?([^"\'\s]+\.[a-zA-Z0-9]+)["\']?', cmd)
        file_name = Path(matches[-1]).name if matches else (cmd.split()[-1] if cmd.split() else "process")

        if idx >= 0:
            shell_name = self._tabs.tabText(idx).split(" — ", 1)[0] or "shell"
            self._tabs.setTabText(idx, f"{shell_name} — {file_name}")
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
