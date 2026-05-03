import subprocess
from typing import Any, Dict
from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

class ASTGrepTool(BaseTool):
    """
    ASTGrepTool: Leverages the `ast-grep` (sg) CLI for semantic, AST-based 
    code search and structural replacement, heavily reducing regex fragility.
    """
    category = ToolCategory.CODE_EXEC
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.MEDIUM
    icon = "🌲"
    tags = ["ast", "grep", "search", "replace", "refactor"]

    def __init__(self):
        super().__init__()
        self._name = "ast_grep"
        self._description = "Performs structural code search or replacement using ast-grep (sg). Uses AST patterns instead of raw regex."
        self._schema = {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "The AST pattern to search for (e.g., 'def $FUNC($ARGS): $BODY')."},
                "lang": {"type": "string", "description": "The programming language (e.g., python, typescript, rust)."},
                "replace": {"type": "string", "description": "Optional: The replacement pattern. If omitted, performs a dry-run search."},
                "target_dir": {"type": "string", "description": "The directory or file to run the search against.", "default": "."}
            },
            "required": ["pattern", "lang"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        pattern = kwargs.get("pattern")
        lang = kwargs.get("lang")
        replace = kwargs.get("replace")
        target_dir = kwargs.get("target_dir", ".")

        if not pattern or not lang:
            return "Error: Both 'pattern' and 'lang' are required."

        # Base ast-grep command
        cmd = ["sg", "-p", pattern, "-l", lang]

        if replace:
            # Add replace flag (in-place modification can be dangerous, so usually we need hits first,
            # but for this tool we allow in-place via -U if requested)
            cmd.extend(["-r", replace, "-U"])

        cmd.append(target_dir)

        try:
            # We assume `ast-grep` (sg) is installed in the environment.
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0 and result.stderr:
                return f"ast-grep execution failed:\n{result.stderr}"
                
            output = result.stdout
            if not output:
                return "No matches found."
                
            return output
        except FileNotFoundError:
            return "Error: 'sg' (ast-grep) command not found. Please install ast-grep (e.g., `npm install -g @ast-grep/cli` or `brew install ast-grep`)."
        except subprocess.TimeoutExpired:
            return "Error: ast-grep execution timed out."
        except Exception as e:
            return f"Error executing ast-grep: {e}"
