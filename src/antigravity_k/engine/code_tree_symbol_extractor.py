from __future__ import annotations

import re

from .code_tree_indexer_models import FileSymbols

RE_PY_FUNCTION = re.compile(r"^(?:async\s+)?def\s+([a-zA-Z_]\w*)\s*\(", re.MULTILINE)
RE_PY_CLASS = re.compile(r"^class\s+([a-zA-Z_]\w*)\s*", re.MULTILINE)
RE_PY_IMPORT = re.compile(r"^(?:from\s+([.\w]+)\s+)?import\s+(.+)$", re.MULTILINE)
_RE_JS_FN = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+\*?\s*([a-zA-Z_$]\w*)\s*\("
)
_RE_JS_ARROW = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_$]\w*)\s*=\s*(?:async\s+)?"
    + r"(?:function\(|\([^)]*\)\s*=>|[a-zA-Z_$]\w*\s*=>)"
)
_RE_GO_FN = re.compile(r"(?:^|\n)\s*func\s+(?:\([^)]*\)\s+)?([a-zA-Z_]\w*)\s*\(")
_RE_RS_FN = re.compile(
    r"(?:^|\n)\s*(?:pub\s+)?(?:unsafe\s+)?(?:async\s+)?fn\s+([a-zA-Z_]\w*)\s*[\(<]"
)
_RE_OO_FN = re.compile(
    r"(?:^|\n)\s*(?:public|private|protected|static|final|abstract|synchronized|override|virtual)?"
    + r"(?:\s+\w+)*\s+([a-zA-Z_]\w*)\s*\("
)
_RE_SWIFT_FN = re.compile(
    r"(?:^|\n)\s*(?:public|private|internal|fileprivate|static|override|mutating|async)?"
    + r"\s*func\s+([a-zA-Z_]\w*)\s*\("
)
_RE_PHP_FN = re.compile(
    r"(?:^|\n)\s*(?:public|private|protected|static|abstract)?\s*function\s+([a-zA-Z_]\w*)\s*\("
)
_RE_RB_FN = re.compile(r"(?:^|\n)\s*def\s+(?:self\.)?([a-zA-Z_]\w*(?:[?!])?)\s")
_RE_CPP_EXACT = re.compile(
    r"(?:^|\n)\s*(?:const\s+)?(?:static\s+)?(?:inline\s+)?(?:virtual\s+)?"
    + r"(?:void|int|char|bool|float|double|long|short|unsigned|size_t|ssize_t|auto|string|vector|map|set|list|unique_ptr|shared_ptr|FILE|ssize_t)"
    + r"\s+(?:[*&]\s+)?([a-zA-Z_]\w*)\s*\("
)
RE_COMMON_CLASS = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:abstract\s+)?(?:open\s+)?class\s+([a-zA-Z_$]\w*)"
)
RE_INTERFACE = re.compile(r"(?:^|\n)\s*(?:export\s+)?(?:interface|trait|protocol)\s+([a-zA-Z_$]\w*)")

_RE_FN_MAP: dict[tuple[str, ...], list[re.Pattern[str]]] = {
    ("js", "jsx", "ts", "tsx"): [_RE_JS_FN, _RE_JS_ARROW],
    ("go",): [_RE_GO_FN],
    ("rs",): [_RE_RS_FN],
    ("java", "kt", "scala"): [_RE_OO_FN],
    ("swift",): [_RE_SWIFT_FN, _RE_OO_FN],
    ("php",): [_RE_PHP_FN],
    ("rb",): [_RE_RB_FN],
    ("c", "cpp", "h", "hpp", "cc", "cxx", "hxx"): [_RE_CPP_EXACT],
    ("css", "scss", "html"): [_RE_OO_FN],
}

_FN_BLACKLIST = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "throw",
        "else",
        "do",
        "try",
        "finally",
        "case",
        "default",
        "break",
        "continue",
        "new",
        "delete",
        "typeof",
        "instanceof",
        "import",
        "export",
        "yield",
        "await",
        "async",
        "this",
        "super",
        "null",
        "undefined",
        "true",
        "false",
        "int",
        "void",
        "float",
        "double",
        "char",
        "bool",
        "long",
        "short",
    }
)

RE_JS_FN = _RE_JS_FN
RE_JS_ARROW = _RE_JS_ARROW
RE_GO_FN = _RE_GO_FN
RE_RS_FN = _RE_RS_FN
RE_OO_FN = _RE_OO_FN
RE_SWIFT_FN = _RE_SWIFT_FN
RE_PHP_FN = _RE_PHP_FN
RE_RB_FN = _RE_RB_FN
RE_CPP_EXACT = _RE_CPP_EXACT


def extract_symbols(rel_path: str, content: str, ext: str) -> FileSymbols | None:
    lines = content.split("\n")
    symbols = FileSymbols(file_path=rel_path, line_count=len(lines), char_count=len(content))

    if ext == ".py":
        _extract_python_symbols(content, symbols)
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        _extract_common_symbols(content, symbols, ext)
        for match in re.finditer(
            r'(?:import\s+.+?\s+from\s+["\']([^"\']+)["\']|require\(["\']([^"\']+)["\']\))',
            content,
        ):
            imp = match.group(1) or match.group(2)
            if imp and imp not in symbols.imports:
                symbols.imports.append(imp)
                if len(symbols.imports) > 20:
                    break
    elif ext in (".go", ".rs", ".java", ".kt", ".swift", ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".scala"):
        _extract_common_symbols(content, symbols, ext)
    elif ext == ".md":
        for match in re.finditer(r"^(#{1,3})\s+(.+)$", content, re.MULTILINE):
            heading = match.group(2).strip()
            if heading:
                symbols.functions.append(f"§{heading[:40]}")
                if len(symbols.functions) > 20:
                    break
    elif ext in (".yaml", ".yml", ".json"):
        symbols.line_count = len(lines)
    elif ext in (".css", ".scss", ".html"):
        _extract_common_symbols(content, symbols, ext)

    if not symbols.functions and not symbols.classes and symbols.line_count < 5:
        return None
    return symbols


def _extract_python_symbols(content: str, symbols: FileSymbols) -> None:
    for match in RE_PY_FUNCTION.finditer(content):
        name = match.group(1)
        if name and name not in symbols.functions:
            symbols.functions.append(name)

    for match in RE_PY_CLASS.finditer(content):
        name = match.group(1)
        if name and name not in symbols.classes:
            symbols.classes.append(name)

    for match in RE_PY_IMPORT.finditer(content):
        from_module = match.group(1)
        imported = match.group(2)
        if from_module:
            for item in re.split(r",\s*", imported):
                item_clean = item.strip().split(" as ")[0].strip()
                if item_clean and f"{from_module}.{item_clean}" not in symbols.imports:
                    symbols.imports.append(f"{from_module}.{item_clean}")
                    if len(symbols.imports) > 20:
                        break
        else:
            for item in re.split(r",\s*", imported):
                item_clean = item.strip().split(" as ")[0].strip()
                if item_clean and item_clean not in symbols.imports:
                    symbols.imports.append(item_clean)
                    if len(symbols.imports) > 20:
                        break


def _extract_common_symbols(content: str, symbols: FileSymbols, ext: str = "") -> None:
    patterns: list[re.Pattern[str]] = []
    for exts, pats in _RE_FN_MAP.items():
        if ext and ext.lstrip(".") in exts:
            patterns.extend(pats)
            break
    else:
        patterns = [_RE_JS_FN, _RE_GO_FN, _RE_RS_FN, _RE_OO_FN, _RE_SWIFT_FN, _RE_PHP_FN, _RE_RB_FN]

    for pattern in patterns:
        for match in pattern.finditer(content):
            name = match.group(1)
            if name and name not in _FN_BLACKLIST and name not in symbols.functions:
                symbols.functions.append(name)
                if len(symbols.functions) > 50:
                    break
        if len(symbols.functions) > 50:
            break

    for match in RE_COMMON_CLASS.finditer(content):
        name = match.group(1)
        if name and name not in symbols.classes:
            symbols.classes.append(name)
            if len(symbols.classes) > 20:
                break

    for match in RE_INTERFACE.finditer(content):
        name = match.group(1)
        if name and name not in symbols.classes:
            symbols.classes.append(name)
            if len(symbols.classes) > 20:
                break
