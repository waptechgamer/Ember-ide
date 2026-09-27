"""Editor-side completion, diagnostics, navigation, and breakpoint helpers."""
from __future__ import annotations

import re
from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.Qsci import QsciScintilla

from app.services import LanguageTools
from app.theme.dark_theme import PALETTE


class EnhancedEditorMixin:
    """Methods mixed into CodeEditor without coupling services to QScintilla."""

    breakpoint_toggled = pyqtSignal(int, bool)

    def configure_language_tools(self) -> None:
        widget = self.widget
        widget.setAutoCompletionSource(QsciScintilla.AcsAll)
        widget.setAutoCompletionThreshold(2)
        widget.setAutoCompletionCaseSensitivity(False)
        widget.setAutoIndent(True)
        widget.setMarginWidth(1, "  ")
        widget.setMarginSensitivity(1, True)
        widget.marginClicked.connect(self._on_margin_clicked)
        self._breakpoints: set[int] = set()
        try:
            widget.setMarkerBackgroundColor(QColor(PALETTE["error"]), 1)
            widget.setMarkerForegroundColor(QColor(PALETTE["fg"]), 1)
        except AttributeError:
            pass

    def show_local_completion(self) -> None:
        line, col = self.widget.getCursorPosition()
        current = self.widget.text(line)[:col]
        match = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", current)
        prefix = match.group(0) if match else ""
        words = LanguageTools.completion_words(self.text, prefix)
        if words:
            self.widget.showUserList(1, words)

    def toggle_breakpoint_current(self) -> None:
        line, _ = self.widget.getCursorPosition()
        self._on_margin_clicked(1, line, 0)

    def _on_margin_clicked(self, margin: int, line: int, _modifiers) -> None:
        if margin != 1:
            return
        if line in self._breakpoints:
            self.widget.markerDelete(line, 1)
            self._breakpoints.remove(line)
            enabled = False
        else:
            self.widget.markerAdd(line, 1)
            self._breakpoints.add(line)
            enabled = True
        self.breakpoint_toggled.emit(line + 1, enabled)

    def breakpoint_lines(self) -> list[int]:
        return sorted(line + 1 for line in getattr(self, "_breakpoints", set()))
