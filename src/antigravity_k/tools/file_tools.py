"""
FileTools — 파일 I/O 도구 4종
==============================
Claw Code의 파일 도구 아키텍처 이식:
- write_file   : 새 파일 생성 (디렉토리 자동 생성)
- edit_file     : diff 기반 정밀 편집 (old_str → new_str)
- glob_search   : 파일 패턴 검색 (수정 시간순)
- grep_search   : 코드 내 텍스트/정규식 검색
"""

import os
import re
import glob as glob_module
import logging
from typing import Any, Dict, List

from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)


class WriteFileTool(BaseTool):
    """새 파일 생성 또는 덮어쓰기. 디렉토리가 없으면 자동 생성."""

    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "📝"
    tags = ["file", "write", "create"]

    def __init__(self):
        super().__init__()
        self._name = "write_file"
        self._description = (
            "Creates a new file or overwrites an existing file with the given content. "
            "Parent directories are created automatically if they don't exist."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path for the file.",
                },
                "content": {
                    "type": "string",
                    "description": "Full content to write to the file.",
                },
            },
            "required": ["file_path", "content"],
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
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")

        try:
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Successfully wrote {len(content)} chars to {file_path}"
        except Exception as e:
            return f"Error writing file: {e}"


class CreateDirectoryTool(BaseTool):
    """새로운 디렉토리를 생성합니다."""

    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "📁"
    tags = ["file", "directory", "mkdir", "create"]

    def __init__(self):
        super().__init__()
        self._name = "create_directory"
        self._description = (
            "Creates a new directory at the specified path. "
            "Parent directories are created automatically if they don't exist."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "Absolute or relative path for the new directory.",
                },
            },
            "required": ["dir_path"],
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
        dir_path = kwargs.get("dir_path", "")

        try:
            os.makedirs(dir_path, exist_ok=True)
            return f"Successfully created directory: {dir_path}"
        except Exception as e:
            return f"Error creating directory: {e}"


class EditFileTool(BaseTool):
    """
    Claw Code 스타일 diff 기반 정밀 편집.
    파일에서 old_str을 찾아 new_str로 교체합니다.
    """

    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "✂️"
    tags = ["file", "edit", "diff", "replace"]

    def __init__(self):
        super().__init__()
        self._name = "edit_file"
        self._description = (
            "Makes a targeted edit to a file by replacing an exact text match (old_str) "
            "with new content (new_str). Use for precise, surgical edits. "
            "The old_str must match exactly, including whitespace and indentation."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit.",
                },
                "old_str": {
                    "type": "string",
                    "description": "Exact text to find and replace. Must match precisely.",
                },
                "new_str": {
                    "type": "string",
                    "description": "New text to replace old_str with.",
                },
            },
            "required": ["file_path", "old_str", "new_str"],
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
        file_path = kwargs.get("file_path", "")
        old_str = kwargs.get("old_str", "")
        new_str = kwargs.get("new_str", "")

        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            count = content.count(old_str)
            if count == 0:
                # 부분 매치 힌트 제공
                lines = old_str.strip().split("\n")
                hint_line = lines[0][:60] if lines else ""
                return (
                    f"Error: old_str not found in {file_path}. "
                    f"No match for: '{hint_line}...'. "
                    f"Verify whitespace/indentation matches exactly."
                )
            if count > 1:
                return (
                    f"Error: old_str found {count} times in {file_path}. "
                    f"Please provide a more unique match to avoid ambiguity."
                )

            new_content = content.replace(old_str, new_str, 1)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # 변경 요약 생성
            old_lines = old_str.count("\n") + 1
            new_lines = new_str.count("\n") + 1
            return (
                f"Successfully edited {file_path}: "
                f"replaced {old_lines} lines with {new_lines} lines "
                f"({len(old_str)} → {len(new_str)} chars)"
            )
        except Exception as e:
            return f"Error editing file: {e}"


class MultiReplaceFileContentTool(BaseTool):
    """한 파일에서 여러 개의 비연속적인 텍스트 영역을 동시에 찾아 바꿉니다."""

    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.MEDIUM
    icon = "🛠️"
    tags = ["file", "edit", "multi", "replace", "refactor"]

    def __init__(self):
        super().__init__()
        self._name = "multi_replace_file_content"
        self._description = (
            "Edit a file by replacing multiple non-contiguous blocks of text at once. "
            "Pass an array of 'chunks', each containing 'old_str' and 'new_str'. "
            "This is safer and faster than rewriting the whole file."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to modify.",
                },
                "chunks": {
                    "type": "array",
                    "description": "List of replacements to make.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_str": {
                                "type": "string",
                                "description": "Exact text to find.",
                            },
                            "new_str": {
                                "type": "string",
                                "description": "Text to replace it with.",
                            },
                        },
                        "required": ["old_str", "new_str"],
                    },
                },
            },
            "required": ["file_path", "chunks"],
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
        file_path = kwargs.get("file_path", "")
        chunks = kwargs.get("chunks", [])

        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            success_count = 0
            for idx, chunk in enumerate(chunks):
                old_str = chunk.get("old_str", "")
                new_str = chunk.get("new_str", "")

                count = content.count(old_str)
                if count == 0:
                    return (
                        f"Error on chunk {idx+1}: old_str not found in file. Aborting."
                    )
                if count > 1:
                    return f"Error on chunk {idx+1}: old_str found {count} times. Be more specific. Aborting."

                content = content.replace(old_str, new_str, 1)
                success_count += 1

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Successfully applied {success_count} replacements to {file_path}."
        except Exception as e:
            return f"Error applying multi-replace: {e}"


class GlobSearchTool(BaseTool):
    """
    파일 패턴 검색 (수정 시간순 정렬).
    Claw Code의 glob 도구 — 최근 수정된 파일을 우선 표시.
    """

    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "🔍"
    tags = ["search", "glob", "files", "find"]

    def __init__(self):
        super().__init__()
        self._name = "glob_search"
        self._description = (
            "Searches for files matching a glob pattern (e.g., '**/*.py'). "
            "Results are sorted by modification time (newest first). "
            "Useful for discovering project structure and finding specific files."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '**/*.py', 'src/**/*.ts')",
                },
                "root": {
                    "type": "string",
                    "description": "Root directory to search from",
                    "default": ".",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum files to return",
                    "default": 50,
                },
            },
            "required": ["pattern"],
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
        pattern = kwargs.get("pattern", "")
        root = kwargs.get("root", ".")
        max_results = kwargs.get("max_results", 50)

        try:
            full_pattern = os.path.join(root, pattern)
            matches = glob_module.glob(full_pattern, recursive=True)

            # 수정 시간순 정렬 (최신 우선) — Claw Code 패턴
            file_info = []
            for m in matches:
                try:
                    mtime = os.path.getmtime(m)
                    size = os.path.getsize(m)
                    file_info.append(
                        {
                            "path": os.path.relpath(m, root),
                            "size": size,
                            "modified": mtime,
                        }
                    )
                except OSError:
                    continue

            file_info.sort(key=lambda x: x["modified"], reverse=True)
            file_info = file_info[:max_results]

            if not file_info:
                return f"No files found matching '{pattern}' in {root}"

            lines = [f"Found {len(file_info)} files (newest first):"]
            for f in file_info:
                size_str = self._human_size(f["size"])
                lines.append(f"  {f['path']} ({size_str})")

            return "\n".join(lines)
        except Exception as e:
            return f"Error searching files: {e}"

    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.0f}{unit}"
            size /= 1024
        return f"{size:.0f}TB"


class GrepSearchTool(BaseTool):
    """
    코드 내 텍스트/정규식 검색.
    Claw Code의 grep 도구 — 행 번호와 컨텍스트를 포함한 결과.
    """

    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "🔎"
    tags = ["search", "grep", "text", "regex"]

    def __init__(self):
        super().__init__()
        self._name = "grep_search"
        self._description = (
            "Searches for text or regex patterns in files. Returns matching lines "
            "with file paths and line numbers. Supports recursive directory search."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text or regex pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in.",
                    "default": ".",
                },
                "include": {
                    "type": "string",
                    "description": "File extension filter (e.g., '*.py')",
                    "default": "",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return.",
                    "default": 30,
                },
                "is_regex": {
                    "type": "boolean",
                    "description": "Treat query as regex pattern.",
                    "default": False,
                },
            },
            "required": ["query"],
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
        query = kwargs.get("query", "")
        path = kwargs.get("path", ".")
        include = kwargs.get("include", "")
        max_results = kwargs.get("max_results", 30)
        is_regex = kwargs.get("is_regex", False)

        if not query:
            return "Error: No search query provided."

        try:
            if is_regex:
                pattern = re.compile(query, re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(query), re.IGNORECASE)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        results: List[str] = []

        try:
            if os.path.isfile(path):
                files = [path]
            else:
                glob_pattern = os.path.join(path, "**", include or "*")
                files = glob_module.glob(glob_pattern, recursive=True)
                files = [f for f in files if os.path.isfile(f)]

            for file_path in files:
                if len(results) >= max_results:
                    break

                # 바이너리 파일 스킵
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if len(results) >= max_results:
                                break
                            if pattern.search(line):
                                rel_path = (
                                    os.path.relpath(file_path, path)
                                    if os.path.isdir(path)
                                    else file_path
                                )
                                results.append(
                                    f"{rel_path}:{line_num}: {line.rstrip()}"
                                )
                except (OSError, UnicodeDecodeError):
                    continue

            if not results:
                return f"No matches found for '{query}' in {path}"

            header = f"Found {len(results)} matches:"
            return header + "\n" + "\n".join(results)
        except Exception as e:
            return f"Error searching: {e}"
