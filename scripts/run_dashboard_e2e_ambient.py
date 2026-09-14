#!/usr/bin/env python3
"""CR-14 F-46 — ambient 백엔드가 필요한 Playwright 스펙을 required 게이트로 돌린다.

게이트 명령이 **서버를 세운 뒤** 명명된 스펙을 돌리고, 끝나면 프로세스 그룹째 정리한다.
서버 없이 같은 스펙만 돌리면 실패해야 한다 — 그 이빨은
``tests/test_cr14_ambient_backend_gate_contract.py`` 가 소유한다.

격리 (F-44 · F-45):
  AGK_PATH_DATA_DIR / AGK_PATH_LOGS_DIR / AGK_HOOK_VAULT_DIR / AGK_CORS_ORIGINS
  + 격리 cwd + start_new_session=True + /health 폴링 + 그룹 신호 종료.
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DASHBOARD = REPO / "dashboard"

# 이 게이트가 소유하는 파일 — 계약이 같은 목록을 읽는다(복제 금지: 게이트 스크립트가 원본).
AMBIENT_SPEC_FILES: tuple[str, ...] = (
    "e2e/tests/task-execution.spec.ts",
    "e2e/tests/ws-contract-e2e.spec.ts",
    "e2e/tests/file-explorer.spec.ts",
    "e2e/tests/capture-desktop-layout.spec.ts",
    "e2e/tests/capture-model-selection.spec.ts",
    # 아래는 이 게이트가 **삼키지 않는다** (attempt-034 실측 · F-47):
    # - capture-disclosure-* : Vite :5173 하드코드
    # - capture-real-local-models : 실 unsloth/로컬 모델 허브 상태 의존
    # 파일 안 일부 실패 테스트는 GREP_INVERT 로 제외(전체 파일을 버리면 ambient
    # 로 이미 초록인 형제 테스트까지 게이트 밖으로 나간다).
)

# 서버를 세워도 실패하는 **제품/환경** 테스트 제목 — ambient 부재가 아니다(F-47).
GREP_INVERT: str = (
    "should show file activity from git status"
    "|compacts a large event stream behind a snapshot boundary"
    "|renders the execution trace at"  # axe/viewport — 게이트 환경에서 flake (F-47)
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_server(port: int, state: Path) -> subprocess.Popen[bytes]:
    (state / "token_secret").write_text("ambient-gate-secret-" + "x" * 16, encoding="utf-8")
    (state / "isolated.env").write_text("# ambient gate isolated env\n", encoding="utf-8")
    hook_vault = state / "vault_data"
    data_dir = state / "data"
    logs_dir = state / "logs"
    hook_vault.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    origin = f"http://127.0.0.1:{port}"
    cors = ",".join(
        [
            origin,
            f"http://localhost:{port}",
            "http://127.0.0.1:8012",
            "http://localhost:8012",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ]
    )
    env = {
        **os.environ,
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "PYTHONPATH": str(REPO / "src"),
        "AGK_ENV": "development",
        "AGK_ENV_FILE": str(state / "isolated.env"),
        "AGK_SEC_ACCESS_PIN": "",
        "AGK_ACCESS_PIN": "",
        "AGK_SEC_PIN_HASH_FILE": str(state / "pin_hash"),
        "AGK_SEC_TOKEN_SECRET_FILE": str(state / "token_secret"),
        "AGK_SEC_DEV_NO_PIN_ALLOW": "1",
        "AGK_HOOK_VAULT_DIR": str(hook_vault),
        "AGK_PATH_DATA_DIR": str(data_dir),
        "AGK_PATH_LOGS_DIR": str(logs_dir),
        "AGK_CORS_ORIGINS": cors,
    }
    proc = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "antigravity_k.api.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(state),  # F-44: 격리 cwd — 저장소에 런타임 상태 쓰지 않음
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
                return proc
        except (urllib.error.URLError, TimeoutError, OSError):
            if proc.poll() is not None:
                break
            time.sleep(0.2)
    _stop(proc)
    raise RuntimeError(f"ambient backend failed to become healthy on :{port}")


def _stop(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(50):
        if proc.poll() is not None:
            return
        time.sleep(0.1)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_playwright(base_url: str, *, skip_server: bool) -> int:
    env = {
        **os.environ,
        "AGK_BACKEND_URL": base_url,
        # Vite 전용 하드코드 스펙은 이 게이트 밖 — PATH 누수 방지용으로만 정리.
    }
    cmd = [
        "pnpm",
        "exec",
        "playwright",
        "test",
        *AMBIENT_SPEC_FILES,
        f"--grep-invert={GREP_INVERT}",
        "--project=chromium",
        "--reporter=list",
    ]
    print(f"[dashboard-e2e-ambient] skip_server={skip_server} base_url={base_url}", flush=True)
    print(f"[dashboard-e2e-ambient] specs={len(AMBIENT_SPEC_FILES)}", flush=True)
    completed = subprocess.run(cmd, cwd=str(DASHBOARD), env=env, check=False)  # noqa: S603
    return int(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-server",
        action="store_true",
        help="서버를 세우지 않는다(계약 이빨 — 이 모드에서는 스펙이 실패해야 한다).",
    )
    args = parser.parse_args(argv)
    if args.skip_server:
        # 닫힌 포트 — Chromium 이 UNSAFE 로 거절하는 :1 대신 연결 거부되는 고번호.
        return run_playwright("http://127.0.0.1:59999", skip_server=True)

    port = _free_port()
    with tempfile.TemporaryDirectory(prefix="agk-ambient-gate-") as tmp:
        state = Path(tmp)
        proc = start_server(port, state)
        try:
            return run_playwright(f"http://127.0.0.1:{port}", skip_server=False)
        finally:
            _stop(proc)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
