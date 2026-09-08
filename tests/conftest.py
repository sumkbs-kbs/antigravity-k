"""SEC-01 테스트 하네스 — 인증 정책의 명시적 dev 익명 허용 env 세팅.

SEC-01 이전에는 테스트가 서버의 취약 분기("plaintext PIN 부재 시 loopback 익명
허용")에 암묵적으로 의존했다. 정책이 fail-closed로 바뀌면서 익명 허용은
``AGK_SEC_DEV_NO_PIN_ALLOW`` 명시 설정이 필요하다 — 테스트도 동일한 명시적
계약을 따른다 (production 코드와 같은 문을 통과).

자격증명 격리:
  - ``AGK_SEC_ACCESS_PIN``/``AGK_SEC_PIN_HASH_FILE``/``AGK_SEC_TOKEN_SECRET_FILE``을
    세션 임시 디렉터리로 향하게 하여, 개발자 로컬 ``data/auth_hash``가 테스트
    실행 중 스캔되지 않게 한다 (결정론적 상태).
  - hash 파일을 만들지 않으면 정책은 credential 전무 상태가 되고, dev-allow env와
    결합해 기존 테스트가 기대하던 "익명 허용" 동작이 재현된다.

개별 인증 테스트(test_auth.py, test_auth_policy_truth_table.py)는 이 fixture가
설정한 값을 monkeypatch로 덮어쓸 수 있다 — fixture는 세션 시작 시 1회 적용이며
테스트가 끝나면 원래 환경으로 복원한다.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _reset_bound_execution_context() -> Iterator[None]:
    """테스트 경계마다 ARC-01 바인딩된 실행 컨텍스트를 해제한다.

    ``resolve_project_execution_context(bind=True)`` (chat/task route)는 실서버에서
    요청별 contextvar 분리로 누수가 없지만, 테스트는 같은 스레드에서 연속 실행되므로
    바인딩이 다음 테스트로 새어 나가 ``effective_project_root()`` 기반 경로 검사
    (WS-02 sandbox)를 오염시킨다. 시작·종료 양쪽에서 리셋해 테스트 순서 무관성을 보장.
    """
    from antigravity_k.api.project_binding import reset_bound_request_execution_context

    reset_bound_request_execution_context()
    yield
    reset_bound_request_execution_context()


@pytest.fixture(scope="session", autouse=True)
def _sec01_test_auth_harness() -> Iterator[None]:
    """세션 전체: SEC-01 명시적 dev 익명 허용 + 자격증명 격리."""
    from antigravity_k.config import config

    orig = {
        "access_pin": os.environ.get("AGK_SEC_ACCESS_PIN"),
        "pin_hash_file": os.environ.get("AGK_SEC_PIN_HASH_FILE"),
        "token_secret_file": os.environ.get("AGK_SEC_TOKEN_SECRET_FILE"),
        "dev_allow": os.environ.get("AGK_SEC_DEV_NO_PIN_ALLOW"),
    }
    tmpdir = Path(tempfile.mkdtemp(prefix="sec01-auth-"))

    os.environ["AGK_SEC_DEV_NO_PIN_ALLOW"] = "1"
    os.environ["AGK_SEC_ACCESS_PIN"] = ""
    os.environ["AGK_SEC_PIN_HASH_FILE"] = str(tmpdir / "auth_hash")
    os.environ["AGK_SEC_TOKEN_SECRET_FILE"] = str(tmpdir / "token_secret")

    # 이미 임포트된 config 인스턴스에도 반영 (BaseSettings는 env를 생성 시 읽음).
    config.security.access_pin = ""
    config.security.pin_hash_file = str(tmpdir / "auth_hash")
    config.security.token_secret_file = str(tmpdir / "token_secret")

    # auth_routes 모듈 상태 재초기화 — 새 자격증명 경로로 부트스트랩.
    import antigravity_k.api.auth_routes as auth_routes_mod

    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
    auth_routes_mod.init_auth_state()

    # WS-01 계약: chat/task route는 project_id 또는 session active-project
    # binding을 요구한다. 기본 세션("default")을 레지스트리의 active project에
    # binding해 두면 라우트 테스트가 실제 사용자 플로우(프로젝트 연 뒤 대화)
    # 와 동일한 상태에서 실행된다. binding이 없던 테스트는 WS-01 게이트에서
    # MissingExecutionContextError로 실패했었다 (2026-09-07 정리).
    from antigravity_k.api.project_binding import bind_session_active_project
    from antigravity_k.engine.project_registry import get_project_registry

    try:
        active = get_project_registry().get_active_project()
        bind_session_active_project("", active.id)
    except Exception:
        pass  # registry 부트 실패 시에도 기존 테스트 동작은 유지

    yield

    for key, value in orig.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    # config 인스턴스는 프로세스 종료와 함께 버려지므로 복원 불필요.
    auth_routes_mod._token_service = None
    auth_routes_mod._pin_hash = None
