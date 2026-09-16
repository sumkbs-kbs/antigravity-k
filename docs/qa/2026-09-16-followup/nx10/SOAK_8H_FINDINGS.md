# NX-10 8시간 soak 회수 — 판정과 근본 원인 (2026-09-16 실행 / 2026-09-17 회수)

이 문서는 **한 번의 실행**(`12:13:12Z` 시작, 28,800초)에 대한 사실과, 그 실행이 드러낸 결함의
**측정된** 원인을 소유한다. 추측은 추측이라고 적는다.

---

## 1. 판정 — FAIL (원인은 하나)

```
$ PYTHONPATH=src .venv/bin/python scripts/collect_soak_result.py      # 2026-09-16T22:09:18Z
  러너: 시작 2026-09-16T12:13:12Z → 종료 2026-09-16T20:13:16Z · exit 1
  지문: start=322b4d3ba062a0d9… end=322b4d3ba062a0d9… 기대=322b4d3ba062a0d9… 지금=322b4d3ba062a0d9…
  기대 지문 출처: soak-schedule.txt 예약 이력 6건 중 마지막
    [pass] SC-1 … [pass] SC-5
    [FAIL] SC-6-soak: duration_s=28800.075 requested_duration_s=28800 orphan_worktrees=0 errors=0
  ── 판정 ──
    [NO  ] ① 지표(all_pass·missing_required) — all_pass=False
    [NO  ] ② 실행 exit==0 — exit=1
    [OK  ] ② 실행 벽시계 ≥ 28800s — 28804s
    [OK  ] ③ 시작 지문 == 종료 지문
    [OK  ] ③ 기대 지문 == 시작 지문
    [OK  ] ③ 지금 트리 == 시작 지문(측정 후 코드 무변경)
  판정: FAIL (미충족: ①, ②)
```

**미충족 ①·②는 같은 하나의 원인**이다: SC-6 의 `rss_growth_mb = 1683.5` (기준 64.0, **26.3배**).
다른 필수 지표는 전부 초록이다.

## 2. 실행 사실 (리포트 `soak-28800.json`)

| 항목 | 값 |
|---|---|
| 기간 | `12:13:12Z` → `20:13:16Z` · `duration_s 28800.075` (요청 28800, 100.0%) |
| 귀속 | `start_fingerprint == end_fingerprint == 322b4d3b…` · 기대 지문(예약 이력 6건 중 마지막)과 동일 |
| SC-1~5 | 전부 `pass` (SC-5: p95 2.55ms · p99 3.25ms · error 0.0%) |
| SC-6 처리량 | `completed_ops 70,430` · `conversation_ops 70,430` · revision 70,431 |
| SC-6 불변식 | `conversation_append_equality true` · `messages_bounded true`(view 19 ≤ soft max 64) · `compaction_generations 1,214` · `constraint_preserved true` · `errors 0` |
| SC-6 원본 보존 | `originals 70,431` · `complete true` · 검증 방식 `full_replay` (70,431건 전수 확인) |
| SC-6 journal | 24,444,921 B / 70,431줄 |
| SC-6 fd·orphan·DB | fd 5→5(`fd_growth 0`) · `orphan_worktrees 0` · `db_accessible_after true` |
| **SC-6 RSS** | **66.8 → 1750.2 MB = +1683.5 MB (기준 64.0) → FAIL** |
| 계측 overhead | `measurement_overhead_ratio 0.0` (샘플링이 soak 를 지배하지 않음) |

해석: **의미 보존·원본 보존·bounded view·오류 0·fd 0·orphan 0 은 8시간 규모에서 처음으로 확인됐다.**
깨진 것은 메모리 하나다. 그리고 처리량도 비정상이다 — `70,430 append / 28,800초 = 2.45 ops/s` 는
같은 저장소가 소량 상태에서 내는 값(수백 ops/s)의 1% 수준이다.

## 3. 근본 원인 — `journal.tail()` 이 매 append 마다 journal 전체를 파싱한다 (측정)

`ConversationStore.append()` 는 커밋 전에 `_authoritative_record()` 를 부르고, 그 안에서
`journal.tail()` 을 부른다. `tail()` 은 자기 docstring 에 **"Last committed event state without
replaying the whole file"** 라고 적혀 있지만 실제 구현은:

```python
raw = self._read_bytes()            # path.read_bytes() — 파일 전체를 메모리에
good_bytes, _, truncated = self._split_truncated_tail(raw)
for line in good_bytes.split(b"\n"):     # 70,431 조각
    data = json.loads(line.decode())     # 모든 줄을 파싱
    last = JournalEvent.from_dict(data)  # 모든 줄을 객체로
```

마지막 이벤트만 필요한데 **전체를 읽고·쪼개고·파싱한다**. 실측(8시간 실행이 남긴 실제 24.4 MB journal):

| 측정 | 값 | 방법 |
|---|---|---|
| `journal.tail()` 1회 | **265 ~ 271 ms** | 실물 journal, tracemalloc 없이 |
| `read_bytes()+count(b"\n")` | 8 ms | 같은 파일(줄 수만 셀 때) |
| `append()` 1회 (8h 상태 위에서) | **814 ~ 830 ms** | 실물 저장소 사본, tracemalloc 없이 |
| 그 안의 `tail()` 호출 | **3회 · 누적 810 ms = append 의 99.5%** | 메서드 래핑 카운터 |
| ↳ `_authoritative_record` | 1회 · 271 ms | 〃 |
| ↳ `_commit_event` | 2회 · 542 ms | 〃 |
| `_refresh_latest`(view 캐시) | **0 ms** | 캐시 자체는 정상 동작 |
| `_materialize_from_journal`(전체 replay) | 663 ms | 재구축 경로 전용 |

**즉 append 1회 = journal 전체 파싱 3회.** 비용은 journal 크기에 비례하므로 실행 전체로는 제곱이 된다:
`70,430 append × 3 × 평균 12.2 MB ≈ 2.6 TB 읽기 · 약 74억 줄 JSON 파싱`. 평균 append 비용 ≈ 0.41초
→ `70,430 × 0.41 ≈ 28,800초` 로, **8시간 벽시계의 사실상 전부가 `tail()` 안에서 쓰였다**(관측 2.45 ops/s 와 일치).

같은 결함을 소규모에서도 재현했다(60초 append 전용 프로브):

| 시점 | journal | 처리량 |
|---|---|---|
| 200 ops | ~0.2 MB | 4 ms/op |
| 2,800 ops | ~0.9 MB | 31 ms/op |
| 70,431 ops (실행 끝) | 24.4 MB | ~814 ms/op |

## 4. 그 1.68 GB 는 **객체 누수가 아니다** (측정)

- 60초 프로브에서 **살아 있는 객체 수는 평탄**(60,818 → 60,817, 등락 ±25)했다. 커진 것은 RSS 뿐이다.
- 8h 상태 위 append 1회의 **일시 할당 peak = 52 MB**(tracemalloc), tracemalloc 없이 프로세스
  `maxrss` 는 60.6 → 133 MB (append 2회).
- live object 델타는 오히려 **감소**(-292)했다.

따라서 RSS 증가는 **journal 전체 파싱이 매번 만드는 수십 MB급 일시 할당의 잔존(high-water)** 이다 —
해제된 객체가 아니라 allocator 가 돌려주지 않은 영역. 같은 원인(무제한 파싱)을 고치면 둘 다 사라진다.
이 구분은 중요하다: “객체 그래프가 무한히 자란다”가 아니라 “매 호출이 파일 크기에 비례하는 일시 할당을
만들고, 파일이 계속 커진다”이므로 **고칠 곳은 파싱 범위**이지 캐시 정책이 아니다.

## 5. NX-04 의 `stream_line_count` 경로는 **이번에도 타지 않았다** (정정)

- 실행은 `conversation_originals_verification: "full_replay"` · `conversation_journal_lines: -1` 로 끝났다.
  즉 8시간 뒤에도 **메모리 전수 replay 분기**를 탔다.
- 이유는 임계값이다: `ORIGINALS_REPLAY_MAX_BYTES = 32 MiB` 인데 **8시간 journal 은 24.4 MB** 였다(미달).
  코드 주석의 가정("정식 soak(8h, 수 GB)")과 실제 크기가 다르다 — 이 가정이 틀렸다는 사실을 여기 적는다.
- **2026-09-17 추가**: 그 뒤 `tail()` 수정으로 처리량이 180배 오르면서 **10분 만에 94.1 MB journal**
  이 만들어졌고, 그 실행이 `stream_line_count` 분기를 처음 탔다(`journal_lines=269,088` ·
  `terminated=True` · `originals_complete=True`). 즉 이 항목은 **임계값을 건드리지 않고 닫혔다** —
  같은 8시간이라면 1,290만 append 규모가 되므로 32 MiB 조건은 사실상 항상 성립한다.

## 5b. 부수 관찰 — `soak_control.sh preflight` 가 이 실패를 예고하지 못한 이유

preflight 10항목은 예약·지문·여유공간·중복 실행을 보지만 **"이 작업량이 8시간 안에 끝나는가"는 보지
않는다**. 사실 8시간은 작업량이 아니라 `tail()` 비용이 결정했다. 다음 회차에는 preflight 에
**처리량 하한**(예: 시작 후 5분 동안 ops/s 측정 → 외삽)을 넣는 것이 옳다 — 이 실행에서는 시작
5분 시점의 ops/s 가 이미 정상의 1% 였고, 그때 알았다면 8시간을 태우지 않았다.

## 5c. 수정과 그 효과 (측정, 2026-09-17)

**바꾼 파일 2개**: `src/antigravity_k/engine/conversation_journal.py`(수정) ·
`tests/test_nx02_history_journal.py`(계약 시험 2건 추가).

**바꾼 것**: `ConversationJournal.tail()` 이 꼬리 창(기본 64 KiB)만 읽고, 창으로 판정하지 못하는
파일(줄이 창보다 긴 경우 등)만 종전 전체 스캔으로 되돌아간다(`_tail_by_full_scan`). 관대한 파싱
(못 읽는 줄을 건너뛰는 규칙)과 `truncated_tail` 판정은 그대로다 — 창 경로와 전체 스캔이 **모든 파일
모양에서 같은 판정**을 낸다는 것을 계약 시험으로 고정했다. 읽는 중에 파일이 줄어드는 경우는 짧게
읽힌 것으로 감지해 다시 읽는다(`os.pread` + `os.fstat`).

**실물 8h journal(24.4 MB / 70,431줄)에서 재측정:**

| 측정 | 수정 전 | 수정 후 |
|---|---:|---:|
| `journal.tail()` 1회 | 265 ~ 271 ms | **0.04 ~ 0.05 ms** (~6,000배) |
| `append()` 1회 (같은 상태) | 814 ~ 830 ms | **0.5 ~ 0.8 ms** (~1,200배) |
| append 3회의 프로세스 `maxrss` | 60.6 → **133 MB** | 60.8 → **60.9 MB** |

**같은 60초 SC-6 리허설 비교(`soak-60.json` vs 수정 뒤 60초):**

| 항목 | 수정 전 | 수정 후 |
|---|---:|---:|
| `completed_ops` (60초) | 2,978 | **29,180** (9.8배) |
| journal 크기 | 995,118 B | 10,090,434 B (**10배 큼**) |
| `rss_growth_mb` | 21.2 | **16.8** |
| RSS 증가/op | 7.29 KB | **0.59 KB** (12배 작음) |
| `pass` · `errors` · `fd_growth` | true · 0 · 0 | true · 0 · 0 |

즉 같은 시간에 **10배 큰 journal 을 상대하면서 9.8배 많은 작업**을 했고, 초록은 그대로다
(view 7 ≤ 64 · 원본 전수 확인 `full_replay` · generations 503).

**계약 시험 2건 추가**(`tests/test_nx02_history_journal.py`):

1. `test_journal_tail_reads_only_its_window` — journal 크기(> 창)와 무관하게 꼬리 판정이 창을 넘지
   않으며 전체 읽기 경로(`_read_bytes`)를 **쓰지 않는다**를 고정한다. `append` 경로에도 같은 계약을 건다.
2. `test_journal_tail_window_verdict_equals_full_scan_for_every_shape` — 빈 파일 · 빈 줄만 · torn 한 줄 ·
   torn tail · 마지막 줄 손상 · 중간 줄 손상 · **창보다 긴 한 줄**까지, 창 경로의 판정이 종전
   전체 스캔과 **정확히 같음**을 고정한다.

**시험에 이빨이 있는지 확인했다**: 수정 전 `tail()` 구현을 주입해 1번 시험을 돌리면
`AssertionError: tail() 이 journal 전체를 읽었다 — 꼬리 창 계약 위반` 으로 **실패**한다(1 failed).

**10분 규모에서 기울기가 0으로 수렴하는지 확인했다(같은 날, `SC-6` 600초):**

| 항목 | 수정 전 8시간 | 수정 후 **10분** |
|---|---:|---:|
| `completed_ops` | 70,430 (2.45 ops/s) | **269,087 (448.5 ops/s)** |
| journal | 24.4 MB | **94.1 MB** |
| `rss_growth_mb` | **1,683.5** (FAIL) | **32.2** |
| `pass` · `errors` · `fd_growth` · `orphan` | false · 0 · 0 · 0 | **true · 0 · 0 · 0** |
| view(≤64) · generations | 19 · 1,214 | 26 · 4,639 |
| 원본 검증 방식 | `full_replay` (24 MB) | **`stream_line_count` (94 MB)** — 첫 실측, 통과 |

**즉 수정된 코드는 10분에 옛 코드가 8시간에 한 일의 3.8배를 했다.** RSS 는 구간별 기울기가
`0.643 → 0.240 → 0.160 → 0.145 → 0.008 → 0.015 → 0.004 → 0.008 → 0.000 → 0.004` KB/op 로
**평탄부(plateau)에 들어갔다**(마지막 5구간 평균 ≈ 0.006 KB/op). 그 기울기로 8시간(≈1,290만 ops)을
외삽하면 **+48 MB < 기준 64 MB** 이고, 이는 **다른 후보의 과거 8시간 재soak 실적(+48.7 MB / 1,210만
append)** 과 사실상 같은 값이라 모델이 교차 검증된다.

**그래서 “수정 전 1.68 GB”의 성격이 확정된다**: 고정된 누수가 아니라 **journal 크기에 비례하는
일시 할당이 커지면서 함께 자란 allocator 고수위**였다. 크기 비례 성분이 사라지면 남는 것은
수십 MB 수준의 상수다.

**부수 성과 — NX-04 의 `stream_line_count` 경로가 처음 실행됐다.** 10분 실행의 journal 이
94.1 MB 로 32 MiB 임계를 넘어 `replay_deferred=True` · `journal_lines=269,088` · `terminated=True` ·
`originals_complete=True` 로 끝났다. 8시간 실행이 닫지 못한 항목(§5)이 이 실행으로 닫혔다 —
메모리에 올리지 않는 스트리밍 검증이 실물 규모에서 작동한다.

## 5d. 회귀 확인 — 전체 스위트와 교차 레인 충돌 (2026-09-17)

수정 뒤 전체 스위트를 돌렸다(수정한 명령 그대로 적는다 — 이 프로젝트의 `python-tests` 게이트는
`-m "not benchmark"` 를 쓰는데 나는 그 플래그 없이 돌렸다):

```
.venv/bin/python -m pytest -q -p no:cacheprovider
→ 5 failed, 6640 passed, 10 skipped, 20 xfailed in 631.46s
```

5개를 하나씩 귀속했다:

| 실패 | 원인 | 이 수정의 것인가 |
|---|---|---|
| `test_benchmark_performance.py::test_context_enrich_total_latency` | 그 파일 자신의 docstring 이 "6000여 개 테스트를 도는 프로세스 안에서는 6084ms 로 임계값(6000ms)을 넘긴다"고 적는다. 기능 게이트는 `-m "not benchmark"` 로 제외하고 전용 게이트가 선별한다. 단독 실행하면 **2.65s 로 pass** | 아니오 — 내가 `-m` 없이 돌린 탓 |
| `test_cr14_fence_movement_detection.py` 2건 | 울타리 이동 탐지기: 선언된 후보 뒤에 **코드 스코프를 건드린 커밋이 없어야 한다**. 지금 작업 트리는 `src/` 를 고쳤으므로 당연히 빨간색. 후보 재선언(CR-14 레인)의 일이다 | 아니오(설계된 동작) |
| `test_nx07_doc_consistency.py::test_soak_phases_stay_separated` · `::test_teeth_soak_done_promotion_is_detected` | **이미 커밋된 트리에서도 위반**이다. `git show HEAD:` 로 두 문서를 꺼내 판정 함수를 돌렸더니 같은 위반이 나온다. 원인: `docs/ga/CR14_EX_EXECUTION_LEDGER.md` 의 EX-05 행이 `**PASS** (resoake Decision A)` 인데, 그 실행의 **귀속(④)은 UNVERIFIED** 다 — NX-07 계약은 이 단계를 한 값으로 뭉개는 것을 금지한다 | 아니오 — **교차 레인** |

**그래서 결론**: 이 수정이 만든 새 실패는 **0건**이다. 대화 저장소 계약 79건은 전부 통과하고(새 계약 2건 포함),
문서 검사기는 ALL OK(링크 134개)다.

**교차 레인 항목 하나를 증거와 함께 올린다(고치지는 않는다).** `EX-05` 행의 상태 셀은 카드의 규칙
(“지표만 통과한 상태를 soak PASS 로 승격하지 않는다”)에 따라 `PASS(JSON 지표) · INCONCLUSIVE(귀속 미확정)`
처럼 두 단계를 분리해 적어야 한다. 지금은 한 단어 `PASS` 이고, 그래서 NX-07 계약이 빨간색이다.
이 대장은 CR-14 레인의 문서이므로 여기서 문장을 바꾸지 않는다 — 근거는 이 표와 §4 이다.

**새 지문**: 수정 뒤 작업 트리 지문은 `792a7d5d…` 이다(soak 이 시작될 때의 `322b4d3b…` 와 다르다 —
당연하다). 다음 측정(게이트 23개·8시간 soak)은 이 지문에서 해야 한다.

## 6. 다음 단계 (순서 고정)

1. **판정 기록 먼저** — 완료: `GATE_LEDGER.md` §16 회수 행 + 이 문서 + `handoff` §10.
2. **결함 수정** — 완료(§5c): `ConversationJournal.tail()` 이 꼬리 창만 읽는다. append 1회에 `tail()` 이
   3번 불리는 구조는 **그대로 두었다** — 각 호출이 O(꼬리)가 되어 합계가 1 ms 미만이고(실측 0.5~0.8 ms),
   프로세스 단위 캐시를 넣으면 stale `seq` 위험을 새로 만든다. 값이 아니라 **읽는 범위**를 고치는 것이
   이 결함의 본질이다.
3. **계약 시험으로 고정** — 완료(§5c): 창 경계 · 전체 스캔 동등성 2건. 수정 전 구현을 주입해
   시험이 실제로 빨개지는 것까지 확인했다.
4. **재측정** — 60초 · **10분** 완료(§5c, 평탄부 확인). 남은 것: 커밋 → 게이트 23개 재실행 →
   **8시간 soak 재실행**(이번에는 preflight 에 처리량 하한을 넣고, 시작 5분 안에 비정상이면 중단).
   수정된 코드에서 8시간은 **1,290만 ops 규모**가 되므로, 그 실행은 종전과 다른 크기를 잰다.
5. **preflight 에 처리량 하한 추가** — 이번 실행의 교훈(§5b). 시작 5분 동안 측정한 ops/s 가 기대
   하한의 1% 수준이면 8시간을 태우지 않고 중단한다.

## 7. 이 문서가 주장하지 않는 것

- 후보를 **GO 로 만들지 않는다**: required 23개 중 `python-tests` 4건(타 레인)이 여전히 red 이고
  이 실행의 FAIL 도 남는다.
- 메모리 원인을 “확정적 단일 원인”으로 못 박지 않는다: 다만 이 문서가 제시한 모델
  (“journal 크기에 비례하는 일시 할당이 흔적을 남긴다”)은 수정 뒤 10분 실행에서 기울기가 **0.004 KB/op
  로 평탄해지고** 8시간 외삽이 과거 다른 후보의 실적과 일치한 것으로 **교차 검증됐다**(§5c).
  그래도 "1.68 GB 의 100% 가 이 하나였다"고 주장하지 않는다 — 크기가 다른 두 실행(8시간/10분)을
  직접 비교하는 것이 아니라 기울기로 모델을 세운 것이다.
- 이 수정을 **후보 PASS**로 승격하지 않는다: 수정된 코드로 게이트 23개를 다시 재지 않았고,
  `python-tests` 4건(타 레인)도 그대로다. 다음 회차의 일이다.
