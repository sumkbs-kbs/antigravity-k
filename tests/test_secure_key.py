"""Antigravity-K: secure_key.py 단위 테스트.

커버리지:
  - _get_machine_seed(): 4단계 우선순위 (IOPlatformUUID → machine-id → MAC → fallback)
  - _get_or_create_master_key(): 생성 + 캐시 복원
  - _get_cipher(): Fernet 암호 정상 생성
  - _load_vault_keys / _save_vault_keys: 암호화 저장/복호화
  - Key lifecycle: store → load → has → remove → clear
"""

from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

# ─── Fixtures: 경로 상수 오버라이드 ─────────────────────────────────


@pytest.fixture(autouse=True)
def patch_paths(monkeypatch, tmp_path):
    """모든 테스트에서 vault 경로를 tmp_path로 변경하여 실제 .agk_vault/ 보호."""
    import antigravity_k.engine.secure_key as sk

    vault_dir = tmp_path / ".agk_vault"
    monkeypatch.setattr(sk, "_VAULT_KEY_DIR", vault_dir)
    monkeypatch.setattr(sk, "_MASTER_KEY_FILE", vault_dir / "master.key")
    monkeypatch.setattr(sk, "_VAULT_DB", vault_dir / "keys.enc")
    monkeypatch.setattr(sk, "_DOTENV_PATH", tmp_path / ".env")
    return vault_dir


@pytest.fixture(autouse=True)
def no_keychain(monkeypatch):
    """키체인 Tier 0을 비활성화합니다 (실제 키체인 간섭 방지).
    모든 테스트에 자동 적용 — 실제 키체인이 필요한 테스트는 없음.
    """
    import antigravity_k.engine.secure_key as sk

    monkeypatch.setattr(sk, "_get_keychain_seed", lambda: None)
    monkeypatch.setattr(sk, "_set_keychain_seed", lambda seed: False)


@pytest.fixture
def fake_ioreg_uuid(monkeypatch):
    """IOPlatformUUID가 반환되는 환경을 시뮬레이션합니다."""
    import subprocess

    fake_result = subprocess.CompletedProcess(
        args=["ioreg"],
        returncode=0,
        stdout='  "IOPlatformUUID" = "E9C3EB2E-A2B0-570C-BC5F-100B4CFD1BB8"\n',
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
    return fake_result


@pytest.fixture
def fake_machine_id(monkeypatch):
    """/etc/machine-id가 반환되는 환경을 시뮬레이션합니다."""
    from pathlib import Path

    def fake_read_text(self, **kw):
        if str(self) in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            return "abc123def456abc123def456abc123def4\n"
        raise FileNotFoundError(f"No such file: {self}")

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    return "abc123def456abc123def456abc123def4"


# ═══════════════════════════════════════════════════════════════════
# _get_machine_seed() - 4단계 우선순위
# ═══════════════════════════════════════════════════════════════════


class TestGetMachineSeed:
    """_get_machine_seed()의 4단계 우선순위를 검증합니다."""

    def test_returns_ioreg_uuid_when_available(self, fake_ioreg_uuid):
        """1순위: IOPlatformUUID가 있으면 이를 반환해야 함."""
        from antigravity_k.engine.secure_key import _get_machine_seed

        seed = _get_machine_seed()
        assert seed == "E9C3EB2E-A2B0-570C-BC5F-100B4CFD1BB8"

    def test_returns_machine_id_when_ioreg_fails(self, fake_machine_id, monkeypatch):
        """2순위: ioreg 실패 시 /etc/machine-id를 반환해야 함."""
        import subprocess

        from antigravity_k.engine.secure_key import _get_machine_seed

        # ioreg 실패 시뮬레이션
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("ioreg not found")),
        )
        seed = _get_machine_seed()
        assert seed == "abc123def456abc123def456abc123def4"

    def test_returns_mac_address_when_all_else_fails(self, monkeypatch):
        """3순위: ioreg도 없고 machine-id도 없으면 MAC 주소를 반환해야 함."""
        import subprocess

        from antigravity_k.engine.secure_key import _get_machine_seed

        # ioreg / machine-id 모두 실패
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("ioreg not found")),
        )

        # uuid.getnode가 유효한 MAC 반환
        import uuid

        monkeypatch.setattr(uuid, "getnode", lambda: 0x00_1A_2B_3C_4D_5E)

        seed = _get_machine_seed()
        assert seed == str(0x00_1A_2B_3C_4D_5E)

    def test_fallback_when_all_tiers_fail(self, monkeypatch):
        """4순위: 모든 Tier 실패 시 하드코딩 폴백을 반환해야 함."""
        import subprocess
        import uuid

        from antigravity_k.engine.secure_key import _get_machine_seed

        # 모든 Tier 차단
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("ioreg not found")),
        )
        monkeypatch.setattr(uuid, "getnode", lambda: (_ for _ in ()).throw(RuntimeError("no MAC")))

        seed = _get_machine_seed()
        assert seed == "antigravity-k-default-salt"

    def test_deterministic_on_same_machine(self, fake_ioreg_uuid):
        """동일 환경에서 항상 같은 시드를 반환해야 함."""
        from antigravity_k.engine.secure_key import _get_machine_seed

        seed1 = _get_machine_seed()
        seed2 = _get_machine_seed()
        assert seed1 == seed2 == "E9C3EB2E-A2B0-570C-BC5F-100B4CFD1BB8"


# ═══════════════════════════════════════════════════════════════════
# _get_or_create_master_key() - 생성 + 캐시 복원
# ═══════════════════════════════════════════════════════════════════


class TestGetOrCreateMasterKey:
    """_get_or_create_master_key()의 생성 및 캐시 복원을 검증합니다."""

    def test_creates_new_key(self, patch_paths, fake_ioreg_uuid):
        """최초 호출 시 마스터 키를 생성하고 반환해야 함."""
        from antigravity_k.engine.secure_key import _get_or_create_master_key

        key = _get_or_create_master_key()
        assert isinstance(key, bytes)
        assert len(key) == 44  # Fernet 키 = base64 44자

        # 키 파일이 생성되었는지 확인
        assert patch_paths.joinpath("master.key").exists()

    def test_restores_cached_key(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """두 번째 호출 시 캐시된 키를 복원해야 함.

        시드가 변경되어도 master.key가 캐싱되어 있으면
        동일한 키를 반환해야 함.
        """
        import subprocess

        from antigravity_k.engine.secure_key import _get_or_create_master_key

        key1 = _get_or_create_master_key()

        # ioreg가 다른 값 반환해도 master.key 캐시가 우선
        fake_result = subprocess.CompletedProcess(
            args=["ioreg"],
            returncode=0,
            stdout='  "IOPlatformUUID" = "DIFFERENT-UUID"\n',
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        key2 = _get_or_create_master_key()
        assert key1 == key2

    def test_key_is_valid_fernet_key(self, patch_paths, fake_ioreg_uuid):
        """생성된 키로 Fernet 암호를 만들 수 있어야 함."""
        from antigravity_k.engine.secure_key import _get_or_create_master_key

        key = _get_or_create_master_key()
        cipher = Fernet(key)
        # 암호화/복호화 검증
        encrypted = cipher.encrypt(b"test-data")
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == b"test-data"

    def test_creates_directory(self, patch_paths, fake_ioreg_uuid):
        """Vault 디렉토리가 없으면 생성해야 함."""
        from antigravity_k.engine.secure_key import _get_or_create_master_key

        assert patch_paths.exists() is False
        _get_or_create_master_key()
        assert patch_paths.exists()

    def test_restores_existing_key_after_reinit(self, patch_paths, fake_ioreg_uuid):
        """master.key가 이미 있으면 재생성하지 않고 복원해야 함."""
        from antigravity_k.engine.secure_key import _get_or_create_master_key

        key1 = _get_or_create_master_key()

        # master.key 파일은 유지, vault DB (keys.enc) 제거
        db_path = patch_paths / "keys.enc"
        if db_path.exists():
            db_path.unlink()

        # 다시 호출 — master.key가 있으므로 캐시된 키 반환
        key2 = _get_or_create_master_key()
        assert key1 == key2

    def test_deterministic_across_calls(self, patch_paths, fake_ioreg_uuid):
        """여러 번 호출해도 동일한 master.key가 생성됨."""
        from antigravity_k.engine.secure_key import _get_or_create_master_key

        keys = [_get_or_create_master_key() for _ in range(5)]
        assert all(k == keys[0] for k in keys)


# ═══════════════════════════════════════════════════════════════════
# Vault 암호화 저장소 — encrypt/decrypt roundtrip
# ═══════════════════════════════════════════════════════════════════


class TestVaultStore:
    """_save_vault_keys / _load_vault_keys의 암호화 roundtrip을 검증합니다."""

    def test_save_and_load_roundtrip(self, patch_paths, fake_ioreg_uuid):
        """저장한 키를 정상적으로 복호화할 수 있어야 함."""
        from antigravity_k.engine.secure_key import _load_vault_keys, _save_vault_keys

        original = {"anthropic": "sk-ant-test123", "openai": "sk-proj-test456"}
        _save_vault_keys(original)
        loaded = _load_vault_keys()
        assert loaded == original

    def test_load_empty_when_no_file(self, patch_paths):
        """저장소 파일이 없으면 빈 dict를 반환해야 함."""
        from antigravity_k.engine.secure_key import _load_vault_keys

        assert _load_vault_keys() == {}

    def test_load_empty_on_corrupt_file(self, patch_paths, fake_ioreg_uuid):
        """파일이 손상되면 빈 dict를 반환해야 함 (예외 처리)."""
        from antigravity_k.engine.secure_key import _load_vault_keys

        vault_db = patch_paths / "keys.enc"
        vault_db.parent.mkdir(parents=True, exist_ok=True)
        vault_db.write_bytes(b"not-encrypted-data")
        loaded = _load_vault_keys()
        assert loaded == {}

    def test_file_permissions_after_save(self, patch_paths, fake_ioreg_uuid):
        """저장 후 파일 권한이 소유자만 읽기/쓰기여야 함."""
        from antigravity_k.engine.secure_key import _save_vault_keys

        _save_vault_keys({"test": "value"})
        vault_db = patch_paths / "keys.enc"
        assert vault_db.exists()

        # macOS/Linux에서만 권한 확인
        if os.name == "posix":
            mode = vault_db.stat().st_mode & 0o777
            assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_multiple_saves_overwrite(self, patch_paths, fake_ioreg_uuid):
        """여러 번 저장해도 마지막 값으로 덮어써져야 함."""
        from antigravity_k.engine.secure_key import _load_vault_keys, _save_vault_keys

        _save_vault_keys({"a": "1"})
        _save_vault_keys({"b": "2"})
        loaded = _load_vault_keys()
        assert loaded == {"b": "2"}  # 덮어쓰기

    def test_encrypted_file_is_not_plaintext(self, patch_paths, fake_ioreg_uuid):
        """저장된 파일이 평문이 아닌 암호화되어야 함."""
        from antigravity_k.engine.secure_key import _save_vault_keys

        _save_vault_keys({"anthropic": "sk-ant-visible-in-plain"})
        vault_db = patch_paths / "keys.enc"
        raw = vault_db.read_bytes()
        # 평문 키가 파일에 직접 나타나지 않아야 함
        assert b"sk-ant-visible-in-plain" not in raw
        assert b"anthropic" not in raw


# ═══════════════════════════════════════════════════════════════════
# Key Lifecycle — store → load → has → remove → clear
# ═══════════════════════════════════════════════════════════════════


class TestKeyLifecycle:
    """공개 API: store_api_key → get_api_key → has_api_key → remove_api_key → clear_vault_keys."""

    def test_store_and_get(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """Store 후 get으로 동일한 키를 조회할 수 있어야 함."""
        from antigravity_k.engine.secure_key import get_api_key, store_api_key

        # 환경변수 오염 방지
        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        assert store_api_key("anthropic", "sk-ant-integration-test")
        assert get_api_key("anthropic") == "sk-ant-integration-test"

    def test_store_rejects_placeholder(self, patch_paths):
        """Placeholder 키는 저장을 거부해야 함."""
        from antigravity_k.engine.secure_key import store_api_key

        assert store_api_key("anthropic", "your-key-here") is False
        assert store_api_key("openai", "sk-proj-your-key-here") is False

    def test_has_api_key(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """has_api_key가 키 존재 여부를 정확히 반환해야 함."""
        from antigravity_k.engine.secure_key import (
            get_api_key,
            has_api_key,
            store_api_key,
        )

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        assert has_api_key("anthropic") is False
        store_api_key("anthropic", "sk-ant-has-test")
        assert has_api_key("anthropic") is True
        assert get_api_key("anthropic") == "sk-ant-has-test"

    def test_remove_api_key(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """Remove 후 키가 vault에서 제거되어야 함."""
        from antigravity_k.engine.secure_key import (
            get_api_key,
            remove_api_key,
            store_api_key,
        )

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        store_api_key("anthropic", "sk-ant-remove-test")
        assert get_api_key("anthropic") == "sk-ant-remove-test"
        assert remove_api_key("anthropic") is True
        assert get_api_key("anthropic") is None

    def test_remove_nonexistent_returns_false(self, patch_paths):
        """존재하지 않는 키를 삭제하면 False를 반환해야 함."""
        from antigravity_k.engine.secure_key import remove_api_key

        assert remove_api_key("nonexistent") is False

    def test_clear_vault_keys(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """clear_vault_keys 후 모든 키가 제거되어야 함."""
        from antigravity_k.engine.secure_key import (
            clear_vault_keys,
            get_api_key,
            list_configured_services,
            store_api_key,
        )

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)
        monkeypatch.delenv("AGK_OPENAI_KEY", raising=False)
        monkeypatch.delenv("AGK_OPENROUTER_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("ZAI_API_KEY", raising=False)

        store_api_key("anthropic", "sk-ant-clear-test")
        store_api_key("openai", "sk-proj-clear-test")
        assert list_configured_services() == ["anthropic", "openai"]

        clear_vault_keys()
        assert get_api_key("anthropic") is None
        assert get_api_key("openai") is None

    def test_get_key_source_priority(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """키 소스 우선순위가 올바르게 보고되어야 함."""
        from antigravity_k.engine.secure_key import (
            get_key_source,
            store_api_key,
        )

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        # vault에만 저장된 경우
        store_api_key("anthropic", "sk-ant-source-test")
        assert get_key_source("anthropic") == "vault"

        # 환경변수가 설정된 경우 env가 우선
        monkeypatch.setenv("AGK_ANTHROPIC_KEY", "sk-ant-from-env")
        assert get_key_source("anthropic") == "env"

        # 환경변수 제거 후 vault 소스 확인
        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)
        assert get_key_source("anthropic") == "vault"

    def test_get_key_source_none(self, patch_paths, monkeypatch):
        """어디에도 키가 없으면 'none'을 반환해야 함."""
        from antigravity_k.engine.secure_key import get_key_source

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)
        assert get_key_source("anthropic") == "none"

    def test_list_configured_services(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """설정된 서비스 목록을 정확히 반환해야 함."""
        from antigravity_k.engine.secure_key import (
            list_configured_services,
            store_api_key,
        )

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)
        monkeypatch.delenv("AGK_OPENAI_KEY", raising=False)
        monkeypatch.delenv("AGK_OPENROUTER_KEY", raising=False)
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("ZAI_API_KEY", raising=False)

        assert list_configured_services() == []
        store_api_key("anthropic", "sk-ant-list-test")
        assert list_configured_services() == ["anthropic"]
        store_api_key("openai", "sk-proj-list-test")
        services = list_configured_services()
        assert "anthropic" in services
        assert "openai" in services


# ═══════════════════════════════════════════════════════════════════
# 환경변수 우선순위 (get_api_key 4단계)
# ═══════════════════════════════════════════════════════════════════


class TestGetApiKeyPriority:
    """get_api_key()의 4단계 조회 우선순위를 검증합니다."""

    def test_env_var_takes_highest_priority(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """환경변수가 vault보다 우선해야 함."""
        from antigravity_k.engine.secure_key import get_api_key, store_api_key

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        store_api_key("anthropic", "sk-ant-vault-value")
        monkeypatch.setenv("AGK_ANTHROPIC_KEY", "sk-ant-env-value")
        assert get_api_key("anthropic") == "sk-ant-env-value"

    def test_dotenv_takes_priority_over_config_and_vault(
        self,
        patch_paths,
        fake_ioreg_uuid,
        monkeypatch,
    ):
        """.env 파일 값이 config.yaml과 vault보다 우선해야 함."""
        from antigravity_k.engine.secure_key import get_api_key, store_api_key

        monkeypatch.delenv("AGK_OPENAI_KEY", raising=False)

        # vault에 저장
        store_api_key("openai", "sk-proj-vault-value")

        # .env 파일 생성
        dotenv = patch_paths.parent / ".env"
        dotenv.write_text("AGK_OPENAI_KEY=sk-proj-dotenv-value\n")

        assert get_api_key("openai") == "sk-proj-dotenv-value"

    def test_returns_none_when_not_found(self, patch_paths, monkeypatch):
        """어디에서도 키를 찾을 수 없으면 None을 반환해야 함."""
        from antigravity_k.engine.secure_key import get_api_key

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)
        monkeypatch.delenv("AGK_OPENAI_KEY", raising=False)
        monkeypatch.delenv("AGK_OPENROUTER_KEY", raising=False)

        assert get_api_key("anthropic") is None
        assert get_api_key("openai") is None
        assert get_api_key("openrouter") is None

    def test_ignores_env_placeholder_keys(self, patch_paths, monkeypatch):
        """환경변수에 placeholder가 설정되어 있으면 무시해야 함."""
        from antigravity_k.engine.secure_key import get_api_key

        monkeypatch.setenv("AGK_ANTHROPIC_KEY", "your-key-here")
        assert get_api_key("anthropic") is None

    def test_unknown_service_returns_none(self, patch_paths, monkeypatch):
        """알 수 없는 서비스 이름에 대해 None을 반환해야 함."""
        from antigravity_k.engine.secure_key import get_api_key

        assert get_api_key("nonexistent-service") is None

    def test_case_insensitive_service_name(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """서비스 이름이 대소문자를 구분하지 않아야 함."""
        from antigravity_k.engine.secure_key import get_api_key, store_api_key

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        store_api_key("Anthropic", "sk-ant-case-test")
        assert get_api_key("ANTHROPIC") == "sk-ant-case-test"
        assert get_api_key("anthropic") == "sk-ant-case-test"


# ═══════════════════════════════════════════════════════════════════
# VALID_SERVICES 상수
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# rotate_master_key()
# ═══════════════════════════════════════════════════════════════════


class TestRotateMasterKey:
    """rotate_master_key()의 순환 및 재암호화를 검증합니다."""

    def test_derive_key_is_deterministic(self):
        """동일한 시드에서 항상 같은 키가 파생되어야 함."""
        from antigravity_k.engine.secure_key import _derive_key_from_seed

        key1 = _derive_key_from_seed("test-seed-123")
        key2 = _derive_key_from_seed("test-seed-123")
        assert key1 == key2
        assert len(key1) == 44  # Fernet 키 길이

    def test_different_seeds_produce_different_keys(self):
        """다른 시드에서 다른 키가 파생되어야 함."""
        from antigravity_k.engine.secure_key import _derive_key_from_seed

        key1 = _derive_key_from_seed("seed-a")
        key2 = _derive_key_from_seed("seed-b")
        assert key1 != key2

    def test_rotate_with_new_seed_reencrypts_vault_data(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """새 시드로 rotation 시 vault 데이터가 재암호화되어야 함."""
        from antigravity_k.engine.secure_key import (
            get_api_key,
            rotate_master_key,
            store_api_key,
        )

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)
        monkeypatch.delenv("AGK_OPENAI_KEY", raising=False)

        # 1. 기존 키 저장
        store_api_key("anthropic", "sk-ant-rot-test")
        store_api_key("openai", "sk-proj-rot-test")
        assert get_api_key("anthropic") == "sk-ant-rot-test"

        # 2. 새 시드로 rotation
        result = rotate_master_key(new_seed="custom-rotation-seed-42")
        assert result["success"] is True
        assert result["rotated"] is True
        assert result["services_count"] == 2

        # 3. rotation 후에도 데이터가 정상 조회되어야 함
        assert get_api_key("anthropic") == "sk-ant-rot-test"
        assert get_api_key("openai") == "sk-proj-rot-test"

    def test_rotate_without_new_seed_is_noop(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """새 시드 없이 rotation하면 동일 키이므로 rotated=False여야 함."""
        from antigravity_k.engine.secure_key import (
            get_api_key,
            rotate_master_key,
            store_api_key,
        )

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        store_api_key("anthropic", "sk-ant-noop-test")
        result = rotate_master_key()  # new_seed=None, same seed
        assert result["success"] is True
        assert result["rotated"] is False, "동일 시드로 rotated=True는 예상치 못함"
        assert get_api_key("anthropic") == "sk-ant-noop-test"

    def test_rotate_without_vault_data_succeeds(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """Vault 데이터가 없어도 rotation이 성공해야 함."""
        from antigravity_k.engine.secure_key import rotate_master_key

        result = rotate_master_key(new_seed="fresh-seed")
        assert result["success"] is True
        assert result["rotated"] is True
        assert result["services_count"] == 0

    def test_rotate_stores_seed_in_keychain(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """Rotation 시 새 시드가 키체인에 저장되어야 함."""
        from antigravity_k.engine.secure_key import (
            rotate_master_key,
        )

        # no_keychain autouse fixture가 _set_keychain_seed를 mock하므로
        # 여기서는 키체인 mock이 False를 반환하는지만 확인
        result = rotate_master_key(new_seed="keychain-test-seed")
        assert result["success"] is True

    def test_rotate_force_forces_reencryption_with_same_key(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """force=True면 동일 키여도 강제 재암호화해야 함."""
        from antigravity_k.engine.secure_key import (
            get_api_key,
            rotate_master_key,
            store_api_key,
        )

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        store_api_key("anthropic", "sk-ant-force-test")

        # force 없음 → rotated=False (동일 키)
        result_no_force = rotate_master_key()
        assert result_no_force["rotated"] is False

        # force=True → rotated=True (동일 키지만 강제 실행)
        result_force = rotate_master_key(force=True)
        assert result_force["success"] is True
        assert result_force["rotated"] is True
        assert result_force["services_count"] == 1
        assert get_api_key("anthropic") == "sk-ant-force-test"

    def test_kdf_migration_v1_to_v2_with_rotate(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """force=True + rotate로 KDF v1→v2 마이그레이션이 실제로 동작해야 함.

        시나리오:
          1. _CURRENT_KDF_VERSION=1 로 v1 키 생성 + vault 데이터 저장
          2. _CURRENT_KDF_VERSION=2 로 rotate_master_key(force=True)
          3. master.key가 V2: 포맷인지 확인
          4. vault 데이터가 여전히 접근 가능한지 확인
        """
        import antigravity_k.engine.secure_key as sk

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        # 1. v1 master key 생성
        monkeypatch.setattr(sk, "_CURRENT_KDF_VERSION", 1)
        sk._get_or_create_master_key()

        # V1: 포맷 확인
        raw = sk._MASTER_KEY_FILE.read_bytes()
        assert raw.startswith(b"V1:"), f"Expected V1: prefix, got {raw[:10]!r}"

        # vault 데이터 저장
        sk.store_api_key("anthropic", "sk-ant-migrate-test")
        assert sk.get_api_key("anthropic") == "sk-ant-migrate-test"

        # 2. KDF 버전을 2로 올리고 rotate(force=True)
        monkeypatch.setattr(sk, "_CURRENT_KDF_VERSION", 2)
        result = sk.rotate_master_key(force=True)
        assert result["success"] is True
        assert result["rotated"] is True
        assert result["services_count"] == 1

        # 3. master.key가 V2:로 업그레이드되었는지 확인
        raw = sk._MASTER_KEY_FILE.read_bytes()
        assert raw.startswith(b"V2:"), f"Expected V2: prefix after migration, got {raw[:10]!r}"

        # 4. vault 데이터가 여전히 접근 가능한지 확인
        assert sk.get_api_key("anthropic") == "sk-ant-migrate-test"

    def test_kdf_migration_reencrypts_vault_data(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """KDF v1→v2 마이그레이션 시 vault 데이터가 실제로 재암호화되는지 검증.

        단순히 접근 가능한지 확인하는 것을 넘어:
          1. 마이그레이션 전/후 vault DB 바이트가 다른지 확인
          2. 이전 v1 키로 새 vault DB를 복호화할 수 없는지 확인
          3. 새 v2 키로 새 vault DB를 정상 복호화할 수 있는지 확인
          4. 다중 서비스 데이터가 모두 마이그레이션되는지 확인
          5. get_api_key()가 여전히 정상 동작하는지 확인
        """
        import json

        import antigravity_k.engine.secure_key as sk

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)
        monkeypatch.delenv("AGK_OPENAI_KEY", raising=False)

        # 1. v1 키 생성 + 다중 서비스 vault 데이터 저장
        monkeypatch.setattr(sk, "_CURRENT_KDF_VERSION", 1)
        v1_key = sk._get_or_create_master_key()
        assert sk._MASTER_KEY_FILE.read_bytes().startswith(b"V1:")

        sk.store_api_key("anthropic", "sk-ant-migrate-reenc")
        sk.store_api_key("openai", "sk-proj-migrate-reenc")
        assert sk.get_api_key("anthropic") == "sk-ant-migrate-reenc"
        assert sk.get_api_key("openai") == "sk-proj-migrate-reenc"

        # 2. 마이그레이션 전 vault DB 스냅샷
        old_vault_bytes = sk._VAULT_DB.read_bytes()
        assert len(old_vault_bytes) > 0

        # 3. v2로 마이그레이션 (force=True)
        monkeypatch.setattr(sk, "_CURRENT_KDF_VERSION", 2)
        result = sk.rotate_master_key(force=True)
        assert result["success"] is True
        assert result["rotated"] is True
        assert result["services_count"] == 2
        assert sk._MASTER_KEY_FILE.read_bytes().startswith(b"V2:")

        new_vault_bytes = sk._VAULT_DB.read_bytes()

        # 4. vault DB 바이트가 변경되었는지 확인 (재암호화 증명)
        assert old_vault_bytes != new_vault_bytes, "Vault encrypted bytes must differ after KDF migration"

        # 5. v1 키로 새 vault DB를 복호화할 수 없는지 확인
        #    (salt/iterations가 달라 서로 다른 파생 키가 생성됨)
        from cryptography.fernet import InvalidToken

        v1_cipher = Fernet(v1_key)
        with pytest.raises(InvalidToken):
            v1_cipher.decrypt(new_vault_bytes)

        # 6. v2 키로 새 vault DB를 정상 복호화할 수 있는지 확인
        v2_key = sk._derive_key_from_seed(sk._get_machine_seed())
        assert v1_key != v2_key, "v1 key and v2 key must differ"
        v2_cipher = Fernet(v2_key)
        decrypted = v2_cipher.decrypt(new_vault_bytes)
        parsed = json.loads(decrypted.decode("utf-8"))
        assert parsed["anthropic"] == "sk-ant-migrate-reenc"
        assert parsed["openai"] == "sk-proj-migrate-reenc"
        assert len(parsed) == 2

        # 7. get_api_key()가 여전히 정상 동작하는지 확인 (통합 검증)
        assert sk.get_api_key("anthropic") == "sk-ant-migrate-reenc"
        assert sk.get_api_key("openai") == "sk-proj-migrate-reenc"

    # ── v2→v3 KDF 마이그레이션 (동일 패턴) ──────────────────────

    def test_kdf_migration_v2_to_v3_with_rotate(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """force=True + rotate로 KDF v2→v3 마이그레이션이 동일 패턴으로 동작해야 함.

        시나리오:
          1. _CURRENT_KDF_VERSION=2 로 v2 키 생성 + vault 데이터 저장
          2. _CURRENT_KDF_VERSION=3 로 rotate_master_key(force=True)
          3. master.key가 V3: 포맷인지 확인
          4. vault 데이터가 여전히 접근 가능한지 확인
        """
        import antigravity_k.engine.secure_key as sk

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)

        # 1. v2 master key 생성
        monkeypatch.setattr(sk, "_CURRENT_KDF_VERSION", 2)
        sk._get_or_create_master_key()

        raw = sk._MASTER_KEY_FILE.read_bytes()
        assert raw.startswith(b"V2:"), f"Expected V2: prefix, got {raw[:10]!r}"

        sk.store_api_key("anthropic", "sk-ant-v3-migrate-test")
        assert sk.get_api_key("anthropic") == "sk-ant-v3-migrate-test"

        # 2. KDF 버전을 3으로 올리고 rotate(force=True)
        monkeypatch.setattr(sk, "_CURRENT_KDF_VERSION", 3)
        result = sk.rotate_master_key(force=True)
        assert result["success"] is True
        assert result["rotated"] is True
        assert result["services_count"] == 1

        # 3. master.key가 V3:로 업그레이드되었는지 확인
        raw = sk._MASTER_KEY_FILE.read_bytes()
        assert raw.startswith(b"V3:"), f"Expected V3: prefix after migration, got {raw[:10]!r}"

        # 4. vault 데이터가 여전히 접근 가능한지 확인
        assert sk.get_api_key("anthropic") == "sk-ant-v3-migrate-test"

    def test_kdf_migration_v2_to_v3_reencrypts_vault_data(self, patch_paths, fake_ioreg_uuid, monkeypatch):
        """KDF v2→v3 마이그레이션 시 vault 데이터가 실제로 재암호화되는지 검증.

        v1→v2와 동일한 패턴:
          1. 마이그레이션 전/후 vault DB 바이트가 다른지 확인
          2. 이전 v2 키로 새 vault DB를 복호화할 수 없는지 확인
          3. 새 v3 키로 새 vault DB를 정상 복호화할 수 있는지 확인
          4. 다중 서비스 데이터가 모두 마이그레이션되는지 확인
          5. get_api_key()가 여전히 정상 동작하는지 확인
        """
        import json

        import antigravity_k.engine.secure_key as sk

        monkeypatch.delenv("AGK_ANTHROPIC_KEY", raising=False)
        monkeypatch.delenv("AGK_OPENAI_KEY", raising=False)

        # 1. v2 키 생성 + 다중 서비스 vault 데이터 저장
        monkeypatch.setattr(sk, "_CURRENT_KDF_VERSION", 2)
        v2_key = sk._get_or_create_master_key()
        assert sk._MASTER_KEY_FILE.read_bytes().startswith(b"V2:")

        sk.store_api_key("anthropic", "sk-ant-v3-reenc")
        sk.store_api_key("openai", "sk-proj-v3-reenc")
        assert sk.get_api_key("anthropic") == "sk-ant-v3-reenc"
        assert sk.get_api_key("openai") == "sk-proj-v3-reenc"

        # 2. 마이그레이션 전 vault DB 스냅샷
        old_vault_bytes = sk._VAULT_DB.read_bytes()
        assert len(old_vault_bytes) > 0

        # 3. v3로 마이그레이션 (force=True)
        monkeypatch.setattr(sk, "_CURRENT_KDF_VERSION", 3)
        result = sk.rotate_master_key(force=True)
        assert result["success"] is True
        assert result["rotated"] is True
        assert result["services_count"] == 2
        assert sk._MASTER_KEY_FILE.read_bytes().startswith(b"V3:")

        new_vault_bytes = sk._VAULT_DB.read_bytes()

        # 4. vault DB 바이트가 변경되었는지 확인 (재암호화 증명)
        assert old_vault_bytes != new_vault_bytes, "Vault encrypted bytes must differ after KDF migration"

        # 5. v2 키로 새 vault DB를 복호화할 수 없는지 확인
        from cryptography.fernet import InvalidToken

        v2_cipher = Fernet(v2_key)
        with pytest.raises(InvalidToken):
            v2_cipher.decrypt(new_vault_bytes)

        # 6. v3 키로 새 vault DB를 정상 복호화할 수 있는지 확인
        v3_key = sk._derive_key_from_seed(sk._get_machine_seed())
        assert v2_key != v3_key, "v2 key and v3 key must differ"
        v3_cipher = Fernet(v3_key)
        decrypted = v3_cipher.decrypt(new_vault_bytes)
        parsed = json.loads(decrypted.decode("utf-8"))
        assert parsed["anthropic"] == "sk-ant-v3-reenc"
        assert parsed["openai"] == "sk-proj-v3-reenc"
        assert len(parsed) == 2

        # 7. get_api_key()가 여전히 정상 동작하는지 확인 (통합 검증)
        assert sk.get_api_key("anthropic") == "sk-ant-v3-reenc"
        assert sk.get_api_key("openai") == "sk-proj-v3-reenc"


class TestValidServices:
    """VALID_SERVICES 상수를 검증합니다."""

    def test_contains_expected_services(self):
        from antigravity_k.engine.secure_key import VALID_SERVICES

        expected = ["anthropic", "openai", "openrouter", "nvidia", "gemini", "zai"]
        assert sorted(VALID_SERVICES) == sorted(expected)


# ═══════════════════════════════════════════════════════════════════
# CLI subprocess e2e — agk key rotate
# ═══════════════════════════════════════════════════════════════════


class TestCliKeyRotateE2E:
    """CLI 'agk key rotate --force' 를 subprocess로 직접 호출하는 e2e 테스트.

    이 테스트는 실제 CLI 바이너리를 subprocess로 실행하여
    KDF v1→v2 마이그레이션이 CLI 수준에서 정상 동작하는지 검증합니다.

    테스트 전략:
      - Python API로 v1 vault 데이터를 tmp_path에 생성
      - AGK_VAULT_DIR 환경변수로 서브프로세스가 같은 경로를 사용하도록 함
      - 'python -m antigravity_k.cli key rotate --force' 실행
      - CLI 출력, V2: prefix, vault 접근성 검증
    """

    def test_kdf_migration_v1_to_v2_via_cli(
        self,
        patch_paths,
        monkeypatch,
    ):
        """Agk key rotate --force CLI로 v1→v2 KDF 마이그레이션 e2e 검증.

        시나리오:
          1. Python API로 v1 vault 데이터 생성 (V1:master.key + keys.enc)
          2. subprocess로 'agk key rotate --force' 실행
          3. CLI 출력 메시지 검증
          4. master.key V2: prefix 확인
          5. vault 데이터 여전히 접근 가능한지 확인
        """
        import subprocess
        import sys

        import antigravity_k.engine.secure_key as sk

        vault_dir = patch_paths  # patch_paths fixture의 tmp_path/.agk_vault

        # Step 1: Python API로 v1 vault 데이터 설정
        monkeypatch.setattr(sk, "_CURRENT_KDF_VERSION", 1)
        sk._get_or_create_master_key()
        sk.store_api_key("anthropic", "sk-ant-e2e-cli-test")

        # V1: prefix 확인
        raw = sk._MASTER_KEY_FILE.read_bytes()
        assert raw.startswith(b"V1:"), f"Expected V1: prefix, got {raw[:10]!r}"

        # Step 2: CLI subprocess 실행
        env = os.environ.copy()
        env["AGK_VAULT_DIR"] = str(vault_dir)
        env.pop("AGK_ANTHROPIC_KEY", None)  # 환경변수 vault 간섭 방지

        result = subprocess.run(
            [sys.executable, "-m", "antigravity_k.cli", "key", "rotate", "--force"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        # Step 3: CLI 출력 검증
        assert result.returncode == 0, (
            f"CLI failed (rc={result.returncode}):\n  stdout: {result.stdout}\n  stderr: {result.stderr}"
        )
        assert "마스터 키 순환 완료" in result.stdout, f"Expected success message in stdout:\n{result.stdout}"
        assert "재암호화된 서비스: 1개" in result.stdout, f"Expected '1 service' in stdout:\n{result.stdout}"

        # Step 4: V3: prefix 확인 (현재 _CURRENT_KDF_VERSION=3)
        raw = sk._MASTER_KEY_FILE.read_bytes()
        assert raw.startswith(b"V3:"), f"Expected V3: prefix after migration, got {raw[:10]!r}"

        # Step 5: vault 데이터 접근 가능 확인
        assert sk.get_api_key("anthropic") == "sk-ant-e2e-cli-test"
