---
title: Ssak-Ai 최종 검토 후 상세 개선 개발계획서
status: executing (RP-00 DONE, RP-01..07 REVIEW — 구현·실측 완료·독립 검토 이연, RP-08 이후 미착수)
date: 2026-09-10
reviewed_sha: 8794aaecabf5664a7ee560b104e0115d915aabb7
source_review: docs/qa/2026-09-10/FINAL_REVIEW.md
checklist: docs/15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md
tags: [development-plan, remediation, handoff, commercialization]
---

# 최종 검토 후 상세 개선 개발계획서

## 1. 목적과 문서 사용법

최종 검토에서 남은 결함을 수정하고, 프로젝트 폴더와 컨텍스트 압축의 사용자 경로를 입증한 뒤, 같은 출시 후보 SHA에서 재승인받는다. 이 문서는 **앞으로 실행할 작업 명세**다. 문서 작성은 결함 수정 완료가 아니다. 실행 체크리스트는 모두 미완료로 시작한다.

작업자는 자신의 작업 카드 하나만 맡아 순서대로 실행한다. 구현자는 `REVIEW`까지만 변경할 수 있고, 독립 검토자가 증거를 확인해야 `DONE`으로 전환한다. 상용화 100%는 아래 필수 작업 전체 완료와 최종 출시 판정에 한해 표시한다. 기능이 존재한다는 것, 테스트가 몇 개 통과했다는 것, 보고서에 GO라고 쓰였다는 것은 서로 다른 사실이다.

문서 우선순위:

1. 사용자의 최신 지시 및 적용되는 AGENTS.md.
2. 원래 상용화 범위와 필수 수용 기준: `docs/11_COMMERCIAL_GA_100_PLAN.md`.
3. 이번 결함과 재검증 범위: 본 문서 및 `docs/15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md`.
4. 관찰 근거: `docs/qa/2026-09-10/FINAL_REVIEW.md` 및 영역별 보고서.
5. 과거 DONE/100점 기록은 역사적 자료이며 이번 열린 항목을 닫지 않는다.

이 문서의 경로는 저장소 루트 기준이다. 현재 루트는 `/Users/mr.k/program/coding/ssak_comp/Ssak-Ai`다. 라인 번호는 검토 SHA의 위치이므로 작업 시작 시 심볼로 재검색한다. 제안된 새 테스트 파일은 아직 존재하지 않을 수 있으며 반드시 “신규 작성 대상”으로 구분한다.

## 2. 현재 확정 사실과 미검증 범위

- 기준 SHA: `8794aaecabf5664a7ee560b104e0115d915aabb7`. 기존 RC SHA는 `2ae967ad7c57513de9b6d3f8e1753e1a5be243b9`다. 이후 실제 제품 코드가 변경돼 기존 RC 결과를 재사용할 수 없다.
- FR-01~05: host 코드 실행, shell 확장 우회, transaction 경로 이탈, 전체 트리 rollback, worker 간 대화 캐시 정합성 결함.
- FR-07: Chroma 삭제 검증의 false-green. **VectorStore 삭제 자체가 실패한다고 확정한 것은 아니다.**
- FR-10: `config.yaml`의 agent 기본값이 `src/antigravity_k/config.yaml`에 없어 테스트가 실제 실패한다.
- 대시보드 750 tests/typecheck/build 통과는 실행자 요약 기록이다. 브라우저 전환/압축 관찰의 원본 action log는 누락됐다. 이번에는 실행 직후 원문을 저장해야 한다.
- 실 cloud provider, 실제 8시간 soak, 선택 파일 내용→실 provider prompt, 자동/수동 압축 UI 전체 경로는 여전히 검증해야 한다.
- 시작 시 `vault_data`에 기존 변경이 있었다. 이를 수정·정리·초기화 대상으로 취급하지 않는다.

## 3. 작업자의 공통 규칙

### 3.1 시작 절차

1. `git rev-parse HEAD`, `git status --short`를 실행해 기준과 작업 트리 상태를 기록한다. 사용자 변경을 stash/reset/clean으로 없애지 않는다.
2. 체크리스트에서 선행 작업이 완료됐는지 확인하고, 담당자·branch/worktree·소유 파일을 기록한다. 작업 중인 파일에 다른 작업자가 있으면 조정자가 소유권을 먼저 정리한다.
3. 코드 탐색은 codebase-memory `search_graph` → `get_code_snippet` → 필요한 `trace_path` 순서다. graph 미색인 시 index부터 실행한다. 결과가 부족할 때만 파일 검색으로 보완한다.
4. 작업 카드의 파일과 호출자를 읽는다. 새 공용 abstraction을 만들기 전에 기존 함수가 요구를 충족하는지 확인한다.
5. 재현은 임시 디렉터리·임시 Git repo·테스트 전용 DB에서 한다. 실제 사용자 HOME, vault, 작업 파일을 공격 테스트에 사용하지 않는다.
6. 필요한 런타임·자격증명·승인 자료가 없다면 어느 단계가 막혔는지 적는다. 나머지 독립 작업은 계속한다. 누락을 skip/pass로 바꾸지 않는다.

### 3.2 구현 및 완료 규칙

- 경로 문자열 필터만으로 실행 격리를 보장하지 않는다. `cwd`, `shell=False`, 임시 폴더 각각도 독립적인 보안 경계가 아니다.
- 테스트가 실패한다고 assert 삭제, `xfail`, 광범위 skip, 임계값 완화, fixture의 성공값 고정으로 통과시키지 않는다.
- provider double은 결정적 회귀 테스트에 사용할 수 있다. 실 provider/실 sandbox/브라우저 검증을 대체하지 않는다.
- mock 대상은 외부 LLM 응답 등으로 제한한다. 검증해야 할 sandbox, CAS, rollback, 경로 검사를 mock해 성공으로 만들지 않는다.
- 외부 라이브러리 도입, API 계약 변경, 공용 lock 형식 변경, OS 지원 확대는 조정자에게 설계 검토를 요청한다. 작업자가 큰 대안을 독단적으로 택하지 않는다.
- 사용자/모델 입력을 로그에 무조건 남기지 않는다. 실 증거에는 합성 데이터만 사용하고 인증 토큰·쿠키·API key는 제거한다.
- 이 계획 작성은 push/배포/브랜치 삭제/사용자 데이터 초기화 권한을 부여하지 않는다. 구현 단계의 커밋·통합은 그 시점 사용자 권한과 저장소 규칙을 따른다.

## 4. 역할, 순서, 충돌 방지

조정자는 전체 상태·통합·증거 인덱스를 담당한다. 각 구현자는 아래 소유 파일만 수정한다. 독립 검토자는 자신이 구현하지 않은 작업의 원문 diff와 재현 결과를 확인한다. 한 사람이 구현·검토·최종 승인을 동시에 대신할 수 없다.

| 순서/ID | 작업 | 대응 발견 | 선행 | 주 소유 파일 | 난이도 |
|---|---|---|---|---|---|
| RP-00 | 기준·증거 디렉터리·실행 환경 확정 | 공통 | 없음 | 체크리스트, 증거 metadata | 낮음 |
| RP-01 | UnifiedAgent 격리 실행 | FR-01 | RP-00 | unified_agent.py, sandbox.py, agent_ask.py | 높음, 설계 검토 필수 |
| RP-02 | shell 실행 경계 강제 | FR-02 | RP-01 | terminal_tools.py, permission_gate.py, tool_path.py의 shell 함수 | 높음 |
| RP-03 | 파일 transaction 경계·복구 | FR-03 | RP-02 | atomic_transaction_engine.py | 중간~높음 |
| RP-04 | RSI mutation 격리·부분 복구 | FR-04 | RP-03 | rsi_sandbox.py 및 확인된 호출자 | 높음, 설계 검토 필수 |
| RP-05 | 대화 저장소 최신 읽기/CAS | FR-05 | RP-04 | conversation_store.py, 관련 API | 높음 |
| RP-06 | Chroma 판정 및 staging 실패 처리 | FR-07 | RP-05 | val01_staging.py 및 신규 회귀 테스트 | 중간 |
| RP-07 | 기본 설정·wheel 정합성 | FR-10 | RP-06 | config.yaml, 번들 config, 필요 시 빌드 설정 | 낮음~중간 |
| RP-08 | 선택 폴더→실 요청 검증·수정 | 폴더 증거 공백 | RP-07 | project_binding/dependencies, ChatPage/client, 신규 E2E | 중간~높음 |
| RP-09 | 자동/수동 압축 종단간 검증·수정 | 압축 증거 공백 | RP-08 | stream/tool_loop, ChatPage/projection, 신규 E2E | 중간~높음 |
| RP-10 | 승인·지원·완료 기록 정합성 준비 | FR-08 | RP-09 | docs/ga, docs 10~15, .omo mirror | 중간, 일부 외부 판단 |
| RP-11 | 필수 gate·증거 수집기 정비 | FR-06/09 | RP-10 | staging/gate scripts, manifest 생성·검증 | 중간~높음 |
| RP-12 | 후보 고정·실 provider·8시간 soak | FR-06 | RP-11 | 외부 증거팩만, 제품 코드 변경 금지 | 장시간 운영 검증 |
| RP-13 | wheel/container/복구·manifest | FR-09/10 | RP-12 | 외부 산출물·manifest | 중간~높음 |
| RP-14 | 같은 SHA 독립 재검토·최종 판정 | 전체 | RP-13 | 최종 리뷰·승인·체크리스트 | 독립 검토 |
| RP-15 | 유지보수 개선, 선택 작업 | 품질 보조 지적 | RP-05 이후, 후보 고정 이전 | budget enforcer/테스트 | 별도 판단 |

기본 실행은 위 순서대로 한 작업씩이다. 조정자가 병렬 작업을 배정하는 경우에만 RP-05와 RP-01~04를 분리할 수 있다. RP-06/07도 독립 파일이라 병렬 가능하나 통합 후 재검증한다. `sandbox.py`는 RP-01 담당자만, `tool_path.py`는 RP-02 담당자만 수정한다. RP-03이 helper 변경을 원하면 RP-02 담당자에게 요청하고 직접 덮어쓰지 않는다. RP-08/09의 ChatPage 공통 파일은 순차 작업한다. RP-15를 실행하면 RP-09/11 전에 통합하며 최종 SHA 이후 끼워 넣지 않는다.

## 5. 상세 작업 카드

### RP-00 — 기준 확정과 증거 준비

**목표:** 이후 작업을 다른 에이전트가 정확히 재개할 수 있는 기록 확보.

1. 최종 보고서와 FR-01~10, 기존 계획의 RC/VAL 기준을 읽는다.
2. 현재 HEAD와 검토 SHA의 차이를 확인한다. 바뀐 코드가 있으면 해당 결함을 재현해 STILL_OPEN/ALREADY_FIXED/UNVERIFIED로 적는다. 이미 고친 것을 중복 수정하지 않는다.
3. 증거 루트 `.omo/evidence/final-review-remediation/`를 사용한다. 각 작업은 `RP-XX/attempt-001/`에 기록한다. 재실행은 attempt 번호를 증가시켜 이전 실패를 보존한다.
4. Python/uv/Node/pnpm/OS/아키텍처와 sandbox backend 사용 가능 여부를 기록한다. 사용 가능한 버전을 임의 업그레이드하지 않는다.
5. 체크리스트에 담당자와 시작 SHA를 기록한다. 외부 key나 하드웨어가 필요한 작업은 필요 조건만 기록하고 비밀값을 요구 문서에 쓰지 않는다.

**완료:** 환경 파일, 작업 배정표, 기준 상태가 존재하고 경로가 실제 열린다. 제품 코드 변경 없음.

### RP-01 — 사용자·모델 테스트 코드의 격리 실행

**읽을 코드:** `api/routes/agent_ask.py`의 요청 모델/handler, `engine/unified_agent.py`의 `_run_code`, `_run_code_consistent`, `engine/sandbox.py`의 `run_sandboxed_argv`, `SandboxRunner.execute` 및 backend 구현. 기존 테스트 `test_agent_ask_api.py`, `test_unified_agent.py`, `test_sandbox.py`.

**구현 순서:**

1. 정상 단일 경로와 consistency 경로가 `test_solution.py`를 host pytest로 실행하는 지점을 각각 찾는다.
2. 기존 `run_sandboxed_argv(args, cwd, timeout, env, max_output_bytes)`를 공용 진입점으로 재사용한다. 현재 함수는 enabled=True/network=none으로 SandboxRunner를 구성한다. 그러나 기본 runner나 `sandboxed=True` 플래그만으로 실제 격리가 성립한다고 보지 않는다.
3. backend의 읽기 허용 범위를 확인한다. 프로젝트 밖 **쓰기뿐 아니라 사용자 비밀 파일 읽기**도 차단돼야 한다. 런타임 라이브러리 경로만 허용하고 임의 HOME 전체를 읽게 하지 않는다. 기존 backend가 불가능하면 이 실행 경로는 명시적 실패로 막고 설계 검토를 요청한다.
4. 전체 `os.environ` 상속을 없앤다. 필요한 실행 PATH/locale/전용 임시 HOME 등 검토된 최소값만 만든다. 가짜 비밀 환경변수가 자식에게 전달되지 않는지 검증한다.
5. 결과 success/return_code/stdout/stderr/timeout을 기존 AgentOutcome 의미에 맞게 연결한다. backend 없음·실행 거부·timeout을 passed=True 또는 정상 모델 답변으로 숨기지 않는다.
6. 단일/consistency 경로를 같은 실행 경계에 연결한다. backend 실패 시 host subprocess 재시도 금지. 사용자 코드가 실행되기 전에 실패해야 한다.
7. timeout 때 자식 프로세스 그룹까지 종료하고 출력 제한을 유지한다. 모델 응답·테스트 결과의 기존 정상 행동을 보존한다.

**필수 테스트:** 정상 작은 Python 함수 성공; pytest 실패 반영; 단일 및 consistency 모두 검사; backend 미설치/비활성화 시 실행 0회; 전용 외부 sentinel 읽기/쓰기 거부; 가짜 환경 secret 비노출; loopback 테스트 서버로 egress 거부; 장시간 자식 프로세스 종료; 출력 quota. 공격 테스트의 외부 파일도 임시 fixture다.

**회귀 명령:** `uv run --no-sync pytest -q tests/test_agent_ask_api.py tests/test_unified_agent.py tests/test_sandbox.py` 및 신규 `tests/test_fr01_agent_execution_isolation.py`.

**완료:** 실제 지원 sandbox에서 정상·차단 시나리오를 실행한 원문 + backend 없는 환경의 fail-closed 증거. mock-only 통과는 REVIEW 진입 불가. public API 응답 형식 변경이 필요하면 client schema와 소비자를 조정자가 확인한다.

### RP-02 — shell 경로 우회와 실행 fallback 차단

**읽을 코드:** `tools/tool_path.py`의 `iter_shell_escape_path_candidates`, `assert_shell_command_paths_in_root`; `permission_gate.py`; `terminal_tools.py`의 sandbox 및 `shell=True` fallback; RP-01에서 확정한 sandbox 계약.

1. permission의 allow 판정과 실제 실행의 root·env·cwd가 같은 request context에서 나온다는 것을 확인한다.
2. `$HOME` 차단 문자열 하나를 추가하는 패치를 최종 해결책으로 삼지 않는다. 프로그래밍 언어로 임의 파일을 여는 command도 있으므로 argv/토큰 검사만으로 전체 경계를 주장할 수 없다.
3. 모델·API가 지시한 shell 명령은 OS sandbox에서 프로젝트 write boundary와 최소 env를 적용한다. 제한을 보장할 수 없으면 명령을 거부하고 raw fallback을 사용하지 않는다.
4. shell 문법을 지원하는 기존 계약이 있다면 sandbox 안에서만 지원한다. structured argv로 변경하면 pipe/redirection 기존 동작 영향을 명시하고 소비자 테스트를 보완한다.
5. lexical path 검사는 빠른 오류 설명용으로 유지할 수 있다. 최종 실행 경계를 대체하지 않도록 호출 경로를 검증한다.
6. root 전환 중 명령이 다른 프로젝트에서 실행되지 않도록 시작 시의 request-bound root를 고정한다.

**테스트 표:** `$HOME`, `${HOME}`, 따옴표, `>file`/`> file`, `$(...)`, backtick 치환, symlink 경유, `../`, glob, absolute path, Python subprocess에서 외부 파일 열기. 모두 임시 외부 파일의 해시가 유지돼야 한다. 정상 root 내부 파일 쓰기·공백 경로는 성공해야 한다.

**신규 테스트:** `tests/test_fr02_shell_execution_boundary.py`. 기존 관련 테스트는 graph에서 permission/terminal/path 호출자를 검색해 검증 목록으로 확정한다. `allow=False`만 확인하지 말고 실제 실행 결과와 외부 파일 불변을 확인한다.

**완료:** RP-01 공용 격리 계약 회귀 통과, 원격/모델 실행 경로에서 sandbox 불가 시 host fallback 없음.

### RP-03 — AtomicTransactionEngine 경로와 rollback 정합성

**읽을 코드:** `engine/atomic_transaction_engine.py`의 `stage_file_patch`, `commit_transaction`; `tools/tool_path.py`의 `resolve_tool_path(raw_path, project_root)`; `tests/test_atomic_transaction_engine.py`.

1. transaction 시작 시 canonical root를 고정한다. request root와 다르면 호출자가 잘못된 root를 넘기지 않는지 확인한다.
2. stage 시 원본 읽기 **전** target을 검증한다. `../`, 외부 absolute path, 외부 symlink, 존재하지 않는 leaf의 부모 경유 이탈을 거부한다.
3. 전체 op의 경로·구문을 확인한 후에만 첫 쓰기를 시작한다. stage 이후 부모가 바뀌는 경우도 commit 직전에 확인한다.
4. resolve→write 사이 symlink 교체 경쟁은 재검사 한 번만으로 닫혔다고 주장하지 않는다. 지원 OS의 directory-handle/no-follow 방식 또는 격리 transaction 디렉터리로 실제 write boundary를 보장한다. 안전한 구현을 확정하기 어려우면 조정자 설계 검토로 올린다.
5. rollback metadata에 원래 존재 여부와 원본 내용을 분리 저장한다. 기존 0-byte 파일은 삭제하면 안 된다. 새 파일만 제거한다. 필요하다면 원본 mode도 보존한다.
6. N번째 쓰기에서 실패를 주입해 앞선 쓰기만 복원한다. unrelated 파일/작업자의 변경을 덮어쓰지 않는다. 동일 파일 외부 변경이 감지되면 충돌을 기록하고 무조건 overwrite하지 않는다.

**필수 테스트:** 내부 정상 2파일 성공; traversal/symlink stage 거부 전 외부 read 0회; commit 전 경로 교체 거부; N번째 write 실패 시 원본/빈 파일/새 파일 상태 복원; 다른 파일 불변. 새 테스트 `tests/test_fr03_transaction_containment.py`.

**명령:** `uv run --no-sync pytest -q tests/test_atomic_transaction_engine.py tests/test_fr03_transaction_containment.py`.

**완료:** 임시 외부 sentinel의 내용·존재 상태 불변, 실패 transaction의 부분 성공 잔재 없음, 필요한 제한사항이 반환 오류에 드러남.

### RP-04 — RSI rollback의 mutation 소유권 보장

**읽을 코드:** `engine/rsi_sandbox.py`의 `take_snapshot`, `rollback_to`, `safe_mutation` 및 실제 mutation callback 호출자; 기존 `worktree_manager.py`, `self_evolution_coordinator.py`, `tests/test_rsi_family.py`, `tests/test_evo01_mutation_fail_closed.py`.

1. mutation callback이 쓰는 실제 cwd/root를 끝까지 추적한다. worktree를 생성만 하고 callback이 본 작업 트리를 쓰면 실패다.
2. 기본 설계는 전용 worktree에서 mutation·검증을 수행하고 실패 시 그 worktree의 자기 변경만 폐기하는 방식이다. snapshot의 전체 tracked file 목록은 소유권 목록이 아니다.
3. 성공 결과를 원래 프로젝트에 적용해야 한다면 수정 대상 집합과 시작 preimage/hash를 기록하고 잠금 안에서 충돌을 검사한다. 바뀐 preimage에는 덮어쓰지 말고 충돌로 종료한다.
4. 전용 worktree 적용이 어렵다면 소유 경로·preimage·신규 여부를 가진 transaction 방식의 대안 설계를 조정자가 승인해야 한다. 전체 `git checkout ... -- .`, `reset --hard`, `clean -fd`로 대체하지 않는다.
5. setup 실패 시 mutation callback 실행 0회. 검증 예외·프로세스 종료·중복 복구 호출도 안전해야 한다. 임시 worktree 정리는 자신의 ID만 대상으로 한다.

**테스트 fixture:** 임시 repo에 committed A/B, 사용자 dirty B, 새 untracked C를 만든다. mutation은 A만 수정 후 실패하게 한다. A는 계약대로 복원, B/C는 바이트 단위 유지. 동시 작업자가 A를 변경하는 경우 충돌을 보고하고 그 변경을 보존. 성공 때 A만 반영. rollback 자체를 mock하지 않는다.

**명령:** `uv run --no-sync pytest -q tests/test_rsi_family.py tests/test_evo01_mutation_fail_closed.py tests/test_fr04_mutation_rollback_isolation.py` (마지막 파일 신규).

**완료:** 실제 임시 Git repo 시나리오 원문, isolation/collision/cleanup 결과, 호출자의 올바른 worktree 사용 증거. 단순 명령 문자열 검사만으로 DONE 불가.

### RP-05 — ConversationStore의 authoritative read와 CAS

**읽을 코드:** `conversation_store.py`의 `_ensure_loaded`, `_reload_from_disk`, `_cross_process_lock`, `get`, `get_revision`, `get_or_create`, `append`, `compact`, 그리고 그 외 persist 호출자. 기존 재현 스크립트는 `docs/qa/2026-09-10/reproduce_conversation_store_stale_cache.py`다.

1. 수정 전 재현 출력과 원본 store JSON을 임시 환경에서 기록한다. 기존 재현 스크립트는 결함 존재를 assert할 수 있으므로 수정 후 스크립트 exit=0을 목표로 삼지 않는다. 수정된 계약은 별도 회귀 테스트로 증명한다.
2. disk를 진실의 원천으로 삼는다. 각 public read/create/CAS에서 process-local cache가 최신인지 확정한다. 초기 구현은 thread lock → process lock → disk refresh 순서의 일관된 경로를 우선한다. 캐시 성능 최적화는 나중이다.
3. helper에서 public 메서드를 재호출해 lock을 이중 획득하거나 deadlock시키지 않는다. `_reload_from_disk`가 파일 부재/삭제/손상 때 오래된 객체를 되살리는지 확인한다.
4. get_or_create의 최신 revision 비교와 신규 persist는 같은 프로세스 간 critical section에서 수행한다. 동시 create가 다른 worker의 append를 덮어쓰면 안 된다.
5. caller에게 mutable cached 객체를 노출해 lock 밖에서 store가 변경되지 않는지 확인한다. 필요하면 기존 snapshot/copy 계약으로 고정하되 모든 caller의 반환형 사용을 확인한다.
6. append/compact의 refresh 및 CAS 보장을 보존한다. summarize 중 lock 보유 정책은 명시한다. lock을 풀었다 다시 쓰는 설계라면 저장 직전 revision을 반드시 재검증한다.

**필수 시나리오:** worker B가 rev1 캐시 → A append rev2 → B get/get_revision은 rev2; B expected1 create/compact는 conflict; 두 process가 동시에 expected0 create+append → 성공 개수와 최종 메시지 수 정확히 일치; append 대 compact 경쟁 → 하나의 CAS만 성공; 재시작 후 같은 상태; 파일 손상 시 명시적 오류/기존 계약 준수.

`time.sleep`으로 우연한 순서를 만들지 말고 multiprocess barrier/event와 join timeout을 쓴다. 테스트 parent가 강제 종료한 자식은 반드시 회수한다.

**명령:** `uv run --no-sync pytest -q tests/test_conversation_store_ctx01.py tests/test_conversation_api_ctx01.py tests/test_val02_conversation_multiprocess.py tests/test_fr05_conversation_authoritative_reads.py` (마지막 신규).

**완료:** 2 인스턴스뿐 아니라 2 process 재현, 실제 API worker 경유 read/CAS 증거, 성공 append 개수와 메시지 수 equality, cross-project 오염 없음.

### RP-06 — Chroma staging이 실패를 정확히 드러내도록 수정

**읽을 코드:** `scripts/val01_staging.py`의 `_record`, `_chroma_scenarios`, `run_staging`, `main`; VectorStore의 delete/search/stats 및 실제 metadata schema.

1. 삭제 target과 유지할 control source를 별도 생성한다. 삭제 전 둘 다 인덱싱됐음을 확인한다.
2. 삭제 후 target source의 실제 chunk 수가 0임을 확인하고, control source가 남아 있는지 확인한다. search 결과가 있다는 사실은 삭제 실패가 아니다.
3. source identity 필드명을 코드에서 확인해 assert한다. 특정 검색 top-k에 target이 없다는 것만으로 전량 삭제를 입증하지 않는다. backend filter/readback도 함께 사용한다.
4. 삭제를 일부러 no-op 처리한 회귀 테스트에서 scenario가 FAIL이어야 한다. false detail을 반환하고 `_record`가 성공 처리하는 구조를 없앤다. 명시적 assertion 또는 typed scenario 결과의 의미를 한 가지로 정한다.
5. citation/restart/reindex도 bool 지표만 출력하고 실패를 삼키는지 같은 범위에서 점검한다. 통계 키가 잘못돼 null이면 성공 근거로 쓰지 않는다.
6. required 실패·예외·미실행이 있으면 요약 FAIL 및 CLI nonzero. 모든 필수 시나리오를 실행하지 않은 빈 목록을 all([])=true로 승인하지 않는다.

**신규 테스트:** `tests/test_fr07_staging_verdicts.py`. 정상 target 삭제/다른 문서 검색 유지/no-op 삭제 검출/예외/빈 필수 시나리오/CLI 실패 exit code.

**완료:** 실제 persistent Chroma에서 delete/restart/reindex 성공과 의도적 실패 negative control을 각각 보존. 이전 false-green JSON은 역사 기록으로 유지한다.

### RP-07 — root/bundled config와 배포 패키지 동기화

1. `config.yaml`, `src/antigravity_k/config.yaml`, `pyproject.toml` package-data, `tests/test_model_registry.py:61`을 읽는다.
2. root의 agent 기본값이 의도된 값인지 실제 UnifiedAgent/CLI 소비자를 확인한다. 두 파일을 일치시킨다. 실패한 equality 테스트를 제거하거나 비교 범위를 줄이지 않는다.
3. 현재 빌드가 두 복사본을 요구하면 최소 동기화 변경을 먼저 한다. 공용 config 생성기를 새로 만드는 refactor는 이 작은 수정의 필수 요건이 아니다.
4. `uv run --no-sync pytest -q tests/test_model_registry.py`를 실행한다.
5. `uv build`로 새 wheel/sdist를 만들고 별도 임시 venv에 그 wheel을 설치한다. 저장소 cwd 밖에서 package resource를 읽어 agent 값이 포함됐는지 확인한다. import 경로가 작업 소스여서는 안 된다.
6. 새 환경의 `agk --help` 및 기존 clean-machine smoke를 수행한다. startup이 외부 provider를 필요로 하면 연결 없는 help/config 확인과 provider staging을 구분한다.

**완료:** equality 테스트, wheel 내 파일 확인, installed resource 경로·내용, CLI exit code. 단순 source test 통과만으로 패키징 완료 처리하지 않는다.

### RP-08 — 선택한 프로젝트 폴더의 파일이 실제 요청에 반영되는지 확인

**읽을 경로:** `api/project_binding.py`, `api/dependencies.py`, project registry/context API, `tools/tool_path.py`, `dashboard/src/api/client.ts`, `ChatPage.tsx`, `Editor/FileTree.tsx`; request-scoped root와 실행 context 연결은 graph로 확인한다.

1. 테스트 전용 root 아래 A/B 두 프로젝트를 만든다. 동일 파일명 `context_probe.txt`에 각각 서로 다른 무작위 marker와 짧은 함수/설정값을 넣는다. 사용자 질문에는 파일명만 넣고 **marker 정답은 넣지 않는다**.
2. 실제 브라우저 프로젝트 설정에서 A를 선택·저장한다. 새 request를 만들고 그 파일을 읽어 값을 답하게 한다. 화면 label, request project identity, 서버 canonical root, 도구 read 경로, provider 직전 직렬화 prompt를 한 request ID로 연결한다.
3. A marker가 실제 provider payload에 들어가고 B marker가 없는지 확인한다. 응답이 정답처럼 보여도 payload 증거가 없으면 충분하지 않다.
4. B로 전환해 새 요청을 반복한다. A→B→A, reload, 별도 탭, 동명 상대경로, 공백·한글 경로, 삭제된 root도 검사한다.
5. A 요청 진행 중 UI를 B로 전환하면 이미 시작된 A request는 A snapshot에 남고 새 요청만 B를 사용해야 한다. 서버 전역 active project 값에 기대어 진행 중 요청의 root를 바꾸면 안 된다.
6. 파일 읽기 실패·등록되지 않은 root는 UI에서 명시적으로 표시하고 요청을 잘못된 cwd로 fallback하지 않는다.
7. 실패하면 위 연결에서 **처음 값이 바뀌거나 사라지는 위치**를 수정한다. 여러 전역 변수를 동시에 덮어쓰는 임시 해결 금지.

**검증 단계:** 결정적 provider double로 payload 경로 회귀 → 실제 브라우저 동작 → RP-12에서 실제 local/cloud provider 반복. UI 수정 시 typecheck/test/build와 실제 화면 QA 필요.

**신규 제안:** `tests/test_fr_workspace_prompt_binding.py`, `dashboard/e2e/tests/project-request-binding.spec.ts`. 기존 graph/fixture와 중복되면 기존 파일에 추가해도 된다.

**완료:** marker 포함·배제 assert, A/B request identity와 prompt 증거, 원본 네트워크/action log와 screenshots. 프로젝트 전환 endpoint 200만으로 DONE 불가.

### RP-09 — 수동·자동 압축과 최종 prompt 예산 검증

**읽을 경로:** `conversation_store.py`, `orchestrator/stream.py`, `tool_loop.py`, `context_budget_enforcer.py`, 압축 API, ChatPage/client/store, `taskExecutionProjection.ts`. 관련 기존 테스트는 아래 명령에 있다.

1. 테스트용 긴 대화를 만든다. 초기 사용자 요구(변경 금지 파일, 핵심 조건), 최근 사용자 지시, tool-call/result 쌍, citation source를 포함한다. 비밀 없는 합성 데이터만 사용한다.
2. 실제 UI의 수동 압축 control을 찾고 클릭한다. 없다면 제품 계약/기존 docs와 대조해 필요한 UX를 구현한다. 브라우저 page.fetch로 API만 호출한 것은 수동 UI 성공 증거가 아니다.
3. 압축 전후 revision, retain message IDs, summary, token count, emitted events를 저장한다. 요약에 초기 핵심 요구가 남고 최신 사용자 지시가 유지되는지 검증한다.
4. 설정된 자동 압축 조건을 실제 요청 흐름으로 발생시킨다. threshold는 테스트 설정으로 줄일 수 있지만 production 임계값을 통과용으로 바꾸지 않는다. 조건과 실측을 로그에 남긴다.
5. 최종 provider 호출 **바로 직전** 모든 system/history/tool/retrieval 구성요소가 직렬화된 payload를 측정한다. 모델 입력 한도와 출력 reserve의 기존 계약 이내인지 확인한다. tokenizer가 estimate면 추정치로 표시하고 실제 provider 거부도 별도 검사한다.
6. 정상 압축, 변경 없음 skipped, 압축 실패, 잔여 over-budget, 동시 append, stale revision, 재시작을 각각 실행한다. skipped를 실패나 계속 running으로 표시하지 않는다. 실패 후 무한 재압축/무한 재시도 금지.
7. tool-call/result pairing과 citation provenance를 보존한다. summary 저장 후 다른 worker가 같은 revision/history를 보는지 RP-05 회귀를 함께 실행한다.
8. 실패한 invariant가 있을 때만 필요한 함수/이벤트 연결을 수정한다. 복잡한 budget 함수를 무조건 재작성하지 않는다.

**명령:** `uv run --no-sync pytest -q tests/test_final_prompt_budget.py tests/test_ctx02_reject_fixes.py tests/test_ctx03_compress_observability.py tests/test_conversation_store_ctx01.py tests/test_conversation_api_ctx01.py tests/test_val02_conversation_multiprocess.py`.

**신규 제안:** `dashboard/e2e/tests/context-compaction-flow.spec.ts`, 필요 시 `tests/test_fr_context_end_to_end.py`.

**완료:** manual UI click + automatic trigger 각각의 실제 흐름, 유지할 정보/paired tool/citation 불변, payload budget, 실패 UI, cross-worker 읽기 증거. 8→4 같은 메시지 개수 감소만으로 성공 처리하지 않는다.

### RP-10 — 완료 상태·지원 범위·승인 등록부 정리

**대상:** docs 10/11/12/13, README, `.omo/plans/ssak-ai-commercial-ga-100-checklist.md`, `docs/ga/GA_SUPPORT_MATRIX.md`, `GA_CLAIMS_AND_REVIEW_REGISTER.md`, `GA_DATA_PRIVACY_OPERATIONS.md`, 기존 task metadata.

1. 각 DONE row를 결과 SHA/원문 테스트/수동 QA/독립 리뷰로 대조한 증거 인덱스를 만든다. `review pending`, SHA 공란, 누락 review는 열린 상태로 적는다.
2. 기존 변경 이력은 지우지 않는다. 현재 상태와 과거 시점을 구분하고, 이번 remediation 상태를 별도 표로 연결한다.
3. 지원 platform/provider를 실제 출시 범위에서 확정한다. 구현만 있는 항목은 Experimental 유지. Windows/CUDA/native desktop 등 원래 범위 밖 지원을 임의 약속하지 않는다.
4. 법률·개인정보·모델/공급자 약관·라이선스·SLA 승인 자료를 담당자에게 연결한다. 에이전트가 법무 담당자 이름이나 승인 내용을 만들어 쓰지 않는다. 외부 판단이 필요하면 BLOCKED_EXTERNAL이며 기술 수정은 계속한다.
5. 점수표의 baseline/current/target을 분리하고 현재 점수는 수용 기준 증거로만 갱신한다. 과거 53을 지금 점수로 복사하거나 TODO를 체크해 100을 만들지 않는다.
6. 이 단계에서는 “검증 준비/승인 대기”로 정합화한다. 최종 candidate SHA와 GO 승인은 RP-14에서 확정한다. 후보 고정 이전에 가능한 review를 끝내고 후보 의존 승인만 남긴다.

**완료:** 모든 FR/task/claim이 증거 또는 명시적 미완료 사유에 연결돼 모순이 없다. 승인 자체가 없는 항목은 최종 게이트 blocker로 남는다. 문서 정리 DONE과 법적/운영 승인 DONE을 혼동하지 않는다.

### RP-11 — gate와 증거 수집을 먼저 검증

1. `scripts/commercial_ga_gates.json`의 모든 required gate를 인벤토리로 만든다. 설치·코드 검사·타입·전체 tests·dashboard·package/docker·SBOM/audit·master/API E2E·accessibility·clean-machine 항목을 빠뜨리지 않는다.
2. 기존 runner를 graph로 찾아 사용한다. 새 runner가 필요하면 명령 배열/cwd/timeout/stdout/stderr/exit code/시작·종료/SHA를 기록하는 최소 구현으로 제한한다.
3. 실행 전에 필수 scenario 목록과 threshold를 고정한다. 미실행/빈 목록/짧은 duration을 FAIL 또는 INCOMPLETE로 판정하는 검증기를 만든다. 임계값 파일 hash도 증거에 넣는다.
4. staged JSON에 source SHA, tree 상태, 환경, actual start/end, duration, scenario ID, 기대/실측/판정을 넣는다. 외부 wrapper를 쓰면 JSON과 wrapper의 checksum 연결을 보존한다.
5. VAL-01 cloud adapter가 없으면 기존 provider abstraction으로 명시적 cloud 시나리오를 추가한다. tool registry 목록 조회를 실제 tool execution 성공으로 계산하지 않는다. 키 없음은 NOT_RUN.
6. VAL-02 soak가 DB 루프만 수행하는지 확인한다. 작업 생성→실행→종료, conversation 작업, cleanup/worker lifecycle, FD/RSS/DB lock/orphan을 요구 부하에 포함시킨다. kill -9 후 `prepare_resume=True`만이 아니라 재시작 후 task 최종 완료·중복 부작용 없음까지 확인한다.
7. 프로세스·worktree count는 구조적으로 수집한다. 숫자 0을 하드코딩하거나 빈 stdout을 0으로 간주하지 않는다. 종료 실패/샘플 누락도 실패로 표기한다.
8. 환경의 pip-audit만 실행하고 출시 dependency 검증이라 하지 않는다. 실제 shipping wheel/lock과 설치 환경이 같은지 확인하고 감사 대상 목록/hash를 기록한다.
9. 수집기 자체에 잘못된 SHA, artifact 없음, false metric, missing required scenario, 60초 soak negative fixture를 넣어 거부를 확인한다.

**완료:** 실 실행 전 dry run이 정상/실패/미실행을 구분한다. gate 도구·테스트·설정 변경은 모두 후보 고정 전에 통합한다. 외부 서비스 조회가 필요한 업데이트 정보는 담당 작업자가 당시 공식 자료로 확인한다.

### RP-12 — 후보 SHA 고정, 실 provider 및 8시간 검증

1. RP-01~11 변경과 선택한 RP-15를 통합하고 focused 회귀를 통과시킨다. clean release checkout에서 full SHA를 고정한다. 작업자 로컬 dirty repo를 정리해서 억지로 clean으로 만들지 말고 별도 checkout을 쓴다.
2. 전체 gate를 해당 SHA에서 실행한다. evidence/artifacts는 checkout 밖 또는 명시적 출력 디렉터리에 저장한다. generated product asset/config가 빌드로 바뀌면 원인을 확인하고 필요 변경을 통합한 새 SHA에서 다시 고정한다.
3. 실제 local provider와 최소 하나의 실제 cloud provider를 사용한다. RP-08/09 marker/압축, streaming, 실제 도구 호출과 결과 반영, cancel, 오류를 실행한다. credential은 환경/secret store에서 공급하고 로그에는 제외한다.
4. Chroma persistence/restart/reindex/delete/citation을 실 backend에서 실행한다. 지원 범위의 MLX 또는 CUDA 실 학습/checkpoint/resume/fuse도 기존 VAL-01 요구에 따라 수행한다. 지원 밖 하드웨어를 통과 처리하지 않는다.
5. 60초 rehearsal은 배선 확인에만 쓴다. 실제 **28,800초 이상** 연속 부하 결과를 따로 생성한다. 재부팅/중단/프로세스 종료 후 짧은 run 합산으로 대체하지 않는다.
6. 승인된 thresholds로 p95/p99/error/FD/RSS trend/orphan/DB 접근·lock 결과를 판정한다. 샘플 수·시간 범위·부하량을 함께 기록한다. 메모리 시작/끝 두 점만 보고 지속 growth 없다고 결론내리지 않는다.
7. 장기 실행은 관리 가능한 job으로 시작해 run ID/PID/output 경로/재연결 방법을 기록한다. 작업자가 종료하거나 컨텍스트를 잃어도 후속 에이전트가 상태를 확인할 수 있게 한다. 완료 전에 PASS 선언 금지.

현재 확인된 실행 entrypoint(수정 후 --help와 대조):

```sh
uv run --no-sync python scripts/val01_staging.py --help
uv run --no-sync python scripts/val02_staging.py --help
```

VAL-02의 검토 당시 옵션은 `--scenarios`, `--soak-seconds`, `--workdir`, `--output`이다. RP-11 완료 후 격리 환경에서 아래 형식으로 실행한다. `rp_run_dir`은 작업자가 만든 전용 디렉터리이며 빈 값이면 실행하지 않는다.

```sh
uv run --no-sync python scripts/val02_staging.py --scenarios SC-1,SC-2,SC-3,SC-4,SC-5,SC-6 --soak-seconds 28800 --workdir "$rp_run_dir/work" --output "$rp_run_dir/val02.json"
```

**완료:** same-SHA full gate, 실제 provider/hardware, 8시간 연속 측정, 필수 시나리오 전부 PASS. 키·장비·시간 부족은 BLOCKED_EXTERNAL/INCOMPLETE이며 DONE 금지.

### RP-13 — 배포 산출물과 실제 복구 검증

1. RP-12와 같은 SHA에서 wheel/sdist/container를 생성한다. 파일명·버전·source SHA·SHA256·size·retrievable path를 기록한다.
2. wheel/sdist가 저장소 밖 clean 환경에서 설치·기동·config/assets 포함·기본 API/auth를 통과하는지 확인한다. source checkout의 PYTHONPATH를 사용하면 설치 검증으로 인정하지 않는다.
3. container tag만 기록하지 말고 image digest/ID와 build 정보, 실행 health/auth/persistence를 연결한다.
4. SBOM/notices/provenance/benchmark/staging/raw gate logs를 manifest에 포함한다. hash만 있고 artifact가 없으면 실패다. evidence를 후보 뒤에 커밋하는 것은 가능하지만 artifact의 source SHA를 바꿔 쓰면 안 된다.
5. backup→corruption→restore→실 read/write, upgrade/migration, previous artifact로 rollback→실 서비스 health/auth/data 확인을 수행한다. 이전 Git checkout 성공은 서비스 rollback 증거가 아니다.
6. 두 번째 검증자가 manifest의 파일 존재·hash·SHA를 독립 확인한다. artifact 하나 제거/변조한 임시 복사본에서 검증기가 실패해야 한다.

**완료:** 새 설치/업그레이드/복구/rollback 실행 증거와 retrievable manifest. 사용자 실제 데이터를 복구 리허설에 사용하지 않는다.

### RP-14 — 최종 독립 검토와 출시 결정

1. 코드 품질, 보안, 수동 QA/런타임, 목표/출시 기준, 문서/운영 정합성 5개 영역을 독립 검토한다. 전부 full SHA와 증거 경로를 명시한다.
2. FR-01~10, 폴더/압축 E2E와 기존 GA 계획 필수 항목이 각각 어떤 테스트·수동 결과·리뷰로 닫혔는지 대조한다.
3. 필요한 지원/법무/개인정보/운영 승인의 범위·책임자·날짜·증거·candidate SHA 적용성을 확인한다. Pending을 승인으로 추론하지 않는다.
4. FAIL 또는 INCONCLUSIVE가 하나라도 있으면 REQUEST_CHANGES/INCOMPLETE다. 구현자가 자신의 코드를 APPROVE해 종료하지 않는다.
5. 모든 검토가 PASS인 경우에만 checklist 완료·현재 scorecard·support/claims·GO를 동기화한다. 모델명이나 작업자의 자기평가가 아닌 충족된 수용 기준으로 판단한다.
6. 코드/테스트/gate 설정이 바뀌면 새 candidate로 재고정한다. 순수 증거 보고 커밋은 승인 대상 artifact/source SHA와 분리 기록해 무한 재검증 루프를 피한다. 최신 repository HEAD 전체를 승인했다고 쓰려면 그 HEAD의 적용 gate coverage가 있어야 한다.

**완료:** 같은 candidate를 가리키는 5개 PASS, 검증 가능한 release manifest, 필요한 외부 승인, 모든 RP-00~13 완료와 FR 재검증 완료 후 RP-14 자체를 종료한다. 최종 보고서에 잔여 제한과 지원 범위를 명시한다.

### RP-15 — 선택적 유지보수 작업

최종 품질 보고서의 대형 budget 함수·구현 상수 고정 테스트·append equality 지적을 다룬다. 출시 결함 수정과 무관한 전면 refactor는 기본 범위 밖이다.

- append count `>=`를 실제 계약의 `==`로 강화하는 작업은 RP-05에 포함해도 된다.
- 상수 0.05/15.0을 그대로 assert하는 테스트는 실 event/config 소비 계약을 검증하도록 보완한다. 보호 기능을 없애기 위해 삭제하지 않는다.
- budget 함수 분해는 기존 behavior matrix를 먼저 확보하고 작은 단위로 진행한다. token accounting/ordering/overflow policy를 바꾸지 않는다.
- 조정자가 실행 여부를 `EXECUTE` 또는 `DEFERRED_NONBLOCKING`과 근거로 기록한다. 미실행을 DONE으로 표기하지 않는다. 실행한다면 후보 고정 전 완료와 RP-09 재검증이 필요하다.

## 6. 공통 증거 형식과 상태 관리

각 attempt에 다음 파일을 남긴다. 파일이 없으면 내용이 있었던 것처럼 링크하지 않는다.

| 파일 | 필수 내용 |
|---|---|
| metadata.json | task ID, 담당자, 시작/검증 SHA, dirty 여부, 환경, 상태, 변경 파일, 선행 결과, 시작/종료 |
| implementation.md | 기존 재현, 원인, 수정한 계약, 영향 범위, 대안/제한, 테스트 목록 |
| commands.jsonl | 실제 argv 배열, cwd, UTC start/end, exit code, stdout/stderr 경로 |
| logs/ | 원문 stdout/stderr. 요약은 원문과 별도 파일 |
| manual-qa.md | 준비물, 클릭/명령 순서, expected/observed, request/scenario ID, screenshot/trace 경로 |
| review.md | 독립 검토자, full SHA, PASS/FAIL/INCONCLUSIVE, 재현 항목, 남은 문제 |
| handoff.md | 완료/미완료, 재개할 정확한 단계, 실행 job 정보, 수정 금지 파일, 외부 의존성 |

metadata 최소 예시는 **양식**이며 실제 완료 증거로 사용하지 않는다:

```json
{
  "schema_version": 1,
  "task_id": "RP-01",
  "attempt": 1,
  "status": "TODO",
  "owner": null,
  "base_sha": null,
  "tested_sha": null,
  "tree_clean_before_run": null,
  "required_scenarios": [],
  "scenario_results": [],
  "commands_log": "commands.jsonl",
  "reviewer": null,
  "review_verdict": null,
  "blocked_reason": null
}
```

scenario마다 `id`, `required`, `expected`, `observed`, `verdict`, `artifact_paths`를 넣는다. null/빈 목록/TODO는 PASS가 아니다. 현재 source와 검증 source가 다르면 coverage를 명시한다. 명령 출력이 누락됐으면 `UNAVAILABLE`라고 쓰고 필요 검증을 재실행한다. 요약문을 원문 log로 가장하지 않는다.

상태: `TODO → IN_PROGRESS → IMPLEMENTED → REVIEW → DONE`. 실패는 `REWORK`, 외부 의존은 `BLOCKED_EXTERNAL`, 수용 기준 미측정은 `INCOMPLETE`. `IMPLEMENTED`는 테스트와 리뷰가 끝났다는 의미가 아니다. 최종 체크리스트는 조정자 한 명만 편집하고 각 작업자는 자신의 evidence만 수정한다.

## 7. 검증 명령 실행 원칙

- 기본 cwd는 repo root, frontend 명령만 dashboard다. `--no-sync` 실패가 dependency 부족 때문이면 기록하고 격리 환경에서 lock대로 준비한다. 사용자 환경의 lock을 자동 갱신하지 않는다.
- 새 테스트 파일은 만든 뒤 명령에 추가한다. 이 문서의 제안 파일을 존재하는 것으로 가정해 가짜 결과를 쓰지 않는다.
- Python 변경은 해당 focused pytest와 프로젝트의 Ruff/format/type 검사를 실행한다. UI 변경은 typecheck/test/lint/build 및 실제 브라우저 시나리오를 실행한다.
- 최종 full gate는 `scripts/commercial_ga_gates.json`의 required 항목 전부다. `not slow and not benchmark` 등의 축소 실행은 smoke로 기록하고 full gate로 부르지 않는다.
- exit code를 보존한다. `tee`가 pytest 실패를 가리지 않도록 runner가 원래 프로세스 exit code를 저장해야 한다.
- 실 provider prompt 기록은 합성 파일/대화만 사용한다. Authorization/Cookie/실 키/사용자 문서를 HAR나 screenshot에 남기지 않는다.

## 8. 다음 에이전트에게 붙여 넣을 작업 지시문

> 저장소의 docs/14_FINAL_REVIEW_REMEDIATION_PLAN.md와 docs/15_FINAL_REVIEW_REMEDIATION_CHECKLIST.md를 먼저 읽으세요. 당신에게 배정된 작업은 RP-XX 하나입니다. 해당 카드의 목표·소유 파일·선행 조건·검증·완료 기준을 따르세요. 다른 작업자와 같은 저장소를 공유하므로 그들의 수정과 vault_data를 되돌리지 마세요. 먼저 현재 HEAD/dirty 상태와 해당 결함을 확인하고, 증거를 작업별 attempt 디렉터리에 기록하세요. 공용 파일 수정이 필요하면 조정자에게 먼저 조율하세요. 테스트·원문 로그·수동 QA가 끝나도 스스로 DONE/APPROVE로 바꾸지 말고 REVIEW와 검증 SHA를 보고하세요. 미실행은 성공이 아닙니다. 막히면 정확한 원인·필요 자원·재개 단계를 handoff.md에 남기세요.

조정자는 RP-XX를 실제 ID로 치환하고 담당 branch/worktree, 소유 파일, 선행 task의 완료 증거를 덧붙여 전달한다. 이 문서 전체를 한 번에 구현하라고 작은 모델에 맡기지 않는다.


## 9. 파일 위치 빠른 참조

아래는 검토 시 실제 존재한 파일이다. 새 테스트 제안과 구분한다. 이 표는 탐색을 돕는 것이며 코드 수정 전 심볼과 호출자를 다시 읽는다.

| 목적 | 파일 |
|---|---|
| UnifiedAgent HTTP entry | `src/antigravity_k/api/routes/agent_ask.py` |
| 단일/consistency 코드 실행 | `src/antigravity_k/engine/unified_agent.py` |
| 실행 sandbox | `src/antigravity_k/engine/sandbox.py` |
| 경로 해석 | `src/antigravity_k/tools/tool_path.py` |
| 권한/터미널 실행 | `src/antigravity_k/tools/permission_gate.py`, `src/antigravity_k/tools/terminal_tools.py` |
| 파일 transaction | `src/antigravity_k/engine/atomic_transaction_engine.py` |
| RSI rollback | `src/antigravity_k/engine/rsi_sandbox.py` |
| 대화 저장소 | `src/antigravity_k/engine/conversation_store.py` |
| 요청 project binding | `src/antigravity_k/api/project_binding.py`, `src/antigravity_k/api/dependencies.py` |
| stream/도구 루프 | `src/antigravity_k/engine/orchestrator/stream.py`, `src/antigravity_k/engine/tool_loop.py` |
| 최종 budget | `src/antigravity_k/engine/context_budget_enforcer.py` |
| 채팅/파일 UI | `dashboard/src/components/Chat/ChatPage.tsx`, `dashboard/src/components/Editor/FileTree.tsx` |
| API client | `dashboard/src/api/client.ts` |
| staging | `scripts/val01_staging.py`, `scripts/val02_staging.py` |
| 출시 gate | `scripts/commercial_ga_gates.json` |

## 10. 설계 결정이 필요한 경우의 중단 지점

하위 모델이 불확실한 보안 설계를 임의로 선택하지 않도록 다음 경우에는 해당 변경을 IMPLEMENTED로 보고하지 말고 조정자 검토를 요청한다. 독립된 테스트·문서 준비는 계속할 수 있다.

| 조건 | 제출할 자료 | 임시 안전 동작 |
|---|---|---|
| SandboxRunner가 host HOME 읽기를 허용하거나 backend별 보장이 다름 | backend profile/허용 경로/임시 sentinel 실행 결과 | 해당 비신뢰 코드 실행 fail-closed |
| transaction의 symlink race를 재검사만으로 해결하려는 상황 | stage→write 경쟁 재현, 지원 OS 대안 비교 | 안전 경로 확정 전 transaction 거부 |
| mutation callback이 기존 project root에 결합됨 | 호출자 목록, root 전달 변경 범위, worktree 적용안 | setup 검증 실패 시 mutation 0회 |
| 대화 read에 flock 추가 후 deadlock/지연 발생 | lock 획득 순서, barrier 재현, profile 측정 | CAS/최신 읽기 보장을 빼서 해결하지 않음 |
| API/UI 계약을 바꿔야 함 | before/after request/response와 모든 소비자 영향 | 기존 실패를 숨기는 성공 응답 금지 |
| 외부 법무/privacy 승인 없음 | 필요한 scope/담당 역할/기존 근거 인덱스 | 해당 claim과 최종 GO를 차단 |

조정자의 설계 판정은 별도 decision.md에 근거·선택·범위·검증을 남긴다. 사용자의 범위나 지원 약속을 바꾸는 선택은 조정자 단독으로 승인하지 않는다.
