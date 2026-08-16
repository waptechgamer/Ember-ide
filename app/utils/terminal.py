"""Integrated terminal — full PTY emulator, OS-aware, ANSI-rendering.

Like VS Code's terminal: the shell owns the prompt and all rendering.
Keystrokes go directly to the shell via PTY stdin. Output is rendered
in a QPlainTextEdit with ANSI color support.

Windows: winpty for real PTY, falls back to cmd.exe pipe.
Unix: stdlib pty module for real PTY.
"""
from __future__ import annotations

import os
import re
import select
import socket
import struct
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt5.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import (
    QColor, QFont, QFontDatabase, QKeyEvent, QTextCharFormat, QTextCursor,
    QTextBlockFormat,
)
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QScrollBar, QVBoxLayout, QWidget,
)

from app.theme.dark_theme import PALETTE


# ---------------------------------------------------------------------------
# OS detection
# ---------------------------------------------------------------------------

def is_windows() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")

def is_macos() -> bool:
    return sys.platform == "darwin"

def is_linux() -> bool:
    return sys.platform.startswith("linux")


# ---------------------------------------------------------------------------
# Shell detection
# ---------------------------------------------------------------------------

def detect_shell() -> List[str]:
    if is_windows():
        # Try PowerShell first, fall back to cmd
        ps = os.environ.get("PSModulePath")
        if ps:
            pwsh = "powershell.exe"
            import shutil
            for p in ("pwsh.exe", "powershell.exe"):
                if shutil.which(p):
                    pwsh = p; break
            return [pwsh, "-NoLogo", "-NoProfile", "-NoExit"]
        shell = os.environ.get("COMSPEC") or "cmd.exe"
        return [shell]
    if is_macos():
        shell = os.environ.get("SHELL")
        if shell: return [shell, "-l"]
        for c in ("/bin/zsh", "/bin/bash", "/bin/sh"):
            if Path(c).exists(): return [c, "-l"]
        return ["/bin/sh", "-l"]
    shell = os.environ.get("SHELL")
    if shell: return [shell, "-l"]
    for c in ("/bin/bash", "/bin/sh", "/bin/zsh"):
        if Path(c).exists(): return [c, "-l"]
    return ["/bin/sh", "-l"]


def shell_for_command(command: str) -> List[str]:
    if is_windows():
        comspec = os.environ.get("COMSPEC") or "cmd.exe"
        return [comspec, "/c", command]
    shell = os.environ.get("SHELL") or ("/bin/zsh" if is_macos() else "/bin/bash")
    return [shell, "-c", command]


# ---------------------------------------------------------------------------
# ANSI color table
# ---------------------------------------------------------------------------

_ANSI_16 = [
    "#1e1e1e", "#f48771", "#7ec699", "#dcdcaa",
    "#6cb6ff", "#d197d9", "#56b6c2", "#d4d4d4",
    "#666666", "#ff8b7a", "#9ee5a4", "#f0e68c",
    "#9cdcfe", "#e8a5e8", "#7ed4d4", "#ffffff",
]


# ---------------------------------------------------------------------------
# ANSI parser — CSI sequences including cursor movement
# ---------------------------------------------------------------------------

_CSI_RE = re.compile(r"\x1B\[([0-9;?]*)([a-zA-Z@`])")
_OSC_RE = re.compile(r"\x1B\]([^\x07\x1B]*(?:\x07|\x1B\\))")


@dataclass
class RunRequest:
    command: str
    cwd: Path


class _Format:
    def __init__(self) -> None:
        self.fg: Optional[str] = None
        self.bg: Optional[str] = None
        self.bold: bool = False
        self.underline: bool = False


def _parse_ansi(text: str, fmt: _Format) -> List[Tuple[str, Optional[str]]]:
    spans: List[Tuple[str, Optional[str]]] = []
    current_idx = 0
    while current_idx < len(text):
        esc_idx = text.find("\x1B", current_idx)
        if esc_idx == -1:
            plain = text[current_idx:]
            if plain:
                spans.append((plain, fmt.fg))
            break

        plain = text[current_idx:esc_idx]
        if plain:
            spans.append((plain, fmt.fg))

        csi_match = _CSI_RE.match(text, esc_idx)
        if csi_match:
            params_str = csi_match.group(1)
            final = csi_match.group(2)
            if final == "m":
                try:
                    params = [int(x) if x else 0 for x in params_str.split(";")]
                except ValueError:
                    params = [0]
                if not params:
                    params = [0]

                i = 0
                while i < len(params):
                    p = params[i]
                    if p == 0:
                        fmt.fg = None
                        fmt.bg = None
                        fmt.bold = False
                        fmt.underline = False
                    elif p == 1:
                        fmt.bold = True
                    elif p == 4:
                        fmt.underline = True
                    elif p == 22:
                        fmt.bold = False
                    elif p == 24:
                        fmt.underline = False
                    elif p == 39:
                        fmt.fg = None
                    elif p == 49:
                        fmt.bg = None
                    elif 30 <= p <= 37:
                        fmt.fg = _ANSI_16[p - 30]
                    elif 40 <= p <= 47:
                        fmt.bg = _ANSI_16[p - 40]
                    elif 90 <= p <= 97:
                        fmt.fg = _ANSI_16[p - 90 + 8]
                    elif 100 <= p <= 107:
                        fmt.bg = _ANSI_16[p - 100 + 8]
                    elif p in (38, 48) and i + 1 < len(params):
                        if params[i + 1] == 2 and i + 4 < len(params):
                            r, g, b = params[i+2], params[i+3], params[i+4]
                            hex_color = f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"
                            if p == 38:
                                fmt.fg = hex_color
                            else:
                                fmt.bg = hex_color
                            i += 4
                        elif params[i + 1] == 5 and i + 2 < len(params):
                            n = params[i + 2]
                            if n < 16:
                                hex_color = _ANSI_16[n]
                            elif n < 232:
                                idx = n - 16
                                rv = (idx // 36) % 6
                                gv = (idx // 6) % 6
                                bv = idx % 6
                                r = 40+rv*40 if rv else 0
                                g = 40+gv*40 if gv else 0
                                b = 40+bv*40 if bv else 0
                                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                            else:
                                v = 8 + (n - 232) * 10
                                hex_color = f"#{v:02x}{v:02x}{v:02x}"
                            if p == 38:
                                fmt.fg = hex_color
                            else:
                                fmt.bg = hex_color
                            i += 2
                    i += 1
            current_idx = csi_match.end()
            continue

        osc_match = _OSC_RE.match(text, esc_idx)
        if osc_match:
            current_idx = osc_match.end()
            continue

        if esc_idx + 1 < len(text):
            current_idx = esc_idx + 2
        else:
            current_idx = esc_idx + 1

    return spans


def strip_ansi(text: str) -> str:
    text = _CSI_RE.sub("", text)
    text = _OSC_RE.sub("", text)
    return text


def build_prompt(cwd: Path) -> Tuple[str, List[Tuple[str, str]]]:
    path_str = shorten_home(cwd)
    if is_windows():
        plain = f"{path_str}> "
        rich = [(path_str, "#6cb6ff"), ("> ", "#7ec699")]
    elif is_macos():
        plain = f"{path_str} % "
        rich = [(path_str, "#6cb6ff"), (" % ", "#7ec699")]
    else:
        plain = f"{path_str} $ "
        rich = [(path_str, "#6cb6ff"), (" $ ", "#7ec699")]
    return plain, rich


def clear_command() -> str:
    return "cls" if is_windows() else "clear"


@dataclass
class Cell:
    """One character cell in the terminal buffer."""
    char: str = " "
    fg: Optional[QColor] = None
    bg: Optional[QColor] = None
    bold: bool = False
    underline: bool = False


@dataclass
class _TermState:
    """Full terminal emulator state."""
    cols: int = 120
    rows: int = 30
    cursor_row: int = 0
    cursor_col: int = 0
    scroll_top: int = 0
    scroll_bottom: int = 29
    fg: Optional[QColor] = None
    bg: Optional[QColor] = None
    bold: bool = False
    underline: bool = False
    reverse: bool = False
    origin_mode: bool = False
    auto_wrap: bool = True
    wrap_pending: bool = False
    # Saved cursor position for ESC 7 / ESC 8
    saved_row: int = 0
    saved_col: int = 0

    buffer: list = field(default_factory=list)
    dirty: bool = True

    def __post_init__(self):
        self._resize_buffer()

    def _resize_buffer(self):
        while len(self.buffer) < self.rows:
            self.buffer.append([Cell() for _ in range(self.cols)])

    def resize(self, cols: int, rows: int):
        old = self.buffer
        self.cols = cols
        self.rows = rows
        self.scroll_bottom = rows - 1
        self.cursor_row = min(self.cursor_row, rows - 1)
        self.cursor_col = min(self.cursor_col, cols - 1)
        self._resize_buffer()
        # Copy old content
        for r in range(min(len(old), rows)):
            for c in range(min(len(old[r]), cols)):
                self.buffer[r][c] = old[r][c]
        self.dirty = True

    def scroll_up(self, n: int = 1):
        for _ in range(n):
            if self.scroll_top < len(self.buffer):
                del self.buffer[self.scroll_top]
            self.buffer.insert(self.scroll_top, [Cell() for _ in range(self.cols)])
        self.dirty = True

    def scroll_down(self, n: int = 1):
        for _ in range(n):
            if self.scroll_bottom < len(self.buffer):
                del self.buffer[self.scroll_bottom]
            self.buffer.insert(self.scroll_bottom, [Cell() for _ in range(self.cols)])
        self.dirty = True

    def erase_line(self, mode: int = 0):
        """Erase line: 0=to end, 1=to start, 2=whole line."""
        row = self.cursor_row
        if row >= len(self.buffer):
            return
        if mode == 0:
            for c in range(self.cursor_col, self.cols):
                self.buffer[row][c] = Cell()
        elif mode == 1:
            for c in range(0, self.cursor_col + 1):
                self.buffer[row][c] = Cell()
        elif mode == 2:
            self.buffer[row] = [Cell() for _ in range(self.cols)]
        self.dirty = True

    def erase_display(self, mode: int = 0):
        """Erase display: 0=to end, 1=to start, 2=all, 3=saved lines."""
        if mode == 0:
            self.erase_line(0)
            for r in range(self.cursor_row + 1, self.rows):
                self.buffer[r] = [Cell() for _ in range(self.cols)]
        elif mode == 1:
            self.erase_line(1)
            for r in range(0, self.cursor_row):
                self.buffer[r] = [Cell() for _ in range(self.cols)]
        elif mode == 2:
            self.buffer = [[Cell() for _ in range(self.cols)] for _ in range(self.rows)]
            self.cursor_row = 0
            self.cursor_col = 0
        self.dirty = True

    def insert_lines(self, n: int = 1):
        """Insert n lines at cursor, pushing lines down."""
        for _ in range(n):
            if self.scroll_bottom < len(self.buffer):
                del self.buffer[self.scroll_bottom]
            self.buffer.insert(self.cursor_row, [Cell() for _ in range(self.cols)])
        self.dirty = True

    def delete_lines(self, n: int = 1):
        """Delete n lines at cursor, pulling lines up."""
        for _ in range(n):
            if self.cursor_row < len(self.buffer):
                del self.buffer[self.cursor_row]
            self.buffer.insert(self.scroll_bottom, [Cell() for _ in range(self.cols)])
        self.dirty = True

    def delete_chars(self, n: int = 1):
        """Delete n chars at cursor on current line."""
        row = self.buffer[self.cursor_row]
        for _ in range(n):
            if self.cursor_col < len(row):
                del row[self.cursor_col]
                row.append(Cell())
        self.dirty = True

    def insert_chars(self, n: int = 1):
        """Insert n blank chars at cursor."""
        row = self.buffer[self.cursor_row]
        for _ in range(n):
            if self.cursor_col < len(row):
                row.insert(self.cursor_col, Cell())
                if len(row) > self.cols:
                    row.pop()
        self.dirty = True

    def set_cell(self, char: str):
        """Write one character at cursor, advance cursor."""
        if self.cursor_row >= len(self.buffer):
            return
        if self.wrap_pending:
            self.cursor_col = 0
            self.cursor_row += 1
            self.wrap_pending = False
            if self.cursor_row > self.scroll_bottom:
                self.scroll_up(1)
                self.cursor_row = self.scroll_bottom
            if self.cursor_row >= len(self.buffer):
                self.buffer.append([Cell() for _ in range(self.cols)])

        bg = self.bg
        fg = self.fg
        if self.reverse:
            fg, bg = (bg or QColor("#1e1e1e")), (fg or QColor("#d4d4d4"))
        bold = self.bold

        cell = Cell(char=char, fg=fg, bg=bg, bold=bold, underline=self.underline)
        row = self.buffer[self.cursor_row]
        if self.cursor_col < len(row):
            row[self.cursor_col] = cell
        self.cursor_col += 1
        if self.cursor_col >= self.cols:
            if self.auto_wrap:
                self.cursor_col = 0
                self.cursor_row += 1
                if self.cursor_row > self.scroll_bottom:
                    self.scroll_up(1)
                    self.cursor_row = self.scroll_bottom
            else:
                self.cursor_col = self.cols - 1
        self.dirty = True


# ---------------------------------------------------------------------------
# ANSI sequence processor — feeds characters into _TermState
# ---------------------------------------------------------------------------

class _AnsiProcessor:
    """Processes raw terminal output and updates _TermState."""

    def __init__(self, state: _TermState):
        self.s = state
        self._buf = ""

    def feed(self, data: str):
        self._buf += data
        while self._buf:
            ch = self._buf[0]
            if ch == "\x1B":
                consumed = self._escape()
                if consumed == 0:
                    break  # need more data
                self._buf = self._buf[consumed:]
            elif ch == "\r":
                self.s.cursor_col = 0
                self._buf = self._buf[1:]
            elif ch == "\n":
                self.s.cursor_row += 1
                if self.s.cursor_row > self.s.scroll_bottom:
                    self.s.scroll_up(1)
                    self.s.cursor_row = self.s.scroll_bottom
                self._buf = self._buf[1:]
            elif ch == "\b":
                if self.s.cursor_col > 0:
                    self.s.cursor_col -= 1
                self._buf = self._buf[1:]
            elif ch == "\t":
                # Tab: advance to next 8-column stop
                self.s.cursor_col = min(self.s.cols - 1, (self.s.cursor_col // 8 + 1) * 8)
                self._buf = self._buf[1:]
            elif ch == "\x07":
                # Bell — ignore
                self._buf = self._buf[1:]
            elif ch == "\x00":
                # Null — ignore
                self._buf = self._buf[1:]
            else:
                self.s.set_cell(ch)
                self._buf = self._buf[1:]

    def _escape(self) -> int:
        """Try to consume an escape sequence. Returns chars consumed, or 0 if incomplete."""
        m = _CSI_RE.match(self._buf)
        if m:
            self._handle_csi(m.group(1), m.group(2))
            return m.end()
        # OSC
        om = _OSC_RE.match(self._buf)
        if om:
            return om.end()
        # Two-char sequences: ESC 7, ESC 8, ESC D, ESC M, ESC c, etc.
        if len(self._buf) >= 2:
            c = self._buf[1]
            if c == "7":
                self.s.saved_row = self.s.cursor_row
                self.s.saved_col = self.s.cursor_col
                return 2
            if c == "8":
                self.s.cursor_row = self.s.saved_row
                self.s.cursor_col = self.s.saved_col
                return 2
            if c == "D":
                # Index — move down, scroll if at bottom
                self.s.cursor_row += 1
                if self.s.cursor_row > self.s.scroll_bottom:
                    self.s.scroll_up(1)
                    self.s.cursor_row = self.s.scroll_bottom
                return 2
            if c == "M":
                # Reverse index — move up, scroll if at top
                self.s.cursor_row -= 1
                if self.s.cursor_row < self.s.scroll_top:
                    self.s.scroll_down(1)
                    self.s.cursor_row = self.s.scroll_top
                return 2
            if c == "c":
                # Full reset
                self.s.__init__(cols=self.s.cols, rows=self.s.rows)
                return 2
        return 0

    def _handle_csi(self, params_str: str, final: str):
        """Process a CSI sequence."""
        try:
            params = [int(x) if x else 0 for x in params_str.split(";")]
        except ValueError:
            params = [0]
        if not params:
            params = [0]

        s = self.s
        p = params

        if final == "m":
            self._sgr(p)
        elif final == "A":
            s.cursor_row = max(s.scroll_top, s.cursor_row - (p[0] or 1))
        elif final == "B":
            s.cursor_row = min(s.scroll_bottom, s.cursor_row + (p[0] or 1))
        elif final == "C":
            s.cursor_col = min(s.cols - 1, s.cursor_col + (p[0] or 1))
        elif final == "D":
            s.cursor_col = max(0, s.cursor_col - (p[0] or 1))
        elif final == "E":
            s.cursor_col = 0
            s.cursor_row = min(s.scroll_bottom, s.cursor_row + (p[0] or 1))
        elif final == "F":
            s.cursor_col = 0
            s.cursor_row = max(s.scroll_top, s.cursor_row - (p[0] or 1))
        elif final == "G":
            s.cursor_col = min(s.cols - 1, max(0, (p[0] or 1) - 1))
        elif final == "H" or final == "f":
            row = max(0, min(s.rows - 1, (p[0] or 1) - 1))
            col = max(0, min(s.cols - 1, (p[1] or 1) - 1))
            s.cursor_row = row
            s.cursor_col = col
        elif final == "J":
            s.erase_display(p[0] if p else 0)
        elif final == "K":
            s.erase_line(p[0] if p else 0)
        elif final == "L":
            s.insert_lines(p[0] or 1)
        elif final == "M":
            s.delete_lines(p[0] or 1)
        elif final == "P":
            s.delete_chars(p[0] or 1)
        elif final == "@":
            s.insert_chars(p[0] or 1)
        elif final == "S":
            s.scroll_up(p[0] or 1)
        elif final == "T":
            s.scroll_down(p[0] or 1)
        elif final == "X":
            # Erase characters
            n = min(p[0] or 1, s.cols - s.cursor_col)
            row = s.buffer[s.cursor_row]
            for c in range(s.cursor_col, min(s.cursor_col + n, s.cols)):
                row[c] = Cell()
            s.dirty = True
        elif final == "d":
            s.cursor_row = min(s.rows - 1, max(0, (p[0] or 1) - 1))
        elif final == "r":
            top = max(0, min(s.rows - 1, (p[0] or 1) - 1))
            bot = max(top, min(s.rows - 1, (p[1] or s.rows) - 1))
            s.scroll_top = top
            s.scroll_bottom = bot
        elif final == "h" or final == "l":
            # Mode set/reset — mostly ignore, handle a few
            pass
        elif final == "n":
            pass  # Device status report — ignore
        elif final == "c":
            pass  # Device attributes — ignore
        elif final == "s":
            s.saved_row = s.cursor_row
            s.saved_col = s.cursor_col
        elif final == "u":
            s.cursor_row = s.saved_row
            s.cursor_col = s.saved_col

    def _sgr(self, params: List[int]):
        """Apply Select Graphic Rendition (colors and attributes)."""
        s = self.s
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                s.fg = None; s.bg = None
                s.bold = False; s.underline = False; s.reverse = False
            elif p == 1:   s.bold = True
            elif p == 4:   s.underline = True
            elif p == 7:   s.reverse = True
            elif p == 22:  s.bold = False
            elif p == 24:  s.underline = False
            elif p == 27:  s.reverse = False
            elif p == 39:  s.fg = None
            elif p == 49:  s.bg = None
            elif 30 <= p <= 37:  s.fg = QColor(_ANSI_16[p - 30])
            elif 40 <= p <= 47:  s.bg = QColor(_ANSI_16[p - 40])
            elif 90 <= p <= 97:  s.fg = QColor(_ANSI_16[p - 90 + 8])
            elif 100 <= p <= 107: s.bg = QColor(_ANSI_16[p - 100 + 8])
            elif p in (38, 48) and i + 1 < len(params):
                if params[i + 1] == 2 and i + 4 < len(params):
                    r, g, b = params[i+2], params[i+3], params[i+4]
                    c = QColor(max(0,min(255,r)), max(0,min(255,g)), max(0,min(255,b)))
                    if p == 38: s.fg = c
                    else:       s.bg = c
                    i += 4
                elif params[i + 1] == 5 and i + 2 < len(params):
                    n = params[i + 2]
                    if n < 16: c = QColor(_ANSI_16[n])
                    elif n < 232:
                        idx = n - 16
                        rv = (idx // 36) % 6; gv = (idx // 6) % 6; bv = idx % 6
                        c = QColor(40+rv*40 if rv else 0, 40+gv*40 if gv else 0, 40+bv*40 if bv else 0)
                    else:
                        v = 8 + (n - 232) * 10; c = QColor(v, v, v)
                    if p == 38: s.fg = c
                    else:       s.bg = c
                    i += 2
            i += 1


# ---------------------------------------------------------------------------
# Persistent shell process
# ---------------------------------------------------------------------------

class _ShellProcess(QObject):
    output = pyqtSignal(str)
    closed = pyqtSignal(int)

    def __init__(self, argv: List[str], cwd: str, cols: int = 120, rows: int = 30) -> None:
        super().__init__()
        self._argv = argv
        self._cwd = cwd
        self._cols = cols
        self._rows = rows
        self._proc = None
        self._stop = False
        self._stdin_lock = threading.Lock()
        self._using_pty = False
        self._fd = -1
        self._pid = -1

    def start(self) -> None:
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = str(self._cols)
        env["LINES"] = str(self._rows)
        env["COLORTERM"] = "truecolor"

        if is_windows():
            # Use winpty for real PTY on Windows
            try:
                from winpty import PtyProcess
                self._proc = PtyProcess.spawn(
                    self._argv, dimensions=(self._rows, self._cols),
                    cwd=self._cwd, env=env,
                )
                self._using_pty = True
                return
            except ImportError:
                pass
            # Fallback: cmd.exe with pipes
            creationflags = subprocess.CREATE_NO_WINDOW
            self._proc = subprocess.Popen(
                self._argv, cwd=self._cwd, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, bufsize=0,
                creationflags=creationflags,
            )
            self._using_pty = False
        else:
            # Unix: use pty.fork
            import pty
            pid, fd = pty.fork()
            if pid == 0:
                # Child
                os.environ.update(env)
                os.environ["TERM"] = "xterm-256color"
                os.environ["COLUMNS"] = str(self._cols)
                os.environ["LINES"] = str(self._rows)
                try: os.chdir(self._cwd)
                except OSError: pass
                os.execvp(self._argv[0], self._argv)
                os._exit(127)
            self._pid = pid
            self._fd = fd
            self._using_pty = True
            self._set_winsize(self._rows, self._cols)

    def _set_winsize(self, rows: int, cols: int) -> None:
        if self._using_pty and not is_windows() and self._fd >= 0:
            try:
                import fcntl, termios
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self._fd, termios.TIOCSWINSZ, winsize)
            except Exception:
                pass
        elif self._using_pty and is_windows() and self._proc is not None:
            try:
                self._proc.resize(rows, cols)
            except Exception:
                pass

    def resize(self, rows: int, cols: int) -> None:
        self._rows = rows
        self._cols = cols
        self._set_winsize(rows, cols)

    def send(self, text: str) -> None:
        data = text.encode("utf-8", errors="replace")
        self.send_bytes(data)

    def send_bytes(self, data: bytes) -> None:
        if self._using_pty and not is_windows() and self._fd >= 0:
            try:
                os.write(self._fd, data)
            except OSError:
                pass
        elif self._using_pty and is_windows() and self._proc is not None:
            try:
                self._proc.write(data)
            except Exception:
                pass
        elif self._proc and self._proc.stdin:
            with self._stdin_lock:
                try:
                    self._proc.stdin.write(data)
                    self._proc.stdin.flush()
                except (OSError, BrokenPipeError):
                    pass

    def stop(self) -> None:
        self._stop = True
        try:
            if self._using_pty and not is_windows() and self._pid > 0:
                os.kill(self._pid, 15)  # SIGTERM
            elif self._using_pty and is_windows() and self._proc:
                self._proc.terminate(force=True)
            elif self._proc:
                self._proc.terminate()
        except Exception:
            pass

    def run(self) -> None:
        try:
            if self._using_pty and not is_windows() and self._fd >= 0:
                while not self._stop:
                    r, _, _ = select.select([self._fd], [], [], 0.05)
                    if r:
                        try:
                            data = os.read(self._fd, 8192)
                            if not data:
                                break
                            self.output.emit(data.decode("utf-8", errors="replace"))
                        except OSError:
                            break
                try:
                    _, status = os.waitpid(self._pid, 0)
                    rc = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
                except Exception:
                    rc = 0
                self.closed.emit(rc)
            elif self._using_pty and is_windows() and self._proc:
                while not self._stop and self._proc.isalive():
                    try:
                        chunk = self._proc.read(8192)
                        if chunk:
                            self.output.emit(chunk)
                    except EOFError:
                        break
                self.closed.emit(self._proc.exitstatus or 0)
            else:
                p = self._proc
                if p and p.stdout:
                    while not self._stop:
                        chunk = p.stdout.read(8192)
                        if not chunk:
                            break
                        self.output.emit(chunk.decode("utf-8", errors="replace"))
                if p:
                    p.wait()
                    self.closed.emit(p.returncode or 0)
        except Exception:
            self.closed.emit(-1)


# ---------------------------------------------------------------------------
# Prompt (for local use — the shell also renders its own prompt)
# ---------------------------------------------------------------------------

def shorten_home(p: Path) -> str:
    try:
        home = Path.home().resolve(); pr = p.resolve()
        if pr == home: return "~"
        if home in pr.parents: return "~" + str(pr).replace(str(home), "", 1).replace("\\", "/")
    except Exception: pass
    return str(p)


# ---------------------------------------------------------------------------
# Command history
# ---------------------------------------------------------------------------

def _history_file() -> Path:
    base = Path.home() / ".ember_ide"
    try: base.mkdir(parents=True, exist_ok=True)
    except OSError: pass
    return base / "history"

def load_history(limit: int = 500) -> List[str]:
    f = _history_file()
    if not f.exists(): return []
    try: lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError: return []
    out: List[str] = []; seen = None
    for ln in lines:
        if not ln or ln == seen: continue
        out.append(ln); seen = ln
        if len(out) >= limit: break
    return out

def save_history(history: List[str]) -> None:
    try: _history_file().write_text("\n".join(history) + "\n", encoding="utf-8")
    except OSError: pass


# ---------------------------------------------------------------------------
# Font picker
# ---------------------------------------------------------------------------

def pick_monospace_font(point_size: int = 11) -> QFont:
    if is_windows():
        candidates = ["Cascadia Mono", "Cascadia Code", "Consolas", "JetBrains Mono"]
    elif is_macos():
        candidates = ["SF Mono", "Menlo", "Monaco", "JetBrains Mono"]
    else:
        candidates = ["JetBrains Mono", "DejaVu Sans Mono", "Ubuntu Mono", "Liberation Mono"]
    families = set(QFontDatabase().families())
    for name in candidates:
        if name in families:
            f = QFont(name); f.setStyleHint(QFont.Monospace); f.setPointSize(point_size)
            return f
    f = QFont("Monospace"); f.setStyleHint(QFont.Monospace); f.setPointSize(point_size)
    return f


# ---------------------------------------------------------------------------
# Terminal view — QPlainTextEdit that accepts raw keyboard input
# ---------------------------------------------------------------------------

class _TerminalView(QPlainTextEdit):
    """QPlainTextEdit subclass that forwards all keyboard input to a callback."""

    key_pressed = pyqtSignal(QKeyEvent)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(False)  # We need key events
        self.setUndoRedoEnabled(False)
        self._term_state: Optional[_TermState] = None

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        self.key_pressed.emit(event)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:
        super().wheelEvent(event)


# ---------------------------------------------------------------------------
# Terminal widget — the full terminal emulator
# ---------------------------------------------------------------------------

class TerminalWidget(QWidget):
    """One terminal tab. Full PTY emulator like VS Code's integrated terminal."""

    closed = pyqtSignal(object)
    SCROLLBACK_LIMIT = 10000

    def __init__(self, parent: QWidget | None = None, cwd: Optional[Path] = None) -> None:
        super().__init__(parent)
        self._cwd = Path(cwd or Path.cwd()).resolve()
        self._display_cwd = self._cwd
        self._history: List[str] = load_history()
        self._history_index = 0
        self._retired: List[_ShellProcess] = []
        self._input_buf = ""  # line buffer for command echo suppression

        # --- Font ---
        self._font = pick_monospace_font(11)
        self._font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)

        # --- Terminal state ---
        self._term = _TermState()
        self._fmt = _Format()

        # --- ANSI processor ---
        self._ansi = _AnsiProcessor(self._term)

        # --- View ---
        self._view = _TerminalView()
        self._view._term_state = self._term
        self._view.setReadOnly(True)
        self._view.setUndoRedoEnabled(False)
        self._view.setMaximumBlockCount(self.SCROLLBACK_LIMIT)
        self._view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setFont(self._font)
        self._view.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {PALETTE['bg_sunken']};
                color: {PALETTE['fg']};
                border: none;
                selection-background-color: {PALETTE['selection']};
                font-family: "{self._font.family()}";
                font-size: {self._font.pointSize()}pt;
                padding: 4px 6px;
            }}
        """)
        self._view.key_pressed.connect(self._on_key)
        self._view.verticalScrollBar().setValue(self._view.verticalScrollBar().maximum())

        # --- Bottom bar: input + stop ---
        self._input = QLineEdit()
        self._input.setFont(self._font)
        self._input.setFrame(False)
        self._input.setPlaceholderText("Type here or click in the terminal...")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {PALETTE['bg_sunken']};
                color: {PALETTE['fg']};
                border-top: 1px solid {PALETTE['border']};
                padding: 4px 8px;
                font-family: "{self._font.family()}";
                font-size: {self._font.pointSize()}pt;
            }}
            QLineEdit:focus {{
                border-top-color: {PALETTE['accent']};
            }}
        """)
        self._input.returnPressed.connect(self._on_input_enter)
        self._input.installEventFilter(self)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("terminalStop")
        self._stop_btn.setFixedWidth(60)
        self._stop_btn.setFont(self._font)
        self._stop_btn.clicked.connect(self._stop_process)
        self._stop_btn.setEnabled(False)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(0)
        bottom.addWidget(self._input, 1)
        bottom.addWidget(self._stop_btn, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view, 1)
        layout.addLayout(bottom, 0)

        # --- Worker thread ---
        self._thread = QThread(self)
        self._proc: Optional[_ShellProcess] = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._render_view)
        self._refresh_timer.start(16)  # ~60fps render

        self._start_shell()

    # ------------------------------------------------------------------ public

    def cwd(self) -> Path:
        return self._cwd

    def is_running(self) -> bool:
        return self._thread.isRunning()

    def focus_input(self) -> None:
        self._view.setFocus()

    def run(self, request) -> None:
        if self._proc:
            if hasattr(request, "command"):
                self._predictive_cd_update(request.command)
                self._proc.send(request.command + "\n")
            else:
                self._proc.send(str(request) + "\n")

    def run_shell(self) -> None:
        self._start_shell()

    def stop(self) -> None:
        if self._proc:
            self._proc.stop()
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self._retired.clear()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._recalc_size()

    def _predictive_cd_update(self, command_str: str) -> None:
        cmd = command_str.strip()
        if cmd == "cd":
            self._display_cwd = Path.home()
        elif cmd.startswith("cd "):
            path_part = cmd[3:].strip()
            if not path_part:
                self._display_cwd = Path.home()
            else:
                is_abs = (
                    path_part.startswith("/") or
                    path_part.startswith("\\") or
                    (len(path_part) >= 2 and path_part[1] == ":" and path_part[0].isalpha())
                )
                if is_abs:
                    self._display_cwd = Path(path_part)
                else:
                    self._display_cwd = (self._display_cwd / path_part).resolve()

    def _append_plain(self, text: str, spans: list = None) -> None:
        if spans:
            for span_text, span_color in spans:
                for char in span_text:
                    if char == "\n":
                        self._term.cursor_row += 1
                        if self._term.cursor_row > self._term.scroll_bottom:
                            self._term.scroll_up(1)
                            self._term.cursor_row = self._term.scroll_bottom
                        self._term.cursor_col = 0
                    elif char == "\r":
                        self._term.cursor_col = 0
                    else:
                        self._term.set_cell(char)
        else:
            for char in text:
                if char == "\n":
                    self._term.cursor_row += 1
                    if self._term.cursor_row > self._term.scroll_bottom:
                        self._term.scroll_up(1)
                        self._term.cursor_row = self._term.scroll_bottom
                    self._term.cursor_col = 0
                elif char == "\r":
                    self._term.cursor_col = 0
                else:
                    self._term.set_cell(char)
        self._term.dirty = True
        self._render_view()

    # ---------------------------------------------------------------- private

    def _recalc_size(self):
        fm = self._view.fontMetrics()
        cw = max(1, fm.horizontalAdvance("M"))
        ch = max(1, fm.height())
        cols = max(40, (self._view.width() - 12) // cw)
        rows = max(10, (self._view.height() - 12) // ch)
        if cols != self._term.cols or rows != self._term.rows:
            self._term.resize(cols, rows)
            if self._proc:
                self._proc.resize(rows, cols)

    def _start_shell(self) -> None:
        if self._proc is not None:
            self._proc.stop()
            try:
                self._proc.output.disconnect(self._on_output)
                self._proc.closed.disconnect(self._on_shell_closed)
            except (TypeError, RuntimeError):
                pass
            self._retired.append(self._proc)
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)

        fm = self._view.fontMetrics()
        cw = max(1, fm.horizontalAdvance("M"))
        ch = max(1, fm.height())
        cols = max(40, self._view.width() // cw) if self._view.width() > 0 else 120
        rows = max(10, self._view.height() // ch) if self._view.height() > 0 else 30

        self._term.resize(cols, rows)
        self._ansi = _AnsiProcessor(self._term)

        self._proc = _ShellProcess(detect_shell(), str(self._cwd), cols=cols, rows=rows)
        self._proc.moveToThread(self._thread)
        self._thread.started.connect(self._proc.start)
        self._proc.output.connect(self._on_output)
        self._proc.closed.connect(self._on_shell_closed)
        self._thread.start()
        self._stop_btn.setEnabled(True)

    def _on_output(self, text: str) -> None:
        """Feed raw shell output into ANSI processor and update view matrix."""
        self._ansi.feed(text)
        self._render_view()

    def _render_view(self) -> None:
        """Render terminal buffer state from _TermState with full ANSI cell formatting to QPlainTextEdit."""
        if not self._term.dirty:
            return
        self._term.dirty = False

        cursor = self._view.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)

        for row_idx, row in enumerate(self._term.buffer):
            spans = []
            curr_text = ""
            curr_cell = None

            for cell in row:
                if curr_cell is None or (cell.fg == curr_cell.fg and cell.bg == curr_cell.bg and cell.bold == curr_cell.bold and cell.underline == curr_cell.underline):
                    curr_text += cell.char
                    curr_cell = cell
                else:
                    spans.append((curr_text, curr_cell))
                    curr_text = cell.char
                    curr_cell = cell
            if curr_text:
                spans.append((curr_text, curr_cell))

            for span_text, cell in spans:
                fmt = QTextCharFormat()
                if cell and cell.fg:
                    fmt.setForeground(cell.fg)
                else:
                    fmt.setForeground(QColor(PALETTE['fg']))
                if cell and cell.bg:
                    fmt.setBackground(cell.bg)
                if cell and cell.bold:
                    fmt.setFontWeight(QFont.Bold)
                if cell and cell.underline:
                    fmt.setFontUnderline(True)
                cursor.insertText(span_text, fmt)

            if row_idx < len(self._term.buffer) - 1:
                cursor.insertText("\n", QTextCharFormat())

        self._view.setTextCursor(cursor)
        self._view.verticalScrollBar().setValue(self._view.verticalScrollBar().maximum())

    def _on_key(self, event: QKeyEvent) -> None:
        """Forward keyboard input to the shell."""
        if not self._proc:
            return

        key = event.key()
        mods = event.modifiers()
        text = event.text()

        # Ctrl+C — interrupt
        if key == Qt.Key_C and mods & Qt.ControlModifier:
            self._proc.send_bytes(b"\x03")
            return

        # Ctrl+L — clear screen
        if key == Qt.Key_L and mods & Qt.ControlModifier:
            self._proc.send_bytes(b"\x1b[H\x1b[2J")
            self._term.erase_display(2)
            return

        # Ctrl+V — paste from clipboard
        if key == Qt.Key_V and mods & Qt.ControlModifier:
            from PyQt5.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            text = clipboard.text()
            if text:
                self._proc.send(text)
            return

        # Ctrl+A — select all
        if key == Qt.Key_A and mods & Qt.ControlModifier:
            return  # let default handle it

        # Arrow keys
        if key == Qt.Key_Up:
            self._proc.send_bytes(b"\x1b[A")
            return
        if key == Qt.Key_Down:
            self._proc.send_bytes(b"\x1b[B")
            return
        if key == Qt.Key_Right:
            self._proc.send_bytes(b"\x1b[C")
            return
        if key == Qt.Key_Left:
            self._proc.send_bytes(b"\x1b[D")
            return

        # Home / End
        if key == Qt.Key_Home:
            self._proc.send_bytes(b"\x1b[H")
            return
        if key == Qt.Key_End:
            self._proc.send_bytes(b"\x1b[F")
            return

        # Page Up / Page Down
        if key == Qt.Key_PageUp:
            self._proc.send_bytes(b"\x1b[5~")
            return
        if key == Qt.Key_PageDown:
            self._proc.send_bytes(b"\x1b[6~")
            return

        # Tab
        if key == Qt.Key_Tab:
            self._proc.send_bytes(b"\t")
            return

        # Backspace
        if key == Qt.Key_Backspace:
            self._proc.send_bytes(b"\x7f")
            return

        # Delete
        if key == Qt.Key_Delete:
            self._proc.send_bytes(b"\x1b[3~")
            return

        # Enter
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._proc.send_bytes(b"\r")
            return

        # Escape
        if key == Qt.Key_Escape:
            self._proc.send_bytes(b"\x1b")
            return

        # Regular character input
        if text:
            self._proc.send(text)
            return

    def _on_input_enter(self) -> None:
        """Bottom bar input field sends command to shell."""
        cmd = self._input.text()
        self._input.clear()
        if self._proc and cmd:
            self._predictive_cd_update(cmd)
            self._proc.send(cmd + "\n")
            self._append_history(cmd)

    def _append_history(self, cmd: str) -> None:
        cmd = cmd.strip()
        if not cmd: return
        if self._history and self._history[-1] == cmd: return
        self._history.append(cmd)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        save_history(self._history)

    def _on_shell_closed(self, code: int) -> None:
        sender = self.sender()
        if sender is not None and sender in self._retired:
            self._retired.remove(sender)
            return
        if sender is self._proc:
            self._stop_btn.setEnabled(False)
            QTimer.singleShot(500, self._start_shell)

    def _stop_process(self) -> None:
        if self._proc:
            self._proc.send_bytes(b"\x03")

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self._input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key_Up:
                if self._history and self._history_index > 0:
                    self._history_index -= 1
                    self._input.setText(self._history[self._history_index])
                return True
            if event.key() == Qt.Key_Down:
                if self._history_index < len(self._history) - 1:
                    self._history_index += 1
                    self._input.setText(self._history[self._history_index])
                else:
                    self._history_index = len(self._history)
                    self._input.clear()
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._refresh_timer.stop()
        self.stop()
        super().closeEvent(event)
