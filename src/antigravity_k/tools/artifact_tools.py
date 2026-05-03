import os
import logging
from typing import Dict, Any

from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)

class WriteArtifactTool(BaseTool):
    """지정된 프로젝트 폴더 내부의 artifacts/ 디렉토리에 마크다운 아티팩트를 저장합니다."""
    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "📄"
    tags = ["artifact", "markdown", "write", "document", "plan"]

    def __init__(self, project_root: str = None):
        super().__init__()
        self._name = "write_artifact"
        self._description = "Write a structured markdown artifact (like an implementation plan, review report, or task list). This will save the artifact directly into the 'artifacts/' directory of the current project, so the frontend UI can display it."
        self._schema = {
            "type": "object",
            "properties": {
                "artifact_name": {"type": "string", "description": "Name of the artifact file (e.g., 'implementation_plan.md', 'review_report.md')."},
                "content": {"type": "string", "description": "The markdown content of the artifact."},
                "artifact_type": {"type": "string", "description": "Type of artifact (md, html, react, generic). Use 'html' or 'react' for UI previews.", "default": "generic"}
            },
            "required": ["artifact_name", "content"]
        }
        self.project_root = project_root or os.getcwd()

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        artifact_name = kwargs.get("artifact_name", "")
        content = kwargs.get("content", "")
        artifact_type = kwargs.get("artifact_type", "generic")
        
        # Ensure name is safe
        artifact_name = os.path.basename(artifact_name)
        
        # Add extension if not present based on type
        if not "." in artifact_name:
            if artifact_type in ["html", "react"]:
                artifact_name += ".html"
            else:
                artifact_name += ".md"
            
        try:
            artifacts_dir = os.path.join(self.project_root, "artifacts")
            os.makedirs(artifacts_dir, exist_ok=True)
            
            file_path = os.path.join(artifacts_dir, artifact_name)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # This special format will be parsed by the frontend to render the artifact UI
            # Include the file content path or raw content depending on how the frontend handles it
            return f"[ARTIFACT GENERATED: {artifact_name} (Type: {artifact_type})]\nSuccessfully saved to {file_path}. The user can now view this in the Artifacts Panel."
        except Exception as e:
            return f"Error generating artifact: {e}"
