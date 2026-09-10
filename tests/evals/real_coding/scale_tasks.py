from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScaleQuestion:
    qid: str
    question: str
    expected_symbols: tuple[str, ...]
    expected_files: tuple[str, ...]


TASKS: tuple[ScaleQuestion, ...] = (
    ScaleQuestion(
        qid="find_compressor",
        question="Which class compresses context before sending to the LLM, and which file defines it?",
        expected_symbols=("HeadroomCompressor", "ContextShaper"),
        expected_files=("headroom_compressor.py", "context_shaper.py"),
    ),
    ScaleQuestion(
        qid="find_sandbox_executor",
        question="Where is the fail-closed sandbox executor that bounds shell commands defined?",
        expected_symbols=("SandboxRunner",),
        expected_files=("sandbox.py",),
    ),
    ScaleQuestion(
        qid="find_capability_policy",
        question="Which module enforces the workspace capability policy before tool execution?",
        expected_symbols=("PermissionGate", "ToolGuardrailManager"),
        expected_files=("permission_gate.py", "tool_guardrail_manager.py"),
    ),
    ScaleQuestion(
        qid="find_parity_report",
        question="Which module produces the Claude Opus parity comparison report?",
        expected_symbols=("ParityReport",),
        expected_files=("parity.py", "report_models.py"),
    ),
    ScaleQuestion(
        qid="find_profile_contract",
        question="Where is the strict local-70B evaluation profile contract defined and validated?",
        expected_symbols=("LocalEvaluationProfile", "preflight_profile"),
        expected_files=("models.py", "preflight.py"),
    ),
    ScaleQuestion(
        qid="find_graphify",
        question="Which module builds the codebase knowledge graph from source files?",
        expected_symbols=("build_graph",),
        expected_files=("graphify_builder.py",),
    ),
    ScaleQuestion(
        qid="find_trial_isolation",
        question="Which module isolates evaluation trials into fresh temporary worktrees with sandbox grants?",
        expected_symbols=("TrialEnvironment", "build_bounded_evaluation_session"),
        expected_files=("trial_environment.py", "bounded_execution.py"),
    ),
    ScaleQuestion(
        qid="find_ponytail",
        question="Where is the lazy-senior-developer system directive defined?",
        expected_symbols=("LAZY_SENIOR_DIRECTIVE", "apply_ponytail"),
        expected_files=("ponytail_shaper.py",),
    ),
)
