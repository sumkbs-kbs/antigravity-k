/**
 * searchFailure 판정 계약 (task 14)
 * =================================
 * 이 판정은 **좁아야** 한다. 산문 중간의 "error" 를 실패로 만들면 정상 답변이 실패로 보이고, 그러면
 * 사용자는 맞는 답을 못 믿게 된다 — 거짓 양성이 거짓 음성보다 나쁘다. 그래서 여기서는
 * "실패로 보는 두 경우"와 "실패로 보지 **않는** 경우들"을 함께 고정한다.
 */

import { describe, expect, it } from "vitest";

import { searchFailureNotice } from "../searchFailure";

describe("실패로 보는 경우", () => {
    it("Search Error: 접두어를 잡는다", () => {
        const notice = searchFailureNotice(
            "Search Error: 결과를 가져오지 못했습니다",
        );
        expect(notice).not.toBeNull();
        expect(notice?.code).toBe("SEARCH_FAILED");
        expect(notice?.detail).toBe("결과를 가져오지 못했습니다");
    });

    it("한국어 접두어도 잡는다", () => {
        expect(
            searchFailureNotice("검색 오류: 백엔드가 응답하지 않습니다")
                ?.detail,
        ).toBe("백엔드가 응답하지 않습니다");
    });

    it("본문 전체가 오류 봉투면 코드와 원인을 꺼낸다", () => {
        const notice = searchFailureNotice(
            '{"error":{"code":"AUTH_REQUIRED","detail":"자격 증명이 필요합니다"}}',
        );
        expect(notice?.code).toBe("AUTH_REQUIRED");
        expect(notice?.detail).toBe("자격 증명이 필요합니다");
    });

    it("detail 이 없으면 코드를 원인으로 쓴다", () => {
        expect(
            searchFailureNotice('{"error":{"code":"TIMEOUT"}}')?.detail,
        ).toBe("TIMEOUT");
    });
});

describe("실패로 보지 않는 경우", () => {
    it("빈 본문", () => {
        expect(searchFailureNotice("")).toBeNull();
        expect(searchFailureNotice("   ")).toBeNull();
        expect(searchFailureNotice(null)).toBeNull();
        expect(searchFailureNotice(undefined)).toBeNull();
    });

    it("error 라는 단어가 들어간 정상 산문", () => {
        expect(
            searchFailureNotice(
                "이 오류는 네트워크 error 로 인한 것이 아닙니다.",
            ),
        ).toBeNull();
    });

    it("접두어 뒤에 설명이 아니라 산문이 이어지는 경우 — 앞에 문장이 있으면 실패가 아니다", () => {
        expect(
            searchFailureNotice("앞선 검색 결과: Search Error: 관련 없음"),
        ).toBeNull();
    });

    it("봉투에 다른 키가 함께 있으면 데이터로 본다", () => {
        expect(
            searchFailureNotice('{"error":{"code":"X"},"hits":[]}'),
        ).toBeNull();
    });

    it("error.code 가 비어 있으면 봉투로 보지 않는다", () => {
        expect(searchFailureNotice('{"error":{"code":""}}')).toBeNull();
    });

    it("JSON 이지만 오류 봉투가 아니면 null", () => {
        expect(searchFailureNotice('{"hits":[{"title":"a"}]}')).toBeNull();
        expect(searchFailureNotice('{"error":"plain string"}')).toBeNull();
        expect(searchFailureNotice("{ not json }")).toBeNull();
    });

    it("배열이나 스칼라는 대상이 아니다", () => {
        expect(searchFailureNotice('[{"error":{"code":"X"}}]')).toBeNull();
        expect(searchFailureNotice("42")).toBeNull();
    });
});
