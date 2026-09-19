---
title: CR-02 세션 저장 실패·내구성 불확실 대응 런북
status: draft-runbook-validated-by-tests (CR-02 REVIEW)
date: 2026-09-12
plan: ../16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md
checklist: ../17_COMMERCIAL_RELIABILITY_CHECKLIST.md
tags: [runbook, session, durability, storage, cr-02]
---

# 세션 저장 실패·내구성 불확실 대응 런북

CR-02가 고정한 세션 저장 계약과, 저장이 실패했을 때 운영자가 취해야 할 순서를 설명한다.
CR-12가 초안을 만들었고, 실제 운영 리허설 결과는 CR-14에서 이 문서에 반영한다
([계획서](../16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md) C12-03/C14).

## 저장 위치와 쓰기 순서

| 항목 | 값 |
|---|---|
| 프로젝트 런타임 경로 | `<project_root>/.antigravity/sessions` |
| 기본(base) 경로(프로젝트 미지정) | `~/.antigravity/sessions` |
| 쓰기 순서 | 직렬화 → 고유 임시 파일 → `flush`/`fsync` → `os.replace` → **디렉터리 `fsync`** |
| 동시 writer | **구버전 프로세스와 신버전 프로세스 동시 운영 미지원** |

`os.replace` **이전**의 모든 실패는 원본 파일 바이트를 그대로 남긴다. `os.replace` **이후**
디렉터리 `fsync` 실패는 되돌리지 않고 "내구성 불확실"로 전달한다 — 그래서 두 실패는 다른
오류로 구분된다.

## 증상 → 의미

| 증상(HTTP/코드) | 의미 | 데이터 상태 |
|---|---|---|
| 409 `stale_session_write` | 메모리 스냅샷의 기반 revision이 디스크와 다르다(다른 writer가 먼저 저장) | 디스크는 정상. 요청은 반영되지 않음 |
| 503 `session_persistence_error` | 직렬화/임시 파일/`replace` 단계 실패 | **원본 파일 바이트 유지**(유실 없음) |
| 503 `session_durability_uncertain` | `replace`는 성공했지만 디렉터리 `fsync` 실패 | 파일은 갱신됐으나 전원 손실 시 유실 가능 |
| 세션 파일 손상(`unreadable`) | JSON 파싱/필드 검증 실패 | 손상 파일은 quarantine으로 이동, 원본 경로에서 제외 |

세션 저장 실패를 "조용히 무시하고 계속"하는 동작은 없다 — 실패는 위 코드로 표면화된다.

## 절차

### A. `stale_session_write`(409)가 반복될 때

1. 같은 세션 ID를 쓰는 프로세스가 둘 이상인지 확인한다.
   ```bash
   ls -l <project_root>/.antigravity/sessions
   ps aux | grep -E "uvicorn|agk" | grep -v grep
   ```
2. 구버전 프로세스가 남아 있으면 **종료한다**(동시 writer 미지원). 그 뒤 최신 revision으로
   다시 요청한다.
3. 클라이언트가 오래된 revision을 재사용하고 있지 않은지 확인한다 — 409는 "다시 읽고
   재시도"를 요구하는 신호이며, 같은 revision으로 재전송하면 계속 409다.

### B. `session_persistence_error`(503)가 날 때

1. 디스크 여유와 권한을 확인한다.
   ```bash
   df -h <project_root>
   ls -ld <project_root>/.antigravity <project_root>/.antigravity/sessions
   ```
2. 쓰기 가능 여부를 직접 확인한다(서비스 계정과 같은 사용자로 실행).
   ```bash
   T="<project_root>/.antigravity/sessions/.write-probe-$$"
   printf 'ok' > "$T" && rm -f "$T" && echo "write OK"
   ```
3. 원본 세션 파일이 그대로인지 확인한다(바이트 유지가 계약이다).
   ```bash
   ls -l <project_root>/.antigravity/sessions | tail -5
   ```
4. 원인(용량/PID 한도/권한)을 해소한 뒤 **같은 요청을 다시 보낸다**. 재시도는 안전하다 —
   실패한 쓰기는 파일을 바꾸지 않았다.

### C. `session_durability_uncertain`(503)이 날 때

1. 이 오류는 "값은 저장됐지만 디스크에 확실히 내려가지 않았다"는 뜻이다. **즉시 재시도하지
   말고** 파일 내용이 기대한 턴을 포함하는지 먼저 확인한다.
   ```bash
   uv run --no-sync python - <<'PY'
   import json, pathlib
   path = pathlib.Path("<project_root>/.antigravity/sessions")
   for f in sorted(path.glob("*.json"))[-3:]:
       data = json.loads(f.read_text(encoding="utf-8"))
       print(f.name, "revision=", data.get("revision"), "turns=", data.get("turn_count"))
   PY
   ```
2. 파일이 기대한 revision을 담고 있으면 세션을 계속 쓴다(다음 성공 저장이 다시 fsync한다).
3. 담고 있지 않으면 해당 세션을 종료하고 이전 대화 이력으로 새 세션을 시작한다 — 서버는
   구버전 프로세스와의 "같은 세션 동시 쓰기"를 보장하지 않는다.

### D. 손상된 세션 파일을 발견했을 때

1. quarantine 파일을 확인한다(원본은 보존된다).
   ```bash
   find <project_root>/.antigravity/sessions -name "*quarantine*" -o -name "*.corrupt*" | head
   ```
2. 손상 파일은 세션 목록에서 빠지므로 해당 세션 이력만 영향을 받는다. 다른 세션 파일은
   건드리지 않는다.
3. 손상 원인(디스크 오류/부분 쓰기/외부 편집)을 기록하고, 복구가 필요하면 파일을 오프라인에서
   검사한 뒤 복사본으로 되돌린다 — 원본을 덮어쓰지 않는다.

## 확인

- 저장 계약 회귀:
  ```bash
  uv run --no-sync python -m pytest tests/test_cr02_session_durability.py -q
  ```
- 정상 저장 확인(성공 경로는 조용히 끝난다): 세션 하나를 열고 턴을 한 번 추가한 뒤
  `revision`이 증가하고 파일 크기가 0이 아닌지 본다.
  ```bash
  find <project_root>/.antigravity/sessions -name "*.json" -size 0 | head
  ```
  `0바이트 파일`이 나오면 즉시 보고 대상이다(CR-02가 닫은 결함의 재발 신호).

## 롤백

- 저장 로직 자체를 되돌리는 롤백은 제공하지 않는다(이전 동작은 0바이트 유실 결함을 포함한다).
- 잘못된 내용이 저장된 경우: 파일을 백업한 뒤 해당 세션을 폐기하고 새 세션을 시작한다.
- 여러 세션을 통째로 되돌려야 하면 서비스를 멈추고 저장소 스냅샷에서 복원한다(복원 중에는
  writer가 없어야 한다).

## 남은 위험 / 지원 범위

- Linux/Docker 파일시스템의 `fsync` 의미(macOS와 다를 수 있음)는 이 저장소에서 실측하지
  않았다. 네트워크 파일시스템(NFS/SMB)은 지원 범위가 아니다.
- 구버전 프로세스와의 동시 실행은 어떤 경우에도 지원하지 않는다 — 배포 시 구버전 종료가
  필요하다.
- 세션 저장 실패의 알림/모니터링 임계는 [지원 매트릭스](GA_SUPPORT_MATRIX.md)에서 아직
  "Experimental"이다(운영 승인 미완료, BLOCKED_EXTERNAL).
