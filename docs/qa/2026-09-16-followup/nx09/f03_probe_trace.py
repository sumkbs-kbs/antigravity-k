#!/usr/bin/env python3
"""NX-09-F03 추적 탐침 — 첨부가 **어느 seam 에서 사라지는가**.

브라우저 E2E 는 "결국 provider 본문에 이미지가 없다"까지만 말해 준다. 이 탐침은
앱을 **프로세스 안에서** 띄우고 다중모달 seam 을 감싸서 호출 횟수/이미지 개수를
기록한다 — 실패 지점이 함수 이름으로 나온다.

사용자 데이터·프로젝트는 쓰지 않는다(임시 디렉터리 + 임시 포트).
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(SRC))

PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/AF+6L4AAAAASUVORK5CYII="

CAPTURED: list[dict[str, Any]] = []


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class _CaptureHandler(BaseHTTPRequestHandler):
    """provider 대역 — 요청 본문을 그대로 기록하고 고정 응답을 돌려준다."""

    def log_message(self, *args: object) -> None:  # noqa: D102 - 조용히
        return

    def _reply(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server 규약
        if self.path.endswith("/api/tags"):
            self._reply({"models": [{"name": "probe-model", "model": "probe-model"}]})
            return
        self._reply({"models": [{"name": "probe-model", "model": "probe-model"}]})

    def do_POST(self) -> None:  # noqa: N802 - http.server 규약
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        CAPTURED.append({"path": self.path, "body_len": len(raw), "has_image": PNG_B64[:16] in raw})
        if "/api/chat" in self.path:
            self._reply({"message": {"role": "assistant", "content": "PROBE-REPLY"}, "done": True})
            return
        self._reply({"choices": [{"message": {"role": "assistant", "content": "PROBE-REPLY"}}]})


def prepare_env(state: Path, provider_port: int) -> None:
    (state / "data").mkdir(parents=True, exist_ok=True)
    (state / "logs").mkdir(parents=True, exist_ok=True)
    (state / "empty.env").write_text("# isolated\n", encoding="utf-8")
    (state / "token_secret").write_text(secrets.token_hex(32), encoding="utf-8")
    (state / "projects.json").write_text(
        json.dumps(
            [
                {
                    "id": "default",
                    "name": "f03-probe",
                    "path": str(state),
                    "is_active": True,
                    "last_accessed_at": "2026-01-05T09:00:00.000000",
                    "tasks": [],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    os.environ.update(
        {
            "AGK_ENV": "development",
            "AGK_ENV_FILE": str(state / "empty.env"),
            "AGK_SEC_ACCESS_PIN": "probe-pin",
            "AGK_SEC_PIN_HASH_FILE": str(state / "pin_hash"),
            "AGK_SEC_TOKEN_SECRET_FILE": str(state / "token_secret"),
            "AGK_PATH_DATA_DIR": str(state / "data"),
            "AGK_PATH_LOGS_DIR": str(state / "logs"),
            "AGK_CONVERSATION_STORE_DIR": str(state / "conversations"),
            "AGK_TASK_DB_PATH": str(state / "tasks.db"),
            "AGK_ALLOWED_ROOTS": str(state),
            "AGK_HOOK_VAULT_DIR": str(state / "vault"),
            "AGK_MODEL_API_BASE": f"http://127.0.0.1:{provider_port}/v1",
            "AGK_MODEL_API_KEY": "probe",
            "AGK_PROVIDER": "ollama",
            "AGK_OLLAMA_API_BASE": f"http://127.0.0.1:{provider_port}",
            "PYTHONPATH": str(SRC),
        }
    )
    os.environ.pop("AGK_SEC_DEV_NO_PIN_ALLOW", None)


def instrument() -> dict[str, list[Any]]:
    """다중모달 seam 을 감싸 호출과 이미지 개수를 기록한다."""
    from antigravity_k.engine import multimodal

    trace: dict[str, list[Any]] = {
        "attach_to_latest_user_turn": [],
        "collect_images": [],
        "prompt_message": [],
        "normalize_message": [],
    }

    original_attach = multimodal.attach_to_latest_user_turn

    def attach(messages: list[dict[str, object]], attachments: list[Any]) -> list[dict[str, object]]:
        out = original_attach(messages, attachments)
        trace["attach_to_latest_user_turn"].append(
            {"attachments": len(attachments), "images_on_last": len(multimodal.extract_images(out[-1]))}
        )
        return out

    original_collect = multimodal.collect_images

    def collect(messages: object) -> list[tuple[str, str]]:
        found = original_collect(messages)
        trace["collect_images"].append(len(found))
        return found

    original_prompt_message = multimodal.prompt_message

    def prompt_message(prompt: str, raw_images: object) -> dict[str, object]:
        message = original_prompt_message(prompt, raw_images)
        trace["prompt_message"].append(len(multimodal.extract_images(message)))
        return message

    original_normalize = multimodal.normalize_message

    def normalize(message: dict[str, object]) -> dict[str, object]:
        out = original_normalize(message)
        trace["normalize_message"].append(len(multimodal.extract_images(out)))
        return out

    multimodal.attach_to_latest_user_turn = attach
    multimodal.collect_images = collect
    multimodal.prompt_message = prompt_message
    multimodal.normalize_message = normalize

    # manager seam — "프롬프트 문자열 + images" 로 왔는지, raw_messages 로 왔는지.
    from antigravity_k.engine.model_manager import ModelManager

    trace["manager_calls"] = []
    for method_name in ("stream_generate", "_do_ollama_stream", "_do_ollama_generate", "_prepare_stream_messages"):
        original = getattr(ModelManager, method_name)

        def wrapper(self: Any, *args: Any, __name: str = method_name, __original: Any = original, **kwargs: Any) -> Any:
            raw = kwargs.get("raw_messages")
            images = kwargs.get("images")
            raw_images = 0
            if isinstance(raw, list):
                raw_images = sum(len(multimodal.extract_images(m)) for m in raw if isinstance(m, dict))
            trace["manager_calls"].append(
                {
                    "method": __name,
                    "kwarg_images": len(images) if isinstance(images, list) else 0,
                    "has_raw_messages": isinstance(raw, list),
                    "raw_message_images": raw_images,
                    "prompt_images": (
                        len(multimodal.extract_images({"role": "user", "content": args[0]}))
                        if args and isinstance(args[0], str)
                        else 0
                    ),
                }
            )
            return __original(self, *args, **kwargs)

        setattr(ModelManager, method_name, wrapper)
    return trace


def main() -> int:
    state = Path(tempfile.mkdtemp(prefix="agk-f03-probe-"))
    provider_port = free_port()
    prepare_env(state, provider_port)

    provider = ThreadingHTTPServer(("127.0.0.1", provider_port), _CaptureHandler)
    threading.Thread(target=provider.serve_forever, daemon=True).start()

    trace = instrument()

    import httpx
    import uvicorn

    from antigravity_k.api.server import app

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.3)
    else:
        print(json.dumps({"error": "server did not start"}, ensure_ascii=False))
        return 1

    report: dict[str, Any] = {"base_url": base, "provider_port": provider_port}
    try:
        with httpx.Client(base_url=base, timeout=120) as client:
            login = client.post("/api/auth/login", json={"pin": "probe-pin"})
            token = login.json().get("access_token", "")
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "model": "probe-model",
                "project_id": "default",
                "stream": True,
                "agent_mode": True,
                "use_conversation_store": False,
                "messages": [{"role": "user", "content": "이 이미지를 봐줘"}],
                "new_turn": {"role": "user", "content": "이 이미지를 봐줘"},
                "conversation_id": f"conv_probe_{secrets.token_hex(4)}",
                "attachments": [{"name": "probe.png", "mime_type": "image/png", "data_base64": PNG_B64}],
            }
            with client.stream("POST", "/v1/chat/completions", json=payload, headers=headers) as response:
                report["status"] = response.status_code
                chunks = []
                for line in response.iter_lines():
                    if line:
                        chunks.append(line)
                    if len(chunks) > 40:
                        break
                report["first_lines"] = chunks[:6]
    except Exception as exc:  # noqa: BLE001 — 탐침: 실패를 그대로 보고한다
        report["exception"] = repr(exc)

    report["provider_requests"] = CAPTURED
    report["images_reached_provider"] = [entry for entry in CAPTURED if entry["has_image"]]
    report["trace"] = trace
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
