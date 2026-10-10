import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication

from app.utils.terminal import _TermState, TerminalWidget, Cell


def test_term_state_scrollback():
    state = _TermState(cols=80, rows=10, max_scrollback=100)
    assert len(state.buffer) == 10
    assert len(state.scrollback) == 0

    # Fill and scroll 15 lines
    for i in range(15):
        state.buffer[0][0] = Cell(char=str(i % 10))
        state.scroll_up(1)

    assert len(state.scrollback) == 15
    assert len(state.buffer) == 10
    assert state.scrollback[0][0].char == "0"


def test_term_state_erase_display():
    state = _TermState(cols=80, rows=10)
    for _ in range(5):
        state.scroll_up(1)
    assert len(state.scrollback) == 5

    state.erase_display(2)
    assert len(state.scrollback) == 0
    assert len(state.buffer) == 10
    assert state.cursor_row == 0
    assert state.cursor_col == 0


def test_term_state_resize():
    state = _TermState(cols=80, rows=10)
    for _ in range(5):
        state.scroll_up(1)

    state.resize(cols=100, rows=15)
    assert state.cols == 100
    assert state.rows == 15
    assert len(state.buffer) == 15
    # Lines pulled from scrollback into buffer
    assert len(state.scrollback) == 0


def test_terminal_widget_key_mapping(qtbot=None):
    app = QApplication.instance() or QApplication(sys.argv)
    tw = TerminalWidget(cwd=Path.home())

    # Verify _is_stopping initially False
    assert not tw._is_stopping

    # Test Ctrl+A keypress handling
    event_ctrl_a = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.ControlModifier, "a")
    tw._on_key(event_ctrl_a)

    # Test Ctrl+E keypress handling
    event_ctrl_e = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_E, Qt.ControlModifier, "e")
    tw._on_key(event_ctrl_e)

    # Stop widget
    tw.stop()
    assert tw._is_stopping
