"""Qt bridge between the language-server client and editor widgets."""
from __future__ import annotations

import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

from PyQt5.QtCore import QObject, pyqtSignal

from app.lsp.manager import LspManager
from app.lsp.types import Diagnostic, Location, WorkspaceEdit


def path_uri(path: Path) -> str:
    return path.resolve().as_uri()


def uri_path(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


class LspBridge(QObject):
    """Non-blocking LSP operations suitable for a Qt application."""

    completion_ready = pyqtSignal(object)
    diagnostics_ready = pyqtSignal(str, object)
    definition_ready = pyqtSignal(object)
    rename_ready = pyqtSignal(object)
    status_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.manager = LspManager()
        self._registered: set[int] = set()
        self._versions: dict[str, int] = {}
        self._lock = threading.Lock()

    def _client(self, path: Path):
        client = self.manager.client_for_file(path)
        if client is None:
            return None
        identity = id(client)
        with self._lock:
            if identity not in self._registered:
                client.register_notification_handler(
                    "textDocument/publishDiagnostics",
                    lambda params: self._on_diagnostics(params),
                )
                self._registered.add(identity)
        return client

    def open_document(self, path: Path, text: str) -> None:
        def work() -> None:
            try:
                client = self._client(path)
                if client is None:
                    return
                uri = path_uri(path)
                version = self._versions.get(uri, 0) + 1
                self._versions[uri] = version
                if version == 1:
                    client.did_open(uri, self._language_id(path), text, version)
                else:
                    client.did_change(uri, [{"text": text}], version)
                self.status_changed.emit(f"Language server: {path.suffix.lower()}")
            except Exception as exc:
                self.status_changed.emit(f"Language server unavailable: {exc}")
        threading.Thread(target=work, daemon=True).start()

    def complete(self, path: Path, line: int, column: int) -> None:
        def work() -> None:
            client = self._client(path)
            if client:
                self.completion_ready.emit(client.completion(path_uri(path), line, column))
        threading.Thread(target=work, daemon=True).start()

    def definition(self, path: Path, line: int, column: int) -> None:
        def work() -> None:
            client = self._client(path)
            self.definition_ready.emit(client.definition(path_uri(path), line, column) if client else [])
        threading.Thread(target=work, daemon=True).start()

    def rename(self, path: Path, line: int, column: int, name: str) -> None:
        def work() -> None:
            client = self._client(path)
            self.rename_ready.emit(
                client.rename(path_uri(path), line, column, name) if client else None
            )
        threading.Thread(target=work, daemon=True).start()

    def _on_diagnostics(self, params) -> None:
        if not isinstance(params, dict):
            return
        uri = str(params.get("uri", ""))
        diagnostics = [
            Diagnostic.from_lsp(item)
            for item in (params.get("diagnostics") or [])
            if isinstance(item, dict)
        ]
        self.diagnostics_ready.emit(uri, diagnostics)

    @staticmethod
    def _language_id(path: Path) -> str:
        return {
            ".py": "python", ".pyw": "python", ".js": "javascript",
            ".mjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
            ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
        }.get(path.suffix.lower(), path.suffix.lower().lstrip("."))

    def shutdown(self) -> None:
        self.manager.shutdown()
