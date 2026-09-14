"""CR-14 attempt-039 — AGK_SEED_LOCAL_HUB hermetic 픽스처 이빨.

생산 경로(플래그 없음)에서는 orpheus 를 running 으로 만들지 않는다.
시드 ON 일 때만 ModelHub 게이트가 소유할 `실행 중` 상태를 만든다.
"""

from __future__ import annotations

from antigravity_k.engine.local_model_discovery import (
    HERMETIC_HUB_MODEL_ID,
    DiscoveredLocalModel,
    LocalModelDiscovery,
    apply_hermetic_local_hub_seed,
    hermetic_local_hub_fixture,
    hermetic_local_hub_seed_enabled,
)


def test_seed_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AGK_SEED_LOCAL_HUB", raising=False)
    assert hermetic_local_hub_seed_enabled() is False
    cached = DiscoveredLocalModel(
        name=HERMETIC_HUB_MODEL_ID,
        repo="unsloth/orpheus",
        provider="unsloth",
        api_base="",
        role="audio",
        status="cached",
        source="huggingface_cache",
    )
    out = apply_hermetic_local_hub_seed((cached,))
    assert len(out) == 1
    assert out[0].status == "cached"


def test_seed_upgrades_existing_orpheus_to_running(monkeypatch) -> None:
    monkeypatch.setenv("AGK_SEED_LOCAL_HUB", "1")
    assert hermetic_local_hub_seed_enabled() is True
    cached = DiscoveredLocalModel(
        name=HERMETIC_HUB_MODEL_ID,
        repo="unsloth/orpheus",
        provider="unsloth",
        api_base="",
        role="audio",
        status="cached",
        quantization="UD-Q4_K_XL",
        source="huggingface_cache",
    )
    out = apply_hermetic_local_hub_seed((cached,))
    assert len(out) == 1
    assert out[0].name == HERMETIC_HUB_MODEL_ID
    assert out[0].status == "running"


def test_seed_injects_fixture_when_absent(monkeypatch) -> None:
    monkeypatch.setenv("AGK_SEED_LOCAL_HUB", "hub")
    out = apply_hermetic_local_hub_seed(())
    assert len(out) == 1
    assert out[0].name == HERMETIC_HUB_MODEL_ID
    assert out[0].status == "running"
    assert out[0].source == "hermetic_seed"
    assert out[0].provider == "unsloth"


def test_discover_applies_seed(monkeypatch) -> None:
    monkeypatch.setenv("AGK_SEED_LOCAL_HUB", "1")
    models = LocalModelDiscovery(model_dirs=(), disable_network=True).discover()
    names = {m.name for m in models}
    assert HERMETIC_HUB_MODEL_ID in names
    target = next(m for m in models if m.name == HERMETIC_HUB_MODEL_ID)
    assert target.status == "running"


def test_discover_without_seed_does_not_invent_fixture(monkeypatch) -> None:
    monkeypatch.delenv("AGK_SEED_LOCAL_HUB", raising=False)
    models = LocalModelDiscovery(model_dirs=(), disable_network=True).discover()
    invented = [m for m in models if m.source == "hermetic_seed"]
    assert invented == []


def test_fixture_shape() -> None:
    fix = hermetic_local_hub_fixture()
    assert fix.name == HERMETIC_HUB_MODEL_ID
    assert fix.status == "running"
    assert "UD-Q4_K_XL" in fix.quantization
