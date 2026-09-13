"""CR-14 F-31 — 배포된 코드가 **config 에서 찾는 이름**을 config 가 실제로 소유하는가.

왜 필요한가
===========
`/benchmark run`(인자 없는 기본 실행)은 `BenchmarkHarness._default_targets()` 로 비교 대상을
정한다. 그 함수는 콤보 이름 `collective-council` 을 **코드에 갖고** 있고, 콤보의 모델 목록은
`config.yaml` 의 `combos` 에서 읽는다. 2026-05 세대 정리(e462a8aa·d131dc71)가 그 콤보를 지웠지만
코드는 남았고, 그래서 **배포된 명령의 기본 경로는 매 실행마다 오류 행(점수 0)을 기록했다** —
`_execute_single` 이 `ComboNotFoundError` 를 삼키기 때문에 사용자에게는 조용한 0점으로 보인다.

이 결함이 오래 숨은 이유는 계약이 아니라 **계약의 방식**이다: 유일한 회귀 테스트
(`tests/test_benchmark_harness.py::test_default_targets`)는 `registry._raw` 에 **합성 매핑**을
주입한다. 합성 입력에는 그 콤보가 늘 있으므로 **실제 config 가 무엇을 소유하는지는 결코 묻지
않았다**. 그래서 이 계약은 `_raw` 를 건드리지 않고 **진짜 파일**을 통해서만 잰다 —
`tests/test_cr14_gate_skip_register.py` 가 게이트 환경을 `_raw` 주입 없이 재현하는 것과 같은 규율이다.

요구(바뀌지 않는다)
===================
**기본 실행이 이름을 대는 모든 타겟은 이 config 가 소유해야 한다** — 콤보이거나 등록된 모델이어야
하고, 두 쪽 다 아니면 그 타겟은 실행될 수 없다. 그리고 그 비교는 **비교**여야 한다: 한쪽
(집단지성 평의회)과 다른 쪽(개별 모델)이 함께 있어야 `/benchmark` 의 전제가 성립한다.

가짜 config 로 이빨을 댄다
=========================
이빨은 `tmp_path` 에 **실제 YAML 파일**을 써서 콤보를 지우거나 로스터에서 모델을 빼고, 같은
검사가 그때 **실패하는지** 본다. 검사가 실패해야 할 입력에서 실패하지 않으면 계약이 아니라
장식이다(F-28·F-29 가 남긴 문장).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

import yaml

from antigravity_k.engine.benchmark_harness import BenchmarkHarness
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.model_router import RouteStrategy

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_CONFIG = REPO_ROOT / "config.yaml"

# `/benchmark` 의 전제가 "평의회 vs 개별 모델" 이므로 비교 대상은 코드가 정한 그 이름이다.
COUNCIL_TARGET = "collective-council"
COUNCIL_MIN_PARTICIPANTS = 3


class _Probe:
    """실제 config 파일 하나로 **배포 경로 그대로** 기본 타겟을 계산한다."""

    def __init__(self, config_path: Path) -> None:
        self.registry = ModelRegistry(str(config_path))
        self.manager = ModelManager(self.registry)
        harness = BenchmarkHarness(model_manager=self.manager)
        method = cast(Callable[[], object], getattr(harness, "_default_targets"))
        self.targets: list[str] = cast(list[str], method())

    def unresolved(self) -> list[str]:
        """기본 실행이 이름을 대는데 이 config 가 소유하지 않는 타겟 — 실행될 수 없는 자리."""
        return [
            target
            for target in self.targets
            if self.manager.router.get_combo(target) is None and self.registry.get_model(target) is None
        ]

    def singles(self) -> list[str]:
        """개별 모델 쪽 타겟 — 평의회와 비교되는 단일 모델들."""
        return [
            target
            for target in self.targets
            if self.manager.router.get_combo(target) is None and self.registry.get_model(target) is not None
        ]

    def raw(self) -> dict[str, object]:
        return cast(dict[str, object], self.registry._raw)  # noqa: SLF001 — config 원문이 곧 계약의 입력이다


def _mutated_config(tmp_path: Path, mutate: Callable[[dict[str, object]], None]) -> Path:
    """워크스페이스 config 를 복사해 **변형한 실제 파일**을 만든다(`_raw` 주입이 아니라 파일이다)."""
    payload = cast(dict[str, object], yaml.safe_load(WORKSPACE_CONFIG.read_text(encoding="utf-8")))
    mutate(payload)
    target = tmp_path / "config.yaml"
    target.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return target


def _drop_council(payload: dict[str, object]) -> None:
    combos = cast(dict[str, object], payload["combos"])
    del combos[COUNCIL_TARGET]


def _drop_gemma(payload: dict[str, object]) -> None:
    models = cast(dict[str, object], payload["models"])
    reasoning = cast(list[dict[str, object]], models["reasoning"])
    models["reasoning"] = [entry for entry in reasoning if "gemma-4-31B" not in str(entry.get("name", ""))]


# ─── 요구: 기본 타겟은 이 config 가 소유한 이름이다 ─────────────────────


def test_benchmark_default_targets_resolve_against_the_real_workspace_config() -> None:
    """기본 실행이 대는 모든 타겟이 콤보이거나 등록된 모델이다 — 미해석 타겟 0건."""
    probe = _Probe(WORKSPACE_CONFIG)
    assert probe.targets, "기본 타겟이 비었다 — /benchmark run 이 아무것도 비교하지 않는다"
    assert probe.unresolved() == [], (
        f"기본 타겟 {probe.unresolved()} 를 이 config 가 소유하지 않는다"
        " — 그 타겟은 실행될 수 없고 오류 행(점수 0)으로 기록된다"
    )


def test_benchmark_default_run_is_a_comparison_not_a_single_target() -> None:
    """평의회와 개별 모델이 **함께** 있어야 비교가 성립한다."""
    probe = _Probe(WORKSPACE_CONFIG)
    assert COUNCIL_TARGET in probe.targets, f"기본 타겟에 {COUNCIL_TARGET} 이 없다"
    assert probe.singles(), "비교할 개별 모델이 없다 — 명령의 전제(평의회 vs 단일 모델)가 성립하지 않는다"


def test_council_is_a_collective_combo_with_enough_participants() -> None:
    """콤보가 `collective` 전략을 선언하고, 참여 모델이 셋 이상 실제로 라우팅 가능하다."""
    probe = _Probe(WORKSPACE_CONFIG)
    combo = probe.manager.router.get_combo(COUNCIL_TARGET)
    assert combo is not None, f"{COUNCIL_TARGET} 콤보가 config 에 없다"
    assert combo.strategy is RouteStrategy.COLLECTIVE, (
        f"{COUNCIL_TARGET} 전략이 {combo.strategy} 다 — 집단지성 합성(제안/비판/중재) 경로로 가지 않는다"
    )
    available = probe.manager.router.available_model_names(COUNCIL_TARGET)
    assert len(available) >= COUNCIL_MIN_PARTICIPANTS, (
        f"참여 모델이 {len(available)}개다(최소 {COUNCIL_MIN_PARTICIPANTS}) — 평의회가 성립하지 않는다: {available}"
    )


def test_every_name_the_config_refers_to_is_registered() -> None:
    """config 안의 참조도 같은 규율을 따른다 — 역할 기본값과 콤보 멤버는 로스터에 있어야 한다."""
    probe = _Probe(WORKSPACE_CONFIG)
    payload = probe.raw()
    roster = {profile.name for profile in probe.registry.list_models()}
    combos = cast(Mapping[str, object], payload.get("combos") or {})
    defaults = cast(Mapping[str, object], payload.get("defaults") or {})
    agent_models = cast(Mapping[str, object], payload.get("agent_models") or {})

    dangling_roles = {key: value for key, value in defaults.items() if str(value) not in roster}
    assert dangling_roles == {}, f"역할 기본값이 로스터에 없다: {dangling_roles}"

    dangling_agents = {
        key: value for key, value in agent_models.items() if str(value) not in roster and str(value) not in combos
    }
    assert dangling_agents == {}, f"역할 대상이 콤보도 모델도 아니다: {dangling_agents}"

    dangling_members = {
        name: [member for member in cast(Sequence[object], spec["models"]) if str(member) not in roster]  # type: ignore[index]
        for name, spec in combos.items()
    }
    dangling_members = {name: members for name, members in dangling_members.items() if members}
    assert dangling_members == {}, f"콤보 멤버가 로스터에 없다: {dangling_members}"


# ─── 이빨: 검사가 실패해야 할 입력에서 실패하는가 ───────────────────────


def test_the_check_notices_a_council_the_config_no_longer_owns(tmp_path: Path) -> None:
    """콤보를 지우면 **같은 검사가 실패**한다 — F-31 의 원래 상태를 재구성한 것이다."""
    broken = _mutated_config(tmp_path, _drop_council)
    probe = _Probe(broken)

    assert probe.unresolved() == [COUNCIL_TARGET], (
        "콤보를 지웠는데 검사가 못 잡았다 — 이 계약은 실제 config 를 보지 않는다"
    )
    assert probe.singles() == [], "콤보가 없으면 개별 모델도 함께 사라진다(비교 대상이 하나도 남지 않는다)"
    assert probe.targets == [COUNCIL_TARGET], f"미해석 타겟 하나만 남아야 한다: {probe.targets}"


def test_the_check_notices_a_participant_that_dropped_out_of_the_roster(tmp_path: Path) -> None:
    """콤보 멤버를 로스터에서 빼면 그 이름이 미해석 타겟으로 드러난다."""
    broken = _mutated_config(tmp_path, _drop_gemma)
    probe = _Probe(broken)

    unresolved = probe.unresolved()
    assert any("gemma-4-31B" in target for target in unresolved), (
        f"로스터에서 뺀 멤버가 미해석 타겟으로 드러나지 않았다: targets={probe.targets} unresolved={unresolved}"
    )
