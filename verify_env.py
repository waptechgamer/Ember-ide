"""
Ember IDE — Environment Verification Script (Phase 0)

Tests that every required dependency is installed, importable, and reports
its version. Also reports platform, Python, and venv info.

Usage:
    venv\\Scripts\\python.exe verify_env.py
"""
from __future__ import annotations

import importlib
import platform
import sys
import sysconfig
from pathlib import Path

REQUIRED = {
    "PySide6": ("PySide6", "PySide6.QtWidgets"),
    "QScintilla": ("PyQt5.Qsci", None),  # current QScintilla wheels bind to PyQt5
    "python-lsp-server": ("pylsp", None),
    "jedi": ("jedi", None),
    "requests": ("requests", None),
    "markdown": ("markdown", None),
    "pygments": ("pygments", None),
}

# Distribution names → importable module names (canonical case matters on Windows)
DIST_VERSION_PKGS = {
    "PySide6": "PySide6",
    "QScintilla": "QScintilla",
    "python-lsp-server": "python-lsp-server",
    "jedi": "jedi",
    "requests": "requests",
    "markdown": "markdown",
    "pygments": "Pygments",
}


def get_version(module_name: str) -> str:
    try:
        mod = importlib.import_module(module_name)
        ver = getattr(mod, "__version__", None)
        if ver:
            return ver
        return "unknown"
    except Exception as exc:  # pragma: no cover
        return f"error: {exc}"


def check(name: str, modules: tuple[str, str | None]) -> tuple[bool, str]:
    primary, secondary = modules
    try:
        importlib.import_module(primary)
        if secondary:
            importlib.import_module(secondary)
        return True, get_version(primary)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    print("=" * 60)
    print("Ember IDE — Environment Report")
    print("=" * 60)
    print(f"Platform     : {platform.platform()}")
    print(f"Architecture : {platform.machine()}")
    print(f"Python       : {sys.version}")
    print(f"Executable   : {sys.executable}")
    print(f"Prefix       : {sys.prefix}")
    print(f"Base prefix  : {sysconfig.get_platform()}")
    print(f"venv active  : {sys.prefix != sys.base_prefix}")
    print(f"CWD          : {Path.cwd()}")
    print("-" * 60)
    print(f"{'Package':<22} {'Status':<8} Version")
    print("-" * 60)

    failures = 0
    for name, modules in REQUIRED.items():
        ok, info = check(name, modules)
        status = "OK" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"{name:<22} {status:<8} {info}")

    print("-" * 60)
    if failures:
        print(f"Result: {failures} package(s) FAILED")
        return 1
    print("Result: all required packages importable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
