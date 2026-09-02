import pytest

from antigravity_k.engine.approval_manager import (
    ApprovalManager,
    ApprovalStatus,
    get_approval_manager,
    reset_approval_manager,
)
from antigravity_k.engine.approval_review import (
    ApprovalReviewDecision,
    ApprovalReviewEngine,
    ApprovalReviewInput,
    LocalModelApprovalReviewProvider,
)


def test_low_risk_read_only_request_is_recommended_for_approval() -> None:
    review = ApprovalReviewEngine().review(
        ApprovalReviewInput(
            tool_name="read_file",
            tool_args={"file_path": "README.md"},
            risk_level="low",
            description="README 확인",
            diff_preview="",
        ),
    )

    assert review.decision is ApprovalReviewDecision.APPROVE
    assert review.risk_score < 0.4
    assert "read_only" in review.reason_codes


def test_secret_or_destructive_request_is_recommended_for_denial() -> None:
    review = ApprovalReviewEngine().review(
        ApprovalReviewInput(
            tool_name="write_file",
            tool_args={"file_path": ".env", "content": "API_KEY=secret"},
            risk_level="high",
            description="환경 변수 파일 갱신",
            diff_preview="+API_KEY=secret",
        ),
    )

    assert review.decision is ApprovalReviewDecision.DENY
    assert review.risk_score >= 0.8
    assert "sensitive_target" in review.reason_codes


def test_unknown_or_failed_review_is_fail_closed() -> None:
    review = ApprovalReviewEngine().review(
        ApprovalReviewInput(
            tool_name="",
            tool_args={},
            risk_level="unknown",
            description="",
            diff_preview="",
        ),
    )

    assert review.decision is ApprovalReviewDecision.ESCALATE
    assert "insufficient_context" in review.reason_codes


def test_approval_request_exposes_review_without_changing_user_status() -> None:
    manager = ApprovalManager(default_timeout_sec=10)
    request = manager.request_approval(
        "read_file",
        {"file_path": "README.md"},
        "low",
        "README 확인",
    )

    payload = request.to_dict()

    assert request.status is ApprovalStatus.PENDING
    auto_review = payload["auto_review"]
    assert auto_review is not None
    assert auto_review["decision"] == "approve"
    assert auto_review["reviewer"] == "policy-v1"


def test_review_provider_failure_escalates_without_approving() -> None:
    class BrokenProvider:
        def review(self, _request: ApprovalReviewInput):
            raise RuntimeError("local reviewer unavailable")

    manager = ApprovalManager(review_provider=BrokenProvider())
    request = manager.request_approval("write_file", {"file_path": "app.py"}, "high", "파일 수정")

    assert request.status is ApprovalStatus.PENDING
    assert request.auto_review is not None
    assert request.auto_review.decision is ApprovalReviewDecision.ESCALATE
    assert request.auto_review.reviewer == "policy-fail-closed"


def test_local_model_review_is_clamped_by_policy_and_names_reviewer() -> None:
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return '{"decision":"approve","risk_score":0.1,"reason_codes":["model_uncertain"],"rationale":"모델 판단"}'

    provider = LocalModelApprovalReviewProvider(generate, model_name="qwen3.8:27b")
    review = provider.review(
        ApprovalReviewInput(
            tool_name="write_file",
            tool_args={"file_path": ".env", "content": "TOP_SECRET"},
            risk_level="high",
            description="환경 변수 파일 갱신",
            diff_preview="[민감 파일 diff가 마스킹되었습니다: .env]",
        ),
    )

    assert len(prompts) == 1
    assert "TOP_SECRET" not in prompts[0]
    assert review.decision is ApprovalReviewDecision.DENY
    assert review.risk_score >= 0.95
    assert review.reviewer == "qwen:qwen3.8:27b"
    assert "model_review" in review.reason_codes


def test_local_model_review_rejects_non_structured_output() -> None:
    provider = LocalModelApprovalReviewProvider(lambda _prompt: "not-json", model_name="qwen3.8:27b")

    with pytest.raises(ValueError):
        _ = provider.review(
            ApprovalReviewInput(
                tool_name="read_file",
                tool_args={"file_path": "README.md"},
                risk_level="low",
                description="README 확인",
                diff_preview="",
            ),
        )


def test_local_model_review_accepts_percent_risk_scores() -> None:
    provider = LocalModelApprovalReviewProvider(
        lambda _prompt: '{"decision":"approve","risk_score":10,"reason_codes":["READ_ONLY_OPERATION"],"rationale":"읽기 전용"}',
        model_name="qwen3.8:27b",
    )

    review = provider.review(
        ApprovalReviewInput(
            tool_name="read_file",
            tool_args={"file_path": "README.md"},
            risk_level="low",
            description="README 확인",
            diff_preview="",
        ),
    )

    assert review.decision is ApprovalReviewDecision.APPROVE
    assert review.risk_score == 0.2


def test_local_model_failure_preserves_policy_denial_for_sensitive_request() -> None:
    provider = LocalModelApprovalReviewProvider(lambda _prompt: "not-json", model_name="qwen3.8:27b")

    review = provider.review(
        ApprovalReviewInput(
            tool_name="write_file",
            tool_args={"file_path": ".env", "content": "TOP_SECRET"},
            risk_level="high",
            description="환경 변수 파일 갱신",
            diff_preview="[민감 파일 diff가 마스킹되었습니다: .env]",
        ),
    )

    assert review.decision is ApprovalReviewDecision.DENY
    assert review.reviewer == "qwen:qwen3.8:27b-fail-closed"
    assert "model_error" in review.reason_codes


def test_configured_local_model_reviewer_is_used_by_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    targets: list[str] = []

    class FakeModelManager:
        def generate(self, _prompt: str, target: str, **_kwargs: str) -> str:
            targets.append(target)
            return '{"decision":"escalate","risk_score":0.8,"reason_codes":["model_review"],"rationale":"추가 확인"}'

    monkeypatch.setenv("AGK_APPROVAL_REVIEW_MODEL", "qwen3.8:27b")
    monkeypatch.setattr(
        "antigravity_k.engine.approval_manager._review_model_manager_provider",
        lambda: FakeModelManager(),
    )
    reset_approval_manager()

    request = get_approval_manager().request_approval(
        "run_bash_command",
        {"command": "git status"},
        "medium",
        "저장소 상태 확인",
    )

    assert request.auto_review is not None
    assert request.auto_review.reviewer == "qwen:qwen3.8:27b"
    assert request.auto_review.decision is ApprovalReviewDecision.ESCALATE
    assert targets == ["qwen3.8"]
    reset_approval_manager()
