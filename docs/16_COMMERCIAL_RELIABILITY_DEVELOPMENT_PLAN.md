---
title: Ssak-Ai 상용 신뢰성 상세 개선 개발 계획서
status: in-progress (CR-00 DONE, CR-01~CR-13 REVIEW, CR-14 REVIEW — 최종 판정 NO-GO 2026-09-13, **후보 커밋 10개로 동결(clean HEAD `0593dd27`) + required gate 21/21 PASS(attempt-013, 동결된 후보에서 되돌리기 없이, fp 2c5a15c8…), F-02~F-06·F-08~F-12·F-14~F-21 CLOSED, F-09 의 qs 편차 실행 검증 완료, F-01 조건부 정정(F-12: '빌드 멱등'은 고정 HEAD 에서만 참), F-07 CLOSED(커밋 후 새 SHA 에서 clean-machine 이 후보를 검증), F-11b ADVISORY(quick 범위 생존 변이 8건), F-13 OPEN(중첩 저장소 vault_data 가 부모를 영구 dirty 로 — advisory), **F-18~F-21 은 검증 장치 결함(3) + 테스트 격리 결함(1)이며 attempt-001~012 의 20/20 은 ambient 도구로 측정됐다** — 상세는 attempt-013 절, 남은 차단 사유는 사람의 영역(EX-01~06·C14-08·C14-03/04/05), GA 승인 없음)
date: 2026-09-12
baseline_sha: 08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f
source_review: docs/qa/2026-09-11-commercial-review/BASELINE.md
checklist: docs/17_COMMERCIAL_RELIABILITY_CHECKLIST.md
tags: [development-plan, reliability, security, migration, agent-handoff]
---

# 상용 신뢰성 상세 개선 개발 계획서

## 1. 이 문서가 요구하는 결과

Ssak-Ai의 로컬/자체 호스팅 **단일 운영자** 제품 범위에서 사용자 데이터 손실, 비밀정보 노출 경계, 오류 은폐, 배포 재현성 공백을 해소한다. 목표는 새 기능 수 확대나 상용화 100점 선언이 아니다. 에이전트가 독립된 작업 카드 하나를 받아도 같은 의도·검증·완료 기준으로 실행할 수 있도록 아래 결정을 고정한다.

**이번 산출물은 계획과 체크리스트다. 작성되었다고 구현·검증·출시가 완료되는 것은 아니다.** 모든 CR 구현 작업은 TODO로 시작한다. 실행 에이전트는 새 요청으로 구현을 위임받은 뒤 진행한다.

읽는 순서: [검토 기준](qa/2026-09-11-commercial-review/BASELINE.md) → 본 문서 공통 계약 → 담당 작업 카드 → [체크리스트](17_COMMERCIAL_RELIABILITY_CHECKLIST.md). 경로는 특별한 표기가 없으면 저장소 루트 기준이다. 예시 줄 번호는 기준 SHA 위치이며, 최신 코드에서 그래프와 심볼로 다시 찾는다.

### 진행 현황 (2026-09-12 갱신)

실행 상태의 단일 원본은 [17번 체크리스트](17_COMMERCIAL_RELIABILITY_CHECKLIST.md)다. 이 절은 인계용 요약이며, 완료 판정은 체크리스트와 증거를 따른다.

| 작업 | 상태 | 코드 위치 | 증거 |
|---|---|---|---|
| CR-00 현재 기준과 재현 분류 | DONE (독립 검토 미배정, 사용자 위임으로 게이트 개방) | 변경 없음 | `.omo/evidence/commercial-reliability/CR-00/attempt-001/` |
| CR-01 대화 ID 충돌 제거와 저장 형식 이전 | **REVIEW** | `engine/conversation_store.py`, `api/contracts/errors.py`, `scripts/migrate_conversation_storage.py`(신규), `tests/test_cr01_conversation_identity.py`(신규), 대시보드 대화 오류 표면화 | `.omo/evidence/commercial-reliability/CR-01/attempt-001/` |
| CR-02 세션 저장 손실·ID 충돌·동시 writer 보호 | **REVIEW** | `engine/session_manager.py`, `api/error_handler.py`, `api/server.py`, `api/routes/system_api.py`(session_save), `api/routes/chat.py`(fast-search hunk), `engine/memory_provider.py`, `engine/orchestrator/agent.py`, `tests/conftest.py`, `tests/test_cr02_session_durability.py`(신규) | `.omo/evidence/commercial-reliability/CR-02/attempt-001/` |
| CR-03 실제 sandbox 읽기 경계 | **REVIEW** | `engine/sandbox.py`, `tests/test_cr03_sandbox_read_boundary.py`(신규), `docs/ga/CR03_SANDBOX_READ_BOUNDARY.md`(신규) | `.omo/evidence/commercial-reliability/CR-03/attempt-001/` |
| CR-04 API shell도 동일한 실행·승인 경계 | **REVIEW** | `api/routes/agent_tools.py`, `api/contracts/shell.py`(신규), `api/server.py`, `tests/test_cr04_shell_api_boundary.py`(신규), `docs/ga/CR04_SHELL_EXECUTION_BOUNDARY.md`(신규) | `.omo/evidence/commercial-reliability/CR-04/attempt-001/` |
| CR-05 설정 비밀 계약(브라우저 영속 제거) | **REVIEW** | `engine/secret_settings.py`(신규), `api/routes/system_api.py`(/api/settings 구간), `dashboard/src/utils/browserSettings.ts`(신규), `dashboard/src/pages/SettingsPage.tsx`, `dashboard/src/api/client.ts`·`clientSchema.ts`, `dashboard/src/main.tsx`, `dashboard/e2e/tests/cr05-settings-secrets.spec.ts`(신규), `tests/test_cr05_settings_secret_contract.py`(신규), `docs/ga/CR05_SETTINGS_SECRET_CONTRACT.md`(신규) | `.omo/evidence/commercial-reliability/CR-05/attempt-001/` |
| CR-06 설정 상태가 서버의 진실을 반영 | **REVIEW** | `dashboard/src/pages/SettingsPage.tsx`(phase 기계), `dashboard/src/api/client.ts`(`ApiHttpError`·`isAuthRequiredError`), `dashboard/src/api/clientSchema.ts`(`cost`), `dashboard/src/pages/SettingsPage.cr06.test.tsx`(신규), `dashboard/e2e/tests/cr06-settings-errors.spec.ts`(신규) | `.omo/evidence/commercial-reliability/CR-06/attempt-001/` |
| CR-07 화면 오류 복구와 잘못된 경로 | **REVIEW** | `dashboard/src/components/UI/AppErrorBoundary.tsx`(신규), `dashboard/src/pages/NotFoundPage.tsx`(신규), `dashboard/src/App.tsx`, `dashboard/src/__tests__/App.routeRecovery.cr07.test.tsx`(신규), `dashboard/e2e/tests/cr07-route-recovery.spec.ts`(신규) | `.omo/evidence/commercial-reliability/CR-07/attempt-001/` |
| CR-08 설정과 명령 팔레트 키보드/접근성 | **REVIEW** | `dashboard/src/hooks/useModalDialog.ts`(신규), `dashboard/src/components/UI/CommandPalette.tsx`, `dashboard/src/pages/SettingsPage.tsx`, `dashboard/src/styles/index.css`, `dashboard/e2e/tests/cr08-keyboard-accessibility.spec.ts`(신규), 접근성 매트릭스 2종(404 route) | `.omo/evidence/commercial-reliability/CR-08/attempt-001/` |
| CR-09 오프라인 로컬 표시 자산 | **REVIEW** | `dashboard/index.html`(CDN 4종 제거), `dashboard/src/utils/mermaidRuntime.ts`(신규)·`monacoRuntime.ts`·`monacoWorkers.ts`(신규), `dashboard/src/components/Chat/ChatMessage.tsx`(로컬 로더·토큰 span), `dashboard/src/components/Editor/{MonacoEditorWrapper,DiffViewer}.tsx`·`History/SnapshotDiffView.tsx`, `dashboard/src/main.tsx`, `dashboard/src/styles/index.css`(폰트 토큰·reduced-motion), `dashboard/vite.config.ts`·`vitest.config.ts`·`vite.alias.ts`(신규), `THIRD_PARTY_PROVENANCE.toml`+`engine/release_dependencies.py`·`release_sbom.py`·`audit_exceptions.py`(declared_licenses), `release/{THIRD_PARTY_NOTICES.txt,dashboard.cdx.json}`, `dashboard/src/tests/monaco*Stub.ts`(신규), `dashboard/e2e/tests/cr09-offline-assets.spec.ts`(신규 4건), `docs/ga/CR09_OFFLINE_ASSETS.md`(신규) | `.omo/evidence/commercial-reliability/CR-09/attempt-001/` |
| CR-10 운영 지표와 빌드 신뢰성 | **REVIEW** | `src/antigravity_k/build_info.py`(신규), `api/routes/system_api.py`(monotonic 업타임·`process_id`·`memory_percent`·`build`), `api/routes/models_api.py`, `dashboard/buildStamp.ts`(신규), `dashboard/src/utils/uiBuildInfo.ts`(신규), `dashboard/vite.config.ts`·`vitest.config.ts`·`vite-env.d.ts`, `dashboard/src/stores/uiStore.ts`(SystemStatus 재정의), `dashboard/src/App.tsx`, `dashboard/src/components/Layout/SystemTelemetricsBar.tsx`(전면 재작성), `dashboard/src/pages/AgentPage.tsx`, `dashboard/src/stores/agentMonitorStore.ts`·`components/Agent/AgentMonitorPanel.tsx`, `dashboard/src/api/clientSchema.ts`, `dashboard/src/styles/index.css`, `dashboard/e2e/tests/cr10-telemetry.spec.ts`(신규 4건), `tests/test_cr10_runtime_metadata.py`(신규 11건), `docs/ga/CR10_RUNTIME_TELEMETRY.md`(신규) | `.omo/evidence/commercial-reliability/CR-10/attempt-001/` |
| CR-11 clean CI/release와 실제 의존성 감사 | **REVIEW** | `.github/workflows/ci.yml`(8 job 환경·Node·감사), `.github/workflows/release.yml`(설치→SBOM→`uv build`→저장소 밖 검증·dry-run 소비), `Dockerfile`(node 22.13), `dashboard/package.json`(engines), `scripts/audit_python_dependencies.sh`(출하 extras 자동 감지·입력 기록·예외 판정), `scripts/verify_dashboard_bundle.sh`(신규), `scripts/verify_release_artifacts.sh`(신규), `config/audit-exceptions.json`(id 정합화), `tests/test_cr11_release_bootstrap.py`(신규 19건), `docs/ga/CR11_RELEASE_BOOTSTRAP_AND_AUDIT.md`(신규) | `.omo/evidence/commercial-reliability/CR-11/attempt-001/` |
| CR-12 지원·운영·VS Code 문구 정합화 | **REVIEW** | `vscode-extension/README.md`(companion 범위·재시도 계약·고지), `docs/ga/GA_CLAIMS_AND_REVIEW_REGISTER.md`(확장 행·`## Disposition vocabulary`·Pending 7행 표기), `docs/ga/GA_SUPPORT_MATRIX.md`(외부 조건 10행 표기), `docs/ga/CR02_SESSION_STORAGE_FAILURE_RUNBOOK.md`·`CR05_KEY_REENTRY_RUNBOOK.md`·`CR12_SANDBOX_UNAVAILABLE_RUNBOOK.md`(신규), `docs/ga/CR08_KEYBOARD_ACCESSIBILITY.md`(링크 정정), `README.md`(RP/CR 상태 분리·GA-100 이력 한정), `tests/test_cr12_docs_alignment.py`(신규 25건) | `.omo/evidence/commercial-reliability/CR-12/attempt-001/` |
| CR-13 이전 후보 증거 재사용 방지와 불변 artifact | **REVIEW** | `scripts/evidence_bundle.py`(신규 — build/verify, redaction 후 hash, sidecar 자기 hash, gate 요약 재계산), `tests/test_cr13_evidence_bundle.py`(신규 31건), `docs/ga/CR13_EVIDENCE_BUNDLE.md`(신규), `.omo/evidence/commercial-reliability/CR-13/attempt-001/`(증인·시연 번들) | `.omo/evidence/commercial-reliability/CR-13/attempt-001/` |
| CR-14 최종 후보 전체 검증과 GO/NO-GO | **REVIEW — NO-GO (required gate 20/20 PASS, F-02 폐쇄)** | `src/antigravity_k/engine/benchmark_harness.py`·`tests/conftest.py`·`tests/test_cr14_benchmark_db_isolation.py`(F-02), `scripts/evidence_bundle.py`(evidence_kind 필수화·빈 required_gates 거부·`REFERENCE_ONLY` exit 3), `scripts/ga_gate.py`(`--merge-into` + 코드 지문), `tests/test_cr14_candidate_evidence.py`(13건), `tests/test_rel01_clean_build_sbom.py`(임시 프로젝트 생성 + 저장소 드리프트 검사), `tests/test_cr13_evidence_bundle.py`, `Dockerfile`(dashboard-builder `NODE_OPTIONS`), `dashboard/src/utils/mermaidRuntime.ts`+`mermaidRuntime.test.ts`, `dashboard/package.json`+lock 3종, `src/antigravity_k/release/*`(재생성), `scripts/commercial_ga_gates.json`(attempt-013: 게이트 환경 고정 + `python-benchmark` 신규 + 인벤토리 21), `pyproject.toml`+`uv.lock`(attempt-013: `bandit` 선언), `tests/conftest.py`(`_reset_login_security_state`), `tests/test_cr14_gate_env_pinning.py`·`test_cr14_login_state_isolation.py`·`test_cr14_gate_load_isolation.py`, `docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md` | `.omo/evidence/commercial-reliability/CR-14/attempt-001/`, `attempt-002/`, **`attempt-013/`**(최신) |

- 기준 SHA `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f`에서 발견 17건을 재분류했다(ALREADY_FIXED 0건).
- ~~CR-01~CR-14 코드는 **미커밋**이다(같은 트리에 patch 공존). 승인 전 커밋 full SHA를 확정하고 같은 SHA에서 게이트를 다시 실행해야 한다.~~ → **attempt-009/010 에서 완료했다**: 후보를 커밋·동결(`5ccb938e5d31411b16f2a69e3015fc8fb826455d`, 커밋 4개)하고 그 트리에서 20 gate 를 재완주했다(지문 `d4a42ab8…`, 되돌리기 0회). **단 커밋은 승인이 아니다** — 판정은 NO-GO 이고 부족한 것은 외부 승인(EX-01~06)·독립 검토·출시 책임자(C14-08)다.
- **CR-14 최종 판정: NO-GO(2026-09-12), attempt-002까지.** attempt-001은 20 required gate 중 **15 실측 = 14 PASS / 1 FAIL / 4 NOT_RUN**(FAIL = `dependency-audit-dashboard`, `mermaid@10.6.1` ∈ `<=10.9.2`, GHSA-m4gq-x24j-jpmf high = **P1**). **attempt-002에서 P1과 신규 F-05(`docker-build` 콜드 `tsc -b` heap OOM)를 닫아 required gate 20개가 단일 코드 지문 `ebbbd7f0…` 위에서 20/20 PASS** 했다. 그럼에도 판정은 NO-GO다 — 남은 조건은 **필수 외부 승인 부재(EX-01~06)**와 **source mismatch(미커밋 → clean full SHA 없음)**이며, 둘 다 §CR-14 판정 규칙의 명시적 NO-GO 조건이다. 판정 근거·재개 순서는 [CR14_FINAL_CANDIDATE_VERDICT.md](ga/CR14_FINAL_CANDIDATE_VERDICT.md). **NO-GO 기록은 평가 산출물이며 GA 승인도 CR-14 DONE도 아니다.** **attempt-013 까지 오면서 이 문단의 마지막 문장을 바꿔 읽어야 한다** — 이제 required gate 는 **21개**(`python-benchmark` 신규)이고 커밋된 후보 `0593dd27` · 지문 `2c5a15c8…` 에서 21/21 PASS 다. 그리고 그 과정에서 **게이트가 lock 이 아니라 실행자의 셸을 검증해 왔다는 사실(F-18)** 과 **lock 이 정의하는 환경에서는 스위트가 실패한다는 사실(F-19)** 이 드러났다 — 즉 attempt-001~012 의 20/20 은 ambient 도구로 측정된 값이며, 기술 결함이 0건이라는 결론은 코드 계약에 근거하므로 유지되지만 "환경까지 검증됐다"는 주장은 attempt-013 부터다. 차단 사유는 변하지 않았다: EX-01~06 · C14-08 · C14-03/04/05.
- 운영 영향(CR-01): legacy 대화 파일이 남아 있으면 API가 503 `conversation_storage_migration_required`로 fail-closed 한다. 이전 절차는 [런북](ga/CR01_CONVERSATION_STORAGE_MIGRATION_RUNBOOK.md)을 따른다.
- 운영 영향(CR-02): 세션 저장 실패는 409 `stale_session_write` / 503 `session_persistence_error`·`session_durability_uncertain`으로 응답하며, 세션 디렉터리(`~/.antigravity/sessions` 또는 프로젝트별 디렉터리)를 쓰는 **구버전 프로세스와 동시 실행을 지원하지 않는다** — 배포 시 구버전 종료가 필요하다.
- CR-02 부수 정리: 회귀 테스트가 `~/.antigravity/sessions`에 파일을 쓰던 누출(CR-02 이전부터)을 `default_session_base_dir()` + conftest fixture로 격리했다. 전체 suite 재실행에서 사용자 홈 신규 항목 0을 실측했다.
- 운영 영향(CR-03): 모델 생성 코드/셸의 읽기 경계가 사용자 트리·`/tmp`·`/var/tmp`·`/var/folders`를 차단한다. 예외·잔여 위험·OS별 실측 상태는 [경계 문서](ga/CR03_SANDBOX_READ_BOUNDARY.md)에 있다. Linux/Docker backend는 미실측(검증 대기)이다.
- 계획 이탈 기록(CR-03 D-01): "허용 목록 구현" 요구는 macOS 26.6.2에서 CPython 부팅 SIGABRT로 불가함을 실측해, 계획 §1 절차로 decision에 사유·영향·새 수용 기준을 남기고 경계를 구현했다. 재검토 조건과 재현 스크립트는 `.../CR-03/attempt-001/repro/`에 있다.
- 운영 영향(CR-04): `POST /api/agent/tools/shell/run`은 이제 현재 권한 모드로 판단하고 CR-03 읽기 경계를 재사용한다. 읽기 전용 모드의 shell은 ASK로 403(승인 flow 없음), sandbox 미적용은 503, timeout은 504로 거부한다. **`security.sandbox_enabled=false` 배포에서는 이 엔드포인트가 동작하지 않는다**(raw 폴백 금지). 계약·롤백 판단은 [실행 경계 문서](ga/CR04_SHELL_EXECUTION_BOUNDARY.md) 참조.
- 운영 영향(CR-05): 설정 화면은 provider 키를 **브라우저에 더 이상 캐시하지 않는다**(입력 중 메모리 → 서버 `.env`만). 서버 저장 대상은 `AGK_ENV_FILE`이 있으면 그 파일, 없으면 프로젝트 루트 `.env`이며 권한 0600·원자적 교체다. `GET /api/settings`는 키 원문·부분값 대신 `settings.api_keys_configured`(bool 맵)를 반환하므로 **이 엔드포인트를 쓰는 외부 소비자가 있으면 파괴적 변경**이다. 저장 가능한 키는 allowlist 8종(6 provider + 예산/한도)뿐이고 그 밖의 `*_API_KEY`는 400으로 거부된다. **이전 버전에서 브라우저에만 저장돼 있던 키는 정화 과정에서 제거되며 자동 업로드되지 않으므로 재입력이 필요할 수 있다.** 계약·롤백 판단은 [설정 비밀 계약 문서](ga/CR05_SETTINGS_SECRET_CONTRACT.md) 참조.
- 계획 이탈 기록(CR-05): 없음. 다만 계획이 요구한 "비밀을 브라우저에 남기지 않는다"를 만족시키려면 응답 형태를 바꿔야 했고(마스킹 문자열 맵 → bool 맵), 임의 `*_API_KEY` 허용을 끊어야 했다. 두 변화의 사유·영향·재검토 조건은 `.../CR-05/attempt-001/decision.md`의 D-03/D-04에 있다.
- 운영 영향(CR-06): 설정 화면은 이제 “서버의 진실을 아는 단계”를 상태로 구분한다(loading → ready 또는 load-error; ready → saving → ready 또는 save-error). **초기 GET 실패 시에는 폼 자체가 없어 기본값을 저장할 수 없다**(오류/재시도만 보임). 서버가 소유한 값(`model.name`·`cost.daily_budget_usd`·`cost.hourly_action_limit`)은 GET 결과가 화면을 채우고, 브라우저에 남아 있는 오래된 값은 서버가 그 값을 주지 않을 때만 쓰인다. 서버가 보고한 `0` 예산/한도는 기본값 50/100으로 대체되지 않는다. 저장 성공 후 서버 관리 값을 재조회해 반영하고, 연속 클릭은 요청 1건으로 된다.
- **주의(CR-06 D-02)**: 화면의 예산/한도 입력은 “이 브라우저의 표시 선호”이며 **서버 강제 한도를 바꾸지 않는다**. 화면은 서버 강제 값을 read-only로 함께 보여준다. 서버 한도를 화면에서 바꾸는 흐름은 후속 작업이며, 도입 시 `POST /api/settings/env`(CR-05 allowlist의 `AGK_DAILY_BUDGET_USD`/`AGK_HOURLY_ACTION_LIMIT`)와 재시작 안내·`critical` 게이트 실패 시 표시를 함께 설계해야 한다.
- **배포 주의(CR-05/CR-06/CR-07/CR-08/CR-09/CR-10/CR-11)**: `src/antigravity_k/dashboard_dist/`는 **추적되는 커밋 대상 번들**이다. 일곱 attempt는 검증 후 이를 HEAD로 복원했으므로, 배포·e2e 재검증 전에 `pnpm --dir dashboard build`가 필요하다(그대로 배포하면 구버전 UI가 서빙되고 **CR-09 e2e와 CR-10 e2e가 각각 4 failed**로 떨어진다). **CR-11부터는 CI가 패키징 전에 반드시 대시보드를 재빌드하고(`scripts/verify_dashboard_bundle.sh`) 새 번들이 wheel에 들어갔는지 hash로 대조한다** — 배포 파이프라인은 낡은 번들을 포장하지 않는다. 다만 `clean-machine` gate는 `git archive HEAD`를 쓰므로 **추적 번들 자체가 낡아 있으면 그 gate는 여전히 낡은 UI를 포장한다**(커밋 시 재빌드 결과 포함 필요). **빌드가 남긴 미추적 산출물은 반드시 삭제해야 한다** — 그대로 두면 `tests/test_dashboard_wheel_assets.py`의 중복 asset 판정이 실패한다(CR-05·CR-09에서 각 1회 경험).
- 운영 영향(CR-09): 필수 렌더링 자산이 더 이상 CDN에 의존하지 않는다 — 폰트는 시스템 스택, 코드 하이라이트 테마는 `highlight.js@11.11.2` 번들 CSS, Mermaid는 `mermaid@10.6.1` 정식 의존성의 **지연 동적 import**(다이어그램을 그릴 때만), Monaco는 설치된 `monaco-editor@0.56.0` + **로컬 워커 chunk**다. 이전에 로더 기본값(`cdn.jsdelivr.net/npm/monaco-editor@0.55.1/min/vs`)에서 오던 편집기가 이제 로컬에서 뜨고, 차단 환경에서도 편집기·diff가 동작한다. 계약·절차·라이선스 운연은 [오프라인 자산 문서](ga/CR09_OFFLINE_ASSETS.md) 참조.
- **주의(CR-09 라이선스)**: Mermaid 클로저가 러타임 의존성으로 들어와(63개 패키지, elkjs EPL-2.0 포함) SBOM/notice가 커졌다. `npm:khroma@2.1.0`은 registry/lock에 license 필드가 없어 `THIRD_PARTY_PROVENANCE.toml`의 `declared_licenses`로 **사람이 선언**해야 license gate가 통과한다(미선언 시 exit 1). 선언값은 SBOM property·notice·gate note에 출처로 남는다. 상류가 메타데이터를 채우면 선언을 제거한다.
- **주의(CR-09 코드블록)**: 하이라이트 토큰 span을 그대로 렌더하도록 고쳤다(CR-09 이전부터 평문으로 치환되어 로컬 테마가 기저 색만 칠했다). 렌더하는 노드는 `rehype-sanitize`를 통과한 것이며 복사 버튼은 계속 추출 텍스트를 쓴다.
- 계획 이탈 기록(CR-09): F05 본문에 없던 **Monaco CDN 로더**를 브라우저 실측으로 찾아 함께 오프라인화했고(추가 범위), cytoscape 깊은 import를 alias했으며, C08-04 axe 스캔이 팔레트 fade 중 색을 측정하던 문제(HEAD에서도 재현)를 스캔 대기 + `prefers-reduced-motion`으로 고정했다. CSP의 CDN 허용 목록 정리는 보류(보안 lane 승인 필요). 사유·영향·재검토 조건은 `.../CR-09/attempt-001/decision.md` D-04·D-07·D-08에 있다.
- 선행 작업 영향(CR-06): 서버 우선 규칙 도입으로 CR-05가 고정한 legacy `default_model` 표시 단언 2건(단위·e2e)을 교체했다. 키 비영속·legacy 정화 단언은 그대로다. 새 hash·사유는 `.../CR-05/attempt-001/metadata.json`의 `successor_changes_to_cr05_evidence`와 `.../CR-06/attempt-001/metadata.json`에 있다.
- 운영 영향(CR-07): 대시보드에 **2층 오류 경계**가 생겼다. 앱 경계는 `PinModal` **바깥**에 있어 로그인 흐름을 fallback에 묻지 않고, route 경계는 `<main>` 안에서 `key={location.pathname}`으로 경로 변경 시 초기화된다. 화면에는 **오류 원문·스택 대신 식별자(`E-XXXXXXXX`, FNV-1a)와 분류(chunk/render)·시도 횟수만** 보이고 원문은 콘솔로 간다. **chunk(모듈) 실패에는 "다시 시도"를 제공하지 않고 새로고침만** 안내한다 — 실패한 모듈 URL은 브라우저 모듈 맵과 `React.lazy` 양쪽에 기억되어 같은 세션 재시도가 복구를 보장하지 못하기 때문이다. 없는 경로는 셸 안 `<Route path="*">`의 404 안내(경로 텍스트 노드 출력·홈 복귀·뒤로가기)로 처리한다. **오류 복구는 어떤 storage(대화·로컬 히스토리·인증)도 지우지 않는다.**
- 운영 영향(CR-08): 명령 팔레트가 이제 진짜 modal이다 — `role="dialog"[aria-modal="true"]`, 열릴 때 검색 입력으로 focus 이동, Tab/Shift+Tab은 팔레트 안에서만 순환, Esc로 닫으면 **열기 전 요소로 focus 복귀**, 열려 있는 동안 배경(사이드바·본문·상단 바·토스트 등)이 `inert`가 된다. 설정 화면의 provider 비밀 입력은 보이는 provider 이름이 접근성 이름으로 연결되어 **여섯 입력이 낭독으로 구분**된다(placeholder는 힌트일 뿐 이름이 아니다). 한글 IME 조합을 확정하는 Enter는 명령을 실행하지 않는다.
- **주의(CR-08)**: 배경 inert 대상은 팔레트 오버레이 기준 **조상 체인의 모든 형제**다(오버레이가 `.app-layout` 안쪽에 마운트됨). 정리 순서는 `inert 해제 → focus 복귀`여야 한다 — 반대로 하면 브라우저가 inert 하위 `focus()`를 무시해 focus가 body로 남는다(실브라우저 실측, jsdom 단위로는 잡히지 않음). 공용 훅(`useModalDialog`)은 현재 **팔레트에만** 적용되어 있고, `PinModal`·`KeyboardShortcutsModal`·`GitCommitDialog`·wiki 모달은 아직 focus trap·배경 inert가 없다(후속 후보).
- 접근성 게이트 확장(CR-08): UI-01·UI-02 매트릭스에 404 화면(`/cr08-unknown-route`, marker `cr07-not-found`)을 추가해 **16 → 17 route**가 되었다. 두 스펙의 매트릭스 고정 단언도 17로 갱신되어 있다. CR-07이 남긴 "404 화면이 게이트 밖" blocker는 해소됐다.
- 운영 영향(CR-10): 헤더 텔레메트리 바가 더 이상 고정 문자열을 보여주지 않는다. `BUILD`는 서버가 보고한 버전(`/health`·`/api/system/status`의 `version` + `build.build_id`)이고, **`UPTIME`은 현재 API 서버 프로세스의 가동 시간**(monotonic 경과)이라 프로세스가 재시작되면 0에서 다시 시작한다(호스트 업타임·탭 열린 시간이 아니다). `NODE`는 응답한 프로세스의 PID다. **값이 없으면 `0`/`false`/`true`로 뭉개지 않고 `UNKNOWN`**이며, 연결이 끊기면 `healthy`가 `null`이 되어 `NOMINAL`을 주장하지 않는다. `LINK`가 마지막 성공 관측 기준 `LIVE`/`STALE`(30s 초과)/`OFFLINE`/`UNKNOWN`을 보여주고 고정 문구 `CTRL`은 삭제됐다. `MEM`은 이제 `%`이며(`/api/system/status`의 `memory_percent`), legacy `memory_mb` 키는 값이 percent인 채로 남아 있다. 계약·운영 절차는 [런타임 텔레메트리 문서](ga/CR10_RUNTIME_TELEMETRY.md) 참조.
- **주의(CR-10 D-01)**: `uptime_seconds`의 의미가 바뀌었다 — 이전에는 벽시계 차이, 이제는 **프로세스 가동 시간**이다. 호스트 업타임을 기대하는 소비자가 있으면 별도 지표를 만들어야 한다. `system_api.START_TIME`을 직접 읽는 외부 코드가 있으면 깨진다(저장소 내 참조는 없다).
- **주의(CR-10 D-04)**: `STALE_AFTER_MS`(30초)는 폴링 주기 10초의 3배로 **상수**다. `App.tsx`의 폴링 주기를 바꾸면 이 값도 함께 바꿔야 stale 판정이 어긋나지 않는다.
- 계획 이탈 기록(CR-10): 계획의 `CTRL` 문구 제거 요구를 “삭제 후 연결 신선도 표시로 대체”로 구현했고(D-05), `memory_mb`를 제거하는 대신 정직한 키를 병행 노출했다(D-02). 진행 중 실패 2건(실시간 CPU 대조 부적합 D-04 아님 — 검증 설계, health 경로 가정 착오)은 `.../CR-10/attempt-001/reproduction.md` §3-1에 있다.
- 선행 작업 영향(CR-10 D-08): CR-09이 남긴 `ruff format` 드리프트(`engine/release_dependencies.py`, `src/` 안 유일한 미포맷 파일)를 CR-10이 정정해 `ruff format --check src/ tests/ scripts/`를 exit 0으로 되돌렸다. CR-08/CR-09 attempt의 같은 파일 sha는 낡았다. CR-10은 `App.tsx`·`styles/index.css`·`clientSchema.ts`·`AgentPage.tsx`를 다시 만져 CR-05~CR-09 attempt의 같은 파일 sha도 함께 낡았다(계약은 그대로).
- 운영 영향(CR-11): CI·릴리스가 **설치 없는 src-layout 실행**과 **출하되지 않는 의존성 감사**를 더 이상 하지 않는다. Python 게이트는 `uv sync --locked --no-editable --extra dev` 하나의 환경에서 돌고, 감사는 Dockerfile이 설치하는 base + 출하 extra(`[rag]`)를 대상으로 한다. 그 결과 **이전에 감사되지 않던 `[rag]` 의존성에서 chromadb 1.5.9 권고 4건이 처음으로 gate에 도달**했고, REL-03 예외 레지스트리를 엔진과 같은 규칙으로 적용해 `excepted`로 통과한다(owner·만료 `2026-12-08` 명시, unresolved 0·expired 0). 게이트 종료코드는 0/1/2로 갈린다(통과 / 취약점·만료 예외 / 인프라 오류). Node/pnpm은 **Node 22.13 + pnpm 11.3.0**(package.json engines·packageManager, Dockerfile `node:22.13-alpine`)으로 통일됐다(Node 20은 pnpm 11의 `node:sqlite` 요구를 못 채운다). 릴리스는 `dry_run` 입력을 실제로 소비하고 수동 실행에서 `dry-run-report`만 남긴다. 계약·절차는 [릴리스 부트스트랩 문서](ga/CR11_RELEASE_BOOTSTRAP_AND_AUDIT.md) 참조.
- **주의(CR-11 예외 id)**: `config/audit-exceptions.json`의 `id`는 **감사 도구가 보고하는 primary id**여야 한다. pip-audit/PyPI는 같은 권고를 `PYSEC-xxxx-xxxx`로 보고하고 CVE/GHSA를 aliases로 주므로, CVE로 등록하면 정확 일치 매칭에 걸리지 않아 `dependency-audit-python`이 실패한다(의도된 deny-by-default). chromadb 4건은 CVE→PYSEC로 재등록하면서 CVE/GHSA를 `justification`에 alias로 남겼다.
- **주의(CR-11 재현성)**: 감사 입력의 `sha256_16`은 주석 줄을 제외한 정규화 내용의 해시다(`uv export`가 헤더에 출력 경로를 적어 넣어 파일 바이트 해시는 실행마다 달라진다). 감사 입력은 합집합 파일이 아니라 각 export 파일을 pip-audit에 그대로 넘긴다 — requirements의 줄 연속(`--hash`)을 `sort -u`하면 입력이 손상된다.
- 선행 작업 영향(CR-11): `config/audit-exceptions.json`의 id 3건이 CVE→PYSEC로 바뀌어 **REL-03 검토자는 이 파일 sha를 다시 확인**해야 한다(계약 의미·만료는 그대로). `scripts/audit_python_dependencies.sh`는 입력·지문·예외 판정이 모두 바뀌었다. `tests/test_rel01_clean_build_sbom.py`는 빌드 명령 문자열 결합만 분리했다(순서 계약 불변).
- 운영 영향(CR-12): 지원·운영 문구가 실제 동작과 일치한다. VS Code 확장은 **context-sync companion**이며 배경 재연결 타이머·오프라인 큐가 없다(엔진이 죽어 있으면 다음 편집기 이벤트에 재시도된다) — “자동 재연결”로 설명하는 문구는 더 이상 쓸 수 없다. 법무·개인정보·보안·provider 약관 승인은 미취득이며, 주장 레지스트리·지원 매트릭스에서 `BLOCKED_EXTERNAL`(해제 주체 명시)로 보존된다. **지원 매트릭스의 플랫폼·provider 분류는 하나도 승격되지 않았다**(여전히 Experimental/Unsupported). 런북 3종(세션 저장 실패·키 재입력·sandbox unavailable)과 CR-01 이전 런북이 운영 절차의 단일 원본이다.
- **인계 주의(CR-12)**: 이번 작업은 문구·상태 표기만 바꿨고 제품 동작은 바꾸지 않았다. `vscode-extension/README.md`·`docs/ga/GA_CLAIMS_AND_REVIEW_REGISTER.md`·`docs/ga/GA_SUPPORT_MATRIX.md`를 증거로 인용한 과거 attempt가 있다면 같은 파일 sha가 낡았다.
- 운영 영향(CR-13): 릴리스 증거는 이제 **자기완결 번들**로 포장된다 — artifact가 번들 안 상대 경로에 복사되고, hash는 redaction **이후** 바이트에서 계산되며, 후보 SHA에 `--expected-sha`로 묶인다. `scripts/evidence_bundle.py verify --bundle <dir> --expected-sha <후보 SHA>`가 exit 0이어야 승인 가능이다. 번들에 `verdict`/`status`를 적으면 거부되고(판정은 검증기 출력), **`required_gates`를 비우면 gate 검사를 건너뛴다** — CR-14는 반드시 채워야 한다. 과거 후보 증거는 `historical: true`로 참고용만 가능하며 gate/soak 근거가 될 수 없다.
- **인계 주의(CR-14 attempt-013)**: `scripts/commercial_ga_gates.json` 은 이제 **예외적으로 바뀌었다** — required gate 가 **21개**이고(`python-benchmark` 추가, 검사 제외가 아니라 wall-clock 검사를 이동) python 게이트는 `--extra dev --extra rag`·`security-bandit` 은 `--extra dev` 를 **반드시** 명시해야 한다. 이유는 F-18 이다: `uv run --isolated --frozen <tool>` 은 도구가 임시환경에 없으면 uv 가 **호출 셸의 PATH** 로 떨어져 게이트가 후보가 아니라 실행자의 머신 상태를 검증하게 된다(실측: 같은 lock 으로 돌린 두 실행이 다른 인터프리터·다른 skip 집합을 냈다). 이 규율은 `tests/test_cr14_gate_env_pinning.py` 가 강제한다 — 게이트를 손대면 그 계약이 먼저 깨진다. 마찬가지로 `uv.lock` 도 바뀌었다(`bandit` 을 dev extra 에 선언 — 선언되지 않은 도구는 extra 로도 환경에 안 들어간다).
- **인계 주의(CR-13)**: `scripts/commercial_ga_gates.json`(당시 20 gate)과 `scripts/release_manifest_verify.py`·`ga_gate_verify.py`는 **당시에는 바꾸지 않았다**(RP-11/RP-13 계약 보존). RP-13 attempt-002의 드리프트(artifact 1건, metadata는 PASS 선언)는 고치지 않고 보존했다 — 과거 기록이며 현재 검증은 FAIL이다.
- 운영 영향(CR-14): ① **CR-13의 우회로가 닫혔다** — 번들은 `evidence_kind`(`release`|`reference`)를 선언해야 하며, `release`인데 `required_gates`가 비면 build·verify 모두 거부한다. 참고 번들은 `verify`가 `PASS` 대신 `REFERENCE_ONLY`(exit 3)를 낸다 — **`exit 0`만 승인으로 보는 스크립트를 쓸 것.** ② `ga_gate.py --merge-into`로 20-gate를 단계별 실행하되 **같은 후보 SHA·manifest sha256·코드 지문**일 때만 이어받는다(다르면 exit 2). ③ 후보 지문은 `docs/`·`.omo/`를 제외한 코드 경로만 대상이다(결과 문서 작성이 gate 증거를 낡게 만들지 않는다).
- **주의(CR-14 · F-08 폐쇄 — 새 영속 경로를 추가할 때)**: 사용량 DB 기본 경로도 `default_usage_db_path()` 한 곳에서 정해지고, `tests/conftest.py` 의 `_isolate_default_usage_db` 픽스처가 테스트에서 임시 디렉터리로 돌린다(`_isolate_default_benchmark_db` 바로 옆 — 패턴이 보이게). **런타임 호출부에 `db_path="data/..."` 를 리터럴로 쓰지 말 것**: F-02 와 F-08 은 둘 다 그 리터럴에서 나왔고, F-08 은 `auto_save_interval`(기본 50)건을 넘길 때만 발현돼 조용히 잠복했다. 리터럴이 돌아오면 conftest 패치가 **효과가 없어지므로**, 회귀가 `dependencies.get_model_manager` 의 **소스**까지 검사한다. `AGK_USAGE_DB` 로 배포·격리 실행에서 위치를 바꿀 수 있다. `data/` 에서 지문을 흔드는 파일은 **`token_usage.json`(추적) 뿐**이고 `data/projects.json`·`data/benchmarks/*` 는 gitignore 다.
- **주의(CR-14 · F-02 폐쇄)**: 벤치마크 결과 DB 기본 경로는 `default_benchmark_db_path()` 한 곳에서 정해지고, `tests/conftest.py` 의 `_isolate_default_benchmark_db` 픽스처가 테스트에서 그 지점을 임시 디렉터리로 돌린다(CR-02 D-07 선례). **`pytest` 를 돌린 뒤 `git checkout -- data/benchmark_results.json` 을 하지 말 것** — F-02 폐쇄 이후 되돌릴 것이 없고, 습관적 복원은 다른 드리프트를 덮는다. `AGK_BENCHMARK_DB` 로 배포·격리 실행에서 위치를 바꿀 수 있다. conftest 는 **모듈 속성**을 패치하므로 테스트는 `harness_mod.default_benchmark_db_path()` 로 읽어야 한다.
- **주의(CR-14 · F-09 — attempt-007 폐쇄, dev 도구 체인)**: dev 도구 체인의 감사 잔여분도 **양쪽 설정의 override** 로 고정된다(`js-yaml: 4.3.2` 는 상류 선언 범위 안이라 편차 아님 / `qs: 6.16.0` 은 **상류 정확 고정을 넘긴 편차**라 근거가 선언 옆에 있어야 하고 회귀가 그 문서화를 검사한다). **pnpm 은 override 를 지워도 해석을 즉시 되돌리지 않으므로**(lock 보존) 선언 검사를 해석 검사와 짝으로 둔다. dev 패키지는 출하 SBOM·고지문에 **없어야** 한다(그것이 override 결정의 안전 근거다). 그리고 **`qs` 편차는 attempt-008 에서 실행 검증까지 끝났다** — 소비자 경로(`core → typed-rest-client → Util.getUrl → qs.stringify`)에서 `6.15.1` 은 **실제 크래시**하고 `6.16.0` 은 정상이다. 즉 이 override 를 revert 하는 것이 **더 위험한 선택**이 된다.

- **주의(CR-14 · F-15 — attempt-011 폐쇄, 감독 분류)**: 취소·중단 사유를 **watchdog 의 관측**에 기대면 안 된다. API cancel 은 `cancel_event.set()` 과 동시에 그룹을 종료하므로 watchdog(0.2초 폴링)이 사유를 세우기 전에 루프를 빠져나갈 수 있고, 그러면 감독이 취소를 `completed` 로 분류해 **취소 기록이 덮어써진다**(`status=failed, termination=completed, exit_code=-15`). 분류는 `cancel_event.is_set()` + 비정상 종료 코드라는 **사실**로 결정한다 — 정상 완료는 exit 0 이라 오분류되지 않는다. 그리고 **required gate 의 일회성 실패를 재실행으로 지우지 말 것**: 이 결함은 단독 5/5 통과로 나타났다(D-57). 회귀는 두 층이다 — 모듈 수준(결정적)과 API 수준(정착 뷰, 확률적 그물 · R-1).

- **주의(CR-14 · F-14 / 지문 범위 — attempt-010)**: gate 코드 지문은 `docs/`·`.omo/` **접두사**만 제외하므로 **`README.md`(루트)와 `tests/**` 는 지문 안**이다. 따라서 "결과 문서를 쓰는 것만으로는 증거가 낡지 않는다"는 전제는 **`docs/**` 에 쓸 때만** 참이고, README·테스트 계약에 지문이나 결과 수치를 적으면 **그 행위가 증거를 낡게 만든다**(실측: `dd34a76b…` → `003205f2…`, 계약 파일 1개 수정). 반대로 **커밋 자체는 지문을 옮기지 않는다**(내용 hash 기반) — 그래서 "트리 동결 → 커밋 → 20 gate" 순서가 보고서의 SHA 와 지문을 같은 트리로 묶는다. 릴리스 기록은 `docs/**` 에 쓰고, **수치는 그 attempt 의 `gate-report.json` 에서 직접 인용**한다(기억·이전 회차 값 금지). 이 규율을 강제하는 회귀는 아직 없다 — 만들 때는 **게이트 실행 직전**에 만들어야 한다(테스트 추가가 지문을 옮긴다, D-55).
- **주의(CR-14 · F-12 — attempt-009 폐쇄, 번들 provenance)**: 대시보드 번들은 **커밋된 핀** `dashboard/build-provenance.json` 이 기록한 소스 리비전을 BUILD 라벨로 담고, 해석 순서는 `AGK_BUILD_ID` → 핀 → `git short SHA` → null 이다. 이 순서를 되돌리면(핀보다 git 을 앞세우면) **커밋 직후 재빌드가 자산을 통째로 바꿔** 커밋된 후보에서 단일 지문 20/20 을 완주할 수 없다(실측: 자산 22개 교체 + 지문 이동). **핀 ≠ HEAD 는 정상이다** — 핀은 '번들을 만든 소스 리비전'을 기록하는데, 그 커밋이 번들을 담고 있는 커밋과 같을 수 없다(자기 자신을 담을 수 없다는 것이 이 결함의 내용이다). **핀을 맞추려고 amend 하지 말 것** — 같은 루프로 돌아간다. 소스를 바꿔 빌드했으면 핀을 그 리비전으로 갱신해야 한다(회귀 `C14-F12-1/2` 가 형식과 '번들이 핀 값을 담는가'를 검사하며, **핀이 실제 소스와 일치하는지는 자동 검사하지 못한다** — R-2 의 남은 구멍).
- **주의(CR-14 · 생성 산출물과 pre-commit)**: `.pre-commit-config.yaml` 은 `src/antigravity_k/dashboard_dist/` 를 `trailing-whitespace`·`end-of-file-fixer`·`check-added-large-files` 에서 **제외**한다. 이 exclude 를 지우면 훅이 번들을 다시 써서 커밋된 바이트와 빌드 결과가 갈라진다. **`--no-verify` 로 우회하지 말 것**(mypy·ruff·private-key 검사가 함께 풀린다).
- **주의(CR-14 · F-13 — repo 위생)**: `git status` 의 ` M vault_data` 는 **별도 저장소의 런타임 이벤트 로그** 때문이며 코드·산출물은 clean 이다. 게이트 보고서의 `git.dirty: true` 를 "미커밋 변경 있음" 으로 읽으면 틀린다. 판정을 바꾸려면 저장소 구조 결정이 먼저다(D-50).
- **주의(CR-14 · F-10/F-11 — attempt-008 폐쇄, mutation testing 도구)**: `Cannot find TestRunner plugin "vitest"` 는 러너 미설치가 아니라 **탐색 경로** 문제다(pnpm 격리 레이아웃에서 자동 탐색이 core 의 설치 디렉터리만 본다) — `stryker.config.mjs` 의 `plugins` 명시 선언 한 줄이 유일한 방어선이고, 오류 메시지에 끌려 **버전을 올리면** 결함을 고치지 않으면서 도구 체인을 흔든다. 도구가 돌아간 뒤에는 **`--mutate` 를 반복하지 말 것** — 마지막 하나만 적용되어 exit 0 이면서 측정 범위가 반토막난다(쉼표 단일 플래그를 쓸 것). 그리고 `reports/mutation/mutation.json` 은 JsonReporter 미설정으로 **갱신되지 않으니** 현재 결과로 인용하지 말고 신선한 `mutation.html` 을 볼 것.

**주의(CR-14 · F-06 — attempt-006 폐쇄)**: 대시보드 `uuid` 는 **두 곳에** override 로 고정돼 있다(`dashboard/pnpm-workspace.yaml` = 설치·빌드, `dashboard/package.json` `overrides` = SBOM·고지). 한쪽만 지우면 두 진실원이 갈라진다. 또한 **잠금을 바꾼 뒤에는 `pnpm run build` 를 반드시 다시 돌려라** — `src/antigravity_k/dashboard_dist/` 는 추적되는 출하 산출물이므로 재빌드하지 않으면 잠금만 패치되고 출하물에는 옛 의존 코드가 남는다(증인 C 절 · `C14-F06-6` 이 감사). `dependency-audit-dashboard` 는 `--prod --audit-level high` 이므로 그 이하(moderate)는 초록과 공존한다 — "감사 통과 = 의존 안전"으로 읽지 말 것(F-09 가 그 잔여분이다).

**주의(CR-14 · F-03 — attempt-005 폐쇄)**: release 라이선스를 읽는 코드를 고칠 때는 **판독 함수를 하나로 유지**해야 한다. 고지문(`THIRD_PARTY_NOTICES.txt`)과 SBOM(`python.cdx.json`)이 각자 판독하게 되돌리면 같은 실행에서 같은 패키지에 다른 답을 한다(실측: 42건 불일치, 그중 35건은 메타데이터가 있는데도 미상으로 적힌 판독 실패). REL-03 gate 는 **SBOM 만** 읽으므로 고지문 쪽 결함은 gate 초록과 공존한다 — 일치는 `tests/test_cr14_python_license_determinism.py` 가 지키고, 미해결이 `THIRD_PARTY_PROVENANCE.toml` 의 `marker_platform_packages` 를 넘으면 그 테스트가 먼저 깨진다. **추정 라이선스를 `declared_licenses` 에 적어 덮지 말 것.** 문서를 바꿨으면 저장소 사본을 재생성(`uv run --no-sync python -m antigravity_k.engine.release_sbom generate --project-root . --release-root src/antigravity_k/release`)해 **커밋에 포함**한다.
- **주의(CR-14 · F-01 — attempt-003 정정)**: `dashboard-build` 는 **비결정적이지 않다.** 재빌드 전후 `src/antigravity_k/dashboard_dist/` **103 파일이 바이트 단위 동일**하고 코드 지문도 불변이다(실측). `git status` 의 39 D / 93 ?? / 1 M 은 churn 이 아니라 **커밋된 HEAD 번들이 현재 소스보다 낡아서** 생긴 차이다 — 갱신 산출물을 후보와 함께 커밋하면 clean 이 된다. **mermaid 승격 이후에는 이 번들을 HEAD로 되돌리지 말 것**(HEAD 번들은 소스와 다른(취약한) 코드를 담는다). 추적을 계속할지 여부만 post-GA 정책 결정으로 남는다.
- **주의(CR-14 · F-07)**: `clean-machine-runtime` gate 는 `scripts/verify_clean_machine.sh` 의 `REF="HEAD"` 로 **커밋된 HEAD** 를 `git archive`(실측 2877 파일)해 검증한다. 후보가 미커밋이면 이 초록은 **후보가 아닌 다른 코드**를 가리키므로 — 지금 HEAD 번들이 낡은 UI(mermaid 10.6.1)를 담고도 초록인 이유다 — **커밋 뒤 새 SHA 에서 반드시 재실행**하고, 그 전까지 이 PASS 를 후보 근거로 인용하지 않는다. CR-10/CR-11 "stale bundle" blocker 의 원인이다.
- **주의(CR-14 · F-05)**: `Dockerfile` dashboard-builder 스테이지의 `ENV NODE_OPTIONS=--max-old-space-size=4096`를 지우면 `docker-build`가 다시 **콜드 `tsc -b` heap OOM**으로 실패한다(실측 14.5s, 3/3 재현). `node:22.13-alpine`의 기본 V8 힙 상한은 **2096MB이며 컨테이너 메모리와 무관**하게 고정이다 — 호스트에서 빌드가 통과해도 컨테이너는 통과하지 않는다.
- **주의(CR-14 · F-04)**: 라벨 주입 차단은 `mermaidRuntime`의 **두 지점**(정의 중화 + 출력 구조 정화)에 의존한다. 한쪽만 남기면 비컨이 되살아나고(출력 정화만으로는 요청이 이미 나간다), `dashboard/e2e/tests/cr09-offline-assets.spec.ts`의 `C09-03`(주입 노드 0 · **외부 요청 0**) 단언이 그 상시 감시자다. 이 단언을 약화시키는 변경은 F-04를 되돌리는 것이다.
- **주의(CR-14, 결정 D-02)**: release 문서의 파이썬 라이선스는 `importlib.metadata`로 **실행 환경**에서 읽힌다. 같은 후보·같은 lock으로도 환경에 따라 값이 달라지므로, 저장소 사본은 release workflow와 같은 명령(`uv run --isolated --frozen python -m antigravity_k.engine.release_sbom generate --project-root . --release-root src/antigravity_k/release`)으로만 만들어야 한다.
- 다음 작업: CR-01~14 **커밋**(갱신된 `THIRD_PARTY_NOTICES.txt`·`dashboard.cdx.json`·`dashboard_dist` 포함)·clean full SHA 확정 → **그 SHA에서 20-gate 재실행**(특히 `clean-machine-runtime` — F-07) → **F-06(uuid moderate)** → 독립 검토·출시 책임자 배정 → CR-14 attempt-006(C14-03/04/05 채우기). F-02(벤치마크 DB 격리)·F-03(release 라이선스 판독)·F-04(mermaid)·F-05(docker OOM)·F-08(사용량 DB 격리)는 닫혔고 F-01 은 재실측으로 GA blocker 에서 내려갔다(빌드 멱등 — §0-B). 20-gate가 **되돌리기 없이** 단일 지문 `1981bfb5…` 에서 전부 PASS한 상태이므로 **다음 변경은 반드시 그 지문에서 다시 검증**해야 한다(§CR-14 8).
- 공통 blocker: CR-01~14 전부 **독립 검토 미배정**이다. 각 attempt의 `review.md` 패킷과 `repro/` 도구가 준비되어 있고, 검토자는 같은 코드 상태를 지문/SHA로 고정한 뒤 재현·반증한다. 검토 전까지는 REVIEW 상태를 DONE으로 올리지 않는다.
- **CR-14 착수 전 필수 확인(CR-13 인계)은 이행됐다**: 실 릴리스 번들의 `required_gates`를 채우는 경로가 이번에 **닫혔고**, CR-14 평가 번들은 20-gate를 다 돌리지 못해 `reference`로 선언됐다(verify exit 3). 즉 “승인 artifact”는 아직 존재하지 않는다.

### 기존 문서와의 관계

- `docs/11_COMMERCIAL_GA_100_PLAN.md`, `docs/adr/0003-ga-product-scope.md`의 제품 범위와 기존 VAL/RC 조건은 유지한다.
- `docs/14_FINAL_REVIEW_REMEDIATION_PLAN.md`, `15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md`의 RP는 기존 작업 이력이다. 이번 CR은 **새로 발견한 경계 및 현재 후보 재검증**이다. RP DONE으로 CR을 자동 종료하지 않는다.
- 이번 발견의 기대 동작은 본 계획이 정의하며, 실행 상태의 단일 원본은 17번 체크리스트다. 과거 보고서의 PASS, 계획의 존재, 테스트 개수는 현재 후보 승인을 대신하지 않는다.
- 사용자 최신 지시와 적용 AGENTS.md가 우선한다. 실제 충돌은 decision 기록에 사유·영향·새 수용 기준을 남겨 해결한다. 기존 열린 출시 조건을 조용히 삭제하지 않는다.
- Windows/CUDA/native desktop/SaaS/SSO/과금 신설, 디자인 전면 교체, 대규모 엔진 재작성은 범위 밖이다. 기존 구현을 보존하는 최소 변경이 기본이다.

## 2. 변경 불가 계약과 실행 규칙

1. **데이터 식별:** project ID와 conversation ID는 API가 수용한 원문 문자열 기준으로 구별한다. 유니코드 정규화/대소문자 변환/문자 치환으로 다른 ID를 합치지 않는다.
2. **실패 보존:** 저장 실패 시 마지막 정상 파일과 다른 사용자의 변경을 보존한다. 실패를 정상 응답, 빈 대화, 자동 초기화로 숨기지 않는다.
3. **비밀 경계:** API 키는 브라우저 영속 저장소/URL/로그/증거에 남기지 않는다. 서버의 기존 비밀 설정 저장 경로를 재사용하되 권한과 응답 정화를 검증한다. 이번 범위에서 임의 암호화나 신규 Keychain 플랫폼을 만들지 않는다.
4. **실행 경계:** 인증, 승인, OS sandbox는 서로 대체하지 않는다. 생성 코드 실행에 최소 환경·읽기/쓰기 경계·타임아웃을 적용하고 sandbox 불가 시 host fallback하지 않는다.
5. **진실한 화면:** unknown·loading·failed를 healthy·기본값·성공으로 표시하지 않는다. 관측하지 않은 uptime/build/version을 꾸며내지 않는다.
6. **증거:** 실패 재현→수정→회귀→실사용 검증 순서를 기록한다. assertion 삭제, 무근거 skip/xfail, gate 삭제/임계값 완화로 통과시키지 않는다.
7. **협업:** 작업 시작 HEAD/status와 기존 dirty 파일을 기록한다. 다른 작업자의 변경을 되돌리지 않는다. 자신의 파일 소유권을 먼저 확보하고 공용 파일은 직렬 수정한다. `.env` 실제 값, 사용자 vault, 개인 임시 파일로 공격 시험을 하지 않는다.
8. **탐색:** codebase-memory MCP를 먼저 사용한다. 색인이 없으면 index; 부정확/오래된 결과는 현재 소스로 확인한다. 설정/문서는 직접 읽는다.
9. **권한:** 본 계획은 push·공개 배포·자격증명 구매·외부 메시지·사용자 데이터 초기화 권한을 부여하지 않는다. 커밋/통합은 실행 시 사용자 지시와 저장소 규칙을 따른다. CI publish 검증은 dry-run으로 수행한다.
10. **격리:** 회귀는 disposable workspace/DB/auth 설정에서 실행한다. 기존 서버·장기 soak를 종료하지 않는다. 생성한 프로세스와 임시 artifact 소유권을 기록하고 종료/정리한다.

## 3. 작업 순서·소유권·규모

기본은 한 작업씩 수행한다. 명시적으로 병렬 위임받았을 때만 아래 비중복 lane을 사용한다. CR-00 완료 전에 구현하지 않는다. 규모는 난이도이며 시간 보장이 아니다.

| ID | 산출물 | 선행 | 주 소유 영역 | 규모 |
|---|---|---|---|---|
| CR-00 | 기준·소유권·증거 준비 | 없음 | 체크리스트/증거 | S |
| CR-01 | 충돌 없는 대화 저장·기존 파일 이전 | CR-00 | conversation_store/contracts/route/tests | L |
| CR-02 | SessionManager 원자 저장·고유 ID·충돌 처리 | CR-01 | session_manager/직접 호출자/tests | L |
| CR-03 | OS별 sandbox 읽기 허용 경계 | CR-00 | sandbox.py/해당 테스트 | L |
| CR-04 | API shell 정책·최소 env·요청 root 통일 | CR-03 | agent_tools/system_tools/permission 호출부 | L |
| CR-05 | 비밀 설정 계약 및 브라우저 키 제거 | CR-00 | SettingsPage/client/system_api의 settings 함수 | L |
| CR-06 | 설정 로드·저장 실패 상태 | CR-05 | SettingsPage 및 회귀 | M |
| CR-07 | 렌더/청크 실패 복구·404 | CR-00 | App/main/신규 UI boundary | M |
| CR-08 | 설정·팔레트 접근성 | CR-06, CR-07 | SettingsPage/CommandPalette/E2E | M |
| CR-09 | 로컬 표시 자산 번들화 (REVIEW — index.html/ChatMessage/main/package+lock/vite 설정/release 라이선스 정합성) | CR-07 | index.html/ChatMessage/package+lock/vite·vitest 설정/엔진 release 모듈 | M |
| CR-10 | 실제 버전·uptime·unknown 표시 | CR-05, CR-07 | SystemTelemetricsBar/uiStore/system status API | M |
| CR-11 | clean CI/release·의존성 감사 통일 | CR-09 | workflows/audit/build 설정 | L |
| CR-12 | 지원·확장 문서와 운영 계약 정합화 | CR-01~11 DONE; 초안은 CR-00 후 가능 | docs/ga/README/extension README/runbooks | M |
| CR-13 | 불변 증거 번들·manifest 검증 | CR-11 | release_manifest/gate scripts/증거 저장 | L |
| CR-14 | 최종 후보 전면 검증·출시 판정 | CR-01~13 DONE | 고정 후보/출시 증거/최종 리뷰 | L+장시간 |

병렬 허용 예: 데이터(CR-01→02), sandbox(CR-03→04), 설정(CR-05→06), UI shell(CR-07), 문서 준비(CR-12). 현재 lane 상태(2026-09-12): 데이터·sandbox·설정 lane은 CR-06까지 REVIEW로 진행되었고, 자산 lane(CR-09)과 운영 지표 lane(CR-10)도 REVIEW로 마감했다. CR-10은 `App.tsx`·`styles/index.css`·`clientSchema.ts`·`AgentPage.tsx`·`system_api.py`를 직렬로 수정했다(CR-05·CR-06·CR-07·CR-08·CR-09와 같은 파일). 미착수 lane은 CR-11/CR-13이고, CR-11은 이제 CR-09 위에서 시작할 수 있다. CR-05와 CR-10이 `system_api.py`를 동시에 수정하지 않는다(CR-10이 이미 마감). CR-07/09가 App/main을 수정할 경우 하나의 소유자 아래 직렬 통합한다. `sandbox.py` 수정은 CR-03 소유자만 하고 CR-04가 필요 변경을 요청한다. 잠금 유틸 공용화를 CR-01/02에서 도입한다면 동일 소유자가 담당한다.

승인자 역할: 조정자(통합·범위), 구현자(수정·증거), 독립 검토자(다른 실행 맥락에서 재현·검토), 출시 책임자(지원 범위·GO). 에이전트 독립 검토는 외부 법무/제품 책임자의 실제 승인을 대체하지 않는다.

## 4. 상세 작업 카드

### CR-00 — 현재 기준과 재현 분류

**의도:** 과거 결함을 중복 수정하거나 다른 작업자의 변경을 덮어쓰지 않게 한다.

- 읽을 것: BASELINE, 본 계획, 체크리스트, ADR-0003, 현재 RP 상태. HEAD/status, OS/arch/Python/uv/Node/pnpm/browser/sandbox backend, lockfile hash를 기록한다. 환경변수 전체 덤프 금지.
- 각 발견을 STILL_OPEN / ALREADY_FIXED / UNVERIFIED로 분류한다. ALREADY_FIXED도 현재 SHA의 같은 수용 시험+독립 검토가 있어야 해당 CR을 종료한다.
- 증거 루트 `.omo/evidence/commercial-reliability/CR-XX/attempt-NNN/`를 만든다. 새 경로이며 과거 RP artifact를 덮어쓰지 않는다. 장기 보존용 증거팩은 CR-13에서 별도 생성한다.
- 원문에 없는 후보/테스트 결과를 추정하지 않는다. 외부 조건 부족은 단계별 BLOCKED_EXTERNAL로 적는다.

**수용 기준:** C00-01 기준 SHA/dirty 목록/환경/lock hash; C00-02 모든 발견의 최신 재현 분류; C00-03 작업 소유권/의존성/증거 위치; C00-04 기존 사용자 변경과 실제 비밀 비접근 확인.

### CR-01 — 대화 ID 충돌 제거와 기존 저장 형식 이전

**읽을 코드:** `src/antigravity_k/engine/conversation_store.py`의 `_path_for`, `_refresh_latest`, 생성/append/compact/lock/persist; `api/contracts/conversation.py`, `api/routes/conversation_api.py`; 기존 `tests/test_fr05_conversation_authoritative_reads.py`, `test_conversation_store_ctx01.py`, `test_fr05_api_workers.py`.

**고정 설계:** 원문 UTF-8 project ID, conversation ID를 각각 SHA-256 전체 hex로 식별하는 버전된 `v2/<project-hash>/<conversation-hash>.json` 레이아웃. 구분된 디렉터리와 레코드 원문 ID 검증을 함께 사용한다. hash로 사용자 ID 자체를 바꾸지 않는다. 잠금 키도 동일한 v2 identity를 따른다.

1. `a.b`/`a_b`, 64자 공통 접두+다른 후미, project ID 충돌, 한글/대소문자 구분을 실패 시험으로 만든다.
2. 모든 읽기에서 저장 레코드 ID가 요청 ID와 정확히 일치하는지 확인한다. 불일치/손상은 명시적 integrity 오류로 반환하고 빈 정상 대화로 복구하지 않는다.
3. 기존 포맷은 **통제된 1회 이전**한다. 서비스 정지→백업→dry-run 인벤토리→레코드 내부 ID 기준 이동 계획→검증→원자 생성 순서. 원본 파일은 보존한다. 경로 이름으로 ID를 역추정하지 않는다. 모호/손상/중복 상충 데이터는 덮어쓰지 않고 충돌 목록과 비성공 종료를 낸다.
4. 이전 완료 전 자동 쓰기를 허용하지 않는 시작/명령 계약을 구현한다. 완료 마커는 모든 파일 검증 후 기록한다. 중단 후 재실행이 멱등이고 이미 동일한 v2 파일은 재작성하지 않는다. 구버전·신버전 동시 writer는 지원하지 않음을 운영 문서에 명시한다.
5. 기존 revision CAS, authoritative read, flock, 정상 압축/append 동작을 보존한다. 공용 API 오류는 문서화하고 프론트가 다른 대화로 자동 대체하지 않게 한다.

**신규 작성 대상:** `tests/test_cr01_conversation_identity.py`, `scripts/migrate_conversation_storage.py`(기존 적합 명령이 있으면 확장 가능; 실제 경로를 체크리스트에 기록).

**수용 기준:** C01-01 ID 4종 충돌 시험 분리; C01-02 실제 API GET/append/compact의 ID·revision 일치 및 integrity 오류; C01-03 dry-run 무변경·원본 보존·중단/재시작 멱등 이전; C01-04 상충/손상 이전 거부 및 완료 마커 미생성; C01-05 실제 worker 2개+재시작 CAS 회귀; C01-06 백업 복구/구버전 복귀 절차와 독립 검토. 롤백은 구버전이 v2를 읽을 수 있다고 가정하지 않으며 서비스 중단과 승인된 백업 복원으로 한다.

### CR-02 — 세션 저장 손실·ID 충돌·동시 writer 보호

**읽을 코드:** `engine/session_manager.py`의 start/save/load/latest 조회와 `_save_session`, `api/dependencies.py`의 프로젝트 runtime 생성; CR-01의 원자 저장/잠금 관례.

- 신규 ID에는 프로젝트 식별 정보와 UUID를 사용한다. 시간은 metadata이며 유일성 근거가 아니다. 기존 ID 파일의 resume/list는 계속 가능해야 한다.
- 직렬화 완료→동일 디렉터리 고유 임시 파일→flush/fsync→atomic replace→지원 OS에서 디렉터리 fsync 순으로 저장한다. replace 전 실패에는 마지막 정상 파일 바이트를 보존한다. replace 후 디렉터리 fsync 실패는 새 완전한 JSON이 이미 보일 수 있으므로 내구성 불확실 오류를 전달하고, 오래된 데이터로 되돌려 동시 변경을 덮어쓰지 않는다. 재조회로 실제 저장 상태를 확인하도록 한다. 임시 파일 권한은 비공개, 실패 잔재는 자신이 만든 것만 정리한다.
- 저장 실패를 명시적 예외/실패 계약으로 호출자에 전달한다. UI/API/CLI가 저장 성공으로 응답하거나 세션을 비워 재생성하지 않도록 직접 호출자를 추적한다.
- 같은 세션을 두 프로세스가 읽고 쓰는 경우 per-session process lock + revision 비교로 stale write를 거부한다. 잠금만으로 오래된 메모리 전체를 덮어쓰는 문제를 해결했다고 보지 않는다. 구형 레코드는 잠금 안에서 revision 기본값 0으로 읽는다. API 오류 계약 변경이 있으면 소비자 회귀를 함께 수정한다.
- 구형 latest 조회가 새 ID suffix를 시간으로 해석하지 않게 한다. metadata와 실제 식별자로 선택한다.

**신규 테스트:** `tests/test_cr02_session_durability.py`. 합성 파일에서 dump/write/fsync/replace 실패, 같은 시각 100회 신규 생성, 두 독립 프로세스 stale save, 정상 restart/resume를 시험한다.

**수용 기준:** C02-01 신규 ID 유일·구형 resume; C02-02 replace 전 실패 시 원본 동일·replace 후 fsync 실패 시 완전한 파일과 불확실 오류; C02-03 호출자 실패 전달·거짓 성공 없음; C02-04 multiprocess stale write 거부; C02-05 재시작·목록·revision 및 임시 잔재 확인; C02-06 독립 검토. power-loss 내구성을 실제 전원 차단 없이 보증하지 않는다.

### CR-03 — 실제 sandbox 읽기 경계

**읽을 코드:** `engine/sandbox.py`의 `run_sandboxed_argv`, `SandboxRunner`와 macOS/Linux backend; `tests/test_sandbox_isolation.py`, `test_fr01_agent_execution_isolation.py`, `test_sandbox.py`.

- restrict_reads는 허용 목록으로 구현한다. workspace, 검증된 런타임 라이브러리/실행파일, 작업 전용 임시 디렉터리만 허용한다. `/var/folders`, HOME 전체, 전체 `/tmp` 허용을 런타임 편의로 추가하지 않는다.
- Python 실행파일·venv·표준 라이브러리·필수 OS 파일 경로를 실제 해석해 최소 허용한다. 런타임 구성에 필요한 예외는 경로와 이유를 문서화한다. 심볼릭 링크의 canonical target과 자식 프로세스에도 동일 경계를 적용한다.
- `/var`와 `/private/var` alias, HOME, `/tmp`, `/var/tmp`, 형제 workspace, symlink sentinel을 합성 fixture로 검사한다. 전용 임시 HOME/TMP를 제공한다.
- sandbox 불가/설정 비활성/정책 생성 실패는 실행 전에 fail-closed. network 제한, 쓰기 제한, timeout/process-group/output quota를 유지한다.
- 지원할 OS backend에서는 실제 실행 시험 필수. 해당 OS가 없으면 그 지원 행은 검증 대기로 유지하며 mock 통과로 승격하지 않는다.

**신규 테스트:** `tests/test_cr03_sandbox_read_boundary.py`.

**수용 기준:** C03-01 workspace 정상 Python/pytest 성공; C03-02 모든 외부 sentinel 읽기/쓰기 거부; C03-03 child/symlink/alias 동일 거부; C03-04 최소 env·전용 tmp·network·timeout 회귀; C03-05 backend unavailable 실행 0회; C03-06 OS별 실측/예외 목록/독립 보안 검토.

### CR-04 — API shell도 동일한 실행·승인 경계

**읽을 코드:** `api/routes/agent_tools.py`의 `run_shell`, `_permission_gate`, `_resolve_project_cwd`; `tools/system_tools.py`의 모델 bash 경로; `api/project_binding.py`, `engine/permission_gate.py`, CR-03 공용 실행 함수.

- `mode="auto-pilot"` 고정을 제거하고 현재 요청의 기존 권한 모드와 snapshot project root를 사용한다. 실행 직전에 전역 active project를 다시 읽어 작업 root를 바꾸지 않는다.
- 이 동기 API는 기존 permission 결정이 ASK이면 **실행 없이 403 승인 필요 오류**를 반환한다. 별도 승인 workflow가 없는 상태에서 allow로 승격하지 않는다. DENY도 실행 0회다. 기존 승인 시스템을 붙이는 확대 작업은 별도 명세가 필요하다.
- ALLOW일 때도 CR-03 제한 읽기와 모델 shell의 최소 env를 재사용한다. provider key·서버 PIN/token 관련 환경을 상속하지 않는다. sandbox 비활성도 host raw 실행으로 대체하지 않는다.
- 기존 정상 응답 모양을 보존하고 정책 거부·sandbox unavailable·명령 실패·timeout을 구분한다. 로그/HTTP 오류에 실행 환경 전체를 포함하지 않는다.

**신규 테스트:** `tests/test_cr04_shell_api_boundary.py`. 실제 인증 앱/HTTP를 통한 합성 printenv, ASK/DENY 실행 marker 없음, A/B 프로젝트 전환 중 실행 root 고정, 명령 실패/timeout을 검증한다. handler 단독 검증만으로 끝내지 않는다.

**수용 기준:** C04-01 auth+ALLOW 정상 실행; C04-02 ASK/DENY 실행 0회; C04-03 합성 secret 비노출; C04-04 CR-03 경계·backend fail-closed; C04-05 요청 root 고정·실패 응답·기존 도구 회귀; C04-06 독립 보안 검토.

### CR-05 — API 키의 브라우저 영속 제거와 명시적 설정 계약

**읽을 코드:** `dashboard/src/pages/SettingsPage.tsx`, `api/client.ts`의 fetch/saveSettings와 schema, `src/antigravity_k/api/routes/system_api.py`의 GET settings/POST settings env, 설정 저장과 secret 정화 유틸.

- 일반 preference와 API 키를 분리한다. 브라우저에는 허용 목록의 비밀 아닌 preference만 저장한다. 키는 입력 동안 메모리에만 존재하고 성공 저장·페이지 이탈에 지운다. sessionStorage/IndexedDB로 이동하는 방식은 해결이 아니다.
- GET은 키 원문/부분값 대신 provider별 `configured` 상태만 반환한다. POST는 **누락 키=유지**, **비어 있는 입력=전송하지 않음**, **명시적 삭제 행동=해당 키 삭제**, **비어 있지 않은 새 값=교체**로 고정한다. 빈 입력 때문에 기존 서버 키를 삭제하지 않는다. wire 필드 이름은 기존 계약을 읽고 decision에 고정하되 이 의미는 바꾸지 않는다.
- 저장 전/후 로그와 응답에 원문 키가 없는지 합성 canary로 검증한다. 서버 기존 비밀 설정 파일은 제한 권한과 원자적 갱신을 유지/보완한다. 일반 설정 저장이 전체 secret map을 덮어쓰지 않게 한다.
- 기존 `agk_user_settings:v1` 및 `agk_user_settings`는 앱 시작 시 허용된 비밀 아닌 키만 남기는 idempotent 정화 대상으로 한다. localStorage 접근 불가/잘못된 JSON도 앱을 중단하지 않는다. 브라우저에만 있던 키는 자동 전송하지 않으며, 제거 후 재입력이 필요할 수 있음을 일반 안내한다. 값을 안내/로그에 포함하지 않는다.
- masked placeholder를 서버로 보내거나 원문을 폼으로 재주입하지 않는다. 성공 저장 후 상태만 다시 조회한다.

**신규 테스트:** `tests/test_cr05_settings_secret_contract.py`, `dashboard/e2e/tests/cr05-settings-secrets.spec.ts`; 기존 SettingsPage 테스트를 확장한다.

**수용 기준:** C05-01 저장/재방문/실패 후 브라우저 영속 키 0; C05-02 legacy 두 키 정화·잘못된 JSON/접근 거부 처리; C05-03 keep/replace/explicit-delete 각각 실제 API 확인; C05-04 응답/로그 원문 비노출·서버 파일 보호; C05-05 fake key로 실제 브라우저 저장·재로드·입력 지움; C05-06 독립 보안 검토.

### CR-06 — 설정 상태가 서버의 진실을 반영

CR-05와 같은 파일을 직렬 수정한다. 상태는 loading → ready 또는 load-error; ready → saving → ready 또는 save-error로 구분한다. 초기 GET 실패 중 저장은 비활성화하고 오류/재시도 버튼을 보인다. 서버가 관리하는 일반 설정은 GET 결과가 우선이며 브라우저 오래된 값이 조용히 덮어쓰지 않게 한다. 0 예산/0 limit 같은 유효한 값에 `||` 기본값을 적용하지 않는다.

서버 저장 실패 시 비밀 아닌 입력은 유지하고 실패를 알린다. 키는 CR-05의 메모리 수명 규칙을 따른다. 연속 클릭은 중복 요청을 만들지 않는다. 오류 복구 후 실제 저장값을 재조회한다. 인증 실패는 기존 PIN 흐름으로 연결한다.

**신규 E2E:** `dashboard/e2e/tests/cr06-settings-errors.spec.ts`(500/timeout은 결정적 실패 주입, 성공은 실제 서버). **수용 기준:** C06-01 loading/error 저장 금지; C06-02 GET 실패→재시도 복구; C06-03 POST 실패/401/중복 클릭 처리; C06-04 정상 저장·재조회·0값 보존; C06-05 source/Vitest/실브라우저 증거.

### CR-07 — 화면 오류 복구와 잘못된 경로

`dashboard/src/App.tsx`, `main.tsx`의 route 구성을 읽는다. 최상위 최후 boundary와 route 수준 복구 UI를 최소 구조로 도입한다. Suspense는 loading만 담당한다. lazy chunk 실패, render throw에 오류 식별자·재시도/안전 재로드를 제공하고 stack/secret을 화면에 노출하지 않는다. 오류 때문에 대화 store/local history를 clear하지 않는다. 404는 명확한 안내와 홈 복귀를 제공한다. 로그인·전역 shell까지 모두 fallback 안에 묻히지 않게 한다.

**신규 E2E:** `dashboard/e2e/tests/cr07-route-recovery.spec.ts`. chunk request 차단→실패 화면→해제 후 복구, renderer fixture 예외, 잘못된 deep link, 기존 대화 보존을 확인한다. **수용 기준:** C07-01 chunk 실패 복구; C07-02 render 오류 경계; C07-03 404/뒤로가기; C07-04 대화·인증 상태 보존; C07-05 실제 production build 브라우저 확인.

### CR-08 — 설정과 명령 팔레트 키보드/접근성

기존 디자인 token/layout을 유지한다. provider별 입력에 고유 label/accessible name을 연결한다. 팔레트는 dialog의 modal 의미, 초기 focus, Tab/Shift+Tab 순환, Esc 닫기, 열기 전 focus 복귀, 배경 비활성 계약을 충족한다. 이미 검증된 dialog primitive가 있으면 재사용한다. 검색 방향키·Enter 실행·한글 IME 조합 중 Enter·비동기 결과 경합을 보존한다. 모달이 아닐 때 background inert를 남기지 않는다.

**신규 E2E:** `dashboard/e2e/tests/cr08-keyboard-accessibility.spec.ts`; 기존 `accessibility.spec.ts` 회귀. **수용 기준:** C08-01 provider accessible name; C08-02 키보드 modal 격리/복귀; C08-03 IME/검색/Enter/ESC 동작; C08-04 데스크톱/좁은 화면 수동 확인과 axe 심각·치명 오류 0; C08-05 기존 접근성 gate 보존. axe 통과를 전체 WCAG 인증이라 표현하지 않는다.

### CR-09 — 오프라인 로컬 표시 자산

`dashboard/index.html`, `components/Chat/ChatMessage.tsx`, Vite/package/lock을 읽고 필수 fonts/CSS/Mermaid를 로컬 번들 또는 시스템 폰트로 교체한다. 필수 렌더링에 third-party CDN을 요구하지 않는다. 기존 sanitize와 Mermaid 보안 설정을 약화하지 않는다. 버전/lock/라이선스 notice를 함께 갱신하고 새 대형 동기 script 대신 필요한 화면에서 로드한다. 선택 외부 링크나 사용자가 선택한 cloud provider를 전체 차단하는 작업은 아니다.

**신규 E2E:** `dashboard/e2e/tests/cr09-offline-assets.spec.ts`. 앱 원점/로컬 backend만 허용하고 외부 네트워크 차단 상태에서 새 캐시 없는 컨텍스트로 시작해 Chat/Settings/Markdown/Mermaid/코드 표시를 확인한다. **수용 기준:** C09-01 필수 CDN 요청 0; C09-02 cold cache 로컬 표시; C09-03 sanitize/악성 diagram 회귀; C09-04 lock/notice/빌드 일치; C09-05 브라우저 network/console 증거. 실제 cloud 추론 offline 지원을 주장하지 않는다.

### CR-10 — 운영 지표와 빌드 신뢰성

`components/Layout/SystemTelemetricsBar.tsx`, `stores/uiStore.ts`, system status API/schema, package의 버전 원본을 추적한다. BUILD는 실제 실행 배포 버전/빌드 식별자를 사용하고 하드코딩을 제거한다. UPTIME은 **현재 API 서버 프로세스 가동 시간**으로 정의하고 monotonic elapsed를 사용한다. 호스트 uptime·탭 열린 시간과 혼합하지 않는다. 다중 worker별 차이는 process-instance 식별 또는 명시적 의미로 표시한다.

값 부재/네트워크 단절/오래된 마지막 값은 UNKNOWN/연결 끊김과 관측 시각으로 표현한다. CPU=0, uptime=0은 유효값이며 누락과 구분한다. 정보 없는 healthy 기본값 true를 제거한다. 고정 CTRL 문구는 실제 상태가 아니면 운영 지표에서 제거한다. 서버/번들 버전이 다르면 오해 없게 구분한다.

**신규 테스트:** `tests/test_cr10_runtime_metadata.py`, `dashboard/e2e/tests/cr10-telemetry.spec.ts`. **수용 기준:** C10-01 실제 버전 연결; C10-02 서버 재시작 후 uptime reset; C10-03 unknown/stale/disconnect/0 구분; C10-04 화면과 API 대조; C10-05 하드코딩 제거·빌드 provenance 기록.

### CR-11 — clean CI/release와 실제 의존성 감사

`.github/workflows/release.yml`, `ci.yml`, `scripts/audit_python_dependencies.sh`, `scripts/commercial_ga_gates.json`, `Dockerfile`, `pyproject.toml`, dashboard packageManager/lock을 읽는다.

- src-layout 모듈 실행 전에 frozen 환경으로 프로젝트를 설치한다. 개인 editable install/PYTHONPATH 우연성에 기대지 않는다. build 필요 의존성과 런타임의 순서를 명시한다. SBOM 생성→wheel/sdist 빌드→설치/검증 순환이 없는지 확인한다.
- CI Python 감사는 기존 lock-export 스크립트를 재사용한다. 출하 base/선택 extras별 실제 감사 대상을 기록하고 해당 릴리스가 지원하지 않는 extra까지 자동 지원 선언하지 않는다. 감사 인프라 오류와 취약점 발견을 모두 비성공으로 다루되 이유는 구분한다.
- Node/pnpm 조합을 packageManager 및 pnpm 실제 engine 요구와 일치시킨다. 당시 Node 20 vs pnpm 11 호환 의심은 설치 실측으로 확정한 후 수정한다. CI·Docker·문서 간 동일 지원 조합을 사용한다.
- test/build job에서 새 dashboard를 패키징하고 fresh wheel의 번들 hash를 비교한다. checkout에 오래된 dist가 있어도 성공처럼 포장하지 않는다.
- GitHub release는 dry-run만 검증한다. publish/upload 단계는 별도 권한이며 테스트 중 실행하지 않는다.

**신규 테스트:** `tests/test_cr11_release_bootstrap.py` 또는 별도 clean-run harness. 설정 문자열 검사만으로 완료하지 않는다. **수용 기준:** C11-01 신규 venv에서 내부 모듈 실행; C11-02 cache 없는 frozen dashboard 설치/build; C11-03 base/출하 extras 감사 입력 기록·음성 입력 거부; C11-04 wheel/sdist 저장소 밖 CLI/API/auth 실행; C11-05 번들 출처·Node 조합·dry-run 원문; C11-06 기존 gate를 보존한 독립 검토.

### CR-12 — 지원·운영·VS Code 문구 정합화

`docs/ga/*`, ADR-0003, README, RELEASE_POLICY, 운영 가이드, `vscode-extension/README.md`와 실제 extension 동작을 대조한다. 확장 범위는 context-sync companion으로 명시하고 **이번 계획에서는 재연결 timer/offline queue를 신설하지 않는다**. 자동 재연결·offline 표현은 다음 editor event 재시도라는 실제 계약에 맞춘다. 새 기능이 필요하면 별도 작업이다.

플랫폼/provider별 target/experimental/supported, 실행 증거 SHA, 지원 책임자와 미완료 승인을 표로 유지한다. 초기 산출물은 준비 완료일 뿐 승인 완료가 아니다. 외부 승인 없음은 BLOCKED_EXTERNAL로 보존한다. CR-01 이전/복원, CR-02 저장 오류 대응, 키 정화 후 재입력, sandbox unavailable, 신규 설치/업그레이드/rollback 절차를 실제 작업 결과가 나올 때 갱신한다. 사전 문구 준비는 독립 실행 가능하지만 최종 내용은 관련 CR의 계약 확정 후 검토한다.

**수용 기준:** C12-01 기능/지원 주장→증거 매핑; C12-02 확장 README 실제 범위; C12-03 데이터 이전·저장실패·키·sandbox runbook 초안과 결과 반영; C12-04 승인 누락/담당자/요청 범위 명시; C12-05 과거 RP와 새 CR 상태 분리·문서 링크 유효. C12 DONE은 문서 준비/정합성 완료이며 외부 승인 및 최종 운영 리허설은 C14에서 별도로 판정한다.

### CR-13 — 이전 후보 증거 재사용 방지와 불변 artifact

`release_manifest_verify.py`, `ga_gate.py`, `ga_gate_verify.py`, `commercial_ga_gates.json`, RP-13 manifest 구조를 읽는다. 증거 수집용 스크립트를 준비하는 작업이며 최종 릴리스 증거는 CR-14에서 생성한다.

- artifact를 번들 내부 상대 경로로 복사한 뒤 hash/size를 계산한다. 사용자 `/tmp`, 현재 `data/benchmark_results.json`, 절대 host 경로를 유일 근거로 참조하지 않는다. 원본 변동이 이미 검증된 bundle을 바꾸지 않아야 한다.
- manifest에 schema, full source SHA, lockfile hash, 도구/환경, 명령, 시작·종료 시각, exit, gate ID/summary, model ID/quantization/hardware, artifact hash를 기록한다. 개인정보/secret 제거 후 최종 hash를 계산한다.
- 검증기는 외부 경로/`..`/symlink 탈출, 누락, 중복, hash·size 불일치, 후보 SHA 불일치, 필수 gate 누락/실패/짧은 soak를 거부한다. manifest 자체 hash를 자기 자신에 넣는 순환을 만들지 않는다.
- 보고서의 주장과 원문을 연결한다. metadata만 PASS로 바꾸거나 옛 로그 source SHA를 덮어쓰지 않는다. 해시가 같다고 과거 실행이 새 코드 실행으로 바뀌지 않는다.
- 별도 위치에 번들을 복사하여 원래 `/tmp` 참조 없이 검증 가능한지 확인한다. 실패한 attempt도 보존하고 새 attempt를 만든다.

**신규 테스트:** `tests/test_cr13_evidence_bundle.py`; 기존 `test_fr11_gate_verifier.py`, `test_fr13_release_manifest.py` 유지. **수용 기준:** C13-01 상대 경로 독립 번들; C13-02 변조/누락/탈출/중복 거부; C13-03 SHA/gate/soak 음성 시나리오; C13-04 외부 원본 변경에도 번들 유지·다른 위치 재검증; C13-05 redaction/hash 순서·원문 연결·독립 검토.

### CR-14 — 최종 후보 전체 검증과 GO/NO-GO

모든 구현/문서 작업을 통합한 뒤 **깨끗한 코드 후보 full SHA**를 고정한다. 기존 RP의 미완료 VAL/RC 조건도 포함한 통합 gate inventory를 먼저 확정한다. 현재 gate manifest와 새 CR 회귀/E2E를 모두 포함하며 gate 수는 실행 시 목록을 기준으로 기록한다. 숫자 20에 맞추려고 새 검사를 제외하지 않는다.

1. 전체 Python tests·정적 분석·dashboard lint/typecheck/Vitest/build·새 E2E·기존 인증/프로젝트 전환/대화 압축/접근성 회귀를 실행한다. 지원 sandbox OS의 실제 차단도 포함한다.
2. 동일 후보에서 빌드한 wheel/container로 새 설치→로그인→프로젝트 A/B→대화/실도구→취소/재개→압축→프로세스 재시작→이력 복구를 수행한다. 브라우저가 읽는 bundle hash를 manifest와 대조한다.
3. 데이터 이전은 구형 fixture와 **실제 이전 출시 artifact가 있으면 그 artifact**로 검증한다. 버전 라벨만 0.0.9로 바꾸는 시뮬레이션은 실제 이전 버전 rollback 증거가 아니다. artifact가 없으면 그 항목은 미검증/외부 조건으로 기록한다.
4. 기존 28,800초 soak 요건을 현재 후보에서 수행한다. 8시간 내 프로세스 생존만이 아니라 완료 작업 수, 오류, 데이터 손실/중복, CAS 충돌 처리, RSS 추이, 지연 분포를 기록한다. 허용 임계값은 기존 VAL 계획을 먼저 계승하고 빠진 기준은 측정 시작 전 decision에 고정한다. 종료 후 결과를 보고 임계값을 조정하지 않는다.
5. 마케팅 대상 local/provider를 실제 호출해 모델 ID/버전/하드웨어/입력·출력 결과와 도구 행동을 기록한다. cloud 자격증명이 없으면 mock으로 승격하지 않는다. 최초 GA를 local-only로 축소하려면 제품 책임자 승인과 ADR/지원표 변경, 기존 cloud gate의 명시적 범위 처리가 필요하다.
6. 모델 실패→성공 metrics 혼선과 RAG 색인 실패 복구를 합성 장애로 확인한다(BASELINE의 미확정 관찰). 새 재현 결함은 별도 CR 확장으로 등록하고 후보를 해제한다.
7. 경쟁 제품 성능 동등성을 주장하려면 동일 held-out tasks, 사전 scoring, 반복 수, timeout/budget/model 조건을 고정한 비교를 별도로 수행한다. 시행하지 않으면 '동등/우월' 주장을 제거한다. 이는 로컬 GA 기능 시험을 대신하지 않는다.
8. 새 결함 수정으로 코드/lock/workflow가 바뀌면 새 후보에서 영향 gate와 최종 통합 증거를 갱신한다. 최종 승인은 보고서 full SHA와 artifact source SHA가 같은 경우만 가능하다. 결과 문서 커밋은 코드 후보와 별도로 기록하고 동일한 코드 tree인지 증명한다.

**수용 기준:** C14-01 full SHA/clean/통합 gate inventory; C14-02 모든 required gate 현재 후보 PASS; C14-03 같은 bundle 실제 UI+API+도구+restart; C14-04 이전/업그레이드/복구 실측 및 제한; C14-05 28,800초·실 provider 조건 충족; C14-06 미확정 실패 경로 조사/신규 blocker 0; C14-07 지원·외부 승인·주장 근거 완료; C14-08 독립 code/security/QA 검토 및 출시 책임자 GO 또는 근거 있는 NO-GO 기록.

**판정:** P1 미해결, required gate 실패/미실행, 필수 외부 승인 부재, source mismatch 중 하나라도 있으면 NO-GO. NO-GO 기록 완료는 평가 작업 산출물이며 GA 승인이나 CR-14 DONE으로 계산하지 않는다. DEFERRED는 선택·범위 밖 항목에만 사용하고 필수 항목의 우회 수단으로 쓰지 않는다.

**attempt-013 결과(2026-09-13, 최신):** **attempt-012 이 한계(R-6)로 남긴 관측을 뿌리까지 파서 검증 장치 결함 3건(F-18·F-19·F-21)과 그 사이에 숨어 있던 테스트 격리 결함(F-20)을 닫았다. 게이트 인벤토리 20 → 21, `uv.lock` 변경, 그리고 "이전 초록이 무엇을 증명했는가"의 해석이 바뀌었다.**

**(a) F-18 — 게이트가 lock 이 아니라 실행자의 셸을 검증하고 있었다.** 게이트는 `uv run --isolated --frozen <tool>` 이면 hermetic 하다고 전제했지만, dev 도구는 `[project.optional-dependencies].dev` 에 있고 `uv run` 은 그 extra 를 기본 설치하지 **않는다** — 임시환경(64 패키지)에는 `pytest`·`ruff`·`mypy`·`basedpyright` 가 없고(`find_spec('pytest') is None` 확인), 도구가 환경에 없으면 uv 는 **호출 셸의 PATH** 에서 찾는다(`VIRTUAL_ENV` 는 무관 — PATH 우선순위가 결정했다). 증거는 같은 `uv.lock` sha256 으로 두 번 돌린 게이트 보고서다: attempt-011 은 `.../.venv/bin/python3` + pytest 9.1.1 + plugins(cov/asyncio/anyio) + 수집 6213 + skipped 13, attempt-012 는 `/Users/mr.k/miniforge3/bin/python3.13` + pytest 9.0.3 + plugins(cov/anyio/asyncio/typeguard/hypothesis) + 수집 6221 + skipped 6. 차이의 정체는 정확히 `TestAgainstInstalled` 7건(그 클래스의 가드가 `import trl; import unsloth` 다) — attempt-012 가 원인 미특정으로 남긴 R-6 의 답이다. 증인은 PATH 앞에 가짜 도구를 두고 게이트를 그대로 실행한다: 수정 전 **HIJACKED 4/4**(가짜가 실행됨), 수정 후 pinned. **같은 결함이 범주를 가리지 않았다** — 보안 게이트의 `bandit` 은 pyproject 에 **선언조차 없어** conda base 의 `bandit 1.9.4` 를 실행하고 있었다. 수정: 게이트에 필요한 extra 명시(`--extra dev --extra rag`, `security-bandit` 은 `--extra dev`) + `bandit` 을 dev extra 에 선언하고 `uv lock`(추가: bandit 1.9.4·stevedore 5.9.1, 그 외 0).

**(b) F-19 — lock 이 정의하는 환경에서는 스위트가 실패했다.** 게이트를 실제로 고정하자마자 `python-tests` 가 `VectorStore requires chromadb but it is unavailable` 로 실패했다(dev extra 만: 해당 세 파일 `10 failed / 25 passed`, dev+rag: `35 passed`). chromadb 는 `rag` extra 에 있고 ambient 환경에는 항상 있었기 때문에 20/20 초록이 나왔다 — 즉 그 초록은 "머신에 rag extra 가 설치돼 있었다"에 의존했다. 제품 코드는 바꾸지 않았다: `VectorStore` 는 chromadb 가 없으면 의도적으로 명확히 거부하고 `gbrain` 은 강등한다.

**(c) F-20 — 그 사이에 숨어 있던 순서 의존.** 새 지문에서 스위트를 다시 돌리자 `TestWsGateIntegration` 5건이 429로 죽었고 단독 실행은 통과했다. 재실행으로 덮지 않고 **순서만 다른 A/B** 로 확정했다: WS 단독 `7 passed` vs 로그인 5회 태우는 버너+WS `5 failed(429)`, 그리고 `test_auth.py`+`test_auth_policy_truth_table.py` `1 failed(403)`. 원인은 키가 '호출자 IP'인 전역 상태 기계가 둘(slowapi `5/minute`, credential gate lockout)이고 TestClient 는 항상 같은 주소라는 것이다. 핵심은 **두 누수가 서로를 가려 왔다는 사실**이다 — 레이트리밋이 먼저 차서 429로 끝나면 실패가 임계까지 쌓이지 않아 lockout 이 켜지지 않는다. 기존 대응은 개별 테스트의 우회였고(429만 처리) 실제로 도착한 403 은 막지 못했다. 수정: `tests/conftest.py::_reset_login_security_state`(autouse) 가 두 기계를 테스트 경계마다 비우고, 개별 우회는 제거해 그 테스트를 격리 계약의 증인으로 바꿨다.

**(d) F-21 — required 게이트가 머신 부하로 깨졌다.** 고립 실행에서 2250~2265ms 인 성능 테스트가 6200여 개를 도는 같은 프로세스 안에서 6084ms(임계값 6000ms, `AssertionError`)였다. 그 모듈의 안내는 "기본: slow 마커로 skip" 이라고 적고 있었지만 deselect 하는 설정은 **없다**(`addopts`·collection hook 부재). 검사를 빼지 않고 **옮겼다**: `python-tests` 는 `-m "not benchmark"`, **신규 required 게이트 `python-benchmark`** 가 `-m benchmark` 로 조용한 프로세스에서 돈다(16 passed / 16.9s). 기존 `TestCandidateGateInventory` 가 21 을 감지해 실패한 것은 계약이 작동한 것이고, 개수 고정을 **목록 고정**으로 강화했다.

**(e) 검증** — 계약 3종 신규(9건) + 이빨 확인(게이트 `--extra` 제거 → 3 failed · `security-bandit` 의 extra 제거 → 2 failed · conftest 무력화 → 1 failed · 성능 마커 제거 → 3 failed · 인벤토리 목록 편집 → 1 failed, 원복은 shasum 일치) · **required gate 21/21 을 커밋된 후보 `0593dd27` 에서 되돌리기 0회로 단일 지문 `2c5a15c8…` 에서 완주**(python-tests **6174 passed / 40 skipped / 16 deselected** 506.6s · python-benchmark 16 passed · dashboard 81 files/849 · docker 223.0s · clean-machine 39.1s `ref: HEAD` · `data/` 드리프트 0 · 실행 후 지문 재측정 동일). 코드를 측정 **전에** 커밋해 HEAD 의존 재실행이 필요 없었다(D-52).

**(f) 해석이 바뀐 부분(정직 기록)** — **attempt-001~012 의 20/20 은 ambient 도구로 측정됐다.** 그 초록은 "스위트가 통과했다"로는 유효하고 "lock 이 검증됐다"로는 유효하지 않았다. F-01~F-17 폐쇄의 근거는 코드 계약이라 영향받지 않는다. 한계: R-8(다른 extra 의 조건부 수집 미감사 — pinned skipped 40 vs ambient 6/13) · R-10(계약이 `uv run` 을 중첩 실행해 스위트에 약 30초 추가) · R-11(성능 임계값은 여전히 wall-clock) · R-12(F-20 격리는 하네스 수준, 제품은 IP 단일 키) · R-13(`vault_data` 가 여전히 부모를 dirty 로). 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-013/`.

**attempt-012 결과(2026-09-13):** **attempt-011 이 한계로 남긴 R-4(`job.view` 무잠금 쓰기)를 결함으로 승격해 닫았고, 그 정리 과정에서 두 번째 결함이 드러나 함께 닫았다.** (a) **F-16 — 종결 기록에 소유자가 없었다**: 종결 상태(`status`/`termination`/`error`/`finished_at`)를 쓰는 주체가 둘(취소 라우트·잡 스레드)인데 "누가 최종 기록을 쓰는가" 규칙이 없어 **나중에 쓴 쪽이 이겼다**. 증인 A(취소가 먼저 기록되고 watchdog 의 `timeout` 이 0.35초 뒤 도착 — 실제 경로에서도 성립하는 순서)에서 **관측된 종결 기록이 두 개**였다: `[('failed','cancelled','cancelled by user'), ('failed','timeout','exit_code=-15')]`. API 는 `200 {"ok": true}` 로 취소를 접수했다고 답했는데 정착한 기록은 `timeout` 이다 — 사용자가 취소했다는 사실이 사라진다. 수정(D-59~D-61): 쓰기 단일 지점 `_Job.finalize()`(**먼저 확정한 쪽이 소유**, 재호출은 no-op) + `note()`(진행) + `snapshot()`(복사본 — `GET` 이 살아 있는 dict 를 넘기지 않는다) + `claim_cancel()`(1회 접수), 그리고 취소는 프로세스 종료보다 **먼저** 기록을 쓴다(종료는 최대 2×grace 블로킹이라 그 뒤에 쓰면 늦게 도착한 `timeout` 이 기록을 가져간다). 계약도 하나 좁혔다 — 소유하지 못한 취소는 `{"ok": false, "detail": "job already finished"}` 이고, 예전에는 그 창에서 **완료된 잡의 기록을 덮고 `ok:true`** 를 돌려줬다. (b) **F-17 — 취소가 이벤트 루프를 세웠다**: cancel 라우트가 `async def` 인데 본체가 `terminate_process_group`(내부 `proc.wait(grace)` 두 번 = 최대 2×grace)을 그대로 호출했다. 실측(heartbeat 최대 간격): 수정 전 실제 라우트 **1010.7ms**, 수정 후 **6.8ms**, 같은 본체를 루프에서 구동한 옛 모양은 1007.3ms. 요청 소요는 ~1.05초로 **불변** — 빨라진 것이 아니라 서버가 멈추지 않게 됐다. 수정은 `def` 라우트 한 단어다(FastAPI 스레드풀). (c) **검증** — 증인 exit 1 → 0(A: 기록 2개 → 1개 · D: 1010.7ms → 6.8ms), 회귀 **8건 신규**(구 코드로 되돌리면 6건 실패, 그중 HTTP 회귀는 `assert 'timeout' == 'cancelled'` 로 **동작** 실패), **required gate 20/20 을 커밋된 후보 `1207118d` 에서 되돌리기 0회로 단일 지문 `7ecb4fc2…` 에서 완주**(python-tests **6215 passed / 6 skipped** 464.6s · docker 230.4s · clean-machine 41.8s · `data/` 드리프트 0 · 실행 후 지문 재측정 동일). **남은 차단 사유는 사람의 영역이다** — EX-01~06 · C14-08 · C14-03/04/05. 한계는 `attempt-012/review.md` R-1~R-8 — 특히 R-6(같은 lock 3종 sha256 인데 skip 집합이 달랐다: 수집 6213 → 6221 = 신규 8건과 정확히 일치, skipped 13 → 6, **원인 미특정**)과 R-7(`uv run --isolated --frozen python -c` 는 게이트 환경이 아니다).

**attempt-011 결과(2026-09-13):** **규율을 계약으로 옮겼고, 그 계약이 드러낸 제품 결함을 닫았다.** (a) **R-4/D-55 계약화** — attempt-010 은 "기록에 지문·수치를 박지 말 것"을 규율로만 남겼고, 규율은 다음 사람이 README 에 지문을 다시 붙이면 무너진다. `tests/test_cr14_fingerprint_scope_contract.py`(9건, **5건은 위반을 심어 확인하는 이빨**)로 옮겼다: README 는 지문 값을 담지 않고 소유 문서를 가리킨다 · 지문 스코프(README·`tests/**`)는 선언된 현재 지문을 인용하지 않는다 · 제외 목록(`FINGERPRINT_EXCLUDED_PREFIXES = ("docs/", ".omo/")`)이 바뀌면 계약이 먼저 깨진다 · 세 기록 문서가 경계를 말한다. **대가를 정직하게 기록한다**: 계약을 만드는 행위 자체가 지문을 옮겼다(`d4a42ab8…` → `cdfbbb96…`) — 그래서 20 gate 를 새 지문에서 다시 완주해야 했다(D-56). (b) **required gate 의 일회성 실패는 flake 가 아니었다(F-15)** — 그 지문에서 `python-tests` 가 1건 실패했다(`test_cancel_sets_termination_cancelled`: `assert 'completed' == 'cancelled'`). **단독 실행은 5/5 통과**했지만 넘기지 않고 증인을 썼다(D-57): A(폴링 간격을 늘려 경주를 확정) 3/3 · B(실제 간격, API 와 같은 순서) **12/12 오분류**. 원인은 감독 분류가 **관측에 의존**한 것이었다 — API cancel 은 `cancel_event.set()` 과 **동시에** `terminate_process_group` 을 호출하는데 watchdog 은 0.2초 폴링이라, 프로세스가 먼저 죽으면 `fired_reason` 을 세우지 못하고 `while proc.poll() is None` 루프를 빠져나간다. 그러면 `reason = "completed" if fired is None else fired` 가 취소를 완료로 분류하고(exit_code=-15), 잡 스레드가 `job.view["termination"]` 으로 **취소 기록을 덮어쓴다** — 사용자는 취소했는데 `status=failed, termination=completed` 로 남는다. 수정(D-58): 분류를 관측이 아니라 **사실**로 바꿨다(`cancel_event.is_set()` + 비정상 종료 코드 → `cancelled`). 정상 완료는 exit_code == 0 이라 오분류되지 않고, 그 방향을 회귀가 고정한다. (c) **검증** — 증인 exit 1 → 0(A 0/3 · B 0/12 · C 유지), 수정을 끄면 결정적 회귀 1건이 실패(이빨), `tests/test_trn02_timeout_resource.py` 17 passed(기존 15 + 신규 2), **required gate 20/20 을 동결된 clean HEAD `d72b1711` 에서 되돌리기 0회로 단일 지문 `e428aacc…` 에서 완주**(python-tests **6200 passed / 13 skipped** · docker 233.3s · clean-machine 41.3s · dashboard-build 24.1s 드리프트 0 · `data/` 드리프트 0). **순서 규율의 실증**: 코드를 게이트 **실행 전에** 커밋했으므로 보고서의 SHA 가 곧 최종 HEAD 이고 HEAD 의존 gate 재실행이 필요 없었다(attempt-010 은 이 순서를 어겨 재실행이 필요했다 — D-52). **남은 차단 사유는 사람의 영역이다** — EX-01~06 · C14-08 · C14-03/04/05. 한계는 `attempt-011/review.md` R-1~R-5(특히 R-4: `job.view` 무잠금 쓰기 구조는 그대로다 — 이번엔 그 증상만 닫았다).

**attempt-010 결과(2026-09-13):** **증거를 동결된 커밋 트리에 묶고, 그 과정에서 이 저장소의 전제 하나가 틀렸음을 실측했다.** (a) **attempt-009 기록을 커밋하면서 지문이 이동했다** — 지문 제외는 `docs/`·`.omo/` **접두사뿐**이고 `README.md`(루트)·`tests/**` 는 지문 **안**이다. 계약 파일(`tests/test_cr12_docs_alignment.py`) 하나를 고쳐 `dd34a76b…` → `003205f2…` 로 옮겼다. 즉 **"결과 문서를 쓰는 것만으로는 gate 증거가 낡지 않는다"는 이 저장소의 전제는 `docs/` 안에 쓸 때만 참이다**(게이트 실행기의 `FINGERPRINT_EXCLUDED_PREFIXES = ("docs/", ".omo/")` 는 경로 접두사 비교다). 그래서 README 에서 지문 **값**을 제거하고 **출처**(판정서·보고서)를 가리키게 했다(D-51) — 최신 값을 손으로 계속 갱신하는 대안은 갱신 행위가 값을 낡게 만들어 자기모순이다. (b) **코드 경로를 동결하고 커밋한 뒤 20 gate 를 새로 완주했다**(D-52): 커밋은 내용 hash 기반 지문을 옮기지 않으므로(`d4a42ab8…` 유지) "동결 → 커밋 → 측정" 순서가 보고서의 SHA 와 지문을 **같은 트리**로 묶는다. 결과: **20 실행 / 20 PASS / 0 실패 · 되돌리기 0회**, 단일 지문 `d4a42ab87697ba299129719d054c9259a717628a1bc8f80d00cd03ae0e372ce7`, clean HEAD `5ccb938e5d31411b16f2a69e3015fc8fb826455d`(커밋 4개: `5a717c4a` 후보 → `54e4169a` F-12 → `7347c5ee` attempt-009 기록 → `5ccb938e` README 지문 제거). python-tests **6189 passed / 13 skipped**(463.3s) · dashboard-test **81 files/849** · `docker-build` 233.7s · `clean-machine-runtime` 41.0s · `dashboard-build` 24.6s(드리프트 0) · `data/` 드리프트 0. (c) **HEAD 의존 gate 2개만 clean HEAD 에서 별도 보고서로 재실행**(D-53): `dashboard-build`(핀을 읽어야 드리프트 0)와 `clean-machine-runtime`(`git archive HEAD`)만 다시 돌려 `gate-report-clean-head.json`(2/2 PASS)에 남겼다 — `ref: HEAD` 로 **3001 파일**을 아카이브했고 `git ls-tree -r HEAD` 도 3001 이며 아카이브의 README 가 커밋본임을 확인했다. 전체 인벤토리는 `gate-report.json`(20/20)이다. (d) **F-14 를 닫았다**: attempt-009 기록의 `frontend 846 passed(80 files)` 는 같이 attempt 의 보고서(`849` / `81 files`)와 달랐다 — F-12 가 추가한 테스트 3건 이전 값이 넘어왔다. 수치는 **그 attempt 의 `gate-report.json` 에서 직접 인용**하도록 정정했다(D-54). **남은 차단 사유는 사람의 영역이다** — EX-01~06 · C14-08(독립 검토·출시 책임자) · C14-03/04/05. 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-010/`(한계는 `review.md` R-1~R-5).

**attempt-009 결과(2026-09-13):** **기술 축을 모두 닫았다.** (a) **후보를 커밋했다**(사용자 결정: 단일 커밋) — `5a717c4a`(CR-01~CR-14 268 파일) + F-12 수정 `54e4169a`(27 파일). **clean full SHA = `54e4169a947d4ba0cbe3fabf92b0c8590b8ccef6`**. 커밋이 **막혔는데 그것이 옳았다** — pre-commit 의 `trailing-whitespace` 가 **생성 번들 11개를 다시 쓰고** `check-added-large-files`(maxkb=1024)가 모나코·TS 워커(MB 단위)를 거부했다. 훅이 생성물을 소스처럼 다루면 커밋된 바이트와 `pnpm run build` 결과가 갈라져 빌드 멱등성이 깨진다. `--no-verify` 가 아니라 **생성 경로를 훅 대상에서 제외**하고, 훅이 고친 번들 11개를 빌드 산출물로 되돌려 커밋했다(D-46). (b) **커밋이 새 결함 F-12 를 드러냈다**: 커밋 직후 `dashboard-build` 가 자산 **22개를 교체**하고 지문을 옮겼다(`07118329…` → `a4be7868…`), 그런데 같은 HEAD 에서 두 번째 빌드는 no-op 이었다. 원인은 `buildStamp.ts` 가 `AGK_BUILD_ID` 기본값으로 `git rev-parse --short HEAD` 를 쓴 것 — **커밋된 번들은 자기 커밋의 SHA 를 담을 수 없다**(치킨-에그). `dashboard-build` 가 required gate 인 한 **커밋된 후보에서 단일 지문 20/20 을 완주할 수 없었다**(C14-01/C14-02 가 구조적으로 미충족). attempt-003 의 "빌드는 멱등" 실측은 **고정 HEAD 에서만** 참이었다 — F-01 의 서술을 F-12 로 조건부 정정한다. 수정: 해석 순서를 `AGK_BUILD_ID`(릴리스 주입) → **커밋된 핀 `dashboard/build-provenance.json`** → `git short SHA` → null 로 바꾸고, 번들을 핀 값(`5a717c4a`)으로 재생성했다. 핀 ≠ HEAD 는 정상이다(핀은 '번들을 만든 소스 리비전'을 기록하며, 그 커밋이 번들을 담고 있는 커밋과 같을 수 없다). **부수 개선**: `.git` 이 없는 Docker 빌드도 핀을 읽어 출하 컨테이너가 커밋된 번들과 같은 바이트를 서빙한다. (c) **F-07 을 닫았다**: 커밋된 SHA 에서 전 게이트를 재실행해 `clean-machine-runtime` 이 `ref: HEAD` 로 **후보 전체(3001 파일, 직전 2877 = 낡은 HEAD)** 를 검증했고, **required gate 20/20 을 되돌리기 0회로 단일 지문 `dd34a76b…` 에서 완주**했다(실행 후 지문 불변). 검증: 증인 `cr14_f12_build_drift_witness.py` exit 0(핀 유효·번들이 핀 보유·재빌드 digest 불변 — 수정 전에는 22개 교체), 핀 값을 바꾸면 pytest 2건이 실패한다(이빨 확인), 전체 suite **6189 passed / 13 skipped**(452.1s, `data/` 드리프트 0). **새 잔여 F-13**: `git status` 의 유일한 줄은 ` M vault_data`(중첩 저장소의 런타임 이벤트 로그, +3537줄)이며 gitlink SHA 는 불변이다 — 커밋에는 영향이 없지만 보고서에 `git.dirty: true` 가 남아 'clean 후보' 판정을 흐린다(선택지 3개를 D-50 에 기록). **남은 차단 사유는 사람의 영역이다** — EX-01~06 · C14-08(독립 검토·출시 책임자) · C14-03/04/05. 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-009/`(한계는 `review.md` R-1~R-5).

**attempt-008 결과(2026-09-13):** **F-10 과 F-11 을 닫고 F-09 의 `qs` 편차를 실행 검증했다** — 세 건 모두 게이트 초록과 공존하던 결함이다. (a) **F-10**: `pnpm run stryker:quick` 이 `Cannot find TestRunner plugin "vitest"` 로 죽었다. 오류 메시지는 "러너를 설치하라" 로 읽히지만 실측은 **탐색 경로**였다 — Stryker 의 자동 플러그인 탐색은 **자기 자신의 설치 디렉터리**를 스캔하고, pnpm 의 격리 레이아웃에서 그 안에는 core 의 의존(api·instrumenter·util)만 있으며 devDependency 인 러너는 없다. 수정은 `stryker.config.mjs` 에 한 줄(`plugins: ['@stryker-mutator/vitest-runner']`)이다 — 버전을 올리면 결함을 고치지 않으면서 도구 체인을 통째로 움직인다. (b) **F-09 검증**: 도구가 살아나자 그 도구가 `qs` override 의 **유일한 소비자 경로**였다는 사실을 이용해 R-1 반증 절차를 수행했다 — `@stryker-mutator/core → typed-rest-client → Util.getUrl → qs.stringify`(여기서 `encodeValuesOnly` 가 **기본값**이고 advisory 발동 조건과 일치)에서 `qs 6.15.1`(벤더 정확 고정값)은 **실제 크래시**(`TypeError: Cannot read properties of null (reading 'length')`, A·B 두 축 모두)하고 `6.16.0` 은 정상이다. 즉 근거가 "advisory 하한" 에서 "우리 경로에서 재현되는 크래시의 수정" 으로 강화됐다. (c) **F-11 신규/폐쇄**: 도구를 돌리자 **측정 범위가 조용히 반토막나 있었다** — `--mutate A --mutate B` 는 **마지막 하나만** 적용하므로 보고서에 `outputStore.ts` 만 들어갔고(82.35%) exit 0 이었다. 통제 실험(단일 플래그로 `terminalStore.ts` → 정상 96.92%)으로 원인을 분리해 **쉼표 단일 플래그**로 고쳤다(All files 91.92%, 두 파일 모두). **판정은 NO-GO 유지** — 남은 기술 축은 **F-07 하나**이고, 나머지는 사람·커밋 위생이다. 검증: 전체 suite **6183 passed / 13 skipped**(457.9s, `data/` 드리프트 0), 회귀 9건(`tests/test_cr14_stryker_toolchain_contract.py` — `plugins` 제거 시 1건 · 반복 플래그 복원 시 2건 실패로 이빨 확인), **되돌리기 없이 단일 지문 `6641446ef41e0562…` 에서 20-gate 20/20 PASS**(실행 후 지문 불변). 한계는 `attempt-008/review.md` R-1~R-5.

**attempt-007 결과(2026-09-13):** **F-09 을 닫았다** — 대시보드 **dev 도구 체인**의 취약 의존(high 1건 `eslint→@eslint/eslintrc→js-yaml` · moderate 3건 `@stryker-mutator→typed-rest-client→qs`)이 게이트(`--prod`) 범위 밖이라 초록과 공존하고 있었다. 실측하니 **절반은 또 '두 진실원 갈라짐'**이었다 — `js-yaml` 이 **pnpm 4.3.1(취약) / npm 4.3.2(패치)** 로 갈라져 있었고(F-03·F-06 에 이어 **세 번째** 같은 병), `qs` 는 양쪽 모두 6.15.1(취약)이었다. 수정: `js-yaml: 4.3.2`(상류 `@eslint/eslintrc` 가 `^4.3.0` 을 선언하므로 **편차가 아니라 최소 패치**) + `qs: 6.16.0`(상류 `typed-rest-client@2.3.1` 이 `6.15.1` 로 **정확히 고정**했고 수정판은 3.x 에만 있는데 stryker 는 `~2.3.0` 만 허용 — 즉 선언 범위 안에 수정판이 없는 **의도된 편차**)를 **양쪽 설정에** override 하고 두 lock 을 재생성했다. 결과: **전체 트리 audit 0/0/0/0/0**(advisories 0), `pnpm run lint` exit 0(js-yaml 정상 로드) · vitest 846 passed · build exit 0. 증인은 세 축(하한·두 lock 일치·**출하 closure 부재**)을 측정해 수정 전 exit 1(위반 4건) → 수정 후 exit 0. 회귀 7건(`tests/test_cr14_dashboard_dev_toolchain_floor.py`)이 하한·일치·선언·상류 범위·**dev 전용 경계**를 고정한다. 게이트는 **되돌리기 없이 단일 지문 `c36327ef…` 에서 20/20 PASS**(python-tests 6174 passed / 13 skipped, docker 240.9s).

닫는 과정에서 **F-10** 을 새로 등록했다 — `pnpm run stryker:quick` 이 `Cannot find TestRunner plugin "vitest"` 로 죽는다(stryker 9.6.1 ↔ vitest 4.1.11). required gate 는 아니지만 **통제 실험**(F-09 override 를 제거하고 같은 명령 실행 → **동일 실패**)으로 내 변경의 회귀가 아님을 확정했고, 그 실패가 **`qs` override 를 검증할 유일한 소비자 경로를 막는다**는 사실도 기록했다. 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-007/`(한계는 `review.md` R-1~R-7).

**attempt-006 결과(2026-09-13):** **F-06 을 닫았다** — mermaid 경유 `uuid@9.0.1`(GHSA-w5hq-g745-h8pq, `<11.1.1`)은 감사 임계값(`high`) 미만이라 게이트가 차단하지 않았고, 실측으로 결함의 성질이 바뀌었다. (a) **의존 하한 위반**: pnpm·npm **두 lock 모두이** `uuid@9.0.1` 으로 해석돼 있었다(pnpm 은 설치·빌드, npm 은 SBOM·고지 진실원). (b) **취약 서명 미도달**: mermaid 의 erDiagram 청크는 `import { v5 } from "uuid"` 후 `v5(str, MERMAID_ERDIAGRAM_UUID)` — 인자 2개이므로 취약 서명(`buf` 전달)에 도달하지 않는다. 즉 이 결함은 악용 경로가 아니라 **하한 문제**였고, 상류(`mermaid 10.9.8`)가 이미 `uuid: ^9.0.0 || ^10 || ^11.1.0 || ^12 || ^13 || ^14.0.0` 를 선언해 **패치 버전을 허용하고 있었다**. 수정: `dashboard/pnpm-workspace.yaml` 과 `dashboard/package.json` **양쪽**에 `uuid: 11.1.1` override(한쪽만 하면 npm 은 14.x 로 가서 설치 코드와 고지 코드가 갈라진다 — F-03 과 같은 병), 두 lock 재생성, **출하 번들 재빌드**(추적 산출물: 청크가 `…Ca1Z6rrW.js` → `…DK8mMXpA.js` 로 교체), release 문서 재생성, 회귀 8건(`tests/test_cr14_dashboard_dependency_floor.py`). 증인은 세 축을 분리해 측정한다 — A) 잠금 하한, B) 취약 서명 도달성(참고), **C) 출하 바이트**(번들에 uuid v35 구현이 있으면 패치 마커 `out of buffer bounds` 도 있어야 한다). C 축의 이유: **잠금만 올리고 재빌드하지 않으면 출하물에는 옛 코드가 남는다**(F-03 의 교훈). 증인 수정 전 exit 1(하한 위반 3건) → 수정 후 exit 0, `pnpm audit --prod` **취약 0건**(moderate 포함), CR-09 실브라우저 4/4(`blockedExternal: []` — mermaid 가 uuid 11.1.1 로 렌더), 전체 suite **6167 passed / 13 skipped**(skip 증가분 7건은 unsloth/trl 환경 오버레이 부재 — uv.lock 에 0건, 후보의 성질이 아니다), **되돌리기 없이 단일 지문 `3a9a7d66…` 에서 20-gate 20/20 PASS**(실행 후 지문 불변). **게이트 범위의 기술 결함은 0건**이되고 남은 축은 커밋·외부 승인·F-07(검증 범위)이며, **dev 도구 체인 취약(eslint→js-yaml high 1건 · stryker→qs moderate 3건)을 F-09 로 등록**했다(게이트가 `--prod` 라 미차단 — "감사 통과 ≠ 위험 0"). 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-006/`(한계는 `review.md` R-1~R-8).

**attempt-005 결과(2026-09-13):** **F-03 을 닫았다** — release 파이썬 라이선스 판독이 **두 갈래로 틀렸다**. (a) **판독 실패**: `THIRD_PARTY_NOTICES.txt` 의 파이썬 절만 `License` 필드를 직접 읽었고 `python.cdx.json` 은 PEP 639 `License-Expression` → License → 분류기 → 별명표로 읽어, **같은 실행의 두 산출물이 같은 패키지에 다른 답**을 했다(파이썬 구성요소 61개 중 **42건 불일치**, 그중 **35건은 메타데이터가 있는데도 미상으로 적힌 판독 실패** — `fastapi`=MIT, `click`=BSD-3-Clause, `cryptography`=Apache-2.0). 이 고지문은 **wheel/sdist 에 동봉되는 법적 문서**이고 `verify` 가 바이트 일치를 강제한다. (b) **환경 의존**: 설치되지 않는 마커 패키지(colorama/pywin32)만 양쪽 모두 미상인데, 그 집합이 어디에도 선언돼 있지 않았다. 수정: 고지문이 SBOM 과 **같은 판독 체인**을 쓰게 통일(SPDX id → 원문(공백만 정규화, 합성 금지) → 미상 표기). 저장소 사본 재생성(미상 41건 → 2건), `python.cdx.json` 은 수정 전후 **바이트 동일**(결함은 고지문 쪽이었다). 미해결 2건은 **추정값을 선언하지 않고**(검증되지 않은 주장 금지) 미해결 ⊆ `marker_platform_packages` 를 회귀 17건이 고정한다(`tests/test_cr14_python_license_determinism.py`). 증인이 수정 전 exit 1 → 수정 후 exit 0, 전체 suite **6166 passed / 6 skipped** 에서 `data/` 드리프트 0, **되돌리기 없이 단일 지문 `1981bfb5…` 에서 20-gate 20/20 PASS**. **남은 기술 결함은 F-06 하나**이고 나머지는 사람·커밋 위생이다. 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-005/`.

**attempt-004 결과(2026-09-12):** **F-08 을 닫았다** — `api/dependencies.py` 가 ModelManager 를 만들 때 `UsageTracker(db_path="data/token_usage.json")` 처럼 **CWD 상대·추적 파일 경로를 하드코딩**했고, `record()` 는 `auto_save_interval`(**기본 50**)건마다 `_save()` 했다. 즉 **사용량을 50건 이상 기록하는 테스트 조합 하나면 pytest 실행이 후보 트리를 더럽혔다**(실측: `M data/token_usage.json`) — F-02 와 **같은 구조의 두 번째 경로**이고, F-02 의 격리는 그 한 경로만 대상이었다. 임계값 아래에서는 발현되지 않아 조용히 잠복했다. 수정: `usage_tracker` 에 단일 패치 지점 `default_usage_db_path()`(+순수 `resolve_usage_db_path`, `AGK_USAGE_DB` override)를 신설하고 — **프로덕션 기본값은 그대로** — `dependencies.py` 가 리졸버를 호출하며, conftest 의 `_isolate_default_usage_db` 가 테스트에서만 저장소 밖으로 돌린다. 증인은 **A(결함 원형 재현) + B(격리) + C(override)** 를 구분해 측정한다(수정 전 exit 1 → 수정 후 exit 0). 전체 suite **6149 passed / 6 skipped** 에서 `data/` 드리프트 0, **20-gate 가 되돌리기 없이 단일 지문 `eca54773…`(2546 files) 에서 20/20 PASS**. 판정은 여전히 NO-GO — 남은 조건은 동일하다(필수 외부 승인 부재 · source mismatch). 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-004/`.

**attempt-003 추가 실측(2026-09-12):** F-01 의 성질을 정정하고 F-07 을 등록했다. ① **F-01 정정** — `pnpm run build` 재실행 전후 `src/antigravity_k/dashboard_dist/` **103 파일이 바이트 단위 동일**(added 0/removed 0/changed 0)이고 코드 지문도 불변이다. 종전 "자산명이 내용 해시라 항상 stale / 검증이 트리를 흔든다" 서술은 **틀렸다** — 트리가 dirty 한 이유는 **커밋된 HEAD(`08b8bb2e…`) 번들이 현재 소스보다 낡았기 때문**이고, 갱신 산출물을 후보와 함께 커밋하면 clean 이 되며 이후 빌드는 no-op 이다. 따라서 F-01 은 **GA blocker 가 아니라 post-GA 추적 정책 선택**으로 내려간다. ② **F-07 신규** — `scripts/verify_clean_machine.sh` 가 `REF="HEAD"` 로 `git archive`(2877 파일)하므로, required gate `clean-machine-runtime` 의 PASS 는 **후보가 아니라 커밋된 HEAD** 에 대한 판정이다(`gate-report.json` `git.dirty: true`). 지금 HEAD 번들이 낡은 UI 를 담고도 초록인 이유이며, CR-10/CR-11 "stale bundle" blocker 의 뿌리다 — 코드 결함이 아니라 **검증 범위(sequencing)** 문제이므로 **커밋 뒤 새 HEAD 에서 재실행**해야 한다. ③ 코드 변경은 없다(지문 `eb10aed6…` 유지) → attempt-003 의 20-gate 증거가 그대로 유효하다. 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-003/logs/f01-build-idempotency.txt`.

**attempt-003 결과(2026-09-12):** F-02를 닫았다 — API 런타임이 `AgentRuntime(task_outcome_recorder=benchmark_harness.record_task_outcome)` 로 **모든 작업 완료를 기록**하는데 기본 DB 경로가 CWD 상대 추적 파일 한 곳으로 고정되어 있어, 작업을 실행하는 테스트가 하나라도 있으면 **pytest 전체 실행이 후보 트리를 더럽혔다**(실측 +423줄, `total_task_results` 656→684; CR-13 R03 드리프트의 뿌리). 기본 경로를 단일 패치 지점 `default_benchmark_db_path()`(+순수 `resolve_benchmark_db_path`, `AGK_BENCHMARK_DB` override)로 분리하고 — **프로덕션 기본값은 그대로** — `tests/conftest.py` autouse 픽스처가 테스트에서만 저장소 밖으로 돌린다. 증인이 수정 전 추적 파일 digest 변경을 재현(exit 1) → 수정 후 exit 0, 전체 suite **6136 passed / 6 skipped** 에서 `data/` 드리프트 0, **required gate 20/20 PASS를 되돌리기 없이 단일 지문 `eb10aed6…` 위에서 완주**했다. 판정은 여전히 NO-GO — 남은 조건은 동일하다(필수 외부 승인 부재 · source mismatch). 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-003/`.

**attempt-002 결과(2026-09-12):** 판정 규칙의 네 조건 중 **P1과 required gate 실패/미실행이 해소**됐다 — `mermaid`를 `10.9.8`로 올려 `dependency-audit-dashboard`가 PASS(그 승격이 드러낸 라벨 주입 비컨은 `mermaidRuntime`의 입력 중화 + 출력 정화로 차단, 실브라우저 계약 `C09-03`이 `blockedExternal: []`로 감시), 처음 실행된 `docker-build`가 드러낸 콜드 `tsc -b` heap OOM은 dashboard-builder 한정 `NODE_OPTIONS`로 닫았다. **required gate 20개가 단일 코드 지문 `ebbbd7f0…`(2544 files) 위에서 20/20 PASS** 다. 남은 두 조건(필수 외부 승인 부재 · clean full SHA 없음)으로 **판정은 NO-GO를 유지**한다. 상세: `.omo/evidence/commercial-reliability/CR-14/attempt-002/{metadata.json,reproduction.md,decision.md,manual-qa.md,review.md,handoff.md,gate-report.json}`.

## 5. 검증 명령과 실행 비용

다음은 저장소 루트에서 실행하는 기존 명령이다. 환경은 CR-00에서 확인하고 frozen 설치는 disposable checkout에서 수행한다. 아래 성공은 기록될 때만 사실이다.

```bash
uv sync --frozen --extra dev
uv run --no-sync ruff check src/ tests/ scripts/
uv run --no-sync ruff format --check src/ tests/ scripts/
uv run --no-sync mypy src/
uv run --no-sync basedpyright src/ scripts/ --level error
uv run --no-sync pytest tests/ -q --tb=short
pnpm --dir dashboard install --frozen-lockfile
pnpm --dir dashboard run lint
pnpm --dir dashboard run typecheck
pnpm --dir dashboard run test
pnpm --dir dashboard run build
```

전체 suite의 optional runtime 요구는 현재 gate 환경을 따른다. base 환경에서 missing extra가 난다고 skip을 추가하지 않는다. 지원 extra 설치/대상 차이를 evidence에 기록한다. build는 추적된 번들 경로를 바꿀 수 있으므로 공유 작업트리에서 무작정 실행하지 않는다.

작업별 신규 테스트 파일은 각 카드의 **신규 작성 대상**이며 계획 작성 시 존재를 전제로 하지 않는다. 구현 후 정확한 경로와 실제 명령을 checklist에 기록한다. 기존 핵심 회귀 예:

```bash
uv run --no-sync pytest tests/test_vault.py tests/test_conversation_store_ctx01.py tests/test_val02_conversation_multiprocess.py -q
uv run --no-sync pytest tests/test_fr01_agent_execution_isolation.py tests/test_fr02_shell_execution_boundary.py tests/test_fr05_api_workers.py -q
uv run --no-sync pytest tests/test_fr11_gate_verifier.py tests/test_fr13_release_manifest.py -q
pnpm --dir dashboard exec playwright test e2e/tests/auth-bootstrap.spec.ts e2e/tests/ws-04-project-switch.spec.ts e2e/tests/conversation-compaction.spec.ts e2e/tests/accessibility.spec.ts
```

Playwright의 server/port/auth helper는 현재 `dashboard/playwright.config.ts`와 e2e helper를 먼저 읽어 격리 환경으로 기동한다. 기존 서버 재사용을 자동으로 허용하지 않는다. CR-14의 전체 gate는 `scripts/commercial_ga_gates.json`과 검증기 CLI `--help`를 확인한 실제 명령을 기록한다. 유료 API 비용/8시간 실행은 스케줄·모델·예산을 명시한 실행 위임 아래 수행한다.

## 6. 증거·상태·인계 규격

작업마다 다음 파일을 만든다. 실제 비밀/개인 경로/원문 사용자 프롬프트는 기록하지 않는다.

```text
.omo/evidence/commercial-reliability/CR-XX/attempt-NNN/
  metadata.json     # ID, owner, start/code SHA, tree 상태, 환경, 상태, deps
  reproduction.md   # 합성 fixture, pre-fix 명령/관찰, 가설과 확정 사실 구분
  decision.md       # 계약/대안/호환성/변경 범위; 결정 없으면 none 명시
  commands.jsonl    # 실제 명령, cwd, 시작/종료, exit, 로그 상대 경로
  logs/            # redacted 원문 출력, 실패 결과도 보존
  manual-qa.md     # 사용자 행동, 예상/실제, UI/API/프로세스 증거
  review.md        # 독립 검토자, full SHA, 판정, blocker와 증거
  handoff.md       # 완료/미완료/다음 한 단계/소유 파일/잔여 프로세스
```

metadata 최소 필드: `task_id`, `attempt`, `owner`, `status`, `start_sha`, `code_sha`, `dirty_paths`, `dependencies`, `acceptance_results`(Cxx ID→PASS/FAIL/NOT_RUN 및 증거 경로), `reviewer`, `review_sha`, `blocking_reasons`. 브랜치명이나 `HEAD` 문자열만을 SHA 대신 쓰지 않는다. 미커밋 검증은 patch hash/tree fingerprint로 보조 기록하되 최종 승인은 full SHA에서 재검증한다.

상태: TODO → IN_PROGRESS → REVIEW → DONE. 실패 후 IN_PROGRESS로 돌아가 새 attempt를 사용한다. 외부 조건 부족은 BLOCKED_EXTERNAL(조건/책임자/요청/재개 명령 필수). 구현자가 REVIEW를 올리고 독립 검토자가 동일 SHA 증거를 확인한 뒤 DONE을 승인한다. ALREADY_FIXED는 재현 분류이지 DONE의 대체 상태가 아니다. 체크박스는 연결 증거가 없으면 체크하지 않는다.

체크리스트 갱신은 작업마다 즉시 수행하고 완료 수는 CR-00~14의 15개 작업 기준이다. 15개 완료도 품질 100점이 아니며 CR-14의 GO 조건 충족 여부를 별도로 표시한다.

**문서 반영은 완료 조건의 일부다(상시 규칙).** 작업을 끝낸 같은 턴에 네 문서를 함께 갱신한다: ① `17_COMMERCIAL_RELIABILITY_CHECKLIST.md`(상태표·수용 기준 체크·실행 기록·결정 대장), ② 본 계획서(front matter `status`, 진행 현황 표, 운영 영향·배포 주의, 다음 작업), ③ `08_CHANGELOG.md`의 해당 날짜 절, ④ `10_FINAL_READINESS_REPORT.md`의 날짜별 갱신 절. 증거팩만 남기고 문서를 미루지 않으며, 문서와 증거가 어긋나면 증거를 기준으로 문서를 즉시 정정한다.

### 다른 에이전트에게 전달할 실행 프롬프트

```text
Ssak-Ai 상용 신뢰성 개선 계획을 실행한다.
먼저 docs/qa/2026-09-11-commercial-review/BASELINE.md,
docs/16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md,
docs/17_COMMERCIAL_RELIABILITY_CHECKLIST.md와 적용 AGENTS.md를 읽어라.
체크리스트에서 명시적으로 배정된 CR 작업 하나만 맡고 선행 DONE 여부를 확인하라.
CR-00 미완료이면 기준/소유권부터 확정하고 구현을 시작하지 마라.
현재 HEAD에서 결함을 재현하고, 담당 카드의 고정 계약·수용 기준을 모두 만족시켜라.
다른 작업자가 있으므로 기존 변경을 되돌리지 말고 소유 파일 변경에 맞춰 조정하라.
실제 데이터/비밀 대신 임시 합성 fixture로 시험하고, 증거팩에 실패와 성공을 보존하라.
구현자는 REVIEW까지만 요청하고 독립 검토자의 같은 SHA 승인 없이 DONE으로 바꾸지 마라.
남은 blocker·정확한 다음 단계·검증 명령을 handoff.md에 남겨라.
계획 밖 기능 확장, 공개 배포, 과거 PASS 재라벨링으로 이 작업을 대체하지 마라.
```

구현 위임 시 조정자가 CR ID/owner/worktree를 실제 값으로 채워 전달한다. 배정이 없으면 소유권 확보부터 진행하고 이미 진행 중인 작업을 중복 실행하지 않는다.
