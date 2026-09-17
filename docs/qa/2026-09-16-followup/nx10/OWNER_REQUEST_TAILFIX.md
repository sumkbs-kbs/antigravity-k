# 오너/타 레인 요청 — 꼬리 창 수정 뒤 남은 결정 4건 (2026-09-17)

이 카드(NX-10)가 **코드로 닫을 수 있는 것은 전부 닫았다**. 남은 네 가지는 이 카드의 변경이 아니라
다른 레인의 기록·정책이므로 **고치지 않고 요청만 한다**(§6 의 경계 규칙). 각 항목에 근거와 1줄 수리안을 붙인다.

현재 후보: 코드 커밋 `7d8c25b5`(꼬리 창 수정) · 지문 **`98855031…`** · HEAD `aa1ead1f`(문서 커밋들).
필수 23개는 이 지문에서 **22 passed · 1 failed · 0 not_run**(`gate-report-tailfix001.json`).

---

## R1. CR-14 후보 재선언 — 필수 게이트 `python-tests` 의 빨간 3건을 닫는 유일한 길

- **무엇**: `tests/test_cr14_fence_movement_detection.py` 3건이 빨간색이다.
  ① `test_no_code_scope_commit_after_the_declared_candidate` ② `test_declared_fingerprint_is_the_fingerprint_of_head_within_the_fence`
  ③ `test_worktree_matches_the_declared_fingerprint_when_the_code_scope_is_settled`.
- **왜 설계상 빨간색인가**: 이 시험은 “선언된 후보 뒤에 **코드 스코프를 건드린 커밋이 없어야 한다**”를
  요구한다. NX-10 은 그 뒤에 `src/` 를 한 번 고쳤다(꼬리 창 수정 `7d8c25b5`) — 그래서 빨간색이다.
  그리고 ③ 은 `promote004` 에서도 이미 빨간색이었다(내 수정이 만든 것이 아니다 — **정정**: 종전 기록의
  “CR-14 울타리 2건”은 오기이고 실제는 3건이다. [GATE_LEDGER.md](./GATE_LEDGER.md) §17-1).
- **요청**: CR-14 레인이 현재 지문을 후보로 **재선언**하거나, 울타리 규칙의 적용 시점을 조정한다.
  (카드 규칙상 이 면제를 NX-10 이 스스로 선언할 수 없다 — “원인별 면제 없음”.)
- **증거**: `gate-report-tailfix001.json`(23/1/0) · `gate_verify-tailfix001.txt`(지적 1개) · `promote-runner-exit.txt`.

## R2. `EX-05` 대장 행의 두 단계 분리 — 지금 빨간 NX-07 계약 2건의 원인

- **무엇**: `docs/ga/CR14_EX_EXECUTION_LEDGER.md` 의 EX-05 행 상태 셀이 한 단어 `**PASS** (resoake Decision A)` 이다.
- **왜 문제인가**: 그 실행(③ 재soak, `all_pass: true` · `rss_growth_mb 48.7`)의 **④ 종료·귀속은 UNVERIFIED** 다
  (`docs/20` §3 ④ 행). 카드의 규칙 — “지표만 통과한 상태를 soak PASS 로 승격하지 않는다” — 을 정면으로 어긴다.
  `tests/test_nx07_doc_consistency.py` 의 2건(`test_soak_phases_stay_separated` ·
  `test_teeth_soak_done_promotion_is_detected`)이 정확히 이 자리를 잡는다.
- **중요**: 이 2건은 **이미 커밋된 트리에서도 실패한다**(`git show HEAD:` 로 두 문서를 꺼내 판정 함수를 돌려
  확인 — NX-10 의 변경이 만든 것이 아니다).
- **1줄 수리안(그 레인의 문서에서)**: 상태 셀을 `**PASS(JSON 지표)** · INCONCLUSIVE(귀속 미확정)` 처럼
  두 단계로 적는다. 지표 값과 귀속 상태를 한 단어로 뭉개지 않는다.
- **부수 확인**: 오늘의 증거가 이 계약을 지지한다 — 지표만 보고 `PASS` 로 적힌 그 실행은 진행 중
  코드 후보가 계속 바뀌었고, 그래서 “어느 후보의 PASS 인가”를 사후에 말할 수 없었다.

## R3. 독립 검토자 지정 — 카드 §선행의 마지막 빈칸

- **현재**: 판정자 공백을 숨기지 않고 그대로 기록해 두었다([handoff.md](./handoff.md) §7·§9).
  오너 허용 기록(`SCOPE.md` 의 비차단 허용)도 **없다**.
- **요청**: 독립 검토자 지정 + 허용 여부 기록. 이 카드가 스스로 “검토자 없음”을 지우면 그건 조서 조작이다.
- **검토자가 먼저 볼 것**: ① 이 FAIL 의 원인이 **측정으로** 닫혔는가(§3 근거: `tail()` 3회·814 ms 중 810 ms)
  ② 수정이 계약 시험 2건으로 고정됐고 **수정 전 구현에서 실제로 빨개지는가** ③ 재실행 결과가 지문에 귀속되는가.

## R4. 두 위생 결정 — `vault_data` 소유와 1MiB 증거 정책

- **`vault_data`**: `git status` 에 계속 ` M vault_data` 로 뜬다(gitlink, 소유 불명). NX-10 이 만들지 않았고
  지문에는 `missing` 으로 들어가므로 측정을 오염시키지는 않지만, **누가 소유하는지 모르는 변경이 작업 트리에
  상존하는 것**은 다음 사람이 “내가 건드렸나?” 를 매번 다시 묻게 만든다. → 소유 레인 지정 또는 회수.
- **1MiB 초과 게이트 리포트**: 정책(`check-added-large-files --maxkb=1024`)대로 커밋하지 않고
  `large-evidence-manifest.md` 에 sha256 으로만 남긴다(현재 7개). 이 방식이 맞는지, 아니면 LFS/압축 같은
  정식 경로를 쓸지 결정이 필요하다 — 지금은 **증거는 디스크에만 있고 git 에는 해시만** 있다.

---

## R5. 로컬 실행(`.venv/bin/python -m pytest`)과 게이트 실행의 결과가 **8건 다르다** (2026-09-17)

**정정: 게이트는 영향을 받지 않았고, 이 항목은 차단 요인이 아니다.** 재측정 `sc3fix001` 의 `python-tests`
결과는 `5 failed, 6626 passed` — 실패 5건은 `promote004` 와 시험 단위로 동일(CR-14 울타리 3 · NX-07 문서 2)이고,
6621 → 6626 의 차이는 **이 창이 추가한 계약 시험 5건**이다. 아래 8건은 **로컬 환경에서만** 나온다
(게이트는 `uv run --isolated --frozen` 으로 돌아 이 홈 저장소를 보지 않는다).

로컬에서만 보인 이유와 그 내용:

- 로컬 실패 8건: `tests/test_ws01_project_binding.py` 5 · `tests/test_agent_runtime.py` 3 — 모두 API 503
  `conversation_storage_migration_required`.
- 원인: 이 기기의 **실제 홈** 저장소 `~/.antigravity/conversations` 에 **v2 이전 레거시 레코드 3건**이 있고
  마이그레이션 표식(`migration_v2.json`)이 없다(파일 시각 09-10~09-11). 그래서 `TestClient` 가 기본 저장소를
  쓸 때마다 `conversation_store._assert_storage_ready()` 가 거절한다.
- 필요한 결정(우선순위 낮음): (a) 문서화된 마이그레이션을 **이 홈 저장소에** 실행한다
  (`scripts/migrate_conversation_storage.py`, 개인 데이터라 오너 승인 필요), 또는
  (b) 시험 쪽이 대화 기본 저장소도 격리하게 고친다(conftest 는 `~/.antigravity/sessions` 만 격리한다 —
  **기기 상태에 따라 로컬 스위트가 갈리는 것** 자체가 시험셋 결함 후보다), 또는
  (c) 그대로 두고 “로컬 실행은 게이트와 8건 다를 수 있다”를 문서로만 남긴다(게이트는 깨끗하다).
- 그리고 이 관측은 **“새 실패 0건” 주장을 어떻게 확인했는가**의 예시다: 로컬 8건을 그대로
  믿었으면 있지도 않은 회귀를 찾아 밤을 썼을 것이다. 확인은 게이트 리포트의 실패 시험 목록을
  직전 attempt(`promote004`)의 실패 목록과 시험 단위로 맞대는 것으로 했다.

## R6. 교차 레인 편집 기록 — `project_registry.py` 를 이 창이 고쳤다

어제까지는 타 레인 파일을 **고치지 않고 증거만** 올렸는데(EX-05 대장 행), 이번에는 고쳤다. 이유:

- 그 파일이 SC-3 시나리오의 대상이고 그 결함이 **실행을 멈춰 버렸다** — 제품 결함을 그대로 두면
  8시간이 또 같은 자리에서 멈출 수 있다(시나리오가 간헐 재현이라 다음 실행마다 운에 갈린다).
- 동작은 안 바뀐다: 최초 생성이 lock 안으로 들어가고(경합에서 진 쪽은 이긴 쪽 파일을 읽는다),
  임시 파일 이름이 pid 로 고유해진다 — 시그니처·응답·계약 이름은 그대로다.
- 계약 시험은 기존 파일(`tests/test_project_registry_atomic.py`)에 **추가**했고 임계값을 완화하지 않았다.
  커밋: `c522b256`. 소유 레인(WS-01/BR-03)이 다르면 되돌림 사유를 밝혀 주시면 즉시 분리한다.

---

## 이 요청이 주장하지 않는 것

- 후보를 GO 로 만들지 않는다: 8시간 재실행은 **중단 뒤 재개 대기**고(SIGTERM 2회 — SC-3 결함 2건, §3f),
  회수 판정이 아직 없으며, R1~R3 이 그대로면 required red 1은 남는다.
- R1 을 “규칙을 느슨하게 하자”로 읽지 않는다 — 재선언은 **후보를 새로 고정하겠다는 선언**이지 면제가 아니다.
