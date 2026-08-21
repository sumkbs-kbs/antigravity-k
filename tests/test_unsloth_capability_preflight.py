from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from antigravity_k.api.routes import unsloth_studio_api
from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.provider_adapters.unsloth_capability_contracts import (
    CapabilityOperation,
    CapabilityProvider,
    CapabilityStatus,
    PlatformKind,
    SystemCapabilityReading,
    UnslothCapabilitySnapshot,
)
from antigravity_k.engine.provider_adapters.unsloth_capability_preflight import (
    SystemCapabilityProbe,
    UnslothCapabilityPreflight,
)
from antigravity_k.engine.provider_adapters.unsloth_platform_policy import (
    default_training_platform,
)


@dataclass(frozen=True, slots=True)
class _ReadingProbe:
    reading_value: SystemCapabilityReading

    def reading(self) -> SystemCapabilityReading:
        return self.reading_value


def _reading(
    *,
    platform: PlatformKind,
    disk_free_bytes: int = 20_000,
    accelerator_status: CapabilityStatus,
    unsloth_installed: bool = False,
    cuda_available: bool = False,
) -> SystemCapabilityReading:
    return SystemCapabilityReading(
        platform=platform,
        memory_total_bytes=100_000,
        memory_available_bytes=25_000,
        disk_free_bytes=disk_free_bytes,
        thermal_state="nominal",
        accelerator_kind="cuda" if cuda_available else "none",
        accelerator_status=accelerator_status,
        accelerator_detail="test accelerator",
        ollama_installed=True,
        mlx_installed=True,
        unsloth_installed=unsloth_installed,
        cuda_available=cuda_available,
    )


def _auth_headers() -> dict[str, str]:
    if not config.security.access_pin:
        return {}
    return {"X-Access-Pin": config.security.access_pin}


def test_darwin_arm64_separates_inference_training_and_export_defaults() -> None:
    preflight = UnslothCapabilityPreflight(
        _ReadingProbe(_reading(platform=PlatformKind.DARWIN_ARM64, accelerator_status="not_required")),
    )

    snapshot = preflight.snapshot()

    defaults = {
        (CapabilityOperation.INFERENCE, CapabilityProvider.OLLAMA),
        (CapabilityOperation.TRAINING, CapabilityProvider.MLX),
        (CapabilityOperation.EXPORT, CapabilityProvider.MLX),
    }
    assert {
        (item.operation, item.provider)
        for item in snapshot.capabilities
        if item.is_default and item.status == "available"
    } == defaults
    assert all(item.max_concurrent == 1 for item in snapshot.capabilities)
    assert {
        (item.operation, item.provider) for item in snapshot.capabilities if item.provider is CapabilityProvider.UNSLOTH
    } == {
        (CapabilityOperation.TRAINING, CapabilityProvider.UNSLOTH),
        (CapabilityOperation.EXPORT, CapabilityProvider.UNSLOTH),
    }
    assert all(
        item.status == "unavailable" for item in snapshot.capabilities if item.provider is CapabilityProvider.UNSLOTH
    )


def test_missing_unsloth_or_cuda_is_unavailable_not_an_error() -> None:
    preflight = UnslothCapabilityPreflight(
        _ReadingProbe(
            _reading(
                platform=PlatformKind.NON_DARWIN,
                accelerator_status="unavailable",
                unsloth_installed=True,
                cuda_available=False,
            ),
        ),
    )

    snapshot = preflight.snapshot()

    unsloth = [item for item in snapshot.capabilities if item.provider is CapabilityProvider.UNSLOTH]
    assert all(item.status == "unavailable" for item in unsloth)
    assert all("CUDA" in item.detail for item in unsloth)


def test_disk_cuda_and_thermal_preflight_use_typed_states() -> None:
    preflight = UnslothCapabilityPreflight(
        _ReadingProbe(
            _reading(
                platform=PlatformKind.NON_DARWIN,
                disk_free_bytes=1_024,
                accelerator_status="unavailable",
            ),
        ),
    )

    snapshot = preflight.snapshot()

    assert snapshot.system.disk.status == "insufficient"
    assert snapshot.system.disk.free_bytes == 1_024
    assert snapshot.system.accelerator.status == "unavailable"
    assert snapshot.system.thermal.state == "nominal"


def test_capability_api_does_not_require_unsloth_runtime() -> None:
    probe = UnslothCapabilityPreflight(
        _ReadingProbe(_reading(platform=PlatformKind.DARWIN_ARM64, accelerator_status="not_required")),
    )
    app.dependency_overrides[unsloth_studio_api.get_unsloth_capability_preflight] = lambda: probe
    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/integrations/unsloth/capabilities",
                headers=_auth_headers(),
            )
    finally:
        _ = app.dependency_overrides.pop(
            unsloth_studio_api.get_unsloth_capability_preflight,
            None,
        )

    assert response.status_code == 200
    payload = UnslothCapabilitySnapshot.model_validate_json(response.text)
    assert payload.platform is PlatformKind.DARWIN_ARM64
    assert payload.write_tools_enabled is False
    assert {(item.operation, item.provider) for item in payload.capabilities if item.is_default} == {
        (CapabilityOperation.INFERENCE, CapabilityProvider.OLLAMA),
        (CapabilityOperation.TRAINING, CapabilityProvider.MLX),
        (CapabilityOperation.EXPORT, CapabilityProvider.MLX),
    }


def test_system_probe_returns_a_complete_reading_without_cuda_dependency(tmp_path: Path) -> None:
    reading = SystemCapabilityProbe(tmp_path).reading()

    assert reading.platform in {
        PlatformKind.DARWIN_ARM64,
        PlatformKind.DARWIN_OTHER,
        PlatformKind.NON_DARWIN,
    }
    assert reading.memory_total_bytes > 0
    assert reading.disk_free_bytes >= 0
    assert reading.thermal_state in {"nominal", "elevated", "critical", "unknown"}
    assert isinstance(reading.ollama_installed, bool)
    assert isinstance(reading.mlx_installed, bool)
    assert isinstance(reading.unsloth_installed, bool)


def test_default_training_platform_uses_mlx_only_on_darwin() -> None:
    assert default_training_platform(PlatformKind.DARWIN_ARM64) == "mlx"
    assert default_training_platform(PlatformKind.DARWIN_OTHER) == "mlx"
    assert default_training_platform(PlatformKind.NON_DARWIN) == "unsloth"
