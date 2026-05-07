#!/usr/bin/env python3
"""
Antigravity-K: Meta-Evolution Agent (Phase 7)
==============================================
본 프로그램 스스로 소스코드를 수정하고, 테스트를 실행하며,
문서(test_process.md 등)를 업데이트하는 자율 진화 에이전트.
"""

import os
import json
import logging
import shutil
import time
from typing import Dict, List, Optional, Generator
from pathlib import Path
import re

logger = logging.getLogger("meta_evolution")


class BackupManager:
    """코드 변경 전 스냅샷 백업 및 롤백을 담당하는 매니저"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / ".evolution_backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.current_snapshot: Optional[Path] = None

    def create_snapshot(self, target_files: List[str]) -> str:
        """수정 예정 파일들의 스냅샷을 만듭니다."""
        snapshot_id = f"snap_{int(time.time())}"
        snapshot_path = self.backup_dir / snapshot_id
        snapshot_path.mkdir(exist_ok=True)

        for file_rel_path in target_files:
            src = self.project_root / file_rel_path
            if src.exists():
                dst = snapshot_path / file_rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        self.current_snapshot = snapshot_path
        return snapshot_id

    def rollback(self) -> bool:
        """가장 최근 스냅샷으로 롤백합니다."""
        if not self.current_snapshot or not self.current_snapshot.exists():
            return False

        try:
            for root, _, files in os.walk(self.current_snapshot):
                for file in files:
                    backup_file = Path(root) / file
                    rel_path = backup_file.relative_to(self.current_snapshot)
                    target_file = self.project_root / rel_path
                    shutil.copy2(backup_file, target_file)
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False


class MetaEvolutionAgent:
    """
    프로그램의 자기 진화(Self-Programming) 루프를 제어합니다.
    Planning -> Execution (Edit) -> Test -> Documentation.
    """

    def __init__(self, model_manager, tool_executor, project_root: str = "."):
        self.manager = model_manager
        self.tool_executor = tool_executor
        self.project_root = project_root
        self.backup_manager = BackupManager(project_root)
        self.max_retries = 3

    def evolve(
        self, requirement: str, target_files: List[str] = None
    ) -> Generator[str, None, str]:
        """
        요구사항에 맞춰 코드를 수정하고 검증하는 메인 루프 (Generator로 스트리밍).
        """
        yield "🧬 **[Meta-Evolution]** 자율 진화 시퀀스 시작...\n"

        if not target_files:
            # 1. 파일 추론 (간소화: LLM으로 추론해야 하나 여기서는 전체로 잡음)
            yield "ℹ️ 수정 대상 파일이 명시되지 않아 기본 파일들로 범위를 설정합니다.\n"
            target_files = [
                "src/antigravity_k/engine/orchestrator.py",
                "test_process.md",
            ]

        yield f"🔒 안전망: 대상 파일 백업 중... ({', '.join(target_files)})\n"
        self.backup_manager.create_snapshot(target_files)

        retry_count = 0
        success = False
        final_report = ""

        while retry_count <= self.max_retries:
            yield f"\n🔄 **[Iteration {retry_count + 1}/{self.max_retries + 1}]** 코드 작성 및 수정 진행...\n"

            # 2. 코드 수정 Action (LLM Prompting & Execution)
            # 여기서는 모델에게 현재 코드를 주고, 패치(Patch) 형태나 도구 호출을 유도합니다.
            # (구현 편의를 위해 도구 호출을 직접 에뮬레이션 하거나 manager.generate 활용)

            prompt = self._build_evolution_prompt(requirement, target_files)
            response = self.manager.generate(
                prompt=prompt,
                model="hf.co/Jiunsong/SuperGemma4-31b-abliterated-GGUF:latest",  # SuperGemma4를 워커로 사용
                system_prompt="You are an autonomous AI software engineer. Generate a specific implementation plan and XML tool calls to edit files.",
            )

            yield "🤖 **[SuperGemma4]** 코드 변경사항 도출 완료.\n"

            # 여기서 response 내의 <tool_call>을 파싱하여 tool_executor로 실행
            tool_calls = self._extract_tool_calls(response.text)
            for tc in tool_calls:
                yield f"🛠️ 도구 실행: {tc['name']}...\n"
                try:
                    self.tool_executor.execute(tc["name"], tc.get("arguments", {}))
                except Exception as e:
                    yield f"⚠️ 도구 실행 에러: {e}\n"

            # 3. 테스트 실행 (pytest)
            yield "🧪 자체 검증 테스트(pytest) 실행 중...\n"
            test_result = self.tool_executor.execute(
                "shell_run", {"command": "python3 -m pytest tests/"}
            )

            if (
                "failed" in test_result.lower()
                or "error" in test_result.lower()
                and "passed" not in test_result.lower()[-50:]
            ):
                # Test failed
                yield "❌ 테스트 실패 감지. 에러 로그 분석 중...\n"
                retry_count += 1
                requirement = f"이전 수정본에서 테스트가 실패했습니다. 다음 에러를 고치세요:\n{test_result[-1000:]}"
            else:
                success = True
                final_report = "✅ 테스트 통과! 진화 성공."
                yield final_report + "\n"
                break

        if not success:
            yield "\n🚨 **[CRITICAL]** 복구 불가능한 에러 발생. 원본 코드로 롤백합니다...\n"
            if self.backup_manager.rollback():
                yield "🔙 롤백 성공. 시스템이 안전한 상태로 복원되었습니다.\n"
            else:
                yield "⚠️ 롤백 실패. 수동 확인이 필요합니다.\n"
            return "진화 실패 (롤백됨)"

        # 4. 문서 업데이트 (test_process.md)
        yield "\n📝 테스트 프로시저(test_process.md) 및 문서 자동 업데이트 중...\n"
        self._update_documentation(requirement)

        yield "\n🎉 **[Meta-Evolution 완료]** 본 프로그램 스스로 기능 고도화를 마쳤습니다!\n"
        return "진화 성공"

    def _build_evolution_prompt(self, requirement: str, target_files: List[str]) -> str:
        # 실제 구현에서는 타겟 파일의 내용을 읽어서 첨부해야 합니다.
        contents = ""
        for f in target_files:
            try:
                with open(os.path.join(self.project_root, f), "r") as fp:
                    contents += f"\n--- {f} ---\n{fp.read()[:2000]}... (truncated)\n"
            except Exception:
                pass

        return f"""
        Requirement: {requirement}

        Target Files Content:
        {contents}

        You MUST use tool calls to modify the files.
        Use <tool_call>{{"name": "write_file", "arguments": {{"file_path": "...", "content": "..."}}}}</tool_call>
        """

    def _extract_tool_calls(self, text: str) -> List[Dict]:
        calls = []
        matches = re.finditer(r"<tool_call>\s*({.*?})\s*</tool_call>", text, re.DOTALL)
        for m in matches:
            try:
                calls.append(json.loads(m.group(1)))
            except Exception:
                pass
        return calls

    def _update_documentation(self, requirement: str):
        """test_process.md 및 test_report.md를 업데이트하는 로직"""
        test_proc_path = os.path.join(self.project_root, "test_process.md")
        if not os.path.exists(test_proc_path):
            return

        try:
            with open(test_proc_path, "a", encoding="utf-8") as f:
                f.write("\n---\n\n## 🔧 Meta-Evolution 자율 검증 이력\n")
                f.write(f"- **업데이트 요구사항**: {requirement}\n")
                f.write("- **상태**: 자동 수정 및 pytest 통과 완료\n")
                f.write("- **검증결과**: PASS\n")
        except Exception as e:
            logger.error(f"Failed to update documentation: {e}")
