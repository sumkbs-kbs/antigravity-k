---
title: NX-01 restore 리허설 · 운영자 복구 절차 — 증거
created: 2026-09-17
state: DONE(리허설) / 미해결 발견 1건(NX03-RESTORE-MARKER)은 동결 해제 뒤
owner: Buffy(NX-10 창, 동결 중 — `docs/` 만 수정해 지문 불변)
evidence: restore_rehearsal.py · restore-rehearsal-output.txt
tags: [nx-01, nx-03, restore, backup, retention, evidence]
---

# restore 를 임시 경로에서 돌린 결과 — 그리고 복구 절차가 지켜야 하는 것

체크리스트의 미완 항목(“restore를 임시 경로에서 실행하고 최신 변경 손실 방지”)을 닫는다.
실행: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/qa/2026-09-16-followup/nx01/restore_rehearsal.py`
→ **경계 4개 전부 통과(exit 0)**. 원본 출력: [restore-rehearsal-output.txt](restore-rehearsal-output.txt).
임시 저장소만 사용했고 실사용 store·vault 는 열지 않았다.

## 0. 먼저 제품 표면을 정확히 적는다 — **import/restore API 가 없다**

있는 것은 export 뿐이다: `ConversationStore.export_original_history()` ·
`GET /v1/conversations/{id}/export`(`journal_sha256`·`revision`·`messages` 포함).
없는 것: import/restore. 따라서 “복구”는 **파일 수준 작업**이고, **안전성은 제품이 아니라 절차가
책임진다.** 그래서 이 리허설은 절차의 판정부(`restore_plan`)를 함께 만들고 **그것이 실제로
최신 변경을 지키는지**를 수로 확인한다.

## 1. 네 경계의 결과

| 경계 | 무엇을 재는가 | 관측 |
|---|---|---|
| S1 왕복 | 빈 임시 저장소에 journal 바이트를 옮기면 원본이 그대로 살아나는가 | `bytes_identical: true` · revision 5=5 · originals 5건 동일(`id`·`role`·`content`·`provenance`) · view 5건 재구성(`Conversation view was missing and rebuilt from the journal`) |
| S2 최신 변경 손실 방지 | 복구 대상이 export 보다 새로우면 **거절**하는가 | `refuse` — “revision 8 > export 5 … export 이후의 원문이 조용히 사라진다” · 그 사이 append 3건은 그대로 생존(`original_message_count 8`) |
| S2b 멱등 | 같은 바이트 재복구는 거절이 아니라 **무동작**인가 | `noop`(“이미 export 와 바이트 동일”) — 운영자가 재실행할 수 있다 |
| S3 삭제 부활 금지 | 삭제 표식이 있는 대상에 삭제 전 바이트를 되돌리면 | 절차는 `refuse` · `deleted` 플래그는 **true 유지** |

**이빨도 확인했다**(같은 날, 같은 트리): 가드를 끄고 옛 바이트를 그대로 덮으면
**revision 8 → 5 로 되돌아가고 그 3건이 사라진다**(원문 8 → 5). 즉 S2 의 거절이 막는 손실은
가정이 아니라 측정된 것이다(원본 출력 하단).

## 2. 남긴 발견 1건 — `NX03-RESTORE-MARKER` (제품 쪽, 지금은 못 고친다)

S3 에서 측정된 사실: **삭제 표식은 `history_state.deleted` 만 이긴다.** 원문 읽기 표면
(`original_history`)은 journal 안의 `delete` 이벤트만 보고 표식은 보지 않으므로,
삭제 전 바이트를 되돌려 놓으면 **삭제된 대화의 원문이 다시 읽힌다**(관측: `deleted true` 인데
originals 3건 반환). 같은 함수의 docstring 은 “Deleted conversations return an empty list.” 라고 적혀 있다.

- 영향: 백업/디스크 이미지 복원처럼 **journal 바이트를 되돌리는 모든 경로**에서 삭제된 대화의
  본문이 export 표면으로 나올 수 있다(표식만 살아 있으므로 UI 상태와 원문 가용성이 엇갈린다).
- 지금 고치지 않은 이유: ① 후보 동결 중이고 ② `src/` 를 건드리면 **도는 8시간 soak 의 지문이 움직인다**.
  검사만 삭제하거나 약화하는 대신 **발견으로 남기고 절차가 거절**하게 했다.
- 수리안(동결 해제 뒤 별도 카드): `original_history`/`export_original_history` 가
  `read_deletion_marker` 도 확인해 삭제된 id 에는 빈 목록/거절을 돌려준다 — NX-03 의 “부활 금지” 계약과
  같은 자리에 검사를 하나 더 붙이는 형태다.

## 3. 운영자 절차(이 리허설이 검증한 것)

1. **복구 전에 export 를 뜬다** — `messages`·`revision`·`journal_sha256` 이 비교 기준이다.
2. 대상 저장소의 현재 상태(`history_state`)와 지문을 잰다.
3. `restore_plan` 규칙대로 판정한다: 삭제 표식 있으면 **거절** · 지문 동일하면 **무동작** ·
   대상이 더 새로우면 **거절** · revision 이 같은데 지문이 다르면 **거절** · 그 외에만 진행.
4. 진행할 때는 **journal 파일만** 대상 경로로 복사한다(view 는 journal 에서 재구성된다 — S1 에서 관측).
5. 복구 뒤 S1 과 같은 항목(id·순서·본문·revision·지문)을 다시 재고 기록한다.

**승격 예정**: 이 리허설은 동결 때문에 `docs/qa/` 안에 있다. 해제 뒤
`tests/` 로 옮겨 계약 시험으로 승격한다(앞서 검사기·판정기·프로브 3종을 승격한 것과 같은 절차).
그 전까지 이 파일은 **재실행 가능한 raw artifact** 다.
