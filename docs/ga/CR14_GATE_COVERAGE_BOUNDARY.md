# 게이트 커버리지 경계 — required gate 21개가 **재지 않는** 것

최종 갱신: 2026-09-13 (CR-14 attempt-022 — `config-models-unregistered` 폐쇄 + F-31)

판정서의 `required gate 21/21 PASS` 는 **강한 문장이지만 만능 문장이 아니다.** 이 문서는 그
문장이 **어디까지 참인지**를 적는다. 목적은 하나다: 초록을 "모든 것이 검증됐다"로 읽는 착각을
막는 것. 스킵은 그 착각이 생기는 대표적인 자리다 — 게이트는 초록인데 그 테스트는 어디서도
돌지 않는다.

소유자: **`scripts/gate_skip_register.json`**(무엇이 스킵되는지·왜·누가 대신 재는가) ·
검사: **`tests/test_cr14_gate_skip_register.py`**(등록부와 실제 게이트 환경을 한 건씩 대조).

## 1. 게이트 환경이 실제로 무엇을 도는가

게이트 `python-tests` 는 다음과 같은 환경에서 돌아간다(게이트 파일이 소유한다):

```
uv run --isolated --frozen --extra dev --extra rag --extra documents pytest tests/ -m "not benchmark" -v --tb=short
```

`--extra documents` 는 **attempt-021 에서 추가**됐다(F-30). 그전에는 어떤 파이프라인도
`documents`(pypdf)를 설치하지 않았고(CI 매트릭스는 `base`/`rag`/`mlx`, 주간 job 은 `mlx`/`unsloth`),
그래서 **PDF/DOCX 수집 능력을 재는 23건이 게이트·CI·주간 어디서도 돌지 않았다.**
이제 게이트가 그 extra 를 설치하므로 그 23건은 스킵이 아니라 **검증**이다(실측 87 passed / 0 skipped).

## 2. 스킵의 변화 (F-18 이 만든 대가를 세었다)

| attempt | 도구 출처 | passed | skipped |
| --- | --- | --- | --- |
| 011 | ambient(호출 셸 PATH) | 6200 | 13 |
| 012 | ambient(혼합) | 6215 | **6** |
| 013 | **lock 고정**(F-18 수정) | 6174 | **40** |
| 020 | lock 고정 | 6251 | 40 |
| 021 | lock 고정 + `documents` | 6280 | **17** |
| **022** | lock 고정 + `documents` | **6289** | **15** |

도구 출처를 바로잡은 것(F-18)은 옳았지만, 그 순간 **돌던 테스트 30여 건이 스킵으로 옮겨졌고
아무도 세지 않았다.** R-8 은 그 사실을 한계로 적어 두었다가 attempt-021 이 감사했다.
40건의 구성이 곧 답이다: `documents` 23(→ 복원) · `mlx` 4 · `unsloth` 7 · access-pin 2 ·
**소유자 없는 제품 능력 4**. 그 4건 중 2건(`config-models-unregistered`)은 **attempt-022 에서
능력으로 되돌았다**(설정 복원 — 아래 §3-2).

**닫는 일이 관측을 줄이면 안 된다(attempt-022, F-31a).** 관측 대상 파일을 등록부의 선언에서
**파생**시키면 항목을 닫는 순간 그 파일이 관측에서 사라지고, 그 자리가 다시 열려도 계약은
침묵한다. 그래서 관측 대상은 등록부가 `observed_files` 로 **고정**하고, 닫힌 항목은 `closed` 에
적혀 그 파일이 계속 관측된다(`tests/test_cr14_gate_skip_register.py` 가 `observed_files ⊇ 선언 파일`
과 `closed` 파일의 관측 잔존을 강제한다).

## 3. 게이트가 **재지 않는** 제품 능력 — 소유자 없는 2건 (+ 닫은 2건)

이 항목들이 이 문서의 핵심이다. 등록부에서 `KNOWN_GAP` 으로 분류되며, **어디서도 돌지 않는다.**

### `orchestrator-refactor-rewrite` — 에이전트 실행 루프 (2건)

- 미검증 능력: **에이전트가 프로그램을 만들고 실행하는가** · **코드 전용 답변에서 품질 재시도가 도는가**
- 왜 스킵인가: `OrchestratorAgent` 가 state graph + engine context 로 리팩토링되면서 두 테스트가
  **조건 없이** `@pytest.mark.skip` 이 됐다("향후 재작성 필요"). 조건이 아니므로 **어떤 환경에서도
  돌지 않는다** — ambient 에서도 돌지 않는다.
- 파일: `tests/test_agent_program_creation.py` · `tests/test_planning_and_rendering_quality.py`
- 소유자: 오케스트레이터 소관(**출시 책임자 미배정 — C14-08 배정 대상**)
- 계획: state graph 구조에 맞게 재작성해 능력을 다시 잰다. 이번 릴리스 범위가 아니면 그 사실을
  판정서 §6 과 여기에 함께 적어 **미검증 능력**으로 남긴다(조용한 스킵으로 두지 않는다).
- 만료: 2026-10-15

### ~~`config-models-unregistered` — 제품 설정의 약속 (2건)~~ → **attempt-022 에서 닫혔다(능력 복원)**

- 미검증 능력이었던 것: **집단지성 모델 가용성**(gemma-4-31B 등록 · collective-council 콤보의 세 모델)
- 어떻게 닫았나: **삭제가 아니라 복원**이다. 그 약속의 소비자를 확인해 보니 테스트만이 아니었다 —
  `BenchmarkHarness._default_targets()` 가 콤보 이름 `collective-council` 을 **코드에** 갖고 있고
  `/benchmark run`(인자 없음)의 기본 타겟이며, 그 이름을 config 가 소유하지 않으면 기본 실행이
  **조용히 오류 행(점수 0)** 을 기록한다(`_execute_single` 이 `ComboNotFoundError` 를 삼킨다 — F-31).
  그래서 `config.yaml`(2부)에 `collective-council` 을 `strategy: collective` 콤보로(로컬 3모델),
  gemma-4-31B 를 reasoning 로스터로 되돌렸다(`provider: ollama` 명시). 두 테스트는 이제 조건 없이
  돌고 **통과**한다 — 스킵이 아니라 **검증**이 됐다(`tests/test_cr14_default_target_config_contract.py`
  6건이 그 일치를 **실제 파일**로 잰다: 이빨 2건은 tmp YAML 에서 콤보·멤버를 지워 확인한다).
- 유일한 회귀 테스트가 `registry._raw` 에 **합성 매핑을 주입**해 실제 config 를 보지 않았던 것이
  이 결함을 오래 숨겼다 — 계약의 방식이 결함을 가린 **일곱 번째** 사례다(F-18·F-24·F-27·F-28·F-29·F-30·F-31).
- 등록부: 이 항목은 `closed` 로 옮겨졌고, **그 파일(`tests/test_upgrade_v6_9.py`)은 관측 목록에 남았다**
  — 다시 스킵되기 시작하면 대조가 즉시 실패한다.

## 4. 게이트 밖에서 재는 것 (손실이 아니다 — 소유자가 있다)

| 스킵 | 건수 | 어디서 도는가 |
| --- | --- | --- |
| `mlx-lm` 미설치 | 4 | `ci.yml` 매트릭스 `deps: [base, rag, mlx]`(macOS·Linux) · `weekly-drift.yml` — 최신 mlx-lm 으로 플래그 드리프트 검사 |
| `unsloth/trl` 미설치 | 7 | `weekly-drift.yml` unsloth-drift — 최신 unsloth·trl 설치 후 API 드리프트 검사 |
| (**닫힘**) 제품 설정 약속 | 2 | attempt-022 에서 **능력으로 되돌았다** — 게이트 환경에서 `tests/test_upgrade_v6_9.py` **21 passed / 0 skipped** |
| Access PIN 미설정 | 2 | `tests/test_cr04_shell_api_boundary.py` — 게이트 안에서 PIN 을 세우고 토큰 없는 요청이 401 로 끝나는 것을 잰다(**이 파일은 게이트에서 스킵되지 않는다**) |

이 세 줄은 등록부의 `ENV_PLATFORM`(워크플로가 그 파일을 **실제로** 도는지 계약이 확인)과
`ENV_CONFIG`(대신 재는 파일이 게이트에서 스킵되지 않는지 계약이 확인)에 대응한다.

## 5. 이 문서를 어떻게 쓰는가

- 판정서·릴리스 노트에서 `21/21` 을 인용할 때, **§3 의 4건이 여전히 미검증**이라는 사실을 함께 본다.
- 새 스킵을 만들려면 **등록부에 적어야 한다.** 적지 않으면 `test_gate_environment_skips_exactly_what_the_register_declares`
  가 실패한다 — "무엇이 사라졌는지 적어라"는 뜻이다.
- `KNOWN_GAP` 의 만료일이 지나면 계약이 실패한다. 그 실패는 **버그가 아니라 알림**이다:
  그 자리를 다시 보라는 뜻이다(감사 예외의 만료와 같은 규율).
- 능력이 복원되면(예: 그 두 테스트를 재작성) 등록부에서 그 항목을 지우고,
  `removed_by_f30` 처럼 **어떻게 복원했는지**를 등록부에 한 줄 남긴다.
