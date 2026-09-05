#!/usr/bin/env python3
"""
Auto-generate missing Python docstrings (D100-D107) using AST analysis + AI.

Detects all ruff D(pydocstyle) violations, extracts function/class/module context,
and generates Google-style docstrings. Supports template-based (fast) and AI-based
(descriptive) generation modes.

Usage:
    python scripts/generate_docstrings.py                    # template mode (default)
    python scripts/generate_docstrings.py --ai               # AI-enhanced mode
    python scripts/generate_docstrings.py --dry-run          # preview only
    python scripts/generate_docstrings.py --check            # exit 1 if any missing
    python scripts/generate_docstrings.py --path src/        # target specific directory

Requires:
    - ruff (for violation detection)
    - openai (optional, for --ai mode)
"""

import argparse
import ast
import importlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypedDict, cast

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _ParamContext(TypedDict):
    name: str
    type: str
    kind: str


class _ModuleContext(TypedDict):
    name: str
    path: str


class _ClassContext(TypedDict):
    name: str
    bases: list[str]


class _FunctionContext(TypedDict):
    name: str
    params: list[_ParamContext]
    return_type: str
    is_method: bool
    is_async: bool
    decorator_names: list[str]


GenerationContext = TypedDict(
    "GenerationContext",
    {
        "error": str,
        "file": str,
        "line": int,
        "code_prefix": str,
        "type": str,
        "module": _ModuleContext,
        "class": _ClassContext,
        "function": _FunctionContext,
        "class_name": str | None,
        "ast_type": str,
    },
    total=False,
)


class _RuffLocation(TypedDict):
    row: int


class _RuffViolation(TypedDict):
    filename: str
    code: str
    message: str
    location: _RuffLocation


class _CliArgs(Protocol):
    ai: bool
    dry_run: bool
    check: bool
    path: str
    verbose: bool


class _OpenAIMessage(Protocol):
    content: str | None


class _OpenAIChoice(Protocol):
    message: _OpenAIMessage


class _OpenAIResponse(Protocol):
    choices: list[_OpenAIChoice]


class _OpenAICompletions(Protocol):
    def create(self, **kwargs: object) -> _OpenAIResponse: ...



class _OpenAIChat(Protocol):
    completions: _OpenAICompletions


class _OpenAIClient(Protocol):
    chat: _OpenAIChat


class _OpenAIModule(Protocol):
    OpenAI: Callable[..., _OpenAIClient]


# ─── Violation Detection ─────────────────────────────────────────────────


def get_ruff_violations(paths: list[str]) -> list[_RuffViolation]:
    """Run ruff --select=D and return parsed JSON violations."""
    cmd = ["ruff", "check", "--select=D", "--output-format=json", *paths]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.returncode == 0:
        return []  # no violations
    try:
        return cast(list[_RuffViolation], json.loads(result.stdout))
    except json.JSONDecodeError:
        print(f"⚠ Failed to parse ruff output: {result.stdout[:200]}", file=sys.stderr)
        return []


# ─── AST Context Extraction ──────────────────────────────────────────────


def find_node_at_line(tree: ast.AST, line: int) -> ast.AST | None:
    """Find the outermost AST definition node starting at the given line.

    Performs an explicit DFS over child nodes (not via ast.walk which is
    order-undefined), returning the outermost Definition/ClassDef/FunctionDef/Module.
    """
    candidate: ast.AST | None = None

    def _search(node: ast.AST) -> None:
        nonlocal candidate
        start_line = getattr(node, "lineno", -1)
        if start_line == line:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                candidate = node
        # Recurse into children — only once, explicit order
        for child in ast.iter_child_nodes(node):
            _search(child)

    _search(tree)
    return candidate


def get_function_context(node: ast.FunctionDef | ast.AsyncFunctionDef) -> _FunctionContext:
    """Extract context from a function/method definition node.

    Collects all parameter kinds: positional, positional-only, vararg (*args),
    keyword-only, and kwarg (**kwargs). Each param carries a ``kind`` field
    to allow the docstring formatter to emit the correct prefix.
    """
    args = node.args
    params: list[_ParamContext] = []

    def _add(name: str, type_str: str, kind: str) -> None:
        params.append({"name": name, "type": type_str, "kind": kind})

    # Positional-only (PEP 570) — e.g. def f(a, b, /, c)
    for arg in args.posonlyargs:
        _add(arg.arg, ast.unparse(arg.annotation) if arg.annotation else "", "posonly")

    # Regular positional/keyword arguments
    for arg in args.args:
        _add(arg.arg, ast.unparse(arg.annotation) if arg.annotation else "", "regular")

    # *args (vararg)
    if args.vararg:
        _add(args.vararg.arg, ast.unparse(args.vararg.annotation) if args.vararg.annotation else "", "vararg")

    # Keyword-only arguments (after * or *args)
    for arg in args.kwonlyargs:
        _add(arg.arg, ast.unparse(arg.annotation) if arg.annotation else "", "kwonly")

    # **kwargs (kwarg)
    if args.kwarg:
        _add(args.kwarg.arg, ast.unparse(args.kwarg.annotation) if args.kwarg.annotation else "", "kwarg")

    return_type = ast.unparse(node.returns) if node.returns else ""

    # Detect if it's a method (first param is self/cls)
    is_method = bool(params and params[0]["name"] in ("self", "cls"))

    return {
        "name": node.name,
        "params": params,
        "return_type": return_type,
        "is_method": is_method,
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "decorator_names": [ast.unparse(d) for d in node.decorator_list],
    }


def get_class_context(node: ast.ClassDef) -> _ClassContext:
    """Extract context from a class definition node."""
    bases = [ast.unparse(b) for b in node.bases]
    return {
        "name": node.name,
        "bases": bases,
    }


def get_module_context(filepath: Path) -> _ModuleContext:
    """Extract module-level context."""
    # Try to infer module purpose from filename and imports
    return {
        "name": filepath.stem,
        "path": str(filepath.relative_to(PROJECT_ROOT)),
    }


def extract_context(filepath: Path, line: int, code: str) -> GenerationContext:
    """Extract context for a violation at the given line."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"error": f"Syntax error: {e}"}

    node = find_node_at_line(tree, line)

    # Python 3.12+ ast.Module may lack lineno attribute, so find_node_at_line
    # won't match it. Fall back to treating the root tree as a module when the
    # violation is at module level (D100 / D104) and no node was found.
    if node is None:
        node = tree

    context: GenerationContext = {
        "file": str(filepath.relative_to(PROJECT_ROOT)),
        "line": line,
        "code_prefix": _get_code_prefix(code, line),
    }

    if isinstance(node, ast.Module):
        context["type"] = "module"
        context["module"] = get_module_context(filepath)
    elif isinstance(node, ast.ClassDef):
        context["type"] = "class"
        context["class"] = get_class_context(node)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        context["type"] = "method" if _is_method(node) else "function"
        context["function"] = get_function_context(node)
        # Find enclosing class for methods
        context["class_name"] = _find_enclosing_class(tree, node)
    else:
        context["type"] = "unknown"
        context["ast_type"] = type(node).__name__

    return context


def _get_code_prefix(code: str, line: int, context_lines: int = 3) -> str:
    """Get surrounding lines for context."""
    lines = code.splitlines()
    start = max(0, line - context_lines - 1)
    end = min(len(lines), line + context_lines)
    return "\n".join(lines[start:end])


def _is_method(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function is likely a method (has self/cls param)."""
    args = node.args
    return bool(args.args and args.args[0].arg in ("self", "cls"))


def _find_enclosing_class(tree: ast.AST, func_node: ast.AST) -> str | None:
    """Find the enclosing class name for a method."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if child is func_node:
                    return node.name
    return None


# ─── Docstring Generation ────────────────────────────────────────────────


def generate_docstring(context: GenerationContext, ai_mode: bool = False) -> str | None:
    """Generate a Google-style docstring for the given context."""
    vtype = context.get("type")

    if vtype == "module":
        return _gen_module_docstring(context)
    elif vtype == "class":
        return _gen_class_docstring(context)
    elif vtype in ("function", "method"):
        return _gen_function_docstring(context, ai_mode)
    return None


def _snake_to_title(name: str) -> str:
    """Convert snake_case to Title Case."""
    return name.replace("_", " ").title().strip()


def _gen_module_docstring(ctx: GenerationContext) -> str:
    """Generate a single-line module docstring.

    Uses single-line format (no D205 issue for single-line docstrings).
    """
    module = ctx.get("module", {})
    name = module.get("name", "")
    path = module.get("path", "")

    # Infer purpose from module name
    parts = re.split(r"[_/]", name)
    purpose = " ".join(parts).title()

    # Check for common module patterns
    if "test" in name.lower():
        result = f'"""Tests for {name.replace("test_", "").replace("_", " ")} module."""'
    elif name == "__init__":
        parent_dir = Path(path).parent.name if path else ""
        result = f'"""{parent_dir.replace("_", " ").title()} package."""'
    else:
        result = f'"""{purpose} module."""'

    return _ensure_docstring_compliance(result)


def _gen_class_docstring(ctx: GenerationContext) -> str:
    """Generate a class docstring from context.

    Generates Google-style docstrings that comply with D205
    (blank line between summary line and description).
    """
    cls = ctx.get("class", {})
    name = cls.get("name", "")
    bases = cls.get("bases", [])

    title = _snake_to_title(name)

    if bases:
        base_str = ", ".join(bases)
        # Blank line after summary ensures D205 compliance
        result = f'''"""{title}.

    Bases: {base_str}
    """'''
    else:
        result = f'''"""{title}."""'''
    return _ensure_docstring_compliance(result)


def _gen_function_docstring(ctx: GenerationContext, ai_mode: bool = False) -> str:
    """Generate a function/method docstring from context.

    Generates Google-style docstrings that comply with D205
    (blank line between summary line and description).
    """
    _ = ai_mode
    func = ctx.get("function", {})
    name = func.get("name", "")
    params = func.get("params", [])
    return_type = func.get("return_type", "")
    is_method = func.get("is_method", False)
    class_name = ctx.get("class_name")

    # Generate summary line from function name
    summary = _gen_summary_line(name, return_type, is_method, class_name)

    # Build Google-style docstring.
    # The empty string after summary creates the required D205 blank line
    # between summary and body (Args/Returns sections).
    docstring_parts: list[str] = [summary, ""]

    # Args section (skip self/cls for methods)
    args_section = _gen_args_section(params, is_method)
    if args_section:
        docstring_parts.append(args_section)

    # Returns section
    returns_section = _gen_returns_section(return_type)
    if returns_section:
        docstring_parts.append(returns_section)

    docstring = "\n    ".join(docstring_parts)
    result = f'"""{docstring}\n    """'
    return _ensure_docstring_compliance(result)


def _gen_summary_line(name: str, return_type: str, is_method: bool, class_name: str | None) -> str:
    """Generate the summary line from function name and context."""
    _ = is_method
    # Strip common prefixes like 'get_', 'set_', 'is_', 'has_'
    verb_map = {
        "get": "Retrieve",
        "set": "Set",
        "is": "Check if",
        "has": "Check if",
        "create": "Create",
        "update": "Update",
        "delete": "Remove",
        "add": "Add",
        "remove": "Remove",
        "find": "Find",
        "search": "Search for",
        "load": "Load",
        "save": "Save",
        "parse": "Parse",
        "build": "Build",
        "gen": "Generate",
        "run": "Run",
        "exec": "Execute",
        "validate": "Validate",
        "format": "Format",
        "convert": "Convert",
        "transform": "Transform",
        "merge": "Merge",
        "split": "Split",
        "init": "Initialize",
        "connect": "Connect",
        "disconnect": "Disconnect",
        "fetch": "Fetch",
        "push": "Push",
        "pull": "Pull",
        "sync": "Synchronize",
        "register": "Register",
        "unregister": "Unregister",
        "subscribe": "Subscribe",
        "notify": "Notify",
        "handle": "Handle",
        "process": "Process",
        "render": "Render",
    }

    # Handle dunder methods
    if name.startswith("__") and name.endswith("__"):
        dunder_desc = {
            "__init__": f"Initialize the {class_name or 'class'}.",
            "__str__": "Return a string representation.",
            "__repr__": "Return a formal string representation.",
            "__len__": "Return the length.",
            "__iter__": "Return an iterator.",
            "__next__": "Return the next item.",
            "__enter__": "Enter the runtime context.",
            "__exit__": "Exit the runtime context.",
            "__aenter__": "Enter the async runtime context.",
            "__aexit__": "Exit the async runtime context.",
            "__call__": "Call the instance as a function.",
            "__eq__": "Check equality.",
            "__ne__": "Check inequality.",
            "__lt__": "Check if less than.",
            "__le__": "Check if less than or equal.",
            "__gt__": "Check if greater than.",
            "__ge__": "Check if greater than or equal.",
            "__hash__": "Return the hash.",
            "__bool__": "Return the truth value.",
            "__contains__": "Check if contains item.",
            "__getitem__": "Get item by key.",
            "__setitem__": "Set item by key.",
            "__delitem__": "Delete item by key.",
            "__add__": "Add.",
            "__sub__": "Subtract.",
            "__mul__": "Multiply.",
            "__truediv__": "Divide.",
            "__floordiv__": "Floor divide.",
            "__mod__": "Modulo.",
            "__pow__": "Power.",
        }
        if name in dunder_desc:
            return dunder_desc[name]

        return f"{name.strip('_').replace('_', ' ').title()}."

    # Infer verb from function name
    for prefix, verb in verb_map.items():
        if name.startswith(prefix + "_") or name == prefix:
            rest = name[len(prefix) + 1 :] if name.startswith(prefix + "_") else ""
            if rest:
                desc = rest.replace("_", " ")
                return f"{verb} {desc}."
            return f"{verb}."

    # Default: convert snake_case to description
    desc = name.replace("_", " ").strip()
    if return_type and return_type not in ("None", "bool", "str", "int", "float"):
        return f"{desc.title()}."
    return f"{desc.title()}."


def _gen_args_section(params: list[_ParamContext], is_method: bool) -> str | None:
    """Generate the Args section of a Google-style docstring.

    Handles all parameter kinds: regular, *args (vararg), **kwargs (kwarg),
    positional-only, and keyword-only. The ``kind`` field in each param dict
    controls the prefix emitted in the listing.
    """
    visible_params = params[1:] if is_method else params
    if not visible_params:
        return None

    lines: list[str] = ["Args:"]
    for p in visible_params:
        # Determine display name with proper prefix for vararg/kwarg
        kind = p.get("kind", "regular")
        if kind == "vararg":
            display_name = f"*{p['name']}"
        elif kind == "kwarg":
            display_name = f"**{p['name']}"
        else:
            display_name = p["name"]

        type_hint = f" ({p['type']})" if p["type"] else ""

        # Build a meaningful description from type hint + param name
        desc_parts: list[str] = []
        if p["type"] and p["type"] != "Any":
            desc_parts.append(p["type"])
        if p["name"]:
            desc_parts.append(p["name"].replace("_", " "))
        desc = " ".join(desc_parts).strip() if desc_parts else p["name"]
        if not desc.endswith("."):
            desc += "."
        lines.append(f"    {display_name}{type_hint}: {desc}")
    return "\n    ".join(lines)


def _gen_returns_section(return_type: str) -> str | None:
    """Generate the Returns section of a Google-style docstring."""
    if not return_type or return_type == "None":
        return None

    lines = ["Returns:"]
    lines.append(f"    {return_type}: The {return_type.lower()} result.")
    return "\n    ".join(lines)


# ─── Docstring Insertion ─────────────────────────────────────────────────


def insert_docstring(line: int, docstring: str, code: str, is_module: bool = False) -> str | None:
    """Insert a docstring at the given line in the source code."""
    lines = code.splitlines()
    if line < 1 or line > len(lines):
        return None

    if is_module:
        # Module docstring: insert right after shebang/encoding comment, or at top
        insert_line = 0  # 0-indexed, default to top
        for i, ln in enumerate(lines):
            if ln.startswith("#!") or ln.startswith("# -*- coding:") or ln.startswith("# coding:"):
                continue  # skip shebang/cookie
            if not ln.strip():
                continue  # skip leading blank lines
            insert_line = i
            break
        indent = ""
    else:
        # Function/class docstring: find the colon at end of signature
        indent = _get_indent(lines[line - 1])

        # Skip Ellipsis/pass-body methods (Protocol, ABC) that have no indented body.
        # Check the original violation line, NOT the while-loop target.
        orig_line = lines[line - 1].strip()
        if (
            orig_line.endswith(":...")
            or orig_line.endswith(": ...")
            or orig_line.endswith(": pass")
            or orig_line.endswith(":pass")
        ):
            return None

        insert_line = line - 1  # 0-indexed
        while insert_line < len(lines) and not lines[insert_line].strip().endswith(":"):
            insert_line += 1
        if insert_line < len(lines):
            insert_line += 1  # After the colon line
        else:
            insert_line = line  # fallback

    # Insert docstring with proper indentation
    docstring_lines = docstring.split("\n")
    if is_module:
        # Module docstrings must not be indented
        indented_docstring = "\n".join(dl if dl.strip() else dl for dl in docstring_lines)
    else:
        indented_docstring = "\n".join(
            (indent + "    " + dl) if dl.strip() else indent + "    " for dl in docstring_lines
        )

    lines.insert(insert_line, indented_docstring)
    return "\n".join(lines)


def _get_indent(line: str) -> str:
    """Get the indentation of a line."""
    return line[: len(line) - len(line.lstrip())]


def _ensure_docstring_compliance(docstring: str) -> str:
    """Post-process a generated docstring to guarantee ruff D rule compliance.

    Ensures:
    - D400/D415: The first (summary) line ends with a period.
    - D205: A blank line exists between the summary and the body
      for multi-line docstrings (already guaranteed by templates, but
      reinforced here for safety).

    This is a safety net — the individual _gen_* functions should already
    produce compliant docstrings, but this catches any edge cases.
    """
    lines = docstring.split("\n")
    if len(lines) < 2:
        # Single-line docstring: no D205 risk; just ensure trailing period
        stripped = docstring.rstrip('"').rstrip()
        if not stripped.endswith("."):
            stripped += "."
            return stripped + '"""'
        return docstring

    # Locate the summary line (first content after opening """)
    first_content_idx = None
    for i, line in enumerate(lines):
        stripped = line.replace('"""', "").strip()
        if stripped:
            first_content_idx = i
            break

    if first_content_idx is None:
        return docstring

    # --- D400: Ensure summary ends with period ---
    summary_line = lines[first_content_idx]
    summary_text = summary_line.replace('"""', "").rstrip()
    if not summary_text.endswith("."):
        lines[first_content_idx] = summary_line.rstrip() + "."
        lines[first_content_idx] = lines[first_content_idx].replace("..", ".")

    # --- D205: Ensure blank line between summary and next non-empty body line ---
    if first_content_idx + 1 < len(lines):
        next_line = lines[first_content_idx + 1].strip()
        # If the next non-empty line is NOT blank (empty string), insert one
        if next_line and not next_line.startswith('"""'):
            # Check if the line after summary is content (not a blank line)
            for j in range(first_content_idx + 1, len(lines)):
                candidate = lines[j].strip()
                if candidate and not candidate.startswith('"""'):
                    # Found content — need blank line before it
                    # Pattern: the line right after summary should be blank
                    line_after_summary = lines[first_content_idx + 1].strip()
                    if line_after_summary:
                        indent = _get_indent(lines[first_content_idx + 1])
                        lines.insert(first_content_idx + 1, indent)
                    break
                elif candidate.startswith('"""'):
                    break  # closing """ — nothing to insert
                elif not candidate:
                    break  # already a blank line

    return "\n".join(lines)


# ─── AI Mode ─────────────────────────────────────────────────────────────


def generate_ai_docstring(context: GenerationContext) -> str | None:
    """Generate a docstring using an LLM (OpenAI-compatible API)."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠ --ai mode requires OPENAI_API_KEY or ANTHROPIC_API_KEY", file=sys.stderr)
        return generate_docstring(context, ai_mode=False)  # fallback to template

    prompt = _build_ai_prompt(context)
    try:
        # Try OpenAI-compatible API first
        openai_module = cast(_OpenAIModule, cast(object, importlib.import_module("openai")))
        client = openai_module.OpenAI(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL"))
        response = client.chat.completions.create(
            model=os.environ.get("DOCSTRING_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a Python documentation expert. Generate concise Google-style docstrings. Output ONLY the docstring content (no markdown, no explanation).",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=350,
        )
        content = response.choices[0].message.content or ""
        docstring = content.strip()
        # Clean up if the AI wraps in markdown
        docstring = docstring.strip("`").strip()
        if not docstring.startswith('"""'):
            docstring = '"""' + docstring + '"""'
        return docstring
    except ImportError:
        print("⚠ openai package not installed. Install with: pip install openai", file=sys.stderr)
        return generate_docstring(context, ai_mode=False)
    except Exception as e:
        print(f"⚠ AI generation failed: {e}", file=sys.stderr)
        return generate_docstring(context, ai_mode=False)


def _build_ai_prompt(context: GenerationContext) -> str:
    """Build a prompt for the AI describing what docstring to generate."""
    vtype = context.get("type")

    if vtype == "module":
        module = context.get("module", {})
        return f"""Generate a one-line module docstring for {module.get("path", "")} (Python module). Context:
{context.get("code_prefix", "")}"""
    elif vtype == "class":
        cls = context.get("class", {})
        return f"""Generate a Google-style docstring for class {cls.get("name", "")} (bases: {cls.get("bases", [])}). Context:
{context.get("code_prefix", "")}"""
    elif vtype in ("function", "method"):
        func = context.get("function", {})
        return f"""Generate a Google-style docstring for {"async " if func.get("is_async") else ""}function {func.get("name", "")}({", ".join(f"{p['name']}: {p['type']}" if p["type"] else p["name"] for p in func.get("params", []))}) -> {func.get("return_type", "None")}. Context:
{context.get("code_prefix", "")}"""
    return "Generate a docstring."


# ─── Main ────────────────────────────────────────────────────────────────


def get_violations_by_file(violations: list[_RuffViolation]) -> dict[str, list[_RuffViolation]]:
    """Group violations by file path."""
    by_file: dict[str, list[_RuffViolation]] = {}
    for v in violations:
        by_file.setdefault(v["filename"], []).append(v)
    return by_file


def _main() -> None:
    parser = argparse.ArgumentParser(description="Auto-generate missing Python docstrings")
    _ = parser.add_argument("--ai", action="store_true", help="Use AI for descriptive docstrings")
    _ = parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    _ = parser.add_argument("--check", action="store_true", help="Exit 1 if any missing docstrings")
    _ = parser.add_argument("--path", default="src/", help="Target path (default: src/)")
    _ = parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = cast(_CliArgs, cast(object, parser.parse_args()))

    target_paths = args.path.split(",")

    if args.check:
        violations = get_ruff_violations(target_paths)
        violations = [v for v in violations if v["code"].startswith("D10")]
        count = len(violations)
        print(f"Missing docstrings: {count}")
        if count > 0:
            for v in violations[:20]:  # show first 20
                print(f"  {v['filename']}:{v['location']['row']}: {v['code']} ({v['message']})")
            if count > 20:
                print(f"  ... and {count - 20} more")
        sys.exit(0 if count == 0 else 1)

    violations = get_ruff_violations(target_paths)
    # Only process D100-D107 (missing docstrings), skip D200+ (formatting)
    violations = [v for v in violations if v["code"].startswith("D10")]
    if not violations:
        print("✅ No missing docstrings found!")
        sys.exit(0)

    by_file = get_violations_by_file(violations)
    total = len(violations)
    print(f"Found {total} missing docstrings across {len(by_file)} files\n")

    fixed = 0
    skipped = 0
    errors = 0

    # Process files in sorted order (most violations first)
    sorted_files = sorted(by_file.items(), key=lambda x: -len(x[1]))

    for filepath_str, file_violations in sorted_files:
        filepath = Path(filepath_str)
        if not filepath.is_file():
            try:
                filepath = PROJECT_ROOT / filepath_str
            except Exception:
                skipped += len(file_violations)
                continue

        if not filepath.exists():
            if args.verbose:
                print(f"⚠ File not found: {filepath}")
            skipped += len(file_violations)
            continue

        try:
            code = filepath.read_text()
        except Exception as e:
            print(f"⚠ Cannot read {filepath}: {e}")
            skipped += len(file_violations)
            continue

        file_fixed = 0

        # Sort violations by line (process bottom-to-top to preserve line numbers)
        sorted_violations = sorted(file_violations, key=lambda v: -v["location"]["row"])

        for v in sorted_violations:
            line = v["location"]["row"]
            code_rule = v["code"]  # e.g., D100, D102

            if args.verbose:
                print(f"  [{code_rule}] {filepath}:{line}")

            context = extract_context(filepath, line, code)
            if "error" in context:
                if args.verbose:
                    print(f"    ⚠ {context['error']}")
                errors += 1
                continue

            # Generate docstring
            if args.ai:
                docstring = generate_ai_docstring(context)
            else:
                docstring = generate_docstring(context)

            if not docstring:
                if args.verbose:
                    print("    ⚠ Could not generate docstring")
                    skipped += 1
                continue

            is_module = context.get("type") == "module"
            new_code = insert_docstring(line, docstring, code, is_module=is_module)
            if new_code and new_code != code:
                code = new_code
                file_fixed += 1
                fixed += 1
                if args.verbose:
                    # Show preview
                    first_line = docstring.split("\n")[0]
                    print(f"    ✅ {first_line}")
            else:
                if args.verbose:
                    print(f"    ⚠ Failed to insert at line {line}")
                skipped += 1

        if file_fixed > 0:
            if args.dry_run:
                print(f"\n📄 {filepath.relative_to(PROJECT_ROOT)}: {file_fixed} docstrings (dry-run)")
            else:
                _ = filepath.write_text(code)
                print(f"📄 {filepath.relative_to(PROJECT_ROOT)}: {file_fixed} docstrings written")

    print(f"\n{'=' * 50}")
    print(f"Summary: {fixed} generated, {skipped} skipped, {errors} errors")
    if args.dry_run:
        print("(dry run — no files modified)")
    else:
        # Re-check with ruff
        remaining = get_ruff_violations(target_paths)
        print(f"Remaining violations: {len(remaining)}")
        if remaining:
            print(f"Run again or address manually for the remaining {len(remaining)} violations.")


if __name__ == "__main__":
    _main()
