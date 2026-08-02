"""LSP manager — lifecycle management for language servers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from app.lsp.client import LspClient
from app.lsp.languages import Language, language_registry
from app.lsp.servers import ServerSpec, server_registry


@dataclass
class LspConfig:
    """Configuration for the LSP manager."""
    enabled: bool = True
    max_concurrent_servers: int = 5


class LspManager:
    """Manages LSP server lifecycle per workspace/language."""

    def __init__(self, config: Optional[LspConfig] = None) -> None:
        self._config = config or LspConfig()
        self._clients: Dict[str, LspClient] = {}

    def client_for_file(self, path: Path) -> Optional[LspClient]:
        """Get or create an LSP client for the given file."""
        if not self._config.enabled:
            return None

        suffix = path.suffix.lower()
        language = language_registry.find(suffix)
        if language is None:
            return None

        if language.server_name in self._clients:
            return self._clients[language.server_name]

        spec = server_registry.find_for_language(language.lsp_language_id)
        if spec is None or not server_registry.is_available(spec):
            return None

        client = LspClient(spec.command, cwd=path.parent)
        if client.start():
            self._clients[language.server_name] = client
            return client
        return None

    def shutdown(self) -> None:
        for client in self._clients.values():
            client.stop()
        self._clients.clear()
