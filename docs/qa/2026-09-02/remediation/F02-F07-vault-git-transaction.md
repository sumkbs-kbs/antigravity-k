---
title: F02/F07 Vault Git 트랜잭션 수정 진행 기록
tags: [qa, vault, git, remediation]
date: 2026-09-02
baseline_commit: 6d0a24d4e6a0686693ce29a4d13a69443ae5149b
status: fixed_pending_final_handoff
---

# F02/F07 진행 기록

다음 우선순위인 Vault 무관 staged 파일 커밋(F02)과 Git 실패 후 상태 계약(F07)을 함께 처리했다. 모든 재현은 임시 Vault 저장소에서만 수행했으며 루트 저장소의 index, hook, staged 파일을 변경하지 않았다.

## 상태

1. 완료: 무관 staged 파일이 노트 커밋에 포함되는 결함을 RED 테스트로 재현.
2. 완료: 대상 노트만 커밋하고 기존 staged/unstaged 상태를 보존하는 트랜잭션 구현.
3. 완료: no-op, hook 실패, 기존 노트 staged+unstaged 혼합, 실제 API 저장, 4-process 동시 저장 회귀 추가.
4. 완료: Vault/API 집중 31건, 전체 비벤치마크 4,836건, F01 wire 28건, 벤치마크 16건 통과.
5. 완료: 변경 파일 ruff/fresh basedpyright 통과.

## 계약

- `write_note`는 파일을 fsync한 뒤 대상 노트 경로만 Git 커밋한다.
- 무관한 staged/unstaged 변경은 커밋에 포함되지 않고 기존 index 상태로 남는다.
- 대상 노트에 staged와 unstaged 변경이 섞여 있으면 워킹트리의 새 노트 내용을 커밋하고, 사용자가 미리 stage한 다른 내용도 index에 유지한다.
- 동일 내용 no-op은 커밋을 만들지 않고 실패가 아니다.
- Git add/commit/hook 실패는 `VaultCommitError`로 전파한다. 이때 파일은 보존하고, 사용자 staged 상태와 HEAD를 변경하지 않는다. 파일까지 되돌리는 자동 롤백은 수행하지 않는다.
- 같은 Vault를 여러 프로세스가 저장할 때 vault lock이 트랜잭션을 직렬화하며 각 커밋은 노트 하나만 포함한다.

## 원인 및 구현

기존 `_auto_commit`은 대상 파일만 `git add`한 뒤 index 전체를 `git commit -m`으로 커밋했다. 따라서 사용자가 미리 stage한 무관 파일이 노트 커밋에 섞였다. Git 오류 메시지도 stdout/stderr을 단순 합쳐 빈 문자열이 될 수 있었다.

- [vault_git.py](../../../../src/antigravity_k/engine/vault_git.py): 신규 노트 전용 임시 index 트랜잭션과 `VaultCommitError`를 분리했다.
- [vault.py](../../../../src/antigravity_k/engine/vault.py): 커밋을 `git commit --only <note>`로 경로 한정하고, Git 상태 코드와 출력을 예외에 보존한다.
- 기존 tracked 노트는 `--only`가 워킹트리 내용을 커밋하고 대상 경로의 index만 갱신한다.
- 신규 노트는 임시 index에서만 stage해 사용자 index를 오염시키지 않는다. 커밋 성공 후 해당 경로만 메인 index에 반영한다. Git이 임시 index를 이동시키는 경계는 사용자 index 백업/복원으로 보존한다.
- `.git/agk-vault-index*` 임시 파일은 성공/실패 후 남기지 않는다.
- [test_tool_sandbox_coverage.py](../../../../tests/test_tool_sandbox_coverage.py): 새 고정 Git 호출 모듈을 프로세스 실행 정책 allowlist에 등록했다.

## 재현 및 RED

```bash
uv run --no-sync pytest tests/test_vault.py -q
```

수정 전 새 계약 테스트는 아래처럼 실패했다.

```text
test_write_note_preserves_unrelated_staged_file
  actual HEAD paths: ['folder/note.md', 'unrelated.md']
test_write_note_preserves_existing_note_staged_and_unstaged_state
  actual HEAD paths: ['note.md', 'unrelated.md']
test_failed_hook_preserves_file_user_index_and_head
  VaultCommitError message was empty; hook stderr was discarded
3 failed, 13 passed
```

## 검증

```bash
uv run --no-sync pytest tests/test_vault.py tests/test_vault_api.py -q
# 31 passed

uv run --no-sync pytest tests -q -m 'not benchmark'
# 4836 passed, 6 skipped, 16 deselected

uv run --no-sync pytest tests/test_workspace_websocket.py tests/test_workspace_websocket_live.py -q
# 28 passed

uv run --no-sync pytest tests/test_benchmark_performance.py -q
# 16 passed

uv run --no-sync ruff check src/antigravity_k/engine/vault.py src/antigravity_k/engine/vault_git.py tests/test_vault.py tests/test_vault_api.py tests/test_tool_sandbox_coverage.py
uv run --no-sync ruff format --check src/antigravity_k/engine/vault.py src/antigravity_k/engine/vault_git.py tests/test_vault.py tests/test_vault_api.py tests/test_tool_sandbox_coverage.py
uv run --no-sync basedpyright src/antigravity_k/engine/vault.py src/antigravity_k/engine/vault_git.py
# 0 errors, 0 warnings, 0 notes
```

첫 전체 실행에서는 `engine/vault_git.py` allowlist 미등록으로 sandbox coverage가 실패했다. 등록 후 통과했다. 같은 실행의 `test_context_enrich_total_latency`는 전체 suite 동시 I/O에서 3200ms로 3000ms 임계를 넘었다가, 단독 재실행과 최종 benchmark 파일 전체에서 모두 통과했다. 이를 F02/F07 해결 증거로 사용하지 않고 변동성으로 기록한다.

실제 surface 검증은 `/api/vault/write` 통합 테스트로 수행했다. 무관 파일을 stage한 상태에서 API가 노트를 저장하면 HTTP 200, HEAD는 노트 한 개만, `git status`는 사용자 staged 항목만 남는다. 4개 프로세스가 같은 임시 Vault에 동시 저장하는 경우도 각 HEAD가 노트 한 개만 포함함을 확인했다.

## 한계

- Git signal 충돌, 강제 종료, 디스크가 백업/복원 중 끊기는 극단적 실패는 자동 복구를 보장하지 않는다. `.git/agk-vault-index*`가 남으면 해당 트랜잭션 실패 직후 상태로 판단하고 사용자 index를 수동 복구해야 한다.
- rename/delete 노트 커밋은 이번 `write_note` 계약에 포함되지 않는다.
- RAG/Wiki 동기화는 기존처럼 Git 커밋 후 best-effort로 실행되며 그 실패가 Git 트랜잭션을 되돌리지 않는다.
- Git 2.50.1 환경에서 검증했다. `--only`와 임시 index의 상호작용은 Git 구현 세부에 의존하므로 Git 버전을 크게 바꾸면 집중 테스트를 다시 실행해야 한다.

## 롤백

`vault.py`, `vault_git.py`, `tests/test_vault.py`, `tests/test_vault_api.py`, `tests/test_tool_sandbox_coverage.py` 변경을 하나의 논리적 단위로 다룬다. 후속 작업이 같은 파일을 수정하지 않았을 때만 이번 hunk를 역적용한다. `git reset --hard`나 index 초기화로 롤백하지 않는다.

## 검증 파일 지문 (SHA-256)

```text
404a9828eb43161e83f933f54828b2d74fa9b1241257757ff3f6e910e7dcad1b  src/antigravity_k/engine/vault.py
eeb3ca3140923422c98d71618d95d746104253015bd0a2700b28a0e5691c8e92  src/antigravity_k/engine/vault_git.py
ec5a018e10dcba5a32d613bac63ed9c0bb406ef85842873d1998497a83ab9e2d  tests/test_vault.py
2132795070f54607e8c456d77d85117d72999a63167d45b00e38960f823fb609  tests/test_vault_api.py
531061273485e2b2029f415ac74dfacc4717a9e23ee5462fe973dc053e00ba9a  tests/test_tool_sandbox_coverage.py
```

이 문서 자체는 내용 변경으로 지문이 바뀌므로 원문 로그 대신 위 명령으로 재계산한다.
