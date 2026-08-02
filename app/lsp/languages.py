"""Language registry — maps file extensions to Language definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Language:
    """A programming language with its file extensions and LSP server info."""
    name: str
    extensions: list[str] = field(default_factory=list)
    lsp_language_id: str = ""
    server_name: str = ""

    def matches(self, suffix: str) -> bool:
        return suffix.lower() in self.extensions


class LanguageRegistry:
    """Registry of known programming languages."""

    def __init__(self) -> None:
        self._languages: list[Language] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._languages.extend([
            Language("Python", [".py", ".pyw"], "python", "pylsp"),
            Language("JavaScript", [".js", ".mjs", ".jsx"], "javascript", "vscode-eslint"),
            Language("TypeScript", [".ts", ".tsx"], "typescript", "vscode-eslint"),
            Language("HTML", [".html", ".htm"], "html", "vscode-html"),
            Language("CSS", [".css", ".scss", ".less"], "css", "vscode-css"),
            Language("JSON", [".json", ".jsonc"], "json", "vscode-json"),
            Language("Markdown", [".md", ".markdown"], "markdown", "vscode-markdown"),
            Language("C", [".c", ".h"], "c", "clangd"),
            Language("C++", [".cpp", ".hpp", ".cc", ".cxx"], "cpp", "clangd"),
            Language("Java", [".java"], "java", "jdtls"),
            Language("Ruby", [".rb"], "ruby", "solargraph"),
            Language("Shell", [".sh", ".bash", ".zsh"], "shellscript", "bash-language-server"),
            Language("YAML", [".yaml", ".yml"], "yaml", "yaml-language-server"),
            Language("XML", [".xml"], "xml", "lemminx"),
            Language("SQL", [".sql"], "sql", "sql-language-server"),
            Language("Rust", [".rs"], "rust", "rust-analyzer"),
            Language("Go", [".go"], "go", "gopls"),
        ])

    def register(self, language: Language) -> None:
        self._languages.append(language)

    def find(self, suffix: str) -> Optional[Language]:
        for lang in self._languages:
            if lang.matches(suffix):
                return lang
        return None

    def all(self) -> list[Language]:
        return list(self._languages)


language_registry = LanguageRegistry()
