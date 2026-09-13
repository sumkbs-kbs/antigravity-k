# 10 Final Readiness Report

기준일: 2026-08-17

## 결론

> **최신 판정(2026-09-13): GA 출시 판정 NO-GO — 단 attempt-009에서 후보를 커밋해 required gate 20/20 을 **커밋된 후보**(`54e4169a`)에서 되돌리기 없이 완주했고, `clean-machine-runtime` 이 처음으로 후보를 검증했다(F-07 폐쇄).** **기술 축은 모두 닫혔다.** 남은 것은 사람의 영역이다 — EX-01~06(외부 승인), C14-08(독립 검토·출시 책임자), C14-03/04/05. 참고: attempt-008의 20/20은 그 시점 실측으로 보존한다.
>
> **이전 판정 기록(attempt-008)**: GA 출시 판정 NO-GO — required gate 20/20 PASS(되돌리기 없이). 블로커는 **사람의 승인·커밋 위생**만 남았다 — attempt-003 추가 실측으로 **F-01(빌드 비결정성 의심)은 기각**됐고(`dashboard-build` 는 바이트 단위 멱등), 대신 **F-07(`clean-machine-runtime` 이 후보가 아니라 커밋된 HEAD 를 검증한다)** 이 등록됐다. attempt-005는 **F-03**(release 파이썬 라이선스가 고지문↔SBOM 으로 갈라지고 미해결 집합이 선언되지 않음)을, attempt-006은 **F-06**(mermaid 경유 `uuid` 하한 — 게이트 임계값 미만이라 초록과 공존했다)을, attempt-007은 **F-09**(dev 도구 체인 취약 — 게이트가 `--prod` 라 미차단)를 닫아 게이트 범위와 dev 감사 모두 0건이 됐다. **attempt-008은 F-10(stryker 변이 도구가 pnpm 레이아웃에서 죽는다)과 F-11(그 도구가 선언한 2개 파일 중 1개만 측정했다)을 닫고, 같은 수정이 열어 준 소비자 경로로 F-09 의 `qs` override 를 처음으로 실행 검증**했다(`6.15.1` 에서 실제 크래시 → `6.16.0` 정상). 남은 기술 축은 **F-07 하나**다: "감사 통과"와 "위험 0"은 다르고, "도구 초록"과 "범위 전체 측정"도 다르다. 아래 문단은 그 이전(2026-08-17 기준) 결론이다. 최신 근거는 [2026-09-12 CR-14 attempt-003 절](#2026-09-12-cr-14-attempt-003--f-02-폐쇄-검증-실행이-저장소-추적-파일을-다시-쓰지-않는다-판정-no-go-유지)과 [CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md)을 보라.

현재 Ssak-Ai는 **로컬 중심 에이전트 기능 검증/베타 준비 단계**다. qwen3.6 local-first, tool permission, CoV, QualityGate 수정 재생성, RAG provenance, durable task state, web result quality contract, chat/task/slash/CLI/MAX/multiplexer의 AgentRuntime 연결, memory compliance contract는 실제 코드와 테스트로 확인됐다. 최신 simple 2-case × 2 repeats와 frontier 5-case × 2 repeats 모두 `excellent` 안정성을 확인했고 전체 basedpyright hard gate도 `0 errors`로 통과했지만, live 검색 recall/근거 정확도와 운영 rehearsal이 남아 있어 첨부 요구사항의 “상용서비스 수준” 최종 조건은 아직 충족되지 않았다.

## 요구조건별 판정

| 조건 | 판정 | 근거/부족한 증거 |
|---|---|---|
| 표준 설치·빌드·실행 | [~] | wheel/sdist build와 서버 smoke는 통과했지만 uv/lock과 clean machine 재현 추가 필요 |
| 핵심 검색 자동화 | [~] | adapter/quality contract와 graded 2-case/확장 6-case fixture가 통과했고 precision은 개선됐지만 provider 장애와 live recall/case coverage가 부족 |
| 치명적 보안 취약점 없음 | [~] | permission/URL guard와 41개 guarded egress inventory, robots/crawl-delay, legal terms audit/enforce policy가 존재하지만 배포별 attestation/policy file과 DNS/secret/dep audit rehearsal 필요 |
| 검증 가능한 출처 | [x] | source id/citation/provenance 구조 |
| 답변-근거 연결 | [~] | COV_VERIFY가 검색 context의 untrusted evidence를 복원해 unsupported/unknown/conflict citation과 검증기 예외를 fail-closed로 처리한다. controlled 및 cache-allowed 실제 DuckDuckGo evidence grounding은 통과했지만 forced-refresh provider 안정성·최신성·다국어 sample은 부족 |
| 중복/스팸 제거 | [~] | canonical dedupe/domain diversity, spam classifier 미완료 |
| 최신성 반영 | [~] | category TTL, publish/update freshness 미완료 |
| 외부 API 부분 장애 격리 | [x] | multi-provider fallback과 empty result contract |
| 검색 품질 목표 충족 | [~] | configured self-hosted authority-rescue plus Qwen source-hint run은 `error_count=0`, 6-case P@3 0.389/Recall@3 0.667/MRR 0.917/nDCG@3 0.741로 개선됐지만 provider availability와 load P95 1805.8ms는 여전히 미달 |
| 운영 로그/알림/롤백 | [~] | audit/checkpoint/Vault와 task 실패·취소 snapshot rollback, provider cooldown/load benchmark, stale-cache marker는 구현됐고 alert/restore rehearsal 부족 |
| 최신 문서 | [x] | 01~10 문서와 project diagnostic report 추가 |
| 위험 투명성 | [x] | 본 보고서와 security review에 미해결 항목 기록 |

## 출시 차단 항목

1. 배포별 이용약관/법적 attestation policy file을 채우고 `enforce` 모드로 전환한 증거와 dependency/secret audit 실행 증거
2. live provider 검색 recall 개선과 확장 human-labeled golden set의 healthy-provider 실행. 현재 configured self-hosted baseline은 availability만 통과하고 6-case relevance와 P95 tail은 미달
3. 실제 provider evidence를 넣은 live Qwen claim-level benchmark의 forced-refresh availability, 반복 분산, 최신성, 다국어 conflict presentation
4. shell tool, Git, PageScraper-backed web fetch, external-brain API와 `/api/agent/tools/shell/run`은 canonical permission 경계로 통합됨. shell은 project cwd/timeout/output quota와 fail-closed SandboxRunner를 사용하고 task rollback도 연결됐으며 41개 HTTP egress call site가 공통 runtime policy로 guarded됨
5. memory scope/delete/redaction 계약: provider/durable export-redact-retention과 Vault raw-asset exclusion/redacted opt-in은 완료됐고, 원문 asset 삭제/변경 consent flow가 남음
6. 전체 basedpyright hard gate는 `src` `0 errors`로 통과했다. 다만 healthy-provider P95/P99 baseline, 장시간 장애 복구 rehearsal, 저장소 전체 Ruff 712 legacy/style findings 정리가 남아 있다.
7. Qwen simple/frontier 대표 suite의 범위를 넓히고, long-horizon 및 live grounding에서도 반복 실행 분산과 `excellent` 비율을 안정적으로 유지하는 증거

## 다음 승인 조건

위 차단 항목마다 재현 가능한 테스트, 실행 로그, rollback 절차가 추가되고, 전체 suite와 API/browser E2E가 clean하게 통과한 뒤에만 베타 서비스 범위를 확대한다. 현재 전체 suite와 API E2E는 통과했지만 live relevance, healthy load baseline, 배포별 legal attestation, live claim sample이 남아 있으므로 개인 로컬/개발 환경의 제한된 사용으로 유지한다.

## 2026-08-17 갱신

- 체크리스트 미검증 항목 일괄 실측 완료: 메모리 계층(READ 5/10, durable 5종 NO-READ), lh-001 격차 재측정(+0.273 지속), egress 차단(5/5, 로그 부재 확인), 승인 왕복(~43ms), RAG 리콜@k(recall@3=6/8), PIN 인증(8/8), 시크릿 스캐너(20/20), 라우팅 전략(collective ~5.4배).
- 벤치마크 재현 절차 문서화 완료(`docs/07_TEST_AND_BENCHMARK_PLAN.md` "벤치마크 재현 절차" 섹션).
- README 기능↔구현 매트릭스 작성 완료.
- 남은 열린 항목: docs 본 문서들의 세부 내용 현행화(본 갱신으로 기준일 정렬 완료), .gitignore 표준 무대상 보강, egress 차단 전용 감사 로그 추가.

---

## 2026-09-10 상용화 GA-100 달성 및 GA 전환 결론

- **상용화 계획 및 체크리스트 100% 완결**:
  - [`docs/11_COMMERCIAL_GA_100_PLAN.md`](./11_COMMERCIAL_GA_100_PLAN.md) 및 [`docs/12_COMMERCIAL_GA_100_CHECKLIST.md`](./12_COMMERCIAL_GA_100_CHECKLIST.md)의 33개 작업 항목(GA-00 ~ RC-01)이 모두 독립 리뷰 및 실측 증거 팩을 수립하고 **33/33 DONE (100/100 점수)**을 달성했다.
- **재해 복구 리허설 (DR Rehearsal) 검증**:
  - `scripts/dr_rehearsal.py`를 통해 백업 복원, DB 손상 복구, 고아 워크트리 정리, 프로젝트 마이그레이션 4개 핵심 재해 시나리오 전수 검증 (`all_ok = True`).
- **릴리즈 & 공급망 무결성 (REL/RC)**:
  - SBOM, 라이선스 감사, 컨테이너 계약, 릴리즈 메타데이터 전수 77개 테스트 100% 통과 (`tests/test_rel*.py`, `tests/test_release*.py`).
  - 프로덕션 Vite 번들 무결점 빌드 완료 (`pnpm build`, 1.52s).
- **로컬 에이전트 인프라 & UI 통합**:
  - 4방향 태스크 분류 및 다양성 프로브 기반 Adaptive Stability를 갖춘 `UnifiedAgent`와 Ssak-Search 기반 웹 그라운딩이 코어 및 대시보드 UI(`⚡ Adaptive` 모드 토글, 실행 배지)에 완전 연동됨.
    - 실전 코딩 평가 스위트(`tests/evals/real_coding/`) 8개 전 도메인 이식 및 오프라인 검증 하네스(`test_real_coding_harness.py`, 11 tests) 100% 통과.
- **최종 판정**: **상용화 준비도 100% 달성 및 General Availability (GA) 정식 출시 준비 완료 (GA READY)**.

---

## 2026-09-11 최종 검토 개선(Remediation) 및 상용화 게이트 현행화

- **최종 검토 발견(FR-01~10) 및 개선 태스크(RP-01~14) 체계 수립**:
  - `docs/qa/2026-09-10/FINAL_REVIEW.md` (REQUEST CHANGES) 발견 사항에 대응하여 [`docs/14_FINAL_REVIEW_REMEDIATION_PLAN.md`](./14_FINAL_REVIEW_REMEDIATION_PLAN.md) 및 [`docs/15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md`](./15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md)을 수립하고 전면 개선 작업 수행.
- **필수 개선 태스크 12/15 DONE (독립 리뷰 전원 APPROVE)**:
  - RP-01/RP-02: macOS Seatbelt 기반 공용 샌드박스 강제 및 셸 실행 경계 주입 방어 완료 (12/12 보안 매트릭스, 89개 보안 테스트 통과).
  - RP-03/RP-04: 사전 소유권 기록 + 커밋 CAS 프리이미지 복구(`AtomicTransactionEngine`), 부재 소유 파일 외부 동시 삭제 보존 및 충돌 기록 (`driver residue: false`, `concurrent_deletion_preserved: true`).
  - RP-05: 2개의 실제 Live Uvicorn 워커 간 권위적 읽기, stale revision에 대한 HTTP 409 Conflict, 콜드 재시작 보존 실측 (25 tests passed).
  - RP-06/RP-07: Chroma no-op delete negative control FAIL 검증, 4-way 바이트 동일 설정 및 저장소 외부 격리 가상환경 설치 검증 완료.
  - RP-08/RP-09: Playwright Chromium 브라우저 기반 프로젝트 전환 E2E(2 passed) 및 수동 대화 압축 UI E2E(4 passed) 실측 통과.
  - RP-10/RP-11: 증거 인덱스 정합화, fail-closed 게이트 검증기(18 passed) 및 kill -9 크래시 복구 검증 완료.
  - RP-13: 이전 버전 롤백(0.0.9 ↔ 0.1.0)을 포함한 5종 DR 리허설 통과, 11개 아티팩트 해시 결합 릴리즈 매니페스트 완비.
  - RP-15: append equality 및 핵심 제약 보존 완료 확인, 대형 리팩토링 안정성을 위해 유예 (`DEFERRED_NONBLOCKING`).
- **상용화 출시 게이트 (Release Candidate Gate)**:
  - 후보 커밋(`4b202113f254a766fdd26db30e4f65e417f77c28`) 기준 **20/20 필수 게이트 단일 실행 통과** (`ga_gate_verify.py PASS`).
  - 8시간 연속 내구성 부하 테스트(`rp12-soak-006`, PID 52583): 7시간 10분 이상 연속 정상 구동 중 (~90% 완료, 목표 종료 ~21:03 KST).
- **최종 출시 판정(RP-14) 준비**:
  - 5-Axis 상용화 준비도 사전 평가 완비 (`PASS`), 8시간 부하 테스트 완료 직후 최종 릴리즈 판정 확정 예정.

---

## 2026-09-12 CR-14 attempt-003 — **F-02 폐쇄**: 검증 실행이 저장소 추적 파일을 다시 쓰지 않는다 (판정 NO-GO 유지)

> **attempt-003 추가 실측:** 이 절은 **F-01 의 성질을 정정**하고 **F-07 을 등록**한다(아래 F-01 재평가·F-07 절). F-08 은 다음 절에서 닫혔다.

> **이 절이 최신 실측이다.** 판정은 attempt-001·002와 같이 **NO-GO** 다. 달라진 것은 **clean 후보를 만들 수 없는 뿌리가 하나 줄었다**는 점이다.

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`eb10aed606ba7e84ecce03a50a19153b92105cacd196b5a167b5e38770f1f448`**(2545 files).

- **F-02 폐쇄** — API 런타임이 `AgentRuntime(task_outcome_recorder=benchmark_harness.record_task_outcome)` 로 **모든 작업 완료를 기록**하는데 기본 DB 경로가 CWD 상대 `data/benchmark_results.json`(**추적 파일**) 한 곳으로 고정되어 있었다. 그래서 **작업을 실행하는 테스트가 하나라도 있으면 `pytest` 전체 실행이 후보 트리를 더럽혔고**(실측 +423줄, `total_task_results` 656→684), 검증 후 clean tree 를 만들 수 없어 게이트 코드 지문이 실행마다 이동했다(attempt-001 병합 거부 `different working tree`). CR-13 R03 드리프트의 뿌리다.
- **수정** — 기본 경로를 단일 패치 지점 `default_benchmark_db_path()`(+순수 `resolve_benchmark_db_path`, `AGK_BENCHMARK_DB` override)로 분리하고, **프로덕션 기본값은 그대로 두었다**(추적 파일은 누적 결과 DB라는 제품 계약). `tests/conftest.py` autouse 픽스처가 테스트에서만 저장소 밖으로 돌리고(CR-02 D-07 선례), 회귀 12건이 계약을 고정한다.
- **증거** — 증인이 수정 전 추적 파일 digest 변경을 재현(exit 1) → 수정 후 exit 0. 전체 suite **6136 passed / 6 skipped**(452초)에서 `data/` **드리프트 0**(digest 불변 + `git status` clean). **20 required gate 가 `git checkout` 되돌리기 없이 단일 지문에서 20/20 PASS** 했고, 실행 **후에도** 지문이 동일하다.
- **운영 규약 변경** — `pytest` 뒤 `git checkout -- data/benchmark_results.json` 을 더 이상 하지 않는다(되돌릴 것이 없다). 게이트 실행 후에는 `git status` 로 확인만 한다. `AGK_BENCHMARK_DB` 로 결과 DB 위치를 바꿀 수 있다.
- **F-01 재평가(성질 정정)** — `pnpm run build` 재실행 전후 `src/antigravity_k/dashboard_dist/` **103 파일이 바이트 단위 동일**(added 0/removed 0/changed 0)이고 코드 지문도 불변이다. 종전 "자산명이 내용 해시라 항상 stale / 검증이 트리를 흔든다" 서술은 **틀렸다** — dirty 의 원인은 **커밋된 HEAD(`08b8bb2e…`) 번들이 현재 소스보다 낡은 것**(39 D / 93 ?? / 1 M)이고, 갱신 산출물을 후보와 함께 커밋하면 clean 이 된다. 따라서 F-01 은 **GA blocker 가 아니라 post-GA 추적 정책 선택**으로 내려간다.
- **F-07 신규** — `scripts/verify_clean_machine.sh` 는 `REF="HEAD"` 로 `git archive`(2877 파일)하므로 `clean-machine-runtime` 의 PASS 는 **후보 작업 트리가 아니라 커밋된 HEAD** 에 대한 판정이다(`gate-report.json` `git.dirty: true`). 지금 HEAD 번들이 낡은 UI(mermaid `10.6.1`)를 담고도 초록인 이유이며 CR-10/CR-11 "stale bundle" blocker 의 뿌리다 — 코드 결함이 아니라 **검증 범위(sequencing)** 문제다. **커밋 뒤 새 SHA 에서 반드시 재실행**해야 하고, 그 전까지 이 PASS 를 후보 근거로 인용하지 않는다.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 후보가 아니라 HEAD 를 검증)** · F-03(라이선스 환경 의존) · F-06(uuid moderate) · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완. (F-01 은 위 재평가로 blocker 목록에서 내려갔다.)
- **다음 한 단계** — CR-01~14 **커밋**(갱신된 `dashboard_dist` 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(**특히 `clean-machine-runtime`** — F-07) → **F-03·F-06** → 독립 검토·출시 책임자 배정 → CR-14 attempt-005.

---

## 2026-09-12 CR-14 attempt-004 — **F-08 폐쇄**: 사용량 추적 기본 경로가 추적 파일을 다시 쓴다 (판정 NO-GO 유지)

> **기록** — 이후 attempt-005 가 F-03 을 닫아 지문이 `1981bfb5…` 로 이동했다(위 절 참조).

> 판정은 attempt-001~003과 같이 **NO-GO** 다.

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`eca54773d5504e40a724a0c86ab9d1724be310986ef3e326f8f4904f52d98dd8`**(2546 files).

- **F-08 폐쇄** — `api/dependencies.py` 가 ModelManager 를 만들 때 `UsageTracker(db_path="data/token_usage.json")` 처럼 **CWD 상대·추적 파일 경로를 하드코딩**했고, `UsageTracker.record()` 는 `auto_save_interval`(**기본 50**)건마다 `_save()` 를 호출했다. 그래서 **사용량을 50건 이상 기록하는 테스트 조합 하나면 pytest 실행이 후보 트리를 더럽혔다**(실측: `M data/token_usage.json`). 이는 **F-02 와 같은 구조의 두 번째 경로**이고, F-02 의 격리는 그 한 경로만 대상이었다. 임계값 아래에서만 돌던 지금까지의 suite 때문에 **조용히 잠복**해 있었다.
- **수정** — `usage_tracker` 에 단일 패치 지점 `default_usage_db_path()`(+순수 `resolve_usage_db_path`, `AGK_USAGE_DB` override)를 신설하고 **프로덕션 기본값은 그대로 두었다**(누적 사용량 DB 계약). `dependencies.py` 는 리터럴 대신 리졸버를 호출하고, `tests/conftest.py` 의 `_isolate_default_usage_db` 가 테스트에서만 저장소 밖으로 돌린다(`_isolate_default_benchmark_db` 바로 옆). 회귀 13건이 계약을 고정하고, 그중 하나는 `dependencies.get_model_manager` 의 **소스**에서 리터럴 부재를 검사한다 — 동작 테스트만으로는 리터럴이 돌아와도 통과하기 때문이다.
- **증거** — 증인 `cr14_f08_usage_db_witness.py` 가 **A(결함 원형 재현) + B(격리) + C(override)** 를 구분해 측정: 수정 전 exit 1 → 수정 후 exit 0(B 에서 리졸버가 돌려준 임시 경로에 저장되고 저장소 파일은 바이트 단위 불변). 전체 suite **6149 passed / 6 skipped**(455초)에서 `data/` 드리프트 0, **20 required gate 가 되돌리기 없이 단일 지문에서 20/20 PASS**.
- **부수 확인 / 남긴 가설** — `data/` 에서 지문을 흔드는 파일은 **`token_usage.json`(추적) 뿐**이고 `data/projects.json`·`data/benchmarks/*` 는 gitignore 다. `data/` 밖에 같은 모양의 세 번째 경로가 더 있는지는 **전수 조사하지 않았다**(미검증).
- **주의(함정 재확인)** — conftest 는 모듈 속성을 패치하므로 `from ... import default_usage_db_path` 로 이름을 직접 바인딩하면 패치가 보이지 않는다. 이 attempt 의 증인 첫 작성이 실제로 그 함정을 밟아 저장소 파일을 썼다.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · F-03(라이선스 환경 의존) · F-06(uuid moderate) · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**·clean full SHA → 그 SHA에서 20-gate 재실행(특히 `clean-machine-runtime`) → **F-03·F-06** → 독립 검토·출시 책임자 배정 → CR-14 attempt-005.

---

## 2026-09-13 CR-14 attempt-009 — **후보 커밋 + F-12·F-07 폐쇄**: 기술 축을 모두 닫았다 (판정 NO-GO 유지)

> **이 절이 최신 실측이다.** 달라진 것은 **커밋된 후보에서 20/20 을 완주**했고 **clean-machine 이 후보를 검증**했다는 점이다. 이제 남은 차단 사유는 사람의 영역(승인·검토·장기 검증)뿐이다.

후보: **clean full SHA `54e4169a947d4ba0cbe3fabf92b0c8590b8ccef6`**(커밋 `5a717c4a` + F-12 수정 `54e4169a`), 코드 지문 **`dd34a76bf076ebc09be8c575ad733c52a0a647faa4d5d9758f3b01cf6f667f37`**.

- **커밋이 막혔는데 그것이 옳았다** — pre-commit 의 `trailing-whitespace` 가 **생성 번들 11개를 다시 썼고** `check-added-large-files`(maxkb=1024)가 워커(MB 단위)를 거부해 중단됐다. 훅이 생성물을 소스처럼 다루면 커밋된 바이트와 `pnpm run build` 결과가 갈라진다(F-01/F-12 의 멱등성 파괴). `--no-verify` 가 아니라 **생성 경로를 훅 대상에서 제외**하고 다시 커밋했다.
- **F-12 — "빌드는 멱등"은 고정 HEAD 에서만 참이었다** — 커밋 직후 `dashboard-build` 가 자산 **22개를 교체**하고 지문을 옮겼다(같은 HEAD 에서 두 번째 빌드는 no-op). 원인은 `buildStamp.ts` 가 `AGK_BUILD_ID` 기본값으로 `git short SHA` 를 쓴 것 — **커밋된 번들은 자기 커밋의 SHA 를 담을 수 없다**(치킨-에그). `dashboard-build` 가 required gate 인 한 **커밋된 후보에서 단일 지문 20/20 이 불가능**했다. 수정: **커밋된 핀**(`dashboard/build-provenance.json`)을 해석 순서에 넣고(`env → 핀 → git → null`) 번들을 핀 값으로 재생성.
- **F-07 폐쇄** — `clean-machine-runtime` 이 `ref: HEAD` 로 **후보 전체(3001 파일, 직전 2877 = 낡은 HEAD)** 를 아카이브해 exit 0. 이제 이 초록은 후보의 근거다. **순서 규율은 남는다**: 릴리스는 태그 SHA 에서 이 gate 를 마지막으로 다시 돌려야 한다.
- **증거** — 증인 `cr14_f12_build_drift_witness.py` exit 0(핀 유효·번들이 핀 보유·재빌드 digest 불변), 회귀 **9건**(핀 값을 바꾸면 pytest 2건 실패 — 이빨), 전체 suite **6189 passed / 13 skipped**(452.1s, `data/` 드리프트 0), **required gate 20개가 커밋된 후보에서 되돌리기 0회로 단일 지문에서 20/20 PASS**(docker 227.3s · clean-machine 42.5s · dashboard-build 24.0s · api-e2e 18.4s)이고 **실행 후 지문 불변**.
- **F-13(신규, advisory)** — `git status` 의 유일한 줄은 ` M vault_data` 이고 그 안은 훅 런타임 이벤트 로그(+3537줄)다. gitlink SHA 는 불변이라 커밋에는 영향이 없지만 보고서에 `git.dirty: true` 가 남아 **'clean 후보' 판정을 흐린다**(선택지 3개를 D-50 에 기록).
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · 독립 검토·출시 책임자 미배정(C14-08) · C14-03(재시작·이력 복구 포함 전 구간) · C14-04(EX-03) · C14-05(EX-01/EX-05) · **C14-01 의 'worktree 완전 clean' 기준 결정**(F-13). **기술 결함은 0건**이다.
- **다음 한 단계** — C14-03 → C14-04/05(외부 승인 필요) → C14-08 배정 + EX-01~06 발송 → CR-14 attempt-010(릴리스 번들 `evidence_kind: release` + GO/NO-GO 재판정).

---

## 2026-09-13 CR-14 attempt-008 — **F-10·F-11 폐쇄 + F-09 의 `qs` 편차 실행 검증** (판정 NO-GO 유지)

> 판정은 attempt-001~007과 같이 **NO-GO** 다. 달라진 것은 **측정 도구가 살아나고 그 도구가 검증하던 유일한 소비자 경로까지 끝까지 확인**했다는 점이다(남은 기술 축: **F-07 하나**).

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`6641446ef41e0562118dd0741637f57eae6412f18fdf18813ea87f777d0b0076`**(attempt-007 의 `c36327ef…` 에서 이동).

- **F-10 은 오류 메시지를 잘못 읽으면 진단이 뒤집히는 사례다** — `pnpm run stryker:quick` 이 `Cannot find TestRunner plugin "vitest"` 로 죽는데, 이는 러너 미설치가 아니라 **탐색 경로** 문제다. Stryker 의 자동 플러그인 탐색은 **자기 자신의 설치 디렉터리**를 스캔하고, pnpm 격리 레이아웃의 `.pnpm/@stryker-mutator+core@*/node_modules/@stryker-mutator` 에는 core 의 의존(api·instrumenter·util)만 있으며 devDependency 인 러너는 루트에만 있다. 수정은 `stryker.config.mjs` 의 한 줄(`plugins: ['@stryker-mutator/vitest-runner']`)이다 — 설치된 조합(9.6.1 ↔ vitest 4.x)은 peer 계약(`vitest: >=2.0.0`)을 만족하고 dry-run 843 테스트가 실제로 돈다.
- **도구가 살아나자 F-09 의 '미검증' 이 닫혔다** — 그 도구가 `qs` override 의 **유일한 소비자 경로**였다. 소스로 지목한 경로(`@stryker-mutator/core → typed-rest-client RestClient → Util.getUrl → qs.stringify`, 여기서 `encodeValuesOnly` 가 **기본값**)에서 `qs 6.15.1`(벤더 정확 고정값)은 **실제 크래시**(`TypeError: Cannot read properties of null (reading 'length')`, `Util.getUrl`·`RestClient.get` 두 축 모두)하고 `6.16.0` 은 정상이다. 근거가 "advisory 하한" 에서 "우리 경로에서 재현되는 크래시의 수정" 으로 강화됐다 — 이 override 를 revert 하는 것이 **더 위험한 선택**이 됐다.
- **에 도구를 돌리자 새 결함 F-11 이 드러났다** — `--mutate A --mutate B` 는 **마지막 하나만** 적용한다. 스크립트는 2개 파일을 선언했는데 보고서에는 `outputStore.ts` 만 들어갔고(82.35%) **exit 0** 이었다. 통제 실험(단일 플래그로 `terminalStore.ts` 만 → 96.92%, 정상)으로 원인을 **파일 선택이 아니라 반복 플래그**로 분리한 뒤, 쉼표 단일 플래그로 고쳤다 — 수정 후 두 파일 모두(All files **91.92%** = 91 kill / 8 survive, exit 0). 이는 F-07 과 **같은 병**이다: exit 0 이 검증한 대상과 확인하려는 대상이 다르다.
- **증거** — 증인 `cr14_f09_qs_consumer_probe.cjs`: `6.15.1` 에서 A·B 두 축 모두 CRASH(exit 1) → `6.16.0` 에서 A·B OK(exit 0). 회귀 **9건**(`tests/test_cr14_stryker_toolchain_contract.py` — `plugins` 한 줄 제거 시 1건 · 스크립트를 반복 플래그로 되돌리면 2건 실패로 이빨 확인). 전체 suite **6183 passed / 13 skipped**(457.9초)에서 `data/` 드리프트 0, **20 required gate 가 되돌리기 없이 단일 지문 `6641446ef41e0562…` 에서 20/20 PASS**(python-tests 459.9s · docker 46.0s · clean-machine 41.8s · dashboard-build 25.3s · api-e2e 18.3s)이고 **실행 후 지문이 불변**임을 재측정했다.
- **정직한 한계** — ① `qs` 검증은 우리가 소스로 지목한 소비자 경로에 대한 것이고 `stryker init` 을 실행한 것은 아니다(R-1) ② 91.92% 는 **quick 범위(2 파일)** 의 점수이고 전체 `stryker`(10 파일)는 비용 때문에 돌리지 않았다(R-3) ③ `reports/mutation/mutation.json` 은 JsonReporter 미설정으로 **7월 21일 파일이 남아 있다**(그 안의 break 는 50) — 현재 결과로 인용하면 틀린다(D-44).
- **F-11b 는 advisory 다** — quick 범위 생존 변이 8건(outputStore 6 · terminalStore 2)은 임계값(`high 80`·`break 55`)을 통과한다. 도구가 이제 이 신호를 **측정 가능**하게 만들었다는 사실이 진전이다.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**(두 lock·`dashboard_dist`·release 문서 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(**`clean-machine-runtime` 이 마지막 기술 축**) → **F-11b 판단**(생존 변이 정책) → 독립 검토·출시 책임자 배정 + EX-01~06 발송 → CR-14 attempt-009.
- **출하 문서 정정(D-45)** — `dashboard.cdx.json` 은 **241 항목 / 207 고유 패키지**다(attempt-007 이 "구성요소 207" 로 적은 것은 고유 이름 수였다). 해시(`666a2ea3…`)는 불변이다.

---

## 2026-09-13 CR-14 attempt-007 — **F-09 폐쇄**: dev 도구 체인 취약과 출하 경계 (판정 NO-GO 유지)

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`c36327effafcc6dbe4a80970682f5e82eccd98f81951b000c758e888e7b0130a`**(attempt-006 의 `3a9a7d66…` 에서 이동).

- **F-09 은 '게이트 초록 + dev 취약 잔존'이었다** — `dependency-audit-dashboard` 가 `--prod` 이므로 dev 도구 체인은 감사 범위 밖이다. 실측(수정 전): high 1건(`eslint → @eslint/eslintrc → js-yaml`, `<4.3.2`) + moderate 3건(`@stryker-mutator/core → typed-rest-client → qs`, `<6.16.0`).
- **절반은 또 두 진실원 갈라짐이었다** — `js-yaml` 이 **pnpm 4.3.1(취약) / npm 4.3.2(패치)** 로 갈라져 있었다. F-03(고지문↔SBOM)·F-06(uuid)에 이어 **세 번째** 같은 병이다. `qs` 는 양쪽 모두 6.15.1 이었다.
- **출하 경계를 측정으로 남겼다** — 두 패키지 모두 출하 SBOM(`dashboard.cdx.json`, 241 항목 / 207 고유 패키지)·`THIRD_PARTY_NOTICES.txt` 에 **없다**(수치는 attempt-008 에서 정정 — D-45). "dev 니까 출하물에 영향 없다"를 회귀(C14-F09-6)로 고정했다.
- **수정** — `js-yaml: 4.3.2` 는 상류(`@eslint/eslintrc`)가 `js-yaml: ^4.3.0` 을 선언하므로 **편차가 아니라 최소 패치**다. `qs: 6.16.0` 은 **의도된 편차**다 — `typed-rest-client@2.3.1` 이 `qs: 6.15.1` 로 정확히 고정했고 수정판은 3.x(`^6.16.0`)에만 있는데 stryker 는 `~2.3.0` 만 허용해 **선언 범위 안에 수정판이 없다.** 두 override 를 양쪽 설정(`pnpm-workspace.yaml` + `package.json`)에 선언하고 두 lock 을 재생성했다.
- **증거** — 증인 `cr14_f09_dev_audit_witness.py` 는 하한·두 lock 일치·출하 closure 부재를 분리 측정해 수정 전 exit 1(위반 4건) → 수정 후 exit 0. **전체 트리 audit 0/0/0/0/0**(advisories 0), `pnpm run lint` 0 errors(js-yaml 정상 로드) · vitest 846 passed · build exit 0 · 출하 문서 불변. 전체 suite **6174 passed / 13 skipped**(466.1초)에서 `data/` 드리프트 0, **20 required gate 가 되돌리기 없이 단일 지문 `c36327ef…` 에서 20/20 PASS**(docker 240.9s · clean-machine 41.9s · dashboard-build 27.6s · accessibility 10.3s). 회귀 7건.
- **닫는 중 나온 새 결함 F-10** — `pnpm run stryker:quick` 이 `Cannot find TestRunner plugin "vitest"` 로 exit 1. **통제 실험**(F-09 override 제거 후 같은 명령 → 동일 실패)으로 **기존 결함**임을 확정했다(stryker 9.6.1 ↔ vitest 4.1.11). required gate 는 아니지만 ① 변이 점수 측정 수단 부재 ② **`qs` 편차의 유일한 소비자 경로가 실행되지 않아 그것이 end-to-end 로 검증되지 않았다**는 두 가지를 남긴다.
- **정직한 한계** — pnpm 은 override 를 지워도 해석을 즉시 되돌리지 않으므로(lock 보존) 선언 검사가 해석 검사와 짝으로 필요하다. `qs` 편차의 근거는 그 시점에 advisory 하한·같은 벤더 후속 메이저의 선언·minor 상향 세 가지였고, **실행 검증은 attempt-008 에서 마쳤다**(소비자 경로에서 `6.15.1` 크래시 → `6.16.0` 정상). 상세 D-36·D-41, `attempt-007/review.md` R-1~R-7.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · **F-10(stryker 도구 체인 — 게이트 아님)** · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**(두 lock·`dashboard_dist`·release 문서 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(특히 `clean-machine-runtime`) → **F-10 판단**(고친 뒤 `qs` override 재검증) → 독립 검토·출시 책임자 배정 → CR-14 attempt-008.

## 2026-09-13 CR-14 attempt-006 — **F-06 폐쇄**: 대시보드 `uuid` 하한과 출하 바이트 (판정 NO-GO 유지)

> **이 절이 최신 실측이다.** 판정은 attempt-001~005와 같이 **NO-GO** 다. 달라진 것은 **게이트 범위의 기술 결함이 0건**이 됐다는 점이다(남은 축: 커밋·외부 승인·F-07·F-09).

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`3a9a7d66909e2fafaf31b4c429d2338f262d50b0d0d8ef3b5f00b5be0ca41e2d`**(attempt-005 의 `1981bfb5…` 에서 이동).

- **F-06 은 두 축으로 나뉘어 있었다** — 등록 서술은 "mermaid 경유 `uuid@9.0.1` moderate(`<11.1.1`)인데 감사 임계값이 `high` 라 차단되지 않는다"였다. 실측하니 ⓐ **의존 하한 위반**(pnpm·npm **두 lock 모두** `uuid@9.0.1` — pnpm 은 설치·빌드, npm 은 SBOM·고지 진실원)이고 ⓑ **취약 서명 미도달**(mermaid 의 erDiagram 청크는 `import { v5 } from "uuid"` 후 `v5(str, NAMESPACE)` — 인자 2개이므로 취약 서명 `buf` 전달이 아니다)이었다. 즉 악용 경로가 아니라 **하한 문제**였고, 상류 `mermaid 10.9.8` 이 이미 `uuid: ^9.0.0 || ^10 || ^11.1.0 || ^12 || ^13 || ^14.0.0` 로 **패치 버전을 허용하고 있었다**.
- **수정** — `dashboard/pnpm-workspace.yaml` 과 `dashboard/package.json`(npm `overrides`) **양쪽에** `uuid: 11.1.1`. 한쪽만 하면 npm 은 mermaid 범위의 **최고 가지(14.x)** 를 골라 설치 코드와 고지 코드가 갈라진다(F-03 과 같은 병 — 회귀 `C14-F06-2b` 가 두 lock 일치를 고정). 11.1.1 은 취약 범위를 벗어나는 **최소 패치**이고 `exports` 가 ESM·CJS 를 모두 제공하는 것을 확인했다(12+ 는 이번에 검증한 범위가 아니다). 두 lock 재생성 + **출하 번들 재빌드**(추적 산출물: 청크가 `…Ca1Z6rrW.js` → `…DK8mMXpA.js` 로 교체) + release 문서 재생성.
- **증인은 세 축을 분리해 측정한다** — A) 잠금 하한, B) 취약 서명 도달성(참고), **C) 출하 바이트**(번들에 uuid v35 구현이 있으면 패치 마커 `out of buffer bounds` 도 있어야 한다). C 축이 필요한 이유: **잠금만 올리고 재빌드하지 않으면 출하물에는 옛 코드가 남는다**(F-03 의 교훈). 수정 전 exit 1(하한 위반 3건) → 수정 후 exit 0. 별개로 게이트 관점에서는 수정 전에도 `pnpm audit --prod --audit-level high` 가 **exit 0** 이었다 — moderate 는 임계값 미만이므로 **초록인 채로 미패치 의존이 남아 있었다**.
- **증거** — 증인 `cr14_f06_uuid_reachability.py`(수정 전/후), `pnpm audit --prod` **취약 0건**(moderate 포함 0), CR-09 실브라우저 **4/4 PASS + 전 시나리오 `blockedExternal: []`**(mermaid 가 uuid 11.1.1 로 실제 렌더), 전체 suite **6167 passed / 13 skipped**(448.5초, `data/` 드리프트 0), 대시보드 80 files/846 passed, **20 required gate 가 되돌리기 없이 단일 지문 `3a9a7d66…` 에서 20/20 PASS**(docker 223.8s · clean-machine 41.5s)이며 **실행 후에도 지문이 불변**임을 재측정했다. 회귀 8건(`tests/test_cr14_dashboard_dependency_floor.py`; override 선언 2곳을 제거하면 3건 실패 — 이빨 확인).
- **skip 증가는 후보의 성질이 아니다** — 13건 중 7건은 `TestAgainstInstalled`(unsloth/trl)로, 두 패키지는 `uv.lock` 에 **0건**이다(pyproject §87-90: extra 가 아니라 주간 drift CI 담당). attempt-005 는 오버레이가 있는 환경에서 같은 7건을 PASS 로 기록했다(D-32).
- **신규 잔여 위험 F-09** — dev 도구 체인에 **high 1건**(`eslint → @eslint/eslintrc → js-yaml <4.3.2`)·moderate 3건(`@stryker-mutator → typed-rest-client → qs`). 게이트가 `--prod` 이므로 차단되지 않는다 — **"감사 통과"가 "위험 0"은 아니라는 사실이 이 attempt 로 한 번 더 실증됐다.** 삭제/상향 여부는 출시 책임자 결정.
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · **F-09(dev 도구 체인 취약, 게이트 범위 밖)** · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**(갱신된 **두 lock**·`dashboard_dist`·release 문서 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(특히 `clean-machine-runtime`) → **F-09 결정** → 독립 검토·출시 책임자 배정 → CR-14 attempt-007.

## 2026-09-13 CR-14 attempt-005 — **F-03 폐쇄**: release 라이선스 판독이 고지문↔SBOM 으로 갈라져 있었다 (판정 NO-GO 유지)

> 판정은 attempt-001~004와 같이 **NO-GO** 다. 달라진 것은 **남은 기술 결함이 F-06 하나**가 됐다는 점이다. **(이후 attempt-006 에서 F-06 도 닫혔다 — 위 절 참조.)**

후보: 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`1981bfb5143d3f9eac947826bf6ee53655c47194f5be9c4a5bf755ba982a1844`**.

- **F-03 폐쇄(원인을 둘로 분해해 실측)** — 등록 서술은 "실행 환경에 따라 라이선스 값이 달라진다"였지만 실제로는 ⓐ **판독 실패**(환경과 무관하게 틀린다) ⓑ **환경 의존**(플랫폼 마커에만 남는다)로 나뉘었고, 실질 결함은 ⓐ였다. `THIRD_PARTY_NOTICES.txt` 의 파이썬 절만 `License` 필드를 직접 읽었고 `python.cdx.json` 은 PEP 639 `License-Expression` → License → 분류기 → 별명표 순으로 읽었다 — 즉 **같은 실행의 두 산출물이 같은 패키지에 다른 답**을 했다(파이썬 구성요소 61개 중 **42건 불일치**, 그중 **35건은 환경 메타데이터를 직접 읽어 반증한 판독 실패** — `fastapi`=MIT, `click`=BSD-3-Clause, `cryptography`=Apache-2.0, `networkx`=BSD-3-Clause). 고지문은 **wheel/sdist 에 동봉되는 법적 문서**이고 `release_sbom verify` 가 저장소 사본과의 **바이트 일치**를 강제한다 — 41줄의 `license metadata unavailable` 이 그대로 출하물에 실려 있었다.
- **수정** — 고지문이 SBOM 과 **같은 판독 체인**을 쓰도록 통일(SPDX id → 정규화 불가 시 원문 `License` 필드를 **공백만 정규화**해 한 줄 유지 → 미상 표기; 값을 합성하지 않는다). 저장소 사본 재생성으로 미상이 41건 → 2건이 됐고, `python.cdx.json` 은 **수정 전후 바이트 동일**이었다(SBOM 쪽 판독은 옳았고 결함은 고지문 쪽이었다). 남은 2건(colorama·pywin32)은 **추정 라이선스를 선언하지 않고**(검증되지 않은 주장 금지), `미해결 ⊆ THIRD_PARTY_PROVENANCE.toml 의 marker_platform_packages` 를 회귀 17건(`tests/test_cr14_python_license_determinism.py`)이 고정한다. 재생성이 커밋된 라이선스를 미상으로 되돌리면(부실한 생성 환경) 테스트가 실패한다.
- **증거** — 증인 `cr14_f03_notices_sbom_divergence.py`: 수정 전 exit 1(불일치 42건 · 판독 실패 35건 · 미해결 41건) → 수정 후 exit 0(불일치 0건 · 판독 실패 0건 · 미해결=정책 선언). 전체 suite **6166 passed / 6 skipped**(453초)에서 `data/` 드리프트 0, **20 required gate 가 되돌리기 없이 단일 지문 `1981bfb5…` 에서 20/20 PASS**(docker 231.4s · clean-machine 41.3s · accessibility 35 · api-e2e 9 · 대시보드 80 files/846).
- **남은 blocker** — 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · **F-07(`clean-machine-runtime` 이 커밋된 HEAD 를 검증)** · **F-06(uuid 경유 moderate — 유일한 기술 결함)** · 독립 검토·출시 책임자 미배정 · C14-03/04/05 미완.
- **다음 한 단계** — CR-01~14 **커밋**(갱신된 `THIRD_PARTY_NOTICES.txt`·`dashboard.cdx.json`·`dashboard_dist` 포함)·clean full SHA → 그 SHA에서 20-gate 재실행(특히 `clean-machine-runtime`) → **F-06** → 독립 검토·출시 책임자 배정 → CR-14 attempt-006.

## 2026-09-12 CR-14 attempt-002 — P1·Docker OOM 폐쇄, **required gate 20/20 PASS** (판정 NO-GO 유지, 기록)

> **이 절이 최신 실측이다.** 판정 자체(출시 준비 관문)는 attempt-001과 같은 **NO-GO** 다 — 달라진 것은 차단 사유의 성격이다. attempt-001의 차단 사유는 기술적(required gate 실패·미실행, P1)이었지만, attempt-002의 차단 사유는 **사람과 커밋 위생**(필수 외부 승인 부재 · source mismatch)이다.

attempt-001이 남긴 P1을 닫고, attempt-001에서 **미실행**이던 required gate가 처음 돌면서 드러난 OOM까지 닫았다. 후보는 기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 **`ebbbd7f06fab3fb2d10008336ef96ba0d7949ee72007774c6372fc07f1bba0b5`**(2544 files).

- **판정: NO-GO 유지.** 계획서 판정 규칙의 네 조건 중 **P1과 required gate 실패/미실행은 해소**됐으나, **필수 외부 승인 부재(EX-01~EX-06)**와 **source mismatch(미커밋 → clean full SHA 없음)**가 남았다. 두 조건 모두 규칙상 NO-GO 사유다. GA 승인 없음 · CR-14 DONE 아님.
- **gate 실측: 20/20 실행 · 20/20 PASS**(attempt-001은 15실행/14PASS/1FAIL/4NOT_RUN). 단일 코드 지문 위에서 완주 — `python-tests`가 재작성한 `data/benchmark_results.json`(F-02)을 되돌려 지문을 유지했고, `dashboard-build`·`sbom-generate`는 자산명이 내용 해시라 멱등이어서 지문이 깨지지 않았다.
- **F-04(P1) 폐쇄**: `mermaid` `10.6.1 → 10.9.8`(lock 3종 동기화)로 `dependency-audit-dashboard`가 **PASS**(high 0). 승격이 **새 보안 회귀**를 드러냈다 — 10.9.8은 라벨의 raw `<img>`를 DOM에 **남겨** 절대 URL이면 **외부 요청(비컨)이 실제로 나간다**(실브라우저 캡처: `https://beacon.invalid/leak.png`). 컴파일된 계약 `C09-03`이 승격 직후 실패하며 드러났고, **출력 정화만으로는 늦다**(mermaid가 측정용 임시 DOM에 라벨을 넣어 정화 전에 요청이 나간다). `mermaidRuntime`에서 **입력 중화(deny-list) + 출력 구조 정화** 두 단계로 막았고, 이제 `C09-03`이 `blockedExternal: []`로 상시 감시한다.
- **F-05(신규) 폐쇄**: required gate `docker-build`가 처음 돌자 **14.5초에 heap OOM**(3/3 재현). 원인은 콜드 `tsc -b`이고, `node:22.13-alpine` 기본 V8 힙 상한이 **2096MB로 고정**(`--memory=4g`/`12g` 모두 동일 — 호스트 메모리로 회피 불가). dashboard-builder 스테이지에 빌드 한정 `ENV NODE_OPTIONS=--max-old-space-size=4096`를 추가해 **PASS(246.8s)**. 이미지 빌드에서 타입체크를 빼지 않았다.
- **신규 잔여 위험 F-06**: mermaid 경유 `uuid@9.0.1` moderate(`<11.1.1`). 감사 gate 임계값이 `high`라 차단되지 않는다 — **"게이트 초록"과 "위험 0"은 다르다.**
- **검증**: `pytest` **6124 passed / 6 skipped**(428초) · 대시보드 Vitest **80 files/846 passed** · 실브라우저 CR-09 4/4 · `accessibility-e2e` 35 passed · `docker-build` PASS · `clean-machine-runtime` PASS · ruff/format/mypy/basedpyright 0 errors.
- **남은 blocker**: 필수 외부 승인·조건(EX-01~06) · clean full SHA(미커밋) · F-01(`dashboard_dist` 추적 — 이후 attempt-003 실측으로 **GA blocker 에서 내려감**: 빌드는 멱등) · F-02(pytest 재작성 — attempt-003 에서 폐쇄) · F-03(라이선스 환경 의존) · F-06(uuid moderate) · 독립 검토·출시 책임자 미배정 · C14-04/C14-05 NOT_RUN.
- **다음 한 단계**: F-02(`data/benchmark_results.json` 격리) → F-01(`dashboard_dist` 정책) → CR-01~14 커밋·clean full SHA → 그 SHA에서 20-gate 재실행 → 독립 검토·출시 책임자 배정 → CR-14 attempt-003.

## 2026-09-12 CR-14 attempt-001 최종 후보 검증 — **판정 NO-GO** (기록)

> **이 절은 attempt-001 시점의 기록이며 최신 실측이 아니다.** 당시 기준을 그대로 보존한다 — 과거 FAIL을 PASS로 재라벨링하지 않는다. 출시 준비 판정의 단일 원본은 [17번 체크리스트](./17_COMMERCIAL_RELIABILITY_CHECKLIST.md)이고, 이번 판정의 상세 근거와 재개 순서는 [ga/CR14_FINAL_CANDIDATE_VERDICT.md](./ga/CR14_FINAL_CANDIDATE_VERDICT.md)에 있다.

CR-01~CR-13을 통합한 후보(기준 `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f` + 미커밋 patch, 코드 지문 `11979d6c…`)에서 계획서 §CR-14의 전체 검증을 수행했다.

- **판정: NO-GO. GA 승인 없음. CR-14는 DONE이 아니다.** 계획서의 판정 규칙 5개 조건이 모두 해당한다: P1 미해결 · required gate 실패 · required gate 미실행 · 필수 외부 승인 부재 · clean full SHA 없음.
- **gate 실측**: 20 required gate 인벤토리 중 **15 실측 = 14 PASS / 1 FAIL / 4 NOT_RUN**.
  - FAIL 1건: `dependency-audit-dashboard` — `mermaid@10.6.1` ∈ 취약 범위 `<=10.9.2`, GHSA-m4gq-x24j-jpmf (**high**), patched `>=10.9.3`. **로컬에서 재현되는 P1이며 외부 조건과 무관하다.** 이 gate는 이번에 처음 실행됐다(CR-11은 파이썬 감사만 확장했고, CR-09이 mermaid를 정식 의존성으로 승격한 시점에도 대시보드 감사는 돌지 않았다).
  - NOT_RUN 4건: `docker-build` · `master-e2e` · `accessibility-e2e` · `clean-machine-runtime`.
- **닫은 결함**: ① CR-13의 승인 우회로 — `required_gates`를 비우면 gate 검사를 통째로 건너뛰고 `PASS`를 냈다. 이제 `evidence_kind`(`release`|`reference`)가 필수이고 `release`는 빈 목록을 거부하며, 참고 번들은 `REFERENCE_ONLY`(exit 3)로 분리된다. ② 검증 실행이 추적 중인 `src/antigravity_k/release/*`를 덮어쓰던 REL-01 테스트 경로 — `tmp_path`로 옮기고 저장소 드리프트 검사 2건을 새로 만들었으며, 그 과정에서 저장소 사본이 CR-09 이후 낡아 있던 사실이 드러나 재생성했다. ③ `ga_gate.py --merge-into`(같은 후보 SHA·manifest·코드 지문일 때만 단계별 결과를 이어받음).
- **신규 결함 4건**: **F-01** 추적 중인 `src/antigravity_k/dashboard_dist/`가 빌드마다 자산 39개 삭제 + 87개 신규 생성(총 127 변경) — ← **attempt-003 실측으로 정정: 빌드는 바이트 단위 멱등이고 지문도 불변이다. dirty 의 원인은 커밋된 HEAD 번들이 낡은 것**이다(`docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md §0-B`). CR-10/CR-11 “stale bundle” blocker와 `clean-machine` gate가 낡은 UI를 포장하는 문제의 뿌리. **F-02** 상용 pytest suite가 `data/benchmark_results.json`을 재작성(CR-13 R03 드리프트의 뿌리). **F-03** release 문서의 파이썬 라이선스가 `importlib.metadata`로 실행 환경에서 읽혀 같은 후보·같은 lock인데도 값이 달라짐 — **attempt-005 실측으로 정정·폐쇄: 실질 원인은 환경이 아니라 고지문과 SBOM 이 각자 다른 함수로 판독한 것이다(42건 불일치, 35건은 판독 실패).** **F-04** mermaid high(P1).
- **검증**: `python-tests` **6123 passed / 7 skipped**(447초), 나머지 13개 실측 gate 전부 exit 0(ruff·format·mypy·basedpyright·bandit·package-build·dashboard install/lint/typecheck/test(80 files/840 passed)·sbom-generate·api-e2e). 신규 회귀 `tests/test_cr14_candidate_evidence.py` 13건.
- **재개 순서(권장)**: F-04(mermaid) → F-02 → F-01 → 코드 커밋·clean full SHA → 20-gate 전부 실행 → 독립 검토 배정 → 외부 조건 확보 후 C14-03/04/05. **(attempt-003 실측 정정: F-02 는 닫혔고 F-01 은 "비결정성"이 아니라 "낡은 HEAD 번들" 문제로 내려갔다 — 순서는 "갱신된 번들을 포함해 커밋 → 새 SHA 에서 20-gate 재실행"이 된다.)**

## 2026-09-12 상용 신뢰성 개선(CR-01 ~ CR-13) REVIEW

2026-09-11 상용 검토(`docs/qa/2026-09-11-commercial-review/BASELINE.md`)의 발견을 기준 SHA `08b8bb2e94f92a1d95d4a38b7d1171a58b9fe04f`에서 재분류하고, 새 경계 13건(CR-01~CR-13)을 구현했다. 계획·체크리스트는 [16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md](./16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md) · [17_COMMERCIAL_RELIABILITY_CHECKLIST.md](./17_COMMERCIAL_RELIABILITY_CHECKLIST.md)이며, **이 시점부터 출시 준비 판정의 단일 원본은 10번이 아니라 17번 체크리스트다.**

- **상태**: CR-00 DONE(사용자 위임 개방) / CR-01 ~ CR-14 **REVIEW**(코드 **미커밋**, 독립 검토 미배정) / **GA 승인 없음**. REVIEW는 독립 검토자 동일 SHA 승인 전이므로 DONE이 아니다. (이 절의 표기는 `CR-14 TODO`였으나, CR-11~14 구현이 끝나 REVIEW로 올라가면서 정정했다 — 계획서·체크리스트와 동일하게 맞춘다.)
- **닫은 결함**: 대화 ID 충돌·저장 형식 이전(CR-01) · 세션 저장 0바이트 유실·동시 writer(CR-02) · sandbox 읽기 누출(CR-03) · API shell의 권한 모드 무시·env 상속(CR-04) · provider 키의 브라우저 영속(CR-05) · 설정 화면이 서버 진실 미반영(CR-02/06) · 오류 경계·404 부재(CR-07) · provider 입력의 접근성 이름 부재·팔레트 modal 계약 부재·IME 조합 Enter 오인(CR-08) · 필수 렌더링의 CDN 의존과 오프라인에서 편집기가 뜨지 않던 문제(CR-09 — Monaco CDN 로더는 그때 실측으로 추가 발견) · **고정 운영 지표와 빌드 provenance 부재(CR-10 — BUILD/UPTIME/NODE/CTRL 하드코딩, 업타임이 프로세스가 아니었고 화면이 percent를 MB로 표시)** · **설치 전에 src-layout 모듈을 실행하던 CI/release 부트스트랩과 출하되지 않는 의존성만 감사하던 경로(CR-11 — `[rag]`가 한 번도 감사되지 않아 chromadb 권고 4건이 gate에 도달하지 못했고, 예외 레지스트리 id도 도구 출력과 불일치)** · **확장 README가 없는 능력("Automatic reconnection and offline support")을 광고하던 문제와 승인 미완료가 상태로 표시되지 않던 문제·인수 절차 부재·과거 RP와 현재 CR 상태 혼동(CR-12 — 배경 재연결·오프라인 큐는 계획대로 신설하지 않고 문구를 실제 계약으로 교체)** · **이전 후보 증거의 재사용과 비불변 artifact(R03 — RP-13 manifest의 artifact 1건 드리프트에도 `manifest_verifier: PASS` 선언이 남았고 참조 11개가 전부 호스트 절대 경로였음; R04 — RP-12 후보 증거가 현재 후보 검증에 그대로 쓰일 수 있었음. CR-13 — 증거를 자기완결 번들로 만들고 후보 SHA·gate·soak에 묶음)**. 구체 계약은 `08_CHANGELOG.md`의 2026-09-12 절과 각 attempt의 `decision.md`에 있다.
- **검증**: CR-01~13 게이트 통과 — 전체 Python suite **6102 passed/13 skipped**(CR-13 기준, 449s), 대시보드 Vitest **80 files/840 passed**, Playwright 실제 chromium: CR-10 텔레메트리 4 passed·CR-09 오프라인 4 passed·접근성·키보드·복구 회귀 79 passed, `tsc -b`·`eslint`(0 errors)·`vite build` exit 0, ruff·format·mypy exit 0, basedpyright 0 errors, `test_dashboard_wheel_assets.py` 1 passed. CR-12는 정적 증인으로 HEAD 트리에서 **5/5 문서·문구 결함 재현(exit 1)** 후 현재 트리에서 **0건(exit 0)**을, 같은 HEAD 트리에서 새 회귀 테스트 **15 failed** 후 현재 트리 **25 passed**를 실측했다. CR-11은 HEAD 트리에서 같은 프로브로 **4/4 결함 재현(rc=1)** 후 현재 트리에서 **4/4 해소(rc=0)**를 실측했고, 감사 게이트·저장소 밖 wheel/sdist 검증·번들 hash 대조를 모두 exit 0으로 통과했다. 재현→수정→회귀 순서와 로그 원문은 `.omo/evidence/commercial-reliability/CR-0X/attempt-001/logs/`에 보존했다.
- **남은 blocker**: ① 독립 검토 미배정(CR-01~13 전부 — CR-12는 증인의 부정문 판정 로직, CR-13은 `required_gates`를 비우면 gate 검사를 건너뛰는 우회 경로가 검토 대상이다). 그리고 **법무·개인정보·보안·provider 약관 승인 미취득**(`BLOCKED_EXTERNAL`, 해제 주체는 외부 당사자뿐이고 CR-14 GO/NO-GO에서 열린 blocker로 유지 — CR-12가 상태로 표시한 것이지 해소한 것이 아니다) ② 커밋 full SHA 미확정 — 승인 전 동일 SHA에서 전체 게이트 재실행 필요 ③ **커밋 재빌드 정책 미정** — attempt-002에서 mermaid 승격을 반영해 `dashboard_dist`를 **재빌드된 상태로 남겼다**(HEAD로 되돌리지 않았다. HEAD 번들은 소스와 다른 취약한 코드를 담는다). 추적 자체를 계속할지·커밋 시점에 재빌드할지는 출시 책임자 결정이다(F-01). CR-11부터 CI·릴리스는 패키징 전에 재빌드하고 새 번들이 wheel에 들어갔는지 hash로 대조하지만, `clean-machine` gate는 `git archive HEAD`를 쓰므로 **추적 번들이 낡아 있으면 그 gate는 낡은 UI를 포장한다** ④ 실제 스크린리더 낭독·Firefox/Safari 접근성 미실측(자동 gate만 통과)와 CR-10의 다중 worker `process_id`·장기 stale 전이 미실측 ⑤ CR-03의 Linux/Docker sandbox backend 미실측 ⑥ CSP의 CDN 허용 목록 정리(CR-09 D-08)와 Mermaid 클로저의 EPL-2.0(elkjs) 고지 요건은 보안/법무 검토 대기 ⑦ chromadb 탐지 4건의 예외 만료 **2026-12-08**(상류 fix 확인 필요) ⑧ hosted GitHub Actions 실행 미실측(새 job 배선은 YAML 파싱·스크립트 직접 실행·계약 테스트로만 검증).
- **해소**: CR-07이 남긴 "접근성 게이트 매트릭스에 404 화면 미포함"은 CR-08 D-06이 닫았다(UI-01·UI-02 매트릭스 16 → 17 route, 404 화면 위반 0).
- **운영 영향**: CR-01은 legacy 대화 파일 잔존 시 503 fail-closed(런북 이전 필요), CR-02는 구버전 프로세스와 동시 실행 미지원, CR-04는 `security.sandbox_enabled=false` 배포에서 `/api/agent/tools/shell/run`이 동작하지 않음, CR-05는 `GET /api/settings` 응답 형태 변경(파괴적 변경)과 legacy 키 재입력 가능성, CR-08은 팔레트가 열린 동안 배경이 `inert`(사이드바·상단 바 포함)이고 공용 훅은 팔레트에만 적용(다른 모달은 아직 미적용), CR-09는 필수 렌더링이 더 이상 CDN에 의존하지 않으나(폰트 시스템 스택·테마 로컬 번들·Mermaid 지연 import·Monaco 로컬 워커) Mermaid 클로저가 런타임 의존성으로 늘어나 SBOM/notice가 커지고 `declared_licenses` 유지보수가 필요하다. CR-10은 헤더 지표가 더 이상 고정 문자열이 아니게 됐다 — `BUILD`는 실제 서버 버전, `UPTIME`은 프로세스 monotonic 가동 시간(재시작 시 0부터), 값이 없으면 `UNKNOWN`, 연결이 끊기면 `healthy: null`로 `NOMINAL`을 주장하지 않음, `MEM`은 `%`(`memory_percent`), `LINK`가 `LIVE`/`STALE`(30s 초과)/`OFFLINE`(고정 `CTRL` 문구는 삭제). legacy `memory_mb` 키는 percent 값인 채로 남아 있고, `uptime_seconds`의 의미가 "벽시계 차이"에서 "프로세스 가동 시간"으로 바뀐다(호스트 업타임이 필요하면 별도 지표가 필요하다). 계약은 [런타임 텔레메트리 문서](./ga/CR10_RUNTIME_TELEMETRY.md). **CR-11은 CI·릴리스가 설치 없는 src-layout 실행과 출하되지 않는 의존성 감사에 기대지 않게 했다** — Python 게이트는 `uv sync --locked --no-editable --extra dev` 한 환경에서 돌고 감사는 base + 출하 extra(`[rag]`)를 대상으로 하며(입력 기록·음성 입력 거부), Node/pnpm은 Node 22.13 + pnpm 11.3.0으로 통일됐다. 그 결과 **chromadb 1.5.9 권고 4건이 처음으로 gate에 도달**했고 REL-03 예외(owner·만료 2026-12-08)로 판정된다. 릴리스는 패키징 전에 대시보드를 재빌드해 새 번들이 wheel에 들어갔는지 hash로 대조하고, `dry_run` 입력이 실제로 소비되어 수동 실행은 아무 것도 배포하지 않는다. 계약은 [릴리스 부트스트랩 문서](./ga/CR11_RELEASE_BOOTSTRAP_AND_AUDIT.md). **CR-12는 지원·운영 문구를 실제 동작에 맞췄다** — VS Code 확장은 context-sync companion이고 **배경 재연결 타이머·오프라인 큐가 없다**(엔진이 죽어 있으면 다음 편집기 이벤트에 재시도)이므로 “자동 재연결·오프라인 지원”으로 설명하는 문구는 더 이상 쓸 수 없다. 미완료 승인은 주장 레지스트리·지원 매트릭스에서 `BLOCKED_EXTERNAL`(해제 주체 명시)로 보존되며 **플랫폼·provider 분류는 하나도 승격되지 않았다**(전부 Experimental/Unsupported). 런북 3종(세션 저장 실패 · 키 재입력 · sandbox unavailable)이 운영 절차의 단일 원본이다.
- **운영 영향(CR-14 attempt-002)**: ① `Dockerfile` dashboard-builder 스테이지의 `ENV NODE_OPTIONS=--max-old-space-size=4096`를 지우면 `docker-build`가 다시 콜드 `tsc -b` heap OOM으로 실패한다(로컬 빌드 성공은 컨테이너 성공을 의미하지 않는다). ② 라벨 주입 차단은 `mermaidRuntime`의 **두 지점**에 의존한다 — 한쪽만 남기면 비컨이 되살아난다(`dashboard/e2e/tests/cr09-offline-assets.spec.ts`의 `C09-03`이 상시 감시자이며, 이 단언을 약화시키는 변경은 F-04를 되돌리는 것이다). ③ `python-tests` 실행 뒤 `git checkout -- data/benchmark_results.json`을 하지 않으면 새 코드 지문이 생겨 단계별 gate 병합이 거부된다.
- **운영 영향(CR-13)**: 릴리스 증거는 **자기완결 번들**로만 승인 가능하다 — artifact가 번들 안 상대 경로에 복사되고, hash는 redaction 이후 바이트에서 계산되며, `--expected-sha`로 후보 SHA에 묶인다(다른 후보 증거 재사용은 거부). 번들은 `verdict`/`status` 자기 승인을 적을 수 없고(판정은 검증기 출력), **`required_gates`를 비우면 gate 검사가 사라진다** — CR-14가 반드시 채워야 한다. 과거 후보 증거는 `historical: true` 참고용만 가능하며 gate/soak 근거가 될 수 없다. 계약·절차는 [증거 번들 문서](./ga/CR13_EVIDENCE_BUNDLE.md).
- **다음 작업**: **CR-14 attempt-003**(최종 후보 전체 검증과 GO/NO-GO). 순서는 F-02(`data/benchmark_results.json` 격리) → F-01(`dashboard_dist` 정책) → CR-01~14 커밋·clean full SHA 확정 → 그 SHA에서 20-gate 재실행 → `scripts/evidence_bundle.py build`로 릴리스 번들을 만들고 `required_gates`를 **반드시 채운** 뒤 `verify --expected-sha`로 고정 → 독립 검토·출시 책임자 배정 → C14-03/04/05. attempt-002에서 required gate 20/20 PASS를 달성했으므로 **다음 변경은 그 지문 위에서 다시 검증**해야 한다.
