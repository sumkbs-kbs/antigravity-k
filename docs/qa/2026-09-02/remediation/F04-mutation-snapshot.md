---
title: F04 Mutation 지표 진실성 진행 기록
tags: [qa, mutation, dashboard, data-integrity, remediation]
date: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: fixed_manual_browser_verified_pending_commit
---

# F04 진행 기록

Mutation 화면이 하드코딩된 수치를 실시간 CI 결과처럼 표시하던 결함을 수정했다. 새 ingestion backend나 API를 만들지 않고, 남아 있는 측정값을 검증된 historical snapshot으로 명시적으로 표현한다. 이 문서의 모든 수정은 기준 commit 위의 미커밋 변경이며 커밋하지 않았다.

## 상태

1. 완료: 기준 구현의 `STORES` 상수와 잘못된 threshold 50이 화면 계산의 원천이었음을 확인.
2. 완료: historical snapshot 계약, Zod boundary parsing, provenance/stale/invalid/empty 상태를 구현.
3. 완료: RED 2건을 확인한 뒤 focused test를 GREEN으로 전환.
4. 완료: focused test, ESLint, TypeScript build, dashboard 전체 598 test, production build 통과.
5. 완료: 실제 loopback FastAPI 서버에서 production bundle을 브라우저 QA. 375/768/1280px, filter/empty, malformed snapshot, console을 검증.
6. 제한: visual-qa skill의 독립 reviewer 2인 게이트는 수행하지 않았다. 후속 인수인계가 사용자 명시 없는 sub-agent를 금지했기 때문이다. 아래 수동 브라우저 QA와 screenshot을 그 대체 증거로 보존한다.

## 계약

- Snapshot은 `schemaVersion: 1`, `kind: "historical-snapshot"`이어야 한다.
- 값은 오직 `dashboard/src/data/mutation-snapshot.json`에서 온다. 컴포넌트에 점수 배열을 하드코딩하지 않는다.
- `capturedAt`, 각 target의 `lastMeasuredAt`, source 설명, 40자 source commit, scope note가 반드시 있다.
- 마지막 측정이 30일을 초과하면 `Historical snapshot: stale`로 표시한다.
- threshold는 snapshot의 `breakThreshold`를 사용한다. 보존된 기준은 Stryker 설정과 같은 55다.
- snapshot이 Zod 검증을 통과하지 못하면 `role="alert"` 오류 상태를 내고 점수/합계/카드를 표시하지 않는다.
- 데이터가 없는 target이나 filter 결과는 empty 상태로 표시하며 PASS를 표시하지 않는다.
- 화면은 live CI gate나 실시간 상태를 주장하지 않는다. 구 문구 `CI Gate: PASS`와 “실시간” 표현을 제거했다.

## 구현

- [mutation-snapshot.json](../../../../dashboard/src/data/mutation-snapshot.json): 검증 대상 historical snapshot. 보존된 세 target과 여섯 시점의 timeline, 원본 설명, scope 제한을 담는다.
- [MutationDashboardPage.tsx](../../../../dashboard/src/pages/MutationDashboardPage.tsx): `decodeMutationSnapshot`, `MutationDashboardView`, typed snapshot export를 추가하고 route default export는 유지한다. provenance/aggregate/filter/card/timeline과 invalid/empty 상태를 snapshot 기반으로 계산한다.
- [MutationDashboardPage.test.tsx](../../../../dashboard/src/pages/MutationDashboardPage.test.tsx): provenance/stale/no-live-CI 표시와 malformed boundary rejection을 잠근다.
- [DESIGN.md](../../../../dashboard/DESIGN.md): Mutation Snapshot Console primitive의 상태, 접근성, 레이아웃 규칙을 문서화한다.

Snapshot 값은 다음과 같다.

| target | score | killed | survived | no coverage | last measured |
|---|---:|---:|---:|---:|---|
| pluginRegistry | 86.78 | 105 | 13 | 3 | 2026-07-17 |
| agentMonitorStore | 78.13 | 100 | 26 | 2 | 2026-07-21 |
| localHistoryStore | 64.52 | 100 | 28 | 27 | 2026-07-15 |

합계는 305 killed / 67 survived / 32 no coverage, 평균 76.5%다. `terminalStore`, `outputStore`는 현재 CI 대상이지만 보존된 점수가 없어 snapshot scope note에 명시했다.

## RED → GREEN

구현 전 named export 부재로 아래 두 오류로 focused test가 실패했다.

```text
- MutationDashboardView is not a function / component type invalid
- decodeMutationSnapshot is not a function
```

구현 후 최종 명령과 결과:

```bash
pnpm --dir dashboard exec vitest run src/pages/MutationDashboardPage.test.tsx --reporter verbose
# 1 file, 2 tests passed

pnpm --dir dashboard exec tsc -b --pretty false
# exit 0

pnpm --dir dashboard exec eslint src/pages/MutationDashboardPage.tsx src/pages/MutationDashboardPage.test.tsx
# exit 0

pnpm --dir dashboard test
# 44 files, 598 tests passed

pnpm --dir dashboard build
# 878 modules transformed, production bundle created
```

첫 lint는 render body의 `Date.now()` impure render 경고를 보고했고, 이를 제거하려던 `useEffect + setState`도 `react-hooks/set-state-in-effect` 경고를 남겼다. 최종적으로 lazy `useState(() => Date.now())`로 mount마다 한 번만 읽도록 바꾸고 경고 없음을 확인했다.

## 실제 브라우저 QA

static `vite preview`는 `/api/session/info`가 없어 PIN lock으로 fail-closed했다. 이는 보안 동작이므로 실패로 계산하지 않았다. 대신 실제 배포 경로와 같은 loopback FastAPI server에서 production dashboard를 검증했다.

```bash
uv run --no-sync agk serve --host 127.0.0.1 --port 18123
```

- Route: `http://127.0.0.1:18123/mutation`
- Viewport: 375x812, 768x900, 1280x900
- 세 폭 모두 `document.scrollWidth == clientWidth`, horizontal overflow 없음.
- Filter 결과: all 3 / passed 1 / warning 2 / failed 0. failed 선택 시 empty message 표시.
- Malformed snapshot: 임시 production asset에서만 `capturedAt`을 비정상 문자열로 바꿔 검증 후 원복. `Mutation snapshot unavailable`, `role="alert"`, 유효성 오류 원문 표시, 점수 없음 확인.
- 최종 clean rebuild 후 페이지 재렌더링 및 console error/warning 0건.
- 한국어 sidebar/상태 UI와 영어 본문에서 glyph 누락, 세로 한 글자 붕괴, descender clipping, 가로 clip 관찰 없음.

증거/스크린샷:

- [browser-qa.json](../../../../.omo/evidence/f04-mutation-qa/browser-qa.json)
- [375px](../../../../.omo/evidence/f04-mutation-qa/mutation-375.png)
- [768px](../../../../.omo/evidence/f04-mutation-qa/mutation-768.png)
- [1280px](../../../../.omo/evidence/f04-mutation-qa/mutation-1280.png)
- [filter empty](../../../../.omo/evidence/f04-mutation-qa/mutation-filter-empty-1280.png)
- [invalid snapshot](../../../../.omo/evidence/f04-mutation-qa/mutation-invalid-1280.png)
- [console](../../../../.omo/evidence/f04-mutation-qa/console.json)

## 한계 및 남은 위험

- Snapshot은 historical record지 현재 CI 결과가 아니다. 화면 문구와 이 문서가 그 한계를 계속 유지해야 한다.
- 현재 CI가 mutate하는 `terminalStore`, `outputStore`의 보존 점수는 없다. 과거 기록을 추정해 채우지 않았다.
- 실시간 Stryker report ingestion/API는 이번 범위가 아니다. 새 측정이 생기면 `mutation-snapshot.json`을 갱신하거나 별도 ingestion 설계가 필요하다.
- F12의 다른 모바일 clip/CJK 이슈는 여기서 해결된 것이 아니다. 이번 검사는 Mutation route에 국한된다.
- 독립 visual reviewer를 아직 실행하지 않았다. 후속 작업에서 sub-agent 사용이 허용되면 현재 SHA와 fresh screenshot 전체로 Pass A/B를 돌려야 한다.

## 검증 대상 지문

기준 commit `6d0a24d4e6a0686693ce29a4d13a69443ae5149b` 위의 미커밋 상태다.

| 파일 | SHA-256 |
|---|---|
| `dashboard/src/pages/MutationDashboardPage.tsx` | `0508b64fe5e0f799de68fd18426b075bba3074ffe22fa7db0b016040f29a0502` |
| `dashboard/src/pages/MutationDashboardPage.test.tsx` | `3bea1808d51f3652229372bd5a4542a1e50e92596ad4a6d345ce587510999166` |
| `dashboard/src/data/mutation-snapshot.json` | `cabf1f2a299bd17bb4204dace96a735df9d6faa840adcbc86e033761488115e6` |
| `dashboard/DESIGN.md` | `20fb2e2a7118f0b1d2cc774ccdfc692ae4c64b567aba2a35c4750f39d8e744a2` |
| `src/antigravity_k/dashboard_dist/assets/MutationDashboardPage-B7qhq642.js` | `61e7e67f0056d1f65e6d0e6fe83cc2e33c5b6903d2b0f4467e75748870dfcb31` |
