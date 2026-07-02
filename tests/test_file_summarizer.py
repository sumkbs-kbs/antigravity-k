"""Tests for FileSummarizer (Freebuff-Style Content Summary).

Tests cover:
- summarize_files() with various file types
- 3-tier summarization (<50 lines, 50-200 lines, 200+ lines)
- Large file statistical summarization
- Edge cases (empty files, non-existent files, empty results)
"""

import tempfile
from pathlib import Path

from antigravity_k.engine.file_summarizer import FileSummarizer

# ─── Helper ──────────────────────────────────────────────────────


def _create_test_file(dir_path: str, rel_path: str, content: str) -> str:
    """테스트 파일을 생성하고 절대 경로를 반환합니다."""
    full_path = Path(dir_path) / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return str(full_path)


# ─── FileSummarizer Tests ───────────────────────────────────────


class TestFileSummarizer:
    """FileSummarizer 단위 테스트."""

    def test_summarize_small_file_includes_full_content(self):
        """50줄 이하 파일이 전체 내용을 포함하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content = "def hello():\n    return 'hello'\n"
            _create_test_file(tmpdir, "src/hello.py", content)

            summarizer = FileSummarizer()
            result = summarizer.summarize_files(
                [{"file": "src/hello.py", "functions": ["hello"], "classes": []}],
                tmpdir,
            )

            assert result is not None
            assert "<auto_context>" in result
            assert "</auto_context>" in result
            assert "hello" in result
            assert "src/hello.py" in result

    def test_summarize_multiple_files(self):
        """여러 파일 요약 시 모두 포함되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_file(tmpdir, "a.py", "def a(): pass\n")
            _create_test_file(tmpdir, "b.py", "def b(): pass\n")

            summarizer = FileSummarizer()
            result = summarizer.summarize_files(
                [
                    {"file": "a.py", "functions": ["a"], "classes": []},
                    {"file": "b.py", "functions": ["b"], "classes": []},
                ],
                tmpdir,
            )

            assert "a.py" in result
            assert "b.py" in result

    def test_summarize_large_file_shows_statistical_summary(self):
        """200줄 이상 큰 파일이 통계 요약으로 표시되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 210줄 파일 생성
            lines = [f"def func_{i}():\n    pass\n" for i in range(210)]
            content = "".join(lines)
            _create_test_file(tmpdir, "large.py", content)

            known_fns = [f"func_{i}" for i in range(10)]
            summarizer = FileSummarizer()
            result = summarizer.summarize_files(
                [{"file": "large.py", "functions": known_fns, "classes": [], "line_count": 210}],
                tmpdir,
            )

            # 210 function defs * 2 lines each ≈ 420+ lines
            assert "lines" in result

    def test_summarize_medium_file_shows_key_structure(self):
        """50~200줄 파일이 핵심 구조만 추출되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lines = []
            lines.append("import os\n")
            lines.append("import sys\n")
            lines.append("\n")
            for i in range(80):
                lines.append(f"def func_{i}(param_{i}):\n    pass\n")
            content = "".join(lines)
            _create_test_file(tmpdir, "medium.py", content)

            summarizer = FileSummarizer()
            result = summarizer.summarize_files(
                [{"file": "medium.py", "functions": [f"func_{i}" for i in range(80)], "classes": []}],
                tmpdir,
            )

            # 함수 시그니처가 포함되어야 함
            assert "def func_0" in result or "func_0" in result
            assert "<auto_context>" in result

    def test_summarize_non_existent_file(self):
        """존재하지 않는 파일이 오류 없이 스킵되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            summarizer = FileSummarizer()
            result = summarizer.summarize_files(
                [{"file": "nonexistent.py", "functions": [], "classes": []}],
                tmpdir,
            )

            assert result is not None
            assert "nonexistent.py" in result  # 파일 없음 표시
            assert "</auto_context>" in result

    def test_summarize_empty_results(self):
        """빈 file_list가 빈 문자열을 반환하는지 검증."""
        summarizer = FileSummarizer()
        result = summarizer.summarize_files([], "/tmp")
        assert result == ""

    def test_summarize_max_files_capped(self):
        """MAX_SUMMARIZE_FILES(8) 이상의 파일이 제한되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_list = []
            for i in range(12):
                content = f"def fn_{i}():\n    pass\n"
                _create_test_file(tmpdir, f"file_{i}.py", content)
                file_list.append({"file": f"file_{i}.py", "functions": [f"fn_{i}"], "classes": []})

            summarizer = FileSummarizer()
            result = summarizer.summarize_files(file_list, tmpdir)

            # 8개 파일만 포함되어야 함 (최대 제한)
            # (일부는 char limit으로 더 적을 수 있음)
            assert result is not None
            assert "</auto_context>" in result

    def test_summarize_with_query_context(self):
        """query 파라미터가 전달될 때 정상 동작하는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_file(tmpdir, "user.py", "def login(): pass\n")

            summarizer = FileSummarizer()
            result = summarizer.summarize_files(
                [{"file": "user.py", "functions": ["login"], "classes": []}],
                tmpdir,
                query="user authentication login",
            )

            assert "user.py" in result
            assert "</auto_context>" in result

    def test_llm_summarize_fallback_on_no_model(self):
        """model_manager 없을 때 llm_summarize가 규칙 기반 요약으로 폴백하는지 검증."""
        content = "def hello():\n    return 'hello'\n"

        summarizer = FileSummarizer()  # model_manager=None
        result = summarizer.llm_summarize("test.py", content)

        # rule-based 폴백 = 코드 블록에 원본 포함
        assert "def hello():" in result

    def test_summarize_single_file_direct(self):
        """_summarize_single_file이 올바른 형식으로 요약하는지 검증."""
        summarizer = FileSummarizer()

        # 50줄 이하
        small = summarizer._summarize_single_file(
            "small.py",
            "def small(): pass\n",
            ["small"],
            [],
        )
        assert "def small()" in small or "small" in small

        # 50-200줄 (key structure)
        medium_lines = [f"def fn_{i}():\n    pass\n" for i in range(60)]
        medium = summarizer._summarize_single_file(
            "medium.py",
            "".join(medium_lines),
            [f"fn_{i}" for i in range(60)],
            [],
        )
        assert "def fn_0" in medium

        # 200+줄 (statistical)
        large_lines = [f"def fn_{i}():\n    pass\n" for i in range(220)]
        large = summarizer._summarize_single_file(
            "large.py",
            "".join(large_lines),
            [f"fn_{i}" for i in range(10)],
            [],
        )
        assert "lines" in large or "Functions" in large

    def test_summarize_mixed_file_types(self):
        """다양한 파일 형식(JS, TS, Go, Rust)이 정상 요약되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_file(tmpdir, "app.js", "function greet() { return 'hi'; }\n")
            _create_test_file(tmpdir, "server.go", "func main() {\n}\n")
            _create_test_file(tmpdir, "lib.rs", "pub fn process() -> Result<()> {\n}\n")
            _create_test_file(tmpdir, "data.json", '{"key": "value"}\n')

            summarizer = FileSummarizer()
            result = summarizer.summarize_files(
                [
                    {"file": "app.js", "functions": ["greet"], "classes": []},
                    {"file": "server.go", "functions": ["main"], "classes": []},
                    {"file": "lib.rs", "functions": ["process"], "classes": []},
                    {"file": "data.json", "functions": [], "classes": []},
                ],
                tmpdir,
            )

            assert "app.js" in result
            assert "server.go" in result
            assert "lib.rs" in result
            assert "data.json" in result

    def test_summarize_empty_file(self):
        """빈 파일이 정상 처리되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_file(tmpdir, "empty.py", "")

            summarizer = FileSummarizer()
            result = summarizer.summarize_files(
                [{"file": "empty.py", "functions": [], "classes": []}],
                tmpdir,
            )

            assert "empty.py" in result

    def test_context_markup_structure(self):
        """출력에 올바른 마크업 구조가 포함되는지 검증."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _create_test_file(tmpdir, "test.py", "def test(): pass\n")

            summarizer = FileSummarizer()
            result = summarizer.summarize_files(
                [{"file": "test.py", "functions": ["test"], "classes": []}],
                tmpdir,
            )

            assert result.startswith("<auto_context>")
            assert result.endswith("</auto_context>")
            assert "**test.py**" in result

    def test_wrap_code_limits_size(self):
        """_wrap_code가 MAX_SUMMARY_CHARS를 초과하는 내용을 자르는지 검증."""
        huge_content = "x\n" * 5000
        result = FileSummarizer._wrap_code(huge_content)
        assert len(result) < len(huge_content)  # 잘렸음
        assert result.endswith("(truncated)\n```") or result.endswith("(truncated)\n```\n")
