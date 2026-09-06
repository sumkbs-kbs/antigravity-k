# DAT-02 수동 QA — 실제 사용자/운영 surface

## QA 1. 실제 runner + 실제 git vault에서 BR-01 재현이 사라졌는지

절차:
1. 임시 git 저장소(vault) 생성, 초기 커밋
2. `VaultEngine`으로 pre-task 스냅샷 생성 (`create_snapshot("Pre-task checkpoint…")`)
3. task B 역할의 동시 변경 3종 작성 (committed / uncommitted / untracked)
4. `_run_failing_task`로 task A를 실행해 실패 → 스코프 롤백 유도
5. task B의 3종 변경이 모두 그대로인지 확인

결과: PASS
- `tests/test_vault_task_isolation.py::TestTaskRollbackPreservesConcurrentChanges` (green)
- 구현 전 동일 시나리오는 `/tmp/br01_red_demo.py`에서 3/3 파괴 (red.txt 참조)

## QA 2. worktree task의 도구 경로 바인딩

절차:
1. 임시 git 저장소에서 `BackgroundTaskRunner` + `WorktreeManager(base_repo_path=repo)`
2. `submit_task(use_worktree=True)` 실행 → worktree 생성 확인
3. 런타임 캡처(`enable_runtime_capture`)로 RequestExecutionContext의
   `canonical_project_root`가 worktree realpath로 바인딩됐는지 확인

결과: PASS (`TestTaskScopedToolBinding::test_task_run_binds_tool_paths_to_worktree`)
- server cwd와 무관하게 task 전용 worktree가 도구 실행 root가 됨
- task 종료 후 ambient binding 복원 (`_reset_worktree_context`)

## QA 3. merge-back 수동 시나리오 (충돌/비충돌)

절차 (충돌):
1. base에 `shared.txt=base-version` 커밋
2. worktree 브랜치에서 `shared.txt=task-version` 커밋
3. base에서 `shared.txt=operator-version` 커밋 (충돌 유발)
4. `merge_worktree_changes()` 호출

결과: PASS — `merged=False`, `shared.txt`는 operator-version 유지 (원본 보존)
- `git merge-tree --write-tree` 사전 탐지가 충돌을 실패로 처리
- 무결성 mutation: 충돌 가드 제거 + 무조건 성공 반환 변이 → 시험 FAILED로 포착 확인

절차 (비충돌):
1. worktree에서 신규 파일 커밋 → merge-back
결과: PASS — base에 파일 생성, merge commit message에 task 브랜치명 포함

절차 (실패 task):
1. `merge_worktree_changes(..., merge_on_failure=False)` (기본값)
결과: PASS — base HEAD 불변, worktree 변경은 merge-back 없이 폐기

## QA 4. scoped restore 계약 (vault API level)

- 소유 untracked 생성 → 스코프 롤백 후 파일 제거: PASS
- 소유 tracked 수정/삭제 → 스코프 롤백 후 스냅샷 상태 복원: PASS
- 스코프 밖 변경 → 보존: PASS
- `../` escape scope → ValueError: PASS
- 스코프 없는 전체 restore → 위험 경로 가드 유지 (legacy 연산자 경로): PASS

## 남은 위험

- vault_writes 추적은 현재 runner의 명시적 기록 지점만 커버한다. tool 실행이
  임의 경로를 쓰는 경우 WS-02의 audit event를 후속 페이즈에서 연결해 완전화할 수 있다.
- `merge_worktree_changes`는 현재 task 러너 성공 경로에서 자동 호출되지 않고
  API/운영자가 호출하는 계약으로 두었다 (worktree task 성공 시 자동 merge는
  승인 게이트 논의 후 연결 권장 — plan §3.4 변경 소유권 원칙).
