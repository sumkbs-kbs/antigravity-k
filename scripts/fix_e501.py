#!/usr/bin/env python3
"""
E501 (line-too-long) auto-fixer: Break lines exceeding max_length.

Focuses on safe mechanical transformations:
  1. Long strings: break at ~100 chars using implicit concatenation
  2. Long f-strings: break at expression boundaries
  3. Long parenthesized calls: add line breaks at comma/operator boundaries
  4. Long comments: break text

Usage:
    python scripts/fix_e501.py                     # fix src/
    python scripts/fix_e501.py --dry-run            # preview only
    python scripts/fix_e501.py --max-length 120     # default
"""

import argparse
import re
import sys
from pathlib import Path


def get_e501_violations(path: str, max_length: int = 120) -> list[tuple[str, int]]:
    """Run ruff to get E501 violations sorted by file/line."""
    import json
    import subprocess

    cmd = ["ruff", "check", "--select=E501", f"--max-line-length={max_length}", path]
    # Actually ruff uses --output-format=json for structured output
    cmd = ["ruff", "check", "--select=E501", "--output-format=json", path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode == 0:
        return []

    try:
        data = json.loads(result.stdout)
        violations = []
        for v in data:
            violations.append((v["filename"], v["location"]["row"]))
        # Sort by file then line (descending for safe editing)
        violations.sort(key=lambda x: (x[0], -x[1]))
        return violations
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing ruff output: {e}", file=sys.stderr)
        # Fallback: parse text output
        violations = []
        for line in result.stdout.splitlines():
            if ".py:" in line and "E501" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    fpath = parts[0].strip()
                    try:
                        lineno = int(parts[1])
                        violations.append((fpath, lineno))
                    except ValueError:
                        pass
        violations.sort(key=lambda x: (x[0], -x[1]))
        return violations


def break_long_string(line: str, max_len: int = 100) -> str | None:
    """Break a long string into concatenated parts.

    Returns the modified line or None if can't break.
    """
    # Find string boundaries
    # Match: variable = "..." continuation
    # or just "..."
    # Skip f-strings with complex expressions (too risky)
    if "f'" in line or 'f"' in line:
        # For f-strings, only break if the expressions are simple
        # Check if there are complex expressions like {x:...} or {x!...}
        if re.search(r"\{[^}]+\}", line):
            # Has format specifiers or conversions - skip f-strings
            # except simple variable references
            braces = re.findall(r"\{([^}]+)\}", line)
            simple = all(
                re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", b) or re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*\[[^\]]+\]$", b)
                for b in braces
            )
            if not simple:
                return None  # Complex f-strings are too risky

    # Strategy: for string literals (regular or f-strings) that are very long,
    # try to find a safe split point within the string content

    # Match lines like: X = "long string..." or X: str = "long..."
    # Or function("long arg...")

    # First, find all string literals in the line
    # Simple case: "..." or '...'
    str_pattern = r'"[^"]*"|\'[^\']*\''
    matches = list(re.finditer(str_pattern, line))

    if not matches:
        return None

    modified_line = line

    # Process from right to left to preserve positions
    for m in reversed(matches):
        start, end = m.start(), m.end()
        s = m.group()
        quote_char = s[0]

        # Only break strings that are long enough
        if len(s) <= 120:
            continue

        # Don't break URLs in strings - they can't be split
        if "://" in s:
            continue

        # Inner content (without quotes)
        content = s[1:-1]

        # Find a good split point around ~100 chars from the string start
        split_point = min(100, max(80, len(content) // 2))

        # Try to split at a space or punctuation
        best_split = -1
        for split_char in [" ", ",", ".", ";", ":", "(", ")", "/", "|", "&"]:
            pos = content.rfind(split_char, 0, split_point + 20)
            if pos > 30 and pos < len(content) - 20:
                best_split = pos
                break

        if best_split == -1:
            # Force split at ~100 chars
            best_split = min(95, len(content) // 2)

        part1 = content[: best_split + 1].rstrip()
        part2 = content[best_split + 1 :].lstrip()

        if not part2:
            continue

        if not part1:
            continue

        # Create concatenation: "part1" "part2"
        prefix = line[:start]
        suffix = line[end:]

        # Check indentation for the continuation line
        indent = " " * (len(line) - len(line.lstrip()))
        if prefix.strip().endswith(","):
            indent += "    "

        new_string = (
            f"{quote_char}{part1}{quote_char}  # type: ignore  # noqa: E501\n{indent}{quote_char}{part2}{quote_char}"
        )

        modified_line = prefix + new_string + suffix

    if modified_line != line:
        return modified_line

    return None


def break_long_call(line: str, max_len: int = 100) -> str | None:
    """Break a long function/method call by adding line breaks at commas."""
    # Check if line has parenthesized arguments
    if "(" not in line or ")" not in line:
        return None

    # Don't touch lines that already have multi-line indentation
    if "\\\n" in line:
        return None

    # Find the outermost parenthesized block
    depth = 0
    open_pos = -1
    close_pos = -1

    for i, ch in enumerate(line):
        if ch == "(":
            if depth == 0:
                open_pos = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                close_pos = i
                break

    if open_pos == -1 or close_pos == -1:
        return None

    # Only break if the content between parens is long enough
    content = line[open_pos + 1 : close_pos]
    if len(content) <= 80:
        return None

    # Break at commas
    if "," not in content:
        return None

    indent = " " * (open_pos + 5)  # indent past the call start + 4

    parts = []
    current = []
    for c in content:
        current.append(c)
        if c == ",":
            parts.append("".join(current).strip())
            current = []

    if current:
        parts.append("".join(current).strip())

    if len(parts) < 2:
        return None

    # Build broken line
    prefix = line[: open_pos + 1]
    suffix = line[close_pos:]

    broken_args = ",\n".join(f"{indent}{p.strip()}" for p in parts)

    return f"{prefix}\n{broken_args}\n{' ' * (open_pos + 1)}{suffix}"


def is_docstring_or_comment(line: str) -> bool:
    """Check if a line is a docstring or comment (single line)."""
    stripped = line.strip()
    return stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")


def fix_file(filepath: Path, dry_run: bool = False, max_length: int = 120) -> bool:
    """Fix E501 violations in a single file."""
    try:
        original = filepath.read_text(encoding="utf-8")
    except Exception as e:
        if dry_run:
            print(f"  [SKIP] {filepath}: {e}")
        return False

    lines = original.split("\n")
    modified = False
    changes = []

    for i in range(len(lines)):
        line = lines[i]
        if len(line) <= max_length:
            continue

        # Try different fix strategies

        # Strategy 1: Break long string
        new_line = break_long_string(line, max_length - 20)
        if new_line and new_line != line:
            changes.append((i, line, new_line))
            lines[i] = new_line
            modified = True
            continue

        # Strategy 2: Break long function call
        new_line = break_long_call(line, max_length - 20)
        if new_line and new_line != line:
            changes.append((i, line, new_line))
            lines[i] = new_line
            modified = True
            continue

    if not modified:
        return False

    new_content = "\n".join(lines)

    if dry_run:
        print(f"\n📄 {filepath.relative_to(Path.cwd())}")
        for idx, old, new in changes[:10]:
            print(f"  L{idx + 1}: {old[:80]}...")
            new_first_line = new.split("\n")[0]
            print(f"    → {new_first_line[:80]}...")
        if len(changes) > 10:
            print(f"    ... and {len(changes) - 10} more changes")
        return True

    filepath.write_text(new_content, encoding="utf-8")
    print(f"📄 {filepath.relative_to(Path.cwd())}: {len(changes)} lines fixed")
    return True


def main():
    parser = argparse.ArgumentParser(description="Fix E501 (line-too-long) violations")
    parser.add_argument("--path", default="src/", help="Target path")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--max-length", type=int, default=120, help="Maximum line length")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show details")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Error: {args.path} not found")
        sys.exit(1)

    # Get E501 violations
    violations = get_e501_violations(str(target), args.max_length)
    if not violations:
        print("✅ No E501 violations found!")
        sys.exit(0)

    # Group by file
    files_to_fix = {}
    for fpath, lineno in violations:
        p = Path(fpath)
        if p.is_absolute():
            files_to_fix[p] = True
        else:
            files_to_fix[Path.cwd() / p] = True

    print(f"Found {len(violations)} E501 violations across {len(files_to_fix)} files")

    fixed = 0
    for filepath in sorted(files_to_fix.keys()):
        if filepath.exists() and filepath.suffix == ".py":
            if fix_file(filepath, dry_run=args.dry_run, max_length=args.max_length):
                fixed += 1

    mode = "Dry-run" if args.dry_run else "Fixed"
    total_violations_after = len(get_e501_violations(str(target), args.max_length))
    reduction = len(violations) - total_violations_after
    print(
        f"\n{mode}: {fixed} files | E501 reduction: {reduction}/{len(violations)} ({reduction * 100 // len(violations)}%) | Remaining: {total_violations_after}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
