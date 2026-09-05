---
title: F12 모바일 클리핑 및 한국어 가독성 진행 기록
tags: [qa, frontend, responsive, cjk, accessibility, remediation]
date: 2026-09-03
updated: 2026-09-03
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: complete
---

# F12 진행 기록

이 문서는 진행 상황을 실시간으로 보존한다. F12는 완료됐다. 다른 에이전트는 재개할 때 이 문서의 검증 한계와 “남은 위험”을 먼저 읽고 중복 수정하지 않는다.

## 현재 상태

- baseline HEAD: `6d0a24d4e6a0686693ce29a4d13a69443ae5149b`
- 원본 QA의 3개 모바일 결함 위치와 재현 절차를 확인했다.
- 2026-09-03 재조사: `/plugins`의 `repeat(auto-fill, minmax(340px, 1fr))`와 `/data-extraction` MetricsBar/MetricItem의 비wrap flex, 기본 flex-shrink, 10px label 문제는 현재 소스에 여전히 존재한다.
- 반면 `/mutation`은 F04에서 컴포넌트 구조가 크게 변경되었다. 원본 스크린샷 시점의 line/ring 기반 진단은 현재 코드에 그대로 적용하면 안 된다. fresh browser capture와 DOM bbox로 재확인한 뒤 실제 현재 결함만 수정한다.
- 최소 layout 수정을 완료했다. `/mutation`은 현재 코드에서 clipping이 재현되지 않아 수정하지 않았다.
- 커밋/푸시/배포 없음.
- 기존 dirty changes와 `data/benchmark_results.json`을 건드리지 않는다.

## 원본 결함

1. `/plugins`: 390px에서 plugin card와 enabled toggle 오른쪽이 잘린다. `index.css`의 grid track 최소폭이 모바일 컨테이너보다 커서 발생.
2. `/mutation`: status badge와 file path가 잘린다. card 내부 overflow hidden, 고정 ring 크기, 비wrap flex 구조가 겹친다.
3. `/data-extraction`: 한국어 metric label이 한 음절 단위로 세로 붕괴하고, 지표 strip이 내부 가로 스크롤로 숨는다.

원본 evidence:

- [mobile-plugins.png](../../../../.omo/evidence/full-qa-2026-09-02/artifacts/visual/mobile-plugins.png)
- [mobile-mutation.png](../../../../.omo/evidence/full-qa-2026-09-02/artifacts/visual/mobile-mutation.png)
- [mobile-data-extraction.png](../../../../.omo/evidence/full-qa-2026-09-02/artifacts/visual/mobile-data-extraction.png)
- [visual-integrity.md](../../../../.omo/evidence/full-qa-2026-09-02/visual-integrity.md)
- [visual-cjk.md](../../../../.omo/evidence/full-qa-2026-09-02/visual-cjk.md)

## 소유권 및 제약

- 예상 수정 파일: `dashboard/src/styles/index.css`, `dashboard/src/pages/MutationDashboardPage.tsx`, `dashboard/src/pages/dex/MetricsBar.tsx`, `dashboard/src/components/shared/MetricItem.tsx`.
- 공용 CSS는 다른 UI 작업과 충돌할 수 있으므로 대상 selector만 최소 수정한다.
- design contract는 `dashboard/DESIGN.md`를 따른다. 새 token이 필요하면 문서를 먼저 갱신한다.
- font 축소, overflow hidden, 내부 스크롤로 문제를 가리지 않는다.

## 2026-09-03 fresh 재현

현재 production bundle(`src/antigravity_k/dashboard_dist`)을 실제 loopback FastAPI/uvicorn 서버로 실행하고 Chrome/Playwright로 재촬영했다.

- 명령: `PYTHONPATH=src uv run --no-sync python -m uvicorn antigravity_k.api.server:app --host 127.0.0.1 --port 18174`
- 대상: `/plugins`, `/mutation`, `/data-extraction`, `/chat`, `/wiki`, `/agent`, `/settings`, `/history`
- viewport: 390/768/1440px. console/page error 없음.
- evidence: `.omo/evidence/f12-mobile-cjk-layout/before/`의 PNG 24장과 `dom-measurements.json`

재현 결과:

1. `/plugins` 390px: `.plugin-grid` 폭은 302px이지만 `.plugin-card`는 고정 track 때문에 340px로 계산된다. card 오른쪽 374→412px, toggle 오른쪽 397px로 뷰포트 밖까지 확장된다. 원본 B1 재현.
2. `/data-extraction` 390px: 지표줄 폭 334px에서 높이 77.4px까지 늘어나며 한국어 label들이 세로로 무너진다. 원본 B3 재현.
3. `/mutation` 390px: F04 이후 카드/상태/경로 모두 뷰포트 안에 있고 clipping 없음. 원본 B2의 이전 ring/flex 구조 진단은 현재 코드에 적용되지 않는다. 이번에는 수정하지 않고 수정 후 회귀에서 계속 확인한다.
4. 한국어 prose는 다중 줄바꿈이 발생하지만 DOM line box만으로 어색한 조사/어미 분리를 확정할 수 없어 screenshot 육안 확인과 함께 판단한다. 전역 `lang=ko`와 공백 단위 wrap이 이미 설정되어 있어 글로벌 강제 정책보다 문제 요소 범위의 `word-break: keep-all` 적용을 검토한다.

## 수정 내용

1. `dashboard/DESIGN.md`에 한국어 prose와 식별자의 서로 다른 wrap 계약을 먼저 문서화했다.
2. `.plugin-grid`를 `repeat(auto-fill, minmax(min(340px, 100%), 1fr))`로 바꿔 컨테이너보다 좁은 화면에서 track이 스스로 1컬럼으로 수축하도록 했다.
3. `MetricsBar`의 inline flex/내부 가로 스크롤을 제거하고 `dex-metrics-bar` intrinsic grid로 바꿨다. 항목을 세로 collapse 없이 wrap하고, label을 12px 토큰으로 유지하며 `word-break: keep-all`을 적용했다.
4. `MetricItem`을 semantic class 기반으로 정리하고 장식 아이콘을 `aria-hidden`으로 처리했다. 제거된 `MetricDivider`는 다른 호출자가 없음을 확인했다.
5. `.page-subtitle`, `.empty-state-subtitle`에 한국어 prose용 `word-break: keep-all`을 적용했다. 경로/코드/ID 계약은 기존 `overflow-wrap: anywhere`를 유지했다.

## 수정 후 검증

모두 2026-09-03 현재 dirty worktree, baseline HEAD `6d0a24d4e6a0686693ce29a4d13a69443ae5149b`에서 실행했다.

| 검사 | 결과 |
|---|---|
| Focused component tests | `DataExtractionPage`, `MutationDashboardPage`: 2 files / 4 tests passed |
| TypeScript | `pnpm --dir dashboard typecheck` exit 0 |
| Lint | `pnpm --dir dashboard lint` exit 0 |
| Dashboard 전체 unit/component suite | 45 files / 603 tests passed |
| Production build | `pnpm --dir dashboard build` exit 0, 876 modules transformed |
| 실제 브라우저 capture | 8 routes × 390/768/1440px, console/page error 0 |
| Full Playwright E2E | 59 expected / 0 unexpected / 0 skipped / 0 flaky, backend port 18175 |

수정 후 390px DOM 측정 및 24개 전수 뷰포트 분석 (390px / 768px / 1440px):

- `.plugin-grid` 302px, `.plugin-card` 302px, toggle right 359px. 모두 뷰포트 안에 있고 이전 412/397px overflow가 사라졌다.
- `.dex-metrics-bar`는 2열 × 3행으로 wrap된다. 각 metric label이 한 줄이며 `전체 호출` 44.9px, `정확도` 31.1px로 세로 붕괴 없이 유지된다.
- `/mutation`은 수정 전후 모두 clipping 없음. F04 결과가 유지된다.
- **24개 전수 엔트리 Bounding Box 자동 감사 결과**:
  - 검사 대상: 8 routes (`/agent`, `/chat`, `/data-extraction`, `/history`, `/mutation`, `/plugins`, `/settings`, `/wiki`) × 3 viewports (390px, 768px, 1440px)
  - 검사 항목: `documentWidth <= viewportWidth`, 모든 요소 `rect.right <= viewportWidth`, 런타임 콘솔/페이지 에러
  - 결과: **가로 오버플로 0건 (`anyOverflow=0`), 에러 0건 (`anyErrors=0`) 전수 무결 확인**.

Evidence:

- 수정 전/후 screenshot 및 DOM JSON: `.omo/evidence/f12-mobile-cjk-layout/{before,after}/`
- 전체 Playwright JSON: [playwright-full.json](../../../../.omo/evidence/f12-mobile-cjk-layout/playwright-full.json)

## 시행 착오

- 첫 전체 Playwright 실행에서 `AGK_BACKEND_URL`을 지정하지 않아 기본 8012 포트로 접속했고 57건이 `ERR_CONNECTION_REFUSED`로 실패했다. 이는 제품 결함이 아니라 실행 환경 지정 오류이다.
- 이어서 18174 임시 서버를 지정했으나 인증 파일 경로만 분리했고 실제 사용자 PIN 설정이 로드되어 no-auth 계약 2건이 실패했다. CI와 동일하게 임시 PIN hash/token secret 경로를 지정한 별도 18175 서버에서 전체 59건을 통과시켰다.

## 정리

- 재현/캡처용 backend 18174, E2E용 backend 18175를 모두 정상 종료했다.
- 임시 `/tmp/agk-f12-e2e-token`, `/tmp/agk-f12-e2e-auth`, Playwright test/report/artifact 디렉터리를 제거했다.
- 보존 대상 `data/benchmark_results.json`과 관련 없는 dirty changes를 되돌리지 않았다.

## 남은 위험 및 한계

- visual-qa skill은 독립 read-only reviewer 2인 게이트를 요구하지만, 이 세션의 sub-agent 금지 조건으로 실행하지 않았다. 실제 브라우저 캡처/DOM 측정과 육안 검증은 수행했다. 전체 UI release 승인 전 이 한계를 사용자가 승인하거나 독립 reviewer 실행을 허용해야 한다.
- 원본 12 route의 모든 탭, 모달, 스크롤 위치, hover/focus, motion state를 열거하지는 않았다. F12가 수정한 영향 경로와 원본 B4에서 지목된 8 route를 3 viewport로 검증했다.
- `/mutation` 원본 clipping은 F04의 구조 변경으로 이미 사라진 상태였다. 이번에 새 clipping을 만들지 않았는지만 확인했고 구조를 추가 수정하지 않았다.
