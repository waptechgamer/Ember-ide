"""Handlers for the explorer's context actions: new file/folder, rename, delete.

Pure functions where possible; the explorer invokes them through
``ExplorerActions`` so error reporting stays in one place.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtWidgets import QInputDialog, QMessageBox, QWidget

from app.utils.file_utils import (
    is_hidden, normalize, safe_new_dir, safe_new_file,
)


class ExplorerActions:
    """Stateless action handlers. ``parent`` is used for dialog parenting."""

    def __init__(self, parent: QWidget, on_after: Optional[Callable[[], None]] = None) -> None:
        self._parent = parent
        self._on_after = on_after or (lambda: None)

    # ------------------------------------------------------------------ API

    def new_file(self, folder: Path) -> Optional[Path]:
        folder = normalize(folder)
        name, ok = QInputDialog.getText(
            self._parent, "New File", "File name:", text="untitled.txt",
        )
        if not ok or not name.strip():
            return None
        target = folder / name.strip()
        try:
            safe_new_file(target)
        except FileExistsError:
            QMessageBox.warning(self._parent, "New File", f"Already exists:\n{target}")
            return None
        except OSError as exc:
            QMessageBox.warning(self._parent, "New File", f"Could not create:\n{exc}")
            return None
        self._on_after()
        return target

    def new_folder(self, folder: Path) -> Optional[Path]:
        folder = normalize(folder)
        name, ok = QInputDialog.getText(
            self._parent, "New Folder", "Folder name:", text="new_folder",
        )
        if not ok or not name.strip():
            return None
        target = folder / name.strip()
        try:
            safe_new_dir(target)
        except FileExistsError:
            QMessageBox.warning(self._parent, "New Folder", f"Already exists:\n{target}")
            return None
        except OSError as exc:
            QMessageBox.warning(self._parent, "New Folder", f"Could not create:\n{exc}")
            return None
        self._on_after()
        return target

    def rename(self, path: Path) -> Optional[Path]:
        path = normalize(path)
        new_name, ok = QInputDialog.getText(
            self._parent, "Rename", "New name:", text=path.name,
        )
        if not ok or not new_name.strip() or new_name.strip() == path.name:
            return None
        target = path.with_name(new_name.strip())
        if target.exists():
            QMessageBox.warning(self._parent, "Rename", f"Already exists:\n{target}")
            return None
        try:
            path.rename(target)
        except OSError as exc:
            QMessageBox.warning(self._parent, "Rename", f"Could not rename:\n{exc}")
            return None
        self._on_after()
        return target

    def delete(self, path: Path) -> bool:
        path = normalize(path)
        kind = "folder" if path.is_dir() else "file"
        choice = QMessageBox.question(
            self._parent, f"Delete {kind}",
            f"Delete {kind} '{path.name}'?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if choice != QMessageBox.Yes:
            return False
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            QMessageBox.warning(self._parent, "Delete", f"Could not delete:\n{exc}")
            return False
        self._on_after()
        return True
