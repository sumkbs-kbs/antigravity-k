"""번들 ssak-search provider 로 기존 web_search 를 연결하는 routing 계층 (task 13).

이 모듈이 정하는 **세 가지 결정**과, 그 결정을 어기지 않게 지키는 규칙:

1. **켤 것인가** — `search.ssak.enabled`(기본 **false**). 꺼져 있으면 아무 일도 일어나지 않고
   기존 4-engine 경로가 그대로 돈다(기존 결과 계약 유지).
2. **어디로 보낼 것인가** — `mode=bundled_stdio` → task 12 의 런타임(호스트당 child 1개).
   성공하면 그 호출 **한 번**으로 끝난다 — 같은 질의를 legacy engine 으로 다시 훑지 않는다.
3. **실패하면 어떻게 할 것인가** — `fallback=legacy_on_transient` → **transient** 실패에만
   **정확히 1회** legacy 로 대체한다. 그 밖의 실패는 장애가 아니라 **결정**이므로 대체하지 않는다:
   POLICY_DENIED(사용자가 이 요청에서 껐다) · INVALID_ARGUMENT(우리 입력이 틀렸다) ·
   AUTH_REQUIRED(자격 증명 문제) · RUNTIME_DISABLED(설정으로 껐다) · artifact 거절(어느 bytes 를
   실행하는지 모른다) · 알 수 없는 예외. 대체하면 그 결정이 조용히 사라진다.

그리고 `artifact_path` 는 **신뢰된 루트 아래**의 파일만 받는다(심볼릭 링크를 해석한 뒤 판정).
경로 하나가 임의 실행 지점이 되는 것을 막는 자리다.

동기 `execute` 안에서 이 경로는 **이벤트 루프를 중첩 실행하지 않는다** — 런타임의 `call_tool` 은
자기 전용 루프에 큐로 넘기는 동기 호출이라, 이미 돌고 있는 루프 안에서도 `run_until_complete` 가
필요 없다(acceptance 의 "sync wrapper 는 nested run 으로 막지 않는다").
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

from antigravity_k.engine.tool_policy import mcp_server_policy_denial

if TYPE_CHECKING:  # pragma: no cover — 순환 import 방지(설정/런타임은 지연 import)
    from antigravity_k.tools.mcp_tool_result import MCPToolOutcome
    from antigravity_k.tools.ssak_search_runtime import SearchRuntimeConfig

logger = logging.getLogger(__name__)

BUNDLED_SERVER_NAME = "ssak_search"
BUNDLED_TOOL_NAME = "ssak_search"
SUPPORTED_MODES: frozenset[str] = frozenset({"bundled_stdio"})
FALLBACK_POLICIES: frozenset[str] = frozenset({"legacy_on_transient", "none"})
DEFAULT_MANIFEST_NAME = "ssak-search-manifest.json"
MANIFEST_RELATIVE_DIR = "release"
TRUSTED_ROOTS_ENV = "AGK_SEARCH_TRUSTED_ROOTS"

# 일시적 장애: 대체(fallback)가 허용된다. `CIRCUIT_OPEN` 은 **반복된 transient 실패의 결과**이므로
# 여기 포함한다(회로가 열려 있다는 사실 자체가 "지금은 번들이 못 한다"는 뜻이다).
TRANSIENT_ERROR_CODES: frozenset[str] = frozenset(
    {
        "TIMEOUT",
        "TRANSPORT_LOST",
        "CHILD_EXITED",
        "RUNTIME_STOPPED",
        "RUNTIME_NOT_READY",
        "CIRCUIT_OPEN",
        "UPSTREAM_UNAVAILABLE",
    }
)

# 결정적인 실패: 대체 금지. 대체하면 사용자/설정의 **결정**이 조용히 뒤집힌다.
PERMANENT_ERROR_CODES: frozenset[str] = frozenset(
    {
        "POLICY_DENIED",
        "INVALID_ARGUMENT",
        "INVALID_TOOL_ARGS",
        "AUTH_REQUIRED",
        "UNKNOWN_TOOL",
        "RUNTIME_DISABLED",
        "NON_IDEMPOTENT_NOT_RETRIED",
        "ARTIFACT_REJECTED",
        "UNTRUSTED_ARTIFACT_PATH",
        "CANCELLED",
    }
)


@dataclass(frozen=True)
class SsakSearchSettings:
    """`search.ssak.*` 의 스냅숏. `problem` 이 있으면 설정 자체가 잘못된 것이다(라우팅하지 않는다)."""

    enabled: bool = False
    mode: str = "bundled_stdio"
    fallback: str = "legacy_on_transient"
    artifact_path: str | None = None
    manifest_path: str | None = None
    problem: str | None = None
    extra_trusted_roots: tuple[str, ...] = ()

    @property
    def mode_supported(self) -> bool:
        return self.mode in SUPPORTED_MODES

    @property
    def fallback_on_transient(self) -> bool:
        return self.fallback == "legacy_on_transient"

    def route_reason(self) -> str:
        """왜 legacy 로 가는가 — 로그/시험에서 읽는 한 줄."""
        if not self.enabled:
            return "search.ssak.enabled=false (opt-in 하지 않음)"
        if self.problem:
            return f"invalid search.ssak configuration: {self.problem}"
        if not self.mode_supported:
            return f"unsupported search.ssak.mode={self.mode}"
        return "bundled_stdio"


@dataclass(frozen=True)
class ProviderAttempt:
    """번들 provider 호출 결과. `transient` 는 "대체가 허용되는가"의 답이다."""

    ok: bool
    transient: bool
    message: str
    results: list[tuple[str, str, str]] = field(default_factory=list)
    error_code: str | None = None
    engine: str = "SsakBundle"

    @property
    def failure_class(self) -> str:
        if self.ok:
            return "ok"
        return "transient" if self.transient else "permanent"


def classify_error_code(code: str | None) -> str:
    """오류 코드를 ok/transient/permanent 로 분류한다(알 수 없는 코드는 **permanent**).

    모르는 실패를 transient 로 넘기면 legacy 가 조용히 2차 실행된다 — 그게 이 계층이 막으려는
    실패 모드다. 모르면 대체하지 않고 드러낸다.
    """
    if not code:
        return "permanent"
    if code in TRANSIENT_ERROR_CODES:
        return "transient"
    if code in PERMANENT_ERROR_CODES:
        return "permanent"
    return "permanent"


# ── 설정 ─────────────────────────────────────────────────────────────────────


def settings_snapshot(app_config: object | None = None) -> SsakSearchSettings:
    """현재 설정에서 `search.ssak.*` 를 읽는다.

    설정 로드 실패는 **꺼진 것으로 처리**한다(검색 도구가 설정 오류로 죽으면 안 되고, 꺼진 상태는
    기존 동작 그대로다). 다만 이유는 `problem` 에 남겨 로그/시험에서 보이게 한다.
    """
    try:
        section = _read_section(app_config)
    except Exception as exc:  # noqa: BLE001 — 설정 오류로 도구를 죽이지 않는다
        logger.warning("search.ssak 설정을 읽지 못했습니다: %s", exc)
        return SsakSearchSettings(problem=f"config load failed: {exc}")
    if section is None:
        return SsakSearchSettings()
    return SsakSearchSettings(
        enabled=bool(_field(section, "enabled", False)),
        mode=str(_field(section, "mode", "bundled_stdio")),
        fallback=str(_field(section, "fallback", "legacy_on_transient")),
        artifact_path=_optional_text(_field(section, "artifact_path", None)),
        manifest_path=_optional_text(_field(section, "manifest_path", None)),
        problem=_validate(section),
        extra_trusted_roots=extra_trusted_roots(),
    )


def _read_section(app_config: object | None) -> Mapping[str, object] | None:
    if app_config is None:
        from antigravity_k.config import AppConfig

        app_config = AppConfig()
    search = getattr(app_config, "search", None)
    if search is None:
        return None
    ssak = getattr(search, "ssak", None)
    if ssak is None:
        return None
    if isinstance(ssak, Mapping):
        return cast(Mapping[str, object], ssak)
    dump = getattr(ssak, "model_dump", None)
    if callable(dump):
        return cast(Mapping[str, object], dump())
    return None


def _field(section: Mapping[str, object], key: str, default: object) -> object:
    value = section.get(key, default)
    return default if value is None else value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _validate(section: Mapping[str, object]) -> str | None:
    mode = str(_field(section, "mode", "bundled_stdio"))
    if mode not in SUPPORTED_MODES:
        return f"mode must be one of {sorted(SUPPORTED_MODES)}, got {mode!r}"
    fallback = str(_field(section, "fallback", "legacy_on_transient"))
    if fallback not in FALLBACK_POLICIES:
        return f"fallback must be one of {sorted(FALLBACK_POLICIES)}, got {fallback!r}"
    enabled = bool(_field(section, "enabled", False))
    if enabled and not _optional_text(_field(section, "artifact_path", None)):
        return "enabled=true requires artifact_path (fail-closed: 어느 bytes 를 실행할지 모른다)"
    return None


# ── 신뢰 경로 ────────────────────────────────────────────────────────────────


def extra_trusted_roots(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """`AGK_SEARCH_TRUSTED_ROOTS` (os.pathsep 구분). 운영자/시험이 추가하는 루트."""
    source = env if env is not None else os.environ
    raw = str(source.get(TRUSTED_ROOTS_ENV, "") or "")
    return tuple(part.strip() for part in raw.split(os.pathsep) if part.strip())


def trusted_roots(extra: Sequence[str] = ()) -> tuple[Path, ...]:
    """artifact 가 있을 수 있는 루트들: 설치된 패키지 루트 · 사용자 데이터 디렉터리 · 명시 루트."""
    roots: list[Path] = []
    for candidate in (
        Path(__file__).resolve().parents[3],  # 설치/개발 트리 루트
        Path.home() / ".antigravity-k",
        *(Path(item) for item in extra),
    ):
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:  # pragma: no cover — 해석 불가 경로는 신뢰하지 않는다
            continue
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def is_trusted_artifact_path(path: str | os.PathLike[str] | None, extra: Sequence[str] = ()) -> bool:
    """`path`(심볼릭 링크 해석 후)가 신뢰된 루트 안에 있는가."""
    if path is None:
        return False
    try:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            return False
        resolved = candidate.resolve()
    except OSError:  # pragma: no cover
        return False
    for root in trusted_roots(extra):
        if resolved == root or root in resolved.parents:
            return True
    return False


def resolve_manifest_path(artifact: str | os.PathLike[str] | None, explicit: str | None) -> Path | None:
    """매니페스트 경로를 찾는다: 명시 > artifact 옆 `release/` 규약 > env.

    task 11 의 번들 배치가 `bin/ssak-mcp` + `release/ssak-search-manifest.json` 이므로 그 규약을
    따른다. 못 찾으면 `None` 을 돌려주고, 런타임이 **fail-closed** 로 거절한다(여기서 추측하지 않는다).
    """

    def _from_env() -> Path | None:
        # 빈 문자열은 "설정하지 않음"이다 — `Path("")` 은 `.` 이라 매니페스트 검사가 디렉터리를 읽는다.
        raw = str(os.environ.get("AGK_SEARCH_MANIFEST", "") or "").strip()
        return Path(raw) if raw else None

    if explicit:
        return Path(explicit).expanduser()
    if not artifact:
        return _from_env()
    parent = Path(artifact).expanduser().resolve().parent
    for candidate in (
        parent / DEFAULT_MANIFEST_NAME,  # artifact 옆
        parent / MANIFEST_RELATIVE_DIR / DEFAULT_MANIFEST_NAME,  # <root>/bin/x + <root>/bin/release/x
        parent.parent / MANIFEST_RELATIVE_DIR / DEFAULT_MANIFEST_NAME,  # task 11 배치: <root>/bin/x + <root>/release/x
    ):
        if candidate.is_file():
            return candidate
    return _from_env()


# ── 호출 ─────────────────────────────────────────────────────────────────────


def _runtime_config(settings: SsakSearchSettings) -> SearchRuntimeConfig:
    from antigravity_k.tools.ssak_search_runtime import SearchRuntimeConfig

    manifest = resolve_manifest_path(settings.artifact_path, settings.manifest_path)
    return SearchRuntimeConfig(
        artifact_path=settings.artifact_path,
        manifest_path=str(manifest) if manifest is not None else None,
        enabled=True,
        server_name=BUNDLED_SERVER_NAME,
    )


def _hits_from_outcome(outcome: MCPToolOutcome) -> list[tuple[str, str, str]]:
    """MCP 결과에서 (title, url, snippet) 을 꺼낸다 — structuredContent 우선, 없으면 본문 JSON."""
    structured = getattr(outcome, "structured_content", None)
    payload: object = structured if isinstance(structured, Mapping) else None
    if payload is None:
        text = str(outcome)
        start = text.find("{")
        if start >= 0:
            try:
                payload = json.loads(text[start:])
            except json.JSONDecodeError:
                payload = None
    if not isinstance(payload, Mapping):
        return []
    mapping = cast(Mapping[str, object], payload)
    raw_hits = mapping.get("hits", mapping.get("results", []))
    if not isinstance(raw_hits, list):
        return []
    hits: list[tuple[str, str, str]] = []
    for item in cast(list[object], raw_hits):
        if not isinstance(item, Mapping):
            continue
        entry = cast(Mapping[str, object], item)
        title = str(entry.get("title") or "").strip()
        url = str(entry.get("url") or "").strip()
        snippet = str(entry.get("snippet") or entry.get("description") or "").strip()
        if title or url:
            hits.append((title or url, url, snippet))
    return hits


def search_with_bundled_provider(
    query: str,
    *,
    max_results: int = 8,
    settings: SsakSearchSettings,
    runtime: object | None = None,
) -> ProviderAttempt:
    """번들 child 에 **한 번** 질의한다. 예외는 실패 결과로 돌려준다(도구가 죽지 않는다).

    `runtime` 은 시험/대체용 주입 지점이다. 주지 않으면 호스트 싱글턴(task 12)을 쓴다 —
    "한 host instance 가 한 child 를 관리한다"를 여기서도 깨지 않는다.
    """
    if settings.problem:
        return ProviderAttempt(False, False, settings.problem, error_code="INVALID_ARGUMENT")
    if not is_trusted_artifact_path(settings.artifact_path, settings.extra_trusted_roots):
        return ProviderAttempt(
            False,
            False,
            f"artifact_path is outside the trusted roots (set {TRUSTED_ROOTS_ENV} to add one): {settings.artifact_path}",
            error_code="UNTRUSTED_ARTIFACT_PATH",
        )
    denial = mcp_server_policy_denial(BUNDLED_TOOL_NAME, BUNDLED_SERVER_NAME)
    if denial is not None:
        # 사용자가 이 요청에서 검색을 껐다 — legacy 로 대체하면 그 결정을 뒤집게 된다.
        return ProviderAttempt(False, False, denial, error_code="POLICY_DENIED")
    try:
        if runtime is None:
            from antigravity_k.tools.ssak_search_runtime import get_ssak_search_runtime

            runtime = get_ssak_search_runtime(_runtime_config(settings))
        call_tool = getattr(runtime, "call_tool")
        outcome = cast("MCPToolOutcome", call_tool(BUNDLED_TOOL_NAME, {"query": query, "max_results": max_results}))
    except Exception as exc:  # noqa: BLE001 — 알 수 없는 예외는 대체하지 않는다(모르면 드러낸다)
        logger.warning("번들 검색 provider 호출이 예외로 끝났습니다: %s", exc, exc_info=True)
        return ProviderAttempt(False, False, f"bundled provider raised: {exc}", error_code="UNKNOWN_ERROR")
    is_error = bool(getattr(outcome, "is_error", False))
    if is_error:
        code = getattr(outcome, "error_code", None)
        code_text = str(code) if code else None
        return ProviderAttempt(
            False,
            classify_error_code(code_text) == "transient",
            str(outcome),
            error_code=code_text or "UNKNOWN_ERROR",
        )
    hits = _hits_from_outcome(outcome)
    if not hits:
        # 응답은 성공인데 쓸 수 있는 결과가 없다 — 그건 검색 결과 0건이지 장애가 아니다.
        return ProviderAttempt(True, False, str(outcome), results=[], engine="SsakBundle(0 hits)")
    return ProviderAttempt(True, False, str(outcome), results=hits)


__all__ = [
    "BUNDLED_SERVER_NAME",
    "BUNDLED_TOOL_NAME",
    "DEFAULT_MANIFEST_NAME",
    "PERMANENT_ERROR_CODES",
    "SUPPORTED_MODES",
    "TRANSIENT_ERROR_CODES",
    "TRUSTED_ROOTS_ENV",
    "ProviderAttempt",
    "SsakSearchSettings",
    "classify_error_code",
    "extra_trusted_roots",
    "is_trusted_artifact_path",
    "resolve_manifest_path",
    "search_with_bundled_provider",
    "settings_snapshot",
    "trusted_roots",
]
