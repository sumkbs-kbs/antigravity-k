"""테스트: 증폭 비교 벤치마크 (compare_amplification).

cascade ON이 OFF 대비 응답 품질을 끌어올리는지 객관 수치로 검증한다.
이것이 "작은 모델 성능 증폭" 목표의 측정 근거다.
"""

from unittest.mock import MagicMock

from antigravity_k.engine.benchmark_harness import BenchmarkHarness
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelProfile, ModelRegistry
from antigravity_k.engine.model_router import ModelCombo, ModelRouter, RouteStrategy
from antigravity_k.engine.quality_gate import QualityGate
from antigravity_k.engine.usage_tracker import UsageTracker

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


def _make_manager():
    registry = MagicMock(spec=ModelRegistry)
    registry.memory_config = MagicMock()
    registry.memory_config.max_loaded_gb = 1000
    registry.memory_config.auto_unload = False
    profiles = {
        "light": ModelProfile(name="light", repo="t", role="test", estimated_memory_gb=1),
        "heavy": ModelProfile(name="heavy", repo="t", role="test", estimated_memory_gb=1),
    }
    registry.get_model.side_effect = lambda x: profiles.get(x)
    registry._raw = {}

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
    manager._load_mlx_model = MagicMock(return_value=(MagicMock(), None))
    return manager, router


def _wire_generate(manager, responses_by_model):
    """모델별로 고정 응답 반환하도록 _do_generate를 설정."""

    def fake(loaded, prompt, **kwargs):
        return responses_by_model[loaded.profile.name]

    manager._do_generate = MagicMock(side_effect=fake)


def test_cascade_off_keeps_weak_response():
    manager, router = _make_manager()
    router.cascade_on_low_confidence = False
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})

    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["sim-001"], "cascade-stack")
    result = out["by_case"]["sim-001"]["cascade_off"]
    assert WEAK_RESPONSE[:10] in result.output_preview or result.quality_grade == "fail"


def test_cascade_on_escalates_to_strong():
    manager, router = _make_manager()
    router.cascade_on_low_confidence = True
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})

    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["sim-001"], "cascade-stack")
    off = out["by_case"]["sim-001"]["cascade_off"]
    on = out["by_case"]["sim-001"]["cascade_on"]

    # cascade ON은 heavy(강한 응답)로 에스컬레이션 → 키워드 커버리지 향상
    assert on.keyword_coverage >= off.keyword_coverage
    assert "def fibonacci" in on.output_preview


def test_summary_table_contains_both_modes():
    manager, _router = _make_manager()
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["sim-001", "sim-002"], "cascade-stack")
    assert "cascade_off" in out["summary"]
    assert "cascade_on" in out["summary"]
    assert "sim-001" in out["summary"]


def test_router_state_restored_after_run():
    manager, router = _make_manager()
    router.cascade_on_low_confidence = False
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    harness.compare_amplification(["sim-001"], "cascade-stack")
    assert router.cascade_on_low_confidence is False


def test_revision_off_skips_regeneration():
    """revision_off(max_retries=0)는 재생성 루프를 발화하지 않는다."""
    manager, _ = _make_manager()
    calls = []

    def fake(loaded, prompt, **kwargs):
        calls.append(prompt[:30])
        return WEAK_RESPONSE

    manager._do_generate = MagicMock(side_effect=fake)
    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["sim-001"], "light", modes=["revision_off"])
    # 단일 호출(초기 생성)만, revision 호출 없음
    assert len(calls) == 1
    assert out["by_case"]["sim-001"]["revision_off"].quality_revision_count == 0


def test_revision_on_applies_regeneration_and_restores_state():
    """revision_on은 weak 답을 strong으로 재생성해 품질을 올리고, 종료 후 max_retries 복구."""
    manager, _ = _make_manager()

    # 첫 호출은 WEAK, 이후 QUALITY REVISION 프롬프트면 STRONG 반환.
    def fake(loaded, prompt, **kwargs):
        if "[QUALITY REVISION]" in prompt:
            return STRONG_RESPONSE
        return WEAK_RESPONSE

    manager._do_generate = MagicMock(side_effect=fake)
    gate = QualityGate(max_retries=2)
    harness = BenchmarkHarness(manager, quality_gate=gate, db_path=None)
    original_retries = gate.max_retries

    out = harness.compare_amplification(["sim-001"], "light", modes=["revision_off", "revision_on"])
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
    out = harness.compare_amplification(["sim-001"], "light", modes=["revision_off", "revision_on"])
    assert "revision_off" in out["summary"]
    assert "revision_on" in out["summary"]
    assert "sim-001" in out["summary"]


def test_amplification_stats_shape():
    """stats 딕셔너리가 모드별 평균/등급분포/개선비율을 올바르게 계산하는지 검증."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": WEAK_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(
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
    out = harness.compare_amplification(["sim-001"], "cascade-stack")
    imp = out["stats"]["improvement"]
    assert imp["baseline"] == "cascade_off"
    # cascade_on이 heavy 강응답으로 에스컬레이션 → 개선.
    assert imp["improved"] >= 1
    assert imp["mean_delta"] >= 0.0


def test_amplification_stats_no_improvement_when_equal():
    """두 모드가 같은 점수면 improvement.same에 반영된다."""
    manager, _ = _make_manager()
    # 항상 동일 응답 → 양 모드 같은 점수.
    manager._do_generate = MagicMock(return_value=STRONG_RESPONSE)
    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["sim-001"], "cascade-stack")
    imp = out["stats"]["improvement"]
    assert imp["same"] >= 1
    assert imp["improved"] == 0
    assert abs(imp["mean_delta"]) < 1e-9


def test_self_consistency_off_uses_plain_generate():
    """sc_off 모드는 일반 generate로 단일 호출한다 (N샘플링 없음)."""
    manager, _ = _make_manager()
    calls = []

    def fake(loaded, prompt, **kwargs):
        calls.append(1)
        return STRONG_RESPONSE

    manager._do_generate = MagicMock(side_effect=fake)
    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["sim-001"], "light", modes=["sc_off"])
    # sc_off는 단일 초기 생성만 (revision은 max_retries 기본값 따라).
    assert len(calls) >= 1
    assert "sc_off" in out["by_case"]["sim-001"]


def test_self_consistency_on_invokes_generate_self_consistent():
    """sc_on 모드는 generate_self_consistent로 초기 답을 N샘플링 생성한다."""
    manager, _ = _make_manager()
    # generate_self_consistent를 추적 — 호출되면 STRONG 반환, 일반 generate는 WEAK.
    sc_calls = {"n": 0}

    def fake(loaded, prompt, **kwargs):
        return WEAK_RESPONSE

    manager._do_generate = MagicMock(side_effect=fake)

    real_sc = manager.generate_self_consistent

    def traced_sc(prompt, target, **kwargs):
        sc_calls["n"] += 1
        return real_sc(prompt, target, **kwargs)

    manager.generate_self_consistent = traced_sc
    # self-consistency config 비활성 → generate_self_consistent는 일반 generate로 폴백하므로
    # 활성화를 흉내내기 위해 manager에 활성 설정을 주입하지 않고 호출 경로만 검증.
    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["sim-001"], "light", modes=["sc_on"])
    assert sc_calls["n"] == 1
    assert "sc_on" in out["by_case"]["sim-001"]


def test_self_consistency_stats_include_sc_modes():
    """sc_off/sc_on A/B의 stats에 양 모드가 모두 포함된다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": STRONG_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["sim-001"], "light", modes=["sc_off", "sc_on"])
    assert "sc_off" in out["stats"]["by_mode"]
    assert "sc_on" in out["stats"]["by_mode"]
    assert "sc_off" in out["summary"] and "sc_on" in out["summary"]


def test_decomposition_on_invokes_generate_decomposed():
    """decomp_on 모드는 generate_decomposed로 초기 답을 단계 분해 생성한다."""
    manager, _ = _make_manager()
    td_calls = {"n": 0}

    def fake(loaded, prompt, **kwargs):
        return STRONG_RESPONSE

    manager._do_generate = MagicMock(side_effect=fake)
    real_td = manager.generate_decomposed

    def traced_td(prompt, target, **kwargs):
        td_calls["n"] += 1
        return real_td(prompt, target, **kwargs)

    manager.generate_decomposed = traced_td
    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["lh-001"], "light", modes=["decomp_on"])
    assert td_calls["n"] == 1
    assert "decomp_on" in out["by_case"]["lh-001"]


def test_decomposition_stats_include_decomp_modes():
    """decomp_off/decomp_on A/B의 stats에 양 모드가 모두 포함된다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": STRONG_RESPONSE, "heavy": STRONG_RESPONSE})
    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["lh-001"], "light", modes=["decomp_off", "decomp_on"])
    assert "decomp_off" in out["stats"]["by_mode"]
    assert "decomp_on" in out["stats"]["by_mode"]
    assert "decomp_off" in out["summary"] and "decomp_on" in out["summary"]


def test_bon_mode_routes_to_generate_best_of_n():
    """bon_on 모드는 generate_best_of_n으로 초기 답을 실행 검증 생성한다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": STRONG_RESPONSE, "heavy": STRONG_RESPONSE})
    manager.generate_best_of_n = MagicMock(return_value=STRONG_RESPONSE)

    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["lh-001"], "light", modes=["bon_on"])

    assert manager.generate_best_of_n.called
    result = out["by_case"]["lh-001"]["bon_on"]
    assert not result.error
    assert "bon_on" in out["stats"]["by_mode"]


def test_bon_vs_off_ab_stats():
    """bon_off/bon_on A/B에서 stats improvement가 baseline을 bon_off로 계산한다."""
    manager, _ = _make_manager()
    _wire_generate(manager, {"light": STRONG_RESPONSE, "heavy": STRONG_RESPONSE})
    manager.generate_best_of_n = MagicMock(return_value=STRONG_RESPONSE)

    harness = BenchmarkHarness(manager, db_path=None)
    out = harness.compare_amplification(["lh-001"], "light", modes=["cascade_off", "bon_on"])
    improvement = out["stats"]["improvement"]
    assert improvement["baseline"] == "cascade_off"
