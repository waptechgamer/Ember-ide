"""Phase 1 + 2 smoke test — runs headless via the offscreen Qt platform plugin."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QCoreApplication, QTimer
from PyQt5.QtWidgets import QApplication

from app.editor.code_editor import CodeEditor
from app.editor.tabbed_editor import TabbedEditor
from app.explorer.explorer_actions import ExplorerActions
from app.explorer.file_explorer import FileExplorer
from app.main_window import MainWindow
from app.theme.dark_theme import apply_dark_theme, pick_lexer_class
from app.utils.file_utils import is_hidden, normalize, safe_new_dir, safe_new_file, safe_write
from app.utils.terminal import (
    RunRequest, _Format, _parse_ansi, build_prompt, clear_command, detect_shell,
    is_linux, is_macos, is_windows, pick_monospace_font, shorten_home, strip_ansi,
)


def main() -> int:
    print("Importing modules…")
    print("  utils, theme, code_editor, tabbed_editor, file_explorer, "
          "explorer_actions, main_window, terminal: OK")

    QCoreApplication.setOrganizationName("Ember")
    QCoreApplication.setApplicationName("Ember IDE")

    app = QApplication.instance() or QApplication(sys.argv)
    apply_dark_theme(app)

    print("Constructing MainWindow…")
    w = MainWindow()
    w.show()

    assert isinstance(w.editor, TabbedEditor)
    assert isinstance(w.explorer, FileExplorer)
    assert w.editor.count() >= 1, "editor should start with one tab"
    assert w.terminal_panel.isVisible(), "terminal should be visible by default"
    assert w.terminal_panel._tabs.count() >= 1, "terminal should have at least one tab"
    print(f"  editor tabs: {w.editor.count()}")
    print(f"  explorer root: {w.explorer.root()}")
    print(f"  terminal tabs: {w.terminal_panel._tabs.count()}")

    ed = w.editor.current_editor()
    assert ed is not None
    ed.text = 'print("hello ember")\n'
    assert "hello ember" in ed.text
    print("  editor text set/read OK")

    # Lexer detection
    assert pick_lexer_class(".py").__name__ == "QsciLexerPython"
    assert pick_lexer_class(".xyz") is None
    print("  lexer detection OK")

    # ANSI stripping
    assert strip_ansi("\x1B[31mred\x1B[0m") == "red"
    assert strip_ansi("plain") == "plain"
    print("  ansi strip OK")

    # ANSI rendering — colors and 256-color
    fmt = _Format()
    spans = _parse_ansi("\x1B[31mERR\x1B[0m \x1B[32mOK\x1B[0m \x1B[38;5;196m256\x1B[0m", fmt)
    # Expected: [ERR, ' ', OK, ' ', '256'] = 5 spans
    assert len(spans) == 5, f"expected 5 spans, got {len(spans)}"
    text_only = "".join(t for t, _ in spans)
    assert text_only == "ERR OK 256", f"text: {text_only!r}"
    print(f"  ansi render: {len(spans)} spans, text reconstructed cleanly")

    # OS detection picks exactly one branch
    branches = sum(bool(x) for x in (is_windows(), is_macos(), is_linux()))
    assert branches == 1, f"OS detection ambiguous: {branches} branches true"
    print(f"  OS detect: win={is_windows()} mac={is_macos()} linux={is_linux()}")

    # Prompt builders
    plain, rich = build_prompt(Path.home())
    assert plain and len(rich) >= 1
    if is_windows():
        assert plain.rstrip().endswith(">"), f"windows prompt should end with '>': {plain!r}"
    elif is_macos():
        assert plain.rstrip().endswith("%"), f"macos prompt should end with '%': {plain!r}"
    else:
        assert plain.rstrip().endswith("$"), f"linux prompt should end with '$': {plain!r}"
    assert any("~" in t for t, _ in rich), "home should be shortened to ~ in the prompt"
    print(f"  prompt for {sys.platform}: {plain!r}")

    # clear command
    if is_windows():
        assert clear_command() == "cls"
    else:
        assert clear_command() == "clear"
    print(f"  clear command: {clear_command()!r}")

    # Font picker
    font = pick_monospace_font(11)
    assert font.pointSize() == 11
    print(f"  monospace font: {font.family()} {font.pointSize()}pt")

    # Shell detection
    argv = detect_shell()
    assert argv and isinstance(argv, list) and argv[0]
    print(f"  detected shell: {argv[0]}")

    # File utils round-trip
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "sub" / "a.txt"
        safe_write(p, "abc\n")
        assert p.read_text(encoding="utf-8") == "abc\n"
        safe_new_file(p.with_name("b.txt"))
        safe_new_dir(p.with_name("d"))
        assert is_hidden(Path(td) / ".hidden")
        assert normalize("~").exists()
    print("  file_utils OK")

    # Open a real file via the editor API (keep the temp dir alive for run)
    sample_dir = tempfile.mkdtemp(prefix="ember_test_")
    sample = Path(sample_dir) / "sample.py"
    sample.write_text('print("from disk")\n', encoding="utf-8")
    w.editor.open_file(sample)
    assert w.editor.current_path() == normalize(sample)
    print("  editor.open_file OK")

    # Run the just-opened file via the Run action — exercises the
    # RunRequest path end to end. We capture terminal output via the
    # widget's _view plain text.
    request = w.editor.run_current()
    assert request is not None
    assert "sample.py" in request.command
    assert request.cwd.is_dir(), f"cwd vanished: {request.cwd}"
    print(f"  run_current() OK: {request.command!r}")

    # Toggle terminal visibility
    assert w.terminal_panel.isVisible() is True
    w._action_toggle_terminal()
    assert w.terminal_panel.isVisible() is False
    w._action_toggle_terminal()
    assert w.terminal_panel.isVisible() is True
    print("  toggle terminal OK")

    # Multiple terminal tabs
    initial = w.terminal_panel._tabs.count()
    w._action_new_terminal()
    assert w.terminal_panel._tabs.count() == initial + 1
    print("  new terminal tab OK")

    # Exercise the _append_plain(spans=...) path that crashed previously.
    tw = w.terminal_panel.current_widget()
    assert tw is not None
    tw._append_plain("prompt> ", spans=[("prompt> ", "#9cdcfe"), ("cmd\n", "#d4d4d4")])
    view_text = tw._view.toPlainText()
    assert "prompt> " in view_text and "cmd" in view_text
    print("  _append_plain(spans=...) OK")

    # Explorer should start empty (no auto-open of $HOME anymore).
    assert w.explorer.root() is None, f"explorer should be empty, got {w.explorer.root()}"
    # Header should be hidden (no "Name / Size / Type" row).
    assert w.explorer._view.isHeaderHidden(), "explorer header should be hidden"
    # Placeholder should be visible until we set a root.
    assert w.explorer._placeholder.isVisible(), "placeholder should be visible at startup"
    assert not w.explorer._view.isVisible(), "tree view should be hidden when placeholder is up"
    print("  explorer starts empty with placeholder OK")

    # _default_cwd falls back to home when no folder is open.
    assert w.terminal_panel._default_cwd() == Path.home()
    print("  default cwd = home when explorer empty")

    # Set an explorer root, then _default_cwd should follow it.
    sample = tempfile.mkdtemp(prefix="ember_proj_")
    w.explorer.set_root(sample)
    assert w.terminal_panel._default_cwd() == normalize(sample)
    # After set_root, placeholder should be hidden and tree visible.
    assert not w.explorer._placeholder.isVisible(), "placeholder should hide after set_root"
    assert w.explorer._view.isVisible(), "tree should be visible after set_root"
    # The root index should have at least one row (the dir itself, visible after expand).
    root_idx = w.explorer._model.index(sample)
    assert root_idx.isValid()
    print(f"  default cwd follows explorer: {normalize(sample).name}")

    # _predictive_cd_update resolves relative and absolute paths
    from app.utils.terminal import TerminalWidget
    tw_test = TerminalWidget(cwd=Path.home())
    base = tw_test._display_cwd
    # relative cd
    tw_test._predictive_cd_update("cd Desktop")
    assert tw_test._display_cwd == base / "Desktop", \
        f"relative cd failed: {base} -> {tw_test._display_cwd}"
    # absolute cd
    tw_test._predictive_cd_update("cd C:\\Windows")
    assert str(tw_test._display_cwd).lower().endswith("windows"), \
        f"absolute cd failed: {tw_test._display_cwd}"
    # bare `cd` returns home
    tw_test._predictive_cd_update("cd")
    assert tw_test._display_cwd == Path.home(), \
        f"bare cd failed: {tw_test._display_cwd}"
    tw_test.stop()
    print("  _predictive_cd_update OK (relative, absolute, bare)")

    # Pump the event loop briefly to let any pending output arrive
    print("Pumping event loop…")
    deadline = time.monotonic() + 2.0
    QTimer.singleShot(200, app.quit)
    code = app.exec()

    # The terminal view should have received some output from the run
    tw = w.terminal_panel.current_widget()
    if tw is not None:
        txt = tw._view.toPlainText()
        # don't fail the test on env-specific output, but report it
        print(f"  terminal captured {len(txt)} chars of output")

    print(f"Event loop exited cleanly (code {code}).")
    # Hard-exit so Python's shutdown doesn't race with still-draining
    # worker QThreads and produce a misleading "QThread destroyed while
    # running" warning. The user-facing app has a proper close path.
    import os
    sys.stdout.flush(); sys.stderr.flush()  # type: ignore[name-defined]
    os._exit(code)


if __name__ == "__main__":
    raise SystemExit(main())
