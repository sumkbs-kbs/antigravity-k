import os
import yaml
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from antigravity_k.engine.capability_policy import (
    AutonomousCapabilityPolicy,
    CapabilityDecision,
)

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    동적 스킬 로더
    프로젝트의 .agent/skills/ 폴더에 있는 Markdown 지침서(Skills)를 파싱하고 로드합니다.
    """

    def __init__(
        self,
        project_root: Optional[str] = None,
        include_global: bool = True,
        capability_policy_config: Optional[Dict[str, Any]] = None,
    ):
        self.project_root = Path(project_root) if project_root else Path(os.getcwd())
        self.skills_dir = self.project_root / ".agent" / "skills"
        self.include_global = include_global

        # 글로벌 스킬 디렉토리 추가 (사용자 요청: mr.k/program/coding/.agents/skills)
        # 추가로 기본 홈 디렉토리의 .agents/skills 도 지원
        home_dir = Path.home()
        self.global_skills_dirs = [
            Path("/Users/mr.k/program/coding/.agents/skills"),
            home_dir / ".agents" / "skills",
        ]

        self._skills: Dict[str, Dict[str, Any]] = {}
        self.active_skills: List[str] = []
        self.last_decisions: List[CapabilityDecision] = []
        policy_config = capability_policy_config or {}
        self.auto_match_enabled = bool(policy_config.get("auto_match_skills", True))
        self._capability_policy = AutonomousCapabilityPolicy(
            project_root=str(self.project_root),
            max_autonomous_risk=str(policy_config.get("max_autonomous_risk", "high")),
            allow_critical_autonomy=bool(
                policy_config.get("allow_critical_autonomy", False)
            ),
        )

        self.refresh()

    def refresh(self):
        """디렉토리를 스캔하여 스킬 목록을 캐시합니다. (전역 -> 로컬 순서로 오버라이드)"""
        self._skills.clear()

        # 1. 글로벌 스킬 로드
        if self.include_global:
            for global_dir in self.global_skills_dirs:
                if global_dir.exists():
                    self._load_from_dir(global_dir, is_global=True)

        # 2. 로컬 프로젝트 스킬 로드 (글로벌을 덮어씀)
        if self.skills_dir.exists():
            self._load_from_dir(self.skills_dir, is_global=False)

    def _load_from_dir(self, directory: Path, is_global: bool = False):
        """지정된 디렉토리에서 스킬을 로드합니다."""
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(".md"):
                    file_path = Path(root) / file
                    skill_id = file_path.stem
                    # Use directory name as ID if the file is SKILL.md
                    if file == "SKILL.md":
                        skill_id = Path(root).name

                    parsed = self._parse_markdown(file_path)
                    if parsed:
                        parsed["is_global"] = is_global
                        self._skills[skill_id] = parsed
                        logger.debug(
                            f"Loaded {'global' if is_global else 'local'} skill: {skill_id}"
                        )

    def _parse_markdown(self, path: Path) -> Optional[Dict[str, Any]]:
        """마크다운 파일에서 YAML Frontmatter와 Body를 추출합니다."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            metadata = {}
            body = content

            if content.startswith("---\n"):
                parts = content.split("---\n", 2)
                if len(parts) >= 3:
                    try:
                        metadata = yaml.safe_load(parts[1]) or {}
                    except yaml.YAMLError:
                        pass
                    body = parts[2]

            # YAML에 이름이나 설명이 없으면 파일 이름 사용
            name = metadata.get("name", path.stem)
            desc = metadata.get("description", "")

            return {
                "id": path.stem if path.name != "SKILL.md" else path.parent.name,
                "name": name,
                "description": desc,
                "content": body.strip(),
                "path": str(path),
                "tags": metadata.get("tags", []),
                "tools": metadata.get("tools", []),
                "risk_level": str(metadata.get("risk_level", "safe")).lower(),
                "trust_level": str(metadata.get("trust_level", "local")).lower(),
                "requires_approval": bool(metadata.get("requires_approval", False)),
            }
        except Exception as e:
            logger.error(f"Failed to parse skill file {path}: {e}")
            return None

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """ID로 스킬을 조회합니다."""
        return self._skills.get(skill_id)

    def list_skills(self) -> List[Dict[str, Any]]:
        """모든 스킬 메타데이터를 반환합니다."""
        return [
            {
                "id": k,
                "name": v["name"],
                "description": v["description"],
                "risk_level": v.get("risk_level", "safe"),
                "trust_level": v.get("trust_level", "local"),
            }
            for k, v in self._skills.items()
        ]

    def activate_skill(self, skill_id: str) -> bool:
        """활성 스킬 목록에 추가합니다."""
        if skill_id in self._skills and skill_id not in self.active_skills:
            self.active_skills.append(skill_id)
            return True
        return False

    def deactivate_skill(self, skill_id: str) -> bool:
        """활성 스킬 목록에서 제거합니다."""
        if skill_id in self.active_skills:
            self.active_skills.remove(skill_id)
            return True
        return False

    def clear_active_skills(self):
        """모든 활성 스킬을 초기화합니다."""
        self.active_skills.clear()

    def get_active_prompts(self) -> str:
        """활성화된 모든 스킬의 내용을 합쳐서 반환합니다."""
        if not self.active_skills:
            return ""

        prompts = ["\n\n=== ACTIVE SKILLS INSTRUCTIONS ==="]
        for s_id in self.active_skills:
            skill = self._skills.get(s_id)
            if skill:
                prompts.append(f"\n--- SKILL: {skill['name']} ---")
                prompts.append(skill["content"])

        prompts.append("==================================\n")
        return "\n".join(prompts)

    def auto_match(self, user_prompt: str, max_skills: int = 3) -> List[str]:
        """
        사용자 프롬프트와 스킬의 키워드/설명을 비교하여 관련 스킬을 자동 활성화합니다.

        자동화 핵심 기능:
        - 사용자가 /skill activate를 수동으로 입력할 필요 없음
        - 프롬프트 키워드 → 스킬 설명 + 태그 매칭
        - 상위 N개만 활성화 (과도한 컨텍스트 소비 방지)
        """
        if not self._skills:
            return []
        if not self.auto_match_enabled:
            logger.info("[AutoSkill] Auto matching disabled by configuration.")
            return []

        prompt_lower = user_prompt.lower()
        decisions: List[CapabilityDecision] = []

        for skill_id, skill_data in self._skills.items():
            if skill_id in self.active_skills:
                continue  # 이미 활성화된 스킬 스킵

            decision = self._capability_policy.decide_skill(
                skill_id, skill_data, prompt_lower
            )
            if decision.score > 3:
                decisions.append(decision)

        # 점수 순으로 정렬하여 상위 N개 활성화
        decisions.sort(key=lambda item: item.score, reverse=True)
        self.last_decisions = decisions[:max_skills]
        activated = []
        for decision in self.last_decisions:
            if not decision.allows_autonomous_use:
                logger.info(
                    "[AutoSkill] Skipped '%s' decision=%s risk=%s reason=%s",
                    decision.capability_id,
                    decision.decision,
                    decision.risk_level,
                    decision.reason,
                )
                continue
            self.activate_skill(decision.capability_id)
            activated.append(decision.capability_id)
            logger.info(
                "[AutoSkill] Activated '%s' (score: %.2f, risk=%s)",
                decision.capability_id,
                decision.score,
                decision.risk_level,
            )

        return activated

    def get_last_decisions(self) -> List[CapabilityDecision]:
        """최근 자동 스킬 판단 결과를 반환합니다."""
        return list(self.last_decisions)

    def get_autonomous_manifest(self, objective: str = "") -> List[CapabilityDecision]:
        """전체 스킬의 자율 활성화 판단 결과를 반환합니다."""
        decisions = [
            self._capability_policy.decide_skill(skill_id, skill_data, objective)
            for skill_id, skill_data in self._skills.items()
        ]
        decisions.sort(key=lambda item: item.score, reverse=True)
        return decisions
