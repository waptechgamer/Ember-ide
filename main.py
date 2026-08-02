"""Ember IDE — entry point.

Run with:
    venv\\Scripts\\python.exe main.py
"""
from __future__ import annotations

import sys

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QApplication

from app.main_window import MainWindow
from app.theme.dark_theme import apply_dark_theme


def main() -> int:
    QCoreApplication.setOrganizationName("Ember")
    QCoreApplication.setApplicationName("Ember IDE")
    QCoreApplication.setApplicationVersion("0.1.0")

    app = QApplication(sys.argv)
    apply_dark_theme(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
