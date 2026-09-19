---
title: Ssak-Ai 현재 상태 (단일 요약)
created: 2026-09-16
status_owner: true
observed_head: ffb0ebb312b76d86742d3e4065628a9704f8268e
tags: [current-status, single-source, handoff, ga]
---

# 현재 상태 — 단일 요약

이 문서가 **"지금 무엇이 참인가"의 단일 소유자**다. 다른 문서(README · `docs/10`~`19` · `docs/ga/**`)는
이 문서를 가리키고 자기 범위와 날짜만 밝힌다. 그 문서들에 남은 "현재 상태 / 최신 판정" 배너는
**그 시점의 이력**이며 현재 상태가 아니다.

이 문서가 소유하지 **않는** 것: 값(후보 SHA · 코드 지문 · required gate 개수)은
[CR-14 판정 카드 §5](ga/CR14_FINAL_CANDIDATE_VERDICT.md)가 유일한 소유자다. 이 문서는 그 값을
복사하지 않고 **범위와 해석**만 말한다. 이 문서와 README 어디에도 값을 박지 않는다 — 값을 박으면
다음 기록 커밋이 그 파일을 고쳐 gate 지문을 옮긴다(attempt-013 에서 실제로 발생, F-22).

기준 HEAD: `ffb0ebb3` (2026-09-16 관측). 판정의 대상은 HEAD 가 아니라 **커밋된 후보**다.

## 1. 제품 접속 — 포트 세 역할을 구분한다

| 역할 | 기본값 | 정의 위치 | 성격 |
|---|---:|---|---|
| **제품 API 서버**(제품 기본값) | **8000** | `src/antigravity_k/config.py` `ServerConfig.port` | `agk serve` 를 인자 없이 띄웠을 때의 포트. `AGK_SERVER_PORT` 로 변경. 대시보드·`/health`·`/api/ready`·`/docs` 가 **같은 포트**다 |
| **대시보드 개발 서버**(Vite dev) | **5173** | `dashboard/vite.config.ts` | `make dev-dashboard` 전용. 제품 사용자 경로가 아니다(서버가 정적 자산을 서빙한다) |
| **패키징(Desktop/Electron)** | `SSAK_HOST_URL` 이 가리키는 주소 | `desktop/hostLifecycle.js` | 없으면 자식 프로세스로 `agk serve --host --port` 를 띄운다. 별도 제품 포트를 발명하지 않는다 |
| 레거시 `8400` | **기본값 아님** | — | Phase 6 커밋(`ddcf3599`)에서 8400 → 8000 기본값 정리. 문서에 남은 8400 은 오기다([운영 가이드 §실행/검증](09_OPERATION_GUIDE.md)) |

**8400 을 무조건 8000 으로 치환하지 않는 이유:** 예시 로컬 런타임 주소도 8000 을 쓴다
(`AGK_VLLM_API_BASE=http://127.0.0.1:8000/v1`, `docker run -p 8000:8000`). 즉 "8000" 은
**제품 서버**와 **사용자가 따로 띄우는 OpenAI 호환 런타임** 양쪽에 등장하는 값이고, 같은 호스트에서
겹치면 한쪽을 옮겨야 한다. 치환은 값이 아니라 **역할**을 보고 해야 한다.

새 사용자 접속: 서버를 띄우면 브라우저에서 그 포트를 열면 된다(같은 포트가 대시보드·API·문서를 모두 낸다).
PIN 이 설정된 배포에서는 첫 화면이 PIN 입력이다.

## 2. 판정·게이트 상태

- **마지막으로 커밋된 후보**: CR-14 attempt-040. 값(후보 SHA · 코드 지문 · required gate 인벤토리 23)은
  [판정 카드 §5](ga/CR14_FINAL_CANDIDATE_VERDICT.md)가 소유한다. 그 후보의 required gate 는 전 항목 통과했고
  **판정은 NO-GO** 다(사유는 §5).
- **이 후보 이후의 NX 작업은 커밋되지 않았다.** `src/**`·`tests/**`·`README.md` 의 NX-01~07 변경은
  작업 트리에만 있고 판정 카드의 코드 지문 **밖**이다. 따라서 "required gate 전 항목 PASS"는
  **현재 작업 트리에 대한 주장이 아니다.**
- `23/23`(required gate 인벤토리 기준) 은 이 저장소에서 **두 가지 뜻**으로 쓰여 왔다:
  1. CR-14 required gate **인벤토리** 23개 중 23개 통과(후보 귀속 — 판정 근거가 되려면 후보·지문이 붙어야 한다),
  2. 특정 테스트 파일 묶음의 **23건** 통과(게이트와 무관 — 판정 근거가 아니다).
  문맥(후보·지문·범위)이 없는 `23/23` 은 판정 근거로 쓰지 않는다.

## 3. 8시간 soak 경과 — 단계를 섞지 않는다

| 단계 | 시각 | 결과 | 상태 |
|---|---|---|---|
| ① 1차 8시간 | 2026-09-15 ~14:47 KST | SC-1~5 PASS · **SC-6 FAIL** — RSS `~66.8 → 1721.8 MB`(`rss_growth_mb=1654.9` ≫ 기준 `64`) · workload ~150,554 append · `errors=0` · `fd_growth=0` · 후보 `b6003205` | **FAIL**(기록 보존) |
| ② 교정 결정 A | 2026-09-15 | ConversationStore soft-max auto-compact 기본 64(`78012f4a`) · **임계값 64MB 는 올리지 않음** | 결정 |
| ③ 재soak | 2026-09-15 15:07 → ~23:08 KST | `duration_s=28801.318` · append `12,102,886` = revision `12,102,886` · 최종 view 26 (≤ soft max 64) · RSS `65.7 → 114.4`(+48.7) · `errors=0` · `fd_growth=0` · `orphan_worktrees=0` · SC-1~6 `all_pass: true` | **JSON 지표 PASS** |
| ④ 종료·귀속 | — | 래퍼 로그 마지막 줄 `finished exit:141`(원문 명령 미보존 → stdout 절단 가능성, INCONCLUSIVE) · **재soak 당시 코드 후보·시작/종료 지문 귀속 UNVERIFIED** | **미확정** |
| ⑥ 재실행 1차(꼬리 창 수정 뒤) | 2026-09-16T23:26:23Z(08:26 KST) → **00:13:54Z 중단**(09:13 KST) | 지문 `98855031…` = 당시 트리 = HEAD(후보 `7691ccc5`) · preflight 6/6 · **47분에 journal 452 MiB → 기본 hard cap 512 MiB 를 8분 뒤 넘긴다** → 넘기면 append 가 507 로 거절되고 하네스가 `errors` 로 세서 **설정 때문의 거짓 FAIL**(§3e) | **중단(도구가 8시간을 살렸다)** · `exit: 143` · 종료 지문 = 시작값 |
| ⑥ 재실행 2차(러너가 cap 명시) | 2026-09-17T00:15:16Z(09:15 KST) → **00:22:48Z 중단**(09:22 KST) | `retention_caps: soft=64MiB hard=8192MiB` 로 재시작했으나 **SC-3 이 제품 경합**을 잡고(§3f), 하네스의 `q.get()` 에 타임아웃이 없어 죽은 worker 하나가 실행 전체를 멈췄다 — 러너는 종료 시에만 리포트를 쓰므로 8시간이 **FAIL 이 아니라 결과 0** 이 될 참이었다 | **중단(결함 둘 노출)** · `exit: 143` · 종료 지문 = 시작값 |
| ⑦ 재실행 3차 | 2026-09-17T01:19:43Z(10:19 KST) → **02:24:15Z 중단**(11:24 KST) | 결함 둘 수정(`c522b256`: registry 최초 생성도 공유 lock 아래 · 고유 tmp 이름 · worker 무응답 상한 120초 → 오류 1건으로 계상) + 계약 시험 5건 → 필수 23개 재측정(`sc3fix001`: **22 passed · 1 failed · 0 not_run**, 시작 = 종료 = `5c90b637…`) → 그 지문에서 재시작 · preflight **7/7 OK**(처리량 451 ops/s · 쓰기량 투영 4,282 MiB < cap 8,192 MiB) · **SC-1~5 완주 · 오류 0**(어제 멈췄던 SC-3 경합 통과) · 회수 감시는 `harvest` 가 대기 중 | **중단(오너 지시)** — 경과 1h 04m 32s · `exit: 143` · 종료 지문 = 시작값(트리 불변). 승격이 `scripts/`·`tests/` 를 옮겨 지문을 바꾸므로 공존할 수 없다(대가 1시간 = 8시간의 13%) |
| ⑧ 재실행 4차(**현재**) | 2026-09-17T03:25:56Z(12:25 KST) → 종료 예정 `11:25:56Z`(**20:25 KST**) | **승격 본실행 완료** — 이동 4건 sha256 동일 · 승격 위치 **14 passed** · 커밋 `bde261dc` → 첫 재측정이 **새 실패를 드러냈다**: `python-basedpyright` 가 새로 빨개짐(승격 전에는 `docs/` 안이라 **정적 게이트가 보지 않았다** — 타입 오류 12건) → 수정 `5c979c0f` → 새 지문 재측정 `promote2c` **22 passed · 1 failed · 0 not_run**(basedpyright 초록) · 승격이 깬 문서 링크 1건을 `docs/` 만 고쳐 닫고 `promote2d` 에서 `python-tests` **5 failed · 6640 passed**(실패 5건은 직전과 시험 단위 동일 = 새 실패 0건 · 증가분 +14 = 승격한 계약 시험). 그 지문 `b6a74304…` = 현재 트리 = HEAD 트리에서 시작 · preflight **7/7 OK**(처리량 474 ops/s · 쓰기량 투영 < cap 8,192 MiB) · 195분 시점 감시 **정상**(journal 2,461 MiB · 605 ops/s · `rss_growth_mb` 37.8/64 · 창 밖 creep 2.93 B/회) · **SC-6 기준 정량 검토·재설계 제안** 완료([SC6_CRITERION_REVIEW.md](qa/2026-09-16-followup/nx10/SC6_CRITERION_REVIEW.md) · [대장 §25](qa/2026-09-16-followup/nx10/GATE_LEDGER.md)): 워밍업이 예산 15.2% · 창 1분은 판정을 모델에 매단다(분산 30.7%) · 30분 창 잡음 8.1 MB · 기준 64 MB 의 반복당 예산 여유 **0.77배** — 구현은 지문 대상이라 **동결 해제 뒤**, 오너 결정 3건(D-A/B/C) 대기 · **오너 지시로 SC-6 새 기준을 코드와 시험으로 고정**(배치 `SC6` — [PROMOTION_PLAN §1f](qa/2026-09-16-followup/nx10/PROMOTION_PLAN.md) · [대장 §26](qa/2026-09-16-followup/nx10/GATE_LEDGER.md)): 순수 함수 `sc6_warmup_window_s`·`sc6_rss_criterion` + 계약 시험 8건 + 가드 셋(동결·사전 이미지 고정·자동 롤백) · 미러 리허설 **ALL PASS 22건**(본 트리 쓰기 0건) · 적용은 **회수 → 3차 배치 → `SC6` → 게이트 → 새 8시간** 순서 · **오너 지시로 처리량 감소를 1급 판정 축으로 추가**(배치 `PERF` — [perf/THROUGHPUT_GATE_DESIGN.md](qa/2026-09-16-followup/nx10/perf/THROUGHPUT_GATE_DESIGN.md) · [대장 §29](qa/2026-09-16-followup/nx10/GATE_LEDGER.md)): 이 실행의 30분 블록 실측이 **벽시계 −26.5% · 효율 −5.0% · 이용률 −22.6%** 라 **벽시계 단독 판정은 건강한 실행을 정확히 27% 지점에서 빨갛게** 만든다 → `벽시계 = 효율 × 이용률` 로 분해해 제품/서비스/재실행을 가르고(허용 15% · 블록 9.6분 중앙값 · `load1/코어 > 0.5` 면 단정 안 함), RSS 축과의 **독립을 계약 시험 13건으로 고정**(오늘의 실측 실행을 “제품 회귀”라 부르지 않는 회귀 시험 포함 · 합계 **23 passed**) · 스모그가 찾은 문(**두 축 다 면제인데 `pass=True`**)을 `criteria_gate` 로 봉인 · **귀속 사다리**(오너 지시 2026-09-17): 게이트가 빨간 실행에서만 돌아 한 반복을 세 국면으로 쪼개 **어느 호출이 느려졌는지**를 좁힌다(`phase` 지목 · `spread` · `outside_phases` · 잡음이면 무지목 · 다음 칸 문장; 실측 단가 transition 980→1,000 µs · create 500 · append 760 · **Σ 국면 = 총량으로 정체식 성립** — [설계 §9](qa/2026-09-16-followup/nx10/perf/THROUGHPUT_GATE_DESIGN.md) · [대장 §30](qa/2026-09-16-followup/nx10/GATE_LEDGER.md)) · **사다리의 다음 칸**(오너 지시 2026-09-17): 지목된 국면 **안**을 창 단위 `cProfile` 로 열어 `function`(이름 지목)/`spread_within_phase`/`outside_functions`/`insufficient` 로 한 번 더 좁히고, 계측한 창의 반복은 **판정 계열에서 제외**(오버헤드 실측 1.57배)·계측기 프레임은 순위에서 제외한다고 밝힘 — 실제 하네스 프로브가 곧바로 답을 냄: `conversation.append` 1,223 µs 중 **`posix.fsync` 847 µs = 69%**(view 재작성 `posix.replace` 98 · `_io.open` 80 은 그 뒤) → 처방이 “직렬화 줄이기”가 아니라 **flush 정책·배치**([설계 §10](qa/2026-09-16-followup/nx10/perf/THROUGHPUT_GATE_DESIGN.md) · [대장 §31](qa/2026-09-16-followup/nx10/GATE_LEDGER.md)): **네 번째 칸**(오너 지시 2026-09-17): 지목된 함수를 **누가 부르고 반복당 몇 번** 부르는지 좁힌다 — `path`/`multi_path`/`insufficient`/`not_applicable` + `path_calls_per_iteration`·`path_callers_top`·`path_chain`; 경로와 빈도를 나눠 내는 이유는 **처방이 다르기 때문**(1회 → 그 호출 자체를 싸게 · 여러 번 → 호출을 합친다) · 자료는 `cProfile` 호출자 표(다만 `Profile.getstats()` 6번째 칸은 **callees**이고 호출자가 아니다 — `pstats.Stats` 를 거치고, 교체가 숫자를 안 바꿨는지 실측 확인) · 실측 `posix.fsync ← _fsync_fd ← _append_bytes ← append ← _commit_event` **반복당 1.00회** · 계약 시험 **47 passed** · 같이 밝혀진 것: 셋째 칸의 몫은 **디스크 상태에 따라 70배 흔든다**(1,930·27.5·27.9 µs) → 순위와 호출 횟수를 읽고 빈도 축을 결정적으로 본다 · **flush 배치 설계**(오너 지시 2026-09-17): `conversation.append` 의 fsync 를 어떻게 다룰 것인가 — 근거를 “69%”가 아니라 **개수**로 잡았다: fsync 곡선이 계단 함수라(더티 0 MB **22 µs** → 8 MB **341 µs**) 일감 크기와 무관한 **300~350 µs 고정세**이고, append 1회는 `tail()` **3.00회**·읽은 바이트 **116 KB**·`open` 5.00·**`fsync` 1.00(불변)**·view 재작성 8,021 B → 세 부품(**F1** 꼬리 3회→1회[계약 변화 **없음**] · **F2** view 스로틸[설계만] · **F3** sync 정책[**ADR §2 개정 필요**·설계만]) · F1 은 안전 논변(“기억의 수명 = 한 flock 임계 구역”) + 계약 시험 9건 + 가드(동결 exit 9·합성 순서 exit 6·사전 이미지 exit 8·자동 롤백 exit 5) · **`src/` 를 바꾸는 첫 배치라 적용이 맨 마지막**(지금 도는 4차 soak 의 지문 대상) · **F2 신선도 계약 결정·구현 완료**(오너 지시 2026-09-17 · 배치 `FLUSH2` — [fsync2/VIEW_FRESHNESS_CONTRACT.md](qa/2026-09-16-followup/nx10/fsync2/VIEW_FRESHNESS_CONTRACT.md) · [대장 §34](qa/2026-09-16-followup/nx10/GATE_LEDGER.md)): 계약 = **읽기는 한 순간도 늦추지 않는다**(신선도는 파일이 아니라 **반환값**의 성질 — 늦출 수 있는 것은 표시용 view 뿐) + 판정은 `mtime` 이 아니라 **시퀀스** + 창은 유한(기본 `immediate` = 현행) + 따라잡기에 **저널 전체 재생 금지** + 수렴점(`flush_views`) + 삭제는 안 되살아난다 — 계약 시험 **10건** · **조사가 실제 결함을 닫았다**(복원·동기화가 옛 view 를 새 mtime 으로 놓으면 읽기가 커밋된 턴 2개를 놓쳤다 — 실측) · 순진한 미루기는 **회귀**(미룸당 재생 1.17회 — 8시간 soak 저널 크기에서 하루를 날렸던 부류)라 C-4 로 금지 · 이득 400턴 실측 **view 재작성 402→52회 · 다시 쓴 바이트 5.6→0.70 MB · 재생 0** · 미러 리허설 **ALL PASS 21/21** · 사전 이미지가 **F1 적용 뒤**라 순서가 해시로 강제(먼저 돌리면 exit 8) · 오너 결정 D-F1~F4 중 **D-F2 는 답함**(옵트인 — 켤 시점만 정하면 된다) · 오너 결정 D-F1·F3·F3′·F4 대기 — **F3 sync 정책은 ADR-DAT-02 §2 개정 초안까지 완료**(오너 지시 2026-09-17 · 배치 `FLUSH3` — [fsync3/ADR_DAT02_S2_AMENDMENT_DRAFT.md](qa/2026-09-16-followup/nx10/fsync3/ADR_DAT02_S2_AMENDMENT_DRAFT.md) · [대장 §35](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) · [계획 §1j](qa/2026-09-16-followup/nx10/PROMOTION_PLAN.md); ADR 본문엔 비규범 포인터 한 줄, Status 는 `Proposed` 그대로): 개정이 필요한 이유 = 현행 “durably committed” 는 **플랫폼이 보장하지 않는 약속**(macOS `os.fsync` 는 미디어 보장이 아니다) → 초안은 **등급 셋**(`process`/`cache`/`media`)·**유실 창 정의**(*가장 최근 성공한 sync 이후 커밋된 줄들만 사라질 수 있다 — 사라짐이지 뒤바뀜이 아니다*)·**관측**(`sync_policy`·`sync_level`·`sync_pending`·`last_sync_at` · 강등은 로그 1회, 조용한 강등 금지)·**플랫폼 표**(macOS `F_FULLFSYNC` · Linux `fdatasync` · 모르면 `media` 요구 거부) + 바뀌지 않는 것(순서·미결 꼬리·재생 결정성·기본 동작 불변) — 실측이 방향을 바꿨다: 같은 파일 2,000 커밋에서 `cache`(`os.fsync`) **45.37 µs/커밋 = 예산의 2.74 %**(배치하면 9.82 µs = 0.59 %) vs `media`(`F_FULLFSYNC`) **4,008.13 µs = 242.5 %**(배치 k=8 도 31.9 %) ⇒ **배치로 얻을 것이 2 %p 뿐이고 진짜 미디어 보장은 핫패스 밖에만 있다** · 단발 `os.fsync` 44.2 µs vs `F_FULLFSYNC` 4,163 µs(94배) · 오너 결정 **D-F3-1~4**(기본 등급·`media` 단위·`batched` 여부·관측 위치 — 초안 §8) 대기 — **세 대안을 배치 셋으로 나눴다**(설계 §10 · 표 §10-1): `FLUSH`=F1(계약 불변 · 스테이징+리허설 **16/16** · 바로 적용 가능) · `FLUSH2`=F2 view 스로틸(훅 4 · 시험 후보 5 · 기본값 현행이라 무회귀) · `FLUSH3`=F3 sync 정책(**ADR-DAT-02 §2 개정 6문장이 선행물** · 훅·시험 후보 6[크래시 시뮬 포함] · 되돌림 노브 한 줄) · 리허설 재확인 2026-09-17T10:01Z **ALL PASS 16/16**(P6: 본 트리 `src/` 두 파일 sha256 전후 동일 = `a89dfd2d82cc…`·`7f3e4605da9d…`) ([설계](qa/2026-09-16-followup/nx10/fsync/FLUSH_BATCH_DESIGN.md) · [대장 §33](qa/2026-09-16-followup/nx10/GATE_LEDGER.md)) · 미러 리허설 **ALL PASS 17/17**(적용 전 이빨 · **합성 순서 exit 6** · 동결 exit 9 · 사전 이미지 exit 8 · 지문 불변 · **승격 위치 정적 검사** · **P2b 승격 위치 타입 오류 → exit 5 + 자동 롤백**) — 리허설이 잡은 두 번째 결함은 계약 시험이 `docs/` 안에 있는 동안 **정적 게이트 시야 밖**이라 `basedpyright` 오류 5건을 숨긴 것(승격하면 빨개지는 부류) · 계측기를 만들며 네 번 틀렸는데 프로브가 셋을 잡았다(창 이중 마감 · 단가 중복 누적 · `getstats()` [3]/[4] 반대로 읽음) → 계약 시험 ㉝(창 수 × 창 크기 = 계측 호출 수)·㉞(음성 대조군: 옛 규칙이면 창 40 → 3,776)로 고정 · **오너 결정 D-P1~3 대기** · **`media` 오프로드 비용 모델·간섭 실측**(오너 지시 2026-09-17 · **D-F3-2 결정지 채움** — [fsync4/MEDIA_OFFLOAD_COST_MODEL.md](qa/2026-09-16-followup/nx10/fsync4/MEDIA_OFFLOAD_COST_MODEL.md) · [대장 §36](qa/2026-09-16-followup/nx10/GATE_LEDGER.md)): 호출은 **부피 무관 배리어**(바닥값 4,383/4,216 µs 가 8.9 MB 에서도 67 %/59 % · 유휴 호출도 4.1 ms) → 주기 상각은 T=10 s 에 예산의 **0.044 %** ⇒ **비용은 결정을 가르지 않는다**; 대신 배경 호출이 **쓰는 쪽을 멈춘다**(200 ms 주기 중앙 −2.2~−27.4 % · 최대 **3.2 s 밀림** · 밀림이 **100 % 진행 중인 호출과 겹쳤고** 기준선에는 0건 · **다른 파일이어도 멈췄다**) ⇒ 답은 **대화별 옵트인 + 상한이 있는 정지 감지**(조용한 창 호출 4.0–4.1 ms · 강행 시 스톨 관측) · 계기·문서 계약 시험 **17 passed**(음성 대조군 둘: 워커의 `O_CREAT` 제거 시 · 문서 수치를 옛 값으로 되돌렸을 때 각각 정확히 그 하나가 빨개짐) | **실행 중** |
| ⑤ NX-10 재soak (새 후보 `fd16368c`) | 2026-09-16 21:13 → 09-17 05:13 KST | `duration_s 28800.075`(요청 100.0%) · append `70,430` · view 19 ≤ 64 · `errors 0` · fd 5→5 · `orphan_worktrees 0` · 원본 70,431건 전수 확인 · **`rss_growth_mb 1683.5` ≫ 64 → SC-6 FAIL** · start = end = 기대 지문 = `322b4d3b…` · **exit 1** | **FAIL(원인 측정)** |

요약 JSON 의 SHA256 과 sample 배열 요약(count/min/max/first/last)은
[soak 요약](qa/2026-09-16-followup/soak-summary.json)에 있고 원본은 수정하지 않았다.

**2026-09-17 회수 — NX-10 의 8시간 soak 은 FAIL 이고, 그 원인이 측정됐다.** `scripts/collect_soak_result.py`
판정(2026-09-16T22:09:18Z): ① 지표 · ② 실행 두 항목 미충족이며 **둘 다 하나의 원인**이다 — SC-6 의
`rss_growth_mb 1683.5`(기준 64). 귀속은 성립한다: start = end = 예약 기대값 = 현재 트리 = `322b4d3b…`.
원인은 `ConversationStore.append()` 1회가 `journal.tail()` 을 **3회** 부르고, 그 `tail()` 이 마지막 줄만
필요한데 journal **전체를 읽고 모든 줄을 파싱**한다는 것이다(8h 상태 실물: append 814ms 중 810ms).
객체 누수는 아니다 — 살아 있는 객체 수는 평탄하고 일시 할당 peak 52 MB ([상세](qa/2026-09-16-followup/nx10/SOAK_8H_FINDINGS.md) ·
[nx10/GATE_LEDGER.md §16](qa/2026-09-16-followup/nx10/GATE_LEDGER.md)). 상세 기록은 `nx10/soak-exit.txt`(러너 블록: `start_head` ·
`start_fingerprint`) 가 소유한다. **이 판정 뒤에는 코드를 고칠 수 있다** — 회수 기록(판정 JSON)이 이미 쓰였으므로
“지금 트리 == 시작 지문”이 깨져도 이 FAIL 의 증거는 남는다.

**수정도 끝났다(같은 날)**: `ConversationJournal.tail()` 이 journal 전체 대신 꼬리 창만 읽는다.
실물 8시간 journal 에서 `append()` 814~830 ms → **0.5~0.8 ms**, 10분 재측정은 ops `269,087`(448.5 ops/s) ·
journal 94.1 MB · `rss_growth_mb` **32.2** 로 `pass: true`, 기울기 평탄부 0.004 KB/op → 8시간 외삽
**+48 MB < 64**. 같은 실행에서 NX-04 의 `stream_line_count` 가 처음 돌아 통과했다.
**거짓으로 보고하지 않기 위해**: ⑤ 는 여전히 FAIL 이다 — 고침은 “원인이 사라졌다”는 뜻이고,
새 지문에서 게이트 23개와 8시간을 다시 재기 전까지 “이김”이 아니다.

**그 3차 실행은 오너 지시로 1시간 4분에 중단하고(⑦) 승격을 즉시 실행했다 — 그리고 승격의 첫 재측정이
“숨은 타입 오류 12건”을 드러냈다(⑧)**: 승격 전에는 그 두 파일이 `docs/` 안이라 `python-basedpyright` 가
**보지 않았다**. 승격은 파일을 옮기는 일이 아니라 **검사 대상으로 편입**시키는 일이고, 그 편입이 곧 첫 검사다 —
타입을 고쳐(`5c979c0f`) 새 지문 `b6a74304…` 에서 다시 재니 **22 passed · 1 failed · 0 not_run**(basedpyright 초록,
`clean-machine-runtime` passed)이고 승격 위치 계약 시험 14건이 통과 수에 그대로 더해졌다(6626 → 6640).
상세: [nx10/GATE_LEDGER.md §22](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) · [nx10/handoff.md §12](qa/2026-09-16-followup/nx10/handoff.md).

**수정 뒤 같은 지문에서 8시간을 다시 시작했고, 그 실행은 두 번 멈췄다 — 매번 이유가 달랐다(⑥, §3e·§3f)**:
1차는 `soak_control.sh run` 의 preflight **6/6**(처리량 하한 포함)으로 시작했지만 **47분에 중단**했다 —
꼬리 창 수정으로 append 가 20배 빨라져 journal 이 **160 KB/s**(452 MiB/47분)로 자라 **기본 hard cap
512 MiB 를 8분 뒤 넘기고**, 넘긴 뒤의 507 이 하네스에서 `errors` 로 세어져 **설정 때문의 거짓 FAIL** 이
될 참이었다. 2차는 `retention_caps: soft=64MiB hard=8192MiB` 로 재시작했으나 **7분에 멈췄다**: SC-3 이
`ProjectRegistry` 의 **최초 생성 경로가 공유 lock 밖**이고 백업 회전 tmp 이름이 고정인 **제품 경합**을
잡았고, 하네스의 `q.get()` 에 타임아웃이 없어 **죽은 worker 하나가 실행 전체를 영원히 붙잡았다**(그대로
두면 8시간이 결과 0). 둘 다 고쳐 커밋 `c522b256`(계약 시험 5건) 뒤 **필수 23개를 재측정**(`sc3fix001`:
22 passed · 1 failed · 0 not_run, 시작 = 종료 = `5c90b637…` = HEAD 트리, 새 실패 0건)하고 **같은 지문에서
3차를 시작했다**(`01:19:43Z` → preflight 7/7 · SC-1~5 완주 · 오류 0). 그 3차는 **오너 지시로 1시간 4분에 중단**하고
(⑦ — 승격이 지문을 바꾸므로 공존할 수 없다) **승격 → 커밋 → 재측정 → 재장전** 순서를 밟아 **4차를 새 지문
`b6a74304…` 에서 시작**했다(⑧ · `03:25:56Z` → 종료 예정 `11:25:56Z` = **20:25 KST**).
직전 FAIL 리포트는 `soak-28800-fail001.json` 으로 보존했고, 회수 판정은 `harvest` 가 한다 — **그 전까지
⑤ 는 FAIL, ⑧ 은 “실행 중”** 이다.

**새 지문에서의 재측정(2026-09-17, attempt `tailfix001`)**: 커밋 `7d8c25b5`(수정) · `099cfc8b`(문서)
뒤 **작업 트리 지문 = HEAD 트리 지문 = `98855031…`** 에서 필수 **23개를 전수 실행**해
**22 passed · 1 failed · 0 not_run**(`clean-machine-runtime` passed 43.0s). 마감 도구가 지적하는 것은
**하나** `required_red: python-tests` 이고, 그 5건의 실패는 직전 attempt 와 **시험 단위로 동일**하다
(CR-14 울타리 3 — 선언 후보 뒤에 코드 커밋이 있으면 설계상 빨간색 · NX-07 문서 정합성 2 — EX-05 대장 행의
두 단계 뭉개기). **새 실패 0건 · 판정은 여전히 NO-GO.**

**그래서 "8시간 soak PASS"는 JSON 지표 기준이며, ④ 가 닫히기 전에는 게이트 PASS 로 승격하지 않는다.**
종료 원문은 복구 불가로 종결하고 NX-10 의 새 후보 시험으로 대체한다(NX-00-F01). ⑤ 는 귀속까지 성립한
**측정된 FAIL** 이므로 ①~④ 와 성격이 다르다: 원인을 알았고 고칠 곳도 하나다.

## 4. 열려 있는 기술 TODO (사람 축과 별도로 존재한다)

**"기술 축은 모두 닫혔다"는 문장은 CR-14 후보 범위에서만 참이다.** 신뢰성·커넥톰 계획 범위에서는
아래가 열려 있다([체크리스트 진행 기록](19_RELIABILITY_AND_CONNECTOME_CHECKLIST.md)이 카드 상태의 단일 원본):

- NX-00: 종료·귀속 INCONCLUSIVE (지표 재확인은 DONE) · **NX-00-F01** harness started/finished + exit 보존 결정
- NX-01·NX-02·NX-03·NX-04·NX-05·NX-06·NX-08: 구현·시험 green **REVIEW** — 독립 검토자 미지정, NX-02 는 ADR 승인자 미지정
- **NX-03 rollback 리허설 완료**(2026-09-17, 동결 중 `docs/` 만 수정): 구버전 판(`d929da01^`)을 그림자 트리로 돌려 ① 구버전끼리는 삭제 뒤 낡은 저장이 **되살아난다**(표식 0개) ② **현재가 삭제한 뒤에도 구버전은 그 세션을 다시 쓴다**(표식은 살아남음) ③ **복귀하면 현재 코드가 거절한다** — 되살아난 본문은 읽기 표면에 안 나오고 삭제된 id 도 새 id 로 대체된다([nx03/handoff.md §5b](qa/2026-09-16-followup/nx03/handoff.md)). 자동 회귀 금지는 유지하되 근거를 “되돌리면 영구히 살아낸다” → **“위험은 되돌림 창 안에서의 노출”** 로 정정했다.
- **NX-02-F01**: 세션 저장소가 prompt view 로 오염되는 경로 수정 여부 결정
- **NX-01 restore 리허설 완료**(2026-09-17, 동결 중 `docs/` 만 수정): 제품에 import/restore API 가 없어 복구는 **파일 수준**이고 안전성은 절차가 책임진다 — 절차용 판정부를 만들고 4개 경계를 임시 저장소에서 실측(왕복·**최신 변경 손실 방지**(대상이 더 새로우면 거절)·멱등·삭제 거절, exit 0). 이빨 확인: 가드를 끄면 revision 8→5 로 되돌아가며 원문 3건이 사라진다([restore-rehearsal.md](qa/2026-09-16-followup/nx01/restore-rehearsal.md)). **남긴 발견 `NX03-RESTORE-MARKER`**: 삭제 표식은 상태 플래그에만 적용되고 원문 읽기 표면은 journal 의 `delete` 이벤트만 보므로, 삭제 전 바이트를 되돌리면 `deleted=true` 인데도 원문이 다시 읽힌다 — 동결 중이라 코드는 안 고치고 절차가 거절한다(수리안·승격 예정은 같은 문서 §2·§3).
- NX-06: 정적 REVIEW / **런타임 BLOCKED**(cluster 없음 — Pod readiness·EndpointSlice 미관측) · `degraded→200` 정책 승인 필요
- **NX-09**(2026-09-16, REVIEW): 실 UI 동선 — ~~**F04**(커밋된 `dashboard_dist` 가 소스보다 낡아 **서빙되는 SPA ≠ 소스**)~~ → **NX-10 에서 닫힘**(번들 재생성 후 UI 증인 30/30 passed · 동결 직전 `pnpm build` 를 절차로 고정)
  (NX-09-F06 은 재측정으로 **결함 아님** — 한 창 측정 아티팩트였고, 두 창 증인 T8 이 `sessions_revoked: 1`·close 571ms 로 계약을 고정한다)
  (NX-09-F03 첨부 이미지 미전달은 **수정** — [ADR-0005](adr/0005-multimodal-attachments.md) · 증인 T4 가 provider 본문의 PNG 바이트와 "그 턴에만" 정책을 고정한다. 잔여: 이전 턴 이미지 재전송, 압축과 첨부의 상호작용)
- NX-01 이 넘긴 **cue lexicon 회수율** — **어휘 성능은 실측**(2026-09-16, 합성 코퍼스 + 실제 경로: 사전 표현 9/10 · 사전 밖 0/12 · 잡담 승격 6/7 · 경로 피해 3건 — [cue-lexicon-measurement.md](qa/2026-09-16-followup/nx01/cue-lexicon-measurement.md)). **실사용 회수율은 미실시**(라벨 코퍼스 필요) — 소유자 재지정 필요(별도 카드).
- NX-02 가 넘긴 **손상 대화 격리·폐기 운영 절차**는 NX-09 가 가져가지 않았으나, NX-10 창에서 **문서화 + 프로브 + 실데이터 사본 리허설까지 마감**했다 — 남은 것은 소유자 지정과 정책 선택(제품 flag·보존 기간).
- NX-08 잔여: **F2**(다른 호스트가 남긴 vault lock 은 깨지지 않음 — filelock 동작, 단일 호스트 배포에서 미발생,
  공유 볼륨·다중 인스턴스 확장 시 정책 필요) · **F1**(NFS flock/fsync 미실측) · **G1**(tombstone GC 정책 미결정, NX-03 후속)
- **NX-10**(2026-09-16, **REVIEW/NO-GO**): 후보 고정·필수 게이트 실행 — 필수 게이트 일부 green·일부 not_run 이고, **후보 SHA·지문과 게이트 수치는 §8 규칙에 따라 여기에 쓰지 않는다**(값 소유자: [nx10/GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) · 판정·미해결: [nx10/handoff.md](qa/2026-09-16-followup/nx10/handoff.md)).
  이 attempt 가 실제로 고친 것: 순환 임포트 6건(`engine/atomic_write.py`·`security/ws_registry.py` leaf 신설 + 패키지 루트 임포트 제거) · 중복 cast 7건 · bandit B324 1건 ·
  기준선에서도 실패하던 `network_access_api` 타입 2건 · **낡은 커밋 번들 재생성**. 동작 변경 0줄(seam 시험 192 passed).
  전용 창에서 전량 스위트·벤치·master-e2e·ambient E2E 를 실행해 대장을 마감했다(전량 스위트에서 **실패 4건**이 드러났고, 넷 다 다른 레인의 커밋에 귀속된다 — 커밋된 트리만 비교하는 계약 테스트다).
SC-1~6 8시간 soak 1차 실행은 **중단했다**(오너 판정): 19분 51초 경과 시점(`2026-09-16T07:41:42Z`)에 SIGTERM 으로 끊었고, 러너가 `exit: 143` 을 기록하는지까지 확인했다(중단 사유·방법·경과는 `nx10/soak-exit.txt` 에 러너 기록과 **구분해서** 남겼다 — 상세는 [nx10/GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) §10). 동결 배치 뒤에는 오너 지시로 **오늘 22:00 KST 예약 실행**으로 옮겼고(`schedule_nx10_soak.sh`, 목표 `2026-09-16T13:00:00Z`, 종료 예정 `~06:00 KST`), 보조도구 승격으로 지문이 이동해 **그 예약을 취소하고 새 지문으로 재장전**했다(취소 이유·시각은 `nx10/soak-exit.txt`, 현재 기대 지문·대기는 `nx10/soak-schedule.txt` 가 소유 — §8 규칙대로 여기 값은 쓰지 않는다). 예약 실행기는 시작 직전 지문을 확인해 동결 트리가 아니면 **8시간을 쓰지 않고 중단**한다. 2차 즉시 실행(08:15:38Z)은 예약으로 옮기며 3분 39초에 중단됐다 — 그때까지 코드를 건드리지 않는다.
사유: **후보 코드를 더 고치기로 했으므로**(SSE 실연결 폐기 · journal quota/retention · tombstone GC) 이 실행의 종료 지문이 최종 후보와 달라져 “시작/종료 지문 동일”을 만족할 수 없고, 러너는 종료 시에만 리포트를 쓰므로 중단 시점에 남는 판정 근거가 없다.
대신 순서를 바꿨다: **코드 배치 → 동결 → 8시간 soak 1회 → 게이트 재측정**. soak 과 나란히 돌릴 수 있는 문서·결정 작업은 그 soak 창으로 옮겼다.
필수 게이트 23개를 **전부 실행**했다(배치 이전 트리: 22 passed · 1 failed · **0 not_run**; 동결 지문 `157311cf…` 에서 **22개 중 21 passed · 1 failed**(`gate-report-freeze002.json`, `clean-machine-runtime` 은 커밋 전제라 제외) — `ga_gate_verify` 가 지적하는 문제는 정확히 `missing_required: clean-machine-runtime` · `required_red: python-tests` 둘). `clean-machine-runtime` 은 SCOPE 의 `BLOCKED_EXTERNAL` 이 사실오류였음이 드러나 실행해 통과했고(`--ref HEAD` 특성상 그 green 은 HEAD 의 것 — 커밋 뒤 후보 값), 실패 1개는 타 레인 계약 충돌 4건이다. **커밋해도 그 4건은 초록이 되지 않는다**(CR-14 울타리 이동·EX-05 승격은 타 레인/오너의 일이고, 우리 커밋은 HEAD 를 선언된 후보에서 더 멀어진다) — 마감 순서는 [nx10/CLOSURE_RUNBOOK.md](qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md) 가 소유한다.
  **2026-09-16 갱신(커밋 뒤):** 오너 지시로 **3분할 커밋 완료**(코드+계약 / 대시보드·번들·SBOM / 증거·문서 — SHA 와 스테이징 방식은 [nx10/CLOSURE_RUNBOOK.md](qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md) §3.1b)했고, 커밋된 후보에서 필수 **23개를 완주**(22 passed · 1 failed · 0 not_run)해 **`clean-machine-runtime` 이 처음으로 후보 값**이 됐다(passed, 43.7s). 그 결과 마감 도구가 지적하는 문제는 **`required_red: python-tests` 하나**로 줄었다. 지문이 이동했으므로(커밋도 지문을 옮길 수 있다 — [§3.1](qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md)) 예약 soak 을 그 지문으로 재장전했다.
  **미해결:** soak 결과와 지문 일치 확인 · 타 레인 실패 4건 정리(CR-14 후보 재선언 · EX-05 승격 판정) · 독립 검토자·owner 허용 기록 · `vault_data`(gitlink·소유 불명) 미커밋 유지 · 1MB 초과 게이트 리포트 4개는 정책상 미커밋(sha256 매니페스트만 커밋).
  **손상 대화 격리·폐기 절차**는 문서화·프로브까지 끝냈다(2026-09-16): 제품은 읽기·삭제 모두 fail-closed 라 삭제도 거절되고, 운영자는 파일을 **저장소 루트 밖**으로 보존 이동 + 삭제 표식으로 처리한다(루트 안에 두면 마이그레이션 **표식 없는** 저장소에서 `legacy_requires_migration` 으로 무관한 대화까지 실패 — 실측 A; 표식이 있으면 견딤 — 실측 B). **실데이터 사본 리허설까지 완료**(migration 3단계 + 격리 절차, 원본 해시 불변) — [nx02/damaged-conversation-disposal.md](qa/2026-09-16-followup/nx02/damaged-conversation-disposal.md).
- **NX-10 동결 배치**(2026-09-16, 오너 판정 — soak 중단 사유이기도 하다): 후보에 닿는 남은 코드·정책을 한 배치로 마감했다. ① **NX-05 SSE 실연결 폐기 구현**(`api/sse_revocation.py` + `server.py` 배선 — 실서버 관측에서 세대 변경 1.112초 뒤 `session.revoked`+EOF, before 는 9프레임 계속 흐름) ② **NX-02 journal retention 기본값 결정·구현**(대화당 soft 64 MiB 경고 / hard 512 MiB 쓰기 거절 507, **자동 prune 없음**, `store_usage()` 관측) ③ **NX-03 tombstone GC 정책·구현**(자동 만료 없음, 운영자 명시 회수를 아카이브 이동으로, 감사 JSON). 지문이 이동했으므로 `c65fe0e1…` 의 값은 더 이상 후보의 것이 아니다 — 새 지문·게이트·soak 값은 [nx10/BATCH_FREEZE.md](qa/2026-09-16-followup/nx10/BATCH_FREEZE.md) 와 [GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) 가 소유한다.
- **보조도구 승격 완료**(NX-10 창, 2026-09-16T09:46:05Z, 오너 판정 B): 검사기·판정기·프로브 3종과 계약 시험 3종을 `scripts/`·`tests/` 로 옮겨 이제 **정적 게이트와 스위트가 지킨다**(그 전에는 `docs/` 안이라 어느 게이트도 돌지 않았다). 지문이 이동했고 `.gitignore` 에 인증 해시 백업 규칙이 들어갔으며, **승격 뒤 필수 22개를 새 지문에서 다시 측정했다**(값은 §8 규칙대로 여기 쓰지 않는다 — 소유자: [nx10/BATCH_FREEZE.md](qa/2026-09-16-followup/nx10/BATCH_FREEZE.md) §4 · [nx10/promote-runner-exit.txt](qa/2026-09-16-followup/nx10/promote-runner-exit.txt) · `gate-report-promote002.json` · [nx10/GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) §13). 계획·이동표·실행 기록: [nx10/PROMOTION_PLAN.md](qa/2026-09-16-followup/nx10/PROMOTION_PLAN.md). 22:00 soak 은 **마지막 측정 뒤에** 새 지문으로 재장전됐다(`docs/` 만 추가 수정 중).
- **예약 통제 도구가 생겼다**(NX-10 창, 2026-09-16): soak 을 `soak_control.sh`(`arm`·`status`·`cancel`·`orphans`·`preflight`·`run`·`harvest`·`selftest`, 자기시험 **70/70**)로만 건다·회수한다.
  **2026-09-17 추가**: 발화 전 점검에 **쓰기량 투영 vs 보존 hard cap** 를 넣었다 — 꼬리 창 수정으로 append 가 20배 빨라져 8시간 soak 의 journal 이 기본 cap(512 MiB)을 50분에 넘기고, 넘긴 뒤의 507 은 하네스가 `errors` 로 세므로 **설정 때문의 거짓 FAIL** 이 된다(실측 452 MiB/47분으로 48분에 중단 → 러너가 `AGK_CONVERSATION_JOURNAL_HARD_CAP_MB=8192` 를 export·기록 → 같은 지문에서 재시작). 회수는 이제 `harvest` 가 “끝날 때까지 기다렸다가 판정기까지” 한다(아직 돌면 `exit 4` 로 거부 — 러너는 종료 시에만 `end_*`·`exit` 를 쓴다).
  **그 재시작도 7분에 멈췄고, 그 사고가 결함 둘을 드러냈다**(2026-09-17): SC-3 이 **제품 경합**을 잡았다 — `ProjectRegistry` 최초 생성이 공유 lock 밖이고 백업 회전 tmp 이름이 고정이라 동시 시작 프로세스가 `RegistrySaveError` 로 죽는다(대화 저장소에서 이미 고친 F1 과 같은 종류). 그리고 **하네스의 `q.get()` 에 타임아웃이 없어** 죽은 worker 하나가 실행 전체를 멈췄다 — 러너는 종료 시에만 리포트를 쓰므로 그대로 두면 8시간이 **FAIL 이 아니라 결과 0** 이 된다. 둘을 고쳐 커밋 `c522b256`(계약 시험 5건) → 필수 23개 재측정(**22 passed · 1 failed · 0 not_run**, 시작 = 종료 = `5c90b637…`, 새 실패 0건·통과 +5) → 그 지문에서 **8시간 실행 중**(`01:19:44Z` 시작 → 종료 예정 `09:19:43Z` = 18:19 KST). 회수용 `harvest` 에는 **무응답 상한**도 붙였다: 살아 있어도 30분간 아무것도 안 쓰면 `exit 6` 으로 알려 준다(그 모양이 이번 사고였다).
  `status` 는 모드를 가른다: 대기 중이면 “단일 예약 · 지문 일치”, **실행 중이면 `RUNNING` = 시작 지문 == 현재 트리**(종전에는 도는 soak 을 두고도 `ATTENTION` 을 냈다 — 실행 중에는 예약 잠금이 없기 때문; 2026-09-17 수정).
  `preflight` 는 발화 전에 ① 예약이 단일·유효한가 ② 지문이 **커밋된 후보**의 것인가(`현재 트리 == HEAD`)
  ③ 인터프리터·러너 자산 ④ `/tmp` 여유 ⑤ 이미 도는 soak 없음 — 을 한 화면에 모아, 실패를 **밤을 태우기 전에** 보여준다. 계기는 실측 사고다 — 직전에 "취소했다"고 기록한 예약 **3건이 실제로는 살아서 대기**하고 있었다(`screen -X quit` 은 화면만 닫고 `login -pflq` 래퍼가 SIGHUP 을 무시한다). 그대로 두면 22:00 에 4개가 동시에 깨어났을 것이다. 같은 점검에서 예약 스크립트의 지문 계산이 PATH 의 `python` 에 의존해(이 기기의 `/usr/bin/python3` 는 3.9 라 `ga_gate.py` 를 파싱하지 못한다) **8시간 창을 통째로 잃을 수 있었다**는 사실도 나와 `.venv/bin/python` 으로 고정하고 `UNVERIFIED` 를 드리프트보다 먼저 막게 했다. 소유자: [nx10/SOAK_SCHEDULING.md](qa/2026-09-16-followup/nx10/SOAK_SCHEDULING.md).
  같은 날 **세 번째 결함**도 이 창에서 잡았다: 회수 판정기(`scripts/collect_soak_result.py`)가 예약 기록에서
  **첫 번째**(철 지난) 기대 지문을 읽고 있어, 밤새 정상으로 끝난 8시간 실행이 귀속 검사에서 **거짓 FAIL**
  로 판정될 참이었다(실측: `기대=157311cf…` → 수정 뒤 마지막 예약). 판정기는 `scripts/` 라 그 수정이
  지문을 옮겼고, 그래서 오늘 soak 은 **커밋 뒤 필수 23개 재측정 → 재장전** 순서로 다시 세운다(값은 §8 규칙대로
  여기 쓰지 않는다).
- **승격이 자기 호출자를 고아로 만들었다 — 그리고 세션 재시작이 그 위에서 일어났다**(2026-09-18, 오너 지시 이어받기): 4차 실행 회수 뒤의 무인 체인은 `2026-09-17T12:19Z` 에 **커밋 직전**에서 멈춰 있었고(재부팅으로 화면 0건 · 승격 5건은 인덱스에 스테이징된 채 · 승격 위치 게이트 A·B·C 는 초록), 배치 체인은 **옳게** ②관문에서 쓰기 0건으로 멈춰 있었다. 이어받아 닫은 결함 셋: ① 승격은 `mv` 인데 **부르는 쪽이 안 옮겨졌다** — 체인 4개가 사라진 `docs/` 사본을 호출했고, 배치 체인이면 **네 배치를 전부 적용·커밋한 뒤 재장전에서** 터진다(고침 + 경로 실재성 계약 시험 7건 · 음성 대조군 3개) ② 승격이 파일을 `scripts/` 로 옮기면서 **필수 `python-basedpyright` 가 28 errors 로 빨개졌다**(`docs/` 안에서는 어느 게이트도 안 보던 코드) — 고침 + **승격 게이트 C 가 필수 게이트와 같은 명령을 승격 전에 돌리게** 함 ③ 체인 리허설이 **본 기록이 비어 있어야** 통과하는 검사를 갖고 있었다(실제 사고가 기록되자 정상을 오염으로 오판) — 내용 해시 비교 + 이빨로 교체. 커밋 `a1c6387f`(승격) · `8d762c3e`(호출자) · `22d653c9`(타입·승격 게이트) → 새 지문 `df512a17…` 에서 필수 23개 재측정 → **`SC6 → PERF → FLUSH → FLUSH2` 배치 체인**(배치마다 적용·커밋·게이트, 마지막에 새 8시간 soak 재장전)을 무인 예약. 소유자: [nx10/GATE_LEDGER.md](qa/2026-09-16-followup/nx10/GATE_LEDGER.md) §38 · [nx10/handoff.md](qa/2026-09-16-followup/nx10/handoff.md) §28 · [nx10/CLOSURE_RUNBOOK.md](qa/2026-09-16-followup/nx10/CLOSURE_RUNBOOK.md) §5d.
- NX-11: desktop 지원 확정 **BLOCKED**(사용자 pause)
- NX-12~NX-15: 선택 연구(커넥톰 baseline·평가 계약)
- CR-14 잔여 기술 항목: **C14-03**(전 구간 번들 시나리오) · **C14-04**(이전 artifact 업그레이드) ·
  **C14-05**(28,800초 + 실 provider) 미완

## 5. 사람·조직·외부 축 (기술 진행으로 닫히지 않는다)

| 항목 | 상태 |
|---|---|
| 출시 책임자 | **강병석** 배정(2026-09-14) — 근거 있는 **NO-GO** 기록([C14-08 판정](ga/CR14_C14_08_RELEASE_OWNER_VERDICT.md)) |
| 독립 code/security/QA 검토자 | **미배정** — 출시 책임자 **겸직**, 제3자 독립성 **미충족**(그 사실을 숨기지 않는다) |
| EX-01 실 provider | **PARTIAL** — 로컬 Ollama PASS · NVIDIA PASS · openrouter/free PASS · Gemini/ZAI/OpenRouter 유료 FAIL |
| EX-02 승인 | **PARTIAL** — 범위 문구 자체 승인 완료, legal **BLOCKED_EXTERNAL** |
| EX-03 이전 artifact | **DONE — NOT_AVAILABLE**(이전 릴리스 artifact 없음) |
| EX-04 지원 OS sandbox | **DONE**(macOS 26.6.2 arm64, seatbelt) — **행렬은 승격하지 않음** |
| EX-05 8시간 soak | §3 참조(JSON PASS / 종료·귀속 미확정) |
| EX-06 범위 축소 | **DONE — 축소 없음** |
| GA 승인 | **없음.** 이 저장소에서 GO 를 선언할 수 있는 주체는 출시 책임자뿐이다 |
| 오너 결정 요청 모음 | [GA owner decision packet](ga/GA_OWNER_DECISION_PACKET.md) — D1~D8 + **D-P1~P3**(성능 임계, §4) + **D-F3-1~4**(flush 정책, §5). 선택지·영향·권고·의존 순서. **값은 이 표가 소유하지 않고 소유 문서를 가리킨다** |
| 결정 시점 | **2026-09-18 오후 회수 결과를 본 뒤** 한자리에서 정한다(오너 지시: “모든 테스트가 완료되고 해당 결과를 보고 결정하자”) — 그때 필요한 숫자는 회수 요약이 한 장에 갖추고 있어야 한다(대장 §40+ · handoff §30) |

## 6. 지원 범위

분류와 근거의 소유자는 [GA 지원표](ga/GA_SUPPORT_MATRIX.md)다. 분류는 네 단계를 쓴다:
**Supported**(GA 지원 약속 — 현재 **0행**) · **Experimental**(구현/설정 근거는 있고 지원 약속은 없음) ·
**Unsupported**(범위 밖) · **Not evaluated**(관측·산출물은 있으나 판정하지 않음).

- 실험 행을 마케팅할 때는 "평가용으로 제공" 까지만 말할 수 있다 — supported/certified/production-ready 금지.
- **macOS DMG**: 로컬 작업 트리에 설치 가능한 산출물이 **있다**(`dist/Ssak-Ai-0.1.0.dmg`, 2026-09-15,
  sha256 로컬 검증 · `dmg-smoke` PASS). 그러나 **커밋되지 않았고**(`dist/` 는 gitignore), 서명·공증 검증,
  깨끗한 실기기 설치, 업데이트 피드·롤백 검증은 **미완**이다. 산출물의 존재와 검증 완료를 같은 것으로
  읽지 않는다 — 그 구분은 지원표의 `Not evaluated` 행이 소유한다.

## 7. 문서 지도 — 누가 무엇을 소유하는가

| 문서 | 소유 범위 | 현재 상태 표기 |
|---|---|---|
| **`docs/20_CURRENT_STATUS.md`** (이 문서) | **현재 상태 · 포트 역할 · soak 단계 · 열린 축** | 소유자 |
| `README.md` | 설치·실행·기능·환경 변수 | 이 문서를 **링크 한 줄**로 가리킨다(값 없음) |
| `docs/08_CHANGELOG.md` | 변경 이력 | 이력 |
| `docs/10_FINAL_READINESS_REPORT.md` | attempt 이력 · 최종 준비도 보고 | 이력(값은 판정 카드 §5) |
| `docs/11`~`13` | GA-100 계획·체크·진행 이력 | 이력 |
| `docs/14`~`15` | RP(최종 검토 개선) 이력 | 이력 |
| `docs/16`~`17` | CR(상용 신뢰성) 이력 · 값 소유자 표기 | 이력 |
| `docs/18`~`19` | **NX 개발계획 · 카드 상태의 단일 원본** | 카드 상태 |
| `docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md` | **후보 SHA · 코드 지문 · 게이트 인벤토리 값** | 이력(값 소유자) |
| `docs/ga/CR14_GATE_COVERAGE_BOUNDARY.md` | 게이트 커버리지 경계(무엇을 검증하지 않는가) | 경계 |
| `docs/ga/GA_SUPPORT_MATRIX.md` | 지원 분류 | 지원 상태 |
| `docs/ga/CR14_EX_EXECUTION_LEDGER.md` | 외부 조건(EX-01~06) 실행 대장 | 실행 상태 |
| `docs/09_OPERATION_GUIDE.md` · `deploy/README.md` | 운영 · 배포 | 운영 |
| `docs/packaging/**` | 데스크톱 패키징 이력(pause) | 이력 |

규칙: **현재 상태 배너는 이 문서가 소유한다.** 다른 문서는 배너를 새로 만들지 않고, 자기가 어느
범위의 이력인지 밝힌 뒤 이 문서를 가리킨다.

## 8. 갱신 규칙

1. 최종 수치(후보·지문·게이트 개수)는 NX-10 이후 **판정 카드 §5 에서 한 번만** 갱신한다.
   이 문서와 README 는 값을 복사하지 않는다.
2. 이 문서를 고칠 때는 §1(포트) · §3(soak) · §4(열린 축) 세 절이 서로 모순되지 않는지 확인한다.
3. 이 문서는 `docs/` 안에 있으므로 gate 코드 지문 **밖**이다 — 기록 커밋은 `docs/` 전용으로 유지한다.
