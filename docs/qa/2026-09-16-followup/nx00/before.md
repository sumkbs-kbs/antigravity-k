# NX-00 — 재현 조건과 관측 (before)

## 재현 조건

- 기준 HEAD: `ffb0ebb312b76d86742d3e4065628a9704f8268e` (2026-09-16 확인, 작업 중 변경 없음).
- 원본 위치(읽기 전용): `.omo/evidence/commercial-reliability/CR-14/ex-2026-09-15/soak/`.
  - `val02_soak_28800_resoake.json` 6,244,278 bytes, sha256 `741d64e3…c948f`
  - `val02_soak_28800_resoake.log` 8,245 bytes, sha256 `bb4546fa…2c2bc`
  - 이전 FAIL 실행: `val02_soak_28800.json` sha256 `7f60bcb0…5292f`, `val02_soak_28800.log` sha256 `96c2e510…39149`
  - `pid_resoake.txt` 내용 `72709 72711` (pid.txt와 동일 바이트, sha256 `228e1b32…c6f8a8`)
- 관측 환경: macOS(darwin arm64), Python 3.13.12 (`./.venv`), 원본 파일 수정 없음.

## 기대

- 8시간 재soak의 지표(SC-1~6 PASS, RSS 64MB 이하, append=revision, 오류·orphan 0).
- 실행 종료의 독립 증명(종료 코드 또는 종료 시각)과 그 결과가 어느 코드 후보의 것인지에 대한 귀속.

## 관측

- 지표: 모두 PASS (원본 JSON 직접 파싱 — `independent-parse.txt`).
- 종료: 래퍼 로그 마지막 줄이 `finished exit:141`이고, 종료 코드를 보존한 파일은 없다.
- 로그 본문은 artifact JSON과 동일한 접두부이며 513줄에서 끊긴다(stdout 절단).
- run 당시 코드 후보/지문을 증명하는 기록이 없다(`run_sha_binding: UNVERIFIED`).

## 소실·권한 위험

- 위험 낮음: 원본은 읽기 전용으로만 열었고 어떤 파일도 수정/이동/삭제하지 않았다.
- 인증 백업(`data/auth_hash.bak.pre-0000`)과 `vault_data` 변경은 이 카드의 범위가 아니며 내용을 읽지 않았다.
- 남은 위험: 종료 증명이 없으므로 이 run을 "정상 종료"로 인용하면 안 된다(소급 승격 금지).
