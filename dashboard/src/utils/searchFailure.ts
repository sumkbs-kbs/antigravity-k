/**
 * searchFailure — 도구 실패 봉투를 **답변처럼 보이지 않게** 분류한다 (task 14).
 *
 * 왜 필요한가: 도구 실행 결과는 `system` 역할 메시지로 대화에 실려 개행되는데, 화면은 `user` 가 아닌
 * 메시지를 전부 마크다운 산문으로 그린다. 그래서 `Search Error: …` 나 `{"error":{"code":"AUTH_REQUIRED"}}`
 * 같은 실패 봉투가 **정상 답변과 똑같은 말풍선**으로 렌더된다 — 사용자는 검색이 실패한 것을 모른 채
 * 본문을 읽는다. 이 모듈은 그 경우를 식별해 화면이 실패 블록으로 그리게 한다.
 *
 * 판정은 **좁게** 한다. 산문 중간에 "error" 라는 단어가 있다고 실패로 만들면 정상 답변이 실패로 보인다
 * — 거짓 양성이 거짓 음성보다 나쁘다(사용자가 맞는 답변을 못 믿게 된다). 그래서:
 *
 *   1. `Search Error: <detail>` / `Search 실패: <detail>` 로 **시작**하는 경우
 *   2. 전체가 하나의 JSON 객체이고 그 `error.code` 가 비어 있지 않은 문자열인 경우
 *
 * 만 그렇다. 앞에 다른 문장이 붙어 있으면(설명 + 봉투) 실패로 보지 않는다.
 */

export interface SearchFailureNotice {
    /** 서버/도구가 밝힌 코드(모르면 `UNKNOWN_ERROR`). */
    code: string;
    /** 사람이 읽을 원인. */
    detail: string;
    /** 원문(접힌 상태로 보여줄 수 있게). */
    raw: string;
}

const ERROR_PREFIXES = ["Search Error:", "Search 실패:", "검색 오류:"] as const;

function asRecord(value: unknown): Record<string, unknown> | null {
    return typeof value === "object" && value !== null && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : null;
}

function text(value: unknown): string {
    return typeof value === "string" ? value.trim() : "";
}

/** 전체 본문이 단일 오류 봉투인가 — `{ "error": { "code": … } }` 형태만. */
function errorEnvelope(content: string): SearchFailureNotice | null {
    const trimmed = content.trim();
    if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;
    let parsed: unknown;
    try {
        parsed = JSON.parse(trimmed);
    } catch {
        return null;
    }
    const body = asRecord(parsed);
    if (!body) return null;
    // 다른 키가 함께 있으면 봉투가 아니라 데이터일 수 있다 — 그때는 건드리지 않는다.
    if (Object.keys(body).length > 1) return null;
    const error = asRecord(body.error);
    if (!error) return null;
    const code = text(error.code) || text(error.error_code);
    if (!code) return null;
    return {
        code,
        detail: text(error.detail) || text(error.message) || code,
        raw: trimmed,
    };
}

/**
 * 실패 봉투면 안내를, 아니면 `null` 을 돌려준다.
 *
 * `null` 은 "이 메시지는 실패가 아니다"라는 뜻이며, 화면은 기존 마크다운 경로를 그대로 쓴다.
 */
export function searchFailureNotice(
    content: string | null | undefined,
): SearchFailureNotice | null {
    const value = typeof content === "string" ? content : "";
    if (!value.trim()) return null;

    const trimmed = value.trim();
    for (const prefix of ERROR_PREFIXES) {
        if (!trimmed.startsWith(prefix)) continue;
        const detail = trimmed.slice(prefix.length).trim();
        return {
            code: "SEARCH_FAILED",
            detail: detail || "검색 도구가 실패했습니다.",
            raw: trimmed,
        };
    }

    return errorEnvelope(trimmed);
}
