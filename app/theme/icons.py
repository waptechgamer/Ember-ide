"""Custom-painted icons for Ember IDE — VS Code Codicon-style.

All icons are drawn via QPainter so they scale cleanly and match
the dark theme without depending on external SVG/icon assets.
"""
from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
)


def _pixmap(size: int, paint_fn, color: str = "#858585") -> QPixmap:
    """Render a 1x1 icon-painting function into a QPixmap."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    rect = QRectF(0, 0, size, size)
    paint_fn(p, rect, size)
    p.end()
    return pm


# ---------------------------------------------------------------------------
# Explorer / Files icon — horizontal lines (like Codicon files)
# ---------------------------------------------------------------------------

def _paint_files(p: QPainter, rect: QRectF, size: int) -> None:
    m = size * 0.18  # margin
    w = size - 2 * m
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#858585"))
    # Three horizontal lines representing a file list
    line_h = size * 0.08
    gap = size * 0.12
    y_start = m + size * 0.15
    for i in range(4):
        lw = w * (0.7 + 0.1 * (i % 2))  # varying widths
        x_off = m + (w - lw) * 0.5
        p.drawRoundedRect(QRectF(x_off, y_start + i * (line_h + gap), lw, line_h), 1, 1)


# ---------------------------------------------------------------------------
# Search icon — magnifying glass
# ---------------------------------------------------------------------------

def _paint_search(p: QPainter, rect: QRectF, size: int) -> None:
    m = size * 0.2
    r = size * 0.25
    cx = m + r
    cy = m + r
    pen = QPen(QColor("#858585"), size * 0.1)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r, r)
    # Handle line
    hx = cx + r * 0.7
    hy = cy + r * 0.7
    p.drawLine(QPointF(hx, hy), QPointF(hx + r * 0.6, hy + r * 0.6))


# ---------------------------------------------------------------------------
# Source Control / Git icon — branching path
# ---------------------------------------------------------------------------

def _paint_git(p: QPainter, rect: QRectF, size: int) -> None:
    pen = QPen(QColor("#858585"), size * 0.09, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    m = size * 0.28
    mid_x = size * 0.45
    # Main vertical line (top to bottom)
    p.drawLine(QPointF(mid_x, m), QPointF(mid_x, size - m))
    # Top branch dot
    p.setBrush(QColor("#858585"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(mid_x, m), size * 0.06, size * 0.06)
    # Bottom branch dot
    p.drawEllipse(QPointF(mid_x, size - m), size * 0.06, size * 0.06)
    # Side branch line
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    branch_x = size * 0.72
    branch_y = size * 0.5
    p.drawPath(_arc_path(mid_x, m + size * 0.15, branch_x, branch_y, mid_x, size - m - size * 0.15))
    # Branch dot
    p.setBrush(QColor("#858585"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(branch_x, branch_y), size * 0.06, size * 0.06)


def _arc_path(x1, y1, cx, cy, x2, y2):
    """Create a smooth S-curve path."""
    path = QPainterPath()
    path.moveTo(x1, y1)
    path.cubicTo(cx, y1, cx, cy, cx, cy)
    path.cubicTo(cx, cy, cx, y2, x2, y2)
    return path


# ---------------------------------------------------------------------------
# Settings / Gear icon — hexagonal cog
# ---------------------------------------------------------------------------

def _paint_gear(p: QPainter, rect: QRectF, size: int) -> None:
    cx, cy = size / 2, size / 2
    outer_r = size * 0.30
    inner_r = size * 0.18
    tooth_r = size * 0.38
    tooth_w = size * 0.10
    n_teeth = 8

    # Outer gear teeth
    path = QPainterPath()
    for i in range(n_teeth):
        a1 = (i * 360 / n_teeth - 90) * 3.14159 / 180
        a2 = ((i + 0.35) * 360 / n_teeth - 90) * 3.14159 / 180
        a3 = ((i + 0.65) * 360 / n_teeth - 90) * 3.14159 / 180
        a4 = ((i + 1) * 360 / n_teeth - 90) * 3.14159 / 180
        # Inner arc
        path.moveTo(cx + outer_r * __import__('math').cos(a1), cy + outer_r * __import__('math').sin(a1))
        # Tooth up
        path.lineTo(cx + tooth_r * __import__('math').cos(a2), cy + tooth_r * __import__('math').sin(a2))
        # Tooth across
        path.lineTo(cx + tooth_r * __import__('math').cos(a3), cy + tooth_r * __import__('math').sin(a3))
        # Tooth down
        path.lineTo(cx + outer_r * __import__('math').cos(a4), cy + outer_r * __import__('math').sin(a4))

    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#858585"))
    p.drawPath(path)

    # Inner circle (hole)
    p.setBrush(QColor("#181818"))
    p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)


# ---------------------------------------------------------------------------
# Stop / Kill icon — filled square
# ---------------------------------------------------------------------------

def _paint_stop(p: QPainter, rect: QRectF, size: int) -> None:
    m = size * 0.3
    p.setBrush(QColor("#f48771"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(m, m, size - 2 * m, size - 2 * m), 2, 2)


# ---------------------------------------------------------------------------
# Plus icon — for "new terminal" etc.
# ---------------------------------------------------------------------------

def _paint_plus(p: QPainter, rect: QRectF, size: int) -> None:
    pen = QPen(QColor("#858585"), size * 0.1, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    m = size * 0.3
    mid = size / 2
    p.drawLine(QPointF(m, mid), QPointF(size - m, mid))
    p.drawLine(QPointF(mid, m), QPointF(mid, size - m))


# ---------------------------------------------------------------------------
# Close / X icon — for tab close buttons
# ---------------------------------------------------------------------------

def _paint_close(p: QPainter, rect: QRectF, size: int) -> None:
    pen = QPen(QColor("#858585"), size * 0.09, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    m = size * 0.28
    p.drawLine(QPointF(m, m), QPointF(size - m, size - m))
    p.drawLine(QPointF(size - m, m), QPointF(m, size - m))


# ---------------------------------------------------------------------------
# Chevron icons — for tree expand/collapse
# ---------------------------------------------------------------------------

def _paint_chevron_right(p: QPainter, rect: QRectF, size: int) -> None:
    pen = QPen(QColor("#858585"), size * 0.12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    m = size * 0.3
    p.drawPolyline(QPolygonF([
        QPointF(m, m),
        QPointF(size - m, size / 2),
        QPointF(m, size - m),
    ]))


def _paint_chevron_down(p: QPainter, rect: QRectF, size: int) -> None:
    pen = QPen(QColor("#858585"), size * 0.12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    m = size * 0.3
    p.drawPolyline(QPolygonF([
        QPointF(m, m),
        QPointF(size / 2, size - m),
        QPointF(size - m, m),
    ]))


# ---------------------------------------------------------------------------
# Folder icon (placeholder) — simple outline folder
# ---------------------------------------------------------------------------

def _paint_folder(p: QPainter, rect: QRectF, size: int) -> None:
    pen = QPen(QColor("#858585"), size * 0.06)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    m = size * 0.15
    tab_w = size * 0.25
    tab_h = size * 0.12
    # Folder body
    p.drawRoundedRect(QRectF(m, m + tab_h, size - 2 * m, size - 2 * m - tab_h), 3, 3)
    # Folder tab
    path = QPainterPath()
    path.moveTo(m, m + tab_h + 3)
    path.lineTo(m, m + 3)
    path.lineTo(m + tab_w, m + 3)
    path.lineTo(m + tab_w + 5, m + tab_h + 3)
    p.drawPath(path)


# ---------------------------------------------------------------------------
# Arrow left / right — for search navigation
# ---------------------------------------------------------------------------

def _paint_arrow_up(p: QPainter, rect: QRectF, size: int) -> None:
    pen = QPen(QColor("#d4d4d4"), size * 0.12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    m = size * 0.3
    p.drawPolyline(QPolygonF([
        QPointF(m, size - m),
        QPointF(size / 2, m),
        QPointF(size - m, size - m),
    ]))


def _paint_arrow_down(p: QPainter, rect: QRectF, size: int) -> None:
    pen = QPen(QColor("#d4d4d4"), size * 0.12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    m = size * 0.3
    p.drawPolyline(QPolygonF([
        QPointF(m, m),
        QPointF(size / 2, size - m),
        QPointF(size - m, m),
    ]))


# ---------------------------------------------------------------------------
# Public API — return QPixmaps ready for QLabel/QPushButton/QAction
# ---------------------------------------------------------------------------

def icon_files(size: int = 20, color: str = "#858585") -> QPixmap:
    return _pixmap(size, _paint_files, color)

def icon_search(size: int = 20, color: str = "#858585") -> QPixmap:
    return _pixmap(size, _paint_search, color)

def icon_git(size: int = 20, color: str = "#858585") -> QPixmap:
    return _pixmap(size, _paint_git, color)

def icon_gear(size: int = 20, color: str = "#858585") -> QPixmap:
    return _pixmap(size, _paint_gear, color)

def icon_stop(size: int = 16, color: str = "#f48771") -> QPixmap:
    return _pixmap(size, _paint_stop, color)

def icon_plus(size: int = 16, color: str = "#858585") -> QPixmap:
    return _pixmap(size, _paint_plus, color)

def icon_close(size: int = 12, color: str = "#858585") -> QPixmap:
    return _pixmap(size, _paint_close, color)

def icon_chevron_right(size: int = 12) -> QPixmap:
    return _pixmap(size, _paint_chevron_right)

def icon_chevron_down(size: int = 12) -> QPixmap:
    return _pixmap(size, _paint_chevron_down)

def icon_folder(size: int = 48, color: str = "#858585") -> QPixmap:
    return _pixmap(size, _paint_folder, color)

def icon_arrow_up(size: int = 16) -> QPixmap:
    return _pixmap(size, _paint_arrow_up)

def icon_arrow_down(size: int = 16) -> QPixmap:
    return _pixmap(size, _paint_arrow_down)
