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
        self._description = "Write a structured markdown artifact (like an implementation plan, review report, or task list). This will save the artifact directly into the 'artifacts/' directory of the current project. When in Planning Mode, set RequestFeedback to true to pause and ask for user approval."
        self._schema = {
            "type": "object",
            "properties": {
                "artifact_name": {
                    "type": "string",
                    "description": "Name of the artifact file (e.g., 'implementation_plan.md', 'review_report.md').",
                },
                "content": {
                    "type": "string",
                    "description": "The markdown content of the artifact.",
                },
                "artifact_type": {
                    "type": "string",
                    "description": "Backward-compatible artifact type hint such as html, markdown, or react.",
                },
                "ArtifactMetadata": {
                    "type": "object",
                    "description": "Metadata for the artifact, used for Planning Mode and task tracking.",
                    "properties": {
                        "ArtifactType": {
                            "type": "string",
                            "enum": [
                                "implementation_plan",
                                "walkthrough",
                                "task",
                                "other",
                            ],
                            "description": "Type of artifact.",
                        },
                        "RequestFeedback": {
                            "type": "boolean",
                            "description": "Set to true to request user feedback/approval on this artifact.",
                        },
                        "Summary": {
                            "type": "string",
                            "description": "Detailed multi-line summary of the artifact file.",
                        },
                    },
                    "required": ["ArtifactType", "Summary"],
                },
            },
            "required": ["artifact_name", "content"],
        }
        self.project_root = project_root or os.getcwd()

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
        artifact_name = kwargs.get("artifact_name", "")
        content = kwargs.get("content", "")
        artifact_type = kwargs.get("artifact_type", "generic")

        # Ensure name is safe
        artifact_name = os.path.basename(artifact_name)

        # Add extension if not present based on type
        if "." not in artifact_name:
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
            metadata = kwargs.get("ArtifactMetadata", {})
            req_feedback = metadata.get("RequestFeedback", False)
            art_type = metadata.get("ArtifactType", artifact_type)

            result_str = f"[ARTIFACT GENERATED: {artifact_name} (Type: {art_type})]\nSuccessfully saved to {file_path}. "
            if req_feedback:
                result_str += "\n[PLANNING_MODE: WAITING_FOR_USER_APPROVAL]"

            return result_str
        except Exception as e:
            return f"Error generating artifact: {e}"
