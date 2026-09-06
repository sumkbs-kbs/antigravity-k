# Runbook — Worktree 고아 복구 (Orphan Worktree Recovery)

**Task:** DAT-02 (vault task 격리와 안전한 rollback) · **발동 조건:** task runner 크래시/강제 종료 뒤 `.ag_worktrees/`에 작업 트리가 남은 경우
**위험도:** 중 — 데이터 손실 방지가 최우선. **모든 단계에서 "판단 불가 = 보존"이 원칙이다.**

## 1. 증상

- task가 크래시/kill로 종료된 뒤 `.ag_worktrees/<task-branch>` 디렉터리가 남아 있다
- `git worktree list`에 더 이상 실행 중이 아닌 task의 worktree가 등록되어 있다
- task API가 "worktree in use"를 반복 보고하지만 해당 task는 실제로 죽어 있다

## 2. 진단

```bash
# 1) 등록된 worktree 목록 (path / head / branch)
git worktree list --porcelain

# 2) Python으로 구조화 조회
uv run python -c "
from antigravity_k.engine.worktree_manager import WorktreeManager
for e in WorktreeManager('.').list_worktrees():
    print(e.get('path'), e.get('branch', '(detached)'), e.get('head'))
"

# 3) 각 worktree에 미커밋 변경이 있는지 확인 (삭제 판단의 핵심)
git -C .ag_worktrees/<task-branch> status --porcelain
```

판정 기준:

| 상태 | 판정 |
|---|---|
| `status --porcelain` 비어 있음 + mtime 오래됨(기본 7일) | 정리 대상 |
| `status --porcelain` 비어 있음 + mtime 최신 | 보존 (활성 가능성) |
| 변경/untracked 존재 | **보존** — task B의 데이터 (BR-01 계약) |
| `git status` 자체가 실패 | **보존** (판단 불가 = 보존) |

## 3. 복구 (안전 자동 정리)

```python
from antigravity_k.engine.worktree_manager import WorktreeManager

m = WorktreeManager(".")
# 3-1) 드라이런: 지워질 대상을 먼저 확인 (아무것도 삭제하지 않음)
targets = m.sweep_orphan_worktrees(older_than_days=7, dry_run=True)
print(targets)

# 3-2) 목록이 기대와 일치할 때만 실제 제거
removed = m.sweep_orphan_worktrees(older_than_days=7, dry_run=False)
print(removed)
```

`sweep_orphan_worktrees`는 worktrees_dir 하위 + clean + 오래된 mtime만 대상으로 하며,
dirty/미판정 worktree와 베이스 repo는 절대 건드리지 않는다.

## 4. 정리 (수동 폴백 — 자동 sweep가 비어 있을 때)

변경이 있는 worktree는 자동 대상이 아니다. 값어치를 수동으로 판단한다:

```bash
# 4-1) 미커밋 변경을 패치로 구출
git -C .ag_worktrees/<task-branch> diff    > /tmp/rescue-<task>.patch
git -C .ag_worktrees/<task-branch> status --porcelain

# 4-2) 커밋이 있다면 브랜치를 보존하고 worktree만 제거
git worktree remove .ag_worktrees/<task-branch>   # 브랜치/커밋은 남는다

# 4-3) 정말 폐기가 확인된 경우에만 강제 제거
git worktree remove --force .ag_worktrees/<task-branch>

# 4-4) 등록 정보만 남은 유령 정리 (디렉터리가 이미 없을 때)
git worktree prune
```

## 5. 리허설 (Rehearsal)

```bash
uv run --no-sync pytest tests/test_worktree_orphan_sweep.py -q
```

`TestSweepOrphanWorktrees::test_rehearsal_end_to_end`가 실제 git 저장소에서
크래시 시나리오(오래된 clean + 최신 + dirty worktree 혼재)를 재현하고
"오래되고 clean한 것만 제거, 나머지 보존"을 검증한다. 배포 전/분기마다 실행한다.
