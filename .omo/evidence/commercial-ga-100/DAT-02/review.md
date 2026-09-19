# DAT-02 독립 리뷰 — r1 APPROVE

- **Reviewer:** dat_02_verify (구현자 dat_02_vault와 상이한 세션 — Freebuff 세션, 2026-09-06)
- **검증 대상:** `codex/dat-02-vault-isolation` @ `5766a4d` (+ 리뷰 수정 커밋)
- **Verdict:** **APPROVE** — 발견 결함 2건 모두 당일 수정·재검증 완료

## 검증 방법

1. plan §DAT-02 수용기준 4건 대조 (아래 체크)
2. 구현자 증거 재현: `tests/test_vault_task_isolation.py` 10건 + `test_task_runner_outcome.py` 등 47건 재실행 → 통과 확인
3. **베이스 대조 회귀 분석**: base `5688332`에서 동일 테스트 파일 세트 실행 → 실패 21건(WS lane fixture 문제, `test_agent_runtime`/`test_runtime_benchmark_binding`/`test_api_server` 등)이 base와 완전 동일함을 diff로 확인 → DAT-02 신규 회귀 0건
4. 품질 게이트: ruff/mypy 재실행 → clean

## 발견 결함 및 조치

| # | 결함 | 심각도 | 조치 |
|---|---|---|---|
| F1 | `task_runner.py`의 신규 `subprocess.run`(worktree merge-back git 파이프라인)이 sandbox-coverage ALLOWLIST 미등록 → `test_all_process_execution_paths_are_accounted_for` 신규 실패 | 중 | `INTERNAL_FIXED` 카테고리로 등록(고정 argv git 파이프라인, 모델 입력 없음) — 해당 테스트 통과 복구 |
| F2 | 수용기준 4 "crash 뒤 orphan worktree 복구/정리 runbook과 rehearsal" 미충족 — runbook/리허설 부재 | 중 | `docs/runbooks/worktree_orphan_recovery.md` 신설 + `WorktreeManager.sweep_orphan_worktrees()`(dry-run 기본, dirty/미판정 보존) + `tests/test_worktree_orphan_sweep.py` 리허설 10건 — 실 git repo에서 end-to-end 검증 |

## 수용기준 체크 (plan §DAT-02)

- [x] task A 실패/취소 뒤 task B의 committed·uncommitted·untracked 보존 — `test_preserves_changes_outside_scope` 등 10건
- [x] task A가 소유한 변경만 제거 — scoped `restore_snapshot`(git checkout/unlink, reset --hard/clean -fd 금지)
- [x] merge conflict는 원본 보존 명시 상태 — `merge-tree --write-tree` 사전 탐지 + 원본 보존 (`manual-qa.md` 시나리오)
- [x] crash 뒤 orphan worktree 복구/정리 runbook과 rehearsal — F2로 충족 (runbook + 리허설 테스트)

## 최종 검증 수치

- 신규/수정 스위트: 59 passed (isolation 10 + outcome + worktree_manager + orphan_sweep 10 + sandbox_coverage)
- 전체 스위트: 5466 passed / 21 failed — 21건은 base `5688332`와 **완전 동일** (WS lane 소유, DAT-02 무관)
- ruff clean, mypy clean (`worktree_manager.py`, `task_runner.py`, `vault.py`)
