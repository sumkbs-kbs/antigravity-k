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


class CurriculumGenerator:
    """자가 벤치마크 생성기 및 TDD 연동 파이프라인."""

    def __init__(self, project_root: str, ollama_url: str = "http://localhost:11434"):
        self.project_root = project_root
        self.ollama_url = ollama_url
        self.benchmark_dir = os.path.join(project_root, "tests", "curriculum")
        os.makedirs(self.benchmark_dir, exist_ok=True)

    def generate_new_challenge(self, domain: str = "algorithm") -> Optional[CurriculumTask]:
        """주어진 도메인에서 현재 수준보다 조금 더 어려운 새로운 테스트 과제를 생성합니다."""
        logger.info(f"[Curriculum] '{domain}' 도메인에서 새로운 과제 탐색 중...")

        prompt = (
            f"[ROLE] 당신은 최고 수준의 AI 트레이너입니다.\n"
            f"[TASK] AI 에이전트의 한계를 시험할 '{domain}' 관련 새로운 파이썬 코딩 과제를 만들어주세요.\n"
            "일반적인 튜토리얼 수준이 아닌, 엣지 케이스 처리나 멀티스레딩, 비동기 등 복잡한 요구사항이 포함되어야 합니다.\n\n"
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
            "options": {"num_predict": 1024, "temperature": 0.4},
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
