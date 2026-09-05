#!/usr/bin/env python3
"""
Fix D401 (docstring first line should be in imperative mood) violations.

Changes descriptive/3rd person docstring starts to imperative mood.
"""

import subprocess
import sys
from pathlib import Path
from typing import TypedDict, cast

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RuffLocation(TypedDict):
    row: int


class RuffViolation(TypedDict):
    filename: str
    location: RuffLocation


def run_ruff() -> list[RuffViolation]:
    """Get D401 violations."""
    cmd = ["ruff", "check", "--select=D401", "--output-format=json", "src/"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=30)
    if result.returncode == 0:
        return []
    import json

    try:
        payload = cast(object, json.loads(result.stdout))
        if not isinstance(payload, list):
            return []
        return cast(list[RuffViolation], payload)
    except json.JSONDecodeError:
        print("Failed to parse ruff output", file=sys.stderr)
        return []


def fix_docstring(text: str) -> str:
    """Fix a single docstring to use imperative mood."""
    # Remove leading/trailing quotes for processing
    stripped = text.strip()

    # English fixes: 3rd person → imperative
    replacements = [
        ("Returns ", "Return "),
        ("Returns\n", "Return\n"),
        ("Returns\t", "Return\t"),
        ("Returns.", "Return."),
        ("Splits ", "Split "),
        ("Splits\n", "Split\n"),
        ("Splits.", "Split."),
        ("Connects ", "Connect "),
        ("Connects\n", "Connect\n"),
        ("Connects.", "Connect."),
        ("Finds ", "Find "),
        ("Finds\n", "Find\n"),
        ("Finds.", "Find."),
        ("Retrieves ", "Retrieve "),
        ("Retrieves\n", "Retrieve\n"),
        ("Checks ", "Check "),
        ("Checks\n", "Check\n"),
        ("Creates ", "Create "),
        ("Creates\n", "Create\n"),
        ("Removes ", "Remove "),
        ("Removes\n", "Remove\n"),
    ]

    for old, new in replacements:
        if stripped.startswith(old):
            stripped = new + stripped[len(old) :]
            break

    # Korean fixes: 합니다 → 하세요 (imperative), etc.
    # Actually for Korean, "합니다" is already imperative-adjacent
    # Let's change declarative endings to imperative
    korean_imp = [
        ("검증합니다.", "검증합니다."),
        ("분류합니다.", "분류합니다."),
        ("포맷합니다.", "포맷합니다."),
        ("보강합니다.", "보강합니다."),
        ("실행합니다.", "실행합니다."),
        ("실행됨.", "실행됨."),
        ("반환.", "반환합니다."),
        ("탐색.", "탐색합니다."),
        ("스냅샷.", "스냅샷을 생성합니다."),
        ("New.", "Create a new instance."),
        ("Main.", "Run the main program."),
        ("Action.", "Set the action."),
        ("Finding Info.", "Set finding info."),
        ("Turns Remaining.", "Return the number of turns remaining."),
    ]

    for old, new in korean_imp:
        if stripped == old or stripped.startswith(old):
            stripped = new + stripped[len(old) :]
            break

    return stripped


def main():
    violations = run_ruff()
    if not violations:
        print("No D401 violations found!")
        return 0

    # Group by file
    files: dict[str, list[int]] = {}
    for v in violations:
        fname = v["filename"]
        lineno = v["location"]["row"]
        files.setdefault(fname, []).append(lineno)

    fixed_count = 0
    for fname, lines in sorted(files.items()):
        fpath = PROJECT_ROOT / fname
        if not fpath.exists():
            continue

        with fpath.open("r", encoding="utf-8") as f:
            content = f.read()

        original = content
        code_lines = content.split("\n")

        for lineno in sorted(set(lines), reverse=True):
            if lineno < 1 or lineno > len(code_lines):
                continue

            line = code_lines[lineno - 1]
            # Find the docstring content (between """ delimiters)
            idx = line.find('"""')
            if idx == -1:
                continue

            # Find opening and closing
            rest = line[idx + 3 :]
            end_idx = rest.find('"""')

            if end_idx != -1:
                # Single-line docstring
                doc_content = rest[:end_idx]
                fixed = fix_docstring(doc_content)
                if fixed != doc_content:
                    code_lines[lineno - 1] = line[: idx + 3] + fixed + '"""' + rest[end_idx + 3 :]
            else:
                # Multi-line docstring - find first line content
                first_content = rest.strip()
                fixed = fix_docstring(first_content)
                if fixed != first_content:
                    code_lines[lineno - 1] = line[: idx + 3] + fixed

        new_content = "\n".join(code_lines)
        if new_content != original:
            _ = fpath.write_text(new_content, encoding="utf-8")
            fixed_count += 1
            print(f"Fixed: {fname} ({len(lines)} violations)")

    # Verify
    remaining = run_ruff()
    print(f"\nFixed {fixed_count} files. Remaining D401 violations: {len(remaining)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
