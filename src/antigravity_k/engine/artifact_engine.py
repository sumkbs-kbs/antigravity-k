"""Antigravity-K: Artifact Engine (Gemini Antigravity Capability Transfer).

=======================================================================
계획 모드(Planning Mode) 시 생성되는 implementation_plan.md, task.md, walkthrough.md 등
아티팩트를 안전하게 생성하고 갱신하며, 사용자 피드백 요청 메타데이터를 관리합니다.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ArtifactMetadata:
    """Artifactmetadata."""

    artifact_type: str
    summary: str
    request_feedback: bool = False


class ArtifactEngine:
    """Artifact 생성을 담당하는 엔진입니다."""

    def __init__(self, project_root: str):
        """Initialize the ArtifactEngine.

        Args:
            project_root (str): str project root.

        """
        self.project_root = project_root
        self.artifacts_dir = os.path.join(project_root, "artifacts")
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def write_artifact(
        self,
        target_file: str,
        code_content: str,
        metadata: ArtifactMetadata | None = None,
    ) -> dict[str, Any]:
        """아티팩트 파일을 작성합니다.

        Args:
            target_file: 대상 파일 이름 또는 경로 (artifacts/ 내부에 저장됨)
            code_content: 작성할 마크다운 내용
            metadata: ArtifactMetadata 객체

        """
        filename = os.path.basename(target_file)
        if not filename.endswith(".md"):
            filename += ".md"

        filepath = os.path.join(self.artifacts_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code_content)

            feedback_msg = ""
            if metadata and metadata.request_feedback:
                feedback_msg = " [APPROVAL REQUIRED]"

            logger.info("Artifact created: %s%s", filepath, feedback_msg)

            return {
                "success": True,
                "filepath": filepath,
                "message": f"Artifact {filename} successfully written.{feedback_msg}",
                "request_feedback": metadata.request_feedback if metadata else False,
            }
        except Exception as e:
            logger.exception("Failed to write artifact %s", filepath)
            return {"success": False, "error": str(e)}

    def read_artifact(self, target_file: str) -> str | None:
        """아티팩트 파일 내용을 읽습니다."""
        filename = os.path.basename(target_file)
        if not filename.endswith(".md"):
            filename += ".md"

        filepath = os.path.join(self.artifacts_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                return f.read()
        return None

    def inject_planning_prompt(self) -> str:
        """계획 모드 진입을 강제하기 위한 프롬프트를 주입합니다."""
        return (
            "\n\n[CRITICAL ALGORITHM OVERRIDE: ARTIFACT-BASED PLANNING MODE]\n"
            "You are executing a COMPLEX task or requested to plan. You MUST enter PLANNING MODE.\n"
            "1. DO NOT write functional code yet. Research and plan first.\n"
            "2. You MUST use the `write_artifact` tool to create `implementation_plan."
            "md` outlining your technical plan.\n"
            "3. Set `request_feedback: true` in the ArtifactMetadata to pause execution and ask the user for"  # type: ignore
            "permission to proceed.\n"
            "4. After approval, create a `task.md` using `write_artifact` with a checkbox list.\n"
            "5. After completion, create a `walkthrough.md` summarizing the changes.\n"
            "\n[ANTIGRAVITY MARKDOWN STANDARDS - STRICT COMPLIANCE REQUIRED]\n"
            "- Use GitHub Alerts (`> [!NOTE]`, `> [!WARNING]`, etc.) to highlight critical info.\n"
            "- NEVER wrap file link text in backticks. Correct: `[utils.py](file:///...)`, Incorrect: `[`utils.py`](file:///...)`.\n"
            "- When writing Mermaid diagrams, NEVER include HTML tags inside node labels.\n"
            "- For presenting multiple sequential visual or code blocks, use ````carousel` syntax with `<!--"  # type: ignore
            "slide -->` separators.\n"
            "- Ensure your output has high information density. Do not generate long, repetitive filler text.\n"
        )


def register_artifact_tool(tool_registry, project_root: str):
    """도구 레지스트리에 write_artifact 도구를 등록합니다."""
    engine = ArtifactEngine(project_root)

    from antigravity_k.tools.base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory

    class WriteArtifactTool(BaseTool):
        name = "write_artifact"
        description = (
            "Create or update planning artifacts like implementation_plan.md, task.md, and walkthrough.md. MUST"  # type: ignore
        )
        "be used when in planning mode."
        category = ToolCategory.FILE_IO
        render_in = RenderIn.CONTEXTUAL
        risk_level = RiskLevel.LOW
        icon = "📝"

        @property
        def parameters_schema(self) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": {
                    "target_file": {
                        "type": "string",
                        "description": "The target file to create (e.g., implementation_plan.md)",
                    },
                    "code_content": {
                        "type": "string",
                        "description": "The markdown content to write",
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "artifact_type": {
                                "type": "string",
                                "enum": [
                                    "implementation_plan",
                                    "task",
                                    "walkthrough",
                                    "other",
                                ],
                            },
                            "summary": {"type": "string"},
                            "request_feedback": {
                                "type": "boolean",
                                "description": "Set to true to pause and request user approval",
                            },
                        },
                        "required": ["artifact_type"],
                    },
                },
                "required": ["target_file", "code_content"],
            }

        def execute(
            self,
            target_file: str,
            code_content: str,
            metadata: dict[str, Any] = None,
        ) -> Any:
            meta_obj = None
            if metadata:
                meta_obj = ArtifactMetadata(
                    artifact_type=metadata.get("artifact_type", "other"),
                    summary=metadata.get("summary", ""),
                    request_feedback=metadata.get("request_feedback", False),
                )
            result = engine.write_artifact(target_file, code_content, meta_obj)
            if result["success"]:
                msg = result["message"]
                if result.get("request_feedback"):
                    msg += "\n\nWAITING_FOR_USER_APPROVAL"
                return msg
            return f"Error writing artifact: {result.get('error')}"

    tool_registry.install(WriteArtifactTool())
    return engine
