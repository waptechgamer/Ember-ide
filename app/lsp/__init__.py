"""Ember IDE — Universal Language Server Protocol package.

This package implements a *language-agnostic* LSP client. The architecture is:

    language_registry  → which file → which Language
    server_registry    → which Language → which LSP server command
    transport          → JSON-RPC over stdio (LSP framing)
    client             → typed RPC methods (initialize, didOpen, completion, …)
    manager            → lifecycle: starts/stops servers per workspace, calls client
    bridge             → Qt-facing adapter: diagnostics, completion popup, hover, …

Public surface (re-exported for convenience):

    from app.lsp import (
        Language, LanguageRegistry,
        ServerSpec, ServerRegistry,
        LspClient, LspManager, LspConfig,
        Position, Range, Location, TextEdit, Diagnostic, Hover,
        CompletionItem, SignatureHelp, SymbolInformation, WorkspaceEdit,
    )
"""
from __future__ import annotations

from app.lsp.types import (  # noqa: F401
    CompletionItem, Diagnostic, DiagnosticSeverity, Hover, Location, MarkupContent,
    MarkupKind, Position, Range, SignatureHelp, SymbolInformation, SymbolKind,
    TextEdit, VersionedTextDocumentIdentifier, WorkspaceEdit,
)
from app.lsp.languages import Language, LanguageRegistry, language_registry  # noqa: F401
from app.lsp.servers import ServerSpec, ServerRegistry, server_registry  # noqa: F401
from app.lsp.client import LspClient  # noqa: F401
from app.lsp.manager import LspConfig, LspManager  # noqa: F401
