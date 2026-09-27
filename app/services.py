"""Small, dependency-free services used by Ember IDE's feature panels.

The UI deliberately talks to these services instead of embedding shell or
filesystem logic in widgets.  All subprocess calls use argument lists and
return captured output so failures can be shown to the user.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_command(argv: list[str], cwd: Path | None = None, timeout: float = 30) -> CommandResult:
    """Run a command without invoking a shell."""
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)
    except FileNotFoundError as exc:
        return CommandResult(127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        return CommandResult(124, out, f"Command timed out: {' '.join(argv)}\n{err}")
    except OSError as exc:
        return CommandResult(1, "", str(exc))


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------


@dataclass
class GitEntry:
    code: str
    path: str

    @property
    def staged(self) -> bool:
        return self.code[0] not in (" ", "?")

    @property
    def unstaged(self) -> bool:
        return len(self.code) > 1 and self.code[1] not in (" ", "?")


class GitService:
    """A small wrapper around the user's installed Git executable."""

    def __init__(self, root: Path | None) -> None:
        self.root = self.find_root(root) if root else None

    @staticmethod
    def find_root(path: Path | None) -> Path | None:
        if path is None:
            return None
        candidate = path if path.is_dir() else path.parent
        result = run_command(["git", "rev-parse", "--show-toplevel"], candidate)
        if not result.ok:
            return None
        try:
            return Path(result.stdout.strip()).resolve()
        except OSError:
            return None

    @property
    def available(self) -> bool:
        return self.root is not None and shutil.which("git") is not None

    def _git(self, *args: str, timeout: float = 30) -> CommandResult:
        if not self.root:
            return CommandResult(128, "", "No Git repository is open.")
        return run_command(["git", *args], self.root, timeout=timeout)

    def branch(self) -> str:
        result = self._git("branch", "--show-current")
        return result.stdout.strip() or "(detached HEAD)" if result.ok else "Not a Git repository"

    def status(self) -> list[GitEntry]:
        result = self._git("status", "--porcelain=v1")
        if not result.ok:
            return []
        entries: list[GitEntry] = []
        for line in result.stdout.splitlines():
            if len(line) >= 4:
                entries.append(GitEntry(line[:2], line[3:]))
        return entries

    def stage(self, paths: Iterable[str]) -> CommandResult:
        return self._git("add", "--", *list(paths))

    def stage_all(self) -> CommandResult:
        return self._git("add", "-A")

    def unstage(self, paths: Iterable[str]) -> CommandResult:
        return self._git("restore", "--staged", "--", *list(paths))

    def discard(self, paths: Iterable[str]) -> CommandResult:
        return self._git("restore", "--worktree", "--", *list(paths))

    def commit(self, message: str) -> CommandResult:
        return self._git("commit", "-m", message)

    def log(self, limit: int = 20) -> list[str]:
        result = self._git("log", f"-{limit}", "--oneline", "--decorate")
        return result.stdout.splitlines() if result.ok else []


# ---------------------------------------------------------------------------
# Workspace search and lightweight language tools
# ---------------------------------------------------------------------------


IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build",
}


@dataclass
class SearchMatch:
    path: Path
    line: int
    column: int
    text: str


class WorkspaceSearch:
    def __init__(self, root: Path | None) -> None:
        self.root = root

    def iter_files(self) -> Iterable[Path]:
        if not self.root or not self.root.is_dir():
            return
        for path in self.root.rglob("*"):
            if not path.is_file() or any(part in IGNORED_DIRS for part in path.parts):
                continue
            if path.stat().st_size > 2_000_000:
                continue
            yield path

    def search(self, query: str, regex: bool = False, case_sensitive: bool = False) -> list[SearchMatch]:
        if not query:
            return []
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query if regex else re.escape(query), flags)
        except re.error:
            return []
        matches: list[SearchMatch] = []
        for path in self.iter_files() or ():
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, 1):
                match = pattern.search(line)
                if match:
                    matches.append(SearchMatch(path, line_no, match.start() + 1, line))
        return matches


class LanguageTools:
    """Useful local tooling that works even when an LSP server is unavailable."""

    KEYWORDS = {
        "and", "as", "assert", "async", "await", "break", "case", "class",
        "continue", "def", "del", "elif", "else", "except", "finally", "for",
        "from", "global", "if", "import", "in", "is", "lambda", "match",
        " nonlocal", "not", "or", "pass", "raise", "return", "try", "while",
        "with", "yield", "True", "False", "None",
    }

    @staticmethod
    def completion_words(text: str, prefix: str = "") -> list[str]:
        words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text))
        words.update(LanguageTools.KEYWORDS)
        if prefix:
            words = {word for word in words if word.startswith(prefix)}
        return sorted(words, key=lambda word: (not word.startswith(prefix), word.lower()))

    @staticmethod
    def python_diagnostics(path: Path, text: str) -> list[tuple[int, str]]:
        if path.suffix.lower() not in (".py", ".pyw"):
            return []
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            return [(max(1, exc.lineno or 1), exc.msg)]
        return []

    @staticmethod
    def definition(text: str, word: str) -> int | None:
        if not word:
            return None
        pattern = re.compile(
            rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(word)}\b|"
            rf"^\s*{re.escape(word)}\s*=",
            re.MULTILINE,
        )
        match = pattern.search(text)
        return text.count("\n", 0, match.start()) + 1 if match else None


# ---------------------------------------------------------------------------
# Tasks, tests, packages, extensions
# ---------------------------------------------------------------------------


class TaskService:
    def __init__(self, root: Path | None) -> None:
        self.root = root

    def discover(self) -> dict[str, str]:
        if not self.root:
            return {}
        tasks: dict[str, str] = {}
        config = self.root / ".ember" / "tasks.json"
        if config.is_file():
            try:
                raw = json.loads(config.read_text(encoding="utf-8"))
                for name, value in (raw.get("tasks") or raw).items():
                    if isinstance(value, str):
                        tasks[str(name)] = value
                    elif isinstance(value, dict) and isinstance(value.get("command"), str):
                        tasks[str(name)] = value["command"]
            except (OSError, ValueError):
                pass
        package = self.root / "package.json"
        if package.is_file():
            try:
                scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
                for name, command in scripts.items():
                    if isinstance(command, str):
                        tasks.setdefault(f"npm: {name}", f"npm run {name}")
            except (OSError, ValueError):
                pass
        if (self.root / "Makefile").is_file():
            result = run_command(["make", "-qp"], self.root)
            if result.ok:
                for line in result.stdout.splitlines():
                    if line and not line.startswith(("\t", "#", ".")) and ":" in line:
                        name = line.split(":", 1)[0].strip()
                        if name and "%" not in name:
                            tasks.setdefault(f"make: {name}", f"make {name}")
        return tasks


class TestService:
    @staticmethod
    def command(root: Path | None, current: Path | None = None) -> list[str] | None:
        if current and current.suffix == ".py":
            return [sys.executable, "-m", "pytest", "-q", str(current)]
        if root:
            if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists() or (root / "tests").is_dir():
                return [sys.executable, "-m", "pytest", "-q"]
            if (root / "package.json").is_file():
                return ["npm", "test"]
        return None


class PackageService:
    @staticmethod
    def ecosystem(root: Path | None) -> str:
        if root and (root / "package.json").is_file():
            return "npm"
        return "python"

    @staticmethod
    def command(ecosystem: str, action: str, package: str = "") -> list[str]:
        package = package.strip()
        if ecosystem == "npm":
            if action == "install":
                return ["npm", "install", package] if package else ["npm", "install"]
            if action == "remove":
                return ["npm", "uninstall", package]
            return ["npm", "list", "--depth=0"]
        if action == "install":
            return [sys.executable, "-m", "pip", "install", package]
        if action == "remove":
            return [sys.executable, "-m", "pip", "uninstall", "-y", package]
        return [sys.executable, "-m", "pip", "list"]


class ExtensionManager:
    """Load optional Python extensions from .ember/extensions."""

    def __init__(self, root: Path | None, command_callback: Callable[[str, Callable], None] | None = None) -> None:
        self.root = root
        self.extensions: list[str] = []
        self.commands: dict[str, Callable] = {}
        self._callback = command_callback

    def load(self) -> list[str]:
        self.extensions.clear()
        self.commands.clear()
        directory = self.root / ".ember" / "extensions" if self.root else None
        if not directory or not directory.is_dir():
            return []
        for path in sorted(directory.glob("*.py")):
            namespace: dict = {"__file__": str(path), "__name__": f"ember_extension_{path.stem}"}
            try:
                exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
                api = namespace.get("activate") or namespace.get("register")
                if callable(api):
                    registered = api()
                    if isinstance(registered, dict):
                        self.commands.update({str(k): v for k, v in registered.items() if callable(v)})
                self.extensions.append(path.stem)
            except Exception:
                # A broken optional extension must not prevent the IDE opening.
                continue
        return list(self.extensions)