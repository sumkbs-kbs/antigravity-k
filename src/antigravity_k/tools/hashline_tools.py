import os
import hashlib
from typing import Any, Dict
from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

def compute_line_hash(line: str) -> str:
    """Compute a short hash for a given line of code."""
    # Use MD5 or SHA256 and take first 4-6 chars
    return hashlib.md5(line.encode('utf-8')).hexdigest()[:4].upper()

class ReadHashFileTool(BaseTool):
    category = ToolCategory.FILE_IO
    render_in = RenderIn.TOOLBAR
    risk_level = RiskLevel.SAFE
    icon = "📄"
    tags = ["file", "read", "hashline"]

    def __init__(self):
        super().__init__()
        self._name = "read_hash_file"
        self._description = "Reads a file and prepends each line with a unique content hash. Use this to prepare for HashlineEditTool."
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute or relative path to the file."}
            },
            "required": ["file_path"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        file_path = kwargs.get("file_path")
        if not file_path or not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            hashed_lines = []
            for i, line in enumerate(lines):
                line_content = line.rstrip('\n')
                line_hash = compute_line_hash(line_content)
                hashed_lines.append(f"{i+1}#{line_hash}| {line_content}")
                
            return "\n".join(hashed_lines)
        except Exception as e:
            return f"Error reading file: {e}"

class HashlineEditTool(BaseTool):
    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "✏️"
    tags = ["file", "write", "edit", "hashline"]

    def __init__(self):
        super().__init__()
        self._name = "hashline_edit"
        self._description = "Replaces a specific line in a file using its exact content hash to prevent stale-line errors."
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to modify."},
                "line_number": {"type": "integer", "description": "1-indexed line number."},
                "expected_hash": {"type": "string", "description": "The 4-character content hash of the original line."},
                "replacement_text": {"type": "string", "description": "New content to replace the line."}
            },
            "required": ["file_path", "line_number", "expected_hash", "replacement_text"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        file_path = kwargs.get("file_path")
        line_number = kwargs.get("line_number")
        expected_hash = kwargs.get("expected_hash", "").upper()
        replacement_text = kwargs.get("replacement_text", "")

        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            if line_number < 1 or line_number > len(lines):
                return f"Error: Line number {line_number} is out of bounds."
                
            target_line_idx = line_number - 1
            current_line = lines[target_line_idx].rstrip('\n')
            current_hash = compute_line_hash(current_line)
            
            if current_hash != expected_hash:
                return f"Error: Hash mismatch (Stale line). Expected {expected_hash}, found {current_hash}."
                
            # Replace the line
            lines[target_line_idx] = replacement_text + ('\n' if lines[target_line_idx].endswith('\n') else '')
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
            return f"Successfully updated line {line_number} in {file_path}."
        except Exception as e:
            return f"Error modifying file: {e}"

class MultiReplaceFileContentTool(BaseTool):
    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "⚡"
    tags = ["file", "write", "edit", "multi_replace"]

    def __init__(self):
        super().__init__()
        self._name = "multi_replace_file_content"
        self._description = "Replaces multiple non-contiguous blocks of text in a single file pass."
        self._schema = {
            "type": "object",
            "properties": {
                "TargetFile": {"type": "string", "description": "Absolute path to the file to modify."},
                "ReplacementChunks": {
                    "type": "array",
                    "description": "List of chunks to replace.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "StartLine": {"type": "integer"},
                            "EndLine": {"type": "integer"},
                            "TargetContent": {"type": "string"},
                            "ReplacementContent": {"type": "string"}
                        },
                        "required": ["StartLine", "EndLine", "TargetContent", "ReplacementContent"]
                    }
                }
            },
            "required": ["TargetFile", "ReplacementChunks"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        target_file = kwargs.get("TargetFile")
        chunks = kwargs.get("ReplacementChunks", [])

        if not os.path.exists(target_file):
            return f"Error: File not found at {target_file}"

        try:
            with open(target_file, "r", encoding="utf-8") as f:
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
            return f"Error modifying file: {e}"
