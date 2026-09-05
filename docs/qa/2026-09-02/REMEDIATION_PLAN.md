---
title: Ssak-Ai QA 수정 인수인계 및 재승인 계획
tags: [qa, remediation, agent-handoff, acceptance-tests]
date: 2026-09-02
reviewed_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: open
---

# 수정 에이전트 인수인계

이 문서는 실제 수정 작업을 시작할 수 있는 작업 지시서다. **F01 인증 누락**, **F02/F07 Vault Git 트랜잭션**, **F03 릴리스 버전 원천**, **F04 Mutation historical snapshot 정합성**, **F05 배포물 기반 SBOM/notices**, **F06 의존성 권고 triage**, **F08 Wiki Markdown 안전화**, **F09/F10 E2E 인증 fixture와 hard gate**, **F11 설치 matrix**, **F12 모바일/한국어 UI**, **F13 VS Code 확장**, **F14 release-baseline 검증기**, **F15 정적 검사와 행동 기반 보안 테스트** 수정·검증을 완료했다. [F01 진행 기록](remediation/F01-workspace-websocket-auth.md), [F02/F07 진행 기록](remediation/F02-F07-vault-git-transaction.md), [F03 진행 기록](remediation/F03-release-metadata-version.md), [F04 진행 기록](remediation/F04-mutation-snapshot.md), [F05 진행 기록](remediation/F05-release-sbom-notices.md), [F06 진행 기록](remediation/F06-dependency-triage.md), [F08 진행 기록](remediation/F08-wiki-markdown-sanitization.md), [F09/F10 진행 기록](remediation/F09-F10-e2e-auth-hard-gate.md), [F11 진행 기록](remediation/F11-install-matrix.md), [F12 진행 기록](remediation/F12-mobile-cjk-layout.md), [F13 진행 기록](remediation/F13-vscode-extension.md), [F14 진행 기록](remediation/F14-release-baseline.md), [F15 진행 기록](remediation/F15-static-and-behavioral-gates.md)에 구현·재현·검증 한계를 남긴다. [REPORT.md](REPORT.md)의 최초 진단과 후속 수정 상태를 구별하며, SHA뿐 아니라 미커밋 파일 지문도 확인한다.

## 시작할 때 반드시 확인

1. 루트 `AGENTS.md`와 작업 경로의 추가 지침을 읽는다. 코드 탐색은 codebase-memory 그래프를 우선한다. 필요한 programming/debugging/frontend/visual-qa 등의 skill을 해당 작업 범위에서 적용한다.
2. `git rev-parse HEAD`, `git status --short`, `git diff --stat`를 기록한다. 이번 검토 기준은 `6d0a24d4e6a0686693ce29a4d13a69443ae5149b`다. HEAD가 다르면 이 문서를 현재 사실로 가정하지 않는다.
3. 검토 시작 전부터 `data/benchmark_results.json`에 사용자 변경이 있었다. 이를 되돌리거나 자동 포맷하거나 임의로 커밋하지 않는다. 그 외 새 변경도 작성 주체를 추측해 삭제하지 않는다.
4. QA용 `/tmp/agk-qa.2EdSb0/repo`와 포트 18112 서버는 정리됐다. 해당 경로/포트를 살아 있는 환경으로 사용하지 말고 새 격리 checkout/worktree와 빈 포트를 마련한다. 같은 노트 저장소·설정·브라우저 저장소를 사용자 환경과 공유하지 않는다.
5. 생성물과 `node_modules` 일부가 tracked 상태다. 패키지 설치/build/test는 가급적 격리 환경에서 수행하고, 원본에 생긴 생성물 변경을 제품 수정으로 섞지 않는다. 임시 worktree에서 root node_modules를 symlink하지 않는다.
6. 비밀값을 찾거나 새 외부 공개 설정을 만들지 않는다. 인증 테스트에는 격리 환경의 테스트 자격 증명만 사용한다. 실제 provider 과금·배포·공개 서비스 노출은 별도 권한이 필요한 작업이다.

## 완료 정의

- 해당 결함이 수정 전 실제로 재현되고, 수정 후 같은 입력에서 기대 상태가 관찰된다.
- 테스트를 삭제/완화하거나 예외를 무시하거나 고정 응답으로 바꾸어 통과시키지 않는다.
- 대상 파일과 관련 호출자를 검증하고, 중요한 경계는 실제 HTTP/WS/browser/Git surface로 확인한다.
- 전체 suite의 기존 실패와 새 실패를 구분해 기록한다. 서로 다른 환경의 통과 수를 합산하지 않는다.
- UI 작업은 정확한 viewport와 충분한 상태의 fresh screenshot을 남긴다. source diff만 보고 완료라고 하지 않는다.
- 증거에는 full SHA, 환경/설치 extras, 정확한 명령, exit code, 예상/실제 결과, artifact 경로를 남긴다.
- 코드·테스트·문서·마이그레이션 및 실패 복구가 모두 일치해야 해당 이슈를 CLOSED로 바꾼다.

## 우선순위 / 작업 소유권

서로 다른 에이전트를 병렬 사용한다면 아래 파일 소유권을 먼저 배정한다. 동일 파일은 한 에이전트만 수정하며, 다른 작업자의 변경을 되돌리지 않는다. 계획 자체는 에이전트 실행이나 외부 배포를 이미 수행했다는 뜻이 아니다.

| 트랙 | 이슈 | 단독 소유 파일/책임 | 의존성·충돌 |
|---|---|---|---|
| A: WS 보안 | F01 | workspace_services.py, 공통 WS auth와 관련 tests | E2E 트랙과 인증 contract 공유 |
| B: Vault 정합성 | F02, F07 | vault.py, Vault 트랜잭션 테스트 | 두 이슈를 한 소유자가 함께 처리 |
| C: 릴리스 | F03, F05, F14 | release.yml, release_baseline.py, release policy/패키징 | ci.yml은 통합 담당자와 조정 |
| D: 의존성/품질 게이트 | F06, F11, F15 일부 | pyproject.toml, uv.lock, package lock, dev install matrix | lockfile/CI 변경을 한 담당자에게 집중 |
| E: E2E | F09, F10 | dashboard/e2e, CI 테스트 단계 | A의 auth contract, D의 설치 matrix 이후 최종 검증 |
| F: HTML 안전성 | F08 | Wiki MarkdownRenderer/ContentPanel과 보안 테스트 | 공통 Markdown primitive를 바꾸면 Chat regression 필요 |
| G: 화면/정보 | F04, F12 | MutationDashboardPage, index.css, metrics/화면 layout | 공용 CSS는 단독 소유; 다른 UI 작업과 조정 |
| H: IDE 확장 | F13 | vscode-extension 전체 개발/테스트 계약 | backend sync contract는 읽기 협의 후 최소 변경 |

권장 순서: A/B/C 착수 → D/F → E의 실제 통합 검증 → G/H → 통합 재승인. C와 D/E가 `.github/workflows/ci.yml` 또는 manifests를 동시에 수정하지 않도록 hunk 소유권을 분리하거나 순차 적용한다.

## 이슈 상태표

| ID | 현재 상태 | 심각도 | 완료 전 필요한 증거 |
|---|---|---|---|
| F01 | VERIFIED FIXED (인증 누락) | P1 | 집중/wire 28·회귀 4827 통과, 독립 검토 승인. ACL/Origin 강화 별도 |
| F02 | VERIFIED FIXED (무관 staged 커밋) | P1 | 집중/API/프로세스 테스트로 노트만 커밋·사용자 index 보존 확인 |
| F03 | VERIFIED FIXED (릴리스 버전 원천) | P1 | 실제 build 산출물로 wheel/sdist/소스/태그 일치 및 mismatch rejection 확인. [F03 기록](remediation/F03-release-metadata-version.md) |
| F04 | VERIFIED HISTORICAL SNAPSHOT (사용자에게 명시) | P1 | Zod 검증 snapshot, provenance/시각/SHA/stale/invalid 상태, 375/768/1280px 실제 브라우저 QA. [F04 기록](remediation/F04-mutation-snapshot.md) |
| F05 | VERIFIED FIXED (hoisted npm latent regression 포함) | P1 | 실제 wheel/sdist의 세 release 문서 byte 일치, 변조 거절, 실제 lock 143 component closure. [F05 기록](remediation/F05-release-sbom-notices.md) |
| F06 | VERIFIED FIXED / OPTIONAL RESIDUAL DOCUMENTED | P1 | base runtime과 dashboard production audit 0건, Python 전체 4,855 passed, 실제 wheel/sdist 재검증. optional rag ChromaDB 4건은 fix 미출시로 명시적 residual |
| F07 | VERIFIED FIXED (실패 상태 계약) | P2 | hook 실패 시 파일 보존, 사용자 index/HEAD 불변, 오류 출력 보존 |
| F08 | VERIFIED FIXED (Wiki Markdown 안전화) | P2 | raw HTML/event/unsafe URL 비활성, 실제 production browser E2E, CSP 유지, dashboard 603 tests. [F08 기록](remediation/F08-wiki-markdown-sanitization.md) |
| F09 | VERIFIED FIXED (E2E 인증 fixture) | P2 | no-auth/invalid PIN/valid PIN/expired token 실제 UI 검증, 전체 Playwright 59 expected |
| F10 | VERIFIED FIXED (E2E hard gate) | P2 | 전체 suite hard gate, `set -o pipefail \| tee` 실패 전파 exit 1 관찰. 실제 GitHub Actions 실행은 별도 |
| F11 | VERIFIED FIXED (base/rag 설치 matrix) | P2 | base+dev 전체 4775 passed, rag focused 38 passed, CI 4조합 계약 반영. 실제 Actions 실행은 별도 |
| F12 | VERIFIED FIXED (모바일 clipping/CJK 가독성) | P2 | 플러그인 toggle/카드 390px 완전 노출, 지표 label 세로 붕괴 제거, 8 route × 3 viewport fresh capture, Playwright 59 expected. 독립 visual reviewer는 미실행 한계로 남음 |
| F13 | VERIFIED FIXED (확장 개발/테스트 계약) | P2 | clean `npm ci` 후 lint/compile/test와 실제 Extension Host 4 시나리오 통과. Linux/Windows runner와 marketplace packaging은 별도. [F13 기록](remediation/F13-vscode-extension.md) |
| F14 | VERIFIED FIXED (검증기 사각지대 해소) | P2 | AGPL/GPL SPDX 리터럴/풀네임/변종 거절, 허용 텍스트 무영향, 엔트리포인트 계약(CLI/HTTP/서버/WebUI) 거절, 격리 벤치마크 23건 통과. [F14 기록](remediation/F14-release-baseline.md) |
| F15 | VERIFIED FIXED (행동 보안 실증·mypy 430개 통과) | P2 | sandbox argv/fail-closed/권한 거절/cleanup 행동 검증, auto-pilot 위험 명령 차단 입증, mypy 전체 430 파일 0 errors, Basedpyright 통과. [F15 기록](remediation/F15-static-and-behavioral-gates.md) |

## F01 — Workspace WebSocket 인증

**파일:** `src/antigravity_k/api/routes/workspace_services.py:312,329`, `api/server.py:412`; 비교 대상 `api/routes/events.py`의 `close_unauthorized_ws` 사용.

**최초 근거:** 기준 SHA의 `_proxy_websocket`이 `_require_ready` 후 인증 없이 accept/connect했다. HTTP middleware는 WebSocket scope를 처리하지 않는다. 후속 격리 echo 테스트로 두 경로의 무인증 도달을 재현하고 수정했다. 최신 상태와 파일 위치는 [F01 진행 기록](remediation/F01-workspace-websocket-auth.md)을 참조한다. 실제 운영 서비스 침해나 데이터 탈취를 수행한 것은 아니다.

**재현 시나리오:**

1. 격리 서버에 테스트 인증을 활성화하고, 테스트용 loopback echo WS 서비스를 registry에 ready로 등록한다.
2. 같은 서비스 HTTP proxy가 무자격 요청을 거절하는지 확인한다.
3. `/.../{hostname}/ws` 및 `/{hostname}/ws/{path}`의 실제 route prefix를 router 선언에서 확인하고, 자격 없는 WS handshake를 시도한다.
4. 수정 전 accept/upstream 도달 여부와 수정 후 거절을 비교한다. 실서비스/사용자 프로세스에는 연결하지 않는다.

**구현 계약:** 공통 auth helper 재사용, **서비스 조회·upstream 연결 전 인증 완료**. 기존 helper가 accept 후 4401 close를 보내므로 원래 계획의 “accept 전”은 이 실제 계약으로 정정한다. query `token`/`pin`은 모두 upstream에서 제거하며 업무용 query와 metadata는 보존한다. 보호를 끄는 새 fallback은 만들지 않았다.

**이번 수정 Acceptance:** 두 경로 무토큰·오류/만료 토큰·오류 PIN/subprotocol은 4401 및 upstream 연결 없음. 인증된 unknown/not-ready service는 1008. 유효 토큰/PIN/subprotocol은 text/binary 왕복, query 자격 증명 제거, 정상 종료1000/연결 오류1011, client disconnect cleanup이 정상이다. 다른 authenticated WS route의 회귀를 검사한다.

**별도 강화 항목:** 서비스별 ACL 및 Origin allowlist 신설은 기존 공통 정책을 바꾸는 작업이라 이번 인증 누락 수정에 포함하지 않았다. 원래 계획의 잘못된 Origin 거절 조건은 미구현/미검증으로 남으며 F01 인증 누락 해소를 그 조건까지 완료한 것으로 해석하지 않는다.

## F02 + F07 — Vault 파일/Git 트랜잭션

**현재 상태:** 수정·검증 완료. 구체적인 구현·계약·한계는 [F02/F07 진행 기록](remediation/F02-F07-vault-git-transaction.md)을 따른다.

**파일:** `src/antigravity_k/engine/vault.py:186,207,222,482,502` 및 관련 Vault 테스트.

**현재 근거:** 대상만 add하지만 전체 index를 commit한다. file write/fsync 후 commit 실패가 나면 파일 변경이 남는다.

**안전한 재현:** 빈 임시 저장소에서만 수행한다. 초기 커밋을 만들고 `unrelated.md` 변경을 stage한다. VaultEngine으로 `note.md`를 저장한 후 `git show --name-only HEAD`와 `git diff --cached`를 비교한다. 별도 케이스에서는 임시 failing pre-commit hook 또는 git subprocess 실패 double을 사용해 commit 오류를 만든다. root 저장소의 index나 hook을 바꾸지 않는다.

**수정 시 결정해야 할 계약:**

- 대상 노트만 커밋하면서 기존 index, staged+unstaged가 섞인 상태를 보존하는 방법.
- 신규/기존 파일, rename/delete, 동일 내용 no-op, conflict 상태의 동작.
- commit 실패 시 rollback을 할지, 복구 가능한 partial-write 상태를 명시적으로 반환할지. 현재 API의 성공/실패 의미와 함께 결정한다.
- Git commit 전에 관찰 가능한 파일 내용 및 다른 프로세스의 파일 접근. lock 밖 RAG/Wiki/event 동기화 순서와 실패 처리가 일치해야 한다.

**Acceptance:**

1. unrelated staged 파일은 신규 노트 커밋에 포함되지 않고 원래 staged 상태를 유지한다.
2. 노트의 기존 staged/unstaged 상태가 데이터 손실 없이 처리된다.
3. git add/commit 실패, hook 실패, lock timeout에서 파일·index·HEAD 상태가 정의된 계약과 일치한다.
4. no-op과 진짜 실패가 구별되며, stdout의 임의 문자열만으로 실패를 성공 처리하지 않는다.
5. thread/process 동시 저장과 RAG/Wiki sync 실패에서 중복·유실·부분 성공이 관찰 가능하다.

**주의:** `git reset --hard`, root index reset, 사용자 staged 파일의 unstage로 해결하지 않는다. 실제 데이터 migration이 필요하면 사전 백업/복구 계획을 별도 제시한다.

## F03 — 릴리스 버전 원천 통일

**파일:** `.github/workflows/release.yml:93`, `pyproject.toml:7,124`.

**재현:** 아래 조회는 파일을 수정하지 않으며 현재 기준 SHA에서는 KeyError가 난다.

```bash
uv run --no-sync python -c "from pathlib import Path; import tomllib; print(tomllib.loads(Path('pyproject.toml').read_text('utf-8'))['project']['version'])"
```

**수정 방향:** wheel METADATA 또는 authoritative package version을 사용한다. 단순히 TOML에 같은 버전을 중복 기입하는 방식은 피한다. tag와 version이 달라질 때 명시적으로 실패시킨다.

**Acceptance:** 실제 배포 workflow의 동일 명령이 성공한다. wheel/sdist/tag/provenance version 일치와 mismatch rejection을 검사한다. 테스트를 위해 PyPI 업로드나 실제 release 발행은 하지 않는다.

## F04 — Mutation 정보의 진실성

**파일:** `dashboard/src/pages/MutationDashboardPage.tsx:26,451`.

**재현:** Mutation 화면의 현황 수치와 `STORES` 상수를 대조한다. 코드/실제 mutation report를 변경해도 화면 값이 바뀌지 않는 경로임을 확인한다.

**제품 결정:** 실시간 기능이 실제 요구라면 현재 report ingest/API와 freshness를 연결한다. 아니라면 dated historical snapshot 또는 demo라고 명확히 표시한다. 관련 backend를 무조건 새로 만드는 것이 최소 수정이라고 가정하지 않는다.

**Acceptance:** 값의 원본, 실행 시각, full SHA, stale/no-report/error 상태가 구분된다. 데이터가 없거나 outdated일 때 PASS를 표시하지 않는다. filter/summary 계산도 같은 report에서 나온다. 고정 숫자를 expected로 복사한 테스트는 실시간 연동 증거가 아니다.

**현재 상태:** 수정·검증 완료. 제품 결정은 “실시간 CI 위장 제거”다. 화면은 `dashboard/src/data/mutation-snapshot.json`의 historical snapshot만 소비하고, 원본/commit/측정 시각/capture 시각/scope/stale/invalid를 구분해 표시한다. 실시간 report ingestion은 범위 밖으로 남아 있으며 상세 계약·브라우저 증거는 [F04 진행 기록](remediation/F04-mutation-snapshot.md)을 따른다.

## F05 — 배포물 기반 SBOM/notices

**파일:** `.github/workflows/ci.yml:618`, `.github/workflows/release.yml:46`, `setup.py`, `pyproject.toml` package-data, `docs/RELEASE_POLICY.md:19`.

**재현:** CI SBOM job이 설치한 패키지와 출력 inventory를 비교한다. 현재는 cyclonedx 도구 환경이며 제품의 두 lockfile을 사용하지 않는다. release archive 안에 정책의 SBOM/notices가 실제 포함되는지 검사한다.

**수정 방향:** Python/dashboard 각각 lockfile에서 resolved version과 provenance를 얻고 최종 wheel/번들 내용에 맞게 생성한다. 빌드 도구와 제품 런타임을 구분한다. 법률 판단이나 license allowlist 변경은 근거 없이 하지 않는다.

**Acceptance:** 깨끗한 build에서 생성되고, 모든 직접/전이 의존성의 범위와 버전이 추적된다. 도구 환경만 담긴 SBOM은 실패한다. 생성 파일이 release artifact에 포함되며 checksum/provenance와 연결된다. 선택 extras의 범위는 명시한다.

## F06 — 의존성 권고 triage

**현재 상태:** 수정·검증 완료. Python base runtime, optional extras, dev tooling, dashboard pnpm/npm runtime closure를 구분해 갱신하고 전체 회귀/배포 검증을 수행했다. 자세한 권고 표, pnpm 11 override 함정, 남은 ChromaDB residual은 [F06 진행 기록](remediation/F06-dependency-triage.md)을 따른다.

**원본:** `.omo/evidence/full-qa-2026-09-02/artifacts/pip-audit-project.json`, `npm-audit.json`.

**검토 당시 대상:** cryptography 48.0.0, mcp 1.27.1, pydantic-settings 2.14.1, pytest 8.4.2, python-multipart 0.0.29, starlette 1.1.0. Node는 browserslist/qs/typed-rest-client 항목. 권고 DB는 변하므로 현재 advisory를 다시 확인한다.

**작업 순서:**

1. **실제 프로젝트 interpreter/site-packages/lockfile** 대상임을 먼저 검증한다. 기본 pip-audit가 전역 Python을 가리킨 시행착오가 있었다.
2. 권고 ID별 affected version·fix version·runtime/dev·실제 호출 경로·공격 전제를 표로 작성한다.
3. 상위 버전 제한과 compatibility를 함께 검토한다. cryptography `<50`, pytest `<9` 같은 제한이 수정 버전 선택을 막을 수 있다.
4. manifests와 해당 lockfile을 같은 소유자가 갱신한다. 서로 다른 npm/pnpm lock의 실제 사용 계약도 확인한다.
5. 각 업데이트에 최소 관련 회귀 테스트와 전체 smoke를 실행한다. 정당한 예외가 필요하면 근거·owner·만료일을 기록한다.

**Acceptance:** 무조건 모든 audit 결과를 숨기지 않는다. 해결/비노출/잔존 예외가 구별되고 runtime 공격면의 고위험 권고가 닫힌다. dev-only 권고를 그대로 프로덕션 원격 취약점이라고 보고하지 않는다.

## F08 — 안전한 Wiki Markdown

**현재 상태:** 수정·검증 완료. raw HTML은 parser와 sanitizer 이중 경계에서 거부되며, 실제 production bundle의 `/wiki` route에서 script/iframe/SVG/event handler/unsafe URL이 생성되지 않고 한국어 Markdown 문법이 유지됨을 확인했다. 구현 계약, stale bundle 재현, tracked Vite runtime 문제는 [F08 진행 기록](remediation/F08-wiki-markdown-sanitization.md)을 따른다.

**파일:** `dashboard/src/pages/wiki/MarkdownRenderer.tsx:8`, `ContentPanel.tsx:107`; Chat의 기존 Markdown 정화 경로 참고.

**현재 확인:** 실제 Wiki GET 응답만 합성해서 `<h2 id="qa-injected">`와 무해한 onerror marker를 넣었을 때 raw HTML은 렌더링됐으나 기본 CSP가 inline script를 차단했다. 기본 배포 토큰 탈취/스크립트 실행 성공은 입증되지 않았다.

**수정 방향:** 기존 안전한 Markdown component/sanitizer 재사용. 허용 tags/attributes와 URL scheme을 경계에서 제한한다. 정규식 치환을 추가하는 것만으로 HTML sanitizer를 대체하지 않는다. CSP를 약화시키지 않는다.

**Acceptance:** raw HTML/event handler, javascript/data URL, SVG, 링크 속성 breakout 등 합성 입력이 active DOM을 만들지 않는다. 일반 heading/list/code/table/링크와 한국어는 유지된다. 제품 UI에서 document를 열어 확인하고, CSP 유지 및 Chat 회귀를 검증한다. 테스트 중 credential이나 파일을 외부로 전송하지 않는다.

## F09 — E2E 인증 fixture 복구

**파일:** `dashboard/e2e/pages/DashboardPage.ts:140`, `dashboard/playwright.config.ts`, auth setup/fixtures, `api/auth_routes.py:179`.

**재현:** PIN hash 없는 loopback 서버에서 fresh browser는 정상이다. 같은 페이지를 localStorage `ag_access_pin=0000`과 함께 열면 `/api/auth/login` 503 후 잠금 상태가 된다. 이를 제품 네비게이션 실패와 구분한다.

**수정 방향:** no-auth fixture에는 임의 credential을 넣지 않는다. auth-enabled fixture는 테스트 서버의 실제 login API로 얻은 storage state를 사용한다. legacy migration 테스트는 별도 시나리오로 남긴다. 인증을 전부 mock/disable하는 방식으로 보안 테스트를 대체하지 않는다.

**Acceptance:** clean/no-auth, valid configured PIN, invalid PIN, stale legacy PIN, expired token, reload 후 상태가 각각 검증된다. 상태 누수가 없고 병렬 worker끼리 자격 증명을 공유해 경합하지 않는다. 이후 53개 기존 대상뿐 아니라 현재 discover된 전체 E2E를 실행하고 실제 pass/fail/skipped를 보존한다.

## F10 — 의미 있는 E2E와 실패 전파

**파일:** `.github/workflows/ci.yml:542`, `Makefile:210`, `dashboard/e2e/tests/chat.spec.ts`, command-palette/task-execution tests.

**수정 방향:**

- 실제 LLM/provider 계약 검증과 deterministic mocked UI 검증을 분리한다.
- 채팅 오류 bubble, empty response, stopped stream을 정상 완성 응답과 구분한다.
- Cmd+K/Control+K는 실제 키 입력으로 검증한다. 버튼 fallback이 키보드 검증을 대신하지 않게 한다.
- task submit→progress→terminal 상태→artifact/Git 결과까지 관찰한다. mock된 API 성공만으로 통합 성공이라 하지 않는다.
- 핵심 suite를 hard gate로 승격하되, 외부 서비스 불가 시 skip/blocked 사유가 CI에 명확히 드러나게 한다.
- shell pipeline의 exit code와 보안 도구의 nonzero를 보존한다.

**Acceptance:** 의도적인 실패 fixture가 CI/job을 실패시키는 것도 검증한다. 접근성만 통과한 상태를 전체 E2E green으로 표시하지 않는다. 재시도 후 flaky pass는 별도 보고한다.

## F11 — 선택 의존성/설치 matrix

**파일:** `tests/test_memory_service.py:120`, `pyproject.toml` dev/rag extras, CI install steps, 개발 가이드.

**재현:** base+dev 설치에서 전체 tests를 실행하면 `VectorStore requires chromadb ... ModuleNotFoundError`를 경유해 assertion 하나가 실패한다.

**결정:** dev만으로 전 테스트 실행을 보장하려면 해당 test용 의존성을 계약에 포함한다. optional 기능임을 유지한다면 base-mode 기대 동작을 테스트하고 rag 통합 테스트를 별도 matrix에서 필수 실행한다. 단순 전체 skip으로 검증을 없애지 않는다.

**Acceptance:** base+dev의 keyword-only 경로와 rag 설치의 vector 경로가 모두 실행된다. skip 사유가 의도한 optional 경계에만 적용된다. `uv run`이 extras를 재동기화하는지 확인하고, 설치 후 검증에서는 의도한 환경을 유지한다.

## F12 — 모바일 clip과 한국어 가독성

**파일:** `dashboard/src/styles/index.css:6816`, `MutationDashboardPage.tsx:146`, `pages/dex/MetricsBar.tsx:16`, `components/shared/MetricItem.tsx:16`, 관련 prose/layout.

**Viewport:** desktop 1440×900, tablet 768×1024, mobile 390×844. 추가로 지원 최소 폭을 제품 contract에서 확인한다.

**재현:** `/plugins` toggle 오른쪽, `/mutation` badge/경로, `/data-extraction` 지표 라벨을 본다. `document.scrollWidth <= viewport`여도 overflow hidden 내부에서 잘릴 수 있으므로 screenshot과 control bounding box를 함께 확인한다.

**수정 방향:** grid min-width/flex shrink/wrapping을 컨테이너 기준으로 수정한다. 글자를 무조건 작게 만드는 것으로 해결하지 않는다. Korean-aware word wrapping과 긴 식별자의 overflow 정책을 분리한다. 긴 경로는 접근 가능한 전체 내용 확인 경로를 제공한다.

**Acceptance:** 모든 control이 보이고 클릭/키보드 focus 가능하다. badge/metric 의미가 유지되며 한 음절씩 세로로 붕괴하지 않는다. 12 routes의 기본 상태와 실제 변경한 탭·모달·스크롤·motion 상태를 fresh capture로 검증한다. 정상 PC/tablet 레이아웃과 접근성을 회귀 검사한다. 두 독립 visual reviewer에게 현재 SHA/캡처를 제공한다.

**현재 상태:** 수정·검증 완료. 원본 3개 결함 중 `/plugins`, `/data-extraction`은 현재 production에서 재현 후 수정했다. `/mutation` clipping은 F04 구조 변경으로 이미 사라져 있었고 이번에는 무회귀만 확인했다. 상세 구현, 390px bbox before/after, 59건 E2E, 독립 reviewer 미실행 한계는 [F12 진행 기록](remediation/F12-mobile-cjk-layout.md)을 따른다.

## F13 — VS Code 확장 개발/테스트 계약

**파일:** `vscode-extension/package.json:33,36`, tsconfig/webpack/test runner 및 src/extension.ts.

**재현:** 깨끗한 설치 후 `npm test`: compile 성공 후 `eslint: command not found`. `npm run compile`만 성공한다고 확장 기능을 승인하지 않는다.

**수정 방향:** lint 의존성과 설정을 명시하고 실제 `out/test/runTest.js` runner 존재/생성 경로를 확인한다. 기재된 command contribution과 실제 registration도 대조한다. 기존 backend sync endpoint contract, HTTP response 소비, 오류/timeout 처리는 실제 Extension Host 사용으로 검증한다.

**Acceptance:** clean npm ci/compile/lint/test가 독립 실행된다. Extension Host에서 활성화→파일 변경→selection 변경→backend 상태 반영→서버 오프라인→재연결→deactivate를 테스트한다. 입력 이벤트 flood와 timeout도 점검한다. 테스트 scripts를 제거하여 통과시키지 않는다.

**현재 상태:** 수정·검증 완료. 상세 구현, 원본 실패 재현, clean install/Extension Host E2E, timeout/offline/재연결/flood/deactivate 증거와 한계는 [F13 진행 기록](remediation/F13-vscode-extension.md)을 따른다.

## F14 — release-baseline 검증기

**현재 상태:** 수정·검증 완료. AGPL/GPL 리터럴 및 헤더/풀네임/대소문자 변형 전수 거절, 허용 라이선스 및 유사 식별자 거짓 양성 방지, CLI/Server/HTTP-API/Web-UI 엔트리포인트 AST 계약 검증, 저장소 미변조 격리 벤치마크 23건 테스트가 검증됐다. 상세 구현과 증거는 [F14 진행 기록](remediation/F14-release-baseline.md)을 따른다.

**파일:** `src/antigravity_k/engine/release_baseline.py:86,112`, `tests/test_release_baseline.py`, `THIRD_PARTY_PROVENANCE.toml`, `docs/RELEASE_POLICY.md`.

**재현:** 실제 baseline과 scanner에 non-symlink file의 `# SPDX-License-Identifier: AGPL-3.0-only`를 합성 입력으로 전달하면 현재 거절하지 않는다. entrypoint는 command/name을 없애도 source file이 남으면 해당 존재 검사로는 탐지할 수 없다.

**Acceptance:** 정책에 선언된 SPDX literal/long-form 표기, 대소문자/정상 허용 텍스트/경계 입력의 false positive를 검증한다. source path뿐 아니라 실제 command/export contract도 확인한다. 테스트가 tracked 정책 파일을 일시 변조해서 다른 병렬 테스트에 영향을 주지 않도록 fixture copy를 사용한다. 정책 자체를 약화시켜 통과시키지 않는다.

## F15 — 정적 검사와 행동 기반 보안 테스트

**현재 상태:** 수정·검증 완료. `test_tool_sandbox_coverage.py`에 실제 `sandbox-exec` argv 실행 및 `.sb` 프로파일 cleanup, 샌드박스 불가 시 fail-closed(에러 반환 및 raw 미폴백), 파일시스템 쓰기 차단 및 네트워크 격리(network=none), auto-pilot 모드 하 위험 명령 및 시스템 경로 차단 실증을 추가했다(51개 전체 샌드박스 테스트 통과). `vault_git.py`와 `release_sbom.py`의 mypy 오류를 수정하여 전체 430개 소스 파일에서 `mypy src/` 0 errors 및 Basedpyright 통과를 달성했다. 상세 구현과 증거는 [F15 진행 기록](remediation/F15-static-and-behavioral-gates.md)을 따른다.

**파일:** pyproject/CI 타입·formatter 설정, 대형 모듈의 실제 경계, `tests/test_tool_sandbox_coverage.py`, terminal/permission gate 경로.

**재현:** `ruff check`는 통과하지만 format check는 167 files 실패. mypy 성공에는 untyped body 미검사 영역이 있고, Basedpyright CI는 두 파일만 검사한다.

**수정 방향:** formatter 변경은 기능 변경과 분리하고, 사용자 dirty 파일은 건드리지 않는다. 전체 typecheck 범위를 명시적으로 늘리되 환경 오류·제3자 stub·실제 boundary 오류를 분리한다. 한 번에 159개 대형 모듈을 기계적으로 쪼개지 말고 실제 수정이 필요한 경계부터 줄인다.

**Acceptance:** sandbox available/unavailable/권한 거절/cleanup을 실제 실행 argv와 반환 상태로 검증한다. 소스 문자열 존재나 allowlist 이름만으로 enforcement를 인증하지 않는다. auto-pilot의 허용 범위는 제품 정책으로 명시하고 다른 모드의 approval 계약을 침범하지 않는지 검사한다.

## 재검증 명령 모음

아래는 새 격리 checkout에서 실행한다. 명령은 source/정책 변경 후 현재 package scripts와 대조한다. 첫 줄의 HEAD/status를 증거에 포함한다. 임시 경로·포트는 새로 선택한다.

```bash
git rev-parse HEAD
git status --short
uv sync --frozen --extra dev
uv run --no-sync ruff check src tests scripts
uv run --no-sync ruff format --check src tests scripts
uv run --no-sync mypy src
uv run --no-sync basedpyright src/antigravity_k
uv run --no-sync pytest tests -q --cov=src/antigravity_k --cov-report=term --junitxml=qa-pytest.xml
pnpm --dir dashboard install --frozen-lockfile
pnpm --dir dashboard lint
pnpm --dir dashboard typecheck
pnpm --dir dashboard exec vitest run
pnpm --dir dashboard build
```

선택 RAG matrix는 필요한 디스크/네트워크 비용을 먼저 확인한다.

```bash
uv sync --frozen --extra dev --extra rag
uv run --no-sync pytest tests/test_memory_service.py -q
```

API/브라우저는 새로 확보한 loopback 포트로 서버를 먼저 실행한다. 아래 18112는 예시이며 빈 포트인지 확인 후 사용한다. 테스트용 auth-enabled/no-auth 설정을 구분한다.

```bash
uv run --no-sync uvicorn antigravity_k.api.server:app --host 127.0.0.1 --port 18112
```

별도 터미널:

```bash
curl -i http://127.0.0.1:18112/health
AGK_BACKEND_URL=http://127.0.0.1:18112 uv run --no-sync pytest tests/test_e2e_smoke.py -q
AGK_BACKEND_URL=http://127.0.0.1:18112 pnpm --dir dashboard exec playwright test --project=chromium --reporter=list,json
```

JSON reporter 출력 경로와 trace/screenshot retention은 현재 Playwright config에 맞춰 지정한다. 고정 sleep만으로 성공을 판정하지 말고 관찰 가능한 상태를 기다린다.

VS Code 확장:

```bash
cd vscode-extension
npm ci
npm run compile
npm test
```

의존성 감사는 도구 실행 interpreter를 먼저 확인하고, 프로젝트 site-packages 또는 lockfile로 대상을 제한한다. 전역 환경 경고가 있으면 그 숫자를 프로젝트 결함 수로 사용하지 않는다. Node의 production-only/full dependency 감사를 구분한다.

## 수정 결과 기록 양식

각 작업은 아래 양식을 `docs/qa/2026-09-02/remediation/Fxx-<slug>.md`에 저장한다. 로컬 raw evidence는 별도 디렉터리에 두고 이 문서에서 참조한다. 토큰/비밀값/사용자 파일 내용은 로그에서 제거한다.

```text
Issue: Fxx
Status: OPEN | FIXED_PENDING_REVIEW | CLOSED | BLOCKED
Base SHA:
Verified SHA:
Owner / files owned:
Original reproduction: command, expected, actual, exit code, artifact
Root cause:
Implementation and scope:
Contract/migration/rollback decision:
Regression scenarios:
Before/after results:
Manual surface evidence:
Full-suite result and remaining pre-existing failures:
Independent review result:
Cleanup and preserved user changes:
Residual risks / untested cases:
```

## 다른 에이전트에게 그대로 전달할 시작 문장

> `docs/qa/2026-09-02/REPORT.md`와 `REMEDIATION_PLAN.md`를 읽고, 배정된 Fxx만 수정하라. 현재 HEAD와 dirty state를 확인하고 원래 재현부터 수행하라. 사용자 `data/benchmark_results.json`과 타 작업자 변경을 보존하라. 파일 소유권을 벗어나는 변경은 조정하라. 테스트 완화/인증 우회/고정 성공 응답으로 해결하지 말고, 실제 surface의 수정 전후 증거와 full SHA를 남겨라. 문서의 감사 판정을 현재 구현에 대한 자동 승인으로 재사용하지 말라.

## 최종 통합 승인 체크리스트

- [x] F01/F02/F03의 재현이 해소되고 실제 경계 시나리오가 통과한다. ([F01](remediation/F01-workspace-websocket-auth.md), [F02/F07](remediation/F02-F07-vault-git-transaction.md), [F03](remediation/F03-release-metadata-version.md))
- [x] 모든 P1이 CLOSED이거나 사용자에게 근거와 잔존 위험을 명확히 승인받았다. (F01–F06 전수 수정 및 residual 관리)
- [x] Mutation 상태 및 SBOM/릴리스 수치가 현재 artifact와 연결된다. ([F04](remediation/F04-mutation-snapshot.md), [F05](remediation/F05-release-sbom-notices.md))
- [x] auth matrix와 core E2E가 실제 결과를 검사하며 실패가 hard gate에 반영된다. ([F09/F10](remediation/F09-F10-e2e-auth-hard-gate.md))
- [x] 개발/선택 의존성 설치 matrix와 확장 테스트가 재현 가능하다. ([F11](remediation/F11-install-matrix.md), [F13](remediation/F13-vscode-extension.md))
- [x] UI의 변경된 모든 state/breakpoint를 fresh capture로 독립 검토했다. ([F12](remediation/F12-mobile-cjk-layout.md))
- [x] F14/F15 라이선스 사각지대 및 행동 기반 샌드박스 보안/mypy 430개 소스 파일 무결성을 달성했다. ([F14](remediation/F14-release-baseline.md), [F15](remediation/F15-static-and-behavioral-gates.md))
- [x] 원래 발견하지 못한 영역을 여전히 명시하고 무결함 보증을 하지 않는다. (각 이슈별 residual risks 및 한계 문서화)
- [x] 임시 서버/브라우저/fixtures를 정리하고 사용자 변경을 보존했다. (`data/benchmark_results.json` 무변조 보존)
- [x] 최종 검증 SHA와 각 reviewer/evidence가 일치한다. (기준 `6d0a24d4e6a0686693ce29a4d13a69443ae5149b` 기반)
