"""EvolutionManager — Self-Evolution 파이프라인.

=============================================
Hermes Agent Self-Evolution의 핵심 원리를 도입하여,
과거의 에러/실패 기록(Vault)을 바탕으로 에이전트가 스스로의 지시문(SKILL.md)과 프롬프트를 개선합니다.
"""

import logging

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.vault import VaultEngine

logger = logging.getLogger("antigravity_k.engine.evolution")

EVOLUTION_PROMPT_TEMPLATE = """
You are the GEPA (Genetic-Pareto Prompt Evolution) Optimizer.

Your task is to evolve and improve an AI Agent's skill or system prompt to prevent it from making past mistakes.

[ORIGINAL TEXT]
{original_text}

[PAST FAILURES & LESSONS LEARNED]
{failures_context}

[OBJECTIVE]
Analyze the past failures carefully. Identify WHY the original text failed or was insufficient.
Rewrite the original text to be more robust, explicit, and defensively programmed against these specific failure modes.
Do NOT completely change the purpose of the text. Keep the same structure
(e.g., Markdown with YAML frontmatter if present).
Add a specific "Evolution Notes" or "Common Pitfalls" section at the end of
the text to explicitly guard against the past mistakes.

Return ONLY the fully evolved text (including frontmatter if it had one), with no preamble or explanation.
"""


class EvolutionManager:
    """Manages self-directed code evolution cycles with validation gates."""

    def __init__(self, model_manager: ModelManager, vault_engine: VaultEngine):
        """Initialize the EvolutionManager.

        Args:
            model_manager (ModelManager): ModelManager model manager.
            vault_engine (VaultEngine): VaultEngine vault engine.

        """
        if vault_engine is None:
            raise ValueError(
                "EvolutionManager requires a valid VaultEngine instance. "
                "Ensure ANTIGRAVITY_VAULT_PATH is set and VaultEngine is initialized.",
            )
        self.manager = model_manager
        self.vault = vault_engine
        self.skills_dir = self.vault.vault_path / ".agent" / "skills"

    def _gather_failures(self, query: str, limit: int = 5) -> str:
        """Vault(Second Brain)에서 과거 에러 로그와 교훈을 검색합니다."""
        if not self.vault.sync_rag:
            return "No past failure data available (RAG disabled)."

        try:
            results = self.vault.vector_store.search(f"Error Failure {query}", n_results=limit)
            context = []
            for doc in results:
                context.append(doc.get("text", ""))
            return "\n\n---\n\n".join(context) if context else "No relevant failures found."
        except Exception:
            logger.exception("Failed to gather failures for evolution")
            return "Error retrieving past data."

    def evolve_skill(self, skill_name: str, target_model: str = "qwen3.6:latest") -> str | None:
        """특정 스킬을 과거 실패 기록을 바탕으로 진화시킵니다."""
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        if not skill_path.exists():
            logger.error("Skill not found: %s", skill_path)
            return None

        with open(skill_path, encoding="utf-8") as f:
            original_text = f.read()

        # 관련된 에러 및 교훈 수집
        failures_context = self._gather_failures(skill_name)

        prompt = EVOLUTION_PROMPT_TEMPLATE.format(
            original_text=original_text,
            failures_context=failures_context,
        )

        logger.info("Starting evolution for skill: %s", skill_name)
        try:
            evolved_text = self.manager.generate(
                prompt=prompt,
                target=target_model,
                temperature=0.7,
                max_tokens=4096,
            )

            # 클린업 (마크다운 코드 블록 제거)
            if evolved_text.startswith("```markdown\n"):
                evolved_text = evolved_text[12:]
            if evolved_text.endswith("```"):
                evolved_text = evolved_text[:-3]

            # 안전하게 Draft 파일로 저장 (Human-in-the-loop)
            draft_path = self.skills_dir / skill_name / "SKILL_EVOLVED.md"
            with open(draft_path, "w", encoding="utf-8") as f:
                f.write(evolved_text.strip())

            logger.info("Successfully evolved skill '%s'. Saved to %s", skill_name, draft_path)
            return str(draft_path)

        except Exception:
            logger.exception("Evolution failed")
            return None

    def evolve_system_prompt(self, target_model: str = "qwen3.6:latest") -> str | None:
        """시스템 프롬프트를 과거 실패 기록을 바탕으로 진화시킵니다."""
        # System prompt path assuming it's in config.yaml or a specific file.
        # For Antigravity-K, we use config.yaml or orchestrator.py directly.
        # Let's save the evolved system prompt to the vault root for review.
        original_text = (
            "You are Antigravity, a powerful agentic AI coding assistant designed by the Google Deepmind team"
        )
        "working on Advanced Agentic Coding."

        failures_context = self._gather_failures("system_prompt_failures", limit=10)

        prompt = EVOLUTION_PROMPT_TEMPLATE.format(
            original_text=original_text,
            failures_context=failures_context,
        )

        logger.info("Starting evolution for System Prompt")
        try:
            evolved_text = self.manager.generate(
                prompt=prompt,
                target=target_model,
                temperature=0.7,
                max_tokens=4096,
            )

            # 클린업
            if evolved_text.startswith("```markdown\n"):
                evolved_text = evolved_text[12:]
            if evolved_text.endswith("```"):
                evolved_text = evolved_text[:-3]

            draft_path = self.vault.vault_path / "SYSTEM_PROMPT_EVOLVED.md"
            with open(draft_path, "w", encoding="utf-8") as f:
                f.write(evolved_text.strip())

            logger.info("Successfully evolved System Prompt. Saved to %s", draft_path)
            return str(draft_path)

        except Exception:
            logger.exception("System prompt evolution failed")
            return None
