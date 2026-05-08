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
import random
import re
import urllib.request
from dataclasses import dataclass
from typing import Optional, List, Dict

try:
    from datasets import load_dataset
    HAS_DATASETS = True
except ImportError:
    HAS_DATASETS = False

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
    ground_truth_code: Optional[str] = None
    is_hf_dataset: bool = False


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


class DatasetIngestor:
    """Hugging Face 데이터셋을 로드하고 미해결 문제를 샘플링하는 인제스터."""
    def __init__(self, dataset_name: str = "openai_humaneval"):
        self.dataset_name = dataset_name
        self.dataset = None

    def load(self):
        if not HAS_DATASETS:
            logger.warning("[Curriculum] Hugging Face 'datasets' 라이브러리가 설치되지 않았습니다.")
            return False
        try:
            logger.info(f"[Curriculum] 데이터셋 로드 중: {self.dataset_name}...")
            self.dataset = load_dataset(self.dataset_name, split="test")
            return True
        except Exception as e:
            logger.error(f"[Curriculum] 데이터셋 로드 실패: {e}")
            return False

    def sample_task(self) -> Optional[CurriculumTask]:
        if not self.dataset:
            if not self.load():
                return None
        
        # 무작위 샘플링 (추후 '이미 푼 문제' 필터링 추가 가능)
        idx = random.randint(0, len(self.dataset) - 1)
        item = self.dataset[idx]
        
        task_id = f"hf_{self.dataset_name.replace('/', '_')}_{item.get('task_id', idx)}"
        prompt_req = item.get("prompt", "")
        tests = item.get("test", "")
        ground_truth = item.get("canonical_solution", "")
        
        # 테스트 코드가 있으면 변환, 없으면 빈 테스트
        pytest_code = tests if tests else "import pytest\n\ndef test_placeholder():\n    pass\n"

        return CurriculumTask(
            task_id=task_id,
            domain="huggingface_dataset",
            difficulty=6, # HumanEval 기본 난이도
            prompt_requirement=prompt_req,
            generated_test_code=pytest_code,
            ground_truth_code=ground_truth,
            is_hf_dataset=True
        )


class CurriculumGenerator:
    """자가 벤치마크 생성기 (Voyager & Frontier 기반)."""

    def __init__(self, project_root: str, ollama_url: str = "http://localhost:11434"):
        self.project_root = project_root
        self.ollama_url = ollama_url
        self.benchmark_dir = os.path.join(project_root, "tests", "curriculum")
        os.makedirs(self.benchmark_dir, exist_ok=True)
        self.skill_library = SkillLibrary(project_root)
        self.dataset_ingestor = DatasetIngestor("openai_humaneval")

    def generate_new_challenge(self, domain: str = "algorithm", force_synthetic: bool = False) -> Optional[CurriculumTask]:
        """듀얼 모드: HF 데이터셋(Mode B)과 자율 창작(Mode A) 중 하나를 선택해 과제를 생성합니다."""
        
        # 50% 확률로 Hugging Face 데이터셋 활용 (Mode B)
        if not force_synthetic and HAS_DATASETS and random.random() < 0.5:
            logger.info("[Curriculum] Mode B: Hugging Face 데이터셋에서 샘플링합니다.")
            task = self.dataset_ingestor.sample_task()
            if task:
                return task
            
        # Mode A (Synthetic Frontier)
        logger.info(f"[Curriculum] Mode A: '{domain}' 도메인에서 Synthetic Frontier 과제 탐색 중...")
        
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
                fail_log = os.path.join(self.benchmark_dir, "failed", f"{task.task_id}.json")
                os.makedirs(os.path.dirname(fail_log), exist_ok=True)
                
                # 정답(Ground Truth)이 존재한다면 초고품질 LoRA 페이로드로 변환
                log_data = report.to_dict()
                if task.is_hf_dataset and task.ground_truth_code:
                    logger.info("[Curriculum] 정답지(Ground Truth)를 포함한 고품질 LoRA 훈련 데이터셋을 생성합니다.")
                    log_data["lora_payload"] = {
                        "instruction": task.prompt_requirement,
                        "failed_attempt": report.final_code,
                        "ground_truth_solution": task.ground_truth_code,
                        "tests": task.generated_test_code
                    }
                    
                with open(fail_log, "w", encoding="utf-8") as f:
                    json.dump(log_data, f, ensure_ascii=False, indent=2)

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
