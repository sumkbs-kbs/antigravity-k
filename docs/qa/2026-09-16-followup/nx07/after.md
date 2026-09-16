# NX-07 after — 현재 상태가 한 문서를 가리키고, 지원표가 존재와 검증을 구분한다

- 측정일: 2026-09-16
- 측정 나무: 작업 트리(미커밋)
- 측정기: 같은 `repro_nx07_doc_consistency.py --root . --label after` (before 와 **동일한 자**, 데이터만 다름)
- 결과: **exit 0 · 8/8 checks PASS** (`after-run-output.json`)

## 무엇이 바뀌었나

| # | 검사 | after |
|---|---|---|
| 1 | `readme_port_guidance` | README 의 `agk serve --port 8000` · API 문서 `localhost:8000` · `AGK_SERVER_PORT` 기본값 `8000` 이 `config.py` 와 **일치**한다. 레거시 8400 은 README 에서 사라졌고, 같은 절에 "8000 을 다른 서비스도 쓴다"는 경고가 들어갔다 |
| 2 | `port_roles_documented` | 신규 `docs/20_CURRENT_STATUS.md` §1 이 **제품 8000 / dev UI 5173 / 패키징 `SSAK_HOST_URL`** 세 역할과, `AGK_VLLM_API_BASE`·`docker -p 8000:8000` 때문에 **무조건 치환하면 안 되는 이유**를 표로 소유한다 |
| 3 | `single_status_owner_links` | README + `docs/10`~`docs/19` **11곳**이 `docs/20` 을 **실재 링크로** 가리킨다. `docs/10` 의 "최신 판정(attempt-034)" 은 "이력 판정"으로 내려갔고, `docs/16` 의 "최신(attempt-039)" 도 이력으로 표시됐다 |
| 4 | `gate_count_scope` | `23/23` 을 쓰는 4줄에 attempt·후보·지문 또는 "required 게이트 인벤토리" 범위가 붙었다. 테스트 23건을 뜻하던 줄은 `23건`으로 바꿔 **두 뜻을 섞지 않는다** |
| 5 | `human_axis_not_only` | README 의 주장이 **"이 후보 범위에서는"** 으로 한정되고, 곧바로 "그 문장을 NX 범위로 넓혀 읽지 않는다 — NX-01~06 REVIEW·NX-06 런타임 BLOCKED·NX-07~15 TODO·이 후보 이후 변경 미커밋" 이 붙는다(`docs/20_CURRENT_STATUS.md` §4). 독립 검토자 미배정 문구는 **출시 책임자가 code/security/QA 를 겸직**한다는 사실로 정정됐다 |
| 6 | `open_axes_documented` | `docs/20` 이 §1 포트 · §2 판정 · §3 soak · §4 열린 기술 TODO · §5 사람 축 · §6 지원 범위 · §7 문서 지도 · §8 갱신 규칙을 소유하고, 열린 카드 12개 중 11개를 이름으로 나열한다 |
| 7 | `support_matrix_levels` | 지원표가 **네 단계**(Supported·Experimental·Unsupported·Not evaluated)를 정의하고, 데스크톱 행을 **범위 행(`Unsupported`, ADR-0003)** 과 **산출물 행(`Not evaluated`)** 으로 분리했다. 산출물 행은 DMG 의 sha256·`dmg-smoke` PASS 를 적고 **미완**(codesign/notarization · 깨끗한 실기기 · 업데이트 피드·rollback)을 나열한다 |
| 8 | `soak_phase_separation` | `docs/20` §3 이 ① FAIL(1654.9MB ≫ 64) ② 결정 A ③ 재soak JSON PASS ④ `exit:141`·귀속 UNVERIFIED 를 **네 줄로 분리**한다. EX 대장의 EX-05 행도 `JSON PASS / 종료·귀속 INCONCLUSIVE — DONE 아님` 으로 갱신했다 |

## 런타임 확인 — 새 고객이 따라가는 접속 (읽기 전용)

8000 은 **이미 실행 중인 인스턴스**(PID 27606/34194)가 점유하고 있었다. 새로 띄우지도, 종료하지도 않았고
그 인스턴스를 읽기만 했다(`runtime-access.txt`):

| 안내 | 관측 |
|---|---|
| `http://127.0.0.1:8000/health` | **200** `{"status":"ok","version":"0.1.0",...}` |
| `http://127.0.0.1:8000/api/ready` | **200** `status=degraded` · `traffic=accept` · `task_db/registry/writable_storage=required ok` · `model_manager=optional` |
| `http://127.0.0.1:8000/openapi.json` | **200** · title `Ssak-Ai API` · paths **227** |
| `http://127.0.0.1:8000/` | **200** · `<title>Ssak-Ai — Cold-blooded engineering</title>` — **대시보드 화면이 맞다** |
| `http://127.0.0.1:8000/docs` · `/redoc` | **200** · **200** |

즉 README 가 안내하는 주소를 그대로 따라가면 서버·대시보드·API 문서가 **같은 포트**에서 나온다.
부수 확인: `/api/ready` 응답이 NX-06 이 도입한 `checks[].kind`·`traffic` 계약 모양 그대로다.

## 이 관측이 말하지 **않는** 것

- 게이트·판정이 바뀌지 않았다. `Supported` 는 여전히 0행이고 GA 판정은 **NO-GO** 다.
- soak 을 다시 돌리지 않았다. §3 의 ④(종료·귀속)는 그대로 미확정이다.
- DMG 를 새로 만들거나 서명하지 않았다. 기존 산출물의 **사실**을 지원표에 옮겨 적었을 뿐이다.
- 제품 코드를 고치지 않았다(변경은 문서·지원표·대장 + 계약 시험 1파일 + 측정기 1파일).
