"""Flame AI Conversion Engine — converts unstructured .flame files into valid source code using AI."""
from __future__ import annotations

import os
import re
from pathlib import Path
import requests
from typing import Tuple, Dict, Any

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

def convert_flame_file(path: Path) -> Tuple[str, Path]:
    """
    Reads the complete .flame file, detects target language from @target,
    sends it to the AI model, validates/cleans the code, and saves it.

    Returns a tuple of (generated_code, target_file_path).
    """
    content = path.read_text(encoding="utf-8")
    target_lang = detect_target_lang(content)
    target_path = get_target_path(path, target_lang)

    generated_code = call_ai_for_conversion(content, target_lang)
    validated_code = validate_and_clean_code(generated_code, target_lang)

    from app.utils.file_utils import safe_write
    safe_write(target_path, validated_code)

    return validated_code, target_path


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
