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
        from pathlib import Path

        provider = str(getattr(profile, "provider", "")).casefold()
        api_base = str(getattr(profile, "api_base", ""))
        repo = str(getattr(profile, "repo", ""))
        disk_path = str(getattr(profile, "disk_path", ""))
        name = str(getattr(profile, "name", repo))

        def _is_gguf(target: Path) -> bool:
            if not target.is_file():
                return False
            if target.suffix.casefold() == ".gguf":
                return True
            try:
                with open(target, "rb") as f:
                    return f.read(4) == b"GGUF"
            except OSError:
                return False

        # 실제 GGUF 파일 경로 탐색
        model_file = ""
        if disk_path:
            p = Path(disk_path)
            if _is_gguf(p):
                model_file = str(p)
            elif p.is_dir():
                shards = sorted(p.rglob("*"))
                gguf_shards = [s for s in shards if _is_gguf(s)]
                shard1 = [s for s in gguf_shards if "-00001-of-" in s.name or "_00001" in s.name]
                if shard1:
                    model_file = str(shard1[0])
                elif gguf_shards:
                    main_shards = [s for s in gguf_shards if not s.name.startswith("mmproj")]
                    model_file = str(main_shards[0] if main_shards else gguf_shards[0])
        elif repo and Path(repo).exists() and _is_gguf(Path(repo)):
            model_file = repo

        is_gguf = bool(model_file)
        if not is_gguf or provider not in {"llama.cpp", "llamacpp", "unsloth"}:
            return api_base

        if not api_base:
            api_base = os.getenv("AGK_LLAMA_CPP_API_BASE", "http://127.0.0.1:8080/v1")
            setattr(profile, "api_base", api_base)

        process = self._processes.get(name)
        if process is not None and process.poll() is None:
            return api_base
        if self._probe(api_base):
            return api_base

        binary = (
            os.getenv("AGK_LLAMA_SERVER_BIN", "").strip()
            or shutil.which("llama-server")
            or "/opt/homebrew/bin/llama-server"
            or "/usr/local/bin/llama-server"
        )
        if not binary or not os.path.exists(binary):
            raise RuntimeError(
                f"GGUF 모델 '{name}'을 실행하려면 llama-server가 필요합니다. llama.cpp를 설치하거나 "
                + "AGK_LLAMA_SERVER_BIN을 설정하세요."
            )

        # 기존에 다른 모델이 8080 포트를 점유하고 있으면 종료 후 새 모델 기동
        for existing_name, existing_proc in list(self._processes.items()):
            if existing_name != name and existing_proc.poll() is None:
                existing_proc.terminate()
                self._processes.pop(existing_name, None)

        parsed = urlparse(api_base)
        port = parsed.port or 8080
        cmd = [
            binary,
            "-m", model_file,
            "--host", "127.0.0.1",
            "--port", str(port),
            "-c", "4096",
            "-ngl", "99",
        ]
        process = self._process_factory(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._processes[name] = process
        if not self._wait_until_available(api_base, timeout=45.0):
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
