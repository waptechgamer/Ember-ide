"""Code editor — a QScintilla widget (PyQt5) for our IDE.

VS Code-inspired code editor with enhanced syntax highlighting.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.Qsci import QsciScintilla
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from app.theme.dark_theme import QSCI_DARK, PALETTE, pick_lexer_class


class CodeEditor(QObject):
    """Thin facade over QsciScintilla.

    The underlying widget is accessible via ``.widget`` for parenting
    into a QTabWidget / QSplitter.
    """

    modification_changed = pyqtSignal(bool)
    cursor_position_changed = pyqtSignal(int, int)  # line, column (1-based)
    file_path: Optional[Path]

    def __init__(self, file_path: Optional[Path] = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.file_path = file_path

        self._scintilla = QsciScintilla()
        self._configure()
        self._scintilla.SCN_SAVEPOINTLEFT.connect(self._on_modified)
        self._scintilla.SCN_SAVEPOINTREACHED.connect(lambda: self._emit_modified(False))
        self._scintilla.cursorPositionChanged.connect(self._on_cursor)

        if file_path is not None:
            self._apply_lexer_for(file_path)

    # ------------------------------------------------------------------ public

    @property
    def widget(self) -> QsciScintilla:
        return self._scintilla

    @property
    def text(self) -> str:
        return self._scintilla.text()

    @text.setter
    def text(self, value: str) -> None:
        self._scintilla.setText(value)
        self._scintilla.setModified(False)

    def is_modified(self) -> bool:
        return self._scintilla.isModified()

    def set_modified(self, value: bool) -> None:
        self._scintilla.setModified(value)

    def set_file_path(self, path: Path) -> None:
        self.file_path = path
        self._apply_lexer_for(path)

    def lexer_name(self) -> str:
        lexer = self._scintilla.lexer()
        return type(lexer).__name__ if lexer else "Plain Text"

    # ----------------------------------------------------------------- private

    def _configure(self) -> None:
        s = self._scintilla

        # Margins: line numbers
        s.setMarginType(0, QsciScintilla.NumberMargin)
        s.setMarginWidth(0, "00000")
        s.setMarginsForegroundColor(QColor(QSCI_DARK["margin_fg"]))
        s.setMarginsBackgroundColor(QColor(QSCI_DARK["margin_bg"]))

        # Caret + selection (VS Code-style)
        s.setCaretForegroundColor(QColor(QSCI_DARK["caret_fg"]))
        s.setCaretLineVisible(True)
        s.setCaretLineBackgroundColor(QColor(QSCI_DARK["line_highlight_bg"]))
        s.setSelectionBackgroundColor(QColor(QSCI_DARK["selection_bg"]))
        s.setMatchedBraceBackgroundColor(QColor(PALETTE["accent"]))
        s.setMatchedBraceForegroundColor(QColor(PALETTE["fg_bright"]))
        s.setUnmatchedBraceBackgroundColor(QColor(PALETTE["error"]))
        s.setUnmatchedBraceForegroundColor(QColor(PALETTE["fg"]))

        # Defaults
        s.setIndentationGuides(True)
        s.setTabWidth(4)
        s.setIndentationsUseTabs(False)
        s.setAutoIndent(True)
        s.setBraceMatching(QsciScintilla.SloppyBraceMatch)
        s.setEdgeMode(QsciScintilla.EdgeNone)
        s.setUtf8(True)
        s.setWhitespaceVisibility(QsciScintilla.WsInvisible)

        # VS Code-inspired editor font
        font = QFont("Cascadia Code")
        if not font.exactMatch():
            font = QFont("JetBrains Mono")
        if not font.exactMatch():
            font = QFont("Fira Code")
        if not font.exactMatch():
            font = QFont("Consolas")
        if not font.exactMatch():
            font = QFont("Monospace")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        s.setFont(font)

    def _apply_lexer_for(self, path: Path) -> None:
        lexer_cls = pick_lexer_class(path.suffix)
        if lexer_cls is None:
            self._scintilla.setLexer(None)
            return
        lexer = lexer_cls()
        
        # Apply VS Code Dark+ inspired colors
        lexer.setDefaultColor(QColor(QSCI_DARK["default_fg"]))
        lexer.setPaper(QColor(QSCI_DARK["default_bg"]))
        
        # Set syntax highlighting colors based on VS Code Dark+ theme
        self._apply_lexer_colors(lexer, path.suffix)
        
        self._scintilla.setLexer(lexer)

    def _apply_lexer_colors(self, lexer, suffix: str) -> None:
        """Apply VS Code Dark+ inspired syntax highlighting colors."""
        from PyQt5.Qsci import (
            QsciLexerPython, QsciLexerJavaScript, QsciLexerJSON,
            QsciLexerHTML, QsciLexerCSS, QsciLexerMarkdown,
            QsciLexerCPP, QsciLexerJava, QsciLexerRuby,
            QsciLexerBash, QsciLexerYAML, QsciLexerXML, QsciLexerSQL,
        )
        
        # Common color assignments
        color_map = {
            QsciLexerPython.Keyword:      QSCI_DARK["keyword"],
            QsciLexerPython.Number:       QSCI_DARK["number"],
            QsciLexerPython.DoubleQuotedString: QSCI_DARK["string"],
            QsciLexerPython.SingleQuotedString: QSCI_DARK["string"],
            QsciLexerPython.Comment:      QSCI_DARK["comment"],
            QsciLexerPython.Decorator:    QSCI_DARK["decorator"],
            QsciLexerPython.FunctionMethodName: QSCI_DARK["function"],
            QsciLexerPython.ClassName:    QSCI_DARK["type"],
        }
        
        # Apply colors to lexer
        for token, color in color_map.items():
            lexer.setColor(QColor(color), token)
    
    def _on_modified(self, *_args) -> None:
        self._emit_modified(True)

    def _emit_modified(self, modified: bool) -> None:
        self.modification_changed.emit(modified)

    def _on_cursor(self, line: int, col: int) -> None:
        # QScintilla is 0-based; callers expect 1-based.
        self.cursor_position_changed.emit(line + 1, col + 1)
