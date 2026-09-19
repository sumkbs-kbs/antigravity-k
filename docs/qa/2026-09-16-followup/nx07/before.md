# NX-07 before — 문서·지원 범위가 하나의 현재 상태를 가리키지 않았다

- 측정일: 2026-09-16
- 기준 나무: `git archive HEAD` 추출본 (`/tmp/nx07-before`) — HEAD `ffb0ebb312b76d86742d3e4065628a9704f8268e`, **작업 트리 무변경**
- 측정기: `repro_nx07_doc_consistency.py --root /tmp/nx07-before --label before`
- 결과: **exit 3 · 8/8 checks FAIL** (`before-run-output.json`)
- 참고: `docs/18`·`docs/19` 는 HEAD 에 **없다**(미커밋). 그래서 "열린 카드" 조건은 작업 트리의 `docs/19` 를
  자(yardstick)의 입력으로 쓴다 — 대상 나무에 없다고 면제하면 조건이 사라져 before 가 조용히 통과한다.

## 실측한 불일치 (전부 문서 계층 — 제품 코드 결함 아님)

| # | 검사 | before 관측 |
|---|---|---|
| 1 | `readme_port_guidance` | README 가 **코드 기본값과 다른 포트**를 안내한다: `agk serve --port 8400`, API 문서 주소 `localhost:8400`, `AGK_SERVER_PORT` 기본값 `8400` — `config.py` `ServerConfig.port` 는 **8000**, `docs/09` 는 레거시 8400 을 금지한다(Phase 6 커밋 `ddcf3599` 가 8400→8000 기본값을 정리했는데 README 만 남았다) |
| 2 | `port_roles_documented` | 제품 포트·dev UI 포트·패키징 주소를 구분한 자리가 **없다**(`docs/20` 부재). 8000 을 다른 서비스도 쓴다는 사실(`AGK_VLLM_API_BASE=http://127.0.0.1:8000/v1`)도 어디에도 없어, "8400→8000 무조건 치환"이 안전해 보인다 |
| 3 | `single_status_owner_links` | 11개 문서가 현재 상태를 **각자** 들고 있다. `docs/16` 은 "**최신** (2026-09-14, attempt-039)" 인데 attempt-040 이 그 뒤에 있고, `docs/10` 은 attempt-034 를 "**최신 판정**"으로 부른다. README·`docs/10`~`docs/19` 어디에도 단일 소유자를 가리키는 링크가 없다 |
| 4 | `gate_count_scope` | 후보·지문·범위 없이 `23/23` 을 쓰는 줄 **3곳**: `docs/08:119`, `docs/13:68`(전혀 다른 뜻 — 테스트 23건), `docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md:71`, `docs/ga/CR14_GATE_COVERAGE_BOUNDARY.md:450` |
| 5 | `human_axis_not_only` | README 가 **"기술 축은 모두 닫혔고 남은 차단 사유는 사람의 영역"** 이라고 단정한다. 같은 저장소에 열린 기술 카드 **12개**(NX-00-F01 · NX-02-F01 · NX-06 · NX-07~NX-11 · NX-12~15)가 있고, 그 claim 에는 범위 한정도 현재 상태 링크도 없다 |
| 6 | `open_axes_documented` | 포트·판정·soak·열린 축·사람 축을 한 곳에 담은 문서가 **없다** |
| 7 | `support_matrix_levels` | 지원표에 **`Not evaluated`** 단계가 없고, **DMG 행이 낡았다** — "no package/distribution evidence establishes a native desktop app" 이라고 적혀 있는데 `dist/Ssak-Ai-0.1.0.dmg`(85M, 2026-09-15, sha256 검증)가 로컬에 실재한다. 산출물의 존재와 서명·실기기·업데이트 검증을 구분하는 자리도 없다 |
| 8 | `soak_phase_separation` | soak 의 **세 단계**(① 1차 FAIL RSS 1654.9MB ② 결정 A ③ 재soak JSON PASS)와 **미확정**(`exit:141`·후보 귀속 UNVERIFIED)을 한자리에서 분리해 보여 주는 자리가 없다. EX 대장은 재soak 결과를 아직 반영하지 않아 EX-05 가 `IN_PROGRESS` 로 남아 있었다 |

## 이 관측이 말하지 **않는** 것

- 제품 코드 결함이 아니다 — before/after 차이는 문서·지원표·대장이다.
- 게이트를 다시 돌린 것이 아니다. before 는 HEAD 트리에서 **문서 정합성만** 쟀다.
- 지원 범위를 넓힌 것이 아니다. `Supported` 는 before·after 모두 0행이다.
