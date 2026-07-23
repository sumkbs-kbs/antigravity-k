"""Tests for the ProviderManager module."""

import os
from unittest import mock

from antigravity_k.engine.provider_manager import ProviderManager, get_provider_manager, provider_manager


class TestProviderManager:
    """Tests for ProviderManager class."""

    def test_init_empty(self):
        """초기화 시 _providers가 비어있고 auto_discover가 환경변수 없이 빈 상태여야 함."""
        with mock.patch.dict(os.environ, {}, clear=True):
            pm = ProviderManager()
            assert pm._providers == {}

    def test_auto_discover_with_env(self):
        """OPENAI_API_KEY 환경변수가 있을 때 auto_discover가 default provider를 등록해야 함."""
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            pm = ProviderManager()
            assert "default" in pm._providers
            assert pm._providers["default"]["OPENAI_API_KEY"] == "sk-test123"

    def test_auto_discover_multiple_env(self):
        """여러 API 키 환경변수가 있을 때 모두 발견해야 함."""
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test1",
                "ANTHROPIC_API_KEY": "sk-ant-test2",
                "GITHUB_TOKEN": "gh_test3",
            },
            clear=True,
        ):
            pm = ProviderManager()
            assert len(pm._providers["default"]) == 3
            assert pm._providers["default"]["OPENAI_API_KEY"] == "sk-test1"
            assert pm._providers["default"]["ANTHROPIC_API_KEY"] == "sk-ant-test2"
            assert pm._providers["default"]["GITHUB_TOKEN"] == "gh_test3"

    def test_register_provider(self):
        """register_provider로 새 provider를 등록할 수 있어야 함."""
        pm = ProviderManager()
        pm.register_provider("custom", {"API_KEY": "custom-key"})
        assert "custom" in pm._providers
        assert pm._providers["custom"]["API_KEY"] == "custom-key"

    def test_register_overwrite(self):
        """동일 이름으로 등록하면 덮어써야 함."""
        pm = ProviderManager()
        pm.register_provider("test", {"key": "val1"})
        pm.register_provider("test", {"key": "val2"})
        assert pm._providers["test"]["key"] == "val2"

    def test_get_provider_env_existing(self):
        """get_provider_env로 등록된 provider의 환경변수를 조회할 수 있어야 함."""
        pm = ProviderManager()
        pm.register_provider("myprovider", {"MY_KEY": "my-val"})
        env = pm.get_provider_env("myprovider")
        assert env == {"MY_KEY": "my-val"}

    def test_get_provider_env_default(self):
        """기본 이름 'default'로 조회할 수 있어야 함."""
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-default"}, clear=True):
            pm = ProviderManager()
            env = pm.get_provider_env()
            assert env["OPENAI_API_KEY"] == "sk-default"

    def test_get_provider_env_nonexistent(self):
        """존재하지 않는 provider 조회 시 빈 dict를 반환해야 함."""
        pm = ProviderManager()
        env = pm.get_provider_env("nonexistent")
        assert env == {}

    def test_singleton_get_provider_manager(self):
        """get_provider_manager()가 동일한 싱글톤 인스턴스를 반환해야 함."""
        pm1 = get_provider_manager()
        pm2 = get_provider_manager()
        assert pm1 is pm2

    def test_singleton_import(self):
        """모듈 레벨 provider_manager가 get_provider_manager()와 동일해야 함."""
        assert provider_manager is get_provider_manager()

    def test_auto_discover_skips_missing_env(self):
        """설정되지 않은 환경변수는 auto_discover에서 제외되어야 함."""
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-only"}, clear=True):
            pm = ProviderManager()
            assert "GITHUB_TOKEN" not in pm._providers.get("default", {})

    def test_register_empty_credentials(self):
        """빈 credentials로 등록해도 오류 없이 동작해야 함."""
        pm = ProviderManager()
        pm.register_provider("empty", {})
        assert pm._providers["empty"] == {}

    def test_get_provider_env_after_register(self):
        """등록 후 조회 시 최신 값을 반환해야 함."""
        pm = ProviderManager()
        pm.register_provider("dynamic", {"KEY": "v1"})
        assert pm.get_provider_env("dynamic")["KEY"] == "v1"
        pm.register_provider("dynamic", {"KEY": "v2"})
        assert pm.get_provider_env("dynamic")["KEY"] == "v2"

    def test_auto_discover_called_on_init(self):
        """__init__에서 _auto_discover가 호출되어야 함."""
        with mock.patch.object(ProviderManager, "_auto_discover") as mock_ad:
            ProviderManager()
            mock_ad.assert_called_once()
