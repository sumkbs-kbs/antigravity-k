"""
GitTools — Git 도구 4종
========================
Claw Code의 Git 도구 아키텍처 이식:
- git_status : 변경 사항 확인
- git_diff   : 변경 내용 상세 비교
- git_commit : 커밋 (HITL 승인)
- git_log    : 커밋 히스토리 조회
"""
import os
import subprocess
import logging
from typing import Any, Dict

from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)


def _run_git(args: list, cwd: str = ".", timeout: int = 30) -> str:
    """Git 명령 실행 헬퍼."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout
        if result.returncode != 0 and result.stderr:
            output += f"\nSTDERR: {result.stderr}"
        return output or "(no output)"
    except FileNotFoundError:
        return "Error: Git is not installed or not in PATH."
    except subprocess.TimeoutExpired:
        return f"Error: Git command timed out after {timeout}s."
    except Exception as e:
        return f"Error running git: {e}"


class GitStatusTool(BaseTool):
    """현재 Git 저장소의 변경 상태를 확인합니다."""
    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "📊"
    tags = ["git", "status", "changes"]

    def __init__(self):
        super().__init__()
        self._name = "git_status"
        self._description = (
            "Shows the current Git repository status including staged, "
            "unstaged, and untracked files."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repository path.", "default": "."},
            },
            "required": []
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        path = kwargs.get("path", ".")
        return _run_git(["status", "--short", "--branch"], cwd=path)


class GitDiffTool(BaseTool):
    """변경 내용 상세 비교 (staged/unstaged)."""
    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "📋"
    tags = ["git", "diff", "changes"]

    def __init__(self):
        super().__init__()
        self._name = "git_diff"
        self._description = (
            "Shows the diff of changes in the repository. "
            "Use staged=true to see staged changes."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repository path.", "default": "."},
                "staged": {"type": "boolean", "description": "Show staged (cached) changes.", "default": False},
                "file": {"type": "string", "description": "Specific file to diff.", "default": ""},
            },
            "required": []
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        path = kwargs.get("path", ".")
        staged = kwargs.get("staged", False)
        file_filter = kwargs.get("file", "")
        
        args = ["diff", "--stat"]
        if staged:
            args.append("--cached")
        if file_filter:
            args.extend(["--", file_filter])
        
        # 통계 먼저
        summary = _run_git(args, cwd=path)
        
        # 상세 diff (너무 길면 잘라냄)
        detail_args = ["diff"]
        if staged:
            detail_args.append("--cached")
        if file_filter:
            detail_args.extend(["--", file_filter])
        
        detail = _run_git(detail_args, cwd=path)
        
        # 5000자 제한 (컨텍스트 절약 — Claw Code 패턴)
        if len(detail) > 5000:
            detail = detail[:5000] + f"\n... (truncated, {len(detail)} total chars)"
        
        return f"=== Summary ===\n{summary}\n=== Diff ===\n{detail}"


class GitCommitTool(BaseTool):
    """변경 사항을 커밋합니다. HITL 승인 필요."""
    category = ToolCategory.CODE_EXEC
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.MEDIUM
    icon = "💾"
    tags = ["git", "commit", "save"]

    def __init__(self):
        super().__init__()
        self._name = "git_commit"
        self._description = (
            "Stages and commits changes with a message. "
            "By default stages all changes. Requires approval."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message."},
                "path": {"type": "string", "description": "Repository path.", "default": "."},
                "stage_all": {"type": "boolean", "description": "Stage all changes before commit.", "default": True},
            },
            "required": ["message"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        message = kwargs.get("message", "")
        path = kwargs.get("path", ".")
        stage_all = kwargs.get("stage_all", True)
        
        if not message:
            return "Error: Commit message is required."
        
        result_parts = []
        
        if stage_all:
            stage_result = _run_git(["add", "-A"], cwd=path)
            result_parts.append(f"Stage: {stage_result}")
        
        commit_result = _run_git(["commit", "-m", message], cwd=path)
        result_parts.append(f"Commit: {commit_result}")
        
        return "\n".join(result_parts)


class GitLogTool(BaseTool):
    """커밋 히스토리를 조회합니다."""
    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "📜"
    tags = ["git", "log", "history"]

    def __init__(self):
        super().__init__()
        self._name = "git_log"
        self._description = (
            "Shows recent commit history with author, date, and message."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repository path.", "default": "."},
                "count": {"type": "integer", "description": "Number of commits to show.", "default": 10},
                "oneline": {"type": "boolean", "description": "Compact one-line format.", "default": True},
            },
            "required": []
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        path = kwargs.get("path", ".")
        count = kwargs.get("count", 10)
        oneline = kwargs.get("oneline", True)
        
        args = ["log", f"-n{count}"]
        if oneline:
            args.append("--oneline")
        else:
            args.extend(["--format=%h %an %ai %s"])
        
        return _run_git(args, cwd=path)
