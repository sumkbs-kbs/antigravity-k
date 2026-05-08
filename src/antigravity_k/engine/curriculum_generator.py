"""
Antigravity-K: Self-Play Curriculum Generator (Level 3 자가 학습 엔진)
=====================================================================
AI가 스스로 새로운 벤치마크(테스트 코드)를 생성하여 자신의 능력을 무한 확장합니다.

특징:
  - 기존 능력을 분석하여 더 어려운 경계 조건(Edge cases)이나 
    새로운 도메인의 Pytest 파일을 동적으로 생성합니다.
  - OmniTDDEngine을 연동해 스스로 코드를 구현(Green)해 봅니다.
  - 통과 시 영구 역량으로 편입, 실패 시 LoRA 훈련 데이터로 기록(Red).
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("antigravity_k.curriculum_generator")


@dataclass
class CurriculumTask:
    """자율 생성된 학습 과제"""
    task_id: str
    domain: str
    difficulty: int  # 1 to 10
    prompt_requirement: str
    generated_test_code: str
    passed: bool = False


class SkillLibrary:
    """Voyager 스타일: 성공한 코드 스니펫(스킬)을 누적하는 로컬 라이브러리."""
    def __init__(self, root_dir: str):
        self.library_dir = os.path.join(root_dir, "data", "skill_library")
        os.makedirs(self.library_dir, exist_ok=True)
        self.index_file = os.path.join(self.library_dir, "skills_index.json")

    def get_known_skills(self) -> List[str]:
        if not os.path.exists(self.index_file):
            return []
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def add_skill(self, task_id: str, domain: str, description: str, code: str):
        skills = self.get_known_skills()
        skill_name = f"{domain}_{task_id}"
        skills.append(description)
        
        # 스킬 인덱스 업데이트
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(skills, f, ensure_ascii=False, indent=2)
            
        # 스킬 코드 저장
        skill_path = os.path.join(self.library_dir, f"{skill_name}.py")
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(f'"""\nDescription: {description}\n"""\n\n{code}')


class CurriculumGenerator:
    """자가 벤치마크 생성기 (Voyager & Frontier 기반)."""

    def __init__(self, project_root: str, ollama_url: str = "http://localhost:11434"):
        self.project_root = project_root
        self.ollama_url = ollama_url
        self.benchmark_dir = os.path.join(project_root, "tests", "curriculum")
        os.makedirs(self.benchmark_dir, exist_ok=True)
        self.skill_library = SkillLibrary(project_root)

    def generate_new_challenge(self, domain: str = "algorithm") -> Optional[CurriculumTask]:
        """주어진 도메인에서 현재 스킬 경계(Frontier)에 있는 새로운 테스트 과제를 생성합니다."""
        logger.info(f"[Curriculum] '{domain}' 도메인에서 Frontier 과제 탐색 중...")
        
        known_skills = self.skill_library.get_known_skills()
        skills_text = "\n".join([f"- {s}" for s in known_skills[-10:]]) if known_skills else "아직 획득한 특수 스킬이 없습니다."

        prompt = (
            f"[ROLE] 당신은 최고 수준의 AI 트레이너입니다.\n"
            f"[HARDWARE TARGET] 시스템은 M5 Max (128GB RAM)에서 구동됩니다. 매우 무거운 병렬 연산이나 대규모 메모리를 쓰는 과제도 충분히 소화할 수 있습니다.\n"
            f"[TASK] AI 에이전트의 현재 한계(Frontier)를 넓힐 '{domain}' 관련 새로운 파이썬 코딩 과제를 만들어주세요.\n"
            f"에이전트가 최근 성공한 스킬 목록은 다음과 같습니다:\n{skills_text}\n\n"
            "위 스킬들을 바탕으로 **단 한 단계 더 복잡하거나 새로운 개념이 추가된(Frontier)** 엣지 케이스 과제를 설계하세요.\n"
            "M5 Max 하드웨어의 이점을 살릴 수 있는 대용량 데이터 처리, 멀티스레딩, 극단적 비동기 처리 관련 주제를 권장합니다.\n"
            "아래 JSON 형식으로만 응답하세요:\n"
            '{"requirement": "에이전트가 풀어야 할 자연어 요구사항", '
            '"difficulty": 8, '
            '"pytest_code": "import pytest\\n\\ndef test_something():..."}\n'
            "주의: pytest_code는 'solution' 모듈에서 함수를 임포트한다고 가정하세요."
        )

        try:
            resp = self._call_llm(prompt, "deepseek-v4")
            data = self._extract_json(resp)
            
            if data and "requirement" in data and "pytest_code" in data:
                import time
                task_id = f"challenge_{int(time.time())}"
                task = CurriculumTask(
                    task_id=task_id,
                    domain=domain,
                    difficulty=data.get("difficulty", 5),
                    prompt_requirement=data["requirement"],
                    generated_test_code=data["pytest_code"]
                )
                logger.info(f"[Curriculum] 과제 생성됨: 난이도 {task.difficulty} - {task.prompt_requirement[:30]}...")
                return task
        except Exception as e:
            logger.error(f"[Curriculum] 과제 생성 실패: {e}")
        return None

    async def self_play(self, task: CurriculumTask) -> bool:
        """생성된 과제를 OmniTDDEngine을 통해 스스로 풀어봅니다."""
        logger.info(f"[Curriculum] Self-Play 시작: {task.task_id}")
        
        try:
            from antigravity_k.engine.tdd_engine import OmniTDDEngine
            
            # 임시 테스트 파일 저장
            test_file_path = os.path.join(self.benchmark_dir, f"test_{task.task_id}.py")
            with open(test_file_path, "w", encoding="utf-8") as f:
                f.write(task.generated_test_code)

            # TDD 엔진 구동
            engine = OmniTDDEngine(workspace_dir=os.path.join(self.benchmark_dir, "workspace"))
            # OmniTDDEngine.run_tdd_loop 내부에 target_file_path가 없으면 결과만 리포트
            
            # TODO: OmniTDDEngine이 외부 test_file_path를 인자로 받도록 구조 확장 필요
            # 현재 구현은 프롬프트 기반으로 로컬 모델이 테스트까지 스스로 생성하므로,
            # Curriculum Generator의 요구사항만 전달
            report = await engine.run_tdd_loop(task.prompt_requirement)
            
            task.passed = (report.status.value == "passed")
            
            if task.passed:
                logger.info(f"[Curriculum] 🏆 챌린지 성공! 새로운 능력 획득. ({task.task_id})")
                # 성공 시 벤치마크 아카이브에 영구 저장
                archive_path = os.path.join(self.benchmark_dir, "passed", f"test_{task.task_id}.py")
                os.makedirs(os.path.dirname(archive_path), exist_ok=True)
                os.rename(test_file_path, archive_path)
                
                # 스킬 라이브러리에 성공한 코드(스킬) 저장 (Voyager 방식)
                if report.final_code:
                    self.skill_library.add_skill(
                        task_id=task.task_id, 
                        domain=task.domain, 
                        description=task.prompt_requirement[:100], 
                        code=report.final_code
                    )
            else:
                logger.warning(f"[Curriculum] 💥 챌린지 실패. LoRA 파인튜닝 대기열에 추가. ({task.task_id})")
                # 실패 로그를 남겨 나중에 LoRAPipeline에서 사용
                fail_log = os.path.join(self.benchmark_dir, "failed", f"{task.task_id}.json")
                os.makedirs(os.path.dirname(fail_log), exist_ok=True)
                with open(fail_log, "w", encoding="utf-8") as f:
                    json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

            return task.passed

        except Exception as e:
            logger.error(f"[Curriculum] Self-Play 오류: {e}")
            return False

    def _call_llm(self, prompt: str, model: str) -> str:
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 1024, 
                "temperature": 0.4,
                "num_ctx": 32768,       # M5 Max 128GB RAM 최적화
                "num_thread": 16,       # M5 Max 최적화
                "num_gpu": 99           # Apple Silicon GPU 완전 가속
            },
        }
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result.get("response", "")
            return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    def _extract_json(self, text: str) -> Optional[Dict]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None
