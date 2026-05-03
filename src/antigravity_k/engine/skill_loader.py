import os
import yaml
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class SkillLoader:
    """
    동적 스킬 로더
    프로젝트의 .agent/skills/ 폴더에 있는 Markdown 지침서(Skills)를 파싱하고 로드합니다.
    """
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path(os.getcwd())
        self.skills_dir = self.project_root / ".agent" / "skills"
        self._skills: Dict[str, Dict[str, Any]] = {}
        self.active_skills: List[str] = []
        
        self.refresh()
        
    def refresh(self):
        """디렉토리를 스캔하여 스킬 목록을 캐시합니다."""
        self._skills.clear()
        if not self.skills_dir.exists():
            return
            
        for root, dirs, files in os.walk(self.skills_dir):
            for file in files:
                if file.endswith(".md"):
                    file_path = Path(root) / file
                    skill_id = file_path.stem
                    # Use directory name as ID if the file is SKILL.md
                    if file == "SKILL.md":
                        skill_id = Path(root).name
                        
                    parsed = self._parse_markdown(file_path)
                    if parsed:
                        self._skills[skill_id] = parsed
                        logger.debug(f"Loaded skill: {skill_id}")

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
                "path": str(path)
            }
        except Exception as e:
            logger.error(f"Failed to parse skill file {path}: {e}")
            return None

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """ID로 스킬을 조회합니다."""
        return self._skills.get(skill_id)

    def list_skills(self) -> List[Dict[str, Any]]:
        """모든 스킬 메타데이터를 반환합니다."""
        return [{"id": k, "name": v["name"], "description": v["description"]} for k, v in self._skills.items()]

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

        prompt_lower = user_prompt.lower()
        scored_skills = []

        for skill_id, skill_data in self._skills.items():
            if skill_id in self.active_skills:
                continue  # 이미 활성화된 스킬 스킵

            score = 0
            name_lower = skill_data.get("name", "").lower()
            desc_lower = skill_data.get("description", "").lower()
            content_preview = skill_data.get("content", "")[:500].lower()

            # 스킬 이름이 프롬프트에 포함 (가장 강력한 시그널)
            if name_lower and name_lower in prompt_lower:
                score += 10

            # 키워드 매칭: description의 단어들이 프롬프트에 포함
            desc_words = set(desc_lower.split())
            prompt_words = set(prompt_lower.split())
            common = desc_words & prompt_words
            # 불용어 제거
            stopwords = {"the", "a", "an", "is", "are", "for", "to", "and", "or", "in", "of", "with", "on", "at", "by"}
            common -= stopwords
            score += len(common) * 2

            # 컨텐츠 프리뷰에 프롬프트 핵심 키워드가 포함
            important_words = [w for w in prompt_words if len(w) > 4 and w not in stopwords]
            for word in important_words:
                if word in content_preview:
                    score += 1

            if score > 3:  # 최소 임계값
                scored_skills.append((skill_id, score))

        # 점수 순으로 정렬하여 상위 N개 활성화
        scored_skills.sort(key=lambda x: x[1], reverse=True)
        activated = []
        for skill_id, score in scored_skills[:max_skills]:
            self.activate_skill(skill_id)
            activated.append(skill_id)
            logger.info(f"[AutoSkill] Activated '{skill_id}' (score: {score}) based on prompt analysis")

        return activated
