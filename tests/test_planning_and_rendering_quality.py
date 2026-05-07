from pathlib import Path

from antigravity_k.engine.orchestrator import OrchestratorAgent
from antigravity_k.engine.quality_gate import QualityGate, QualityGrade


class _FakeManager:
    def is_loaded(self, name):
        return True

    def stream_generate(self, *args, **kwargs):
        yield "ok"


class _QualityRetryManager:
    def __init__(self):
        self.calls = 0

    def is_loaded(self, name):
        return True

    def stream_generate(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            yield "```python\ndef gcd(a, b):\n    return a\n```"
        else:
            yield (
                "GCD는 최대공약수를 구하는 함수입니다.\n\n"
                "```python\ndef gcd(a, b):\n    while b:\n        a, b = b, a % b\n    return abs(a)\n```\n\n"
                "시간복잡도는 `O(log(min(a, b)))`, 공간복잡도는 `O(1)`입니다."
            )


def test_orchestrator_planning_mode_skips_simple_coding_request(tmp_path):
    orchestrator = OrchestratorAgent(
        model_manager=_FakeManager(),
        vault_engine=None,
        project_root=str(tmp_path),
    )

    assert (
        orchestrator._requires_planning_mode(
            "coding", [{"role": "user", "content": "Python으로 GCD 함수를 작성해줘"}]
        )
        is False
    )


def test_orchestrator_planning_mode_keeps_large_refactor_guard(tmp_path):
    orchestrator = OrchestratorAgent(
        model_manager=_FakeManager(),
        vault_engine=None,
        project_root=str(tmp_path),
    )

    assert (
        orchestrator._requires_planning_mode(
            "coding",
            [
                {
                    "role": "user",
                    "content": "플러그인 시스템을 추가하고 아키텍처를 대규모 리팩토링해줘",
                }
            ],
        )
        is True
    )


def test_quality_gate_does_not_force_planning_for_small_code_answer():
    output = """GCD는 두 수의 최대공약수를 구하는 함수입니다.

```python
def gcd(a, b):
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a
```

시간복잡도는 `O(log(min(a, b)))`, 공간복잡도는 `O(1)`입니다. 입력값 0과 음수도
함께 테스트하면 실제 사용 시 안정성을 높일 수 있습니다.
"""

    score = QualityGate().evaluate(
        "coding", "Python으로 GCD 함수를 작성하고 복잡도도 알려줘", output
    )

    assert score.grade in (QualityGrade.A, QualityGrade.B)
    assert (
        "복잡한 태스크에서 Planning Mode(계획안 및 승인 요청) 누락 (재시도 필요)"
        not in score.issues
    )


def test_dashboard_carousel_renderer_escapes_model_output():
    source = Path("dashboard/src/pages/chat.js").read_text(encoding="utf-8")

    assert "safeCarouselImageSrc" in source
    assert "escapeMarkdownHTML(slideHtml)" in source
    assert "%%CAROUSEL_IMAGE_" in source
    carousel_source = source[
        source.index("safeCarouselImageSrc") : source.index("// 인라인 코드 복원")
    ]
    assert "javascript:" not in carousel_source


def test_dashboard_markdown_links_are_sanitized():
    source = Path("dashboard/src/pages/chat.js").read_text(encoding="utf-8")

    assert "safeMarkdownUrl" in source
    assert 'href="$2"' not in source
    assert 'rel="noopener noreferrer"' in source


def test_dashboard_chat_output_uses_codex_like_reading_style():
    source = Path("dashboard/src/styles/index.css").read_text(encoding="utf-8")

    assert "--chat-content-width: 780px;" in source
    assert "--chat-font-size: 14.5px;" in source
    assert "--chat-line-height: 1.68;" in source
    assert ".message.assistant," in source
    assert "max-width: var(--chat-content-width);" in source
    assert "font-size: var(--chat-font-size);" in source
    assert ".message.assistant .bubble strong" in source
    assert ".md-h1 { font-size: 1.18em; }" in source
    assert "min-width: 680px;" in source
    assert "white-space: nowrap;" in source
    assert "letter-spacing: -0." not in source


def test_agent_manager_is_mobile_accessible_and_project_scoped():
    source = Path("dashboard/src/pages/chat.js").read_text(encoding="utf-8")

    assert 'id="mobile-agent-mgr-btn"' in source
    assert "getAgentWorkspaceQuery" in source
    assert "filterAgentTasksForWorkspace" in source
    assert "currentWorkspacePath" in source
    assert "'/api/kanban/tasks' + getAgentWorkspaceQuery()" in source
    assert "const tasks = Array.isArray(data.tasks) ? data.tasks : null;" in source
    assert "renderAgentTasks(filterAgentTasksForWorkspace(tasks));" in source
    assert "agent-manager-project" in source
    assert "task-remove-btn" in source


def test_orchestrator_runs_quality_retry_for_code_only_answer(tmp_path, monkeypatch):
    manager = _QualityRetryManager()

    def fake_ceo_analyze(self, user_message, target_model):
        yield {
            "task_type": "coding",
            "delegate_to": "WORKER",
            "reasoning": "quality retry test",
            "refined_prompt": user_message,
        }

    monkeypatch.setattr(OrchestratorAgent, "_ceo_analyze", fake_ceo_analyze)

    orchestrator = OrchestratorAgent(
        model_manager=manager,
        vault_engine=None,
        project_root=str(tmp_path),
    )

    output = "".join(
        orchestrator.run_stream(
            [
                {
                    "role": "user",
                    "content": "Python으로 GCD 함수를 작성하고 시간복잡도도 알려줘",
                }
            ],
            target_model="test-model",
            max_steps=2,
        )
    )

    assert manager.calls == 2
    assert "품질 미달" in output
    assert "O(log(min(a, b)))" in output
