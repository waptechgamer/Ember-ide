"""Cross-platform file/path helpers.

Kept tiny and dependency-free so it can be reused by every later phase.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def normalize(path: str | os.PathLike) -> Path:
    """Resolve a path to an absolute, expanded Path. Cross-platform safe."""
    return Path(path).expanduser().resolve()


def safe_write(target: Path, content: str, encoding: str = "utf-8") -> None:
    """Write ``content`` to ``target`` atomically.

    Writes to a temp file in the same directory, fsyncs, then replaces the
    destination. This avoids partial writes if the process is killed mid-save
    and is the standard pattern across OSes.
    """
    target = normalize(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, target)
    except Exception:
        # Clean up the orphan temp file on failure
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def safe_new_file(target: Path) -> None:
    """Create an empty file (and any missing parents). Raises if it exists."""
    target = normalize(target)
    if target.exists():
        raise FileExistsError(f"Already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()


def safe_new_dir(target: Path) -> None:
    """Create a directory (and any missing parents). Raises if it exists."""
    target = normalize(target)
    if target.exists():
        raise FileExistsError(f"Already exists: {target}")
    target.mkdir(parents=True)


def is_hidden(path: Path) -> bool:
    """Cross-platform hidden-file detection (dotfiles + Windows attribute)."""
    if path.name.startswith("."):
        return True
    if os.name == "nt":
        try:
            import ctypes  # noqa: import-outside-toplevel
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))  # type: ignore[attr-defined]
            return bool(attrs & 2)  # FILE_ATTRIBUTE_HIDDEN
        except Exception:
            return False
    return False
