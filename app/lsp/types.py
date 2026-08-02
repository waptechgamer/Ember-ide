"""LSP protocol types — language-agnostic data shapes.

We model the subset of LSP we actually use, with plain dataclasses, so:

* the rest of the package can talk in typed objects, not raw dicts;
* tests can construct and assert against real values;
* future LSP versions / extensions slot in without rewrites.

These mirror the LSP 3.17 spec names but only the fields we read. Server
payloads we don't model simply stay as dicts; the client never reaches
into them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


# ---------------------------------------------------------------------------
# Position / range
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Position:
    """Zero-based line/character position in a text document.

    LSP positions are zero-based even though the QScintilla API is zero-based
    too — convenient — but our editor exposes 1-based positions to users.
    Use ``Position.from_qsci(line0, col0)`` at the editor boundary.
    """

    line: int
    character: int

    def to_lsp(self) -> dict[str, int]:
        return {"line": self.line, "character": self.character}

    @classmethod
    def from_lsp(cls, d: dict[str, Any] | None) -> "Position | None":
        if d is None:
            return None
        return cls(line=int(d.get("line", 0)), character=int(d.get("character", 0)))


@dataclass(frozen=True)
class Range:
    start: Position
    end: Position

    def to_lsp(self) -> dict[str, Any]:
        return {"start": self.start.to_lsp(), "end": self.end.to_lsp()}

    @classmethod
    def from_lsp(cls, d: dict[str, Any] | None) -> "Range | None":
        if d is None:
            return None
        s = Position.from_lsp(d.get("start")) or Position(0, 0)
        e = Position.from_lsp(d.get("end")) or Position(0, 0)
        return cls(start=s, end=e)


# ---------------------------------------------------------------------------
# Locations and edits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Location:
    uri: str
    range: Range

    @classmethod
    def from_lsp(cls, d: dict[str, Any] | None) -> "Location | None":
        if d is None:
            return None
        return cls(
            uri=str(d.get("uri", "")),
            range=Range.from_lsp(d.get("range")) or Range(Position(0, 0), Position(0, 0)),
        )


@dataclass
class TextEdit:
    range: Range
    new_text: str

    def to_lsp(self) -> dict[str, Any]:
        return {"range": self.range.to_lsp(), "newText": self.new_text}

    @classmethod
    def from_lsp(cls, d: dict[str, Any] | None) -> "TextEdit | None":
        if d is None:
            return None
        return cls(
            range=Range.from_lsp(d.get("range")) or Range(Position(0, 0), Position(0, 0)),
            new_text=str(d.get("newText", "")),
        )


# ---------------------------------------------------------------------------
# Markup
# ---------------------------------------------------------------------------


class MarkupKind:
    PLAIN_TEXT = "plaintext"
    MARKDOWN = "markdown"


@dataclass
class MarkupContent:
    kind: str
    value: str

    @classmethod
    def from_lsp(cls, d: dict[str, Any] | None) -> "MarkupContent | None":
        if d is None:
            return None
        return cls(kind=str(d.get("kind", MarkupKind.PLAIN_TEXT)),
                   value=str(d.get("value", "")))


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@dataclass
class VersionedTextDocumentIdentifier:
    uri: str
    version: int

    def to_lsp(self) -> dict[str, Any]:
        return {"uri": self.uri, "version": self.version}


def text_document_identifier(uri: str) -> dict[str, str]:
    return {"uri": uri}


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


class DiagnosticSeverity(IntEnum):
    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


@dataclass
class Diagnostic:
    range: Range
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING
    code: Any = None
    source: str | None = None

    @classmethod
    def from_lsp(cls, d: dict[str, Any]) -> "Diagnostic":
        return cls(
            range=Range.from_lsp(d.get("range")) or Range(Position(0, 0), Position(0, 0)),
            message=str(d.get("message", "")),
            severity=DiagnosticSeverity(int(d.get("severity", 2))),
            code=d.get("code"),
            source=d.get("source"),
        )


# ---------------------------------------------------------------------------
# Hover
# ---------------------------------------------------------------------------


@dataclass
class Hover:
    contents: MarkupContent | str
    range: Range | None = None

    @classmethod
    def from_lsp(cls, d: dict[str, Any] | None) -> "Hover | None":
        if d is None:
            return None
        contents = d.get("contents")
        if isinstance(contents, dict):
            mc = MarkupContent.from_lsp(contents) or MarkupContent(MarkupKind.PLAIN_TEXT, "")
        elif isinstance(contents, list):
            joined = "\n\n".join(
                m.get("value", "") if isinstance(m, dict) else str(m) for m in contents
            )
            mc = MarkupContent(MarkupKind.MARKDOWN, joined)
        else:
            mc = str(contents or "")
        return cls(contents=mc, range=Range.from_lsp(d.get("range")))


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------


@dataclass
class CompletionItem:
    label: str
    kind: int | None = None
    detail: str | None = None
    documentation: str | None = None
    insert_text: str | None = None
    sort_text: str | None = None
    filter_text: str | None = None

    @classmethod
    def from_lsp(cls, d: dict[str, Any]) -> "CompletionItem":
        return cls(
            label=str(d.get("label", "")),
            kind=d.get("kind"),
            detail=d.get("detail"),
            documentation=d.get("documentation"),
            insert_text=d.get("insertText"),
            sort_text=d.get("sortText"),
            filter_text=d.get("filterText"),
        )


# ---------------------------------------------------------------------------
# Signature help
# ---------------------------------------------------------------------------


@dataclass
class SignatureInformation:
    label: str
    parameters: list["ParameterInformation"] = field(default_factory=list)
    documentation: str | None = None
    active_parameter: int | None = None

    @classmethod
    def from_lsp(cls, d: dict[str, Any]) -> "SignatureInformation":
        params = [
            ParameterInformation.from_lsp(p) for p in (d.get("parameters") or [])
        ]
        return cls(
            label=str(d.get("label", "")),
            parameters=params,
            documentation=d.get("documentation"),
        )


@dataclass
class ParameterInformation:
    label: str
    documentation: str | None = None

    @classmethod
    def from_lsp(cls, d: dict[str, Any]) -> "ParameterInformation":
        lbl = d.get("label", "")
        return cls(label=lbl if isinstance(lbl, str) else str(lbl),
                   documentation=d.get("documentation"))


@dataclass
class SignatureHelp:
    signatures: list[SignatureInformation]
    active_signature: int | None = None
    active_parameter: int | None = None

    @classmethod
    def from_lsp(cls, d: dict[str, Any] | None) -> "SignatureHelp | None":
        if d is None:
            return None
        sigs = [SignatureInformation.from_lsp(s) for s in (d.get("signatures") or [])]
        return cls(
            signatures=sigs,
            active_signature=d.get("activeSignature"),
            active_parameter=d.get("activeParameter"),
        )


# ---------------------------------------------------------------------------
# Symbols
# ---------------------------------------------------------------------------


class SymbolKind(IntEnum):
    FILE = 1
    MODULE = 2
    NAMESPACE = 3
    PACKAGE = 4
    CLASS = 5
    METHOD = 6
    PROPERTY = 7
    FIELD = 8
    CONSTRUCTOR = 9
    ENUM = 10
    INTERFACE = 11
    FUNCTION = 12
    VARIABLE = 13
    CONSTANT = 14
    STRING = 15
    NUMBER = 16
    BOOL = 17
    ARRAY = 18
    OBJECT = 19
    KEY = 20
    NULL = 21
    ENUM_MEMBER = 22
    STRUCT = 23
    EVENT = 24
    OPERATOR = 25
    TYPE_PARAMETER = 26


@dataclass
class SymbolInformation:
    name: str
    kind: SymbolKind
    location: Location
    container_name: str | None = None

    @classmethod
    def from_lsp(cls, d: dict[str, Any]) -> "SymbolInformation":
        return cls(
            name=str(d.get("name", "")),
            kind=SymbolKind(int(d.get("kind", 13))),
            location=Location.from_lsp(d.get("location"))
            or Location(uri="", range=Range(Position(0, 0), Position(0, 0))),
            container_name=d.get("containerName"),
        )


# DocumentSymbol is what documentSymbol returns; DocumentSymbol is recursive
# (children), SymbolInformation is flat (used by workspace/symbol). We expose
# both, with a thin uniform shape for callers.
@dataclass
class DocumentSymbol:
    name: str
    kind: SymbolKind
    range: Range
    selection_range: Range
    detail: str | None = None
    children: list["DocumentSymbol"] = field(default_factory=list)

    @classmethod
    def from_lsp(cls, d: dict[str, Any]) -> "DocumentSymbol":
        children = [cls.from_lsp(c) for c in (d.get("children") or [])]
        return cls(
            name=str(d.get("name", "")),
            kind=SymbolKind(int(d.get("kind", 13))),
            range=Range.from_lsp(d.get("range")) or Range(Position(0, 0), Position(0, 0)),
            selection_range=Range.from_lsp(d.get("selectionRange"))
            or Range(Position(0, 0), Position(0, 0)),
            detail=d.get("detail"),
            children=children,
        )


# ---------------------------------------------------------------------------
# Workspace edits
# ---------------------------------------------------------------------------


@dataclass
class WorkspaceEdit:
    """Minimal workspace edit: per-URI list of TextEdits.

    `documentChanges` (with optional create/rename/delete) is rarely used by
    rename refactors; we accept the dict form when applying and let the
    client deal with conversion.
    """
    changes: dict[str, list[TextEdit]] = field(default_factory=dict)

    @classmethod
    def from_lsp(cls, d: dict[str, Any] | None) -> "WorkspaceEdit | None":
        if d is None:
            return None
        out: dict[str, list[TextEdit]] = {}
        for uri, edits in (d.get("changes") or {}).items():
            out[uri] = [TextEdit.from_lsp(e) for e in edits if e is not None]
        return cls(changes=out)


# ---------------------------------------------------------------------------
# Code actions
# ---------------------------------------------------------------------------


@dataclass
class CodeAction:
    title: str
    kind: str | None = None
    edit: WorkspaceEdit | None = None
    command: dict[str, Any] | None = None

    @classmethod
    def from_lsp(cls, d: dict[str, Any]) -> "CodeAction":
        return cls(
            title=str(d.get("title", "")),
            kind=d.get("kind"),
            edit=WorkspaceEdit.from_lsp(d.get("edit")),
            command=d.get("command"),
        )
