"""Server registry — maps language IDs to LSP server commands."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ServerSpec:
    """Specification for an LSP server."""
    name: str
    command: List[str]
    language_ids: List[str] = None

    def __post_init__(self) -> None:
        if self.language_ids is None:
            self.language_ids = []


class ServerRegistry:
    """Registry of known LSP servers."""

    def __init__(self) -> None:
        self._servers: dict[str, ServerSpec] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(ServerSpec(
            name="pylsp",
            command=["pylsp"],
            language_ids=["python"],
        ))
        self.register(ServerSpec(
            name="clangd",
            command=["clangd"],
            language_ids=["c", "cpp"],
        ))

    def register(self, server: ServerSpec) -> None:
        self._servers[server.name] = server

    def find_for_language(self, language_id: str) -> Optional[ServerSpec]:
        for server in self._servers.values():
            if language_id in server.language_ids:
                return server
        return None

    def find(self, name: str) -> Optional[ServerSpec]:
        return self._servers.get(name)

    def is_available(self, server: ServerSpec) -> bool:
        return shutil.which(server.command[0]) is not None

    def all(self) -> List[ServerSpec]:
        return list(self._servers.values())


server_registry = ServerRegistry()
