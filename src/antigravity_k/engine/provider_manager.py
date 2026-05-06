import os
import logging
from typing import Dict

logger = logging.getLogger("antigravity_k.engine.provider_manager")


class ProviderManager:
    """
    Manages sensitive credentials and dynamically injects them into agent contexts.
    Ensures that secrets are not leaked into disk states or logs.
    """

    def __init__(self):
        self._providers: Dict[str, Dict[str, str]] = {}
        # Auto-discover common API keys from environment
        self._auto_discover()

    def _auto_discover(self):
        common_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN"]
        discovered = {}
        for key in common_keys:
            if os.environ.get(key):
                discovered[key] = os.environ[key]
        if discovered:
            self._providers["default"] = discovered

    def register_provider(self, name: str, credentials: Dict[str, str]):
        self._providers[name] = credentials

    def get_provider_env(self, name: str = "default") -> Dict[str, str]:
        return self._providers.get(name, {})


# Singleton instance
provider_manager = ProviderManager()


def get_provider_manager() -> ProviderManager:
    return provider_manager
