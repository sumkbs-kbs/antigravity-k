# NX-07 인계 — 문서·지원 범위의 단일 현재 상태

- 카드: [계획서 §4 NX-07](../../../18_RELIABILITY_AND_CONNECTOME_DEVELOPMENT_PLAN.md) · 상태: **REVIEW**(2026-09-16)
- 기준 HEAD: `ffb0ebb312b76d86742d3e4065628a9704f8268e` · **커밋하지 않았다**
- 증거: `before.md` · `after.md` · `before-scan.txt` · `runtime-access.txt` · `before-run-output.json` ·
  `after-run-output.json` · `commands.txt` · `regression.txt`
- 제품 코드 변경: **0줄**(문서·지원표·EX 대장 + 계약 시험 1파일 + 측정기 1파일)

## 1. 이 카드가 실제로 고친 것

카드의 수용 기준 넷 중 **셋은 문장이 아니라 관계**다. 그래서 문서를 고치는 데서 멈추지 않고
그 관계를 `tests/test_nx07_doc_consistency.py`(26 passed)로 고정했다.

| 수용 기준 | before | after | 계약 시험 |
|---|---|---|---|
| '남은 것은 사람뿐'과 실제 기술 TODO 가 동시에 현재 상태로 나타나지 않음 | README 가 "**기술 축은 모두 닫혔고** 남은 차단 사유는 사람의 영역"이라고 단정(열린 카드 12개) | "**이 후보 범위에서는**" 으로 한정 + NX 상태·미커밋 사실·`docs/20` §4 링크. 독립 검토자 "미배정"은 "겸직"으로 정정 | `human_axis_violations` — 열린 카드가 있는 동안 한정 없는 주장·범위 없는 사람 축 줄을 잡는다 |
| 지원표에 4분류와 근거가 있음 | `Not evaluated` 없음 · DMG 행이 "패키징 산출물 없음"이라는 **낡은 근거** | 4단계 어휘 + 데스크톱 행을 **범위(`Unsupported`, ADR-0003)** 와 **산출물(`Not evaluated`)** 로 분리 | `support_matrix_violations` |
| 새 고객이 README 대로 따라가면 맞는 화면 | README 가 **코드 기본값과 다른** 8400 안내(`--port`, 문서 주소, 환경변수 기본값) | 8000 으로 일치 + 세 포트 역할 구분 + 런타임 관측(`/`, `/health`, `/api/ready`, `/docs`, `/redoc` = 200) | `readme_port_violations`(포트를 `config.py`·`vite.config.ts` 에서 읽는다) |
| (카드 절차 3·4·5·7) `23/23` 범위 표기 · soak 단계 분리 · 문서 지도 | 문맥 없는 `23/23` 4줄 · soak 3단계/미확정을 한자리에서 보여 주는 문서 없음 | 4줄에 attempt·후보·지문·범위 부착 · `docs/20` §3 이 4단계로 분리 · EX 대장 EX-05 행 갱신 | `gate_count_context_violations` · `soak_phase_violations` |

## 2. 새 단일 소유자: `docs/20_CURRENT_STATUS.md`

이 저장소에는 이미 `docs/10`(210KB, attempt 배너 누적) · `docs/16`/`docs/17`(CR 상태) · `docs/11`~`15`
(GA-100·RP 이력)가 각자 "최신"을 들고 있었고, 그 중 `docs/16` 의 "최신(attempt-039)" 은 이미 틀렸다
(그 뒤에 attempt-040 이 있다). 그래서 **현재 사실만 담는 새 문서 하나**를 소유자로 세웠다:

- §1 포트 세 역할 · §2 판정·`23/23` 두 뜻 · §3 soak 4단계 · §4 열린 기술 TODO(12개) ·
  §5 사람·외부 축 · §6 지원 범위 · §7 문서 지도(누가 무엇을 소유하는가) · §8 갱신 규칙.
- **값은 복사하지 않는다.** 후보 SHA·코드 지문·게이트 인벤토리 수의 소유자는
  `docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md` §5 하나다(F-22 — 값을 박으면 다음 기록 커밋이
  그 파일을 고쳐 gate 지문을 옮긴다). 이 원칙은 `test_cr14_fingerprint_scope_contract.py` 가 계속 강제한다.
- README 는 이제 **링크 한 줄 + 포트 정합**만 갖는다. 값이 없으므로 NX-10 의 최종 수치 갱신이
  README 를 건드릴 필요가 없다(자기참조 루프 회피).

`docs/10`~`docs/19` 11곳에 소유자 링크를 넣었고, `docs/10`·`docs/16` 의 "최신" 배너는 **이력**으로
내렸다(과거 attempt 본문은 재작성하지 않았다 — 카드의 금지 사항).

## 3. 8400 → 8000 을 **무조건** 치환하지 않은 이유

카드 절차 6 은 포트를 역할별로 구분하라고 요구한다. 실제로 8000 은 **두 서비스가 같이 쓰는 값**이다:

- 제품 API 서버 기본값(`ServerConfig.port`) = 8000 — `agk serve` 는 `port or config.server.port` 로 고른다
  (`cli.py:100`).
- 예시 OpenAI 호환 로컬 런타임도 8000 이다(`AGK_VLLM_API_BASE=http://127.0.0.1:8000/v1`,
  `docker run -p 8000:8000`).

그래서 README 의 환경변수 절에는 **"같은 호스트에서 겹치면 한쪽을 옮긴다"** 는 경고를 넣고,
`docs/20` §1 표에 네 번째 행(레거시 8400)과 충돌 주의를 함께 뒀다. 대시보드 dev 서버는 5173,
패키징 셸은 `SSAK_HOST_URL`(없으면 자식으로 `agk serve --host --port`)이다.

## 4. 지원표에서 바꾼 것과 **바꾸지 않은 것**

- 산출물 행은 `Not evaluated` 다 — **`Supported` 로 승격하지 않았다**(승격은 소유자 승인 사항).
- DMG 사실(`dist/Ssak-Ai-0.1.0.dmg`, 85M, sha256, `dmg-smoke` PASS, bundled CPython 3.12.13)은
  `docs/packaging/notes/SESSION_CHECKPOINT_2026-09-15.md` 를 근거로 인용했고, **미완**을 같은 행에 적었다:
  codesign/notarization 검증 · 깨끗한 지원 macOS 실기기 설치 · 업데이트 피드/중단/rollback ·
  phone LAN·Tailscale smoke · Electron 셸→DMG.
- `dist/` 는 gitignore 이므로 **커밋된 산출물·SBOM·릴리스 피드가 없다**는 사실도 행에 적었다.
- 기존 계약(`test_cr12_docs_alignment.py::test_support_matrix_preserves_external_blockers`)이 요구하는
  `BLOCKED_EXTERNAL` 행 수·"No row below is supported" 문구·담당자 열은 그대로 유지했다.

## 4.5 NX-10 창의 2차 fact check (2026-09-16, 지원표 행 근거 재검증)

NX-07 이 “다른 행은 각 lane 담당” 으로 남겨 둔 부분을 NX-10 창에서 **코드·산출물 대조**로 한 번 더 확인했다
(분류는 바꾸지 않았다 — 근거만 검증·정정):

- **일치 확인**: 패키징 산출물 sha256(문서값과 동일)·`dist/` 무시·체크포인트 근거 / `mlx` extra + Darwin 전용 로더 /
  `config.yaml` 기본 ollama + README / `Dockerfile` + `deploy/k8s/*.yaml` / 클라우드 provider 6종 구성 /
  ADR-0003 의 데스크톱 비주장 문구.
- **정정 2건(동시 사용자 행)**: ① 인용된 `codex/val-02-resilience` 브랜치가 **없다**(커밋 `74271a94` 는
  `codex/m1-task-events`·`codex/rc-01-gate-done` 에 있음) ② 인용 수치의 **원본 아티팩트가 `docs/qa/**` 에 없다**
  — 인용 사슬임을 행에 명시해 게이트 근거로 승격하지 못하게 했다.
- **계약 시험이 내 편집을 잡았다(기록)**: fact-check 내용을 표로 적었더니 `|` 로 시작하는 줄에 산출물 파일명이
  들어가 `support_matrix_violations` 가 이를 “DMG 행” 으로 보고 실패했다(`_DMG_ROW_MARKER = "Ssak-Ai-0.1.0.dmg"`).
  표를 bullet 로 바꾸자 기준선(2 failed / 24 passed — 둘 다 EX-05 soak 승격)으로 복귀했다.
  **즉 이 계약은 문서 배치까지 검사한다** — 지원표에 행을 추가할 때는 `|` 시작 줄을 피해야 한다.
- `Supported` 행 0개·`last_fact_check` 값은 그대로다. 최종 문구 소유권은 여전히 NX-07/지원 담당 lane 에 있다.

## 5. 남긴 것 (다음 사람이 이어받을 자리)

- **독립 검토자 미지정** — 이 카드의 판정도 겸직 상태다. REVIEW 로만 올린다.
- `docs/20` 의 soak §3 ④(종료141·후보 귀속)는 **NX-00/NX-10 소관**이다. 이 카드는 문장만 정리했다.
- 지원표의 다른 행(macOS·Linux·provider)은 2026-09-06 근거를 그대로 두고 `last_fact_check: 2026-09-16`
  만 붙였다. 행별 재검증은 각 담당 lane(EX-01/EX-04)이다.
- NX-11(데스크톱)이 풀리면 지원표의 `Not evaluated` 행이 갱신 대상 1순위다.
- 전체 스위트의 실패 7건은 이 카드 이전부터 있던 것(커밋 이동 2 · 사용자 홈 레거시 데이터 5)이며
  `regression.txt` 에 근거를 적었다. **하나도 이번 변경으로 생기지 않았다.**
- **남은 문맥 없는 수치(의도적 미수정)**: `docs/16` 의 카드 상태 표에는 `required gate 20/20 PASS` 같은
  **과거 attempt 의 수치**가 본문에 남아 있다(이번 계약은 `23/23` 만 본다). 그 파일 상단은 이제 "이력"이고
  값을 소유한 문서를 가리키므로, 본문 재작성(카드 금지 사항) 대신 사실만 기록한다.
  `docs/08`·`docs/09`·`docs/02`·`docs/04`·`docs/project_diagnostic_report.md` 등 계획 범위 밖 문서의
  '최신' 표현도 같은 이유로 손대지 않았다 — 현재 상태 배너를 새로 만들지 않는다는 규칙으로 뚜는다.

## 6. 검토 시 확인할 것

1. `docs/20` §2 의 "**이 후보 이후의 NX 작업은 커밋되지 않았다**" 가 지금도 참인지
   (`git status`, `git log b6003205..HEAD`).
2. port 계약이 `config.py` 를 읽는지 — 문서에 값을 복사하지 않았는지.
3. 지원표의 `Not evaluated` 행이 **검증 완료로 읽히지 않는지**(미완 목록 유지).
4. README 가 휘발성 값(후보 SHA·게이트 수)을 다시 들여오지 않았는지
   (`test_cr14_fingerprint_scope_contract.py` 가 잡는다).
