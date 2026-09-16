#!/usr/bin/env python
"""NX-05 before/after driver: does a PIN change revoke existing sessions?

Run against two trees:

    rm -rf /tmp/nx05-before && mkdir -p /tmp/nx05-before
    git archive HEAD src | tar -x -C /tmp/nx05-before

    NX05_TREE=before PYTHONPATH=/tmp/nx05-before/src .venv/bin/python \
        docs/qa/2026-09-16-followup/nx05/repro_nx05_pin_change_revocation.py > before.json
    NX05_TREE=after PYTHONPATH=src .venv/bin/python \
        docs/qa/2026-09-16-followup/nx05/repro_nx05_pin_change_revocation.py > after.json

Probes (all observable over the public HTTP surface, no private state assumed):

* 이전 bearer 가 PIN 변경 뒤에도 보호 경로를 통과하는가,
* 이전 PIN 으로 로그인해 **새 세대 토큰**을 받을 수 있는가 (폐기 무력화),
* 새 PIN 로그인이 되는가,
* change-pin 응답이 재인증 필요를 알리는가,
* PIN 변경 전에 발급한 단기 WS ticket 이 변경 뒤에도 소비되는가 (연결형 채널),
* 저장 문서가 (hash, epoch) 를 함께 담는가 / 폐기 API 가 존재하는가,
* **다른 프로세스가 PIN 을 바꿨을 때** 이 프로세스가 구 PIN 로그인을 계속 받는가
  (파일을 외부에서 교체해 캐시 동작을 관측 — 구 버전의 stale cache 결함).

종료 코드: 0 = 폐기 관측(수정 트리), 3 = 이전 자격증명이 살아 있음(결함 재현).
"""

from __future__ import annotations

import getpass
import json
import os
import tempfile
from pathlib import Path

PIN = "nx05-pin-1234"
NEW_PIN = "nx05-pin-5678"


def main() -> int:
    # 이 드라이버는 PYTHONPATH 로 어느 트리를 검사할지 결정한다.
    from antigravity_k.config import config

    tmpdir = Path(tempfile.mkdtemp(prefix=f"nx05-{getpass.getuser()}-"))
    config.security.access_pin = PIN
    config.security.pin_hash_file = str(tmpdir / "auth_hash")
    config.security.token_secret_file = str(tmpdir / "token_secret")

    import antigravity_k.api.auth_routes as auth_routes
    from antigravity_k.api.auth_policy import init_shared_auth_policy

    auth_routes._token_service = None
    auth_routes._pin_hash = None
    auth_routes.init_auth_state()
    _ = init_shared_auth_policy(config.security.pin_hash_file)

    from fastapi.testclient import TestClient

    from antigravity_k.api.server import app
    from antigravity_k.security.ws_ticket import get_ws_ticket_service

    state_path = Path(config.security.pin_hash_file)
    raw_state = state_path.read_text(encoding="utf-8").strip()

    report: dict[str, object] = {
        "tree": os.environ.get("NX05_TREE", "unknown"),
        "tree_module": str(Path(auth_routes.__file__).resolve()),
        "epoch_support_present": hasattr(auth_routes, "get_current_auth_epoch"),
        "state_document_is_json": raw_state.startswith("{"),
        "state_epoch": None,
    }

    def _restore_original_state() -> None:
        payload = json.dumps(
            {"schema": "agk.auth.v1", "pin_hash": hash_pin(PIN), "epoch": 1, "updated_at": 0.0},
            ensure_ascii=False,
            indent=2,
        )
        if report["state_document_is_json"]:
            state_path.write_text(payload + "\n", encoding="utf-8")
        else:
            state_path.write_text(hash_pin(PIN), encoding="utf-8")

    from antigravity_k.engine.auth import hash_pin

    with TestClient(app, raise_server_exceptions=False) as client:
        # ── 다른 프로세스가 PIN 을 바꿨을 때의 stale cache 관측 ──
        # 파일을 외부에서 교체한 뒤 구 PIN 로그인을 시도한다.
        if report["state_document_is_json"]:
            state_path.write_text(
                json.dumps(
                    {
                        "schema": "agk.auth.v1",
                        "pin_hash": hash_pin("nx05-other-process-pin"),
                        "epoch": 2,
                        "updated_at": 0.0,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        else:
            state_path.write_text(hash_pin("nx05-other-process-pin"), encoding="utf-8")
        external_login = client.post("/api/auth/login", json={"pin": PIN})
        report["old_pin_login_status_after_external_change"] = external_login.status_code
        report["old_pin_accepted_after_external_change"] = external_login.status_code == 200
        _restore_original_state()

        login = client.post("/api/auth/login", json={"pin": PIN})
        report["login_before_change_status"] = login.status_code
        old_token = login.json().get("access_token") if login.status_code == 200 else None

        # 연결형 채널 probe: PIN 변경 전에 ticket 을 발급한다.
        ticket_service = get_ws_ticket_service(auth_routes.get_token_service())
        stale_ticket = ticket_service.issue("nx05")

        token_for_change = auth_routes.get_token_service().issue_token(subject="nx05")
        changed = client.post(
            "/api/auth/change-pin",
            headers={"Authorization": f"Bearer {token_for_change}"},
            json={"current_pin": PIN, "new_pin": NEW_PIN},
        )
        report["change_pin_status"] = changed.status_code
        body = changed.json() if changed.status_code < 500 else {}
        report["change_pin_response_keys"] = sorted(body.keys()) if isinstance(body, dict) else []
        report["change_pin_reports_reauth"] = bool(body.get("reauth_required")) if isinstance(body, dict) else False

        if old_token is not None:
            probe = client.get("/api/vault/config", headers={"Authorization": f"Bearer {old_token}"})
            report["old_bearer_status_after_change"] = probe.status_code
            report["old_bearer_accepted_after_change"] = probe.status_code != 401
        else:
            report["old_bearer_status_after_change"] = None
            report["old_bearer_accepted_after_change"] = None

        old_pin_login = client.post("/api/auth/login", json={"pin": PIN})
        report["old_pin_login_status_after_change"] = old_pin_login.status_code
        report["old_pin_accepted_after_change"] = old_pin_login.status_code == 200
        new_pin_login = client.post("/api/auth/login", json={"pin": NEW_PIN})
        report["new_pin_login_status_after_change"] = new_pin_login.status_code
        report["new_pin_accepted_after_change"] = new_pin_login.status_code == 200

        # 이미 열린 연결의 폐기 경로가 제품에 존재하는가(실제 close 는 pytest 가 고정).
        from antigravity_k.api.routes import session_state

        report["open_ws_revocation_api_present"] = hasattr(session_state, "close_authorized_ws_blocking")
        report["stale_ws_ticket_subject_after_change"] = ticket_service.consume(stale_ticket)
        report["stale_ws_ticket_reusable"] = report["stale_ws_ticket_subject_after_change"] is not None

    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        report["state_epoch"] = parsed.get("epoch")
        report["state_schema"] = parsed.get("schema")

    leaked = [
        name
        for name in (
            "old_bearer_accepted_after_change",
            "old_pin_accepted_after_change",
            "old_pin_accepted_after_external_change",
            "stale_ws_ticket_reusable",
        )
        if report.get(name) is True
    ]
    report["revoked_and_rejected"] = not leaked
    report["still_valid_credentials"] = leaked

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["revoked_and_rejected"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
