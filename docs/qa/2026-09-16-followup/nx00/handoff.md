---
title: NX-00 기준선 봉인 및 soak 증거 완결성 — 인계
created: 2026-09-16
state: REVIEW (지표 재확인 DONE / 종료·후보 귀속 INCONCLUSIVE)
baseline_sha: ffb0ebb312b76d86742d3e4065628a9704f8268e
tags: [nx-00, evidence, soak, exit-141, handoff]
---

# NX-00 인계 기록

```text
Task ID / attempt: NX-00 / attempt-001
Owner / reviewer: Buffy(작업 에이전트) / 미지정 (독립 검토자 필요)
State: REVIEW — 지표 독립 재확인 DONE, wrapper 종료141·후보 귀속은 INCONCLUSIVE
Baseline full SHA / code fingerprint: ffb0ebb312b76d86742d3e4065628a9704f8268e (작업 시작·종료 동일)
Dirty paths (secret contents excluded): vault_data(기존), data/auth_hash.bak.pre-0000(기존, 내용 미열람),
  docs/18·19, docs/qa/2026-09-16-followup/**, src/antigravity_k/engine/{conversation_store,context_summary}.py,
  src/antigravity_k/engine/summary_memory.py(신규), tests/test_nx01_compaction_retention.py
Scope / files / symbols: 스크립트 `docs/qa/2026-09-16-followup/nx00/verify_soak_artifact.py`;
  원본 soak artifact 4종 + pid 파일. 제품 코드 변경 없음.
Preconditions / dependency evidence: `.omo/evidence/commercial-reliability/CR-14/ex-2026-09-15/soak/` 원본 보존,
  `docs/ga/CR14_EX_EXECUTION_LEDGER.md` EX-05 resoake 항목.
Observed failure before / exact reproduction: [before.md](before.md) 참조 — wrapper 로그 종료141 + stdout 절단.
Change and invariant: 제품/런타임 미변경. 증거만 추가. 임계값 rss_leak_mb=64 불변.
Commands / cwd / exit codes / environment: [commands.txt](commands.txt) — 모두 exit 0, 원본 쓰기 없음.
Runtime expected vs observed: 지표 PASS / 프로세스 자체 exit code 미확정(141 = 128+13 SIGPIPE).
Regression results / raw log paths / hashes: [independent-parse.txt](independent-parse.txt),
  [artifact-hashes.txt](artifact-hashes.txt), [log-prefix-check.txt](log-prefix-check.txt), [after.md](after.md).
Data migration / backup / rollback observed: 해당 없음(읽기 전용). rollback 불필요.
Unverified / reason / impact: wrapper 종료141의 실행 명령 원문, run 당시 코드 후보 귀속.
  저장소에 래퍼 스크립트가 남아 있지 않다(`finished exit` 문자열은 계획/기준 문서에만 존재).
  영향: 기존 run을 정상 exit로 승격할 수 없고 NX-10에서 재실행이 필요하다.
Reviewer verdict / reviewed SHA / artifact: 미지정 — REVIEW 상태.
Next owner / exact next action: 다음 NX-00 담당자는 원인 확정을 시도하지 말고
  (1) NX-00-F01 harness 계약을 구현할지 결정하고, (2) NX-10에서 stdout 파일 리다이렉트 + exit code 별도 보존으로 재실행한다.
```

## 1. 지표 독립 재확인 (DONE)

`soak-summary.json`(이전 작성자가 만든 요약)을 신뢰하지 않고 원본 JSON을 직접 파싱했다.

| 항목 | 원본에서 재계산 | 판정 |
|---|---|---|
| artifact sha256 | `741d64e31bf0df7251b51104108d7178ddedf538a50fafa164d23007cd6c948f` | 이전 요약과 동일 |
| 크기/파싱 | 6,244,278 bytes / 484,210줄, JSON 파싱 성공 | OK |
| thresholds | `p95 500 / p99 1000 / error_rate 0 / fd_leak 5 / rss_leak 64` | 동결값과 동일, 완화 없음 |
| 시나리오 | SC-1~SC-6 모두 존재·`pass: true`, `missing_required: []`, `all_pass: true` | PASS |
| SC-6 시간 | `duration_s = actual_duration_s = 28,801.318` (요청 28,800) | 28,800초 이상 |
| append/revision | `conversation_ops = conversation_revision = 12,102,886`, `conversation_append_equality: true` | 일치 |
| view 크기 | `conversation_message_count = 26` ≤ `conversation_soft_max = 64`, `messages_bounded: true` | bounded |
| RSS | 원본 sample 배열 242,057개에서 last−first = **48.7MB** = 선언 `rss_growth_mb` | 64MB 이하 |
| FD | sample 배열 242,057개에서 last−first = **0** | 누수 없음 |
| 기타 | `errors 0`, `orphan_worktrees 0`, `db_accessible_after true` | OK |

샘플 1개당 약 0.119초 간격(28,801.318 / 242,057)이라는 점도 확인했다. 이는 관측 밀도이며 종료 시각 증명이 아니다.

## 2. wrapper 종료 141 — 원인 분석 (부분 확정, 귀속은 INCONCLUSIVE)

확인된 사실:

1. **harness 계약** (`scripts/val02_staging.py`, `main()` 끝): `rendered = json.dumps(report)` → `--output` 경로에 **파일 먼저 기록** → `print(rendered)` → `return 0 if all_pass else 1`.
   즉 파일 완성과 stdout 출력은 순차이며, 파일은 stdout 출력 **이전에** 완성된다.
2. **로그 절단** ([log-prefix-check.txt](log-prefix-check.txt)): 래퍼 로그는 총 515줄(8,245 bytes)이고
   1행은 `starting 2026-09-15T15:08:33+09:00`, 마지막 행은 `finished exit:141`이다.
   로그 본문(2~514행)은 artifact JSON과 **정확히 동일한 접두부**이며 513번째 줄 `75.8,`에서 끊긴다.
   artifact는 484,210줄이므로 stdout 스트림의 **약 0.11%만** 소비된 뒤 절단됐다.
   (`rss_samples_mb` 배열은 242,057개 → 절단 지점의 75.8은 런 초반부 값이다.)
3. **종료값 해석**: 141 = 128 + 13 = SIGPIPE. `print(rendered)`가 6.2MB를 한 번에 쓰는 동안 stdout의 **읽는 쪽이 닫혀** 프로세스가 SIGPIPE로 종료됐다는 해석이 로그 절단 형태와 일치한다. 이때 `return 0`에는 도달하지 못했다.
4. **원문 명령 미확보**: 저장소 전체에서 `finished exit` 문자열은 계획(18)·기준(BASELINE) 문서에만 있고 래퍼 스크립트는 없다.
   `docs/ga/CR14_EX_EXECUTION_LEDGER.md`에는 CLI(`val02_staging.py --scenarios … --soak-seconds 28800`, workdir `run28800e`)와
   pid(`72699` shell + `72709`/`72711`, `pid_resoake.txt`)만 남아 있다. 파이프 연결(누가 stdout을 읽었는지)은 복구 불가다.

결론(수용 조건 준수):

- **지표 PASS와 프로세스 종료 증명을 분리한다.** artifact 지표는 위 §1에서 독립 재확인했고, 임계값도 완화되지 않았다.
- **정상 exit 0으로 소급하지 않는다.** 프로세스는 SIGPIPE로 종료되었고 종료 코드를 보존한 파일이 없다.
- **후보 귀속 미확인.** 실행 시점 SHA/코드 지문과 시작·종료 지문을 연결할 증거가 없다(`run_sha_binding: UNVERIFIED`).
- 따라서 NX-00의 종료·귀속 항목은 `INCONCLUSIVE`이며, NX-10에서 새 후보로 8시간 시험을 다시 수행한다.

## 3. generated_at / 시작 / 종료 시각 구분 (개선안 기록)

- `generated_at`은 `main()` 시작부에서 `time.gmtime()`으로 생성된다(코드 확인). **완료 시각이 아니다.**
- 로그 1행 `starting …`은 래퍼가 남긴 시작 시각(2026-09-15T15:08:33+09:00 = 06:08:33Z)이며 `generated_at`과 일치한다.
- **종료 시각을 기록하는 필드는 현재 artifact에 없다.** 파일 mtime(15일 23:08)은 harness가 아닌 다른 요인(복사·동기화·감시)으로도 바뀌므로 증거로 쓰지 않는다.

## 4. 후속 카드 제안 — NX-00-F01 (harness/래퍼 계약, 미구현)

계획 §3의 "stdout 전부 파일 리다이렉트 + 종료 코드 별도 보존" 계약을 도구 수준에서 강제하기 위한 제안이다.
**이번 작업에서는 구현하지 않았다**(NX-10이 사용하는 harness·CR-14 gate diff를 건드리지 않기 위함).

1. `scripts/val02_staging.py`: `started_at`(UTC) / `finished_at`(UTC)를 `generated_at`과 **별도 필드**로 기록.
2. 긴 실행은 `--output`만 신뢰하고 stdout에는 요약 1줄(예: `verdict=PASS all_pass=true …`)을 **먼저** 출력해 절단돼도 판정이 남게 한다.
3. 실행 래퍼는 stdout/stderr를 전부 파일로 리다이렉트하고(잘림 없는 파일), `$?`를 별도 작은 파일(`exit_code.txt`)에 기록한다. 파이프 마지막 명령의 종료값을 제품 종료값으로 쓰지 않는다.
4. 래퍼 스크립트 자체를 저장소에 커밋해 다음 시도의 명령 원문을 남긴다(이번 조사의 원문 소실을 반복하지 않는다).

## 5. 산출물

- [before.md](before.md) — 재현 조건/관측.
- [after.md](after.md) — 재확인 결과/변경 없음 명시.
- [commands.txt](commands.txt) — 실행한 명령과 exit code.
- [artifact-hashes.txt](artifact-hashes.txt) — 원본 4종 + pid + probe 해시.
- [independent-parse.txt](independent-parse.txt) — 원본 JSON 독립 파싱 출력.
- [log-prefix-check.txt](log-prefix-check.txt) — 로그 절단이 stdout 절단임을 보이는 검사 출력.
- [verify_soak_artifact.py](verify_soak_artifact.py) — 위 파싱을 재실행하는 스크립트(원본 읽기 전용).

`.omo/`는 `.gitignore`(117행) 대상이므로 접근 가능한 artifact는 이 `docs/qa/` 경로에 두었다.
