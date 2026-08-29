#!/usr/bin/env python3
"""Fix G004 violations: convert f-string logging to lazy % formatting.

Handles both single-line and multi-line (implicit concatenation) f-strings.

Usage:
    python scripts/fix_g004.py                          # fix all src/
    python scripts/fix_g004.py --dry-run                # preview only
    python scripts/fix_g004.py src/antigravity_k/foo.py # single file
"""

import ast
import os
import sys

LOG_METHODS = frozenset(
    {
        "error",
        "info",
        "warning",
        "debug",
        "critical",
        "exception",
        "log",
    }
)


def convert_fstring(fs: ast.JoinedStr) -> tuple[str, list[str]]:
    """Convert a JoinedStr to (format_string_with_%s, expression_strings)."""
    parts: list[str] = []
    exprs: list[str] = []
    for v in fs.values:
        if isinstance(v, ast.Constant):
            parts.append(v.value if isinstance(v.value, str) else str(v.value))
        elif isinstance(v, ast.FormattedValue):
            conv = {114: "%r", 115: "%s", 97: "%a"}.get(v.conversion, "%s") if v.conversion != -1 else "%s"
            parts.append(conv)
            exprs.append(ast.unparse(v.value))
    return "".join(parts), exprs


def _escape_for_string(fmt: str) -> str:
    """Escape a format string for use in a double-quoted Python string."""
    return fmt.replace("\\", "\\\\").replace('"', '\\"')


def fix_file(filepath: str, dry_run: bool = False) -> int:
    """Fix G004 violations in a single file. Returns number of fixes."""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source, filepath)
    except SyntaxError:
        return 0

    fixes: list[tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in LOG_METHODS
            and node.args
            and isinstance(node.args[0], ast.JoinedStr)
        ):
            continue

        fstring: ast.JoinedStr = node.args[0]

        # Only fix if there's at least one expression
        has_expr = any(isinstance(v, ast.FormattedValue) for v in fstring.values)
        if not has_expr:
            continue

        fmt_string, exprs = convert_fstring(fstring)

        # Get the source segment of the f-string node
        seg = ast.get_source_segment(source, fstring)
        if not seg:
            continue

        # Build the replacement string
        escaped_fmt = _escape_for_string(fmt_string)
        replacement = f'"{escaped_fmt}", {", ".join(exprs)}' if exprs else f'"{escaped_fmt}"'

        # Find the segment in the source (using whole-source search)
        # To avoid wrong matches, search only from the line position
        # Build a position-aware search
        lines = source.splitlines(keepends=True)
        line_start_offset = sum(len(lines[i]) for i in range(fstring.lineno - 1))

        # Search for the segment starting from the approximate position
        search_start = line_start_offset + fstring.col_offset
        pos = source.find(seg, max(0, search_start - 10))

        if pos < 0:
            # Try wider search from the start of the line
            pos = source.find(seg, line_start_offset)
            if pos < 0:
                continue

        byte_end = pos + len(seg)
        fixes.append((pos, byte_end, replacement))

    if not fixes:
        return 0

    # Apply fixes from last to first (by byte position) to preserve offsets
    fixes.sort(key=lambda x: x[0], reverse=True)

    new_source = source
    for byte_start, byte_end, replacement in fixes:
        new_source = new_source[:byte_start] + replacement + new_source[byte_end:]

    if new_source == source:
        return 0

    if dry_run:
        return len(fixes)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_source)

    return len(fixes)


def collect_py_files(paths: list[str]) -> list[str]:
    """Collect all .py files from given paths."""
    files: list[str] = []
    for p in paths:
        if os.path.isfile(p) and p.endswith(".py"):
            files.append(p)
        elif os.path.isdir(p):
            for root, dirs, filenames in os.walk(p):
                dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules", ".venv", "venv")]
                for fn in filenames:
                    if fn.endswith(".py"):
                        files.append(os.path.join(root, fn))
    return sorted(files)


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    paths = [p for p in args if not p.startswith("--")]
    if not paths:
        paths.append("src/")

    py_files = collect_py_files(paths)
    total_fixes = 0
    fixed_files = 0

    for fp in py_files:
        fixes = fix_file(fp, dry_run=dry_run)
        if fixes > 0:
            total_fixes += fixes
            fixed_files += 1
            if dry_run:
                print(f"[DRY-RUN] {fp}: {fixes} fix(es)")

    if dry_run:
        print(f"\n[Dry-run complete] {total_fixes} fix(es) in {fixed_files}/{len(py_files)} files")
    else:
        print(f"[Complete] {total_fixes} fix(es) applied to {fixed_files}/{len(py_files)} files")


if __name__ == "__main__":
    main()
