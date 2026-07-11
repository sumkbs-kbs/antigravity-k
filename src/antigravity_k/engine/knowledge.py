"""Knowledge base management and retrieval utilities."""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class KIEngine:
    """Knowledge Items (KIs) 시스템.

    이전 대화의 지식 구조화 및 패턴을 `.antigravity/knowledge/` 내부에 저장하고,
    에이전트가 호출될 때 로컬 맥락(KIs)을 시스템 프롬프트에 자동으로 주입합니다.
    (Tolaria Advanced Agentic Architecture 패리티)
    """

    def __init__(self, project_root: str):
        """Initialize the KIEngine.

        Args:
            project_root (str): str project root.

        """
        self.project_root = project_root
        self.ki_dir = os.path.join(project_root, ".antigravity", "knowledge")

    def ensure_dir(self):
        """Ensure Dir."""
        os.makedirs(self.ki_dir, exist_ok=True)

    def load_kis(self) -> list[dict[str, Any]]:
        """Load kis.

        Returns:
            list[dict[str, Any]]: The list[dict[str, any]] result.

        """
        self.ensure_dir()
        kis = []
        for file in os.listdir(self.ki_dir):
            if file.endswith("metadata.json"):
                try:
                    with open(os.path.join(self.ki_dir, file), encoding="utf-8") as f:
                        kis.append(json.load(f))
                except Exception:
                    logger.exception("Failed to load KI %s", file)
        return kis

    def save_ki(self, ki_id: str, data: dict[str, Any]):
        """새로운 지식(KI)을 JSON 파일로 저장합니다."""
        self.ensure_dir()
        file_path = os.path.join(self.ki_dir, f"{ki_id}_metadata.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Saved new KI: %s", ki_id)
        except Exception:
            logger.exception("Failed to save KI %s", ki_id)

    def build_ki_prompt(self) -> str:
        """KIs 정보를 읽어 에이전트용 시스템 프롬프트 주입 텍스트를 생성합니다."""
        kis = self.load_kis()
        if not kis:
            return ""

        prompt = "\n\n<persistent_context>\n# Knowledge Items (KIs)\n"
        prompt += "다음은 이전에 요약된 지식 구조(KIs)입니다. 기존에 확립된 패턴을 유지하고 중복 작업을 방지하세요.\n\n"

        for ki in kis:
            title = ki.get("title", "Untitled KI")
            summary = ki.get("summary", "")
            artifacts = ki.get("artifacts", [])

            prompt += f"## {title}\n"
            if ki.get("commit_hash"):
                prompt += f"*(Anchored to Commit: {ki['commit_hash']})*\n"
            prompt += f"{summary}\n"
            if artifacts:
                prompt += "Related Artifacts: " + ", ".join(artifacts) + "\n"
            prompt += "\n"

        prompt += "</persistent_context>\n"
        return prompt
