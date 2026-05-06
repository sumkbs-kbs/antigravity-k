import asyncio
import json
import logging
import os
import subprocess
import time
import shutil
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple
import httpx

from antigravity_k.engine.external_brain import ExternalBrainRouter

logger = logging.getLogger("antigravity_k.tdd_engine")


class TDDStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    TESTING = "testing"
    FIXING = "fixing"
    PASSED = "passed"
    FAILED = "failed"


@dataclass
class TDDCandidate:
    source: str
    code: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    passed: bool = False
    duration_ms: float = 0.0


@dataclass
class TDDAttempt:
    iteration: int
    test_code: str
    candidates: List[TDDCandidate] = field(default_factory=list)
    winner_source: str = ""
    duration_ms: float = 0.0


@dataclass
class TDDReport:
    prompt: str
    status: TDDStatus = TDDStatus.PENDING
    final_code: str = ""
    explanation: str = ""
    winner_source: str = ""
    total_iterations: int = 0
    attempts: List[TDDAttempt] = field(default_factory=list)
    duration_ms: float = 0.0
    error: str = ""
    skipped_racing: bool = False

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "status": self.status.value,
            "final_code": self.final_code,
            "explanation": self.explanation,
            "winner_source": self.winner_source,
            "total_iterations": self.total_iterations,
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error,
            "skipped_racing": self.skipped_racing,
            "attempts": [
                {
                    "iteration": a.iteration,
                    "winner_source": a.winner_source,
                    "candidates": [
                        {
                            "source": c.source,
                            "passed": c.passed,
                            "exit_code": c.exit_code,
                            "duration_ms": round(c.duration_ms, 1),
                        }
                        for c in a.candidates
                    ],
                    "duration_ms": round(a.duration_ms, 1),
                }
                for a in self.attempts
            ],
        }


class OmniTDDEngine:
    """
    Omni-Resource Test-Driven Generation Engine.
    가용 가능한 모든 두뇌(로컬 모델, ChatGPT 웹, Gemini 앱 등)를 동시에 호출하여
    코드를 작성하고, 테스트를 통과한 최적의 코드를 선별(Racing & Synthesis)합니다.
    """

    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434",
        coding_model: str = "deepseek-r1:70b",
        max_iterations: int = 3,
        workspace_dir: str = "",
    ):
        self.ollama_url = ollama_url
        self.coding_model = coding_model
        self.max_iterations = max_iterations
        self.workspace_dir = workspace_dir or os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            ),
            "tests",
            ".tdd_tmp",
        )
        self.brain_router = ExternalBrainRouter()

    def _should_skip_racing(self, prompt: str) -> bool:
        """단순한 코딩 요청은 멀티모델 레이싱을 건너뛰고 로컬 모델만 사용합니다.

        Adaptive Mode: 토큰 수가 적고, 설명/작성/구현 등 단순 지시어만 포함된 경우
        외부 브레인 호출을 생략하여 10~15배 빠른 응답을 제공합니다.
        """
        token_count = len(re.findall(r"[\w가-힣]+", prompt))
        simple_indicators = {
            "작성",
            "만들어",
            "구현",
            "알려",
            "설명",
            "보여",
            "짜줘",
            "코드",
            "write",
            "create",
            "implement",
            "show",
        }
        has_simple = any(ind in prompt.lower() for ind in simple_indicators)
        # 30토큰 미만 + 단순 지시어 → 레이싱 불필요
        return token_count < 30 and has_simple

    async def run_tdd_loop(
        self, prompt: str, target_file_path: str = None
    ) -> TDDReport:
        report = TDDReport(prompt=prompt)
        start_time = time.time()
        skip_racing = self._should_skip_racing(prompt)
        report.skipped_racing = skip_racing

        os.makedirs(self.workspace_dir, exist_ok=True)
        test_file = os.path.join(self.workspace_dir, "test_solution.py")

        current_test_code = ""
        # 에러 로그 풀 (각 소스별 에러를 저장하여 다음 라운드에 피드백)
        error_logs: Dict[str, str] = {}

        try:
            for iteration in range(1, self.max_iterations + 1):
                report.total_iterations = iteration
                attempt_start = time.time()
                attempt = TDDAttempt(iteration=iteration, test_code="")

                logger.info(
                    f"[OmniTDD] Iteration {iteration} starting... (racing={'OFF' if skip_racing else 'ON'})"
                )

                if iteration == 1:
                    report.status = TDDStatus.GENERATING
                    # 1. 로컬 모델로 테스트 코드 생성 (기준점 확보)
                    _, current_test_code = await self._generate_local_baseline(prompt)
                    attempt.test_code = current_test_code

                    # 테스트 파일 기록
                    with open(test_file, "w", encoding="utf-8") as f:
                        test_code_to_write = current_test_code
                        if (
                            "import solution" not in test_code_to_write
                            and "from solution" not in test_code_to_write
                        ):
                            test_code_to_write = (
                                "import solution\n\n" + test_code_to_write
                            )
                        f.write(test_code_to_write)

                    # 2. Adaptive: 단순 요청이면 로컬만, 복잡하면 멀티모델 레이싱
                    if skip_racing:
                        candidates = await self._get_local_only_candidate(prompt)
                    else:
                        candidates = await self._get_initial_candidates(prompt)
                else:
                    report.status = TDDStatus.FIXING
                    attempt.test_code = current_test_code
                    # 2. 다중 모델 병렬 버그 픽스
                    candidates = await self._get_fixed_candidates(
                        prompt, current_test_code, error_logs
                    )

                if not candidates:
                    raise Exception("모든 모델이 코드 생성을 실패했습니다.")

                report.status = TDDStatus.TESTING
                # 3. 샌드박스에서 각각 테스트 실행
                for cand in candidates:
                    await self._test_candidate(cand, test_file)

                attempt.candidates = candidates

                # 4. 결과 종합 (Synthesis)
                passed_candidates = [c for c in candidates if c.passed]

                if passed_candidates:
                    report.status = TDDStatus.PASSED
                    # 한 명만 통과했으면 그대로 우승, 여럿이면 심판이 결정
                    winner = await self._synthesize_results(passed_candidates, prompt)
                    attempt.winner_source = winner.source
                    report.winner_source = winner.source
                    report.final_code = winner.code
                    attempt.duration_ms = (time.time() - attempt_start) * 1000
                    report.attempts.append(attempt)
                    logger.info(
                        f"[OmniTDD] Iteration {iteration} Success! Winner: {winner.source}"
                    )

                    # Response Reconstructor: 코드 + 한국어 설명 생성
                    report.explanation = await self._reconstruct_response(
                        prompt, winner.code
                    )

                    if target_file_path:
                        try:
                            os.makedirs(
                                os.path.dirname(os.path.abspath(target_file_path)),
                                exist_ok=True,
                            )
                            with open(target_file_path, "w", encoding="utf-8") as tf:
                                tf.write(winner.code)
                            logger.info(
                                f"[OmniTDD] Saved winning code to target path: {target_file_path}"
                            )
                        except Exception as e:
                            logger.error(
                                f"[OmniTDD] Failed to write target file {target_file_path}: {e}"
                            )

                    break
                else:
                    logger.warning(
                        f"[OmniTDD] Iteration {iteration} failed for all candidates."
                    )
                    # 다음 라운드 피드백용 에러 저장
                    for c in candidates:
                        error_logs[c.source] = (
                            f"Code:\n{c.code}\nExit code: {c.exit_code}\nSTDOUT:\n{c.stdout}\nSTDERR:\n{c.stderr}"
                        )

                    attempt.duration_ms = (time.time() - attempt_start) * 1000
                    report.attempts.append(attempt)

            if report.status != TDDStatus.PASSED:
                report.status = TDDStatus.FAILED
                report.error = (
                    "Max iterations reached. All models failed to pass the tests."
                )

        except Exception as e:
            logger.error(f"[OmniTDD] Error: {e}")
            report.status = TDDStatus.FAILED
            report.error = str(e)
        finally:
            report.duration_ms = (time.time() - start_time) * 1000
            # Clean up
            shutil.rmtree(self.workspace_dir, ignore_errors=True)

        return report

    async def _test_candidate(self, cand: TDDCandidate, test_file_path: str):
        """특정 후보의 코드를 solution.py로 저장하고 pytest를 실행합니다."""
        main_file = os.path.join(self.workspace_dir, "solution.py")
        start = time.time()

        with open(main_file, "w", encoding="utf-8") as f:
            f.write(cand.code)

        cmd = ["python3", "-m", "pytest", test_file_path, "-v", "--tb=short"]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.workspace_dir,
            )
            stdout_bytes, stderr_bytes = await process.communicate()
            cand.stdout = stdout_bytes.decode("utf-8", errors="replace")
            cand.stderr = stderr_bytes.decode("utf-8", errors="replace")
            cand.exit_code = process.returncode
            cand.passed = cand.exit_code == 0
        except Exception as e:
            cand.exit_code = -1
            cand.stderr = str(e)
            cand.passed = False

        cand.duration_ms = (time.time() - start) * 1000

    async def _generate_local_baseline(self, prompt: str) -> Tuple[str, str]:
        """로컬 모델로부터 기준 테스트 코드(pytest)를 추출합니다."""
        sys_prompt = (
            "You are an expert Test-Driven Python Engineer. "
            "Given a requirement, you must produce BOTH the implementation code AND pytest test code. "
            "Output ONLY a single raw JSON object (no markdown fences, no explanations before or after). "
            'The JSON must have exactly two keys: "code" (the implementation) and "test_code" (the pytest tests). '
            "The test_code must import from 'solution' module (e.g. 'from solution import ...'). "
            'Example output format: {"code": "def add(a,b):\\n    return a+b", "test_code": "from solution import add\\n\\ndef test_add():\\n    assert add(1,2)==3"}'
        )
        user_prompt = f"Requirement:\n{prompt}\n\nReturn only the JSON object:"

        content = await self._call_llm(sys_prompt, user_prompt)
        # JSON 추출: 마크다운 펜스 안에 있을 수도 있고 바로 있을 수도 있음
        # 1차: 가장 바깥쪽 { ... } 블록 추출
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return data.get("code", ""), data.get("test_code", "")
            except json.JSONDecodeError:
                # 2차: 이스케이프 문제 → 코드 블록에서 분리 시도
                code_blocks = re.findall(
                    r"```(?:python)?\s*(.*?)\s*```", content, re.DOTALL
                )
                if len(code_blocks) >= 2:
                    return code_blocks[0], code_blocks[1]
                elif len(code_blocks) == 1:
                    return code_blocks[0], ""
        return "", ""

    async def _get_local_only_candidate(self, prompt: str) -> List[TDDCandidate]:
        """Adaptive Mode: 로컬 모델만으로 단독 코드 생성 (레이싱 스킵)."""
        logger.info("[OmniTDD] Adaptive mode — local model only (skip racing)")
        sys = "You are an expert Python engineer. Provide only the raw python code. No markdown formatting, no explanations."
        res = await self._call_llm(sys, f"Requirement:\n{prompt}")
        code = self._extract_python_code(res)
        if code:
            return [TDDCandidate(source=f"local({self.coding_model})", code=code)]
        return []

    async def _get_initial_candidates(self, prompt: str) -> List[TDDCandidate]:
        """모든 가용 두뇌에 코딩을 요청합니다."""
        logger.info("[OmniTDD] Racing all available models...")
        tasks = []

        # 1. 로컬 모델
        async def local_task():
            sys = "You are an expert Python engineer. Provide only the raw python code. No markdown formatting, no explanations."
            res = await self._call_llm(sys, f"Requirement:\n{prompt}")
            code = self._extract_python_code(res)
            return TDDCandidate(source=f"local({self.coding_model})", code=code)

        tasks.append(local_task())

        # 2. 외부 두뇌 (ChatGPT, Gemini 등)
        ext_prompt = f"You are an expert Python engineer. Implement the following requirement. Provide only the raw python code without markdown formatting or explanations.\n\nRequirement:\n{prompt}"

        async def external_task():
            try:
                resp = await self.brain_router.send(ext_prompt, strategy="compare")
                cands = []
                # Compare strategy returns a combined markdown report. We must parse it.
                if resp.success and "## 🧠 외부 두뇌 비교 결과" in resp.text:
                    blocks = resp.text.split("### [")
                    for block in blocks[1:]:
                        source_end = block.find("]")
                        if source_end != -1:
                            source = block[:source_end]
                            content = block[source_end + 1 :].split("---")[0].strip()
                            code = self._extract_python_code(content)
                            if code:
                                cands.append(TDDCandidate(source=source, code=code))
                return cands
            except Exception as e:
                logger.error(f"[OmniTDD] External brain task failed: {e}")
                return []

        tasks.append(external_task())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        candidates = []
        for r in results:
            if isinstance(r, TDDCandidate) and r.code:
                candidates.append(r)
            elif isinstance(r, list):
                candidates.extend(
                    c for c in r if isinstance(c, TDDCandidate) and c.code
                )

        logger.info(f"[OmniTDD] Received {len(candidates)} candidates.")
        return candidates

    async def _get_fixed_candidates(
        self, prompt: str, test_code: str, error_logs: Dict[str, str]
    ) -> List[TDDCandidate]:
        """실패한 각 두뇌에 자신의 에러 로그를 주어 버그 픽스를 요청합니다."""
        logger.info("[OmniTDD] Requesting bug fixes from all models...")
        tasks = []

        # 로컬 모델 픽스
        local_source = f"local({self.coding_model})"
        if local_source in error_logs:

            async def local_fix():
                sys = "You are an expert Python engineer. The previous code failed the tests. Provide only the raw fixed python code. No markdown formatting."
                user = f"Requirement:\n{prompt}\n\nTests:\n{test_code}\n\nMy Previous Attempt & Error:\n{error_logs[local_source]}\n\nPlease fix the code."
                res = await self._call_llm(sys, user)
                return TDDCandidate(
                    source=local_source, code=self._extract_python_code(res)
                )

            tasks.append(local_fix())

        # 외부 두뇌 픽스
        for source, error in error_logs.items():
            if source.startswith("local"):
                continue

            async def ext_fix(src=source, err=error):
                ext_prompt = f"You are an expert Python engineer. The previous code failed. Provide only the raw fixed python code. No markdown formatting.\n\nRequirement:\n{prompt}\n\nTests:\n{test_code}\n\nMy Previous Attempt & Error:\n{err}"
                resp = await self.brain_router.send(ext_prompt, target=src)
                if resp.success:
                    return TDDCandidate(
                        source=src, code=self._extract_python_code(resp.text)
                    )
                return None

            tasks.append(ext_fix())

        results = await asyncio.gather(*tasks, return_exceptions=True)
        candidates = [r for r in results if isinstance(r, TDDCandidate) and r.code]
        logger.info(f"[OmniTDD] Received {len(candidates)} fixed candidates.")
        return candidates

    async def _synthesize_results(
        self, passed_candidates: List[TDDCandidate], prompt: str
    ) -> TDDCandidate:
        """통과한 여러 후보 중 최고의 코드를 로컬 심판 모델이 채택합니다."""
        if len(passed_candidates) == 1:
            return passed_candidates[0]

        logger.info(
            f"[OmniTDD] Synthesizing {len(passed_candidates)} passing candidates..."
        )
        sys_prompt = "You are a senior principal engineer evaluating multiple working implementations."
        user_prompt = f"Requirement: {prompt}\n\n"

        for i, c in enumerate(passed_candidates):
            user_prompt += f"Implementation {i+1} (Source: {c.source}):\n```python\n{c.code}\n```\n\n"

        user_prompt += (
            "All implementations pass the tests. Choose the best one based on performance, "
            "readability, security, and thread-safety. "
            "Reply strictly with the integer index of the best implementation (e.g., '1' or '2')."
        )

        choice_str = await self._call_llm(sys_prompt, user_prompt)

        match = re.search(r"\d+", choice_str)
        if match:
            idx = int(match.group()) - 1
            if 0 <= idx < len(passed_candidates):
                return passed_candidates[idx]

        # 기본값으로 가장 짧은 코드(또는 첫 번째) 선택
        return passed_candidates[0]

    async def _reconstruct_response(
        self, original_prompt: str, winning_code: str
    ) -> str:
        """Response Reconstructor: 우승 코드를 기반으로 완전한 한국어 응답을 생성합니다.

        TDD 엔진의 핵심 품질 게이트. 코드-only 응답을
        '분석 → 코드 → 설명(복잡도/비교)' 3단 구조로 재구성합니다.
        """
        sys_prompt = (
            "당신은 시니어 소프트웨어 엔지니어이자 기술 교육자입니다. "
            "아래의 '사용자 원본 질문'과 '검증 완료된 코드'를 바탕으로 "
            "완전한 한국어 기술 응답을 작성하세요.\n\n"
            "반드시 다음 3단 구조를 지키세요:\n"
            "### 🔍 분석\n사용자 요구사항의 핵심 파악 (2~3문장)\n\n"
            "### 💻 구현 코드\n검증 완료된 코드를 그대로 ```python 블록으로 제시\n\n"
            "### 📊 설명\n"
            "- 각 방법/함수의 동작 원리를 간결하게 설명\n"
            "- 시간/공간 복잡도가 관련되면 Big-O 표기를 반드시 포함\n"
            "- 여러 방법 비교 시 비교 표(마크다운 테이블) 포함\n"
            "- '💡 팁:' 섹션으로 실무 활용 팁 제공\n\n"
            "규칙:\n"
            "- 코드는 수정하지 마세요 (이미 테스트 통과됨)\n"
            "- 응답은 반드시 한국어로 작성\n"
            "- 같은 문단을 반복하지 마세요"
        )
        user_prompt = (
            f"사용자 원본 질문:\n{original_prompt}\n\n"
            f"검증 완료된 코드:\n```python\n{winning_code}\n```"
        )
        try:
            explanation = await self._call_llm(sys_prompt, user_prompt)
            if explanation and len(explanation.strip()) > 50:
                return explanation.strip()
        except Exception as e:
            logger.warning(f"[OmniTDD] Response reconstruction failed: {e}")
        # 폴백: 최소한의 설명
        return f"### 💻 구현 코드\n\n```python\n{winning_code}\n```"

    def _extract_python_code(self, text: str) -> str:
        """마크다운이나 불필요한 텍스트에서 파이썬 코드만 추출합니다."""
        # 마크다운 코드 블록 찾기
        matches = re.findall(r"```(?:python)?\s*(.*?)\s*```", text, re.DOTALL)
        if matches:
            # 가장 긴 블록 반환 (보통 그게 정답)
            return max(matches, key=len)
        return text.strip()

    async def _call_llm(self, sys_prompt: str, user_prompt: str) -> str:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.coding_model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
            )
            if resp.status_code == 200:
                return resp.json().get("message", {}).get("content", "")
            else:
                logger.error(f"LLM API error: {resp.status_code}")
                return ""
