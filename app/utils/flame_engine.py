"""Flame AI Conversion Engine — converts unstructured .flame files into valid source code using AI."""
from __future__ import annotations

import os
import re
import json
import difflib
from dataclasses import dataclass
from pathlib import Path
import requests
from typing import Any, Optional, Tuple

from app.utils.file_utils import safe_write

EXT_MAP = {
    "python": ".py", "py": ".py",
    "javascript": ".js", "js": ".js",
    "typescript": ".ts", "ts": ".ts",
    "react": ".jsx", "vue": ".vue", "svelte": ".svelte",
    "c": ".c", "cpp": ".cpp", "c++": ".cpp",
    "rust": ".rs", "rs": ".rs",
    "go": ".go", "golang": ".go",
    "html": ".html", "css": ".css",
    "java": ".java", "kotlin": ".kt", "swift": ".swift",
    "ruby": ".rb", "rb": ".rb",
    "php": ".php", "lua": ".lua", "bash": ".sh", "sh": ".sh",
    "powershell": ".ps1", "sql": ".sql", "r": ".r",
    "zig": ".zig", "haskell": ".hs", "hs": ".hs",
    "elixir": ".ex", "ex": ".ex", "ocaml": ".ml", "ml": ".ml",
    "assembly": ".asm", "asm": ".asm", "c#": ".cs", "csharp": ".cs"
}

STATE_SUFFIX = ".flame.json"


@dataclass
class FlameConversion:
    """A conversion ready to show in the preview dialog."""

    code: str
    target_path: Path
    target_lang: str
    source_content: str
    mode: str  # "created", "incremental", or "unchanged"


def get_state_path(flame_path: Path, target_path: Path | None = None) -> Path:
    """Return the sidecar used to remember the previous Flame conversion."""
    target = target_path or get_target_path(flame_path, detect_target_lang(
        flame_path.read_text(encoding="utf-8")
    ))
    return target.with_name(target.name + STATE_SUFFIX)


def _load_state(path: Path, target_path: Path) -> dict[str, Any] | None:
    state_path = get_state_path(path, target_path)
    try:
        value = json.loads(state_path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def save_conversion_state(
    flame_path: Path,
    target_path: Path,
    source_content: str,
    generated_code: str,
    target_lang: str,
) -> None:
    """Persist source/output pairing so later edits can be applied incrementally."""
    state_path = get_state_path(flame_path, target_path)
    safe_write(
        state_path,
        json.dumps(
            {
                "version": 1,
                "flame_path": str(flame_path),
                "target_path": str(target_path),
                "target_lang": target_lang,
                "source_content": source_content,
                "generated_code": generated_code,
            },
            indent=2,
        )
        + "\n",
    )

def detect_target_lang(content: str) -> str:
    """Extracts target language from @target directive without truncating symbols like c++ or c#."""
    match = re.search(r"@target\s+(\S+)", content, re.IGNORECASE)
    if match:
        return match.group(1).lower().strip()
    return "python"

def get_target_path(path: Path, target_lang: str) -> Path:
    """Computes target file path based on target language extension."""
    ext = EXT_MAP.get(target_lang, f".{target_lang}")
    return path.with_suffix(ext)

def convert_flame_file(path: Path, content: str | None = None) -> Tuple[str, Path]:
    """
    Reads the complete .flame file, detects target language from @target,
    sends it to the AI model, validates/cleans the code, and saves it.

    Returns a tuple of (generated_code, target_file_path).
    """
    preview = prepare_flame_conversion(path, content)
    # Direct engine callers may provide editor content that has not been
    # written yet.  Keep the .flame source and generated file in sync.
    safe_write(path, preview.source_content)
    safe_write(preview.target_path, preview.code)
    save_conversion_state(
        path,
        preview.target_path,
        preview.source_content,
        preview.code,
        preview.target_lang,
    )
    return preview.code, preview.target_path


def prepare_flame_conversion(path: Path, content: str | None = None) -> FlameConversion:
    """Prepare a conversion without writing files.

    On the first conversion this calls the normal generator.  Once a state
    sidecar exists, only the changed Flame source is sent to the incremental
    updater.  The previous generated file is preserved as context, including
    edits made directly in that file.
    """
    source = content if content is not None else path.read_text(encoding="utf-8")
    target_lang = detect_target_lang(source)
    target_path = get_target_path(path, target_lang)
    state = _load_state(path, target_path)

    if state and state.get("source_content") == source:
        try:
            existing = target_path.read_text(encoding="utf-8")
        except OSError:
            existing = str(state.get("generated_code", ""))
        if existing:
            return FlameConversion(
                validate_and_clean_code(existing, target_lang),
                target_path,
                target_lang,
                source,
                "unchanged",
            )

    if state and state.get("source_content") is not None:
        previous_source = str(state.get("source_content", ""))
        previous_code = str(state.get("generated_code", ""))
        try:
            previous_code = target_path.read_text(encoding="utf-8")
        except OSError:
            pass
        code = call_ai_for_incremental_update(
            previous_source,
            source,
            previous_code,
            target_lang,
        )
        return FlameConversion(
            validate_and_clean_code(code, target_lang),
            target_path,
            target_lang,
            source,
            "incremental",
        )

    generated = call_ai_for_conversion(source, target_lang)
    return FlameConversion(
        validate_and_clean_code(generated, target_lang),
        target_path,
        target_lang,
        source,
        "created",
    )


def _source_diff(previous: str, current: str) -> str:
    return "".join(
        difflib.unified_diff(
            previous.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile="previous.flame",
            tofile="current.flame",
        )
    )


def _apply_line_edits(code: str, edits: list[dict[str, Any]]) -> str | None:
    """Apply one-based inclusive generated-code edits from the AI response."""
    lines = code.splitlines(keepends=True)
    try:
        normalized = []
        for edit in edits:
            start = int(edit["start_line"])
            end = int(edit.get("end_line", start))
            replacement = str(edit.get("replacement", ""))
            if start < 1 or end < start or end > len(lines) + 1:
                return None
            normalized.append((start, end, replacement))
        for start, end, replacement in sorted(normalized, reverse=True):
            if replacement and not replacement.endswith("\n"):
                replacement += "\n"
            lines[start - 1:end] = replacement.splitlines(keepends=True)
        return "".join(lines)
    except (KeyError, TypeError, ValueError):
        return None


def _offline_incremental_update(
    previous_source: str,
    current_source: str,
    previous_code: str,
    target_lang: str,
) -> str:
    """Keep the offline fallback stable while replacing changed source notes."""
    # Use a line-level patch even in offline mode. This keeps unrelated
    # generated code and direct edits intact while the fallback updates only
    # lines affected by the changed Flame source.
    candidate = generate_offline_fallback(current_source, target_lang)
    old_lines = previous_code.splitlines(keepends=True)
    reference_lines = generate_offline_fallback(previous_source, target_lang).splitlines(keepends=True)
    new_lines = candidate.splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(a=reference_lines, b=new_lines)
    for tag, start, end, new_start, new_end in reversed(matcher.get_opcodes()):
        if tag != "equal":
            old_lines[start:end] = new_lines[new_start:new_end]
    return "".join(old_lines)


def call_ai_for_incremental_update(
    previous_source: str,
    current_source: str,
    previous_code: str,
    target_lang: str,
) -> str:
    """Update only the generated ranges affected by a Flame source edit.

    The model returns line edits against the existing generated file instead
    of regenerating the whole file.  If the model or network is unavailable,
    the deterministic offline representation is used.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _offline_incremental_update(
            previous_source, current_source, previous_code, target_lang
        )

    changed = _source_diff(previous_source, current_source)
    numbered_code = "\n".join(
        f"{index:04d}: {line}" for index, line in enumerate(previous_code.splitlines(), 1)
    )
    prompt = (
        "Update an existing generated source file from a changed .flame file.\n"
        "Do not regenerate the file. Return only the minimal changed line edits "
        "as JSON: {\"edits\":[{\"start_line\":1,\"end_line\":1,"
        "\"replacement\":\"new line\"}]}. Replacement may contain \\n.\n"
        "Preserve all unrelated generated code exactly, including user edits. "
        "If a new block is needed, insert it with start_line=end_line equal to "
        "the insertion line. If a block is removed, use an empty replacement.\n\n"
        f"Target language: {target_lang}\n"
        f"Changed Flame source:\n{changed}\n\n"
        f"Existing generated file with line numbers:\n{numbered_code}\n"
    )
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.environ.get("FLAME_AI_MODEL", "gpt-4o-mini"),
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise source-to-source patch editor. Return JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=30.0,
        )
        if response.status_code == 200:
            payload = response.json()
            raw = payload["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            patched = _apply_line_edits(previous_code, parsed.get("edits", []))
            if patched is not None:
                return patched
    except Exception:
        pass
    return _offline_incremental_update(
        previous_source, current_source, previous_code, target_lang
    )


def commit_flame_conversion(
    flame_path: Path,
    target_path: Path,
    source_content: str,
    generated_code: str,
    target_lang: str,
) -> None:
    """Write both source and generated files and update their pairing state."""
    safe_write(flame_path, source_content)
    safe_write(target_path, validate_and_clean_code(generated_code, target_lang))
    save_conversion_state(
        flame_path,
        target_path,
        source_content,
        validate_and_clean_code(generated_code, target_lang),
        target_lang,
    )


def call_ai_for_conversion(flame_content: str, target_lang: str) -> str:
    """Interactions with LLM API (OpenAI) with structured prompts and robust offline/error fallbacks."""
    api_key = os.environ.get("OPENAI_API_KEY")

    prompt = (
        f"You are an expert AI code generator. Convert the following .flame file content "
        f"into clean, fully functional, and valid source code in '{target_lang}'.\n\n"
        f"Instructions:\n"
        f"- Understand the developer's intent, pseudo code, natural language, or instructions.\n"
        f"- Generate only the raw, production-grade source code for '{target_lang}'.\n"
        f"- Do not include markdown formatting backticks (like ```python) around the code.\n"
        f"- Do not include any conversational text, explanations, or warnings.\n\n"
        f"Content of .flame file:\n"
        f"---------------------\n"
        f"{flame_content}\n"
        f"---------------------\n"
    )

    if api_key:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            model = os.environ.get("FLAME_AI_MODEL", "gpt-4o-mini")
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a code-only assistant. Never explain anything. Output code only."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30.0
            )
            if response.status_code == 200:
                res_json = response.json()
                return res_json["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    # Dynamic/Smart Offline/Mock Fallback Engine
    return generate_offline_fallback(flame_content, target_lang)


def generate_offline_fallback(content: str, target_lang: str) -> str:
    """Intelligently processes free-form .flame input offline to build mock code structure."""
    lines = content.splitlines()
    clean_lines = [ln for ln in lines if not ln.strip().startswith("@target")]

    if target_lang in ("python", "py"):
        fallback = f'# Generated from .flame file (Offline Fallback)\n'
        fallback += f'# Target: {target_lang}\n\n'
        fallback += 'def main():\n'
        for ln in clean_lines:
            if ln.strip():
                fallback += f'    # {ln.strip()}\n'
        fallback += '    print("Flame execution complete (mock output).")\n\n'
        fallback += 'if __name__ == "__main__":\n'
        fallback += '    main()\n'
        return fallback
    elif target_lang in ("javascript", "js", "typescript", "ts"):
        fallback = f'// Generated from .flame file (Offline Fallback)\n'
        fallback += f'// Target: {target_lang}\n\n'
        fallback += 'function main() {\n'
        for ln in clean_lines:
            if ln.strip():
                fallback += f'    // {ln.strip()}\n'
        fallback += '    console.log("Flame execution complete (mock output).");\n'
        fallback += '}\n\n'
        fallback += 'main();\n'
        return fallback
    else:
        fallback = f'/* Generated from .flame file (Offline Fallback) for {target_lang} */\n\n'
        for ln in clean_lines:
            if ln.strip():
                fallback += f'// {ln.strip()}\n'
        return fallback


def validate_and_clean_code(code: str, target_lang: str) -> str:
    """Strips Markdown backticks and standardizes file endings."""
    # Strip leading ```lang or ```
    code = re.sub(r"^```\w*\n", "", code, flags=re.MULTILINE)
    # Strip trailing ```
    code = re.sub(r"\n```$", "", code, flags=re.MULTILINE)
    return code.strip() + "\n"
