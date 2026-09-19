/**
 * SearchIntegrationPanel — 통합 검색 상태·설정·증거 (task 14)
 * ==========================================================
 * 번들 검색(task 11~13)을 **사용자에게 보이는 표면**으로 만든다. 세 가지를 한 곳에서 한다:
 *
 * 1. **켜고 끄기** — `search.ssak.*` 를 저장하면 서버가 `.env` + 프로세스 env 를 함께 바꿔
 *    재시작 없이 반영된다(설정 화면의 API 키와 다른 점이다).
 * 2. **상태** — 서버가 옮긴 사용자 의미(`label`/`tone`/`detail`)를 그대로 그린다. 화면은
 *    `ready`/`degraded` 같은 **구현 용어를 해석하지 않는다**: 번역이 두 곳에 생기면 갈라진다.
 *    회복 가능하면 "다시 시도"를, 아니면 무엇을 해야 하는지 보여준다.
 * 3. **증거** — 검색 한 건이 남긴 사실(출처 원문 링크·수집시각·부분 수집 경고·상한 초과).
 *    **실패는 실패로 그린다**: 오류 응답은 성공 카드가 아니라 `role="alert"` 블록이며 출처 목록이
 *    비어 있다 — 실패가 "출처 0건의 성공"처럼 보이는 것이 이 화면이 막으려는 모습이다.
 *
 * 비밀 위생: 토큰 입력은 `type="password"` 이고 저장 후 값을 지우며, 서버는 원문 대신
 * `설정됨/미설정`만 돌려준다. artifact 경로도 서버는 **파일명만** 보고하므로 입력란은 저장된 값을
 * 되비추지 않는다(값을 되돌려 받지 않는다는 규칙이 곧 "평문 재노출 금지"의 구현이다).
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { GlassPanel } from "../shared";
import {
    fetchSearchStatus,
    isAuthRequiredError,
    probeSearch,
    retrySearch,
    saveSearchSettings,
    saveSettings,
    type SearchEvidence,
    type SearchStatus,
} from "../../api/client";

/** 원격 검색 백엔드(legacy 대체 경로)의 bearer — 설정 화면이 다루는 유일한 검색 비밀. */
const ENGINE_TOKEN_KEY = "AGK_SEARCH_ENGINE_TOKEN";

const TONE_BADGE_CLASS: Record<string, string> = {
    success: "status-badge success",
    warning: "status-badge pending",
    info: "status-badge active",
    muted: "status-badge muted",
    error: "status-badge",
};

const TONE_COLOR: Record<string, string> = {
    success: "var(--success-color)",
    warning: "var(--warning-color)",
    info: "var(--info-color)",
    muted: "var(--text-muted)",
    error: "var(--error-color)",
};

function errorMessage(error: unknown): string {
    return error instanceof Error ? error.message : String(error);
}

/**
 * 수집 시각을 사람이 읽는 형태로.
 *
 * 정확한 시각(UTC)은 `title` 에 남긴다 — "15분 전"만 있으면 사용자가 원문을 열어 대조할 수 없다.
 */
export function describeRetrievedAt(
    iso: string | null | undefined,
    now: number,
): { relative: string; absolute: string } {
    if (!iso) return { relative: "수집 시각 미기록", absolute: "" };
    const at = Date.parse(iso);
    if (Number.isNaN(at))
        return { relative: "수집 시각 미기록", absolute: iso };
    const seconds = Math.max(0, Math.round((now - at) / 1000));
    const relative =
        seconds < 60
            ? `${seconds}초 전 수집`
            : seconds < 3600
              ? `${Math.floor(seconds / 60)}분 전 수집`
              : `${Math.floor(seconds / 3600)}시간 전 수집`;
    return { relative, absolute: new Date(at).toISOString() };
}

/** 실패한 검색은 성공 카드로 그리지 않는다 — 이 분기가 그 문장이다. */
export const SearchEvidenceCard: React.FC<{
    evidence: SearchEvidence;
    now: number;
}> = ({ evidence, now }) => {
    if (!evidence.ok) {
        return (
            <div
                className="search-evidence-card"
                data-testid="search-evidence-error"
                role="alert"
                style={{
                    border: "1px solid var(--error-color)",
                    borderRadius: 6,
                    padding: "10px 12px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                }}
            >
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span
                        className="status-badge"
                        style={{
                            color: "var(--error-color)",
                            borderColor: "var(--error-color)",
                        }}
                    >
                        검색 실패
                    </span>
                    <span
                        style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: 11,
                            color: "var(--text-muted)",
                        }}
                    >
                        {evidence.error_code || "UNKNOWN_ERROR"} ·{" "}
                        {evidence.failure_class}
                    </span>
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    {evidence.query ? `질의: ${evidence.query}` : "질의 없음"}
                </div>
                {/* 원인은 남기되 출처 블록은 만들지 않는다(실패에 출처가 있으면 성공으로 읽힌다). */}
                {evidence.message && (
                    <div
                        style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: 11,
                            color: "var(--text-muted)",
                            maxHeight: 96,
                            overflow: "auto",
                        }}
                    >
                        {evidence.message}
                    </div>
                )}
            </div>
        );
    }

    const retrieved = describeRetrievedAt(evidence.retrieved_at, now);
    const budget = evidence.budget;

    return (
        <div
            className="search-evidence-card"
            data-testid="search-evidence-card"
            style={{ display: "flex", flexDirection: "column", gap: 8 }}
        >
            <div
                style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    flexWrap: "wrap",
                }}
            >
                <span className="status-badge success">검색 성공</span>
                <span
                    style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--text-muted)",
                    }}
                >
                    {evidence.sources.length}개 출처 · {evidence.route}
                    {evidence.took_ms !== null && evidence.took_ms !== undefined
                        ? ` · ${evidence.took_ms}ms`
                        : ""}
                    {evidence.from_cache ? " · 캐시" : ""}
                </span>
                <span
                    data-testid="search-evidence-retrieved"
                    title={retrieved.absolute}
                    style={{ fontSize: 11, color: "var(--text-muted)" }}
                >
                    {retrieved.relative}
                </span>
            </div>

            {evidence.partial && (
                <div
                    data-testid="search-evidence-partial"
                    role="status"
                    style={{
                        fontSize: 12,
                        color: "var(--warning-color)",
                        border: "1px solid var(--warning-color)",
                        borderRadius: 6,
                        padding: "6px 10px",
                    }}
                >
                    ⚠ 일부 소스만 수집했습니다
                    {evidence.aborted_backends.length > 0
                        ? ` (응답하지 않음: ${evidence.aborted_backends.join(", ")})`
                        : ""}
                    {evidence.signal_confidence
                        ? ` · 신뢰도 ${evidence.signal_confidence}`
                        : ""}
                </div>
            )}

            {budget?.truncated && (
                <div
                    data-testid="search-evidence-budget"
                    role="status"
                    style={{
                        fontSize: 12,
                        color: "var(--info-color)",
                        border: "1px solid var(--info-color)",
                        borderRadius: 6,
                        padding: "6px 10px",
                    }}
                >
                    ⓘ 응답 상한으로 {budget.trimmed_items}건을 잘라냈습니다
                    {budget.exceeded ? ` (초과 축: ${budget.exceeded})` : ""}
                </div>
            )}

            {evidence.sources.length > 0 && (
                <ol
                    data-testid="search-evidence-sources"
                    style={{
                        margin: 0,
                        paddingLeft: 18,
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                    }}
                >
                    {evidence.sources.map((source) => (
                        <li key={`${source.url}:${source.title}`}>
                            <a
                                href={source.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                data-testid="search-evidence-source-link"
                                style={{
                                    color: "var(--accent-color)",
                                    fontSize: 13,
                                }}
                            >
                                {source.title || source.url}
                            </a>
                            <span
                                style={{
                                    marginLeft: 6,
                                    fontFamily: "var(--font-mono)",
                                    fontSize: 10,
                                    color: "var(--text-muted)",
                                }}
                            >
                                {source.provider || "unknown"}
                                {source.score !== null &&
                                source.score !== undefined
                                    ? ` · ${source.score.toFixed(2)}`
                                    : ""}
                                {source.authority_boost ? " · 권위" : ""}
                            </span>
                            {source.security_warning && (
                                <span
                                    style={{
                                        marginLeft: 6,
                                        fontSize: 10,
                                        color: "var(--warning-color)",
                                    }}
                                    title={source.security_warning}
                                >
                                    ⚠ 주의
                                </span>
                            )}
                        </li>
                    ))}
                </ol>
            )}

            {evidence.sources.length === 0 && (
                <div
                    data-testid="search-evidence-empty"
                    style={{ fontSize: 12, color: "var(--text-muted)" }}
                >
                    결과 0건 — 질의를 바꾸거나 출처를 직접 확인하세요.
                </div>
            )}
        </div>
    );
};

export interface SearchIntegrationPanelProps {
    /**
     * 검색 백엔드 토큰이 설정돼 있는가 — **설정 화면이 알려준다**.
     *
     * 이 패널이 `/api/settings` 를 스스로 부르지 않는 이유: 같은 응답을 두 컴포넌트가 각자 부르면
     * (a) 왕복이 두 배가 되고 (b) 페이지가 보는 "설정됨" 상태와 패널이 보는 상태가 서로 다른 시점의
     * 것이 될 수 있다. 진실의 소유자는 `/api/settings` 를 이미 읽는 쪽(설정 화면) 한 곳이다.
     */
    engineTokenConfigured?: boolean;
    /** 토큰을 저장했다 — 페이지가 자기 `configuredKeys` 를 다시 읽게 한다(선택). */
    onEngineTokenSaved?: () => void;
    /** 외부(설정 화면)가 상태를 공유해야 할 때(선택). */
    onStatusChange?: (status: SearchStatus) => void;
}

export const SearchIntegrationPanel: React.FC<SearchIntegrationPanelProps> = ({
    engineTokenConfigured = false,
    onEngineTokenSaved,
    onStatusChange,
}) => {
    const [status, setStatus] = useState<SearchStatus | null>(null);
    const [phase, setPhase] = useState<"loading" | "ready" | "error">(
        "loading",
    );
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [busy, setBusy] = useState<
        "" | "toggle" | "path" | "retry" | "probe" | "token"
    >("");
    const [artifactPath, setArtifactPath] = useState("");
    const [engineToken, setEngineToken] = useState("");
    const [probeQuery, setProbeQuery] = useState("");
    const [now, setNow] = useState(() => Date.now());
    const mountedRef = useRef(true);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);

    const applyStatus = useCallback(
        (next: SearchStatus) => {
            setStatus(next);
            onStatusChange?.(next);
        },
        [onStatusChange],
    );

    /**
     * 상태를 다시 읽는다.
     *
     * 첫 문장이 `await` 인 것이 의도적이다: effect 본문에서 **동기** setState 를 만들면 캐스케이딩
     * 렌더가 생긴다(react-hooks/set-state-in-effect). 상태 갱신은 응답을 받은 뒤에만 일어난다.
     */
    const refresh = useCallback(async () => {
        try {
            const next = await fetchSearchStatus();
            if (!mountedRef.current) return;
            applyStatus(next);
            setError("");
            setPhase("ready");
        } catch (err) {
            if (!mountedRef.current) return;
            setPhase("error");
            setError(
                isAuthRequiredError(err)
                    ? "🔒 PIN 인증이 필요합니다. 잠금을 해제한 뒤 다시 시도하세요."
                    : `검색 상태를 읽지 못했습니다: ${errorMessage(err)}`,
            );
        }
    }, [applyStatus]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    // 상대 시각("15분 전 수집")을 살아 있게 둔다 — 한 번 그린 시각이 굳으면 거짓이 된다.
    useEffect(() => {
        const timer = window.setInterval(() => setNow(Date.now()), 30_000);
        return () => window.clearInterval(timer);
    }, []);

    const run = useCallback(
        async (kind: NonNullable<typeof busy>, action: () => Promise<void>) => {
            if (busy) return;
            setBusy(kind);
            setNotice("");
            // 이전 동작의 오류를 지운다 — 성공한 동작 옆에 낡은 실패가 남으면 화면이 거짓말한다.
            setError("");
            try {
                await action();
            } catch (err) {
                setError(
                    isAuthRequiredError(err)
                        ? "🔒 PIN 인증이 필요합니다. 잠금을 해제한 뒤 다시 시도하세요."
                        : errorMessage(err),
                );
            } finally {
                if (mountedRef.current) setBusy("");
            }
        },
        [busy],
    );

    const toggleEnabled = (enabled: boolean) =>
        run("toggle", async () => {
            const next = await saveSearchSettings({ enabled });
            applyStatus(next);
            setNotice(
                enabled
                    ? "검색을 켰습니다. 첫 검색에서 시작합니다."
                    : "검색을 껐습니다 — 기존 검색 경로가 그대로 돕니다.",
            );
        });

    const savePath = () =>
        run("path", async () => {
            const next = await saveSearchSettings({
                artifact_path: artifactPath.trim(),
            });
            applyStatus(next);
            setArtifactPath("");
            setNotice("번들 경로를 저장했습니다.");
        });

    const clearPath = () =>
        run("path", async () => {
            const next = await saveSearchSettings({ artifact_path: "" });
            applyStatus(next);
            setNotice(
                "번들 경로를 지웠습니다(설정 파일 기본값으로 돌아갑니다).",
            );
        });

    const retry = () =>
        run("retry", async () => {
            const next = await retrySearch();
            applyStatus(next);
            setNotice(
                next.ready
                    ? "다시 연결됐습니다."
                    : "아직 준비되지 않았습니다 — 상태를 확인하세요.",
            );
        });

    const probe = () =>
        run("probe", async () => {
            const query = probeQuery.trim();
            if (!query) return;
            const result = await probeSearch(query);
            // 연결 확인은 상태와 무관하게 **관측 결과**를 남긴다 — 실패도 그대로 보여준다.
            await refresh();
            setNotice(
                result.ok
                    ? "연결 확인 성공."
                    : `연결 확인 실패: ${result.error_code ?? "UNKNOWN_ERROR"}`,
            );
        });

    const saveToken = () =>
        run("token", async () => {
            const value = engineToken.trim();
            if (!value) return;
            await saveSettings({ [ENGINE_TOKEN_KEY]: value });
            // 원문은 즉시 버린다(메모리에도 남기지 않는다) — 화면은 서버의 '설정됨'만 보여준다.
            setEngineToken("");
            onEngineTokenSaved?.();
            setNotice(
                "검색 백엔드 토큰을 저장했습니다(값은 다시 표시하지 않습니다).",
            );
        });

    return (
        <GlassPanel
            title={
                <>
                    <span className="section-index">03B</span> 통합 검색 — 번들
                    provider
                </>
            }
            variant="section"
            className="settings-section"
        >
            <div
                style={{ display: "flex", flexDirection: "column", gap: 14 }}
                data-testid="search-integration-panel"
            >
                <p className="settings-desc" style={{ margin: 0 }}>
                    번들 검색을 켜면 <code>web_search</code> 가 번들 provider 로{" "}
                    <strong>한 번</strong> 갑니다. 상태는 구현 이름이 아니라{" "}
                    <strong>쓸 수 있는지</strong>로 보여줍니다.
                </p>

                {phase === "loading" && (
                    <div
                        data-testid="search-status-loading"
                        className="settings-desc"
                    >
                        검색 상태 확인 중...
                    </div>
                )}

                {error && (
                    <div
                        role="alert"
                        data-testid="search-status-error"
                        style={{
                            color: "var(--error-color)",
                            fontSize: 13,
                            display: "flex",
                            gap: 10,
                            alignItems: "center",
                        }}
                    >
                        <span>{error}</span>
                        {phase === "error" && (
                            <button
                                type="button"
                                className="btn-primary"
                                data-testid="search-status-retry-load"
                                onClick={() => {
                                    setPhase("loading");
                                    void refresh();
                                }}
                            >
                                ↻ 다시 시도
                            </button>
                        )}
                    </div>
                )}

                {phase === "ready" && status && (
                    <>
                        <div
                            className="settings-row"
                            style={{ alignItems: "center" }}
                        >
                            <div className="settings-row-label">
                                <div className="settings-row-title">
                                    <span
                                        className={
                                            TONE_BADGE_CLASS[status.tone] ??
                                            "status-badge"
                                        }
                                        data-testid="search-status-badge"
                                        data-availability={status.availability}
                                        style={{
                                            color:
                                                TONE_COLOR[status.tone] ??
                                                "var(--text-muted)",
                                            borderColor:
                                                TONE_COLOR[status.tone],
                                        }}
                                    >
                                        {status.label}
                                    </span>
                                </div>
                                <div
                                    className="settings-row-hint"
                                    data-testid="search-status-detail"
                                >
                                    {status.detail}
                                </div>
                            </div>
                            <div
                                className="settings-row-status"
                                style={{
                                    display: "flex",
                                    gap: 8,
                                    alignItems: "center",
                                }}
                            >
                                <label
                                    className="toggle-switch"
                                    style={{ margin: 0 }}
                                >
                                    <input
                                        type="checkbox"
                                        data-testid="search-enable-toggle"
                                        aria-label="번들 검색 사용"
                                        checked={status.settings.enabled}
                                        disabled={busy === "toggle"}
                                        onChange={(event) =>
                                            void toggleEnabled(
                                                event.target.checked,
                                            )
                                        }
                                    />
                                    <span className="toggle-track" />
                                    <span className="toggle-label">
                                        {status.settings.enabled
                                            ? "사용"
                                            : "사용 안 함"}
                                    </span>
                                </label>
                                {status.recoverable && (
                                    <button
                                        type="button"
                                        className="btn-primary"
                                        data-testid="search-retry"
                                        disabled={busy === "retry"}
                                        onClick={() => void retry()}
                                    >
                                        ↻ 다시 시도
                                    </button>
                                )}
                            </div>
                        </div>

                        {status.settings.problem && (
                            <div
                                data-testid="search-settings-problem"
                                role="alert"
                                style={{
                                    fontSize: 12,
                                    color: "var(--warning-color)",
                                }}
                            >
                                설정 문제: {status.settings.problem}
                            </div>
                        )}

                        {status.runtime.restart_required && (
                            <div
                                data-testid="search-restart-required"
                                role="status"
                                style={{
                                    fontSize: 12,
                                    color: "var(--warning-color)",
                                }}
                            >
                                ⚠ 설정이 바뀌었지만 실행 중인 검색 프로세스가
                                남아 있습니다 — 호스트를 재시작해야 새 설정이
                                적용됩니다.
                            </div>
                        )}

                        <div className="settings-row">
                            <div className="settings-row-label">
                                <div className="settings-row-title">
                                    📦 번들 실행 파일 경로
                                </div>
                                <div className="settings-row-hint">
                                    신뢰된 루트 안의 경로만 허용합니다. 서버는
                                    저장된 경로를 파일명(
                                    {status.settings.artifact_name
                                        ? ` ${status.settings.artifact_name} `
                                        : " 없음 "}
                                    )으로만 보고하므로, 바꿀 때만 새 경로를
                                    입력하세요.
                                </div>
                            </div>
                            <input
                                type="text"
                                className="text-input settings-row-input"
                                data-testid="search-artifact-path"
                                aria-label="번들 실행 파일 경로"
                                placeholder={
                                    status.settings.artifact_configured
                                        ? "새 경로를 입력하면 교체됩니다"
                                        : "예: /path/to/bin/ssak-mcp"
                                }
                                value={artifactPath}
                                onChange={(event) =>
                                    setArtifactPath(event.target.value)
                                }
                            />
                            <div
                                className="settings-row-status"
                                style={{ display: "flex", gap: 6 }}
                            >
                                <button
                                    type="button"
                                    className="btn-primary"
                                    data-testid="search-artifact-save"
                                    disabled={
                                        busy === "path" ||
                                        artifactPath.trim().length === 0
                                    }
                                    onClick={() => void savePath()}
                                >
                                    저장
                                </button>
                                {status.settings.artifact_configured && (
                                    <button
                                        type="button"
                                        className="btn-ghost"
                                        data-testid="search-artifact-clear"
                                        disabled={busy === "path"}
                                        onClick={() => void clearPath()}
                                    >
                                        지우기
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* ── 연결 확인: 번들로 실제 검색 1회(legacy 대체 없음) ── */}
                        <div className="settings-row">
                            <div className="settings-row-label">
                                <div className="settings-row-title">
                                    🔌 연결 확인
                                </div>
                                <div className="settings-row-hint">
                                    번들 provider 로 실제 검색을 한 번 돌려
                                    봅니다. 실패해도 기존 검색 경로로 대체하지
                                    않습니다 — 여기서 답하려는 질문은 “번들이
                                    되느냐”이기 때문입니다.
                                </div>
                            </div>
                            <input
                                type="text"
                                className="text-input settings-row-input"
                                data-testid="search-probe-query"
                                aria-label="연결 확인 질의"
                                placeholder="확인용 검색어"
                                value={probeQuery}
                                onChange={(event) =>
                                    setProbeQuery(event.target.value)
                                }
                            />
                            <div className="settings-row-status">
                                <button
                                    type="button"
                                    className="btn-primary"
                                    data-testid="search-probe"
                                    disabled={
                                        busy === "probe" ||
                                        probeQuery.trim().length === 0
                                    }
                                    onClick={() => void probe()}
                                >
                                    {busy === "probe"
                                        ? "확인 중..."
                                        : "연결 확인"}
                                </button>
                            </div>
                        </div>

                        {/* ── 원격 검색 백엔드 토큰(비밀) ── */}
                        <div className="settings-row">
                            <div className="settings-row-label">
                                <div
                                    className="settings-row-title"
                                    id="search-token-label"
                                >
                                    🔑 원격 검색 백엔드 토큰
                                </div>
                                <div className="settings-row-hint">
                                    legacy 대체 경로가 쓰는 bearer 입니다. 입력
                                    중에만 메모리에 있고, 서버는 값 대신 설정
                                    여부만 돌려줍니다.
                                </div>
                            </div>
                            <input
                                type="password"
                                autoComplete="off"
                                className="text-input settings-row-input"
                                data-testid="search-engine-token"
                                aria-labelledby="search-token-label"
                                placeholder={
                                    engineTokenConfigured
                                        ? "•••••••• (새 값을 입력하면 교체됩니다)"
                                        : "토큰 입력"
                                }
                                value={engineToken}
                                onChange={(event) =>
                                    setEngineToken(event.target.value)
                                }
                            />
                            <div
                                className="settings-row-status"
                                style={{
                                    display: "flex",
                                    gap: 6,
                                    alignItems: "center",
                                }}
                            >
                                {engineTokenConfigured ? (
                                    <span
                                        className="status-badge success"
                                        data-testid="search-token-state"
                                    >
                                        ✓ 설정됨
                                    </span>
                                ) : (
                                    <span
                                        className="status-badge muted"
                                        data-testid="search-token-state"
                                    >
                                        ⚪ 미설정
                                    </span>
                                )}
                                <button
                                    type="button"
                                    className="btn-primary"
                                    data-testid="search-token-save"
                                    disabled={
                                        busy === "token" ||
                                        engineToken.trim().length === 0
                                    }
                                    onClick={() => void saveToken()}
                                >
                                    저장
                                </button>
                            </div>
                        </div>

                        {/* ── 증거: 최근 검색들이 남긴 사실 ── */}
                        <div
                            style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: 8,
                            }}
                            data-testid="search-evidence"
                        >
                            <div className="settings-row-label">
                                <div className="settings-row-title">
                                    🧾 최근 검색 증거
                                </div>
                                <div className="settings-row-hint">
                                    출처 원문 링크·수집시각·부분 수집·상한
                                    초과를 그대로 보여줍니다. 실패는 실패로
                                    표시됩니다.
                                </div>
                            </div>
                            {(status.evidence ?? []).length === 0 && (
                                <div
                                    data-testid="search-evidence-none"
                                    className="settings-desc"
                                    style={{ margin: 0 }}
                                >
                                    아직 검색 기록이 없습니다 — “연결 확인”으로
                                    한 번 돌려 보세요.
                                </div>
                            )}
                            {(status.evidence ?? []).map((item) => (
                                <SearchEvidenceCard
                                    key={`${item.query}:${item.retrieved_at}:${item.route}`}
                                    evidence={item}
                                    now={now}
                                />
                            ))}
                        </div>
                    </>
                )}

                {notice && (
                    <div
                        data-testid="search-notice"
                        role="status"
                        style={{ fontSize: 12, color: "var(--text-secondary)" }}
                    >
                        {notice}
                    </div>
                )}
            </div>
        </GlassPanel>
    );
};

export default SearchIntegrationPanel;
