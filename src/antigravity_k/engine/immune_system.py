import ast
import os
import json
import logging
from pathlib import Path
from typing import Optional

from .model_manager import ModelManager
from .vault import VaultEngine

logger = logging.getLogger(__name__)

# 세션당 최대 자가 수복 시도 횟수
_MAX_HEAL_ATTEMPTS_PER_SESSION = 3


class ImmuneSystem:
    """
    Antigravity-K 자가 수복/자가 발전 엔진 (ECA Phase 2)
    에이전트가 동작 중 치명적 오류나 무한루프에 빠졌을 때,
    자신의 엔진 코드를 스스로 분석하고 패치하는 면역 체계입니다.

    안전장치:
    - 세션당 최대 3회 시도 제한
    - 패치를 _drafts/ 디렉토리에 먼저 저장 (HITL 검토용)
    - Python AST 파싱으로 구문 유효성 검증
    - Vault 스냅샷 자동 생성 (롤백 가능)
    """

    _session_heal_count: int = 0  # 클래스 레벨 세션 카운터

    def __init__(
        self,
        project_root: str,
        model_manager: ModelManager,
        vault_engine: Optional[VaultEngine],
    ):
        self.project_root = project_root
        self.model_manager = model_manager
        self.vault_engine = vault_engine

    def heal(self, error_trace: str, tool_name: str, args_context: str) -> str:
        """
        주어진 에러 로그를 바탕으로 패치 초안을 생성합니다.
        패치는 _drafts/ 에 저장되며, 자동 적용하지 않습니다 (HITL 패턴).
        반환값: 사용자에게 보고할 수복 결과 메시지
        """
        # 안전장치 0: 세션당 시도 횟수 제한
        ImmuneSystem._session_heal_count += 1
        if ImmuneSystem._session_heal_count > _MAX_HEAL_ATTEMPTS_PER_SESSION:
            logger.warning(
                f"[IMMUNE SYSTEM] Heal attempt limit reached ({_MAX_HEAL_ATTEMPTS_PER_SESSION})"
            )
            return (
                f"🚨 **[IMMUNE SYSTEM]** 세션 내 자가 수복 시도 횟수 제한"
                f"({_MAX_HEAL_ATTEMPTS_PER_SESSION}회)에 도달했습니다. 수동 개입이 필요합니다."
            )

        logger.error(
            f"[IMMUNE SYSTEM TRIGGERED] Self-healing started for tool {tool_name}"
        )

        # 안전장치 1: 백업 스냅샷 생성
        snapshot_msg = ""
        if self.vault_engine:
            try:
                snap_hash = self.vault_engine.create_snapshot(
                    f"Auto-backup before healing {tool_name} error"
                )
                if snap_hash:
                    snapshot_msg = f"Vault snapshot created: {snap_hash[:7]}."
            except Exception as e:
                snapshot_msg = f"Vault snapshot failed: {e}"

        prompt = f"""You are the Antigravity-K MetaAgent (Immune System).
Your core engine just encountered a critical repetitive error. You need to write a code patch for YOURSELF.

Error Trace/Info:
{error_trace}

Tool Attempted: {tool_name}
Args Used: {args_context}

Analyze the error. Return a JSON block specifying exactly which file to modify in the `src/antigravity_k/` directory, and provide a single chunk of replacement code.
Format your response ONLY as this JSON (no markdown wrapping, no extra text):
{{
    "target_file": "src/antigravity_k/...",
    "search_content": "exact code lines to replace",
    "replace_content": "new code lines to insert",
    "explanation": "why this fixes the issue"
}}
If the error is a hallucination or impossible to fix, set target_file to empty string.
"""

        try:
            # C-2 수정: model_id= → target= (ModelManager.generate() 시그니처)
            default_model = self.model_manager._registry.get_default("reasoning")
            target_name = default_model.name if default_model else "qwen3.6:latest"
            response = self.model_manager.generate(prompt, target=target_name)

            import re

            clean = response.strip()
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL)
            if json_match:
                clean = json_match.group(1)
            else:
                start = clean.find("{")
                end = clean.rfind("}")
                if start != -1 and end != -1:
                    clean = clean[start : end + 1]
            data = json.loads(clean.strip())

            target_file = data.get("target_file", "")
            if not target_file:
                return (
                    "🚨 [IMMUNE SYSTEM] Analyzed the error but determined it could not "
                    "be safely self-patched. Manual intervention required."
                )

            abs_path = os.path.join(self.project_root, target_file)
            search_code = data.get("search_content", "")
            replace_code = data.get("replace_content", "")

            if not os.path.exists(abs_path) or not search_code:
                return (
                    f"⚠️ [IMMUNE SYSTEM FAILED] Target file `{target_file}` not found "
                    f"or search content is empty. Healing aborted."
                )

            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            if search_code not in content:
                return (
                    f"⚠️ [IMMUNE SYSTEM FAILED] The generated patch search string was "
                    f"not found in `{target_file}`. Healing aborted."
                )

            # 안전장치 2: 패치 적용 후 AST 구문 검증 (Python 파일만)
            new_content = content.replace(search_code, replace_code, 1)
            if target_file.endswith(".py"):
                if not self._validate_syntax(new_content, target_file):
                    return (
                        f"⚠️ [IMMUNE SYSTEM FAILED] Generated patch causes syntax errors "
                        f"in `{target_file}`. Healing aborted for safety."
                    )

            # 안전장치 3: 파일 덮어쓰기로 자동 패치 적용 (Max Autonomy)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # 변경 이력 기록을 위해 patch_log 폴더에 저장
            draft_dir = Path(self.project_root) / ".agent" / "memory" / "immune_patches"
            draft_dir.mkdir(parents=True, exist_ok=True)
            draft_path = (
                draft_dir / f"patch_{tool_name}_{ImmuneSystem._session_heal_count}.json"
            )
            with open(draft_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "target_file": target_file,
                        "search_content": search_code,
                        "replace_content": replace_code,
                        "explanation": data.get("explanation", ""),
                        "error_trace": error_trace[:2000],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            return (
                f"💉 **[IMMUNE SYSTEM] 자동 수복 완료!**\n"
                f"- 대상: `{target_file}` 코드가 스스로 수정되었습니다.\n"
                f"- 사유: {data.get('explanation')}\n"
                f"- {snapshot_msg}\n\n"
                f"자율 판단에 따라 즉시 핫픽스를 적용했습니다. 도구를 다시 호출해 보세요!"
            )

        except Exception as e:
            logger.error(f"Immune system crashed during healing: {e}")
            return (
                f"🔥 [IMMUNE SYSTEM FATAL] MetaAgent crashed during self-healing: {e}"
            )

    @staticmethod
    def _validate_syntax(source: str, filename: str) -> bool:
        """Python 소스 코드의 AST 구문 유효성을 검증합니다."""
        try:
            ast.parse(source, filename=filename)
            return True
        except SyntaxError as e:
            logger.warning(
                f"[IMMUNE SYSTEM] Syntax validation failed for {filename}: {e}"
            )
            return False

    @classmethod
    def reset_session_counter(cls) -> None:
        """세션 카운터를 초기화합니다 (새 세션 시작 시 호출)."""
        cls._session_heal_count = 0
