---
title: CR-01 대화 저장소 v2 이전 런북
status: draft-runbook-validated-by-tests (CR-01 REVIEW)
date: 2026-09-11
plan: ../16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md
checklist: ../17_COMMERCIAL_RELIABILITY_CHECKLIST.md
tags: [runbook, conversation-storage, migration, cr-01]
---

# 대화 저장소 v2 이전 런북

이 문서는 CR-01에서 고정한 대화 저장 레이아웃과 그 1회 이전 절차를 운영자에게 설명한다.
수치·경로는 실제 실행 결과가 나올 때 CR-12/CR-14에서 갱신한다.

## 레이아웃

| 버전 | 경로 | 식별 방식 |
|---|---|---|
| legacy (구버전) | `<storage>/<치환된 project>/<치환된 conversation>.json` | 문자 치환 + 64자 절단 → 서로 다른 ID가 같은 파일을 공유할 수 있음 |
| v2 (현재) | `<storage>/v2/<sha256(project_id)>/<sha256(conversation_id)>.json` | 원문 UTF-8 ID의 SHA-256 전체 hex |

기본 storage 루트는 `~/.antigravity/conversations`이며 `AGK_CONVERSATION_STORE_DIR`로 바꿀 수 있다.
v2 레이아웃에서도 모든 읽기는 저장 레코드 본문의 `project_id`/`conversation_id`가 요청 ID와 정확히 일치하는지 검증한다.

## 동시 writer 지원 계약

- **구버전 writer와 신버전 writer를 동시에 운영하지 않는다.** 이전이 끝난 v2 트리에는 v2 코드만 쓴다.
- 이전 완료 마커(`migration_v2.json`)가 없는데 legacy 파일이 남아 있으면 저장소는 읽기/쓰기를 거부하고
  `conversation_storage_migration_required`(HTTP 503)를 돌려준다. 이는 신규 쓰기가 데이터 집합을 갈라놓는 것을 막기 위한 fail-closed 동작이다.
- 롤백은 "구버전 코드가 v2 파일을 읽을 수 있다"고 가정하지 않는다. 서비스를 멈추고 승인된 백업을 복원한다.

## 절차

1. **서비스 정지.** 실행 중인 API/worker/CLI 세션이 대화를 쓰지 않는 상태에서만 진행한다.
2. **백업.** 아래 `--apply`가 자동으로 원본을 백업하지만, 별도 저장소 백업을 미리 받아두는 것을 권장한다.
3. **dry-run(무변경 확인).**
   ```bash
   uv run --no-sync python scripts/migrate_conversation_storage.py --dry-run \
     --storage-dir ~/.antigravity/conversations
   ```
   출력의 `planned[].action`과 `conflicts`를 확인한다. `conflicts`가 비어 있지 않으면 4단계로 진행하지 않는다.
4. **이전 실행.**
   ```bash
   uv run --no-sync python scripts/migrate_conversation_storage.py --apply \
     --storage-dir ~/.antigravity/conversations
   ```
   - 실행 순서: 원본 백업 → v2 파일 원자 생성(`tmp` + `os.replace`) → 재조회 검증 → 완료 마커.
   - legacy 원본 파일은 **삭제하지 않는다**. 삭제는 별도 승인된 정리 작업이다.
   - 이미 동일한 v2 파일이 있으면 다시 쓰지 않는다(중단 후 재실행 멱등).
5. **검증.**
   ```bash
   uv run --no-sync python scripts/migrate_conversation_storage.py --verify-only \
     --storage-dir ~/.antigravity/conversations
   ```
   `state=verified`(exit 0)일 때만 서비스를 재시작한다.
6. **서비스 재시작.** 재시작 후 대화 이력 조회/추가/압축이 정상 동작하는지 확인한다.

## 충돌/손상 시

- exit code `2`는 충돌 또는 검증 실패다. 이때 v2 파일과 완료 마커는 생성되지 않으며 원본은 그대로다.
- `kind`별 의미:
  - `identity_duplicate`: 같은 (project_id, conversation_id)를 가진 legacy 파일 2개가 서로 다른 내용을 담고 있다. 자동 선택하지 않고 운영자가 판단한다.
  - `target_conflict`: v2 대상 파일이 이미 있고 내용이 다르다. 덮어쓰지 않는다.
  - `corrupt` / `missing_ids` / `unreadable`: 레코드 본문에서 ID를 확정할 수 없다. 해당 파일을 격리하거나 복구한 뒤 재실행한다.
- 경로 이름으로 ID를 역추정하지 않는다. 반드시 레코드 본문의 ID를 기준으로 판단한다.

## 롤백

1. 서비스 정지.
2. 이전 시 생성된 백업(기본값: `<storage>.migration-backup-<UTC>` — storage 루트 **바깥** 형제 디렉터리)에서 원본을 복원한다.
3. `<storage>/v2`와 `<storage>/migration_v2.json`을 제거하면 이전 이전 상태로 돌아간다.
4. 구버전 바이너리로 되돌릴 경우에도 위 복원을 먼저 수행한다(v2 파일은 구버전이 읽지 못한다).

## 실패/오류 계약 (API)

| 상황 | 응답 |
|---|---|
| 레코드 바이트 손상 또는 ID 불일치 | HTTP 409 `conversation_integrity_error` (빈 대화로 대체하지 않음) |
| legacy 이전 미완료 | HTTP 503 `conversation_storage_migration_required` |
| 리비전 불일치 | HTTP 409 `stale_conversation_revision` |
| 대상 대화 없음 | HTTP 404 `conversation_not_found` |

대시보드는 `conversation_not_found`(아직 서버에 없는 새 로컬 대화)만 조용히 무시하고, 무결성/이전/서버 오류는 토스트로 표시하며 **다른 대화로 자동 대체하지 않는다**.

## 증거

- 구현/검증 attempt: `.omo/evidence/commercial-reliability/CR-01/attempt-001/`
- 회귀: `tests/test_cr01_conversation_identity.py`, `tests/test_fr05_conversation_authoritative_reads.py`(손상 계약 갱신), `tests/test_conversation_api_ctx01.py`
