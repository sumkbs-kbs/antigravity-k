/**
 * SearchIntegrationPanel 계약 (task 14)
 * ======================================
 * 이 화면이 지키는 문장들:
 *
 *  - **상태는 서버가 옮긴 의미를 그대로** 보여준다(화면이 `ready`/`degraded` 를 해석하지 않는다).
 *  - 켜고/끄면 서버에 **그 필드만** 보낸다(부분 갱신).
 *  - **실패는 성공 카드가 아니다**: 오류 증거는 `role="alert"` 이고 출처 목록이 없다.
 *  - **부분 수집·상한 초과는 그 사실을 말한다**(추측이 아니라 서버가 준 값으로).
 *  - 출처는 **원문 링크**이며 수집시각이 함께 보인다.
 *  - artifact 입력은 **저장된 경로를 되비추지 않는다**(서버는 파일명만 준다).
 *  - 토큰은 `type="password"` 이고 저장 뒤 **값을 버린다**.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { SearchEvidence, SearchStatus } from "../../../api/client";
import { searchStatus as statusFixture } from "../../../tests/searchStatusFixture";

const apiMocks = vi.hoisted(() => ({
    fetchSearchStatus: vi.fn(),
    saveSearchSettings: vi.fn(),
    retrySearch: vi.fn(),
    probeSearch: vi.fn(),
    saveSettings: vi.fn(),
    isAuthRequiredError: vi.fn(() => false),
}));

vi.mock("../../../api/client", () => apiMocks);

import SearchIntegrationPanel from "../SearchIntegrationPanel";

function evidence(overrides: Partial<SearchEvidence> = {}): SearchEvidence {
    return {
        query: "질의",
        ok: true,
        route: "bundled",
        error_code: null,
        failure_class: "ok",
        message: "",
        engine: "SsakBundle",
        sources: [],
        retrieved_at: new Date().toISOString(),
        took_ms: 512,
        from_cache: false,
        cache_age_ms: null,
        aborted_backends: [],
        signal_confidence: "HIGH",
        decomposed_subqueries: [],
        phishing_filtered: null,
        partial: false,
        budget: null,
        artifact_name: "ssak-mcp",
        ...overrides,
    };
}

function renderPanel(
    status: SearchStatus,
    props: React.ComponentProps<typeof SearchIntegrationPanel> = {},
) {
    apiMocks.fetchSearchStatus.mockResolvedValue(status);
    return render(<SearchIntegrationPanel {...props} />);
}

beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.isAuthRequiredError.mockReturnValue(false);
    apiMocks.saveSettings.mockResolvedValue({
        ok: true,
        updated: 1,
        message: "saved",
    });
    apiMocks.saveSearchSettings.mockResolvedValue(
        statusFixture({ availability: "idle", label: "시작 전" }),
    );
    apiMocks.retrySearch.mockResolvedValue(
        statusFixture({ availability: "available", label: "사용 가능" }),
    );
    apiMocks.probeSearch.mockResolvedValue({
        ok: true,
        query: "질의",
        evidence: evidence(),
    });
});

describe("상태 표시", () => {
    it("서버가 옮긴 라벨을 그대로 그리고, 구현 상태 이름을 화면에 노출하지 않는다", async () => {
        renderPanel(
            statusFixture({
                availability: "unavailable",
                label: "연결 실패 · 재시도 가능",
                tone: "error",
                detail: "다시 시도하면 회로를 닫고 재시작합니다.",
                recoverable: true,
                settings: { ...statusFixture().settings, enabled: true },
                runtime: {
                    ...statusFixture().runtime,
                    present: true,
                    state: "failed",
                    circuit_open: true,
                },
            }),
        );

        const badge = await screen.findByTestId("search-status-badge");
        expect(badge).toHaveTextContent("연결 실패 · 재시도 가능");
        expect(badge).toHaveAttribute("data-availability", "unavailable");
        expect(screen.getByTestId("search-status-detail")).toHaveTextContent(
            "다시 시도하면",
        );
        // 내부 상태 이름은 화면 문구가 아니다.
        expect(
            screen.queryByText(/degraded|circuit_open/),
        ).not.toBeInTheDocument();
    });

    it("회복 가능하면 다시 시도를 주고, 아니면 주지 않는다", async () => {
        const { unmount } = renderPanel(
            statusFixture({ recoverable: false, availability: "disabled" }),
        );
        await screen.findByTestId("search-status-badge");
        expect(screen.queryByTestId("search-retry")).not.toBeInTheDocument();
        unmount();

        renderPanel(
            statusFixture({
                recoverable: true,
                availability: "unavailable",
                tone: "error",
            }),
        );
        await screen.findByTestId("search-status-badge");
        expect(await screen.findByTestId("search-retry")).toBeInTheDocument();
    });

    it("설정이 바뀌었는데 프로세스가 남아 있으면 재시작이 필요하다고 말한다", async () => {
        renderPanel(
            statusFixture({
                settings: {
                    ...statusFixture().settings,
                    enabled: true,
                    artifact_configured: true,
                },
                runtime: {
                    ...statusFixture().runtime,
                    present: true,
                    child_count: 1,
                    restart_required: true,
                },
            }),
        );

        expect(
            await screen.findByTestId("search-restart-required"),
        ).toBeInTheDocument();
    });
});

describe("켜기/끄기", () => {
    it("토글은 enabled 필드만 보낸다(다른 설정을 덮지 않는다)", async () => {
        apiMocks.fetchSearchStatus.mockResolvedValue(statusFixture());
        render(<SearchIntegrationPanel />);
        const toggle = await screen.findByTestId("search-enable-toggle");
        expect(toggle).not.toBeChecked();

        fireEvent.click(toggle);

        await waitFor(() =>
            expect(apiMocks.saveSearchSettings).toHaveBeenCalledWith({
                enabled: true,
            }),
        );
    });

    it("저장이 거절되면 그 이유를 보여준다", async () => {
        apiMocks.fetchSearchStatus.mockResolvedValue(statusFixture());
        apiMocks.saveSearchSettings.mockRejectedValue(
            new Error("HTTP 400: 켜려면 번들 경로가 필요합니다"),
        );
        render(<SearchIntegrationPanel />);
        const toggle = await screen.findByTestId("search-enable-toggle");

        fireEvent.click(toggle);

        const alert = await screen.findByTestId("search-status-error");
        expect(alert).toHaveTextContent("번들 경로");
    });
});

describe("설정 입력", () => {
    it("artifact 입력은 저장된 경로를 되비추지 않고 파일명만 안내한다", async () => {
        renderPanel(
            statusFixture({
                settings: {
                    ...statusFixture().settings,
                    enabled: true,
                    artifact_configured: true,
                    artifact_name: "ssak-mcp",
                },
            }),
        );

        const input = await screen.findByTestId("search-artifact-path");
        expect(input).toHaveValue("");
        expect(screen.getByText(/ssak-mcp/)).toBeInTheDocument();
        // 저장된 값이 없으므로 저장은 비활성이어야 한다(빈 경로를 보내지 않는다).
        expect(screen.getByTestId("search-artifact-save")).toBeDisabled();
    });

    it("토큰 입력은 password 이고 저장 뒤 값을 버린다", async () => {
        const onEngineTokenSaved = vi.fn();
        renderPanel(statusFixture(), { onEngineTokenSaved });
        const input = (await screen.findByTestId(
            "search-engine-token",
        )) as HTMLInputElement;
        expect(input.type).toBe("password");
        expect(input).toHaveAttribute("autocomplete", "off");

        fireEvent.change(input, { target: { value: "secret-token-value" } });
        expect(input).toHaveValue("secret-token-value");
        fireEvent.click(screen.getByTestId("search-token-save"));

        await waitFor(() =>
            expect(apiMocks.saveSettings).toHaveBeenCalledWith({
                AGK_SEARCH_ENGINE_TOKEN: "secret-token-value",
            }),
        );
        await waitFor(() =>
            expect(screen.getByTestId("search-engine-token")).toHaveValue(""),
        );
        // 페이지가 자기 configuredKeys 를 다시 읽도록 알린다(패널이 스스로 /api/settings 를 부르지 않는다).
        await waitFor(() => expect(onEngineTokenSaved).toHaveBeenCalled());
    });

    it("토큰 상태는 페이지가 알려준 설정 여부만 보여준다", async () => {
        const first = renderPanel(statusFixture(), {
            engineTokenConfigured: true,
        });
        expect(
            await screen.findByTestId("search-token-state"),
        ).toHaveTextContent("설정됨");
        first.unmount();

        renderPanel(statusFixture(), { engineTokenConfigured: false });
        expect(
            await screen.findByTestId("search-token-state"),
        ).toHaveTextContent("미설정");
    });
});

describe("증거 렌더링", () => {
    it("출처는 원문 링크와 수집시각을 함께 보여준다", async () => {
        renderPanel(
            statusFixture({
                availability: "available",
                label: "사용 가능",
                evidence: [
                    evidence({
                        sources: [
                            {
                                title: "공식 문서",
                                url: "https://example.test/official",
                                snippet: "공식 본문",
                                score: 0.93,
                                provider: "searxng",
                                authority_boost: true,
                                security_warning: null,
                            },
                        ],
                        took_ms: 649,
                    }),
                ],
            }),
        );

        const link = await screen.findByTestId("search-evidence-source-link");
        expect(link).toHaveAttribute("href", "https://example.test/official");
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute(
            "rel",
            expect.stringContaining("noopener"),
        );
        expect(
            screen.getByTestId("search-evidence-retrieved"),
        ).toHaveTextContent(/초 전 수집|분 전 수집/);
        expect(screen.getByTestId("search-evidence-card")).toHaveTextContent(
            "649ms",
        );
    });

    it("실패한 검색은 오류 블록이며 출처 목록이 없다", async () => {
        renderPanel(
            statusFixture({
                evidence: [
                    evidence({
                        ok: false,
                        route: "bundled (error)",
                        error_code: "AUTH_REQUIRED",
                        failure_class: "permanent",
                        message: '{"error":{"code":"AUTH_REQUIRED"}}',
                    }),
                    evidence({ sources: [] }),
                ],
            }),
        );

        const alert = await screen.findByTestId("search-evidence-error");
        expect(alert).toHaveAttribute("role", "alert");
        expect(alert).toHaveTextContent("AUTH_REQUIRED");
        // 오류 카드는 출처 목록을 만들지 않는다 — 출처 목록은 성공 카드에만 달린다.
        expect(screen.queryAllByTestId("search-evidence-sources")).toHaveLength(
            0,
        );
        // 성공 카드(출처 0건)는 별도로 그려지며 "결과 0건"이라고 말한다.
        expect(screen.getAllByTestId("search-evidence-card")).toHaveLength(1);
        expect(screen.getByTestId("search-evidence-empty")).toBeInTheDocument();
    });

    it("부분 수집은 경고와 응답하지 않은 백엔드를 보여준다", async () => {
        renderPanel(
            statusFixture({
                evidence: [
                    evidence({
                        partial: true,
                        aborted_backends: ["bing", "naver"],
                        signal_confidence: "MEDIUM",
                        sources: [
                            {
                                title: "A",
                                url: "https://example.test/a",
                                snippet: "",
                                score: 0.8,
                                provider: "bing",
                                authority_boost: false,
                                security_warning: null,
                            },
                        ],
                    }),
                ],
            }),
        );

        const warning = await screen.findByTestId("search-evidence-partial");
        expect(warning).toHaveTextContent("일부 소스만 수집했습니다");
        expect(warning).toHaveTextContent("bing, naver");
        expect(warning).toHaveTextContent("MEDIUM");
    });

    it("상한 초과는 잘라낸 사실과 초과 축을 보여준다", async () => {
        renderPanel(
            statusFixture({
                evidence: [
                    evidence({
                        budget: {
                            bytes: 262144,
                            tokens: 9000,
                            exceeded: "tokens",
                            trimmed_items: 3,
                            truncated: true,
                        },
                    }),
                ],
            }),
        );

        const chip = await screen.findByTestId("search-evidence-budget");
        expect(chip).toHaveTextContent("3건");
        expect(chip).toHaveTextContent("tokens");
    });

    it("증거가 없으면 없다고 말한다(빈 카드 금지)", async () => {
        renderPanel(statusFixture({ evidence: [] }));

        expect(
            await screen.findByTestId("search-evidence-none"),
        ).toBeInTheDocument();
    });
});

describe("연결 확인", () => {
    it("질의를 보내고 결과를 상태에 반영한다", async () => {
        renderPanel(statusFixture());
        fireEvent.change(await screen.findByTestId("search-probe-query"), {
            target: { value: "연결 확인" },
        });
        fireEvent.click(screen.getByTestId("search-probe"));

        await waitFor(() =>
            expect(apiMocks.probeSearch).toHaveBeenCalledWith("연결 확인"),
        );
        // 연결 확인 뒤에는 서버 상태를 다시 읽는다(결과를 화면이 추측하지 않는다).
        await waitFor(() =>
            expect(apiMocks.fetchSearchStatus).toHaveBeenCalledTimes(2),
        );
    });

    it("연결 확인이 실패해도 그 실패를 사용자에게 그대로 말한다", async () => {
        apiMocks.probeSearch.mockResolvedValue({
            ok: false,
            query: "연결 확인",
            evidence: null,
            error_code: "CHILD_EXITED",
        });
        renderPanel(statusFixture());
        fireEvent.change(await screen.findByTestId("search-probe-query"), {
            target: { value: "연결 확인" },
        });
        fireEvent.click(screen.getByTestId("search-probe"));

        await waitFor(() =>
            expect(screen.getByTestId("search-notice")).toHaveTextContent(
                "CHILD_EXITED",
            ),
        );
    });
});
