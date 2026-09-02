"""테스트: 증폭 비교 벤치마크 (compare_amplification).

cascade ON이 OFF 대비 응답 품질을 끌어올리는지 객관 수치로 검증한다.
이것이 "작은 모델 성능 증폭" 목표의 측정 근거다.
"""

from collections.abc import Mapping
from typing import Protocol, TypedDict, cast
from unittest.mock import MagicMock

from antigravity_k.engine.benchmark_harness import BenchmarkHarness, BenchmarkResult
from antigravity_k.engine.model_manager import LoadedModel, ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.quality_gate import QualityGate
from antigravity_k.engine.usage_tracker import UsageTracker


class _GenerateCallback(Protocol):
    def __call__(self, loaded: LoadedModel, prompt: str, **kwargs: object) -> str: ...


class _ModeStats(TypedDict):
    mean_score: float
    excellent_rate: float
    fail_rate: float
    n: int


class _ImprovementStats(TypedDict, total=False):
    baseline: str
    mean_delta: float
    improved: int
    worse: int
    same: int


class _CompleteImprovementStats(TypedDict):
    baseline: str
    mean_delta: float
    improved: int
    worse: int
    same: int


class _AmplificationStats(TypedDict):
    by_mode: dict[str, _ModeStats]
    improvement: _ImprovementStats


class _AmplificationOutput(TypedDict):
    by_case: dict[str, dict[str, BenchmarkResult]]
    summary: str
    stats: _AmplificationStats


def _compare(
    harness: BenchmarkHarness,
    case_ids: list[str],
    target: str,
    modes: list[str] | None = None,
) -> _AmplificationOutput:
    return cast(
        _AmplificationOutput,
        cast(object, harness.compare_amplification(case_ids, target, modes=modes)),
    )


def _set_do_generate(manager: ModelManager, callback: _GenerateCallback) -> None:
    setattr(manager, "_do_generate", MagicMock(side_effect=callback))


def _quality_gate(harness: BenchmarkHarness) -> QualityGate:
    return cast(QualityGate, getattr(harness, "_quality_gate"))

WEAK_RESPONSE = "모르겠습니다. 잘 모르겠습니다."  # 신뢰도 매우 낮음
STRONG_RESPONSE = (
    "### 분석\n피보나치 수열 함수입니다.\n\n"
    "```python\n"
    "def fibonacci(n: int) -> int:\n"
    "    if n < 0:\n"
    "        raise ValueError('음수 불가')\n"
    "    if n <= 1:\n"
    "        return n\n"
    "    a, b = 0, 1\n"
    "    for _ in range(2, n + 1):\n"
    "        a, b = b, a + b\n"
    "    return b\n"
    "```\n"
    "반복 방법의 시간복잡도는 O(n), 공간복잡도 O(1)입니다.\n"
)


def _make_manager() -> tuple[ModelManager, ModelRouter]:
    registry = cast(ModelRegistry, MagicMock(spec=ModelRegistry))
    memory_config = MagicMock()
    memory_config.max_loaded_gb = 1000
    memory_config.auto_unload = False
    setattr(registry, "memory_config", memory_config)
    profiles = {
        "light": ModelProfile(name="light", repo="t", role="test", estimated_memory_gb=1),
        "heavy": ModelProfile(name="heavy", repo="t", role="test", estimated_memory_gb=1),
    }
    def get_model(name: str) -> ModelProfile | None:
        return profiles.get(name)

    get_model_mock = MagicMock(side_effect=get_model)
    setattr(registry, "get_model", get_model_mock)
    setattr(registry, "_raw", {})

    router = ModelRouter(registry)
    router.register_combo(
        ModelCombo(
            name="cascade-stack",
            models=["light", "heavy"],
            strategy=RouteStrategy.CASCADING,
        )
    )
    router.cascade_confidence_threshold = 0.4
    router.cascade_max_escalations = 2

    manager = ModelManager(registry=registry, router=router, tracker=UsageTracker(db_path=None))
    setattr(manager, "_load_mlx_model", MagicMock(return_value=(MagicMock(), None)))
    return manager, router


def _wire_generate(manager: ModelManager, responses_by_model: Mapping[str, str]) -> None:
    """모델별로 고정 응답 반환하도록 _do_generate를 설정."""

    def fake(loaded: LoadedModel, prompt: str, **kwargs: object) -> str:
        _ = prompt
        _ = kwargs
        return responses_by_model[loaded.profile.name]

    _set_do_generate(manager, fake)


def test_cascade_off_keeps_weak_response():
    manager, router = _make_manager()
    router.cascade_on_low_confidence = False
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})

    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001"], "cascade-stack")
    result = out["by_case"]["sim-001"]["cascade_off"]
    assert WEAK_RESPONSE[:10] in result.output_preview or result.quality_grade == "fail"


def test_cascade_on_escalates_to_strong():
    manager, router = _make_manager()
    router.cascade_on_low_confidence = True
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})

    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001"], "cascade-stack")
    off = out["by_case"]["sim-001"]["cascade_off"]
    on = out["by_case"]["sim-001"]["cascade_on"]

    # cascade ON은 heavy(강한 응답)로 에스컬레이션 → 키워드 커버리지 향상
    assert on.keyword_coverage >= off.keyword_coverage
    assert "def fibonacci" in on.output_preview


def test_summary_table_contains_both_modes():
    manager, _router = _make_manager()
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001", "sim-002"], "cascade-stack")
    assert "cascade_off" in out["summary"]
    assert "cascade_on" in out["summary"]
    assert "sim-001" in out["summary"]


def test_router_state_restored_after_run():
    manager, router = _make_manager()
    router.cascade_on_low_confidence = False
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    _ = _compare(harness, ["sim-001"], "cascade-stack")
    assert router.cascade_on_low_confidence is False


def test_revision_off_skips_regeneration():
    """revision_off(max_retries=0)는 재생성 루프를 발화하지 않는다."""
    manager, _ = _make_manager()
    calls: list[str] = []

    def fake(loaded: LoadedModel, prompt: str, **kwargs: object) -> str:
        _ = loaded
        _ = kwargs
        calls.append(prompt[:30])
        return WEAK_RESPONSE

    _set_do_generate(manager, fake)
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001"], "light", modes=["revision_off"])
    # 단일 호출(초기 생성)만, revision 호출 없음
    assert len(calls) == 1
    assert out["by_case"]["sim-001"]["revision_off"].quality_revision_count == 0


def test_revision_on_applies_regeneration_and_restores_state():
    """revision_on은 weak 답을 strong으로 재생성해 품질을 올리고, 종료 후 max_retries 복구."""
    manager, _ = _make_manager()

    # 첫 호출은 WEAK, 이후 QUALITY REVISION 프롬프트면 STRONG 반환.
    def fake(loaded: LoadedModel, prompt: str, **kwargs: object) -> str:
        _ = loaded
        _ = kwargs
        if "[QUALITY REVISION]" in prompt:
            return STRONG_RESPONSE
        return WEAK_RESPONSE

    _set_do_generate(manager, fake)
    gate = QualityGate(max_retries=2)
    harness = BenchmarkHarness(manager, quality_gate=gate, db_path=None)
    original_retries = gate.max_retries

    out = _compare(harness, ["sim-001"], "light", modes=["revision_off", "revision_on"])
    off = out["by_case"]["sim-001"]["revision_off"]
    on = out["by_case"]["sim-001"]["revision_on"]

    # revision_off는 증폭 없이 weak 유지; revision_on은 재생성으로 keyword coverage 향상.
    assert off.quality_revision_count == 0
    assert on.quality_revision_applied is True
    assert on.keyword_coverage >= off.keyword_coverage
    # 종료 후 QualityGate.max_retries 원복.
    assert gate.max_retries == original_retries


def test_revision_summary_contains_both_modes():
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001"], "light", modes=["revision_off", "revision_on"])
    assert "revision_off" in out["summary"]
    assert "revision_on" in out["summary"]
    assert "sim-001" in out["summary"]


def test_amplification_stats_shape():
    """stats 딕셔너리가 모드별 평균/등급분포/개선비율을 올바르게 계산하는지 검증."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(
        harness,
        ["sim-001", "sim-002"],
        "cascade-stack",
        modes=["cascade_off", "cascade_on"],
    )
    stats = out["stats"]
    assert "by_mode" in stats and "improvement" in stats
    for mode in ("cascade_off", "cascade_on"):
        ms = stats["by_mode"][mode]
        assert {"mean_score", "excellent_rate", "fail_rate", "n"} <= set(ms)
        assert ms["n"] == 2


def test_amplification_stats_improvement_when_on_beats_off():
    """cascade_on이 off보다 점수가 높으면 improvement.improved에 반영된다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001"], "cascade-stack")
    imp = cast(_CompleteImprovementStats, cast(object, out["stats"]["improvement"]))
    assert imp["baseline"] == "cascade_off"
    # cascade_on이 heavy 강응답으로 에스컬레이션 → 개선.
    assert imp["improved"] >= 1
    assert imp["mean_delta"] >= 0.0


def test_amplification_stats_no_improvement_when_equal():
    """두 모드가 같은 점수면 improvement.same에 반영된다."""
    manager, _ = _make_manager()
    # 항상 동일 응답 → 양 모드 같은 점수.
    setattr(manager, "_do_generate", MagicMock(return_value=STRONG_RESPONSE))
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001"], "cascade-stack")
    imp = cast(_CompleteImprovementStats, cast(object, out["stats"]["improvement"]))
    assert imp["same"] >= 1
    assert imp["improved"] == 0
    assert abs(imp["mean_delta"]) < 1e-9


def test_self_consistency_off_uses_plain_generate():
    """sc_off 모드는 일반 generate로 단일 호출한다 (N샘플링 없음)."""
    manager, _ = _make_manager()
    calls: list[int] = []

    def fake(loaded: LoadedModel, prompt: str, **kwargs: object) -> str:
        _ = loaded
        _ = prompt
        _ = kwargs
        calls.append(1)
        return STRONG_RESPONSE

    _set_do_generate(manager, fake)
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001"], "light", modes=["sc_off"])
    # sc_off는 단일 초기 생성만 (revision은 max_retries 기본값 따라).
    assert len(calls) >= 1
    assert "sc_off" in out["by_case"]["sim-001"]


def test_self_consistency_on_invokes_generate_self_consistent():
    """sc_on 모드는 generate_self_consistent로 초기 답을 N샘플링 생성한다."""
    manager, _ = _make_manager()
    # generate_self_consistent를 추적 — 호출되면 STRONG 반환, 일반 generate는 WEAK.
    sc_calls = {"n": 0}

    def fake(loaded: LoadedModel, prompt: str, **kwargs: object) -> str:
        _ = loaded
        _ = prompt
        _ = kwargs
        return WEAK_RESPONSE

    _set_do_generate(manager, fake)

    real_sc = manager.generate_self_consistent

    def traced_sc(prompt: str, target: str, **kwargs: object) -> str:
        _ = kwargs
        sc_calls["n"] += 1
        return real_sc(prompt, target, **kwargs)

    setattr(manager, "generate_self_consistent", traced_sc)
    # self-consistency config 비활성 → generate_self_consistent는 일반 generate로 폴백하므로
    # 활성화를 흉내내기 위해 manager에 활성 설정을 주입하지 않고 호출 경로만 검증.
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001"], "light", modes=["sc_on"])
    assert sc_calls["n"] == 1
    assert "sc_on" in out["by_case"]["sim-001"]


def test_self_consistency_stats_include_sc_modes():
    """sc_off/sc_on A/B의 stats에 양 모드가 모두 포함된다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": STRONG_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["sim-001"], "light", modes=["sc_off", "sc_on"])
    assert "sc_off" in out["stats"]["by_mode"]
    assert "sc_on" in out["stats"]["by_mode"]
    assert "sc_off" in out["summary"] and "sc_on" in out["summary"]


def test_decomposition_on_invokes_generate_decomposed():
    """decomp_on 모드는 generate_decomposed로 초기 답을 단계 분해 생성한다."""
    manager, _ = _make_manager()
    td_calls = {"n": 0}

    def fake(loaded: LoadedModel, prompt: str, **kwargs: object) -> str:
        _ = loaded
        _ = prompt
        _ = kwargs
        return STRONG_RESPONSE

    _set_do_generate(manager, fake)
    real_td = manager.generate_decomposed

    def traced_td(prompt: str, target: str, force: bool = False, **kwargs: object) -> str:
        _ = kwargs
        td_calls["n"] += 1
        return real_td(prompt, target, force=force, **kwargs)

    setattr(manager, "generate_decomposed", traced_td)
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["lh-001"], "light", modes=["decomp_on"])
    assert td_calls["n"] == 1
    assert "decomp_on" in out["by_case"]["lh-001"]


def test_decomposition_stats_include_decomp_modes():
    """decomp_off/decomp_on A/B의 stats에 양 모드가 모두 포함된다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": STRONG_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["lh-001"], "light", modes=["decomp_off", "decomp_on"])
    assert "decomp_off" in out["stats"]["by_mode"]
    assert "decomp_on" in out["stats"]["by_mode"]
    assert "decomp_off" in out["summary"] and "decomp_on" in out["summary"]


def test_bon_mode_routes_to_generate_best_of_n():
    """bon_on 모드는 generate_best_of_n으로 초기 답을 실행 검증 생성한다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": STRONG_RESPONSE, "heavy": STRONG_RESPONSE})
    bon_mock = MagicMock(return_value=STRONG_RESPONSE)
    setattr(manager, "generate_best_of_n", bon_mock)

    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["lh-001"], "light", modes=["bon_on"])

    assert bon_mock.called
    result = out["by_case"]["lh-001"]["bon_on"]
    assert not result.error
    assert "bon_on" in out["stats"]["by_mode"]


def test_bon_vs_off_ab_stats():
    """bon_off/bon_on A/B에서 stats improvement가 baseline을 bon_off로 계산한다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": STRONG_RESPONSE, "heavy": STRONG_RESPONSE})
    bon_mock = MagicMock(return_value=STRONG_RESPONSE)
    setattr(manager, "generate_best_of_n", bon_mock)

    harness = BenchmarkHarness(manager, db_path=None)
    out = _compare(harness, ["lh-001"], "light", modes=["cascade_off", "bon_on"])
    improvement = cast(_CompleteImprovementStats, cast(object, out["stats"]["improvement"]))
    assert improvement["baseline"] == "cascade_off"


# ─── AVO 감독축 모드 (avo_on / bon_avo) ──────────────────────────────


def test_avo_mode_injects_stall_directive_on_repeat_failure():
    """avo_on: 반복 실패 시 STALL 전략수정 지시문이 feedback에 주입된다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": WEAK_RESPONSE})

    harness = BenchmarkHarness(manager, db_path=None)
    revision_mock = MagicMock(return_value=None)
    setattr(harness, "_quality_revision", revision_mock)

    out = _compare(harness, ["lh-001"], "light", modes=["avo_on"])

    feedbacks = [cast(str, cast(object, call.args[2])) for call in revision_mock.call_args_list]
    assert len(feedbacks) >= 2, "감독 예산(2회) 내 재시도가 발화해야 한다"
    assert "[STALL DETECTED]" not in feedbacks[0], "첫 실패에는 개입이 없어야 한다"
    assert "[STALL DETECTED]" in feedbacks[-1], "반복 실패 시점에 개입이 주입되어야 한다"
    result = out["by_case"]["lh-001"]["avo_on"]
    assert not result.error


def test_avo_retry_budget_restored_after_run():
    """avo_on 실행 후 QualityGate.max_retries가 원복된다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": STRONG_RESPONSE, "heavy": STRONG_RESPONSE})

    harness = BenchmarkHarness(manager, db_path=None)
    quality_gate = _quality_gate(harness)
    original_retries = quality_gate.max_retries

    _ = _compare(harness, ["lh-001"], "light", modes=["avo_on", "bon_avo"])

    assert quality_gate.max_retries == original_retries


def test_bon_avo_combines_best_of_n_and_supervision():
    """bon_avo: 초기 답은 BoN 경로로 생성되고, 감독 예산도 함께 적용된다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": WEAK_RESPONSE})
    bon_mock = MagicMock(return_value=STRONG_RESPONSE)
    setattr(manager, "generate_best_of_n", bon_mock)

    harness = BenchmarkHarness(manager, db_path=None)
    setattr(harness, "_quality_revision", MagicMock(return_value=None))

    out = _compare(harness, ["lh-001"], "light", modes=["bon_avo"])

    assert bon_mock.called, "초기 답 생성에 BoN이 사용되어야 한다"
    result = out["by_case"]["lh-001"]["bon_avo"]
    assert not result.error
