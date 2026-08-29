from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import Request

from antigravity_k.tools.egress_policy import safe_urlopen


class _Process(Protocol):
    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...


class LocalRuntimeSupervisor:
    def __init__(self, *, process_factory: Callable[..., _Process] | None = None) -> None:
        self._process_factory: Callable[..., _Process] = process_factory or subprocess.Popen
        self._processes: dict[str, _Process] = {}
        _ = atexit.register(self.shutdown)

    def ensure_available(self, profile: object) -> str:
        provider = str(getattr(profile, "provider", "")).casefold()
        api_base = str(getattr(profile, "api_base", ""))
        repo = str(getattr(profile, "repo", ""))
        name = str(getattr(profile, "name", repo))
        if provider not in {"llama.cpp", "llamacpp"} or not repo.casefold().endswith(".gguf") or not api_base:
            return api_base
        process = self._processes.get(name)
        if process is not None and process.poll() is None:
            return api_base
        if self._probe(api_base):
            return api_base

        binary = os.getenv("AGK_LLAMA_SERVER_BIN", "").strip() or shutil.which("llama-server")
        if not binary:
            raise RuntimeError(
                f"GGUF 모델 '{name}'을 사용하려면 llama-server가 필요합니다. llama.cpp를 설치하거나 "
                + "AGK_LLAMA_SERVER_BIN을 설정하세요."
            )
        parsed = urlparse(api_base)
        port = parsed.port or 8080
        process = self._process_factory(
            [binary, "-m", repo, "--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._processes[name] = process
        if not self._wait_until_available(api_base):
            process.terminate()
            _ = self._processes.pop(name, None)
            raise RuntimeError(f"llama-server가 모델 '{name}'을 준비하지 못했습니다.")
        return api_base

    def shutdown(self) -> None:
        for name, process in tuple(self._processes.items()):
            if process.poll() is None:
                process.terminate()
            _ = self._processes.pop(name, None)

    @staticmethod
    def _probe(api_base: str) -> bool:
        try:
            request = Request(f"{api_base.rstrip('/')}/models")
            with safe_urlopen(request, timeout=1):
                return True
        except (OSError, TimeoutError, ValueError):
            return False

    @classmethod
    def _wait_until_available(cls, api_base: str, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cls._probe(api_base):
                return True
            time.sleep(0.25)
        return False
