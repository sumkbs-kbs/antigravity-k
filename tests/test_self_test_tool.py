"""Tests for self_test_tool.py — SelfTestTool.

Tests pure-logic methods (properties, _format_markdown) without
needing Playwright, asyncio, or external dependencies.
"""

from antigravity_k.tools.self_test_tool import SelfTestTool


class TestSelfTestToolInit:
    def test_name(self):
        tool = SelfTestTool()
        assert tool.name == "self_test"

    def test_description(self):
        tool = SelfTestTool()
        assert "테스트" in tool.description
        assert "Playwright" in tool.description

    def test_parameters_schema(self):
        tool = SelfTestTool()
        schema = tool.parameters_schema
        assert "scope" in schema["properties"]
        assert "verbose" in schema["properties"]
        assert "run_hygiene_scan" in schema["properties"]
        assert schema["properties"]["scope"]["enum"] == ["full", "api_only", "ui_only"]


class TestFormatMarkdown:
    """Tests for SelfTestTool._format_markdown pure string formatting."""

    def test_full_report_with_all_statuses(self):
        tool = SelfTestTool()
        report = {
            "total": 10,
            "passed": 7,
            "healed": 1,
            "failed": 1,
            "skipped": 1,
            "pass_rate": "70%",
            "duration_ms": 1500,
            "hygiene_issues": [],
            "results": [
                {"intent_id": "TEST-001", "status": "passed", "message": "Login works", "duration_ms": 200},
                {"intent_id": "TEST-002", "status": "failed", "message": "Logout fails", "duration_ms": 500},
                {
                    "intent_id": "TEST-003",
                    "status": "healed",
                    "message": "Recovered automatically",
                    "duration_ms": 300,
                    "healed": True,
                    "heal_details": "Restarted service",
                },
                {"intent_id": "TEST-004", "status": "skipped", "message": "Not applicable", "duration_ms": 0},
            ],
        }
        md = tool._format_markdown(report)
        assert "# 🧪 Antigravity-K Self-Test Report" in md
        assert "| 총 테스트 | 10 |" in md
        assert "| ✅ 통과 | 7 |" in md
        assert "| 🔧 자가치유 | 1 |" in md
        assert "| ❌ 실패 | 1 |" in md
        assert "| ⏭ 스킵 | 1 |" in md
        assert "| 합격률 | 70% |" in md
        assert "TEST-001" in md
        assert "Login works" in md
        assert "TEST-002" in md
        assert "TEST-003" in md
        assert "TEST-004" in md
        assert "Restarted service" in md
        assert "✅ 프로덕션 코드 내 명명 규칙" in md

    def test_empty_report(self):
        tool = SelfTestTool()
        report = {
            "total": 0,
            "passed": 0,
            "healed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "0%",
            "duration_ms": 0,
            "hygiene_issues": [],
            "results": [],
        }
        md = tool._format_markdown(report)
        assert "| 총 테스트 | 0 |" in md
        assert "| 합격률 | 0% |" in md
        assert "| 소요시간 | 0ms |" in md
        assert "명명 규칙" in md  # hygiene scan result

    def test_all_passed_report(self):
        tool = SelfTestTool()
        report = {
            "total": 5,
            "passed": 5,
            "healed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "100%",
            "duration_ms": 500,
            "hygiene_issues": [],
            "results": [
                {"intent_id": "T1", "status": "passed", "message": "OK", "duration_ms": 100},
            ],
        }
        md = tool._format_markdown(report)
        assert "| 총 테스트 | 5 |" in md
        assert "| ✅ 통과 | 5 |" in md
        assert "| ❌ 실패 | 0 |" in md
        assert "| 합격률 | 100% |" in md

    def test_all_failed_report(self):
        tool = SelfTestTool()
        report = {
            "total": 3,
            "passed": 0,
            "healed": 0,
            "failed": 3,
            "skipped": 0,
            "pass_rate": "0%",
            "duration_ms": 1000,
            "hygiene_issues": [],
            "results": [
                {"intent_id": "F1", "status": "failed", "message": "Crash", "duration_ms": 300},
            ],
        }
        md = tool._format_markdown(report)
        assert "| 총 테스트 | 3 |" in md
        assert "| ❌ 실패 | 3 |" in md
        assert "| 합격률 | 0% |" in md
        assert "F1" in md

    def test_report_with_hygiene_issues(self):
        tool = SelfTestTool()
        report = {
            "total": 2,
            "passed": 2,
            "healed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "100%",
            "duration_ms": 200,
            "hygiene_issues": ["src/test_bad_file.py", "src/bad/test_helpers.py"],
            "results": [],
        }
        md = tool._format_markdown(report)
        assert "> [!WARNING]" in md
        assert "test_bad_file.py" in md
        assert "test_helpers.py" in md
        assert "파일명 충돌 위험" in md

    def test_healed_without_details(self):
        """healed=True but no heal_details should not crash."""
        tool = SelfTestTool()
        report = {
            "total": 1,
            "passed": 0,
            "healed": 1,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "0%",
            "duration_ms": 100,
            "hygiene_issues": [],
            "results": [
                {"intent_id": "H1", "status": "healed", "message": "Auto-fixed", "duration_ms": 50, "healed": True},
            ],
        }
        md = tool._format_markdown(report)
        assert "H1" in md
        assert "Auto-fixed" in md

    def test_numeric_duration_formatting(self):
        """Duration should be formatted with 0 decimal places."""
        tool = SelfTestTool()
        report = {
            "total": 1,
            "passed": 1,
            "healed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "100%",
            "duration_ms": 1234.56,
            "hygiene_issues": [],
            "results": [
                {"intent_id": "T", "status": "passed", "message": "OK", "duration_ms": 250.7},
            ],
        }
        md = tool._format_markdown(report)
        assert "1235ms" in md or "1234ms" in md

    def test_multiple_hygiene_issues(self):
        """Multiple hygiene issues should each appear as list items."""
        tool = SelfTestTool()
        issues = [f"src/module/test_{i}.py" for i in range(3)]
        report = {
            "total": 0,
            "passed": 0,
            "healed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "0%",
            "duration_ms": 0,
            "hygiene_issues": issues,
            "results": [],
        }
        md = tool._format_markdown(report)
        for issue in issues:
            assert issue in md

    def test_minimal_report(self):
        """A report with only required keys should not crash."""
        tool = SelfTestTool()
        report = {
            "total": 0,
            "passed": 0,
            "healed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "0%",
            "duration_ms": 0,
            "hygiene_issues": [],
            "results": [],
        }
        md = tool._format_markdown(report)
        assert isinstance(md, str)
        assert len(md) > 0

    def test_report_with_unknown_status(self):
        """Unknown status should use ❓ icon."""
        tool = SelfTestTool()
        report = {
            "total": 1,
            "passed": 0,
            "healed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "0%",
            "duration_ms": 0,
            "hygiene_issues": [],
            "results": [
                {"intent_id": "U1", "status": "unknown_status", "message": "Unrecognized", "duration_ms": 0},
            ],
        }
        md = tool._format_markdown(report)
        assert "U1" in md
        assert "❓" in md

    def test_report_without_results_key(self):
        """Missing 'results' key should not crash."""
        tool = SelfTestTool()
        report = {
            "total": 0,
            "passed": 0,
            "healed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "0%",
            "duration_ms": 0,
            "hygiene_issues": [],
        }
        md = tool._format_markdown(report)
        assert isinstance(md, str)
        assert "## 상세 결과" in md
