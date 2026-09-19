# NX-02 후속 — journal retention/quota 결정과 집행 (2026-09-16, NX-10 동결 배치)

## 왜 이 결정이 릴리스 blocker 였나

NX-02 는 "원본은 압축 뒤에도 보존한다"를 채택했고, 그 결과 **journal 은 총 턴 수에 비례해
커진다**(view 만 soft max 64 로 bounded). 그런데 `ADR-DAT-02` Context 8 이 요구한 기본값이
없었고, 그 문서는 **조용한 prune 을 금지**한다:

> 8. **Retention/quota defaults are decided before the journal is enabled** (explicit byte/age
>    limits and a user-visible notice when a prune happens); silent pruning is not allowed.

즉 "가득 차면 오래된 것을 지운다"를 기본값으로 넣는 선택은 ADR 위반이고, 사용자에게 보이는
원본 이력을 제품이 임의로 지우는 일이 된다.

## 결정 (오너 판정 2026-09-16)

| 항목 | 결정 |
|---|---|
| 자동 prune | **없음.** 자동 삭제를 넣지 않는다(ADR 금지 조항). 한계에 닿아도 기존 데이터는 그대로다. |
| 단위 | **대화 하나당 journal 바이트**. 전체 저장소 스캔은 O(대화 수)라 쓰기 경로에 넣지 않는다. |
| soft cap | `AGK_CONVERSATION_JOURNAL_SOFT_CAP_MB` = **64 MiB** — 넘으면 경고 로그(대화당 1회). 쓰기는 계속된다. |
| hard cap | `AGK_CONVERSATION_JOURNAL_HARD_CAP_MB` = **512 MiB** — 넘으면 append **거절**(507). |
| 비활성 | `0` = 그 단계 비활성(hard 를 끄면 거절하지 않는다). |
| 거절의 표면 | 507 `conversation_history_quota_exceeded` + `journal_bytes`/`soft_cap_bytes`/`hard_cap_bytes`/`remedy` 컨텍스트. |
| 운영자 회수 | `ConversationStore.store_usage()` 가 전체 바이트·journal 수·가장 큰 journal·한계 초과 개수를 보고한다. |

거절(hard)과 경고(soft)를 나눈 이유: 512 MiB 는 **폭주 방지선**이지 디스크 계획 도구가 아니다.
운영자는 64 MiB 경고를 보고 미리 조치하고, 512 MiB 는 사고(무한 루프·대화 폭주)에서 저장소를
지키는 마지막 닫힘이다. 값은 두 환경변수로 재시작 없이 바뀐다.

## 구현

* `src/antigravity_k/engine/conversation_retention.py` — 정책 해석(환경변수 검증: 잘못된 값/음수는
  기본값 + 경고), `verdict(size)`(`ok`/`soft_exceeded`/`hard_exceeded`, 역전 설정에서도 hard 우선),
  `format_mb`.
* `ConversationStore._assert_journal_capacity()` — `_commit_event`(journal 커밋 지점) 앞에서 집행.
  hard 초과면 **쓰기 전에** 타입 오류를 올린다(부분 쓰기 없음). soft 초과는 대화당 한 번만 경고한다
  (`_soft_cap_warned`).
* `ConversationStore.store_usage()` — 요청 시 관측(전체 바이트·journal 수·top 10·한계 초과 개수·정책).
* `api/contracts/errors.py` + dashboard `clientSchema.ts` + 두 fixture — 새 코드 507 을 wire 계약에
  동시에 등록(NX-02 가 세운 "한 쪽만 바뀌지 않는다" 규칙 유지).

## 증거

`tests/test_nx02_journal_retention.py` — **9 passed**: 정책 기본값/경계/환경변수/비활성/역전,
hard 초과 거절(저널 byte·revision·이력 **불변**, 회복 경로 포함), 비활성 시 거절 없음,
soft 경고 1회 + 쓰기 지속, `store_usage()` 수치와 한계 초과 계수,
wire 계약(Python 맵 + 두 fixture + dashboard 스키마), HTTP 표면에서 507 + 코드 + 이력 유지.

## 남은 것 / 한계

* **저장소 전체 사용량은 집행하지 않고 관측만** 한다. 전체 스캔을 매 append 에 넣으면 쓰기 경로가
  O(대화 수) 가 된다. 전체 상한이 필요해지면 별도 카드(주기적 스캔 + 운영 경보)로 다룬다.
* 운영자 **부분 회수 도구는 없다**: 한계에 닿으면 값을 올리거나 대화 단위로 export/삭제해야 한다.
  journal 의 앞부분만 잘라내는 prune 은 revision/삭제 표식/export 의미를 깨므로 의도적으로 만들지
  않았다(그 판단은 이 카드의 계약이다).
* 손상된 대화의 격리·폐기 운영 절차는 여전히 미결정(별도 소유자 필요 — NX-02 handoff §5).
