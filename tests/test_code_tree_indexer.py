"""Tests for CodeTreeIndexer (Freebuff-Style Proactive Context).

Tests cover:
- build_tree() with Python, JS, Go, Rust files
- search() for keyword-based file discovery
- stats() for index statistics
- Language-specific regex patterns
- Edge cases (empty files, empty dirs, hidden dirs)
"""

import tempfile
from pathlib import Path

from antigravity_k.engine.code_tree_indexer import (
    _RE_GO_FN,
    _RE_JS_ARROW,
    _RE_JS_FN,
    _RE_OO_FN,
    _RE_PHP_FN,
    _RE_RB_FN,
    _RE_RS_FN,
    IGNORE_DIRS,
    RE_COMMON_CLASS,
    RE_INTERFACE,
    CodeTreeIndexer,
)

# ─── Helper ──────────────────────────────────────────────────────


def _create_test_project(tmpdir: str, extra_files: dict[str, str] | None = None):
    """테스트 프로젝트 디렉토리를 생성합니다."""
    root = Path(tmpdir)
    pkg = root / "mypkg"
    pkg.mkdir(parents=True)

    files = {
        "mypkg/__init__.py": "",
        "mypkg/utils.py": (
            "import os\nimport json\n\n"
            "def helper():\n    return 42\n\n"
            "class UtilTools:\n"
            "    def process(self, data):\n        return data\n"
        ),
        "mypkg/main.py": (
            "from mypkg.utils import helper, UtilTools\n\n"
            "async def run_app():\n"
            '    return "hello"\n\n'
            "class App:\n"
            "    async def start(self):\n"
            "        pass\n"
        ),
        "README.md": "# Test Project\n\nThis is a test.\n",
        "config.yaml": "key: value\n",
    }
    if extra_files:
        files.update(extra_files)

    for rel_path, content in files.items():
        full_path = root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    return str(root)


# ─── CodeTreeIndexer Tests ──────────────────────────────────────


class TestCodeTreeIndexer:
    """CodeTreeIndexer 단위 테스트."""

    def test_build_tree_creates_tree_string(self):
        """build_tree()가 압축된 코드 트리 문자열을 생성하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = _create_test_project(tmpdir)
            indexer = CodeTreeIndexer(project_root)

            tree = indexer.build_tree()

            assert isinstance(tree, str)
            assert len(tree) > 0
            # Python 파일들이 트리에 포함되어야 함
            assert "mypkg/utils.py" in tree
            assert "mypkg/main.py" in tree
            # 함수/클래스 심볼이 포함되어야 함
            assert "fn:" in tree or "cls:" in tree

    def test_build_tree_caches_and_reuses(self):
        """build_tree()가 변경 없을 때 캐시를 재사용하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = _create_test_project(tmpdir)
            indexer = CodeTreeIndexer(project_root)

            tree1 = indexer.build_tree()
            tree2 = indexer.build_tree()  # 캐시
            tree3 = indexer.build_tree(force=True)  # 강제 재구축

            assert tree1 == tree2  # 캐시 = 동일
            assert tree3 is not None  # 강제 재구축 성공

    def test_build_tree_ignores_hidden_dirs(self):
        """build_tree()가 .git 등 숨김 디렉토리를 스킵하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("dummy")
            (root / ".venv").mkdir()
            (root / ".venv" / "activate").write_text("dummy")
            # 실제 소스 파일
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("def foo(): pass\n")

            indexer = CodeTreeIndexer(str(root))
            tree = indexer.build_tree()

            # .git, .venv 파일이 인덱싱되지 않아야 함
            assert ".git" not in tree
            assert ".venv" not in tree
            # 실제 소스 파일은 인덱싱되어야 함
            assert "src/app.py" in tree
            assert "fn:foo" in tree or "foo" in tree

    def test_build_tree_ignores_node_modules(self):
        """IGNORE_DIRS의 디렉토리가 제외되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "lodash.js").write_text("function map() {}\n")
            (root / "src").mkdir()
            (root / "src" / "index.js").write_text("function greet() {}\n")

            indexer = CodeTreeIndexer(str(root))
            tree = indexer.build_tree()

            assert "node_modules" not in tree
            assert "src/index.js" in tree

    def test_search_returns_relevant_files(self):
        """search()가 쿼리와 관련된 파일을 반환하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = _create_test_project(tmpdir)
            indexer = CodeTreeIndexer(project_root)
            indexer.build_tree()

            # 'helper' 함수 검색
            results = indexer.search("helper", max_files=5)

            assert len(results) > 0
            result_paths = [r["file"] for r in results]
            assert "mypkg/utils.py" in result_paths  # helper 함수가 있는 파일

    def test_search_ranks_by_relevance(self):
        """search()가 관련성 높은 파일을 먼저 반환하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = _create_test_project(tmpdir)
            indexer = CodeTreeIndexer(project_root)
            indexer.build_tree()

            # 'app' 검색 → main.py가 관련
            results = indexer.search("app")

            assert len(results) > 0
            # 첫 번째 결과(가장 높은 점수)는 비어있지 않아야 함
            assert results[0]["score"] > 0

    def test_search_empty_query(self):
        """search()가 빈 쿼리에 대해 빈 결과를 반환하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = _create_test_project(tmpdir)
            indexer = CodeTreeIndexer(project_root)
            indexer.build_tree()

            results = indexer.search("")
            assert len(results) == 0

    def test_search_no_match(self):
        """search()가 매칭 없는 쿼리에 대해 빈 결과를 반환하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = _create_test_project(tmpdir)
            indexer = CodeTreeIndexer(project_root)
            indexer.build_tree()

            results = indexer.search("xyznonexistentkeyword12345")
            assert len(results) == 0

    def test_stats_returns_correct_counts(self):
        """stats()가 올바른 통계를 반환하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = _create_test_project(tmpdir)
            indexer = CodeTreeIndexer(project_root)
            indexer.build_tree()

            stats = indexer.stats()

            assert stats["files_indexed"] >= 3  # utils.py, main.py, README.md
            assert stats["total_functions"] >= 3  # helper, run_app, process, start
            assert stats["total_classes"] >= 2  # UtilTools, App
            assert stats["tree_size_kb"] > 0
            assert stats["total_lines"] > 0

    def test_python_symbol_extraction(self):
        """Python 파일에서 함수/클래스/임포트가 올바르게 추출되는지 검증."""
        content = (
            "import os\n"
            "from typing import Optional\n\n"
            "def my_function():\n    pass\n\n"
            "class MyClass:\n"
            "    def method(self):\n        pass\n\n"
            "async def async_fn():\n    pass\n"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "test.py").write_text(content)
            indexer = CodeTreeIndexer(str(root))
            indexer.build_tree()
            stats = indexer.stats()

            # my_function, method(MyClass의 메서드), async_fn = 3
            # method는 PyFunction과 ClassDef 내부 Func 둘 다 매칭될 수 있음
            assert stats["total_functions"] >= 2  # my_function, async_fn
            assert stats["total_classes"] >= 1  # MyClass

    def test_js_function_extraction(self):
        """JS/TS 함수가 올바르게 추출되는지 검증."""
        content = (
            "function greet(name) { return `Hello ${name}`; }\n"
            "export function format(data) { return data; }\n"
            "async function fetchData() { return await api.get(); }\n"
            "const handler = (req, res) => { res.send(); };\n"
        )

        # _RE_JS_FN 테스트
        matches = [m.group(1) for m in _RE_JS_FN.finditer(content)]
        assert "greet" in matches
        assert "format" in matches
        assert "fetchData" in matches

        # _RE_JS_ARROW 테스트 (arrow function)
        arrow_matches = [m.group(1) for m in _RE_JS_ARROW.finditer(content)]
        assert "handler" in arrow_matches

    def test_go_function_extraction(self):
        """Go 함수가 올바르게 추출되는지 검증."""
        content = (
            "func main() {\n}\n"
            "func (s *Service) Handle(ctx context.Context) error {\n}\n"
            "func processData(input string) (int, error) {\n}\n"
        )

        matches = [m.group(1) for m in _RE_GO_FN.finditer(content)]
        assert "main" in matches
        assert "Handle" in matches
        assert "processData" in matches

    def test_rust_function_extraction(self):
        """Rust 함수가 올바르게 추출되는지 검증."""
        content = "fn main() {\n}\npub fn process() -> Result<()> {\n}\npub async fn fetch_data() -> String {\n}\n"

        matches = [m.group(1) for m in _RE_RS_FN.finditer(content)]
        assert "main" in matches
        assert "process" in matches
        assert "fetch_data" in matches

    def test_php_function_extraction(self):
        """PHP 함수가 올바르게 추출되는지 검증."""
        content = "<?php\nfunction helper() {}\nfunction process() {}\npublic function validate() {}\n"

        matches = [m.group(1) for m in _RE_PHP_FN.finditer(content)]
        assert "helper" in matches
        assert "process" in matches
        assert "validate" in matches

    def test_ruby_function_extraction(self):
        """Ruby 함수가 올바르게 추출되는지 검증."""
        content = "def hello\nend\ndef self.greet\nend\ndef process_data!\nend\n"

        matches = [m.group(1) for m in _RE_RB_FN.finditer(content)]
        assert "hello" in matches
        assert "greet" in matches
        assert "process_data!" in matches

    def test_class_extraction(self):
        """클래스/인터페이스가 올바르게 추출되는지 검증."""
        content = "class UserModel { }\nexport class ApiService { }\nabstract class BaseProvider { }\n"

        matches = [m.group(1) for m in RE_COMMON_CLASS.finditer(content)]
        assert "UserModel" in matches
        assert "ApiService" in matches
        assert "BaseProvider" in matches

    def test_interface_extraction(self):
        """인터페이스/트레이트가 올바르게 추출되는지 검증."""
        content = "interface UserRepository { }\ntrait Loggable { }\nprotocol DataSource { }\n"

        matches = [m.group(1) for m in RE_INTERFACE.finditer(content)]
        assert "UserRepository" in matches
        assert "Loggable" in matches
        assert "DataSource" in matches

    def test_java_function_extraction(self):
        """Java/Kotlin 함수가 올바르게 추출되는지 검증."""
        content = "public void process() { }\nprivate String getData() { }\nprotected int calculate() { }\n"

        matches = [m.group(1) for m in _RE_OO_FN.finditer(content)]
        assert "process" in matches
        assert "getData" in matches
        assert "calculate" in matches

    def test_arrow_regex_no_false_positive(self):
        """화살표 함수 정규식이 일반 할당을 매칭하지 않는지 검증."""
        content = "const x = 42\nlet y = 'hello'\nvar z = [1, 2, 3]\n"

        matches = [m.group(1) for m in _RE_JS_ARROW.finditer(content)]
        assert len(matches) == 0  # 일반 할당은 매칭되지 않아야 함

    def test_arrow_regex_matches_function_expression(self):
        """화살표 함수 정규식이 실제 함수 표현식만 매칭하는지 검증."""
        content = "const fn1 = function() { }\nconst fn2 = (x) => x * 2\nconst fn3 = async () => { }\n"

        matches = [m.group(1) for m in _RE_JS_ARROW.finditer(content)]
        assert "fn1" in matches
        assert "fn2" in matches
        assert "fn3" in matches

    def test_global_function_with_regex(self):
        """전역 함수 키워드(function, fn, func)가 false positive를 일으키지 않는지 검증."""
        content = (
            "if (condition) {\n"
            "  process(data)\n"  # 일반 호출
            "}\n"
            "for (let i = 0; i < n; i++) {\n"
            "}\n"
            "while (running) {\n"
            "}\n"
            "return result\n"
        )

        # _RE_JS_FN은 'if', 'for', 'while', 'return'을 매칭하지 않아야 함
        matches = [m.group(1) for m in _RE_JS_FN.finditer(content)]
        for keyword in ("if", "for", "while", "return"):
            assert keyword not in matches, f"{keyword} should not be matched by _RE_JS_FN"

    def test_ignore_dirs_config(self):
        """IGNORE_DIRS에 예상 디렉토리가 포함되어 있는지 검증."""
        assert ".git" in IGNORE_DIRS
        assert "node_modules" in IGNORE_DIRS
        assert "__pycache__" in IGNORE_DIRS
        assert ".next" in IGNORE_DIRS
        assert "coverage" in IGNORE_DIRS
        assert ".coverage" in IGNORE_DIRS

    def test_empty_project_returns_empty_tree(self):
        """빈 프로젝트가 빈 트리를 반환하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = CodeTreeIndexer(tmpdir)
            tree = indexer.build_tree()

            assert tree == ""  # 빈 프로젝트

    def test_non_indexable_files_are_skipped(self):
        """인덱싱 불가능한 확장자(.png, .exe 등)가 스킵되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "image.png").write_bytes(b"fake_png")
            (root / "binary.bin").write_bytes(b"\x00\x01\x02")
            (root / "data.csv").write_text("a,b,c\n")
            (root / "code.py").write_text("def foo(): pass\n")

            indexer = CodeTreeIndexer(str(root))
            tree = indexer.build_tree()

            assert "code.py" in tree  # .py는 인덱싱
            # .png, .bin, .csv는 인텍싱되지 않아야 함
            assert "image.png" not in tree
            assert "binary.bin" not in tree
            assert "data.csv" not in tree

    def test_build_tree_detects_new_files(self):
        """파일 추가 후 build_tree(force=True)가 새 파일을 감지하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "original.py").write_text("def existing(): pass\n")
            indexer = CodeTreeIndexer(str(root))
            tree1 = indexer.build_tree()
            assert "original.py" in tree1

            # 새 파일 추가
            (root / "newfile.py").write_text("def new_func(): pass\n")

            # force=True로 재구축
            tree2 = indexer.build_tree(force=True)
            # 새 파일이 감지되어야 함
            assert "newfile.py" in tree2
            assert "new_func" in tree2 or "fn:new_func" in tree2

    def test_get_tree_returns_cached(self):
        """get_tree()가 캐시된 결과를 반환하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = _create_test_project(tmpdir)
            indexer = CodeTreeIndexer(project_root)

            # build_tree 직접 호출 없이 get_tree
            tree = indexer.get_tree()
            assert isinstance(tree, str)
            assert "mypkg/utils.py" in tree
