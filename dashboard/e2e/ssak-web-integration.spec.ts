/**
 * 통합 검색 UI witness — 실 브라우저 · 실 host · (가능하면) **실 번들 binary** (task 14)
 * ==============================================================================
 * 이 파일이 재는 것
 * ---------------
 *   S1 정상: 실 host + **실 `bin/ssak-mcp`** 검색 → 출처 원문 링크·수집시각·성공 배지
 *   S2 실패: 번들 프로세스가 없을 때 → 상태가 "연결 실패 · 재시도 가능"이고, 증거가 **오류 블록**이며
 *         출처 목록이 없다(실패가 "출처 0건의 성공"처럼 보이지 않는다)
 *   S3 부분 수집: 응답하지 않은 백엔드가 있으면 경고와 그 이름이 보인다
 *   S4 상한 초과: 잘라낸 항목 수와 초과 축이 보인다
 *   S5 키보드만으로: 토글(Space) → 연결 확인(Enter) 까지 도달한다
 *   S6 좁은 viewport: 420px 에서도 잘리지 않고 가로 스크롤을 만들지 않는다
 *
 * 무엇으로 재는가
 * --------------
 * - **실 hermetic 서버**(`startBackendServer`): 실제 uvicorn + 실제 `/api/search/*`. 개발자의 `.env`
 *   는 `AGK_ENV_FILE` 격리로 건드리지 않는다 — 설정 저장이 실제로 파일에 쓰이는지도 볼 수 있다.
 * - **실 child 프로세스**: S1 은 W 의 64MB 번들 바이너리, S3/S4 는 저장소의 fixture child 를 실행하는
 *   shim. 둘 다 "SDK stdio 가 소유하는 자식 프로세스"라는 계약은 같다(다른 것은 실행 파일뿐이다).
 *   그래서 S1 이 필요로 하는 **실제 번들 경로는 opt-in** 이다(`AGK_E2E_SSAK_BUNDLE`) — 그 변수가 없으면
 *   S1 은 skip 하고, 왜 건너뛰었는지 말한다(통과로 위장하지 않는다).
 * - **화면이 실제로 보낸 것**: `/api/search/probe` 는 번들 provider 를 **한 번** 부르고, legacy 로
 *   대체하지 않는다. 그래서 여기서 출처가 보이면 그 출처는 번들 결과다.
 *
 * 표시: S3/S4 는 **fixture child** 의 응답이다 — 실제 검색 품질의 증거가 아니라, 화면이 부분 수집과
 * 상한 초과를 **표시하는지**의 증거다. 그 구분을 result.md 에도 적는다.
 */

import { mkdir, mkdtemp, writeFile, chmod } from "node:fs/promises";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import path from "node:path";

import { expect, test, type Page, type TestInfo } from "@playwright/test";

import {
    startBackendServer,
    type HermeticServer,
} from "./helpers/hermeticBackend";

process.env.AGK_SEC_DEV_NO_PIN_ALLOW = "1";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const EVIDENCE_FIXTURE = path.join(
    REPO_ROOT,
    "tests",
    "fixtures",
    "ssak_search_evidence_child.py",
);
const ARTIFACT_DIR =
    process.env.SSAK14_ARTIFACT_DIR ??
    path.join(
        REPO_ROOT,
        ".omo",
        "evidence",
        "ssak-ai-web-integration",
        "2026-09-18T1112Z",
        "task-14",
        "artifacts",
    );
const REAL_BUNDLE = process.env.AGK_E2E_SSAK_BUNDLE ?? "";

interface SearchServer extends HermeticServer {
    bundleDirectory: string;
}

/**
 * 저장소의 fixture child 를 실행하는 번들 shim(+매니페스트)을 만든다.
 *
 * 매니페스트는 필수다: 런타임은 "어느 bytes 를 실행하는지" 모르면 child 를 만들지 않는다(fail-closed).
 * shim 은 `bin/ssak-mcp`, 매니페스트는 `release/` — task 11 이 정한 배치 규약 그대로다.
 */
async function writeFixtureBundle(
    scenario: string,
): Promise<{ root: string; binary: string }> {
    const root = await mkdtemp(path.join(tmpdir(), "ssak14-bundle-"));
    const binary = path.join(root, "bin", "ssak-mcp");
    await mkdir(path.dirname(binary), { recursive: true });
    await writeFile(
        binary,
        "#!/bin/sh\n" +
            `export SSAK_EVIDENCE_SCENARIO="${scenario}"\n` +
            `exec python3 -I -S "${EVIDENCE_FIXTURE}"\n`,
        { mode: 0o755 },
    );
    await chmod(binary, 0o755);
    await mkdir(path.join(root, "release"), { recursive: true });
    const sha256 = createHash("sha256")
        .update(await (await import("node:fs/promises")).readFile(binary))
        .digest("hex");
    await writeFile(
        path.join(root, "release", "ssak-search-manifest.json"),
        JSON.stringify({
            artifact: { sha256, platform: "darwin", arch: "arm64" },
        }),
        "utf8",
    );
    return { root, binary };
}

/** 번들 설정을 **환경변수로** 넘긴 서버(설정 화면의 저장 경로와 같은 키를 쓴다). */
async function startSearchServer(options: {
    binary?: string;
    trustedRoot?: string;
    enabled?: boolean;
}): Promise<SearchServer> {
    const overrides: Record<string, string> = {};
    if (options.enabled !== false && options.binary) {
        overrides.AGK_SEARCH_SSAK_ENABLED = "true";
        overrides.AGK_SEARCH_SSAK_ARTIFACT_PATH = options.binary;
    }
    if (options.trustedRoot)
        overrides.AGK_SEARCH_TRUSTED_ROOTS = options.trustedRoot;
    const server = await startBackendServer(overrides);
    return Object.assign(server, {
        bundleDirectory: options.trustedRoot ?? "",
    });
}

async function gotoSearchPanel(page: Page): Promise<void> {
    await page.goto("/settings");
    await page.waitForLoadState("domcontentloaded");
    await expect(
        page.getByRole("heading", { name: "시스템 설정" }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("search-integration-panel")).toBeVisible({
        timeout: 20_000,
    });
    await expect(page.getByTestId("search-status-badge")).toBeVisible({
        timeout: 20_000,
    });
}

/** 연결 확인을 눌러 **실제 검색 한 번**을 돌린다(번들 provider 로만 — legacy 대체 없음). */
async function runProbe(page: Page, query: string): Promise<void> {
    await page.getByTestId("search-probe-query").fill(query);
    await page.getByTestId("search-probe").click();
}

async function capture(
    page: Page,
    testInfo: TestInfo,
    name: string,
): Promise<void> {
    await mkdir(ARTIFACT_DIR, { recursive: true });
    await page.screenshot({
        path: path.join(ARTIFACT_DIR, `${name}.png`),
        fullPage: true,
    });
    // 콘솔 증거도 파일로 남긴다. 단언문은 "비어 있다"까지만 말하고, 그 사실이 나중에 **읽을 수
    // 있는 형태**로 남지 않으면 다른 에이전트는 화면만 보고 콘솔을 추정해야 한다.
    const observed = consoleEvidence.get(page) ?? [];
    await writeFile(
        path.join(ARTIFACT_DIR, `${name}.console.txt`),
        [
            `test: ${testInfo.title}`,
            `url: ${page.url()}`,
            `console_errors: ${observed.length}`,
            ...observed,
        ].join("\n") + "\n",
        "utf-8",
    );
    if (!testInfo.outputDir.includes(ARTIFACT_DIR)) {
        await page.screenshot({
            path: path.join(testInfo.outputDir, `${name}.png`),
            fullPage: true,
        });
    }
}

//: 페이지별로 모은 콘솔 오류 — `capture()` 가 같은 목록을 증거로 쓸 수 있게 둔다.
const consoleEvidence = new WeakMap<Page, string[]>();

function collectProblems(page: Page): string[] {
    const problems: string[] = [];
    page.on("console", (message) => {
        if (message.type() === "error")
            problems.push(`[console] ${message.text()}`);
    });
    page.on("pageerror", (error) =>
        problems.push(`[pageerror] ${error.message}`),
    );
    consoleEvidence.set(page, problems);
    return problems;
}

test.describe("통합 검색 UI", () => {
    test("S1 실 번들 바이너리 검색 — 출처 링크와 수집시각이 화면에 있다", async ({
        browser,
    }, testInfo) => {
        test.skip(
            !REAL_BUNDLE,
            "AGK_E2E_SSAK_BUNDLE 미설정 — 실 번들 검색은 opt-in 이다(건너뜀을 통과로 위장하지 않는다)",
        );
        test.setTimeout(180_000);
        const server = await startSearchServer({
            binary: REAL_BUNDLE,
            // task 11 배치: <W>/bin/ssak-mcp + <W>/release/ssak-search-manifest.json → 신뢰 루트는 <W>.
            trustedRoot: path.dirname(path.dirname(REAL_BUNDLE)),
        });
        const context = await browser.newContext({ baseURL: server.baseUrl });
        const page = await context.newPage();
        const problems = collectProblems(page);
        try {
            await gotoSearchPanel(page);
            await expect(
                page.getByTestId("search-status-badge"),
            ).not.toHaveText(/연결 실패/);

            await runProbe(page, "파이썬 3.13 릴리스 노트");

            await expect(
                page.getByTestId("search-evidence-card").first(),
            ).toBeVisible({ timeout: 60_000 });
            const links = page.getByTestId("search-evidence-source-link");
            await expect(links.first()).toBeVisible({ timeout: 30_000 });
            const href = await links.first().getAttribute("href");
            expect(href, "출처는 원문 링크여야 한다").toMatch(/^https?:\/\//);
            await expect(
                page.getByTestId("search-evidence-retrieved").first(),
            ).toHaveText(/수집/);

            await capture(page, testInfo, "s1-real-bundle-search");
            expect(problems, problems.join("\n")).toEqual([]);
        } finally {
            await context.close();
            await server.cleanup();
        }
    });

    test("S2 child 가 없으면 실패로 보이고 출처 목록이 없다", async ({
        browser,
    }, testInfo) => {
        test.setTimeout(120_000);
        const missingRoot = await mkdtemp(
            path.join(tmpdir(), "ssak14-missing-"),
        );
        const missingBinary = path.join(missingRoot, "bin", "ssak-mcp");
        await mkdir(path.dirname(missingBinary), { recursive: true });
        const server = await startSearchServer({
            binary: missingBinary,
            trustedRoot: missingRoot,
        });
        const context = await browser.newContext({ baseURL: server.baseUrl });
        const page = await context.newPage();
        const problems = collectProblems(page);
        try {
            await gotoSearchPanel(page);

            await runProbe(page, "없는 번들");

            const error = page.getByTestId("search-evidence-error");
            await expect(error).toBeVisible({ timeout: 60_000 });
            await expect(error).toHaveAttribute("role", "alert");
            // 실패는 출처 목록을 만들지 않는다 — "출처 0건의 성공"이 되면 사용자는 실패를 모른 채 읽는다.
            await expect(
                page.getByTestId("search-evidence-sources"),
            ).toHaveCount(0);

            // 상태는 회복 가능으로 바뀌고 재시도를 제공한다.
            await expect(page.getByTestId("search-status-badge")).toHaveText(
                /연결 실패/,
                { timeout: 30_000 },
            );
            await expect(page.getByTestId("search-retry")).toBeVisible();
            await page.getByTestId("search-retry").click();
            await expect(page.getByTestId("search-status-badge")).toHaveText(
                /연결 실패|시작 중|사용 가능/,
                { timeout: 60_000 },
            );

            await capture(page, testInfo, "s2-child-down");
            expect(problems, problems.join("\n")).toEqual([]);
        } finally {
            await context.close();
            await server.cleanup();
        }
    });

    test("S3 부분 수집이면 경고와 응답하지 않은 백엔드를 보여준다", async ({
        browser,
    }, testInfo) => {
        test.setTimeout(120_000);
        const bundle = await writeFixtureBundle("partial");
        const server = await startSearchServer({
            binary: bundle.binary,
            trustedRoot: bundle.root,
        });
        const context = await browser.newContext({ baseURL: server.baseUrl });
        const page = await context.newPage();
        const problems = collectProblems(page);
        try {
            await gotoSearchPanel(page);
            await runProbe(page, "부분 수집");

            const warning = page.getByTestId("search-evidence-partial");
            await expect(warning).toBeVisible({ timeout: 60_000 });
            await expect(warning).toHaveText(/일부 소스만 수집했습니다/);
            await expect(warning).toHaveText(/bing, naver/);
            // 받은 출처는 남는다 — 부분 수집이 "결과 없음"은 아니다.
            await expect(
                page.getByTestId("search-evidence-source-link").first(),
            ).toBeVisible();

            await capture(page, testInfo, "s3-partial-sources");
            expect(problems, problems.join("\n")).toEqual([]);
        } finally {
            await context.close();
            await server.cleanup();
        }
    });

    test("S4 상한 초과면 잘라낸 항목 수와 초과 축을 보여준다", async ({
        browser,
    }, testInfo) => {
        test.setTimeout(120_000);
        const bundle = await writeFixtureBundle("truncated");
        const server = await startSearchServer({
            binary: bundle.binary,
            trustedRoot: bundle.root,
        });
        const context = await browser.newContext({ baseURL: server.baseUrl });
        const page = await context.newPage();
        const problems = collectProblems(page);
        try {
            await gotoSearchPanel(page);
            await runProbe(page, "상한 초과");

            const chip = page.getByTestId("search-evidence-budget");
            await expect(chip).toBeVisible({ timeout: 60_000 });
            await expect(chip).toHaveText(/3건/);
            await expect(chip).toHaveText(/tokens/);

            await capture(page, testInfo, "s4-budget-truncation");
            expect(problems, problems.join("\n")).toEqual([]);
        } finally {
            await context.close();
            await server.cleanup();
        }
    });

    test("S5 키보드만으로 토글하고 연결 확인까지 도달한다", async ({
        browser,
    }, testInfo) => {
        test.setTimeout(120_000);
        const bundle = await writeFixtureBundle("ok");
        const server = await startSearchServer({
            binary: bundle.binary,
            trustedRoot: bundle.root,
        });
        const context = await browser.newContext({ baseURL: server.baseUrl });
        const page = await context.newPage();
        const problems = collectProblems(page);
        try {
            await gotoSearchPanel(page);

            // 1) 토글까지 Tab 으로 도달해 Space 로 끈다 → 서버가 그 결정을 받는다(배지/안내가 바뀐다).
            await page.getByTestId("search-enable-toggle").focus();
            await expect(
                page.getByTestId("search-enable-toggle"),
            ).toBeFocused();
            await page.keyboard.press("Space");
            await expect(page.getByTestId("search-notice")).toHaveText(
                /검색을 껐습니다|검색을 켰습니다/,
                { timeout: 30_000 },
            );

            // 다시 켠다(연결 확인은 켜져 있어야 의미가 있다).
            await page.getByTestId("search-enable-toggle").focus();
            await page.keyboard.press("Space");
            await expect(page.getByTestId("search-enable-toggle")).toBeChecked({
                timeout: 30_000,
            });

            // 2) 질의 입력 → 버튼까지 Tab → Enter 로 연결 확인.
            await page.getByTestId("search-probe-query").focus();
            await page.keyboard.type("키보드 확인");
            await page.getByTestId("search-probe").focus();
            await expect(page.getByTestId("search-probe")).toBeFocused();
            await page.keyboard.press("Enter");

            await expect(
                page.getByTestId("search-evidence-card").first(),
            ).toBeVisible({ timeout: 60_000 });
            await expect(
                page.getByTestId("search-evidence-source-link").first(),
            ).toBeVisible();

            await capture(page, testInfo, "s5-keyboard-only");
            expect(problems, problems.join("\n")).toEqual([]);
        } finally {
            await context.close();
            await server.cleanup();
        }
    });

    test("S6 좁은 viewport 에서도 잘리지 않고 가로 스크롤을 만들지 않는다", async ({
        browser,
    }, testInfo) => {
        test.setTimeout(120_000);
        const bundle = await writeFixtureBundle("ok");
        const server = await startSearchServer({
            binary: bundle.binary,
            trustedRoot: bundle.root,
        });
        const context = await browser.newContext({
            baseURL: server.baseUrl,
            viewport: { width: 420, height: 760 },
        });
        const page = await context.newPage();
        const problems = collectProblems(page);
        try {
            await gotoSearchPanel(page);
            await runProbe(page, "좁은 화면");

            await expect(
                page.getByTestId("search-evidence-card").first(),
            ).toBeVisible({ timeout: 60_000 });
            // 설정 화면은 길다 — 좁은 화면에서 각 요소가 **가로로** 들어오는지가 이 시나리오의 질문이다.
            for (const testId of [
                "search-status-badge",
                "search-evidence-source-link",
            ]) {
                const target = page.getByTestId(testId).first();
                await target.scrollIntoViewIfNeeded();
                await expect(target).toBeInViewport();
            }

            const overflow = await page.evaluate(() => ({
                scrollWidth: document.documentElement.scrollWidth,
                clientWidth: document.documentElement.clientWidth,
            }));
            expect(
                overflow.scrollWidth,
                JSON.stringify(overflow),
            ).toBeLessThanOrEqual(overflow.clientWidth + 2);

            await capture(page, testInfo, "s6-narrow-viewport");
            expect(problems, problems.join("\n")).toEqual([]);
        } finally {
            await context.close();
            await server.cleanup();
        }
    });
});
