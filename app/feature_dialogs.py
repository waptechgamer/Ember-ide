"""Qt dialogs for Ember IDE's project features."""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSpinBox, QTextEdit, QVBoxLayout,
)

from app.services import GitService, SearchMatch
from app.theme.dark_theme import PALETTE


def command_string(argv: list[str]) -> str:
    """Quote an argv list for the integrated shell."""
    return shlex.join([str(part) for part in argv])


class GitDialog(QDialog):
    def __init__(self, service: GitService, parent=None, on_changed: Callable | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.on_changed = on_changed
        self.setWindowTitle("Source Control")
        self.resize(620, 460)

        self.branch = QLabel()
        self.status = QListWidget()
        self.message = QLineEdit()
        self.message.setPlaceholderText("Commit message")

        refresh = QPushButton("Refresh")
        stage_all = QPushButton("Stage All")
        stage = QPushButton("Stage Selected")
        unstage = QPushButton("Unstage Selected")
        commit = QPushButton("Commit")
        history = QPushButton("Show History")
        refresh.clicked.connect(self.refresh)
        stage_all.clicked.connect(self._stage_all)
        stage.clicked.connect(lambda: self._stage_selected(True))
        unstage.clicked.connect(lambda: self._stage_selected(False))
        commit.clicked.connect(self._commit)
        history.clicked.connect(self._history)

        actions = QHBoxLayout()
        for button in (refresh, stage_all, stage, unstage):
            actions.addWidget(button)
        actions.addStretch()
        actions.addWidget(history)

        layout = QVBoxLayout(self)
        layout.addWidget(self.branch)
        layout.addWidget(self.status, 1)
        layout.addWidget(self.message)
        layout.addLayout(actions)
        layout.addWidget(commit)
        self.refresh()

    def refresh(self) -> None:
        self.branch.setText(
            f"Repository: {self.service.root or 'not found'}   Branch: {self.service.branch()}"
        )
        self.status.clear()
        for entry in self.service.status():
            item = QListWidgetItem(f"{entry.code}  {entry.path}")
            item.setData(Qt.UserRole, entry.path)
            item.setCheckState(Qt.Unchecked)
            self.status.addItem(item)
        if self.status.count() == 0:
            self.status.addItem("Working tree clean")

    def _selected(self) -> list[str]:
        return [
            self.status.item(i).data(Qt.UserRole)
            for i in range(self.status.count())
            if self.status.item(i).checkState() == Qt.Checked
            and self.status.item(i).data(Qt.UserRole)
        ]

    def _show_result(self, result) -> None:
        if not result.ok:
            QMessageBox.warning(self, "Git", result.stderr or result.stdout or "Git command failed.")
        else:
            self.refresh()
            if self.on_changed:
                self.on_changed()

    def _stage_all(self) -> None:
        self._show_result(self.service.stage_all())

    def _stage_selected(self, stage: bool) -> None:
        paths = self._selected()
        if paths:
            self._show_result(self.service.stage(paths) if stage else self.service.unstage(paths))

    def _commit(self) -> None:
        message = self.message.text().strip()
        if not message:
            QMessageBox.information(self, "Git", "Enter a commit message first.")
            return
        result = self.service.commit(message)
        self._show_result(result)
        if result.ok:
            self.message.clear()

    def _history(self) -> None:
        history = "\n".join(self.service.log())
        QMessageBox.information(self, "Git History", history or "No commits found.")


class WorkspaceSearchDialog(QDialog):
    def __init__(self, root: Path | None, parent=None, on_open: Callable | None = None) -> None:
        super().__init__(parent)
        self.root = root
        self.on_open = on_open
        self.setWindowTitle("Search Workspace")
        self.resize(760, 520)
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search across project files")
        self.regex = QCheckBox("Regular expression")
        self.case = QCheckBox("Match case")
        self.results = QListWidget()
        button = QPushButton("Search")
        button.clicked.connect(self.search)
        self.query.returnPressed.connect(self.search)
        self.results.itemDoubleClicked.connect(self._open)

        top = QHBoxLayout()
        top.addWidget(self.query, 1)
        top.addWidget(self.regex)
        top.addWidget(self.case)
        top.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.results, 1)

    def search(self) -> None:
        from app.services import WorkspaceSearch
        self.results.clear()
        matches = WorkspaceSearch(self.root).search(
            self.query.text(), self.regex.isChecked(), self.case.isChecked()
        )
        for match in matches:
            item = QListWidgetItem(f"{match.path}  ({match.line}:{match.column})  {match.text.strip()}")
            item.setData(Qt.UserRole, match)
            self.results.addItem(item)

    def _open(self, item: QListWidgetItem) -> None:
        if self.on_open:
            self.on_open(item.data(Qt.UserRole))


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None, on_apply: Callable | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.on_apply = on_apply
        self.setWindowTitle("Ember IDE Settings")
        self.resize(420, 260)
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 32)
        self.font_size.setValue(int(settings.value("editor/font_size", 10)))
        self.tab_width = QSpinBox()
        self.tab_width.setRange(1, 16)
        self.tab_width.setValue(int(settings.value("editor/tab_width", 4)))
        self.auto_complete = QCheckBox()
        self.auto_complete.setChecked(settings.value("editor/autocomplete", True, type=bool))
        self.confirm_delete = QCheckBox()
        self.confirm_delete.setChecked(settings.value("files/confirm_delete", True, type=bool))

        form = QFormLayout()
        form.addRow("Editor font size", self.font_size)
        form.addRow("Tab width", self.tab_width)
        form.addRow("Enable autocomplete", self.auto_complete)
        form.addRow("Confirm file deletion", self.confirm_delete)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Settings are stored for this Ember IDE installation."))
        layout.addWidget(buttons)

    def _save(self) -> None:
        self.settings.setValue("editor/font_size", self.font_size.value())
        self.settings.setValue("editor/tab_width", self.tab_width.value())
        self.settings.setValue("editor/autocomplete", self.auto_complete.isChecked())
        self.settings.setValue("files/confirm_delete", self.confirm_delete.isChecked())
        self.settings.sync()
        if self.on_apply:
            self.on_apply()
        self.accept()


class CommandListDialog(QDialog):
    """List tasks, packages, or extensions and optionally return a selection."""
    def __init__(self, title: str, entries: dict[str, str] | list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 360)
        self.list = QListWidget()
        if isinstance(entries, dict):
            for name, command in entries.items():
                item = QListWidgetItem(f"{name}  —  {command}")
                item.setData(Qt.UserRole, (name, command))
                self.list.addItem(item)
        else:
            for entry in entries:
                self.list.addItem(str(entry))
        self.list.itemDoubleClicked.connect(self.accept)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addWidget(close)

    def selected(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None


class PackageDialog(QDialog):
    def __init__(self, ecosystem: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Package Manager")
        self.action = QComboBox()
        self.action.addItems(["install", "remove", "list"])
        self.package = QLineEdit()
        self.package.setPlaceholderText("Package name (not needed for list)")
        form = QFormLayout()
        form.addRow("Ecosystem", QLabel(ecosystem))
        form.addRow("Action", self.action)
        form.addRow("Package", self.package)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def request(self) -> tuple[str, str]:
        return self.action.currentText(), self.package.text().strip()


class ProblemsDialog(QDialog):
    def __init__(self, problems: list[tuple[int, str]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Problems")
        self.resize(600, 320)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(
            "\n".join(f"Line {line}: {message}" for line, message in problems)
            or "No problems detected."
        )
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(view)
        layout.addWidget(close)