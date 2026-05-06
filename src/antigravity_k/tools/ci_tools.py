import subprocess
import os
import logging
from typing import Any, Dict, List, Optional
from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)


class TestRunnerTool(BaseTool):
    """
    자동 테스트 프레임워크 감지 + 구조화된 결과 파싱.

    자동화 기능:
    - 프로젝트 루트의 package.json, pyproject.toml, Makefile 등을 분석하여 테스트 명령 자동 감지
    - 테스트 결과를 JSON 구조로 파싱 (passed/failed/error counts)
    - auto_detect=true 시 커맨드 없이도 실행 가능
    """

    category = ToolCategory.CODE_EXEC
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.MEDIUM
    icon = "🧪"
    tags = ["test", "qa", "verify", "execute", "automation"]

    def __init__(self):
        super().__init__()
        self._name = "run_tests"
        self._description = (
            "Executes a test suite. If no command is provided, auto-detects the test "
            "framework from project files (package.json, pyproject.toml, Makefile, etc.)."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The test command (e.g., 'pytest', 'npm test'). If omitted, auto-detects.",
                },
                "path": {
                    "type": "string",
                    "description": "Project root path for auto-detection.",
                    "default": ".",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Maximum time to allow the test to run.",
                    "default": 120,
                },
                "file_filter": {
                    "type": "string",
                    "description": "Run tests only for a specific file or pattern.",
                    "default": "",
                },
            },
            "required": [],
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return self._schema

    def _detect_test_framework(self, path: str) -> Optional[str]:
        """프로젝트 파일을 분석하여 테스트 프레임워크와 명령을 자동 감지합니다."""
        detections = [
            # (파일, 조건, 명령)
            ("package.json", lambda c: "jest" in c or '"test"' in c, "npm test"),
            ("package.json", lambda c: "vitest" in c, "npx vitest run"),
            (
                "pyproject.toml",
                lambda c: "pytest" in c,
                "python -m pytest -v --tb=short",
            ),
            ("pytest.ini", lambda _: True, "python -m pytest -v --tb=short"),
            ("setup.py", lambda _: True, "python -m pytest -v --tb=short"),
            ("Makefile", lambda c: "test:" in c, "make test"),
            ("Cargo.toml", lambda _: True, "cargo test"),
            ("go.mod", lambda _: True, "go test ./..."),
            ("mix.exs", lambda _: True, "mix test"),
            ("Gemfile", lambda c: "rspec" in c, "bundle exec rspec"),
        ]

        for filename, condition, command in detections:
            filepath = os.path.join(path, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if condition(content):
                        logger.info(
                            f"Auto-detected test framework: {command} (from {filename})"
                        )
                        return command
                except Exception:
                    continue

        return None

    def _parse_test_result(self, output: str, returncode: int) -> Dict[str, Any]:
        """테스트 출력을 구조화된 결과로 파싱합니다."""
        result = {
            "passed": returncode == 0,
            "returncode": returncode,
            "summary": "",
            "total": 0,
            "passed_count": 0,
            "failed_count": 0,
            "error_count": 0,
            "errors": [],
        }

        import re

        # pytest 결과 파싱
        pytest_match = re.search(r"(\d+) passed", output)
        if pytest_match:
            result["passed_count"] = int(pytest_match.group(1))
        pytest_fail = re.search(r"(\d+) failed", output)
        if pytest_fail:
            result["failed_count"] = int(pytest_fail.group(1))
        pytest_err = re.search(r"(\d+) error", output)
        if pytest_err:
            result["error_count"] = int(pytest_err.group(1))

        # jest/vitest 결과 파싱
        jest_match = re.search(r"Tests:\s+(\d+) passed", output)
        if jest_match:
            result["passed_count"] = int(jest_match.group(1))
        jest_fail = re.search(r"Tests:\s+(\d+) failed", output)
        if jest_fail:
            result["failed_count"] = int(jest_fail.group(1))

        result["total"] = (
            result["passed_count"] + result["failed_count"] + result["error_count"]
        )

        # 에러 메시지 추출
        if not result["passed"]:
            error_lines = []
            for line in output.split("\n"):
                line_lower = line.lower()
                if any(
                    kw in line_lower
                    for kw in [
                        "error:",
                        "failed",
                        "assertion",
                        "traceback",
                        "exception",
                    ]
                ):
                    error_lines.append(line.strip())
            result["errors"] = error_lines[:10]  # 최대 10개

        result["summary"] = (
            f"{'✅ PASSED' if result['passed'] else '❌ FAILED'} — "
            f"Total: {result['total']}, Passed: {result['passed_count']}, "
            f"Failed: {result['failed_count']}, Errors: {result['error_count']}"
        )
        return result

    def execute(self, **kwargs) -> Any:
        command = kwargs.get("command", "")
        path = kwargs.get("path", ".")
        timeout = kwargs.get("timeout_seconds", 120)
        file_filter = kwargs.get("file_filter", "")

        # 자동 감지
        if not command:
            command = self._detect_test_framework(path)
            if not command:
                return (
                    "⚠️ 테스트 프레임워크를 자동 감지할 수 없습니다.\n"
                    "지원 파일: package.json, pyproject.toml, pytest.ini, Makefile, Cargo.toml, go.mod\n"
                    "직접 command를 지정해주세요."
                )

        # 파일 필터 적용
        if file_filter:
            command = f"{command} {file_filter}"

        logger.info(f"[AutoTest] Running: {command} (timeout: {timeout}s)")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=path,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"

            # 구조화된 결과 파싱
            parsed = self._parse_test_result(output, result.returncode)

            # 최종 포맷
            report = f"--- {parsed['summary']} ---\n"
            report += f"Command: {command}\n"
            if parsed["errors"]:
                report += "\n**Error Details:**\n"
                for err in parsed["errors"]:
                    report += f"  • {err}\n"
            report += f"\n{output}" if output.strip() else ""

            # 출력이 너무 길면 truncate
            if len(report) > 8000:
                report = report[:8000] + f"\n... (truncated, {len(report)} total chars)"

            return report

        except subprocess.TimeoutExpired:
            return f"Error: Test execution timed out after {timeout} seconds."
        except Exception as e:
            return f"Error executing tests: {e}"


class AutoLintTool(BaseTool):
    """
    자동 린트/포맷팅 도구.

    파일 변경 후 자동으로 린트를 실행하여 코드 품질을 검증합니다.
    프로젝트의 린트 도구를 자동 감지합니다.
    """

    category = ToolCategory.CODE_EXEC
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "🔍"
    tags = ["lint", "format", "quality", "automation"]

    def __init__(self):
        super().__init__()
        self._name = "auto_lint"
        self._description = (
            "Auto-detects and runs linting/formatting tools for the project. "
            "Supports: eslint, prettier, ruff, black, flake8, pylint, rustfmt, gofmt."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Specific file to lint. If omitted, lints entire project.",
                },
                "fix": {
                    "type": "boolean",
                    "description": "Auto-fix issues when possible.",
                    "default": True,
                },
                "path": {
                    "type": "string",
                    "description": "Project root path.",
                    "default": ".",
                },
            },
            "required": [],
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return self._schema

    def _detect_linters(self, path: str) -> List[Dict[str, str]]:
        """프로젝트 린트 도구 자동 감지"""
        linters = []

        # Python
        if os.path.exists(os.path.join(path, "pyproject.toml")):
            try:
                with open(os.path.join(path, "pyproject.toml"), "r") as f:
                    content = f.read()
                if "ruff" in content:
                    linters.append(
                        {
                            "name": "ruff",
                            "cmd": "ruff check",
                            "fix_cmd": "ruff check --fix",
                        }
                    )
                elif "black" in content:
                    linters.append(
                        {"name": "black", "cmd": "black --check", "fix_cmd": "black"}
                    )
                else:
                    linters.append(
                        {
                            "name": "ruff",
                            "cmd": "ruff check",
                            "fix_cmd": "ruff check --fix",
                        }
                    )
            except Exception:
                pass

        if os.path.exists(os.path.join(path, ".flake8")) or os.path.exists(
            os.path.join(path, "setup.cfg")
        ):
            linters.append({"name": "flake8", "cmd": "flake8", "fix_cmd": "flake8"})

        # JavaScript/TypeScript
        if os.path.exists(os.path.join(path, ".eslintrc.json")) or os.path.exists(
            os.path.join(path, ".eslintrc.js")
        ):
            linters.append(
                {"name": "eslint", "cmd": "npx eslint", "fix_cmd": "npx eslint --fix"}
            )

        if os.path.exists(os.path.join(path, ".prettierrc")) or os.path.exists(
            os.path.join(path, ".prettierrc.json")
        ):
            linters.append(
                {
                    "name": "prettier",
                    "cmd": "npx prettier --check",
                    "fix_cmd": "npx prettier --write",
                }
            )

        # Rust
        if os.path.exists(os.path.join(path, "Cargo.toml")):
            linters.append(
                {
                    "name": "rustfmt",
                    "cmd": "cargo fmt -- --check",
                    "fix_cmd": "cargo fmt",
                }
            )

        # Go
        if os.path.exists(os.path.join(path, "go.mod")):
            linters.append(
                {"name": "gofmt", "cmd": "gofmt -l .", "fix_cmd": "gofmt -w ."}
            )

        return linters

    def execute(self, **kwargs) -> Any:
        file_path = kwargs.get("file_path", "")
        fix = kwargs.get("fix", True)
        path = kwargs.get("path", ".")

        linters = self._detect_linters(path)
        if not linters:
            return "⚠️ 린트 도구를 자동 감지할 수 없습니다. 프로젝트에 lint 설정 파일이 없습니다."

        results = []
        for linter in linters:
            cmd = linter["fix_cmd"] if fix else linter["cmd"]
            if file_path:
                cmd = f"{cmd} {file_path}"

            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=path,
                )
                status = "✅ Clean" if result.returncode == 0 else "⚠️ Issues found"
                output = result.stdout + (f"\n{result.stderr}" if result.stderr else "")
                if len(output) > 2000:
                    output = output[:2000] + "..."
                results.append(f"**{linter['name']}**: {status}\n{output.strip()}")
            except subprocess.TimeoutExpired:
                results.append(f"**{linter['name']}**: ⏱️ Timed out")
            except Exception as e:
                results.append(f"**{linter['name']}**: ❌ Error: {e}")

        return "\n\n".join(results)


class PRCreationTool(BaseTool):
    """
    자동 PR/MR 생성 도구.

    현재 브랜치의 변경 사항을 기반으로 PR을 자동 생성합니다.
    GitHub CLI (gh)를 활용합니다.
    """

    category = ToolCategory.CODE_EXEC
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.HIGH
    icon = "🔀"
    tags = ["git", "pr", "pull-request", "automation"]

    def __init__(self):
        super().__init__()
        self._name = "create_pr"
        self._description = (
            "Creates a Pull Request using GitHub CLI. Auto-generates title and body "
            "from recent commits and diff summary."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "PR title. Auto-generated if omitted.",
                },
                "body": {
                    "type": "string",
                    "description": "PR description. Auto-generated if omitted.",
                },
                "base": {
                    "type": "string",
                    "description": "Base branch.",
                    "default": "main",
                },
                "draft": {
                    "type": "boolean",
                    "description": "Create as draft PR.",
                    "default": False,
                },
                "path": {
                    "type": "string",
                    "description": "Repository path.",
                    "default": ".",
                },
            },
            "required": [],
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return self._schema

    def execute(self, **kwargs) -> Any:
        title = kwargs.get("title", "")
        body = kwargs.get("body", "")
        base = kwargs.get("base", "main")
        draft = kwargs.get("draft", False)
        path = kwargs.get("path", ".")

        def _git(args):
            r = subprocess.run(
                ["git"] + args, cwd=path, capture_output=True, text=True, timeout=15
            )
            return r.stdout.strip()

        # 자동 타이틀 생성
        if not title:
            branch = _git(["branch", "--show-current"])
            last_commit = _git(["log", "-1", "--format=%s"])
            title = last_commit or f"Changes from {branch}"

        # 자동 바디 생성
        if not body:
            diff_stat = _git(["diff", "--stat", f"{base}...HEAD"])
            log = _git(["log", f"{base}...HEAD", "--format=- %s"])
            body = f"## Changes\n\n{log}\n\n## Diff Summary\n\n```\n{diff_stat}\n```"

        cmd = ["gh", "pr", "create", "--title", title, "--body", body, "--base", base]
        if draft:
            cmd.append("--draft")

        try:
            result = subprocess.run(
                cmd, cwd=path, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return f"✅ PR created successfully!\n{result.stdout}"
            else:
                return f"❌ PR creation failed:\n{result.stderr}"
        except FileNotFoundError:
            return (
                "Error: GitHub CLI (gh) is not installed. Install with: brew install gh"
            )
        except Exception as e:
            return f"Error: {e}"
