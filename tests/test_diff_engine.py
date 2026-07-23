"""DiffApplyEngine 단위 테스트 (P0-1).

apply_patch 포맷 파싱, hunk 매칭, 퍼지 폴백, 신규/삭제 파일,
다중 hunk, 매치 실패 에러 처리를 검증합니다.
"""

from antigravity_k.engine.diff_engine import DiffApplyEngine, FilePatch, Hunk
from antigravity_k.tools.file_tools import ApplyPatchTool


class TestApplyPatchParsing:
    """apply_patch 포맷 파싱 검증."""

    def test_parse_single_hunk_update(self):
        """단일 hunk 업데이트 파싱."""
        engine = DiffApplyEngine()
        text = """*** Begin Patch
*** Update File: src/app.py
@@ def hello():
-    print('world')
+    print('hello')
*** End Patch"""
        patches = engine.parse_apply_patch(text)

        assert len(patches) == 1
        assert patches[0].file_path == "src/app.py"
        assert not patches[0].is_new_file
        assert len(patches[0].hunks) == 1
        hunk = patches[0].hunks[0]
        assert hunk.context_before == ["def hello():"]
        assert hunk.removals == ["    print('world')"]
        assert hunk.additions == ["    print('hello')"]

    def test_parse_new_file(self):
        """신규 파일 추가 파싱."""
        engine = DiffApplyEngine()
        text = """*** Begin Patch
*** Add File: new.py
+def func():
+    return 42
*** End Patch"""
        patches = engine.parse_apply_patch(text)

        assert len(patches) == 1
        assert patches[0].is_new_file
        assert patches[0].file_path == "new.py"
        assert patches[0].new_file_content == ["def func():", "    return 42"]

    def test_parse_delete_file(self):
        """파일 삭제 파싱."""
        engine = DiffApplyEngine()
        text = """*** Begin Patch
*** Delete File: old.py
*** End Patch"""
        patches = engine.parse_apply_patch(text)

        assert len(patches) == 1
        assert patches[0].is_delete_file
        assert patches[0].file_path == "old.py"

    def test_parse_multi_file(self):
        """다중 파일 패치 파싱."""
        engine = DiffApplyEngine()
        text = """*** Begin Patch
*** Update File: a.py
@@ x = 1
-x = 1
+x = 2
*** Update File: b.py
@@ y = 3
-y = 3
+y = 4
*** End Patch"""
        patches = engine.parse_apply_patch(text)

        assert len(patches) == 2
        assert patches[0].file_path == "a.py"
        assert patches[1].file_path == "b.py"

    def test_parse_pure_addition_hunk(self):
        """제거 없이 추가만 하는 hunk."""
        engine = DiffApplyEngine()
        text = """*** Begin Patch
*** Update File: app.py
@@ def hello():
+    return True
*** End Patch"""
        patches = engine.parse_apply_patch(text)

        hunk = patches[0].hunks[0]
        assert hunk.is_pure_addition
        assert not hunk.removals
        assert hunk.additions == ["    return True"]


class TestHunkProperties:
    """Hunk 속성 검증."""

    def test_old_block_new_block(self):
        """old_block과 new_block 계산."""
        hunk = Hunk(
            context_before=["line1", "line2"],
            removals=["old_line"],
            additions=["new_line"],
            context_after=["line3"],
        )
        assert hunk.old_block == ["line1", "line2", "old_line", "line3"]
        assert hunk.new_block == ["line1", "line2", "new_line", "line3"]

    def test_is_pure_addition_removal(self):
        """순수 추가/제거 판별."""
        add_hunk = Hunk(additions=["x"])
        assert add_hunk.is_pure_addition
        assert not add_hunk.is_pure_removal

        del_hunk = Hunk(removals=["x"])
        assert del_hunk.is_pure_removal
        assert not del_hunk.is_pure_addition


class TestApplyPatch:
    """패치 적용 검증."""

    def test_apply_exact_match(self):
        """정확 매칭 적용."""
        engine = DiffApplyEngine()
        original = "def hello():\n    print('world')\n    return True\n"
        patch = FilePatch(
            file_path="test.py",
            hunks=[
                Hunk(
                    context_before=["def hello():"],
                    removals=["    print('world')"],
                    additions=["    print('hello')"],
                )
            ],
        )

        result = engine.apply_patch(patch, original)

        assert result.success
        assert "print('hello')" in result.new_content
        assert "print('world')" not in result.new_content
        assert result.hunks_applied == 1
        assert not result.is_fuzzy

    def test_apply_fuzzy_match_whitespace(self):
        """공백 차이 퍼지 매칭."""
        engine = DiffApplyEngine()
        # 원본은 4스페이스, 패치는 탭 또는 다른 들여쓰기
        original = "def f():\n    return 1\n"
        patch = FilePatch(
            file_path="test.py",
            hunks=[
                Hunk(
                    context_before=["def f():"],
                    removals=["  return 1"],  # 2스페이스 (원본은 4)
                    additions=["  return 2"],
                )
            ],
        )

        result = engine.apply_patch(patch, original)

        assert result.success
        assert result.is_fuzzy
        assert "return 2" in result.new_content

    def test_apply_multi_hunk(self):
        """다중 hunk 순차 적용."""
        engine = DiffApplyEngine()
        original = "a = 1\nb = 2\nc = 3\nd = 4\n"
        patch = FilePatch(
            file_path="test.py",
            hunks=[
                Hunk(
                    context_before=["a = 1"],
                    removals=["a = 1"],
                    additions=["a = 10"],
                ),
                Hunk(
                    context_before=["c = 3"],
                    removals=["c = 3"],
                    additions=["c = 30"],
                ),
            ],
        )

        result = engine.apply_patch(patch, original)

        assert result.success
        assert result.hunks_applied == 2
        assert "a = 10" in result.new_content
        assert "b = 2" in result.new_content
        assert "c = 30" in result.new_content
        assert "d = 4" in result.new_content

    def test_apply_pure_addition(self):
        """순수 추가 hunk 적용."""
        engine = DiffApplyEngine()
        original = "line1\nline2\n"
        patch = FilePatch(
            file_path="test.py",
            hunks=[
                Hunk(
                    context_before=["line1"],
                    additions=["inserted"],
                )
            ],
        )

        result = engine.apply_patch(patch, original)

        assert result.success
        lines = result.new_content.split("\n")
        assert "inserted" in lines
        assert lines.index("inserted") > lines.index("line1")

    def test_apply_match_failure_returns_error(self):
        """매치 실패 시 명확한 에러."""
        engine = DiffApplyEngine()
        original = "completely different content\n"
        patch = FilePatch(
            file_path="test.py",
            hunks=[
                Hunk(
                    context_before=["def nonexistent():"],
                    removals=["    pass"],
                    additions=["    return True"],
                )
            ],
        )

        result = engine.apply_patch(patch, original)

        assert not result.success
        assert result.error
        assert result.hunks_applied == 0
        assert result.hunks_total == 1

    def test_apply_preserves_trailing_newline(self):
        """원본의 후행 줄바꿈 보존."""
        engine = DiffApplyEngine()
        original = "x = 1\n"
        patch = FilePatch(
            file_path="test.py",
            hunks=[
                Hunk(
                    context_before=["x = 1"],
                    removals=["x = 1"],
                    additions=["x = 2"],
                )
            ],
        )

        result = engine.apply_patch(patch, original)

        assert result.success
        assert result.new_content.endswith("\n")


class TestApplyPatchTool:
    """ApplyPatchTool 통합 검증."""

    def test_tool_properties(self):
        """도구 속성 검증."""
        tool = ApplyPatchTool()
        assert tool.name == "apply_patch"
        assert "patch" in tool.parameters_schema["properties"]
        assert tool.parameters_schema["required"] == ["patch"]

    def test_tool_empty_patch_error(self):
        """빈 패치 에러."""
        tool = ApplyPatchTool()
        result = tool.execute(patch="")
        assert "Error" in result or "empty" in result.lower()

    def test_tool_update_existing_file(self, tmp_path):
        """기존 파일 업데이트."""
        test_file = tmp_path / "target.py"
        test_file.write_text("x = 1\ny = 2\n")

        tool = ApplyPatchTool()
        patch_text = f"""*** Begin Patch
*** Update File: {test_file}
@@ x = 1
-x = 1
+x = 10
*** End Patch"""

        result = tool.execute(patch=patch_text)

        assert "OK" in result
        assert "x = 10" in test_file.read_text()
        assert "y = 2" in test_file.read_text()

    def test_tool_create_new_file(self, tmp_path):
        """신규 파일 생성."""
        new_file = tmp_path / "created.py"

        tool = ApplyPatchTool()
        patch_text = f"""*** Begin Patch
*** Add File: {new_file}
+def new_func():
+    return 42
*** End Patch"""

        result = tool.execute(patch=patch_text)

        assert "CREATED" in result
        assert new_file.exists()
        content = new_file.read_text()
        assert "def new_func()" in content
        assert "return 42" in content

    def test_tool_multi_file_operations(self, tmp_path):
        """다중 파일 작업 (업데이트 + 생성)."""
        existing = tmp_path / "existing.py"
        existing.write_text("a = 1\n")
        new_file = tmp_path / "new.py"

        tool = ApplyPatchTool()
        patch_text = f"""*** Begin Patch
*** Update File: {existing}
@@ a = 1
-a = 1
+a = 100
*** Add File: {new_file}
+def foo():
+    pass
*** End Patch"""

        result = tool.execute(patch=patch_text)

        assert "2/2" in result
        assert "a = 100" in existing.read_text()
        assert new_file.exists()

    def test_tool_missing_file_reports_error(self, tmp_path):
        """존재하지 않는 파일 에러 보고."""
        missing = tmp_path / "nonexistent.py"

        tool = ApplyPatchTool()
        patch_text = f"""*** Begin Patch
*** Update File: {missing}
@@ anything
-old
+new
*** End Patch"""

        result = tool.execute(patch=patch_text)

        assert "FAIL" in result or "ERROR" in result
