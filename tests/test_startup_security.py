from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_k.config import SecurityConfig
from antigravity_k.engine.auth import hash_pin


def test_security_config_has_no_predictable_default_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGK_SEC_ACCESS_PIN", raising=False)

    assert SecurityConfig().access_pin == ""


def test_loopback_bind_allows_local_bootstrap_without_pin(tmp_path: Path) -> None:
    from antigravity_k.api.startup_security import validate_startup_security

    validate_startup_security(
        host="127.0.0.1",
        environment="development",
        access_pin="",
        pin_hash_file=tmp_path / "missing-auth-hash",
    )


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.20"])
def test_public_bind_requires_a_strong_bootstrap_credential(host: str, tmp_path: Path) -> None:
    from antigravity_k.api.startup_security import StartupSecurityError, validate_startup_security

    with pytest.raises(StartupSecurityError, match="strong access PIN"):
        validate_startup_security(
            host=host,
            environment="development",
            access_pin="0000",
            pin_hash_file=tmp_path / "missing-auth-hash",
        )


def test_production_requires_a_strong_bootstrap_credential_even_on_loopback(tmp_path: Path) -> None:
    from antigravity_k.api.startup_security import StartupSecurityError, validate_startup_security

    with pytest.raises(StartupSecurityError, match="strong access PIN"):
        validate_startup_security(
            host="127.0.0.1",
            environment="production",
            access_pin="",
            pin_hash_file=tmp_path / "missing-auth-hash",
        )


def test_public_bind_accepts_strong_pin(tmp_path: Path) -> None:
    from antigravity_k.api.startup_security import validate_startup_security

    validate_startup_security(
        host="0.0.0.0",
        environment="production",
        access_pin="correct-horse-battery-staple",
        pin_hash_file=tmp_path / "missing-auth-hash",
    )


def test_production_accepts_persisted_pin_hash(tmp_path: Path) -> None:
    pin_hash_file = tmp_path / "auth-hash"
    pin_hash_file.write_text(hash_pin("persisted-strong-pin"), encoding="utf-8")

    from antigravity_k.api.startup_security import validate_startup_security

    validate_startup_security(
        host="127.0.0.1",
        environment="production",
        access_pin="",
        pin_hash_file=pin_hash_file,
    )
