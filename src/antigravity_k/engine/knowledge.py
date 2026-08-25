"""Knowledge base management and retrieval utilities."""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# persistent_context 주입 상한(문자). KI가 누적될수록 매 요청 비용이
# 선형 증가하는 것을 막는다 — 최신 KI 우선으로 예산 내에서만 포함한다.
MAX_KI_PROMPT_CHARS = 4000


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
                    path = os.path.join(self.ki_dir, file)
                    with open(path, encoding="utf-8") as f:
                        entry = json.load(f)
                    try:
                        entry["_mtime"] = os.path.getmtime(path)
                    except OSError:
                        entry["_mtime"] = 0.0
                    kis.append(entry)
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
        """KIs 정보를 읽어 에이전트용 시스템 프롬프트 주입 텍스트를 생성합니다.

        최신 KI 우선으로 MAX_KI_PROMPT_CHARS 예산 내에서만 포함합니다.
        """
        kis = self.load_kis()
        if not kis:
            return ""

        ordered = sorted(kis, key=lambda ki: ki.get("_mtime", 0.0), reverse=True)

        prompt = "\n\n<persistent_context>\n# Knowledge Items (KIs)\n"
        prompt += "다음은 이전에 요약된 지식 구조(KIs)입니다. 기존에 확립된 패턴을 유지하고 중복 작업을 방지하세요.\n\n"

        included = 0
        skipped = 0
        for ki in ordered:
            block = self._render_ki_block(ki)
            if included > 0 and len(prompt) + len(block) > MAX_KI_PROMPT_CHARS:
                skipped += 1
                continue
            # 첫 KI는 예산을 넘어도 항상 포함 (빈 지식 주입 방지)
            if included == 0 and len(prompt) + len(block) > MAX_KI_PROMPT_CHARS:
                block = block[: MAX_KI_PROMPT_CHARS - len(prompt)] + "\n\n"
            prompt += block
            included += 1

        if skipped:
            prompt += f"_(오래된 KI {skipped}개는 예산 초과로 생략됨)_\n\n"

        prompt += "</persistent_context>\n"
        return prompt

    @staticmethod
    def _render_ki_block(ki: dict[str, Any]) -> str:
        """단일 KI를 프롬프트 블록 문자열로 렌더링합니다."""
        title = ki.get("title", "Untitled KI")
        summary = ki.get("summary", "")
        artifacts = ki.get("artifacts", [])

        block = f"## {title}\n"
        if ki.get("commit_hash"):
            block += f"*(Anchored to Commit: {ki['commit_hash']})*\n"
        block += f"{summary}\n"
        if artifacts:
            block += "Related Artifacts: " + ", ".join(artifacts) + "\n"
        return block + "\n"
