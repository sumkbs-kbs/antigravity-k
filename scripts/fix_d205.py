#!/usr/bin/env python3
"""
D205 auto-fixer: Insert blank line between docstring summary and body.

ruff D205 rule: 1 blank line required between summary line and description.
Applies only to multi-line docstrings (\"\"\"...\"\"\" with >= 2 content lines).
"""

import argparse
import sys
from pathlib import Path
from typing import cast


def find_docstring_pairs(lines: list[str]) -> list[tuple[int, int]]:
    """Find all triple-quoted string pairs (possibly docstrings).

    Returns list of (open_idx, close_idx) tuples.
    Only considers pairs where open and close are on different lines (multi-line).
    Skips single-line docstrings.
    """
    pairs: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for opening """
        pos = line.find('"""')
        if pos == -1:
            i += 1
            continue

        rest = line[pos + 3 :]

        # Single-line docstring: """...""" on same line
        if '"""' in rest:
            i += 1
            continue

        # Multi-line: find closing """
        j = i + 1
        while j < len(lines):
            if '"""' in lines[j]:
                pairs.append((i, j))
                i = j + 1
                break
            j += 1
        else:
            # No closing found - malformed, skip
            i += 1

    return pairs


def fix_docstring_d205(text: str) -> str:
    """Fix D205 violations in Python file content.

    Uses line-based approach that handles multiple docstrings per file
    and both '``' on its own line vs same line as summary.
    """
    lines = text.split("\n")
    pairs = find_docstring_pairs(lines)

    # Process pairs in reverse order so line numbers stay valid
    for open_idx, close_idx in reversed(pairs):
        open_line = lines[open_idx]
        pos = open_line.find('"""')
        text_after = open_line[pos + 3 :]  # Content after """ on the same line

        if text_after.strip():
            # """Summary.\nBody. pattern - content starts on same line as """
            content_start = open_idx
            content_lines = [text_after] + lines[open_idx + 1 : close_idx]
        else:
            # """\nSummary.\nBody. pattern - content starts on next line
            content_start = open_idx + 1
            content_lines = lines[content_start:close_idx]

        # Find first and second non-empty content lines
        first_non_empty = None
        second_non_empty = None
        for idx, cl in enumerate(content_lines):
            if cl.strip():
                if first_non_empty is None:
                    first_non_empty = idx
                elif second_non_empty is None:
                    second_non_empty = idx
                    break

        if first_non_empty is None or second_non_empty is None:
            continue  # Less than 2 content lines - no D205 issue

        # Check if there's already a blank line between them
        has_blank = any(not content_lines[k].strip() for k in range(first_non_empty + 1, second_non_empty))

        if has_blank:
            continue  # Already has blank line

        # Need to insert a blank line after the first content line
        # The blank line should match the indentation of the closing """
        close_line = lines[close_idx]
        indent = " " * (len(close_line) - len(close_line.lstrip()))

        insert_pos = content_start + first_non_empty + 1
        lines.insert(insert_pos, indent)

    return "\n".join(lines)


def fix_file(filepath: Path, dry_run: bool = False) -> bool:
    """Fix D205 violations in a file. Returns True if modified."""
    try:
        original = filepath.read_text(encoding="utf-8")
    except Exception as e:
        if dry_run:
            print(f"  [SKIP] {filepath}: {e}")
        return False

    fixed = fix_docstring_d205(original)

    if original == fixed:
        return False

    if dry_run:
        orig_lines = original.split("\n")
        fix_lines = fixed.split("\n")
        print(f"  [DRY-RUN] {filepath}")
        for idx in range(len(fix_lines)):
            o = orig_lines[idx] if idx < len(orig_lines) else None
            f = fix_lines[idx]
            if o != f:
                if o is None:
                    print(f"    Line {idx + 1} (+): {f}")
                else:
                    print(f'    Line {idx + 1}: "{o}" -> "{f}"')
        return True

    _ = filepath.write_text(fixed, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix D205 (missing blank line after docstring summary).")
    _ = parser.add_argument("--path", default="src/", help="Path to scan")
    _ = parser.add_argument("--dry-run", action="store_true", help="Preview only")
    _ = parser.add_argument("--verbose", "-v", action="store_true", help="Show details")
    args = parser.parse_args()

    path_arg = cast(str, args.path)
    dry_run = cast(bool, args.dry_run)
    verbose = cast(bool, args.verbose)
    target = Path(path_arg)
    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.rglob("*.py"))
    else:
        print(f"Error: {path_arg} not found")
        sys.exit(1)

    modified = 0
    skipped = 0

    for fp in files:
        if fix_file(fp, dry_run=dry_run):
            modified += 1
            if verbose and not dry_run:
                print(f"  [FIXED] {fp}")
        else:
            skipped += 1

    mode = "Dry-run" if dry_run else "Fixed"
    print(f"\n{mode}: {modified} files | Unchanged: {skipped} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
