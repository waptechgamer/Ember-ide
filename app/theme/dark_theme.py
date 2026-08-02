"""Dark theme — palette, stylesheet, and QScintilla color helpers.

VS Code-inspired dark theme with refined colors and modern styling.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt  # noqa: F401  (used in stylesheet-driven enum lookups)
from PyQt5.QtGui import QColor, QFont, QPalette

# ---------------------------------------------------------------------------
# Palette — VS Code Dark+ inspired colors
# ---------------------------------------------------------------------------
PALETTE = {
    # Core backgrounds
    "bg":              "#1e1e1e",  # Main editor background
    "bg_alt":          "#252526",  # Side panel, tabs background
    "bg_elevated":     "#2d2d2d",  # Elevated surfaces (menus, popups)
    "bg_sunken":       "#181818",  # Sunken areas (status bar)
    "panel":           "#333333",  # Hover states, subtle highlights
    
    # Borders
    "border":          "#3c3c3c",  # Default border
    "border_light":    "#474747",  # Lighter border for focus
    "border_accent":   "#007acc",  # Accent border for focus states
    
    # Text colors
    "fg":              "#d4d4d4",  # Primary text
    "fg_dim":          "#858585",  # Secondary text
    "fg_bright":       "#e0e0e0",  # Bright text for emphasis
    "fg_disabled":     "#5a5a5a",  # Disabled text
    
    # Accent colors (VS Code Blue theme)
    "accent":          "#007acc",  # Primary accent
    "accent_hover":    "#1c8cd9",  # Accent hover
    "accent_pressed":  "#005a9e",  # Accent pressed
    
    # Status colors
    "selection":       "#264f78",  # Selection background
    "selection_dim":   "#1a3a5c",  # Dimmed selection
    "error":           "#f48771",  # Error red
    "warning":         "#cca700",  # Warning yellow
    "success":         "#89d185",  # Success green
    "info":            "#75beff",  # Info blue
    
    # Special
    "hidden_fg":       "#5a5a5a",  # Greyed-out explorer items
    "link":            "#3794ff",  # Link color
    "find_match":      "#515c6a",  # Find match highlight
}

# ---------------------------------------------------------------------------
# Enhanced stylesheet — VS Code-inspired modern styling
# ---------------------------------------------------------------------------
STYLESHEET = f"""
/* ================================================================
   Global styles
   ================================================================ */
QMainWindow {{
    background: {PALETTE['bg']};
    color: {PALETTE['fg']};
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", sans-serif;
}}
QWidget {{
    background: transparent;
    color: {PALETTE['fg']};
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", sans-serif;
}}

/* ================================================================
   Menu bar
   ================================================================ */
QMenuBar {{
    background: {PALETTE['bg_alt']};
    color: {PALETTE['fg']};
    border-bottom: 1px solid {PALETTE['border']};
    padding: 0;
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: 0;
    margin: 0;
}}
QMenuBar::item:selected {{
    background: {PALETTE['panel']};
}}
QMenuBar::item:pressed {{
    background: {PALETTE['accent']};
}}

/* ================================================================
   Drop-down menus
   ================================================================ */
QMenu {{
    background: {PALETTE['bg_elevated']};
    color: {PALETTE['fg']};
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 24px 6px 28px;
    border-radius: 4px;
    margin: 0 4px;
}}
QMenu::item:selected {{
    background: {PALETTE['accent']};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {PALETTE['border']};
    margin: 4px 12px;
}}
QMenu::item:disabled {{
    color: {PALETTE['fg_disabled']};
}}

/* ================================================================
   Toolbar
   ================================================================ */
QToolBar {{
    background: {PALETTE['bg_alt']};
    border-bottom: 1px solid {PALETTE['border']};
    spacing: 2px;
    padding: 2px 4px;
}}
QToolBar::separator {{
    width: 1px;
    background: {PALETTE['border']};
    margin: 4px 4px;
}}
QToolBar QToolButton {{
    background: transparent;
    color: {PALETTE['fg']};
    padding: 4px 6px;
    border-radius: 3px;
    border: none;
    min-width: 26px;
    min-height: 26px;
}}
QToolBar QToolButton:hover {{
    background: {PALETTE['panel']};
}}
QToolBar QToolButton:pressed {{
    background: {PALETTE['accent']};
    color: white;
}}

/* ================================================================
   Status bar
   ================================================================ */
QStatusBar {{
    background: {PALETTE['accent']};
    color: white;
    border: none;
    padding: 0;
    font-size: 12px;
    font-weight: 500;
}}
QStatusBar::item {{
    border: none;
}}
QStatusBar QLabel {{
    color: white;
    padding: 2px 6px;
}}

/* ================================================================
   Splitters
   ================================================================ */
QSplitter::handle {{
    background: {PALETTE['border']};
}}
QSplitter::handle:hover {{
    background: {PALETTE['accent']};
}}
QSplitter::handle:horizontal {{
    width: 2px;
    margin: 0;
}}
QSplitter::handle:vertical {{
    height: 2px;
    margin: 0;
}}

/* ================================================================
   Tab widget — VS Code style
   ================================================================ */
QTabWidget::pane {{
    border: 0;
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
    width: 16px;
    height: 16px;
}}
QTabBar::close-button:hover {{
    background: rgba(255, 255, 255, 0.2);
    border-radius: 3px;
}}

/* ================================================================
   Tree view (File Explorer)
   ================================================================ */
QTreeView {{
    background: {PALETTE['bg_alt']};
    color: {PALETTE['fg']};
    border: 0;
    outline: none;
    selection-background-color: {PALETTE['selection']};
    selection-color: white;
    font-size: 13px;
}}
QTreeView::item {{
    padding: 3px 8px;
    border-radius: 4px;
    margin: 1px 4px;
}}
QTreeView::item:selected {{
    background: {PALETTE['selection']};
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

/* ================================================================
   Header view
   ================================================================ */
QHeaderView::section {{
    background: {PALETTE['bg_alt']};
    color: {PALETTE['fg_dim']};
    border: 0;
    border-right: 1px solid {PALETTE['border']};
    border-bottom: 1px solid {PALETTE['border']};
    padding: 4px 8px;
    font-weight: 500;
}}

/* ================================================================
   Scroll bars — VS Code thin style
   ================================================================ */
QScrollBar:vertical {{
    background: transparent;
    border: 0;
    width: 8px;
    margin: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    border: 0;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle {{
    background: rgba(121, 121, 121, 0.4);
    border-radius: 4px;
    min-height: 30px;
    min-width: 30px;
}}
QScrollBar::handle:hover {{
    background: rgba(121, 121, 121, 0.7);
}}
QScrollBar::handle:pressed {{
    background: rgba(121, 121, 121, 0.9);
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* ================================================================
   Dialogs
   ================================================================ */
QMessageBox, QInputDialog {{
    background: {PALETTE['bg_elevated']};
    color: {PALETTE['fg']};
    border: 1px solid {PALETTE['border']};
    border-radius: 6px;
}}

/* ================================================================
   Buttons — VS Code style
   ================================================================ */
QPushButton {{
    background: {PALETTE['accent']};
    color: white;
    border: none;
    padding: 5px 14px;
    border-radius: 4px;
    font-weight: 500;
    min-height: 20px;
}}
QPushButton:hover {{
    background: {PALETTE['accent_hover']};
}}
QPushButton:pressed {{
    background: {PALETTE['accent_pressed']};
}}
QPushButton:disabled {{
    background: {PALETTE['panel']};
    color: {PALETTE['fg_disabled']};
}}
QPushButton:flat {{
    background: transparent;
    border: none;
}}
QPushButton:flat:hover {{
    background: {PALETTE['panel']};
}}
QPushButton#welcomeBtnPrimary {{
    background: {PALETTE['accent']};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0 20px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#welcomeBtnPrimary:hover {{
    background: {PALETTE['accent_hover']};
}}
QPushButton#welcomeBtnPrimary:pressed {{
    background: {PALETTE['accent_pressed']};
}}
QPushButton#welcomeBtnSecondary {{
    background: transparent;
    color: {PALETTE['accent']};
    border: 1px solid {PALETTE['border']};
    border-radius: 4px;
    padding: 0 20px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#welcomeBtnSecondary:hover {{
    border-color: {PALETTE['accent']};
    background: rgba(0, 122, 204, 0.08);
}}
QPushButton#welcomeBtnSecondary:pressed {{
    background: rgba(0, 122, 204, 0.15);
}}
QPushButton#explorerBtnPrimary {{
    background: {PALETTE['accent']};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0 24px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#explorerBtnPrimary:hover {{
    background: {PALETTE['accent_hover']};
}}
QPushButton#explorerBtnPrimary:pressed {{
    background: {PALETTE['accent_pressed']};
}}
QPushButton#explorerBtnLink {{
    background: transparent;
    color: {PALETTE['accent']};
    border: none;
    padding: 8px 16px;
    font-size: 13px;
}}
QPushButton#explorerBtnLink:hover {{
    color: {PALETTE['accent_hover']};
    text-decoration: underline;
}}
QPushButton#terminalStop {{
    background: {PALETTE['error']};
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 3px;
    font-weight: 500;
}}
QPushButton#terminalStop:hover {{
    background: #e85d51;
}}
QPushButton#terminalStop:disabled {{
    background: {PALETTE['panel']};
    color: {PALETTE['fg_disabled']};
}}

/* ================================================================
   Line edit — VS Code style
   ================================================================ */
QLineEdit {{
    background: {PALETTE['bg_sunken']};
    color: {PALETTE['fg']};
    border: 1px solid {PALETTE['border']};
    border-radius: 3px;
    padding: 4px 8px;
    selection-background-color: {PALETTE['selection']};
}}
QLineEdit:focus {{
    border-color: {PALETTE['accent']};
}}
QLineEdit:disabled {{
    background: {PALETTE['panel']};
    color: {PALETTE['fg_disabled']};
}}

/* ================================================================
   Combo box
   ================================================================ */
QComboBox {{
    background: {PALETTE['bg_sunken']};
    color: {PALETTE['fg']};
    border: 1px solid {PALETTE['border']};
    border-radius: 3px;
    padding: 3px 8px;
    min-height: 22px;
}}
QComboBox:hover {{
    border-color: {PALETTE['border_light']};
}}
QComboBox:focus {{
    border-color: {PALETTE['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {PALETTE['fg_dim']};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {PALETTE['bg_elevated']};
    color: {PALETTE['fg']};
    border: 1px solid {PALETTE['border']};
    border-radius: 3px;
    selection-background-color: {PALETTE['accent']};
    selection-color: white;
    padding: 4px 0;
}}

/* ================================================================
   Check box & Radio button
   ================================================================ */
QCheckBox, QRadioButton {{
    color: {PALETTE['fg']};
    spacing: 8px;
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {PALETTE['fg_disabled']};
}}

/* ================================================================
   Group box
   ================================================================ */
QGroupBox {{
    color: {PALETTE['fg']};
    border: 1px solid {PALETTE['border']};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: 500;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

/* ================================================================
   Tooltip
   ================================================================ */
QToolTip {{
    background: {PALETTE['bg_elevated']};
    color: {PALETTE['fg']};
    border: 1px solid {PALETTE['border_light']};
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 12px;
}}

/* ================================================================
   Integrated terminal — VS Code style
   ================================================================ */
QPlainTextEdit[role="terminal"] {{
    background: {PALETTE['bg_sunken']};
    color: {PALETTE['fg']};
    border: none;
    selection-background-color: {PALETTE['selection']};
    font-family: "Cascadia Code", "JetBrains Mono", "Fira Code", "Consolas", "Monospace";
    font-size: 13px;
    padding: 8px;
}}
QLineEdit[role="terminal-input"] {{
    background: {PALETTE['bg_sunken']};
    color: {PALETTE['fg']};
    border: 1px solid {PALETTE['border']};
    border-radius: 4px;
    padding: 8px 12px;
    font-family: "Cascadia Code", "JetBrains Mono", "Fira Code", "Consolas", "Monospace";
    font-size: 13px;
    selection-background-color: {PALETTE['selection']};
}}
QLineEdit[role="terminal-input"]:focus {{
    border-color: {PALETTE['accent']};
}}

/* ================================================================
   Scroll area
   ================================================================ */
QScrollArea {{
    border: none;
    background: transparent;
}}

/* ================================================================
   Progress bar
   ================================================================ */
QProgressBar {{
    background: {PALETTE['bg_sunken']};
    border: none;
    border-radius: 3px;
    text-align: center;
    color: {PALETTE['fg']};
    height: 4px;
}}
QProgressBar::chunk {{
    background: {PALETTE['accent']};
    border-radius: 3px;
}}
"""


def apply_dark_theme(app) -> None:
    """Configure a QApplication with the VS Code-inspired dark palette + stylesheet."""
    palette = QPalette()
    
    # Core palette
    palette.setColor(QPalette.Window, QColor(PALETTE["bg"]))
    palette.setColor(QPalette.WindowText, QColor(PALETTE["fg"]))
    palette.setColor(QPalette.Base, QColor(PALETTE["bg"]))
    palette.setColor(QPalette.AlternateBase, QColor(PALETTE["bg_alt"]))
    palette.setColor(QPalette.Text, QColor(PALETTE["fg"]))
    palette.setColor(QPalette.Button, QColor(PALETTE["panel"]))
    palette.setColor(QPalette.ButtonText, QColor(PALETTE["fg"]))
    
    # Highlight / Selection
    palette.setColor(QPalette.Highlight, QColor(PALETTE["accent"]))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    
    # Placeholder text
    palette.setColor(QPalette.PlaceholderText, QColor(PALETTE["fg_dim"]))
    
    # Link colors
    palette.setColor(QPalette.Link, QColor(PALETTE["link"]))
    palette.setColor(QPalette.LinkVisited, QColor(PALETTE["accent"]))
    
    # Disabled states
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(PALETTE["fg_disabled"]))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(PALETTE["fg_disabled"]))
    
    # Tooltips
    palette.setColor(QPalette.ToolTipBase, QColor(PALETTE["bg_elevated"]))
    palette.setColor(QPalette.ToolTipText, QColor(PALETTE["fg"]))
    
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)

    # VS Code-inspired UI font
    font = QFont("Segoe UI")
    font.setStyleHint(QFont.SansSerif)
    font.setPointSize(10)
    app.setFont(font)


# ---------------------------------------------------------------------------
# QScintilla (PyQt5) colors — VS Code Dark+ inspired syntax highlighting
# ---------------------------------------------------------------------------
QSCI_DARK = {
    # Base colors
    "default_fg":     0xD4D4D4,
    "default_bg":     0x1E1E1E,
    "caret_fg":       0xAEAFAD,
    "selection_bg":   0x264F78,
    
    # Line numbers / margins
    "margin_bg":      0x252526,
    "margin_fg":      0x858585,
    "margin_border":  0x3C3C3C,
    
    # Line highlight
    "line_highlight_bg": 0x2A2D2E,
    
    # Syntax colors (VS Code Dark+ theme)
    "keyword":        0x569CD6,   # Blue - keywords
    "function":       0xDCDCAA,   # Yellow - functions
    "string":         0xCE9178,   # Orange - strings
    "number":         0xB5CEA8,   # Green - numbers
    "comment":        0x6A9955,   # Green - comments
    "type":           0x4EC9B0,   # Teal - types
    "variable":       0x9CDCFE,   # Light blue - variables
    "operator":       0xD4D4D4,   # White - operators
    "constant":       0x4FC1FF,   # Light blue - constants
    "preprocessor":   0xC586C0,   # Purple - preprocessor
    "decorator":      0xDCDCAA,   # Yellow - decorators
    "tag":            0x569CD6,   # Blue - HTML tags
    "attribute":      0x9CDCFE,   # Light blue - HTML attributes
    "regex":          0xD16969,   # Red - regex
}

LANG_LEXERS = {
    # extension → (QsciLexer class name, lexer-dark-fg override)
    ".py":   ("QsciLexerPython",),
    ".js":   ("QsciLexerJavaScript",),
    ".ts":   ("QsciLexerJavaScript",),
    ".json": ("QsciLexerJSON",),
    ".html": ("QsciLexerHTML",),
    ".css":  ("QsciLexerCSS",),
    ".md":   ("QsciLexerMarkdown",),
    ".c":    ("QsciLexerCPP",),       # QScintilla builds vary; CPP covers C too
    ".cpp":  ("QsciLexerCPP",),
    ".h":    ("QsciLexerCPP",),
    ".hpp":  ("QsciLexerCPP",),
    ".java": ("QsciLexerJava",),
    ".rb":   ("QsciLexerRuby",),
    ".sh":   ("QsciLexerBash",),
    ".yaml": ("QsciLexerYAML",),
    ".yml":  ("QsciLexerYAML",),
    ".xml":  ("QsciLexerXML",),
    ".sql":  ("QsciLexerSQL",),
}


def pick_lexer_class(suffix: str):
    """Return the QsciLexer* class for a given file suffix, or None."""
    if not suffix:
        return None
    from PyQt5.Qsci import (  # noqa: import-outside-toplevel
        QsciLexerPython, QsciLexerJavaScript, QsciLexerJSON,
        QsciLexerHTML, QsciLexerCSS, QsciLexerMarkdown,
        QsciLexerCPP, QsciLexerJava, QsciLexerRuby,
        QsciLexerBash, QsciLexerYAML, QsciLexerXML, QsciLexerSQL,
    )
    table = {
        ".py":   QsciLexerPython,
        ".js":   QsciLexerJavaScript,
        ".ts":   QsciLexerJavaScript,
        ".json": QsciLexerJSON,
        ".html": QsciLexerHTML,
        ".css":  QsciLexerCSS,
        ".md":   QsciLexerMarkdown,
        ".c":    QsciLexerCPP,
        ".cpp":  QsciLexerCPP,
        ".h":    QsciLexerCPP,
        ".hpp":  QsciLexerCPP,
        ".java": QsciLexerJava,
        ".rb":   QsciLexerRuby,
        ".sh":   QsciLexerBash,
        ".yaml": QsciLexerYAML,
        ".yml":  QsciLexerYAML,
        ".xml":  QsciLexerXML,
        ".sql":  QsciLexerSQL,
    }
    return table.get(suffix.lower())
