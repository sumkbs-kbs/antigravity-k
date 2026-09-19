/**
 * 검색 상태 wire fixture (task 14)
 * ===============================
 * 설정 화면을 검증하는 기존 테스트들은 **통합 검색 패널 자체를 검증하지 않는다** — 그 패널은 자기
 * 테스트를 갖는다(`src/components/Search/__tests__`). 그래서 그 테스트들에는 "서버가 꺼진 상태를
 * 보고했다"는 고정 응답만 주면 충분하다(패널이 미해석 상태로 실패하지 않게).
 *
 * 값을 여기 한 곳에 두는 이유: 네 개의 기존 SettingsPage 테스트가 각자 다른 모양의 가짜 응답을
 * 들고 있으면, 서버 계약이 한 번 바뀔 때 넷이 서로 다르게 낡는다.
 */

import type { SearchStatus } from "../api/client";

export const SEARCH_STATUS_DISABLED: SearchStatus = {
    ok: true,
    availability: "disabled",
    label: "검색 꺼짐",
    tone: "muted",
    detail: "켜면 번들 검색이 대신 답합니다.",
    recoverable: false,
    settings: {
        enabled: false,
        mode: "bundled_stdio",
        mode_supported: true,
        fallback: "legacy_on_transient",
        artifact_configured: false,
        artifact_name: null,
        artifact_trusted: false,
        problem: null,
    },
    runtime: {
        present: false,
        state: null,
        circuit_open: false,
        last_error: null,
        child_count: 0,
        start_attempts: 0,
        spawn_attempts: 0,
        restart_required: false,
    },
    evidence: [],
};

export function searchStatus(
    overrides: Partial<SearchStatus> = {},
): SearchStatus {
    return {
        ...SEARCH_STATUS_DISABLED,
        ...overrides,
        settings: {
            ...SEARCH_STATUS_DISABLED.settings,
            ...(overrides.settings ?? {}),
        },
        runtime: {
            ...SEARCH_STATUS_DISABLED.runtime,
            ...(overrides.runtime ?? {}),
        },
        evidence: overrides.evidence ?? SEARCH_STATUS_DISABLED.evidence,
    };
}
