"""CR-14 F-43 — 대시보드가 보내는 경로는 **서버가 서는 namespace** 안에 있어야 한다.

왜 필요한가
===========
`dashboard/src/api/client.ts` 의 `apiRequest(endpoint)` 는 `requestJson('/v1' + endpoint, ...)` 다 —
**접두사가 래퍼 안에서 붙는다.** 그래서 `apiRequest('/api/agent/ask')` 라고 적으면 실효 경로는
`/v1/api/agent/ask` 가 되고, 서버가 서는 `/api/agent/ask` 에는 **닿지 않는다**.

측정된 사실(attempt-033, 고침 전)
=================================
- `askAgent`(`client.ts`) → 실효 `/v1/api/agent/ask` · 서버에는 `/v1/api/*` 가 **없다**.
- `fetchWsTicket`(`utils/wsTicket.ts`) → 실효 `/v1/auth/ws-ticket` · 서버에는 `/v1/auth/*` 가
  **없다**. 살아 있는 서버가 둘 다 405(SPA fallback)로 막았다. 정본 `POST /api/auth/ws-ticket` 은
  200 + ticket 을 준다.
- 이 실패는 **조용하지 않은 채로 조용했다**: `fetchWsTicket` 은 `catch { return null }` 로 삼키고,
  ticket 없이 연결하면 WS 게이트(`routes/session_state.py`)는 `open_loopback` 일 때만 통과한다 —
  즉 **PIN 이 설정된(protected) 배포에서는 이벤트 스트림이 4401 로 거절되고 3초마다 재시도**한다.
  로컬 dev 익명 모드(`AGK_SEC_DEV_NO_PIN_ALLOW`)가 그 실패를 가린다.
- **왜 아무도 못 봤나**: 소스에 `/v1/auth/ws-ticket` 이라는 문자열이 **없다**(접두사는 래퍼가 만든다).
  `grep` 으로도, 리터럴만 모으는 대조로도 보이지 않는다.

무엇을 소유하는가
=================
**래퍼를 해석한 실효 경로의 첫 두 마디(namespace)가 서버 라우트 표에 존재해야 한다**는 하나의
불변식. 문자열 조립에서 오는 잡음(쿼리 보간·뒤에 붙는 id)에 흔들리지 않도록 **정확 일치**가 아니라
**namespace 도달성**을 잰다 — 이 결함 부류(잘못된 접두사)를 정확히 잡으면서 거짓 실패를 내지 않는다.

재지 않는 것
============
- **응답의 내용**은 재지 않는다 — 여기서 재는 것은 **도달 가능성**뿐이다.
- **메서드 일치**는 재지 않는다(경로 오타 부류가 대상이다).
- 동적으로 조립되는 경로(예: 변수에 담긴 base)는 정적 접두만 본다 — 그 자리는 이 계약의 사각이다.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DASH_SRC = REPO_ROOT / "dashboard" / "src"
API_BASE = "/v1"  # dashboard/src/api/client.ts 의 API_BASE


# ─────────────────────────── 추출기 (계약의 자) ───────────────────────────
def _static(literal: str) -> str:
    """템플릿 리터럴의 **정적 접두**만 취한다 — `${…}` 뒤는 경로가 아니다(쿼리·id 조립)."""
    return literal.split("${", 1)[0].split("?", 1)[0].strip()


def _norm(path: str) -> str:
    """`{name}`·`{name:path}` 를 하나의 param 자리로 접어 서버 표와 비교 가능하게 만든다."""
    return re.sub(r"\{[^}]*\}", "{p}", path)


def _method(window: str) -> str:
    return "POST" if re.search(r"method:\s*['\"]POST['\"]", window) else "GET"


def _strip_comments(text: str) -> str:
    """주석을 지운다 — 주석 안의 경로가 위반이 되거나(거짓 양성) 결함을 가리는(거짓 음성)
    일을 막는다. 이 계약의 자(ruler)는 **실행되는 코드**만 본다."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def _api_sources() -> list[tuple[str, str]]:
    """(source_path, text) — 테스트 파일은 제외하고 주석은 지운 대시보드 소스."""
    out: list[tuple[str, str]] = []
    for path in sorted(DASH_SRC.rglob("*.ts*")):
        src = path.relative_to(REPO_ROOT).as_posix()
        if "__tests__" in src or ".test." in src:
            continue
        out.append((src, _strip_comments(path.read_text(encoding="utf-8"))))
    return out


def resolved_calls() -> list[tuple[str, str, str]]:
    """(effective_path, method, source) — **래퍼를 해석한** 대시보드의 요청 목록."""
    out: list[tuple[str, str, str]] = []
    for src, text in _api_sources():
        # apiRequest(fragment) → '/v1' + fragment
        for m in re.finditer(r"\bapiRequest\(\s*(['\"`])([^'\"`]*)\1", text):
            frag = _static(m.group(2))
            if not frag.startswith("/"):
                continue  # 래퍼 정의(`${API_BASE}${endpoint}`) 등 — 호출부가 아니다
            out.append((_norm(API_BASE + frag), _method(text[m.end() : m.end() + 400]), src))
        # apiRequestPath(path) · requestJson(path, …) — 전체 경로를 그대로 받는다
        for fn in ("apiRequestPath", "requestJson"):
            for m in re.finditer(rf"\b{fn}\(\s*(['\"`])([^'\"`]*)\1", text):
                full = _static(m.group(2))
                if full.startswith("/"):
                    out.append((_norm(full), _method(text[m.end() : m.end() + 400]), src))
        # raw fetch('/api/…', …)
        for m in re.finditer(r"""\bfetch\(\s*(['\"`])(/api/[^'\"`]*)\1""", text):
            full = _static(m.group(2))
            if full.startswith("/"):
                out.append((_norm(full), _method(text[m.end() : m.end() + 400]), src))
    return out


def literal_only_paths() -> set[str]:
    """래퍼를 해석하지 않고 **소스 리터럴만** 모은 경로 — 이 결함의 눈먼 자리."""
    found: set[str] = set()
    for _, text in _api_sources():
        for pre in ("/v1/", "/api/"):
            for m in re.finditer(rf"""['"`]({re.escape(pre)}[^'"`]*)['"`]""", text):
                found.add(_norm(_static(m.group(1))))
    return found


def namespace(path: str) -> str:
    """경로의 첫 두 마디 — 라우트 표가 실제로 서비스하는 구역인가."""
    return "/" + "/".join([s for s in path.split("/") if s][:2])


def server_namespaces() -> set[str]:
    from antigravity_k.api.server import app  # noqa: PLC0415

    return {namespace(_norm(getattr(r, "path", ""))) for r in app.routes if getattr(r, "path", "")}


# ─────────────────────────────── 조항 ───────────────────────────────
def test_every_client_path_lands_in_a_namespace_the_server_serves() -> None:
    """핵심 불변식 — 서버에 없는 namespace 로 나가는 호출이 하나도 없어야 한다."""
    serves = server_namespaces()
    offenders = sorted({(path, method, src) for path, method, src in resolved_calls() if namespace(path) not in serves})
    assert not offenders, "대시보드가 서버에 없는 namespace 로 요청한다(래퍼 접두사를 확인하라 — F-43):\n" + "\n".join(
        f"  {m} {p} ← {s}" for p, m, s in offenders
    )


def test_resolved_calls_are_not_empty_and_cover_both_wrappers() -> None:
    """자의 전제 — 추출이 실제로 일어나고, 두 래퍼 형태가 모두 잡혀야 한다."""
    calls = resolved_calls()
    paths = {p for p, _, _ in calls}
    assert len(calls) > 20, f"추출된 호출부가 너무 적다({len(calls)}) — 자가 고장났을 수 있다"
    assert any(p.startswith("/v1/") for p in paths), "apiRequest 경로가 하나도 없다"
    assert any(p.startswith("/api/") for p in paths), "전체 경로 호출이 하나도 없다"


def test_extractor_applies_the_wrapper_prefix_and_ignores_its_own_definition() -> None:
    """자(ruler)의 자기 검사 — 접두사 규칙과 래퍼 정의 제외가 실제로 동작한다."""
    # 접두사가 붙는가
    assert _norm(API_BASE + "/models") == "/v1/models"
    # 쿼리 보간은 경로가 아니다
    assert _static("/api/fs/browse${query}") == "/api/fs/browse"
    # 리터럴이 비면 호출부가 아니다(래퍼 정의)
    assert _static("${API_BASE}${endpoint}") == ""
    # 추출 결과에 래퍼 정의가 섞이지 않는다
    assert "" not in {p for p, _, _ in resolved_calls()}


def test_the_two_known_defects_stay_closed() -> None:
    """F-43 회귀 — 두 자리가 **전체 경로**로 나가야 한다(래퍼 접두사가 붙으면 안 된다)."""
    calls = resolved_calls()
    post_paths = {p for p, m, _ in calls if m == "POST"}
    assert "/api/auth/ws-ticket" in post_paths, (
        "fetchWsTicket 이 정본 경로로 나가지 않는다 — '/v1/auth/ws-ticket' 로 되돌아갔는지 보라"
    )
    assert "/api/agent/ask" in post_paths, (
        "askAgent 가 정본 경로로 나가지 않는다 — '/v1/api/agent/ask' 로 되돌아갔는지 보라"
    )


def test_the_dead_paths_are_gone_from_the_client() -> None:
    """고침 전 실효 경로 두 개가 다시 등장하면 실패한다."""
    paths = {p for p, _, _ in resolved_calls()}
    assert "/v1/auth/ws-ticket" not in paths
    assert "/v1/api/agent/ask" not in paths


def test_the_ticket_call_is_invisible_to_a_literal_only_sweep() -> None:
    """이 발견의 핵심을 고정한다 — 리터럴만 보는 검사로는 그 자리가 **보이지 않는다**.

    즉 앞으로 이 부류를 잡으려면 래퍼를 해석해야 한다. 이 조항은 'literal 전용 검사가
    충분하다'는 착각이 계약에 다시 들어오는 것을 막는다.
    """
    literals = literal_only_paths()
    resolved = {p for p, _, _ in resolved_calls()}
    blind = {p for p in resolved if p not in literals}
    # 래퍼가 만드는 경로는 리터럴에 없다 — 그 자리가 존재한다는 사실 자체를 고정
    assert blind, "래퍼가 만드는 경로가 하나도 없다면 자가 규칙을 잃은 것이다"
    assert "/v1/auth/ws-ticket" not in literals
