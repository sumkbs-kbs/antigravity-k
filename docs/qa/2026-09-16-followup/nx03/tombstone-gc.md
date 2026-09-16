# NX-03 후속 — 삭제 표식(tombstone) GC 정책 (2026-09-16, NX-10 동결 배치)

## 문제

NX-03 은 삭제를 "표식 선기록 → 가시 데이터 제거"로 고정했고, 그 덕분에 stale writer 가 삭제된
세션을 되살리지 못한다. 대가는 누적이다: 표식은 `<sessions>/.tombstones/<id>.json` 에 **삭제된
ID 당 1개**씩 남고 **자동 만료가 없었다**(NX-03 handoff §6.1 이 "GC 정책 없음 — 임의 TTL 금지"로
남긴 항목).

## 결정 (오너 판정 2026-09-16)

* **자동 TTL 만료는 없다.** 표식을 지우면 그 세대의 stale writer 가 다시 살아날 수 있으므로,
  "얼마나 오래된 표식을 버려도 되는가"는 제품이 정할 값이 아니라 **위험을 감수하는 운영자의 결정**이다.
* 대신 **명시적 회수 API** 를 둔다: `SessionManager.collect_tombstones(older_than_seconds=..., dry_run=True)`.
  * `older_than_seconds` 는 **필수**이고 `> 0` 이어야 한다 — `0`/음수로 "전부 만료"하는 사고를 코드가 거부한다.
  * 기본은 **dry-run** 이다. 실제 회수도 **삭제가 아니라 이동**이다: `<tombstones>/gc/<UTC>/` 로 옮기고
    `gc-report.json`(스키마 `agk.session-tombstone-gc.v1`)에 옮긴 목록·기준·시각을 남긴다. 파일을
    되돌려 놓으면 보호가 복원되므로 이 작업은 가역·감사 가능하다.
* 누적은 **관측 가능**해야 한다: `SessionManager.tombstone_usage()` 가 개수·바이트·가장 오래된/최신
  나이와 `automatic_expiry: False` 를 보고한다. 아카이브(`gc/` 하위)는 활성 표식 집계에 들어가지 않는다.

## 구현

* `src/antigravity_k/engine/session_manager.py`
  * `tombstone_usage()` — 누적 관측(`automatic_expiry: False` 명시).
  * `collect_tombstones()` — 나이 기준 회수. `older_than_seconds <= 0` → `ValueError`.
    후보만 dry-run 으로 보고하고, 실제 회수 시 아카이브로 이동 + 감사 JSON. 이동 실패는 경고 후 계속
    (부분 회수도 감사 기록에 남는다).
* 삭제 경로(제품 코드)는 **바뀌지 않았다** — 표식을 쓰는 계약은 NX-03 그대로다. 이 배치는 GC 만 더한다.

## 증거

`tests/test_nx03_tombstone_gc.py` — **6 passed**:

* 표식은 **제품 삭제 경로**(`start_session` → `clear_memory("all")`)로 만든다(손으로 쓰지 않는다),
* 사용량이 개수·바이트·나이를 보고하고 `automatic_expiry: False`,
* dry-run 은 후보만 보고하고 파일을 건드리지 않는다,
* 실제 회수는 아카이브로 **이동**하고 감사 기록을 남기며 활성 집계에서 빠진다,
* 기준보다 젊은 표식은 남는다,
* `0`/음수 기준은 `ValueError`,
* 회수 뒤 새 삭제는 다시 표식을 남긴다(보호는 계속 동작한다).

## 남은 것 / 한계

* **회수의 대가를 코드가 막을 수는 없다**: 기준보다 오래된 stale writer(예: 몇 달 전 스냅샷을 쥔
  프로세스)는 표식이 사라진 뒤 그 ID 를 되살릴 수 있다. 그래서 기본값이 없고 자동화도 없다.
* 저장소에 `gc/` 가 쌓인다 — 그것을 언제 비울지는 같은 문제(운영자 판단)이며, 여기서는 이동만 한다.
* NX-03 이전 버전이 남긴 삭제(표식 없음)는 여전히 복구할 수 없다(기존 한계 그대로).
