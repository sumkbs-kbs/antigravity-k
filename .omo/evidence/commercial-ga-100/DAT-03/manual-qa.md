# DAT-03 Manual QA — 2026-09-06

## 1. 실제 레지스트리 파일 관찰 (worktree data/)

`uv run --no-sync python` 대화형으로 worktree의 실제 `data/projects.json`에 add/switch 수행:

- 저장 후 파일 구성 관찰: `projects.json` + `projects.json.bak` + `projects.json.lock`
  (정상 저장마다 .bak 회전 확인)
- on-disk JSON은 기존 스키마와 동일 (id/name/path/is_active/last_accessed_at/tasks)
  → 구버전 코드·API와 파일 호환 유지

## 2. 동시성 관찰 (실제 process 2개)

테스트와 동일한 서브프로세스 시나리오를 수동 재실행:
- alpha 프로세스 100개 추가 후, beta 프로세스 100개 추가
- 최종 로드: alpha 100 + beta 100 + default = 201 레코드
  (구현 전에는 beta가 alpha를 덮어써 101이었다 — BR-03 실측 손실)
- lock 파일은 프로세스 종료 후에도 남지만(POSIX flock 관례) 잠금은 fd 기반이라
  유령 잠금 없음.

## 3. 손상 복구 관찰

- `data/projects.json`을 임의 절단 후 새 인스턴스 생성 → .bak에서 자동 복구,
  `projects.json.corrupt-<ts>` 생성 확인 (손상본 보존)
- .bak까지 손상시킨 경우 → default 프로젝트로 클린 부트 (서비스 중단 없음)

## 4. API surface (fail-closed)

`create_project` 경로 코드 리딩 + import 검증:
- `RegistrySaveError` → HTTP 500 "Failed to persist project registry: …"
- 조용한 성공(200 ok 후 실제 저장 누락)이 불가능해짐 — 수용기준 2의 API 관점 충족
- 라이브 서버 기동은 후속 리뷰 단계에서 재확인 권장 (본 단계는 코드 계약 검증)

## 5. 잔여 관찰 (non-blocking)

- 단일 .bak 세대 — 마지막 저장 직후 손상 시 최신 1회분은 손실 가능 (계약 명시)
- `data/projects.json.lock`은 gitignore 대상 아님 — 운영 환경에서 local-only 파일
  (worktree에서 untracked로 관찰됨, 커밋 대상 아님)
