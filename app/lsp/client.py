"""LSP client — JSON-RPC transport over stdio."""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.lsp.types import (
    CompletionItem, Diagnostic, DiagnosticSeverity, Hover, Location,
    Position, Range, SignatureHelp, WorkspaceEdit,
)


class LspClient:
    """A minimal LSP client that communicates via stdio JSON-RPC."""

    def __init__(self, command: List[str], cwd: Optional[Path] = None) -> None:
        self._command = command
        self._cwd = str(cwd) if cwd else None
        self._proc: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._callbacks: Dict[int, threading.Event] = {}
        self._responses: Dict[int, Any] = {}
        self._running = False

    def start(self) -> bool:
        try:
            self._proc = subprocess.Popen(
                self._command,
                cwd=self._cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._running = True
            threading.Thread(target=self._read_loop, daemon=True).start()
            self.initialize()
            return True
        except Exception:
            return False

    def stop(self) -> None:
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def _read_loop(self) -> None:
        if not self._proc or not self._proc.stdout:
            return
        try:
            while self._running:
                header = self._proc.stdout.readline()
                if not header:
                    break
                content_length = 0
                while True:
                    line = self._proc.stdout.readline()
                    if line == b"\r\n" or line == b"\n":
                        break
                    if line.startswith(b"Content-Length:"):
                        content_length = int(line.split(b":")[1].strip())
                if content_length > 0:
                    body = self._proc.stdout.read(content_length)
                    msg = json.loads(body.decode("utf-8"))
                    if "id" in msg and msg["id"] in self._callbacks:
                        self._responses[msg["id"]] = msg.get("result")
                        self._callbacks[msg["id"]].set()
        except Exception:
            pass

    def _send(self, method: str, params: Optional[Dict[str, Any]] = None) -> int:
        with self._lock:
            self._request_id += 1
            msg_id = self._request_id
        msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params:
            msg["params"] = params
        body = json.dumps(msg)
        if self._proc and self._proc.stdin:
            self._proc.stdin.write(
                f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}".encode("utf-8")
            )
            self._proc.stdin.flush()
        event = threading.Event()
        self._callbacks[msg_id] = event
        return msg_id

    def _call(self, method: str, params: Optional[Dict[str, Any]] = None,
              timeout: float = 5.0) -> Any:
        msg_id = self._send(method, params)
        event = self._callbacks.get(msg_id)
        if event:
            event.wait(timeout)
        return self._responses.pop(msg_id, None)

    def initialize(self) -> Any:
        return self._call("initialize", {
            "processId": None,
            "rootUri": None,
            "capabilities": {},
        })

    def did_open(self, uri: str, language_id: str, text: str, version: int = 1) -> None:
        self._send("textDocument/didOpen", {
            "textDocument": {"uri": uri, "languageId": language_id, "version": version, "text": text},
        })

    def did_change(self, uri: str, changes: List[Dict[str, Any]], version: int) -> None:
        self._send("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": version},
            "contentChanges": changes,
        })

    def completion(self, uri: str, line: int, character: int) -> List[CompletionItem]:
        result = self._call("textDocument/completion", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        if result is None:
            return []
        items = result if isinstance(result, list) else result.get("items", [])
        return [CompletionItem.from_lsp(i) for i in items]

    def hover(self, uri: str, line: int, character: int) -> Optional[Hover]:
        result = self._call("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        return Hover.from_lsp(result) if result else None

    def definition(self, uri: str, line: int, character: int) -> List[Location]:
        result = self._call("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        if not result:
            return []
        if isinstance(result, dict):
            result = [result]
        return [Location.from_lsp(loc) for loc in result if loc]

    def references(self, uri: str, line: int, character: int) -> List[Location]:
        result = self._call("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        if not result:
            return []
        return [Location.from_lsp(loc) for loc in result if loc]
