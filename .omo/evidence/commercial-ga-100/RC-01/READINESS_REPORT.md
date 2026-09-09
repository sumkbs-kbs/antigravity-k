# RC-01 — Release Candidate 100점 Gate · Readiness Report

- **Candidate SHA (immutable)**: `2ae967ad7c57513de9b6d3f8e1753e1a5be243b9` (branch `codex/rc-01-gate`)
- **Gate 실행일**: 2026-09-09
- **Coordinator**: rc_01_coordinator (Freebuff 세션) · **Verifier**: rc_01_verify (독립 실측)
- **중간 fix 정책**: 본 gate 실행 후 코드 변경 시 SHA를 재고정하고 영향 gate를 전부 재실행한다.

## 1. Gate 실측 결과 (candidate SHA 전부 동일 SHA)

| Gate | 명령 | 결과 |
|---|---|---|
| Backend 전체 테스트 | `uv run --no-sync pytest tests/ -m "not slow and not benchmark"` | **5,699 passed, 13 skipped** ✅ |
| Type check | `uv run --no-sync mypy src/` | **470 files, 0 errors** ✅ |
| Lint | `uv run --no-sync ruff check src/ tests/ scripts/` | **All checks passed** ✅ |
| Frontend typecheck | `pnpm run typecheck` (tsc -b) | **0 errors** ✅ |
| Frontend 테스트 | `pnpm run test -- --run` (vitest) | **749 passed** ✅ |
| Frontend lint | `pnpm run lint` (eslint) | **0 errors** (30 warnings — 기존 스타일 경고, error 아님) ✅ |
| Frontend build | `pnpm run build` (vite) | **built in 1.49s** ✅ |
| DR 리허설 | `scripts/dr_rehearsal.py` | **all_ok=true** (backup/restore·DB corruption·migration) ✅ |
| VAL-01 provider/RAG/학습 staging | `scripts/val01_staging.py` | **12/12 all_ok** ✅ |
| VAL-02 동시성/장애 staging | `scripts/val02_staging.py` | **6/6 all_pass** (CAS race·kill -9·부하·soak) ✅ |
| Container build+runtime | `docker build -t ssak-ai:rc-01 .` + run smoke | **health 200 + PIN login 200** ✅ |
| Rollback rehearsal | worktree checkout of prev SHA | **worktree_checkout_test=true** ✅ |

## 2. Release manifest

| 항목 | 값 |
|---|---|
| Candidate full SHA | `2ae967ad7c57513de9b6d3f8e1753e1a5be243b9` |
| Wheel | `antigravity_k-0.1.0-py3-none-any.whl` — sha256 `daa3f3084b8941e6de860e57565bc469841cacebb79d1b1fa52cd120277be5bd` |
| sdist | `antigravity_k-0.1.0.tar.gz` — sha256 `fda2e80f08726904303b333cb46db85afdf8f29c1824a0c93b6f447b0726dd76` |
| SBOM (CycloneDX JSON) | `rc01-sbom.json` — sha256 `a1ac7f67f885a40414a53305e11a271fad3d3c14617f49aa4eed3b220b702f63` |
| Container image | `ssak-ai:rc-01` — id `sha256:3e15f1d9d40a56014b65448d6799e9736ef15add92acaab92708f0fc1752e989` |
| Staging reports | `rc01-val01.json`, `rc01-val02.json`, `rc01-dr.json` (본 디렉터리) |

## 3. Checklist blocking item 점검

- 체크리스트 원장: **32/32 task DONE + RC-01 본 gate** (TODO 행 0)
- 열린 P1/P2 finding: **0건** — plan §7 finding 추적표 전 행이 해당 task DONE으로 종료.
  VAL-02에서 발견한 conversation CAS 결함 F1/F2는 당일 수정·회귀 테스트 고정 완료(`74271a9`).
- 문서: DOC-01에서 과거 주장 모순 6건 제거, checklist 7/7 체크.

## 4. Rubric 스코어카드 (100/100)

| 영역 | 배점 | 근거 |
|---|---:|---|
| 기능 범위·제품 골격 | 20/20 | WS-01~04, ARC-01, GOV-01 — A→B 격리/실행 컨텍스트/도구 바인딩 실측 |
| 정확성·핵심 계약 | 20/20 | TRN-01/02, RAG-01/02, EVO-01/02 — request/argv/progress/result 일치, fail-closed |
| 데이터 무결성·동시성 | 15/15 | DAT-01~03, VAL-02 — CAS race 0 contradiction, kill -9 복구, flock 원자성 |
| 보안 | 15/15 | SEC-01~03 — fail-closed hash, rate limit+lockout, WS origin/ticket, secret-free audit |
| UX·접근성 | 10/10 | UI-01/02 — 16 라우트 × 2 뷰포트 axe 위반 0, 키보드 워크플로 |
| 테스트·유지보수성 | 10/10 | QLT-01 — flaky 0, 5,699 backend + 749 frontend green, mypy/ruff clean |
| 릴리스·운영 | 10/10 | REL-01~03, OBS-01, DOC-01, RC-01 — SBOM/checksum/manifest, SLO/runbook, DR rehearsal |
| **합계** | **100/100** | |

## 5. 독립 리뷰 상태

| 리뷰 | 상태 |
|---|---|
| Code review | PASS — task별 독립 r1/r2 리뷰 완료 (DAT-02/03, SEC-01/02, TRN-01, VAL-02 등 review.md) |
| Security review | PASS — SEC-01(독립 재현 6/6), SEC-02(12/12), SEC-03(18건), LintAI strict fail-closed |
| Manual QA | PASS — UI-01/02 게이트(a11y+키보드), 대시보드 라이브 검증, disclosure 카드 경고/소진/정상 상태 |
| Release gate review | PASS — 본 report §1의 12개 gate 전부 동일 candidate SHA에서 green |

## 6. Rollback rehearsal & Go 결정

- Rollback 방법: `git checkout <prev-candidate>` + `uv sync --frozen` (reset 불필요, 문서 runbook 방식).
- 실측: 이전 SHA worktree checkout 성공 (`worktree_checkout_test=true`).
- 데이터 롤백: `data/` 백업 복원 + `.bak` 자동 복구 + tasks.db quarantine 절차 (OBS-01 DR 리허설 all_ok).

**Go/No-Go 결정: GO** — 승인자: rc_01_coordinator (2026-09-09), 근거: 본 report 전 항목.

## 7. 알려진 제한 (차단 아님)

- 공개 인터넷 대상 상용 운영은 DNS-aware SSRF/robots/load-test 항목이 남아
  GA 승인 범위 밖 (plan §OBS-01/GOV-01 범위 유지, 09_OPERATION_GUIDE "현재 운영 제한" 기재).
- Windows/CUDA는 GOV-01 지원 매트릭스에서 Unsupported 유지.
