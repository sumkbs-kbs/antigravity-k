---
title: Ssak-Ai QA 증거 인덱스
tags: [qa, evidence, reproducibility]
date: 2026-09-02
reviewed_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
---

# 증거 인덱스

검토 SHA: `6d0a24d4e6a0686693ce29a4d13a69443ae5149b`.
상세 raw evidence는 저장소 `.omo/evidence/full-qa-2026-09-02/`에 있다. 이 파일의 링크는 현재 저장소에서 동작하는 상대 경로다. Git clone에는 ignored 자료가 포함되지 않을 수 있으므로 없으면 인수인계 계획의 명령으로 재생성한다. 외부 공유 전에는 내부 경로/환경 정보/사용자 데이터 포함 여부를 다시 검토한다.

## 자동 검사 원문

### 후속 F01 수정 검증

아래는 최초 QA가 아닌 미커밋 F01 수정본에 대한 결과다. [수정 기록](remediation/F01-workspace-websocket-auth.md)의 HEAD+파일 지문으로 정확한 대상을 구별한다.

| 자료 | 링크 | 결과 |
|---|---|---|
| 집중/실제 네트워크 E2E | [focused-wire-final.log](../../../.omo/evidence/full-qa-2026-09-02/remediation-f01/focused-wire-final.log) | 28 passed, 실제 로그인·등록·WS 왕복/거절/종료 |
| 격리 Python 회귀 | [regression-final.log](../../../.omo/evidence/full-qa-2026-09-02/remediation-f01/regression-final.log) | 4827 passed, 6 skipped, 19 deselected |
| 변경 파일 정적 검사 | [static-final.log](../../../.omo/evidence/full-qa-2026-09-02/remediation-f01/static-final.log) | ruff/format/fresh basedpyright 통과; 편집기 LSP 잔류 표시는 수정 기록 참조 |
| wheel build | [build-final.log](../../../.omo/evidence/full-qa-2026-09-02/remediation-f01/build-final.log) | 새 transport 포함 wheel 성공, 배포하지 않음 |
| 독립 경계 검토 | [f01-boundary-gate-review.md](../../../.omo/evidence/f01-boundary-gate-review.md) | 송신 중 disconnect 지적→회귀 RED/GREEN→최종 APPROVE |

### 후속 F02/F07 수정 검증

결과 요약과 정확한 재현 명령은 [F02/F07 진행 기록](remediation/F02-F07-vault-git-transaction.md)에 있다. 아래 핵심 결과는 문서에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| Vault/API 집중 regression | 31 passed, 무관 staged 보존·기존 노트 staged+unstaged 보존·no-op·hook 실패 포함 |
| 실제 멀티프로세스 저장 | 4개 프로세스 동일 Vault 저장, 각 HEAD가 노트 1개만 포함 |
| 전체 비벤치마크 regression | 4,836 passed, 6 skipped, 16 deselected |
| F01 실제 wire regression | 28 passed |
| benchmark suite 단독 실행 | 16 passed; 전체 실행 중 3.2s 변동 실패는 문서에 별도 기록 |
| 변경 파일 정적 검사 | ruff check/format 및 fresh basedpyright 0/0/0 통과 |

### 후속 F03 수정 검증

결과 요소, RED 실패 2건, 실제 build 산출물 CLI 출력은 [F03 진행 기록](remediation/F03-release-metadata-version.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| 릴리스/provenance 집중 regression | 29 passed |
| F01+F02/F07+F03 통합 집중 regression | 97 passed |
| 실제 `python -m build` | wheel/sdist 생성 성공, 배포하지 않음 |
| 실제 metadata CLI, tag `v0.1.0` | wheel/sdist/소스/태그 모두 0.1.0 일치 |
| 실제 metadata CLI, tag `v0.9.9` | exit 2, 태그 불일치 명시적 거절 |
| 실제 metadata CLI, branch ref | 태그 검증 없이 버전 검증 통과 |
| workflow YAML 파싱 | release.yml/ci.yml 모두 `yaml.safe_load` 통과 |
| 변경 파일 정적 검사 | ruff check/format 및 basedpyright 0/0/0 통과 |
| 전체 비벤치마크 regression | 4,847 passed, 6 skipped, 16 deselected |

### 후속 F05 수정 검증

결과 요약, 실제 build 출력, wheel/sdist member 목록, supply-chain manifest는 [F05 진행 기록](remediation/F05-release-sbom-notices.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| SBOM/notices 집중 regression | 6 passed |
| 릴리스/provenance 통합 집중 regression | 36 passed |
| 실제 generate → `python -m build` → verify | wheel/sdist 모두 세 release 문서 포함, 검증 통과 |
| 문서 변조 거절 | `python.cdx.json` 수정 후 verify exit 2 |
| workflow YAML 파싱 | release.yml/ci.yml 모두 `yaml.safe_load` 통과 |
| 변경 파일 정적 검사 | ruff check/format 및 basedpyright 0/0/0 통과 |
| 전체 비벤치마크 regression | 4,853 passed, 6 skipped, 16 deselected |
| 2026-09-03 hoisted npm latent regression | 실제 lock에서 20개만 반환하던 문제를 143 component closure로 수정. 실제 wheel/sdist 재검증 통과 |
| 후속 F05 집중 regression | [F05 기록](remediation/F05-release-sbom-notices.md)의 hoisted 재검증 절 참조, 8 passed |
| 후속 릴리스 관련 regression | 38 passed |
| 후속 실제 배포물 | [supply-chain manifest](../../../.omo/evidence/f05-hoisted-supply-chain.json), [build log](../../../.omo/evidence/f05-hoisted-build.log) |

### 후속 F04 수정 검증

결과 요약과 정확한 브라우저 시나리오는 [F04 진행 기록](remediation/F04-mutation-snapshot.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| Focused component/boundary test | 1 file, 2 tests passed |
| Mutation page lint | `eslint src/pages/MutationDashboardPage.tsx src/pages/MutationDashboardPage.test.tsx` exit 0 |
| Dashboard TypeScript build | `tsc -b --pretty false` exit 0 |
| Dashboard 전체 suite | 44 files, 598 tests passed |
| Production build | `pnpm --dir dashboard build`, 878 modules transformed |
| 실제 브라우저 QA | [browser-qa.json](../../../.omo/evidence/f04-mutation-qa/browser-qa.json), route `/mutation`, 375/768/1280px, filter/empty, malformed fail-closed, console error/warning 0 |
| Responsive screenshots | [375](../../../.omo/evidence/f04-mutation-qa/mutation-375.png), [768](../../../.omo/evidence/f04-mutation-qa/mutation-768.png), [1280](../../../.omo/evidence/f04-mutation-qa/mutation-1280.png) |
| 상태 screenshots | [filter empty](../../../.omo/evidence/f04-mutation-qa/mutation-filter-empty-1280.png), [invalid snapshot](../../../.omo/evidence/f04-mutation-qa/mutation-invalid-1280.png) |

F04는 사용자 명시 없는 sub-agent 금지 조건 때문에 visual-qa skill의 독립 reviewer 2인 게이트를 실행하지 않았다. 수동 실제 브라우저 QA와 fresh screenshot을 보존했으며, 전체 UI release 승인 전 독립 reviewer 실행이 남아 있다.

### 후속 F06 수정 검증

결과 요약, 권고별 분류, exact dependency path, 남은 ChromaDB optional residual은 [F06 진행 기록](remediation/F06-dependency-triage.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| 최초 project venv pip-audit | 43 findings / 11 packages. 전역 Python 감사 숫자는 폐기 |
| 최종 project venv pip-audit | 4 findings / 1 package. optional `rag` ChromaDB만 남음, fix 미출시 |
| pnpm dashboard production audit | exit 0, vulnerabilities 0 |
| npm dashboard production audit | exit 0 |
| Dashboard DOMPurify closure | Monaco 아래 포함 모든 경로 3.4.14 |
| Python 관련 집중 regression | 122 passed |
| Python 전체 비벤치마크 regression | 4,855 passed, 6 skipped, 16 deselected |
| Dashboard lint/typecheck/test/build | 모두 통과, 44 files / 598 tests |
| 격리 wheel/sdist SBOM 검증 | dashboard 143, Python 61 components, 세 release 문서 포함/verify 통과 |

주요 raw evidence: [final pip-audit](../../../.omo/evidence/f06-dependency-triage/pip-audit-final.json), [pnpm production audit](../../../.omo/evidence/f06-dependency-triage/dashboard-pnpm-audit-after-prod.json), [npm production audit](../../../.omo/evidence/f06-dependency-triage/dashboard-npm-audit-after-prod.json), [release supply-chain manifest](../../../.omo/evidence/f06-dependency-triage/release-supply-chain.json).

### 후속 F08 수정 검증

결과 요약, RED→GREEN 입력표, stale production bundle 실패, CSP 원문, tracked Vite runtime 문제는 [F08 진행 기록](remediation/F08-wiki-markdown-sanitization.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| Wiki adversarial component test | 수정 전 5 failed로 injection 재현, 수정 후 5 passed |
| Wiki + Chat focused regression | 2 files / 38 tests passed |
| Dashboard 전체 suite | 45 files / 603 tests passed |
| TypeScript / lint | 모두 exit 0 |
| Production build | 876 modules transformed, exit 0 |
| 실제 production browser E2E | [Playwright JSON](../../../.omo/evidence/f08-wiki-markdown-sanitization/playwright-security-e2e.json), 2 passed |
| 실제 Wiki UI screenshot | [wiki-security-safe.png](../../../.omo/evidence/f08-wiki-markdown-sanitization/wiki-security-safe.png), 1280×800 |
| CSP 원문 | [health-headers.txt](../../../.omo/evidence/f08-wiki-markdown-sanitization/health-headers.txt), 설정 변경 없음 |

### 후속 F09/F10 수정 검증

결과 요약, F10 RED 실패 전파, backend 격리/정리 상태는 [F09/F10 진행 기록](remediation/F09-F10-e2e-auth-hard-gate.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| Focused auth/command/chat | 15 passed |
| 기존 page-object/a11y/security/task suite | 44 passed |
| 전체 Playwright | 59 expected, 0 unexpected/skipped/flaky, exit 0 |
| Hard gate 실패 전파 | 의도적 실패 1건이 `set -o pipefail \| tee`에서 exit 1 |
| Dashboard TypeScript/lint | 모두 exit 0 |
| CI/release YAML strict parse | duplicate key 없음 |
| 임시 backend/상태 정리 | uvicorn 종료, `/tmp/agk-f09-noauth.*` 제거 |

주요 raw evidence: [전체 Playwright JSON](../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/playwright-full-before-ci-cleanup.json), [정규화 통계](../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/playwright-full-normalized.json), [실패 전파 로그](../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/hard-gate-failure-propagation.log), [파일 지문](../../../.omo/evidence/f09-f10-e2e-auth-hard-gate/metadata.json).

### 후속 F11 수정 검증

결과 요약과 RED→GREEN 해석은 [F11 진행 기록](remediation/F11-install-matrix.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| base+dev 격리 설치 | `chromadb=None` 확인 |
| base+dev 수정 전 | 1 failed, 34 passed, exit 1 |
| base+dev 수정 후 | 35 passed, exit 0 |
| base+dev 전체 비벤치마크 | 4775 passed, 8 skipped, 19 deselected, exit 0 |
| rag 환경 memory+RAG focused | 38 passed, exit 0 |
| CI matrix 정적 검증 | base/rag × ubuntu/macos 4조합, artifact 이름 일치 |

주요 raw evidence: [base RED](../../../.omo/evidence/f11-install-matrix/base-memory-service-red.log), [base GREEN](../../../.omo/evidence/f11-install-matrix/base-memory-service-green.log), [base 전체](../../../.omo/evidence/f11-install-matrix/base-full-suite.log), [rag focused](../../../.omo/evidence/f11-install-matrix/rag-memory-rag-green.log), [파일 지문](../../../.omo/evidence/f11-install-matrix/metadata.json).

### 후속 F12 수정 검증

결과 요약, 390px before/after bbox, 시행 착오와 독립 reviewer 한계는 [F12 진행 기록](remediation/F12-mobile-cjk-layout.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| 수정 전 실제 브라우저 재현 | `/plugins` card 340px로 overflow, `/data-extraction` 지표 label 세로 붕괴 |
| Mutation 재확인 | F04 이후 clipping 없음. 이번 수정 대상 아님 |
| Focused component tests | 2 files / 4 tests passed |
| TypeScript / lint / build | 모두 exit 0 |
| Dashboard 전체 suite | 45 files / 603 tests passed |
| 실제 브라우저 fresh capture | 8 routes × 390/768/1440px, console/page error 0 |
| Full Playwright E2E | 59 expected / 0 unexpected / 0 skipped / 0 flaky |

주요 raw evidence: [수정 전 PNG/DOM](../../../.omo/evidence/f12-mobile-cjk-layout/before/dom-measurements.json), [수정 후 PNG/DOM](../../../.omo/evidence/f12-mobile-cjk-layout/after/dom-measurements.json), [전체 Playwright JSON](../../../.omo/evidence/f12-mobile-cjk-layout/playwright-full.json).

### 후속 F13 수정 검증

결과 요약, 시행 착오, clean reproduction 환경은 [F13 진행 기록](remediation/F13-vscode-extension.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| 원본 재현 | compile 후 `eslint: command not found`, exit 127 |
| 현재 `npm test` | compile-tests/webpack/ESLint, Extension Host 4 passing, exit 0 |
| clean reproduction | 임시 복사 → `npm ci` → `npm test`, Extension Host 4 passing, exit 0 |
| VS Code dev audit | 0 vulnerabilities |
| 실제 시나리오 | command registration, offline, hanging timeout, 재연결, 파일/커서/열린 문서, 문서 변경, 60-event flood, stop |

주요 raw evidence: [현재 npm test](../../../.omo/evidence/f13-vscode-extension/npm-test.log), [clean install](../../../.omo/evidence/f13-vscode-extension/clean-install.log), [clean npm test](../../../.omo/evidence/f13-vscode-extension/clean-npm-test.log), [audit JSON](../../../.omo/evidence/f13-vscode-extension/npm-audit.json), [파일 지문](../../../.omo/evidence/f13-vscode-extension/sha256.txt).

### 후속 F14 수정 검증

결과 요약, SPDX 변형 및 엔트리포인트 AST 계약 검증, 격리 픽스처 상세는 [F14 진행 기록](remediation/F14-release-baseline.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| 원본 재현 | `# SPDX-License-Identifier: AGPL-3.0-only` 미거절 및 가상 커맨드 미탐지 확인 |
| 라이선스 검증기 regression | 23 passed (AGPL/GPL SPDX 리터럴, 풀네임, 변종 거절 및 Apache/MIT 허용) |
| 엔트리포인트 계약 검증 | CLI 서브커맨드 트리, ASGI app, HTTP 라우트, package.json 스크립트 계약 거절 4종 통과 |
| 격리 벤치마크 픽스처 | `tmp_path` 기반 복사본 검증으로 저장소 `data/benchmarks` 무변조 입증 |
| 연관 릴리스 검사 회귀 | `test_release_metadata.py` + `test_release_sbom.py` 19 passed |
| 정적 검사 | ruff check 통과, basedpyright 0/0/0 통과 |

### 후속 F15 수정 검증

결과 요약, 행동 기반 샌드박스/권한 검증 및 mypy 430개 소스 파일 전수 통과는 [F15 진행 기록](remediation/F15-static-and-behavioral-gates.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| 원본 재현 | 소스 문자열 단순 존재 검사 및 mypy 4 errors in 2 files 확인 |
| 행동 기반 샌드박스 검증 | `build_sandbox_argv` 실제 실행, returncode 0, `.sb` 파일 언링크 cleanup 통과 |
| Fail-Closed 거절 검증 | 샌드박스 백엔드 불가 시 raw 미우회, exit code -1, `raw execution is disabled` 반환 |
| OS 쓰기/네트워크 격리 | `/etc` 쓰기 불가(OS 수준 차단), `network="none"` 하 소켓 연결 불가 입증 |
| Auto-pilot 경계 계약 | `strict`/`balanced`/`auto-pilot` 모드 계약 및 위험 명령(`rm -rf /`, `curl \| bash`) 차단 입증 |
| 전체 샌드박스 스위트 | `test_sandbox.py` 등 4개 스위트 51 passed |
| 전체 mypy 정적 분석 | `mypy src/` 430개 소스 파일 0 errors 달성 |
| Basedpyright strict 게이트 | `sandbox.py` + `release_baseline.py` 0 errors, 0 warnings 통과 |

### 최종 전체 통합 검증 (2026-09-03)

결과 요약, Vite 청크 충돌 해결 및 E2E 전수 통과 상세는 [최종 통합 검증 기록](remediation/FINAL-INTEGRATION-VERIFICATION.md)에 직접 보존했다.

| 검사 | 결과 |
|---|---|
| 대시보드 청크 충돌 수정 | `rehype-sanitize`/`unified` 명시적 번들링으로 휠 내 duplicate `index.js` 해소 |
| 대시보드 휠 자산 검증 | `tests/test_dashboard_wheel_assets.py` 1 passed |
| Python 비벤치마크 전체 단위/회귀 | `pytest tests --ignore=tests/benchmarks` 4,890 passed, 0 failed, 6 skipped (182.95s) |
| 백엔드 라이브 스모크 | `tests/test_e2e_smoke.py` 9 passed (17.39s) |
| Playwright 브라우저 E2E 전체 | `playwright test --project=chromium` 59 passed, 0 failed (40.3s) |
| 배포 패키지 빌드 및 검증 | Wheel/SDist 생성 및 `release_metadata` + `release_sbom` verify 통과 |

### 최초 전체 QA

| 자료 | 링크 | 확정할 수 있는 것 |
|---|---|---|
| 전체 pytest 원문 | [pytest-final.log](../../../.omo/evidence/full-qa-2026-09-02/artifacts/pytest-final.log) | 4,790 passed / 1 failed / 11 skipped, ChromaDB 미설치 실패, coverage 76.69% |
| JUnit | [pytest-final.xml](../../../.omo/evidence/full-qa-2026-09-02/artifacts/pytest-final.xml) | 개별 테스트 결과와 실패 trace |
| 프로젝트 Python 감사 | [pip-audit-project.json](../../../.omo/evidence/full-qa-2026-09-02/artifacts/pip-audit-project.json) | base+dev 설치의 권고 버전, 실제 악용 가능성은 별도 |
| Dashboard npm 감사 | [npm-audit.json](../../../.omo/evidence/full-qa-2026-09-02/artifacts/npm-audit.json) | high 1/moderate 2 패키지 항목, dev/runtime 분류 필요 |
| VS Code build | [extension-build.log](../../../.omo/evidence/full-qa-2026-09-02/artifacts/extension-build.log) | webpack compile 성공 |
| VS Code test | [extension-test.log](../../../.omo/evidence/full-qa-2026-09-02/artifacts/extension-test.log) | pretest ESLint 미설치 실패 |
| 원래 Playwright 실패 목록 | [.last-run.json](../../../.omo/evidence/full-qa-2026-09-02/artifacts/original-playwright-results/.last-run.json) | 28개 실패 ID. 원인 판정은 후속 수동 QA와 함께 읽기 |

## 수동/API/브라우저 검사

- [수동 QA 시나리오 보고서](../../../.omo/evidence/full-qa-2026-09-02/hands-on-qa.md): 11 surface 및 4 adversarial 사례, valid PIN/실제 LLM 한계.
- [HTTP 원문](../../../.omo/evidence/full-qa-2026-09-02/api-scenarios.txt): health/models/path traversal/auth no-config 상태.
- [fresh/stale browser 관찰](../../../.omo/evidence/full-qa-2026-09-02/browser-stabilized.json): fresh state 정상, legacy PIN seed에서 auth 503.
- [탐색/팔레트](../../../.omo/evidence/full-qa-2026-09-02/browser-ui-scenarios.json), [탐색기 새로고침](../../../.omo/evidence/full-qa-2026-09-02/browser-explorer-refresh-stable.json).
- [fresh dashboard](../../../.omo/evidence/full-qa-2026-09-02/browser-no-seed-stable.png), [잘못된 legacy PIN lock](../../../.omo/evidence/full-qa-2026-09-02/browser-legacy-0000-stable.png).

## 화면 검토

- [42개 이미지 중 36개 기본 route manifest](../../../.omo/evidence/full-qa-2026-09-02/artifacts/visual/manifest.json).
- [capture summary](../../../.omo/evidence/full-qa-2026-09-02/artifacts/visual-capture.log).
- [Pass A: 실제 구현/기능/디자인 정합성](../../../.omo/evidence/full-qa-2026-09-02/visual-integrity.md).
- [Pass B: 화면/CJK 정밀 검토](../../../.omo/evidence/full-qa-2026-09-02/visual-cjk.md).
- 직접 결함 증거: [mobile Plugins](../../../.omo/evidence/full-qa-2026-09-02/artifacts/visual/mobile-plugins.png), [mobile Mutation](../../../.omo/evidence/full-qa-2026-09-02/artifacts/visual/mobile-mutation.png), [mobile extraction](../../../.omo/evidence/full-qa-2026-09-02/artifacts/visual/mobile-data-extraction.png), [mobile Chat](../../../.omo/evidence/full-qa-2026-09-02/artifacts/visual/mobile-chat.png).
- 기본 route는 12개 × 3개 viewport, 추가 palette/terminal은 6장. 모든 탭·모달·스크롤·motion state를 검사했다는 의미는 아니다.

## 독립 검토 및 정리

- [코드 품질 원본](../../../.omo/evidence/code_quality-code-review.md).
- [문서/릴리스 정합성](../../../.omo/evidence/full-qa-2026-09-02/context.md).
- [이전 완료 lane 복구 기록](../../../.omo/evidence/full-qa-2026-09-02/recovered-lanes.md).
- [환경 정리 기록](../../../.omo/evidence/full-qa-2026-09-02/cleanup.md).

## 해석할 때 주의

1. 전역 Python을 잘못 감사한 최초 숫자는 사용하지 않는다. 보존된 project audit는 site-packages 범위를 명시했다.
2. Wiki raw HTML은 렌더링됐지만 기본 CSP가 inline onerror를 차단했다. script 실행/credential 탈취가 입증된 보고서가 아니다.
3. 원래 Playwright 실패는 invalid legacy PIN fixture와 no-auth 서버의 불일치가 주요 원인이다. 후속 fresh browser 검사에서 정상 동작을 확인했다.
4. Python 실패 하나는 optional rag 의존성 계약 문제다. 서로 다른 설치 조건의 test count를 합산하거나 통과 결과로 덮지 않는다.
5. 알려진 취약 버전과 실제 exploitability, source inspection과 live reproduction, mocked UI와 real integration을 구별한다.
6. 이전 reviewer가 참조한 `/tmp/agk-qa.2EdSb0/visual`의 원본은 정리됐고 같은 파일명으로 `artifacts/visual`에 보존했다. 해당 경로 문자열 자체를 현재 실행 환경으로 사용하지 않는다.
