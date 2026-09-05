---
title: Ssak-Ai 전체 제품 QA 보고서
tags: [qa, audit, release-readiness, handoff]
date: 2026-09-02
reviewed_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
verdict: failed
score: 58
---

> 이 파일이 사용자/수정 에이전트를 위한 정본입니다. 아래 `artifacts/`, 개별 lane 문서 및 `cleanup.md` 경로는 저장소의 `.omo/evidence/full-qa-2026-09-02/`를 기준으로 합니다. 수정 작업은 [REMEDIATION_PLAN.md](REMEDIATION_PLAN.md)를 먼저 읽으세요. 원본 증거는 로컬 보존 자료이며 Git clone에 자동 포함되지 않을 수 있습니다.

# Ssak-Ai 전체 제품 QA 보고서

검토일: 2026-09-02 (Asia/Seoul)  
검토 SHA: `6d0a24d4e6a0686693ce29a4d13a69443ae5149b`  
종합 판정: **FAILED / 배포 승인 불가**  
완성도 평가: **58 / 100, 개인용 로컬 베타 수준**

수치는 아래 증거에 대한 QA 판단 점수이며, 통계적 정확도나 결함이 없을 확률이 아니다. 구현 범위는 넓지만 신뢰성·보안·출시 통제가 그 범위를 따라가지 못한다. 상용·공개·다중 사용자 서비스 수준으로 승인하지 않는다.

> 후속 수정 및 재검증 완료 현황: 본 보고서에서 지적된 15개 전체 결함(F01~F15)에 대해 전수 원인 분석, 격리 재현, 코드 수정, 및 단위/E2E 검증을 완료했다. 상세 내역은 [수정 인수인계 계획](REMEDIATION_PLAN.md), [증거 인덱스](EVIDENCE_INDEX.md), 및 [최종 통합 검증 기록](remediation/FINAL-INTEGRATION-VERIFICATION.md)을 참조한다. 이 보고서 본문의 원래 발견 사항·최초 판정 점수(58점)는 최초 감사 시점의 불변 기록으로 보존한다.

## 1. 범위와 판정 원칙

- 작성 주체, 사용자/에이전트 수정 여부, 최근 diff 여부로 검사 대상을 제한하지 않았다.
- Python 엔진·API·도구·테스트, React/TypeScript 대시보드·E2E, CI/릴리스·패키징, VS Code 확장, 부가 Python 스크립트까지 조사했다.
- 전체 자동 검사와 위험 구간의 심층 소스 검토를 병행했다. 모든 코드 줄·가능한 입력·플랫폼 조합을 완전 증명했다는 뜻은 아니다.
- 실제 실행은 동일 SHA의 격리 worktree에서 수행했다. 기존 사용자 변경 `data/benchmark_results.json`은 별도 검토하고 보존했다. 제품 코드를 수정하거나 커밋하지 않았다.
- 원인별로 **제품 결함**, **테스트/환경 불일치**, **확인하지 못한 영역**을 구분했다. 테스트 개수를 완성도와 동일시하지 않았다.
- codebase-memory, review-work의 5개 검토 관점, debugging의 실제 실행/정리 절차, visual-qa의 독립 2인 화면 검토를 사용했다. 그래프의 일부 한국어 인코딩 표시는 실제 파일/화면과 교차 확인하여 오탐에서 제외했다.

## 2. 우선순위별 발견 사항

P1은 외부 배포 전에 해결할 문제, P2는 안정적인 제품/검증 체계에 필요한 문제이다. P0급 실피해나 원격 침해가 발생했다는 주장은 하지 않는다.

### F01 [P1, 보안] Workspace 서비스 WebSocket 프록시에 인증 검사가 없다

- 위치: `src/antigravity_k/api/routes/workspace_services.py:312`, `:329`; HTTP 인증 미들웨어 `src/antigravity_k/api/server.py:412`.
- `_proxy_websocket`은 준비된 서비스 조회 후 바로 `websocket.accept()`와 upstream 연결을 실행한다. HTTP 미들웨어는 WebSocket scope를 보호하지 않는다. 다른 WS 경로인 `api/routes/events.py`는 별도 인증 함수를 사용한다.
- 영향: 서버가 외부에 노출되고 등록된 서비스가 실행 중인 조건에서, 프록시의 인증 경계를 우회할 수 있다. upstream 자체 인증 여부에 따라 최종 영향은 달라진다.
- 필요한 조치: accept 전에 공통 WS 인증·인가, 서비스 접근 권한, Origin 정책을 적용하고 무인증/잘못된 토큰/유효 토큰의 실제 handshake 테스트를 추가한다.
- 증거 수준: 정확한 소스 경로 검토. 외부 서비스를 공격하거나 실제 데이터를 탈취하지 않았다.

후속 F01 작업에서는 격리 echo upstream으로 인증 누락을 실제 재현했다. 공통 helper 계약에 따라 “accept 전” 권고는 “서비스 조회/upstream 연결 전 인증, accept 후 거절4401”로 명확히 했다. 서비스별 ACL/Origin 정책은 이번 수정 범위 밖으로 명시했으며 강화 필요성을 해소한 것으로 주장하지 않는다.

### F02 [P1, Git 정합성] 노트 자동 커밋이 다른 staged 파일까지 포함한다

- 위치: `src/antigravity_k/engine/vault.py:207`, `:222`.
- 대상 파일만 `git add`하지만 `git commit -m`에는 대상 제한이 없다. 이미 index에 있던 무관한 변경도 함께 커밋된다.
- 검토 에이전트가 임시 Git 저장소에서 unrelated.md를 먼저 stage한 뒤 노트를 저장하여 두 파일이 같은 커밋에 들어가는 것을 재현했다.
- 영향: 사용자/다른 에이전트의 준비 중인 변경이 의도하지 않은 메시지와 시점에 커밋된다. Git-first 제품의 핵심 신뢰 문제다.
- 필요한 조치: 기존 index를 보존하면서 대상 노트만 커밋하는 트랜잭션을 만들고, pre-staged 변경·동시 쓰기·커밋 실패를 검증한다.

후속 F02 작업에서 대상 노트만 커밋하고 무관 staged/unstaged 상태를 보존하는 트랜잭션을 적용·검증했다. 상세 계약과 한계는 [F02/F07 진행 기록](remediation/F02-F07-vault-git-transaction.md)을 따른다.

### F03 [P1, 릴리스] 태그 릴리스가 버전 추출에서 실패한다

- 위치: `.github/workflows/release.yml:93`, `pyproject.toml:7`, `:124`.
- 프로젝트는 `dynamic = ["version"]`인데 workflow는 TOML의 `project['version']`을 읽는다.
- 정확한 추출 표현식 실행 결과: `KeyError: 'version'`. 네트워크나 CI 인증과 무관하게 재현된다.
- 영향: 이 build job에 의존하는 업로드/배포 단계가 진행되지 않는다.
- 필요한 조치: 빌드된 wheel metadata 또는 패키지의 단일 버전 원천을 사용하고, workflow가 쓰는 표현식 자체를 검사한다.

### F04 [P1, 상태 표시 정합성] Mutation 점수가 실시간 데이터가 아니다

- 위치: `dashboard/src/pages/MutationDashboardPage.tsx:26`, `:451`.
- 점수·이전 점수·killed/survived·CI 상태가 고정 `STORES` 배열에서 나온다. 화면은 실시간 모니터링으로 설명한다.
- 실제 화면에서 76.5%, CI Gate PASS 등의 현황처럼 보이는 표시를 확인했다. 이 페이지에는 현재 report를 fetch/load하는 경로가 없다.
- 영향: 최신 코드가 기준을 충족하는지 사용자가 잘못 판단할 수 있다. 과거 수치 자체가 거짓이라는 주장은 아니다.
- 필요한 조치: 실제 Stryker 결과와 실행 시각·SHA를 연결하거나 명시적으로 날짜가 있는 예시/스냅샷으로 표시한다.

### F05 [P1, 공급망/정책] 배포 SBOM이 애플리케이션을 설명하지 않는다

- 위치: `.github/workflows/ci.yml:618`, `.github/workflows/release.yml:46`, `docs/RELEASE_POLICY.md:19`.
- SBOM job은 애플리케이션 의존성을 설치하거나 lockfile을 소비하지 않고 cyclonedx 도구 환경을 수집한다. 릴리스 workflow에는 정책에서 요구한 lockfile 기반 Python/대시보드 SBOM 및 의존성 notices 생성 단계가 없다.
- 영향: 만들어진 SBOM을 실제 배포물의 의존성 목록이라고 신뢰할 수 없다.
- 필요한 조치: 두 lockfile 및 최종 배포 artifact를 기준으로 목록·notice를 생성하고, 실제 wheel/번들 내용과 대조한다. 이는 저장소의 자체 정책 위반 지적이며 법률 판단이 아니다.

### F06 [P1, 의존성] 프로젝트 설치 의존성에 보안 권고가 남아 있다

- 격리된 base+dev site-packages를 명시하여 감사한 결과: **6개 패키지, 15개 권고 레코드(서로 다른 ID 14개)**.
- 대상: cryptography 48.0.0, mcp 1.27.1, pydantic-settings 2.14.1, pytest 8.4.2, python-multipart 0.0.29, starlette 1.1.0.
- 대시보드 npm audit: **high 1 / moderate 2**, 총 3개 패키지 항목. Browserslist high 항목은 빌드 도구의 입력 처리와 관련되며 그대로 브라우저 런타임 취약점이라고 해석하면 안 된다.
- 필요한 조치: 런타임/개발용, 실제 호출 경로, 권고의 공격 전제별로 triage하고 범위 제한과 lockfile을 함께 갱신한다. 설치된 취약 버전 탐지와 실제 악용 입증은 다르다.
- 원본: `artifacts/pip-audit-project.json`, `artifacts/npm-audit.json`.
- 감사 도구의 첫 기본 실행은 전역 Python 환경을 가리켰으므로 그 수치는 폐기했다. 위 수치는 `--path .../.venv/lib/python3.13/site-packages`로 범위를 지정한 결과다. 선택적 rag/finetune/MLX 조합 전체의 최종 승인 결과는 아니다.

### F07 [P2, Git 트랜잭션] 커밋 실패 후 파일 쓰기가 남는다

- 위치: `src/antigravity_k/engine/vault.py:502`–515.
- 파일 저장/fsync가 먼저 실행되고, 커밋 실패 시 이전 내용 또는 새 파일을 되돌리는 처리가 없다. 검토 에이전트가 강제 커밋 실패 후 orphan note가 남는 것을 확인했다.
- 영향: 호출자는 실패를 받지만 파일시스템은 변경되고 Git 기록은 남지 않을 수 있다. 예외 발생 테스트만으로 atomicity가 보장되지 않는다.
- 필요한 조치: 실패 시 파일/index 상태의 계약을 정하고 rollback 또는 명확한 partial-success/recovery 처리를 검증한다. 곧바로 영구 데이터 손실이 발생했다는 주장은 아니다.

후속 F07 작업은 자동 파일 롤백 대신 명시적 계약을 선택했다. Git 실패 시 파일은 보존하고 사용자 staged 상태와 HEAD는 불변으로 유지하며 `VaultCommitError`로 partial 상태를 알린다. 극단적 강제 종료 복구 한계는 진행 기록에 남겼다.

### F08 [P2, HTML 안전성] Wiki는 원시 HTML을 정화하지 않는다

- 위치: `dashboard/src/pages/wiki/MarkdownRenderer.tsx:8`, `dashboard/src/pages/wiki/ContentPanel.tsx:107`.
- Markdown 문자열을 치환한 후 `dangerouslySetInnerHTML`에 넣으며 원시 HTML과 href를 안전하게 제한하지 않는다.
- 실제 앱의 Wiki 읽기 응답만 합성 입력으로 대체하여 확인: `rawHtmlRendered=1`, `inlineScriptExecuted=false`, `cspBlockedInline=true`.
- **중요한 제한:** 기본 CSP가 inline onerror 실행을 차단했다. 따라서 이 검토는 토큰 탈취나 기본 배포에서의 스크립트 실행을 입증하지 않았다. 초기 보안 lane의 광범위한 XSS 표현은 이 후속 관찰로 범위를 좁힌다.
- 원시 HTML에 의한 UI 위장/예상하지 않은 DOM은 여전히 렌더링된다. CSP 하나에만 의존하지 말고 Chat과 같은 안전한 Markdown/sanitizer 경로를 사용한다.

### F09 [P2, E2E 신뢰성] 기본 PIN fixture와 실행 서버 설정이 불일치한다

- 위치: `dashboard/e2e/pages/DashboardPage.ts:140`, `src/antigravity_k/api/auth_routes.py:179`.
- 테스트 helper가 `ag_access_pin=0000`을 무조건 저장한다. PIN hash가 없는 서버는 `/api/auth/login`에 명시적인 503을 반환하고, 테스트는 잠금 화면에 머문다.
- 원래 53개 대상 실행의 저장 결과에서 28개 실패가 확인됐다. 실패 화면과 후속 독립 재현은 이 fixture 문제를 뒷받침한다.
- 새 브라우저 저장소에서는 Chat/Git/명령 팔레트/탐색기가 정상 렌더링·이동했고 콘솔/page/request 오류가 없었다. **28개 실패를 곧바로 28개 제품 기능 고장으로 계산하지 않았다.**
- 필요한 조치: auth-enabled와 loopback/no-auth fixture를 분리하고, 실제 로그인 계약을 사용하는 storage state를 만든다. 이어서 전체 E2E를 다시 실행해야 한다.

### F10 [P2, 품질 게이트] CI 성공이 전체 사용자 흐름 성공을 의미하지 않는다

- 위치: `.github/workflows/ci.yml:542`; `Makefile:210`; `dashboard/e2e/tests/chat.spec.ts:40`.
- 전체 Playwright suite는 `continue-on-error`; 접근성 suite만 hard gate다. 이는 문서에도 명시된 의도적인 선택이지만 배포 신뢰 수준은 제한된다.
- 일부 채팅 테스트는 오류 응답 bubble도 성공으로 받아들일 수 있고, task 실행 테스트는 API를 mock한다. 명령 팔레트 helper는 버튼을 우선하므로 Cmd+K 성공 증거와 동일하지 않다.
- `make security`는 pip-audit/bandit 실패를 `|| true`로 삼킨다. 다만 CI에는 별도의 Python 보안 검사가 있으므로 모든 보안 검사가 무력화됐다는 주장은 아니다.
- 필요한 조치: 핵심 happy-path 및 오류-path의 의미 있는 assertion을 hard gate로 만들고, mocked UI 검사와 진짜 통합 E2E를 구분한다.

### F11 [P2, 설치/테스트 정합성] dev 설치만으로 전체 Python suite가 통과하지 않는다

- 위치: `tests/test_memory_service.py:120`, `pyproject.toml:55`.
- `uv sync --frozen --extra dev` 후 실행한 전체 suite는 ChromaDB가 없는 환경에서 `mem.vector_store is not None` assertion 하나가 실패한다.
- ChromaDB는 rag extra다. 선택 기능을 필수로 가정한 테스트/설치 계약의 불일치이지, 설치하지 않은 벡터 엔진이 고장 났다는 결론이 아니다.
- 필요한 조치: CI/개발 명령의 extras를 명시하거나 optional dependency 유무별 테스트를 나눈다.

### F12 [P2, 모바일 UI] 제어 요소와 상태 정보가 잘린다

- Plugins: `dashboard/src/styles/index.css:6816`의 `minmax(340px, 1fr)`가 모바일 콘텐츠 폭 약 302px보다 커서 toggle이 잘린다.
- Mutation: `dashboard/src/pages/MutationDashboardPage.tsx:146`의 overflow hidden + 고정 ring/가로 row 때문에 상태 badge와 경로가 잘린다.
- Data extraction: `dashboard/src/pages/dex/MetricsBar.tsx:16`, `dashboard/src/components/shared/MetricItem.tsx:16`에서 지표 라벨이 한글 음절 단위의 세로 열처럼 압축된다.
- Chat/Wiki/Settings/History 등에서 단어·어미가 부자연스럽게 갈라진다. 인코딩 오류가 아니라 줄바꿈/폭 문제다.
- 독립 검토자 2명이 42개 원본 캡처를 모두 확인했다. 문서 전체 scrollWidth가 정상이어도 내부 clip은 존재한다.
- 증거: `artifacts/visual/mobile-plugins.png`, `mobile-mutation.png`, `mobile-data-extraction.png`; 상세 `visual-cjk.md`, `visual-integrity.md`.

### F13 [P2, 확장 테스트] VS Code 확장의 npm test가 실행되지 않는다

- 위치: `vscode-extension/package.json:33`, `:36`.
- 깨끗한 격리 설치에서 webpack compile은 통과했지만 `npm test`의 pretest가 `sh: eslint: command not found`로 실패했다. manifest에는 lint 스크립트가 있으나 ESLint 개발 의존성이 없다.
- 필요한 조치: 확장의 독립 개발/테스트 의존성과 실제 테스트 runner 계약을 복구하고 Extension Host에서 동기화 동작을 검증한다. 이번에는 실제 VS Code host 동작을 인증하지 않았다.

### F14 [P2, 정책 검증] release-baseline 검사에 사각지대가 있다

- 위치: `src/antigravity_k/engine/release_baseline.py:86`, `:112`.
- 금지 목록의 AGPL SPDX 단독 헤더가 source-text 검사에 걸리지 않는 것을 실제 validator에 합성 파일 입력을 주어 확인했다. long-form 문구만 검사하는 기존 테스트가 놓친다.
- entrypoint 검사는 소스 파일 존재만 검사하므로, 파일을 유지한 채 command/name을 제거하는 경우를 검증하지 못한다.
- 이는 현재 저장소에 금지 코드가 실제 포함됐거나 명령이 실제 누락됐다는 주장이 아니라, 문서화된 배포 검증기의 방어 범위 문제다.

### F15 [P2/유지보수] 정적 품질 게이트가 일관되지 않다

- Ruff lint는 통과하지만 `ruff format --check src tests scripts`는 167개 파일 재포맷 필요로 실패한다.
- mypy는 425개 소스 파일에서 오류 없이 끝났지만 untyped body 미검사 메모가 있다. Basedpyright CI는 전체 Python이 아닌 두 파일만 검사한다. 환경이 다른 전체 실행의 warning 개수는 혼합하여 점수화하지 않았다.
- 159개 product 모듈이 250 pure LOC를 넘는다. 큰 파일 자체가 버그라는 뜻은 아니지만, tool loop/모델 관리/시스템 API에 복잡성과 수정 위험이 집중된다.
- 일부 sandbox 검사는 실행되는 정책 대신 소스 문자열·allowlist 존재를 검사한다. 권한 gate의 auto-pilot 경로도 사용자 승인을 대체하지 않는다. 구체적인 행동 기반 보안 테스트가 필요하다.

## 3. 실제 검사 결과

| 검사 | 결과 | 해석 |
|---|---|---|
| Python 전체 tests + coverage, base+dev | 4,790 passed / 1 failed / 11 skipped, 148.56초 | optional ChromaDB 계약 실패 1건 |
| Python statement coverage | 76.69% | 설정된 최소 60% 통과, 전체 동작 증명 아님 |
| Python warnings | 202 | SQLite 미종료 ResourceWarning 등이 포함됨 |
| 이전 별도 Python quick run | 4,799 passed / 6 skipped / 19 deselected | 설치/선택 조건이 달라 전체 실행과 합산하지 않음 |
| Ruff check | PASS | src/tests/scripts |
| Ruff format check | FAIL, 167 files | CI formatter gate와 불일치 |
| mypy | PASS, 425 source files | 비엄격/untyped 영역 제한 있음 |
| Dashboard ESLint / TypeScript | PASS / PASS | 현재 소스 빌드 기반 |
| Dashboard Vitest | 43 files / 596 tests PASS | 단위/컴포넌트 검사 |
| Dashboard production build | PASS | 875 modules |
| API E2E smoke | 9 PASS | live backend |
| Playwright 접근성 | 12 PASS | 이것만으로 전체 E2E 통과 아님 |
| Playwright 전체 | 53개 대상, 저장 실패 목록 28개 | PIN fixture 불일치; 통과 숫자 추정/합산 안 함 |
| 독립 수동 QA | 11 surface + 4 adversarial 기록 | 정상 탐색/경로 차단 확인, valid PIN 미확인 |
| 화면 | 12 routes × 3 viewport + palette/terminal 6 = 42 PNG | 2인 독립 검토 REVISE |
| VS Code 확장 | build PASS / npm test FAIL | ESLint 미설치 |
| swarm_mode, ssak-ai-lab 및 부가 Python | compileall PASS | 문법 검사만, 실제 시나리오 승인 아님 |
| Python 의존성 감사 | 6 packages / 14 distinct advisory IDs | base+dev site-packages 대상 |
| Dashboard npm audit | high 1 / moderate 2 | 노출/개발 의존성 분리 필요 |

보안 확인에서 경로 traversal 요청은 403으로 거절됐다. 기본 응답에는 CSP, nosniff, frame DENY 등 보호 헤더가 있었다. fresh browser 기본 부트스트랩 및 실행 중 확인한 route에는 pageerror가 없었다. 장점은 그대로 유지해야 한다.

## 4. 독립 검토 판정과 증거

| 관점 | 최종 상태 | 근거 |
|---|---|---|
| 목표/정합성 | FAIL | Vault index/커밋 실패 상태, recovered-lanes.md |
| 실제 QA 실행 | INCONCLUSIVE for whole product | 일부 실제 흐름 통과, valid PIN/LLM/전체 E2E 미검증; hands-on-qa.md |
| 코드 품질 | FAIL | ../code_quality-code-review.md |
| 보안 | FAIL | WS 경계 및 의존성; Wiki 영향은 후속 CSP 실험으로 축소 |
| 문서/릴리스 맥락 | FAIL | context.md |
| 화면 Pass A / Pass B | REVISE / REVISE | visual-integrity.md / visual-cjk.md |

각 lane은 위 SHA에 묶인다. 새로운 커밋에는 승인으로 재사용할 수 없다. 이전 세션에서 완료된 세 lane은 대화 증거와 원본 보고서로 복구했고, 소실된 QA/맥락 lane은 더 좁은 범위로 재실행했다. 완료되지 않은 lane을 PASS로 간주하지 않았다.

## 5. 냉정한 완성도 평가

| 항목 | 점수 | 판단 |
|---|---:|---|
| 기능 구현 기반 | 78 | 실제 API/React/CLI와 넓은 테스트 기반은 존재 |
| 데이터/Git 정합성 | 50 | 자동 커밋 scope와 실패 후 상태가 불안정 |
| 보안·권한 경계 | 45 | 좋은 기본 방어가 있으나 WS 누락·의존성 조치 필요 |
| 테스트 신뢰성 | 62 | 수량은 많지만 E2E fixture/게이트/의미 있는 assertion 부족 |
| UX·정보 신뢰도 | 60 | 모바일 잘림과 정적 수치의 실시간 표시 |
| 출시·운영 준비 | 40 | 릴리스 버전 추출, SBOM/notice, 확장 테스트 미완성 |
| 유지보수성 | 58 | 큰 모듈·혼합 패턴·엄격 검증 사각지대 |

**종합 58/100.** 개인 개발자가 로컬에서 직접 관찰하며 사용하는 베타로는 가치가 있다. 그러나 기능 수나 4천 개 이상의 테스트를 근거로 안정적 완제품이라고 부르기는 어렵다. 특히 파일과 Git을 수정하는 에이전트는 일반 조회용 대시보드보다 정합성·권한 기준이 높아야 한다.

## 6. 재승인 순서와 종료 조건

1. WS 프록시 인증/인가 및 Vault 커밋 범위를 우선 수정한다. 실패·동시성·기존 staged 상태의 행동 테스트가 필요하다.
2. 릴리스 버전 추출과 실제 배포물 기반 SBOM/notices를 복구하고, 버전/entrypoint/금지 marker 검증을 artifact 기준으로 실행한다.
3. 의존성 권고를 runtime/dev와 실제 공격 전제로 분리해 조치한다. 단순 audit 무시 설정으로 통과시키지 않는다.
4. E2E auth fixture를 고치고 실제 provider/task/file/Git 흐름의 성공 결과와 부작용을 검증한다. 핵심 suite를 hard gate로 승격한다.
5. Mutation 표시를 실제 보고서 또는 명시적인 snapshot으로 바꾸고, 모바일 clip/CJK/전체 탭·모달·스크롤 상태를 재검증한다.
6. 지원 설치 조합·VS Code 확장·formatter·전체 타입 검사를 일관된 재현 명령으로 묶는다.

재승인 조건은 단순 테스트 개수 증가가 아니라 **현재 SHA의 핵심 흐름이 실제로 완료되고, 고위험 결함이 닫히고, 실패가 CI에 정확히 반영되는 것**이다.

## 7. 확인하지 못한 영역

- 실제 외부 LLM 유료 호출, 장시간 자율 작업, 모델별 도구 호출 품질, MLX/학습/GPU/OOM 및 장기 부하.
- 유효 PIN 설정이 있는 배포에서 로그인/토큰 만료/갱신의 전체 운영 흐름. 없는 비밀값을 추정하거나 새 보안 설정을 만들지 않았다.
- 실제 shell 실행은 QA 서버에서 의도적으로 비활성화되어 terminal 연결/disabled 안내만 확인했다.
- 모든 OS, 실제 VS Code Extension Host, 컨테이너/Kubernetes 배포, 실제 PyPI/GitHub release publication.
- 모든 화면의 하위 탭·모달·입력 조합·스크롤·motion/IME 상태. 42개 캡처는 모든 기본 route/3개 크기의 resting state를 뜻한다.
- 실제 권고 exploitability 및 별도 침투 테스트. 취약 버전 감사는 보안 인증이 아니다.

따라서 **오류가 전혀 없다는 보증은 하지 않는다. 오히려 확인된 결함 때문에 현 시점에서는 그 결론을 내릴 수 없다.** 본 작업은 진단/평가 요청이므로 제품 수정은 수행하지 않았다.

## 8. 증거 보관과 정리

- 테스트 원문/JUnit, 감사 JSON, 확장 build/test log, 42개 PNG와 manifest, 원래 Playwright 실패 결과는 `artifacts/`에 보관했다.
- fresh browser 및 HTTP 수동 QA 원문과 이미지는 이 보고서 옆에 있다.
- 그래프 도구의 인코딩 표현, 잘못된 전역 audit 대상, 선택 의존성 누락, E2E fixture 불일치는 제품 결함과 분리했다.
- 임시 worktree/서버 정리와 원본 상태 최종 확인은 `cleanup.md`에 기록한다. 사용자 benchmark 변경은 유지한다.
