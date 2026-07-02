"""Antigravity-K: Code Tree Indexer (Freebuff-Style Proactive Context).

=============================================================
사용자 메시지 수신 시 관련 파일을 자동 탐색하기 위한 경량 코드 트리 인덱서.

Freebuff의 Tree-sitter 기반 코드 트리를 모방하되,
Python AST + regex 기반으로 구현하여 의존성 없이 동작합니다.

기능:
- 프로젝트 전체 파일 스캔 → 함수/클래스/임포트 맵 구축
- 변경 감지 (MD5 해시) → 증분 갱신
- 쿼리 기반 관련 파일 검색 (키워드 + 심볼 매칭)
- 압축된 코드 트리 문자열 생성 (전체 레포 100KB 이하 목표)
"""

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity_k.code_tree_indexer")

# 인덱싱 대상 확장자
INDEXABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".kt", ".swift",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".scala",
    ".css", ".scss", ".html", ".md", ".yaml", ".yml", ".json",
}

# 무시할 디렉토리
IGNORE_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    "dist", "build", ".egg-info", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", ".hypothesis", ".tox", "coverage", ".coverage", ".next",
    "out", ".turbo", ".cache", ".output",
    "public", "static", "assets", "images", "fonts",
    ".agent",  # 에이전트 스킬/메타데이터는 제외
}

# Python 함수/클래스/임포트 추출 정규식
RE_PY_FUNCTION = re.compile(r"^(?:async\s+)?def\s+([a-zA-Z_]\w*)\s*\(", re.MULTILINE)
RE_PY_CLASS = re.compile(r"^class\s+([a-zA-Z_]\w*)\s*", re.MULTILINE)
RE_PY_IMPORT = re.compile(
    r"^(?:from\s+([.\w]+)\s+)?import\s+(.+)$", re.MULTILINE,
)

# ─── 언어별 함수/메서드 추출 정규식 ───
# JS/TS: function name(), async function name(), export function name()
_RE_JS_FN = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+\*?\s*([a-zA-Z_$]\w*)\s*\(",
)
# JS/TS: const name = (...) => { ... } (화살표 함수, function으로 시작하는 경우만)
_RE_JS_ARROW = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_$]\w*)\s*=\s*(?:async\s+)?"
    r"(?:function\(|\([^)]*\)\s*=>|[a-zA-Z_$]\w*\s*=>)",
)
# Go: func name(), func (r *T) name()
_RE_GO_FN = re.compile(
    r"(?:^|\n)\s*func\s+(?:\([^)]*\)\s+)?([a-zA-Z_]\w*)\s*\(",
)
# Rust: fn name(), pub fn name(), pub unsafe fn name()
_RE_RS_FN = re.compile(
    r"(?:^|\n)\s*(?:pub\s+)?(?:unsafe\s+)?(?:async\s+)?fn\s+([a-zA-Z_]\w*)\s*[\(<]",
)
# Java/C#/Kotlin: access_modifier return_type name()  또는 fun name()
_RE_OO_FN = re.compile(
    r"(?:^|\n)\s*(?:public|private|protected|static|final|abstract|synchronized|override|virtual)?"
    r"(?:\s+\w+)*\s+([a-zA-Z_]\w*)\s*\(",
)
# Swift: func name()
_RE_SWIFT_FN = re.compile(
    r"(?:^|\n)\s*(?:public|private|internal|fileprivate|static|override|mutating|async)?"
    r"\s*func\s+([a-zA-Z_]\w*)\s*\(",
)
# PHP: function name(), public function name()
_RE_PHP_FN = re.compile(
    r"(?:^|\n)\s*(?:public|private|protected|static|abstract)?\s*function\s+([a-zA-Z_]\w*)\s*\(",
)
# Ruby: def name, def self.name
_RE_RB_FN = re.compile(
    r"(?:^|\n)\s*def\s+(?:self\.)?([a-zA-Z_]\w*(?:[?!])?)\s",
)
# C/C++: ret_type name(  (제한적: type이 먼저 오는 패턴)
_RE_CPP_EXACT = re.compile(
    r"(?:^|\n)\s*(?:const\s+)?(?:static\s+)?(?:inline\s+)?(?:virtual\s+)?"
    r"(?:void|int|char|bool|float|double|long|short|unsigned|size_t|ssize_t|auto|string|vector|map|set|list|unique_ptr|shared_ptr|FILE|ssize_t)"
    r"\s+(?:[*&]\s+)?([a-zA-Z_]\w*)\s*\(",
)

# 공통 클래스 추출
RE_COMMON_CLASS = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:abstract\s+)?(?:open\s+)?class\s+([a-zA-Z_$]\w*)",
)
# 인터페이스/트레이트/프로토콜 추출
RE_INTERFACE = re.compile(
    r"(?:^|\n)\s*(?:export\s+)?(?:interface|trait|protocol)\s+([a-zA-Z_$]\w*)",
)



@dataclass
class FileSymbols:
    """파일별 추출 심볼 정보."""

    file_path: str
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    line_count: int = 0
    char_count: int = 0


class CodeTreeIndexer:
    """프로젝트 코드 트리를 구축하고 쿼리 기반 검색을 제공합니다.

    사용법:
        indexer = CodeTreeIndexer(project_root)
        tree_str = indexer.build_tree()          # 압축된 코드 트리 문자열
        files = indexer.search("user auth")       # 관련 파일 검색
    """

    def __init__(self, project_root: str):
        """Initialize the CodeTreeIndexer.

        Args:
            project_root: 프로젝트 루트 경로
        """
        self.project_root = os.path.abspath(project_root)
        self._symbols: dict[str, FileSymbols] = {}  # rel_path → FileSymbols
        self._tree_cache: str = ""
        self._tree_hash: str = ""
        self._file_hashes: dict[str, str] = {}  # rel_path → md5

    def build_tree(self, force: bool = False) -> str:
        """전체 프로젝트 코드 트리를 구축합니다.

        변경이 없으면 캐시를 반환합니다.

        Args:
            force: True면 강제 재구축

        Returns:
            압축된 코드 트리 문자열
        """
        if not force and self._tree_cache:
            return self._tree_cache

        self._symbols.clear()
        total_files = 0
        changed_files = 0

        for root, dirs, files in os.walk(self.project_root):
            # 무시할 디렉토리 필터링
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

            for fname in files:
                ext = Path(fname).suffix.lower()
                if ext not in INDEXABLE_EXTENSIONS:
                    continue

                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, self.project_root)

                try:
                    with open(fpath, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue

                # 변경 감지
                content_hash = hashlib.md5(content.encode()).hexdigest()
                if self._file_hashes.get(rel_path) == content_hash and not force:
                    # 이미 있으면 기존 심볼 유지
                    if rel_path in self._symbols:
                        total_files += 1
                        continue

                self._file_hashes[rel_path] = content_hash
                changed_files += 1

                # 심볼 추출
                symbols = self._extract_symbols(rel_path, content, ext)
                if symbols:
                    self._symbols[rel_path] = symbols
                    total_files += 1

        # 압축된 트리 문자열 생성
        tree_lines = []
        for rel_path in sorted(self._symbols.keys()):
            sym = self._symbols[rel_path]
            parts = []

            # 클래스
            for cls in sym.classes:
                parts.append(f"cls:{cls}")
            # 함수
            for fn in sym.functions:
                parts.append(f"fn:{fn}")
            # 임포트 (요약)
            if sym.imports:
                imports_short = ", ".join(
                    imp.split(".")[0] for imp in sym.imports[:5]
                )
                if len(sym.imports) > 5:
                    imports_short += f" (+{len(sym.imports) - 5})"
                parts.append(f"import:{imports_short}")

            sym_str = " | ".join(parts) if parts else f"{sym.line_count} lines"
            tree_lines.append(f"{rel_path} [{sym_str}]")

        self._tree_cache = "\n".join(tree_lines)

        logger.info(
            "[CodeTree] Built tree: %s files (%s new/changed), %s KB",
            total_files,
            changed_files,
            len(self._tree_cache) // 1024,
        )
        return self._tree_cache

    def get_tree(self) -> str:
        """캐시된 코드 트리를 반환하거나, 없으면 구축합니다."""
        if not self._tree_cache:
            return self.build_tree()
        return self._tree_cache

    def search(self, query: str, max_files: int = 12) -> list[dict[str, Any]]:
        """사용자 쿼리와 관련된 파일을 코드 트리 기반으로 검색합니다.

        매칭 전략 (가중치 순):
        1. 파일명 정확 매칭 (3점)
        2. 심볼명(클래스/함수) 매칭 (2점)
        3. 파일 경로 부분 매칭 (1점)
        4. 임포트 키워드 매칭 (1점)

        Args:
            query: 사용자 메시지 (자연어)
            max_files: 최대 반환 파일 수

        Returns:
            [{"file": "rel/path.py", "score": 5.0, "symbols": [...]}, ...]
        """
        if not self._symbols:
            self.build_tree()

        query_lower = query.lower()
        query_tokens = set(query_lower.split())

        scored: list[tuple[float, str, FileSymbols]] = []

        for rel_path, sym in self._symbols.items():
            score = 0.0
            path_lower = rel_path.lower()
            file_stem = Path(rel_path).stem.lower()

            # 1. 파일명 정확 매칭
            for token in query_tokens:
                if token == file_stem:
                    score += 3.0
                elif token in file_stem:
                    score += 1.5

            # 2. 심볼명 매칭
            for cls in sym.classes:
                cls_lower = cls.lower()
                for token in query_tokens:
                    if token == cls_lower:
                        score += 2.0
                    elif token in cls_lower:
                        score += 1.0

            for fn in sym.functions:
                fn_lower = fn.lower()
                for token in query_tokens:
                    if token == fn_lower:
                        score += 2.0
                    elif token in fn_lower:
                        score += 1.0

            # 3. 파일 경로 부분 매칭
            for token in query_tokens:
                if token in path_lower:
                    score += 1.0

            # 4. 임포트 키워드 매칭
            for imp in sym.imports:
                imp_lower = imp.lower()
                for token in query_tokens:
                    if token in imp_lower:
                        score += 0.5
                        break

            if score > 0.5:
                scored.append((score, rel_path, sym))

        # 점수 순 정렬
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, rel_path, sym in scored[:max_files]:
            results.append({
                "file": rel_path,
                "score": round(score, 1),
                "functions": sym.functions[:5],
                "classes": sym.classes[:5],
                "line_count": sym.line_count,
            })

        return results

    def _extract_symbols(
        self, rel_path: str, content: str, ext: str
    ) -> FileSymbols | None:
        """파일 확장자에 따라 심볼을 추출합니다."""
        lines = content.split("\n")
        symbols = FileSymbols(
            file_path=rel_path,
            line_count=len(lines),
            char_count=len(content),
        )

        if ext == ".py":
            self._extract_python_symbols(content, symbols)
        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            self._extract_common_symbols(content, symbols, ext)
            # JS/TS import 추출
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
            self._extract_common_symbols(content, symbols, ext)
        elif ext in (".md",):
            # Markdown: 헤딩 추출
            for match in re.finditer(r"^(#{1,3})\s+(.+)$", content, re.MULTILINE):
                heading = match.group(2).strip()
                if heading:
                    symbols.functions.append(f"§{heading[:40]}")
                    if len(symbols.functions) > 20:
                        break
        elif ext in (".yaml", ".yml", ".json"):
            symbols.line_count = len(lines)
            # 구조 정보는 생략 (설정 파일)
            pass
        elif ext in (".css", ".scss", ".html"):
            self._extract_common_symbols(content, symbols, ext)

        # 최소 내용이 없으면 None
        if not symbols.functions and not symbols.classes and symbols.line_count > 500:
            pass  # 큰 파일도 추적
        elif not symbols.functions and not symbols.classes and symbols.line_count < 5:
            return None  # 빈 파일 제외

        return symbols

    def _extract_python_symbols(self, content: str, symbols: FileSymbols):
        """Python 파일에서 함수/클래스/임포트를 추출합니다."""
        for match in RE_PY_FUNCTION.finditer(content):
            name = match.group(1)
            if name and name not in symbols.functions:
                symbols.functions.append(name)

        for match in RE_PY_CLASS.finditer(content):
            name = match.group(1)
            if name and name not in symbols.classes:
                symbols.classes.append(name)

        # import 추출
        for match in RE_PY_IMPORT.finditer(content):
            from_module = match.group(1)
            imported = match.group(2)
            if from_module:
                # from X import Y, Z → 각각 추출
                for item in re.split(r",\s*", imported):
                    item_clean = item.strip().split(" as ")[0].strip()
                    if item_clean and f"{from_module}.{item_clean}" not in symbols.imports:
                        symbols.imports.append(f"{from_module}.{item_clean}")
                        if len(symbols.imports) > 20:
                            break
            else:
                # import X, Y
                for item in re.split(r",\s*", imported):
                    item_clean = item.strip().split(" as ")[0].strip()
                    if item_clean and item_clean not in symbols.imports:
                        symbols.imports.append(item_clean)
                        if len(symbols.imports) > 20:
                            break

    _RE_FN_MAP = {
        ("js", "jsx", "ts", "tsx"): [_RE_JS_FN, _RE_JS_ARROW],
        ("go",): [_RE_GO_FN],
        ("rs",): [_RE_RS_FN],
        ("java", "kt", "scala"): [_RE_OO_FN],
        ("swift",): [_RE_SWIFT_FN, _RE_OO_FN],
        ("php",): [_RE_PHP_FN],
        ("rb",): [_RE_RB_FN],
        ("c", "cpp", "h", "hpp", "cc", "cxx", "hxx"): [_RE_CPP_EXACT],
        ("css", "scss", "html"): [_RE_OO_FN],  # CSS custom properties, HTML IDs
    }

    # 언어별 키워드 블랙리스트 (false positive 방지)
    _FN_BLACKLIST = {
        "if", "for", "while", "switch", "catch", "return",
        "throw", "else", "do", "try", "finally", "case", "default",
        "break", "continue", "new", "delete", "typeof", "instanceof",
        "import", "export", "yield", "await", "async",
        "this", "super", "null", "undefined", "true", "false",
        "int", "void", "float", "double", "char", "bool", "long", "short",
    }

    def _extract_common_symbols(self, content: str, symbols: FileSymbols, ext: str = ""):
        """언어별 정규식으로 함수/클래스 추출 (false positive 최소화)."""
        # 언어별 정규식 선택
        patterns = []
        for exts, pats in self._RE_FN_MAP.items():
            if ext and ext.lstrip(".") in exts:
                patterns.extend(pats)
                break
        else:
            # 매칭되는 언어 없음 → 모든 패턴 시도 (기존 호환)
            patterns = [
                _RE_JS_FN, _RE_GO_FN, _RE_RS_FN,
                _RE_OO_FN, _RE_SWIFT_FN, _RE_PHP_FN, _RE_RB_FN,
            ]

        for pattern in patterns:
            for match in pattern.finditer(content):
                name = match.group(1)
                if name and name not in self._FN_BLACKLIST:
                    if name not in symbols.functions:
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

    def stats(self) -> dict[str, Any]:
        """인덱서 통계 정보를 반환합니다."""
        total_classes = sum(len(s.classes) for s in self._symbols.values())
        total_functions = sum(len(s.functions) for s in self._symbols.values())
        total_lines = sum(s.line_count for s in self._symbols.values())

        return {
            "files_indexed": len(self._symbols),
            "total_classes": total_classes,
            "total_functions": total_functions,
            "total_lines": total_lines,
            "tree_size_kb": round(len(self._tree_cache) / 1024, 1),
        }
