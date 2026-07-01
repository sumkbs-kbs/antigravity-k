"""Hashline Tools module."""

import hashlib
import logging
import os
from typing import Any

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory

logger = logging.getLogger(__name__)


def compute_line_hash(line: str) -> str:
    """Compute a short hash for a given line of code."""
    # Use MD5 or SHA256 and take first 4-6 chars
    return hashlib.md5(line.encode("utf-8")).hexdigest()[:4].upper()


class ReadHashFileTool(BaseTool):
    """Readhashfiletool.

    Bases: BaseTool
    """

    category = ToolCategory.FILE_IO
    render_in = RenderIn.TOOLBAR
    risk_level = RiskLevel.SAFE
    icon = "📄"
    tags = ["file", "read", "hashline"]

    def __init__(self):
        """Initialize the ReadHashFileTool."""
        super().__init__()
        self._name = "read_hash_file"
        self._description = (
            "Reads a file and prepends each line with a unique content hash. Use this to prepare for HashlineEditTool."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file.",
                },
            },
            "required": ["file_path"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        file_path = kwargs.get("file_path")
        if not file_path or not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"

        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            hashed_lines = []
            for i, line in enumerate(lines):
                line_content = line.rstrip("\n")
                line_hash = compute_line_hash(line_content)
                hashed_lines.append(f"{i + 1}#{line_hash}| {line_content}")

            return "\n".join(hashed_lines)
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Error reading file: {e}"


class HashlineEditTool(BaseTool):
    """Hashlineedittool.

    Bases: BaseTool
    """

    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "✏️"
    tags = ["file", "write", "edit", "hashline"]

    def __init__(self):
        """Initialize the HashlineEditTool."""
        super().__init__()
        self._name = "hashline_edit"
        self._description = (
            "Replaces a specific line in a file using its exact content hash to prevent stale-line errors."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to modify."},
                "line_number": {"type": "integer", "description": "1-indexed line number."},
                "expected_hash": {
                    "type": "string",
                    "description": "The 4-character content hash of the original line.",
                },
                "replacement_text": {
                    "type": "string",
                    "description": "New content to replace the line.",
                },
            },
            "required": ["file_path", "line_number", "expected_hash", "replacement_text"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        file_path = kwargs.get("file_path")
        line_number = kwargs.get("line_number")
        expected_hash = kwargs.get("expected_hash", "").upper()
        replacement_text = kwargs.get("replacement_text", "")

        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"

        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            if line_number < 1 or line_number > len(lines):
                return f"Error: Line number {line_number} is out of bounds."

            target_line_idx = line_number - 1
            current_line = lines[target_line_idx].rstrip("\n")
            current_hash = compute_line_hash(current_line)

            if current_hash != expected_hash:
                return f"Error: Hash mismatch (Stale line). Expected {expected_hash}, found {current_hash}."

            # Replace the line
            lines[target_line_idx] = replacement_text + ("\n" if lines[target_line_idx].endswith("\n") else "")

            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return f"Successfully updated line {line_number} in {file_path}."
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Error modifying file: {e}"


class MultiReplaceFileContentTool(BaseTool):
    """Multireplacefilecontenttool.

    Bases: BaseTool
    """

    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "⚡"
    tags = ["file", "write", "edit", "multi_replace"]

    def __init__(self):
        """Initialize the MultiReplaceFileContentTool."""
        super().__init__()
        self._name = "multi_replace_file_content"
        self._description = "Replaces multiple non-contiguous blocks of text in a single file pass."
        self._schema = {
            "type": "object",
            "properties": {
                "TargetFile": {
                    "type": "string",
                    "description": "Absolute path to the file to modify.",
                },
                "ReplacementChunks": {
                    "type": "array",
                    "description": "List of chunks to replace.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "StartLine": {"type": "integer"},
                            "EndLine": {"type": "integer"},
                            "TargetContent": {"type": "string"},
                            "ReplacementContent": {"type": "string"},
                        },
                        "required": ["StartLine", "EndLine", "TargetContent", "ReplacementContent"],
                    },
                },
            },
            "required": ["TargetFile", "ReplacementChunks"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        target_file = kwargs.get("TargetFile")
        chunks = kwargs.get("ReplacementChunks", [])

        if not os.path.exists(target_file):
            return f"Error: File not found at {target_file}"

        try:
            with open(target_file, encoding="utf-8") as f:
                content = f.read()

            for chunk in chunks:
                target = chunk.get("TargetContent", "")
                repl = chunk.get("ReplacementContent", "")
                if target not in content:
                    return f"Error: TargetContent not found in file: {target[:50]}..."

                content = content.replace(target, repl)

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Successfully applied {len(chunks)} replacement chunk(s) to {target_file}."
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Error modifying file: {e}"
