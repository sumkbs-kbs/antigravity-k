"""
Antigravity-K: Meta-Architect Engine (Level 3 자율 아키텍처 재설계)
================================================================
에이전트가 전체 시스템 아키텍처를 분석하고, 구조적 병목을 해결하기 위해
코어 엔진을 자율적으로 리팩터링 및 재설계합니다.

특징:
  - Macromutation (대규모 변이): 단일 파일이 아닌 여러 파일을 동시에 리팩터링
  - RSISandbox와 연동하여 100% 안전 보장 (실패 시 롤백)
  - 완전 자율 (Option B): 벤치마크 통과 시 자동 병합
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("antigravity_k.meta_architect")


@dataclass
class ArchitectureProposal:
    """아키텍처 변경 제안서"""
    proposal_id: str
    title: str
    target_files: List[str]
    description: str
    expected_benefit: str
    modifications: Dict[str, str] = field(default_factory=dict)  # filepath -> new_content
    passed: bool = False


class MetaArchitect:
    """시스템 전체를 조망하고 재설계하는 메타 아키텍트 엔진."""

    def __init__(self, project_root: str, ollama_url: str = "http://localhost:11434"):
        self.project_root = project_root
        self.ollama_url = ollama_url
        self._engine_dir = os.path.join(project_root, "src", "antigravity_k", "engine")

    def _get_architecture_context(self) -> str:
        """시스템의 현재 구조적 컨텍스트를 수집합니다."""
        context = []
        arch_file = os.path.join(self.project_root, "ARCHITECTURE.md")
        if os.path.exists(arch_file):
            with open(arch_file, "r", encoding="utf-8") as f:
                context.append(f"--- ARCHITECTURE.md ---\n{f.read()[:2000]}\n")

        # 코어 엔진 파일 목록 및 크기
        if os.path.exists(self._engine_dir):
            files = [f for f in os.listdir(self._engine_dir) if f.endswith(".py")]
            files_info = []
            for file in files:
                path = os.path.join(self._engine_dir, file)
                size = os.path.getsize(path)
                files_info.append(f"- {file} ({size} bytes)")
            context.append("--- Core Modules ---\n" + "\n".join(files_info))

        return "\n".join(context)

    def analyze_and_propose(self, performance_data: Dict[str, Any]) -> Optional[ArchitectureProposal]:
        """현재 시스템의 병목을 분석하고 리팩터링을 제안합니다."""
        logger.info("[Meta-Architect] 전체 아키텍처 분석 및 제안 시작...")
        
        context = self._get_architecture_context()
        perf_text = json.dumps(performance_data, ensure_ascii=False, indent=2)

        prompt = (
            "[ROLE] 당신은 최고 수준의 AI 아키텍트(Meta-Architect)입니다.\n"
            "목표는 현재 AI 에이전트 코어 시스템의 병목을 발견하고 아키텍처를 개선하는 것입니다.\n\n"
            f"{context}\n\n"
            f"--- 최근 성능 데이터 ---\n{perf_text}\n\n"
            "[TASK]\n"
            "위 데이터를 바탕으로 가장 필요한 1가지 대규모 리팩터링 또는 신규 모듈 도입을 제안하세요.\n"
            "제안은 다음 JSON 형식으로 출력해야 합니다:\n"
            '{"title": "...", "description": "...", "target_files": ["file1.py", "file2.py"], "expected_benefit": "..."}\n'
            "오직 JSON만 출력하세요. (마크다운 불필요)"
        )

        try:
            response = self._call_llm(prompt, "deepseek-v4", 1024)
            data = self._extract_json(response)
            if data and "title" in data:
                proposal = ArchitectureProposal(
                    proposal_id=f"arch_{int(os.path.getmtime(self._engine_dir))}",
                    title=data["title"],
                    target_files=data.get("target_files", []),
                    description=data["description"],
                    expected_benefit=data["expected_benefit"],
                )
                logger.info(f"[Meta-Architect] 제안 생성: {proposal.title}")
                return proposal
        except Exception as e:
            logger.error(f"[Meta-Architect] 제안 생성 실패: {e}")
        return None

    def execute_proposal(self, proposal: ArchitectureProposal) -> bool:
        """제안된 아키텍처 변경을 샌드박스 내에서 실행합니다 (Option B: 완전 자율)."""
        logger.info(f"[Meta-Architect] 리팩터링 실행 시도: {proposal.title}")
        
        try:
            from antigravity_k.engine.rsi_sandbox import RSISandbox
            sandbox = RSISandbox(project_root=self.project_root)
            
            # 파일 내용 읽기
            file_contents = {}
            for filename in proposal.target_files:
                if sandbox.is_immutable(filename):
                    logger.warning(f"[Meta-Architect] 불변 파일({filename}) 수정 시도 차단.")
                    return False
                
                path = os.path.join(self._engine_dir, filename)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        file_contents[filename] = f.read()

            # LLM에게 수정된 코드 요청
            for filename, content in file_contents.items():
                new_content = self._generate_modified_code(filename, content, proposal)
                if new_content:
                    proposal.modifications[filename] = new_content

            if not proposal.modifications:
                logger.warning("[Meta-Architect] 생성된 수정 코드가 없습니다.")
                return False

            # Sandbox 적용 및 검증 (Option B)
            with sandbox.safe_mutation(f"meta_architect_{proposal.proposal_id}"):
                all_passed = True
                
                # 1. 파일 임시 덮어쓰기
                for filename, new_code in proposal.modifications.items():
                    path = os.path.join(self._engine_dir, filename)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_code)
                
                # 2. 샌드박스 일괄 검증
                for filename, new_code in proposal.modifications.items():
                    val_result = sandbox.validate_mutation(filename, new_code)
                    if val_result.get("ast", "").value == "fail" or val_result.get("tests", "").value == "fail":
                        all_passed = False
                        logger.error(f"[Meta-Architect] 샌드박스 검증 실패: {filename} -> {val_result}")
                        break
                
                if not all_passed:
                    raise Exception("Meta-Architect macromutation failed validation. Rolling back.")

                proposal.passed = True
                logger.info(f"[Meta-Architect] 리팩터링 완전 통과 및 병합 완료: {proposal.title}")
                return True

        except Exception as e:
            logger.error(f"[Meta-Architect] 실행 중 롤백됨: {e}")
            return False

    def _generate_modified_code(self, filename: str, original_code: str, proposal: ArchitectureProposal) -> str:
        prompt = (
            f"[ROLE] 당신은 시니어 소프트웨어 아키텍트입니다.\n"
            f"[TASK] 아래 아키텍처 제안을 수행하기 위해 '{filename}' 코드를 리팩터링하세요.\n\n"
            f"제안: {proposal.title}\n설명: {proposal.description}\n\n"
            f"--- 원본 {filename} ---\n{original_code}\n\n"
            "개선된 전체 Python 코드를 출력하세요. 다른 텍스트 없이 순수 코드만 출력하세요. "
            "반드시 완전한 코드를 출력해야 합니다."
        )
        try:
            resp = self._call_llm(prompt, "deepseek-v4", 8192)
            # 코드 블록 추출
            matches = re.findall(r"```(?:python)?\s*(.*?)\s*```", resp, re.DOTALL)
            if matches:
                return max(matches, key=len)
            return resp.strip()
        except Exception:
            return ""

    def _call_llm(self, prompt: str, model: str, num_predict: int) -> str:
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": num_predict, "temperature": 0.2},
        }
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
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
