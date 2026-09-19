# NX-00 — 결과 (after)

## 변경

- 제품 코드·런타임·gate 설정 변경 **없음**. 원본 soak artifact 4종·pid 파일 모두 바이트 단위로 동일(해시는 `artifact-hashes.txt`).
- 추가된 것은 증거 도구와 기록뿐이다.
  - `docs/qa/2026-09-16-followup/nx00/verify_soak_artifact.py` (원본 읽기 전용 파서)
  - `independent-parse.txt`, `artifact-hashes.txt`, `log-prefix-check.txt`, `before.md`, `after.md`, `handoff.md`

## 동일 입력의 결과

| 질문 | 답 |
|---|---|
| SC-1~6 지표가 PASS인가 | 예 — 원본 JSON에서 독립 재계산, 임계값 동결값 유지 |
| RSS 기준이 완화됐는가 | 아니오 — `rss_leak_mb 64` 그대로, 재계산 증가 48.7MB |
| append와 revision이 같은가 | 예 — 12,102,886 = 12,102,886 |
| 이전 FAIL 실행이 보존됐는가 | 예 — `val02_soak_28800.json`(sha256 `7f60bcb0…`) 미변경 |
| run이 정상 종료했는가 | **미확정** — 로그 `finished exit:141`, 종료 코드 파일 없음 |
| 이 run이 어느 후보의 결과인가 | **미확정** — 시작/종료 지문 연결 증거 없음 |

## 회귀 범위

- 없음(제품 코드 미변경). 검증 명령은 `commands.txt` 참조.

## 데이터 이전·복구 조건

- 해당 없음. 원본 artifact는 이후에도 수정 금지이며, NX-10 재실행 시에도 이전 파일을 덮지 않고 새 attempt 디렉터리를 사용한다.

## 인계 요약

- 지표 재확인 항목은 완료로 닫을 수 있다.
- 종료·후보 귀속 항목은 `INCONCLUSIVE`로 남기고 NX-10의 새 시험으로 대체한다.
- harness/래퍼 계약은 `handoff.md` §4의 `NX-00-F01` 제안으로 넘긴다(미구현).
