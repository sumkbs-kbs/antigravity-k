# 삭제 감사 리포트 (Delete Audit) — 머스크 알고리즘 2단계

> 작성일: 2026-08-25 · 도구: `scripts/audit_dead_code.py` · 원본 데이터: `.tmp/delete_audit.json`
> 방법: AST 임포트 그래프 + 진입점(`agk` CLI) 정적 도달 분석 + 동적 로드(auto_discover) 보정 + tests/scripts/dashboard/docs 참조 근거 수집

### 현재 호환성 판정 (2026-08-30)

`agent_api.py`, `agents/commands.py`, `agents/coordinator.py`,
`agents/team_manager.py`는 현재 working tree에서 삭제된 상태이며,
`src/`, `tests/`, `scripts/`, `pyproject.toml`에 해당 모듈을 import하거나
entrypoint로 등록한 현행 참조는 없다. `agent_api.py` 삭제는 커밋
`7f8a593`에서 미등록·중복 라우트 정리로 확정됐고, health/models/embedding은
각각 `routes/models_api.py` 등 등록된 canonical router가 담당한다. 따라서
호환 shim을 복원하지 않고, 아래 표와 실행 계획의 해당 문구는 역사적 감사
기록으로 보존한다.

---

## 1. 요약 (한눈에)

| 지표 | 값 |
|---|---:|
| 전체 모듈 | 380개 / 110,476 LOC |
| 진입점(`antigravity_k.cli`)에서 **정적** 도달 | 292개 |
| 동적 로드(`tool_registry.auto_discover("antigravity_k.tools")`)로 생존 | 50개 |
| **도달 불가 삭제 후보** | **38개 모듈 / 6,882 LOC (전체의 6.2%)** |
| └ A티어 (즉시 삭제 안전) | 8개 / 1,405 LOC |
| └ B티어 (벤치마크 스크립트 전용) | 18개 / 2,306 LOC |
| └ B+티어 (테스트만 생존 — 제품 판단 필요) | 12개 / 3,171 LOC |

> 재현: `uv run python scripts/audit_dead_code.py --json .tmp/delete_audit.json`

### 이번 감사에서 배운 오탐 방지 (중요)

초기 단순 그래프는 122개(31,953 LOC)를 후보로 잡았으나, 다음 3가지 보정으로 38개까지 좁혔다.
**역방향(살아있는 것을 죽은 것으로 판정) 오탐이 삭제 작업의 최대 리스크**임을 보여준다.

1. **`uvicorn.run("antigravity_k.api.server:app")` 문자열 임포트** — `:attr` 접미사 파싱 필요
2. **패키지 `__init__.py`의 상대 임포트** — level=1은 부모가 아니라 자기 패키지를 가리킴 (`routes/*` 전체 오탐 해소)
3. **`tool_registry.auto_discover()`의 pkgutil 동적 로딩** — `tools/` 패키지 전체(50개)가 정적 임포트 없이 런타임 로드됨 → **tools/* 는 절대 "미사용"으로 판정 불가**

---

## 2. A티어 — 즉시 삭제 안전 (참조 0, 8개 / 1,405 LOC)

src·tests·scripts·dashboard·docs 어디서도 참조되지 않는다.

| LOC | 모듈 | 비고 |
|---:|---|---|
| 337 | `engine/memory_hygiene.py` | |
| 230 | `engine/json_logger.py` | `engine/logger.py`(B+)와 별개. test_logger는 logger.py만 테스트 |
| 227 | `engine/logging_util.py` | `logging_setup.py`와 기능 중복 추정 |
| 223 | `agents/coordinator.py` | ⚠️ 아래 §5.1 — team_manager만 참조하므로 **team_manager와 세트 삭제** |
| 181 | `knowledge/artifact_service.py` | |
| 90 | `integrations/discord_bot.py` | 통합 패키째 평가 권장 |
| 87 | `integrations/slack_bot.py` | 통합 패키째 평가 권장 |
| 30 | `scripts/ingest_obsidian.py` | |

## 3. B티어 — 벤치마크/스크립트 전용 생존 (18개 / 2,306 LOC)

프로덕션 경로에는 없지만 `scripts/run_*` 벤치마크가 import한다. **측정 루프 인프라이므로
일괄 삭제 금지.** 개별 판단 원칙: (a) 실측 근거를 만든 모듈은 유지, (b) 한 번도 결과를 내지
못한 실험 코드는 스크립트와 함께 삭제.

| LOC | 모듈 | scripts refs | 메모 |
|---:|---|---:|---|
| 435 | `agents/skills_registry.py` | 1 | tests:6 |
| 354 | `tools/search_benchmark.py` | 1 | tools인데 auto_discover 대상 아님? 확인 필요* |
| 141 | `engine/robust_tool_parser.py` | 2 | §5.3 — 프로덕션 미연결 |
| 135 | `engine/universal_compiler_bridge.py` | 2 | |
| 119 | `engine/surgical_patcher.py` | 1 | §5.3 — 프로덕션 미연결 |
| 106 | `engine/tdd_verifier.py` | 1 | |
| 101 | `engine/semantic_qa_engine.py` | 1 | |
| 98 | `engine/mcts_code_explorer.py` | 1 | |
| 90 | `engine/ast_drift_reconciler.py` | 1 | |
| 83 | `engine/smart_breakpoint.py` | 1 | |
| 82 | `engine/self_consistency_voter.py` | 1 | §5.4 — tool_loop가 SC 설정을 읽지만 이 모듈은 미사용 |
| 79 | `engine/prompt_compiler.py` | 1 | |
| 78 | `engine/attention_guard_sharder.py` | 1 | |
| 76 | `engine/vram_kv_throttler.py` | 1 | |
| 69 | `engine/algorithmic_skeleton_synthesizer.py` | 1 | |
| 67 | `engine/hybrid_reranker.py` | 1 | |
| 66 | `engine/bayesian_prompt_tuner.py` | 1 | |
| 63 | `engine/zero_waste_compressor.py` | 2 | §5.3 |

\* `search_benchmark.py`가 tools/에 있음에도 후보로 나온 것은 auto_discover가 BaseTool 서브클래스만 설치하고
모듈 자체는 로드한다는 점에서 모순 → **감사 도구 한계 표시. 삭제 전 런타임 smoke(`agk` 실행 후 도구 목록)로 재확인할 것.**

## 4. B+티어 — 테스트만 생존 (12개 / 3,171 LOC)

프로덕션 진입점에서 도달 불가. 테스트가 있어 살아있을 뿐이다. **테스트 동반 삭제** 전제.

| LOC | 모듈 | 판단 권고 |
|---:|---|---|
| 817 | `finetune/trainer.py` | ⚠️ §5.2 전략 자산 — 삭제 말고 **연결** 검토 |
| 762 | `engine/lora_pipeline.py` | ⚠️ §5.2 DPO 선호쌍+run_training — 전략 자산 |
| 545 | `agents/team_manager.py` | coordinator와 세트 삭제 |
| 441 | `api/routes/agent_api.py` | **서버에 등록 안 된 죽은 라우트** (routes/__init__에 include 없음). test_agent_runtime만 참조 |
| 189 | `engine/tool_guardrail_manager.py` | tool_guardrails.py(생존)와 중복 여부 확인 |
| 188 | `engine/reflection.py` | cognitive_loop(생존)와 역할 중복 여부 |
| 152 | `finetune/resource_admission.py` | finetune 패키지 운명과 연동 |
| 129 | `engine/release_baseline.py` | |
| 121 | `engine/logger.py` | logging_setup.py 사용 중인지 확인 후 판단 |
| 117 | `agents/commands.py` | slash_commands(생존)와 중복 여부 |
| 51 | `tasks/local_agent_task.py` | |
| 13 | `finetune/training_runtime.py` | |

---

## 5. 특이 발견 (삭제보다 중요한 사실들)

### 5.1 README 주장 vs 구현 불일치 #2 — MoE 스웜 코디네이터 고립

README 기능↔구현 매트릭스는 집단지성(MoE Swarm)의 핵심 구현으로 `coordinator.py`를 명시하지만,
실제 `agents/coordinator.py` + `agents/team_manager.py` 체인은 **CLI 진입점에서 완전히 고립**돼 있다
(오직 tests만 참조). 실제 스웜은 `model_manager.generate_collective()`(생존, model_manager.py:520)가 담당.

→ speculative branching("병렬 주장, 실제 순차")에 이은 **두 번째 문서-구현 불일치 사례**.
조치: README 매트릭스 수정 또는 coordinator 연결. 둘 중 하나는 반드시 필요.

### 5.2 자가개선 루프의 '학습' 단계가 프로덕션에 연결 안 됨

`lora_pipeline.run_training()`, DPO 선호쌍(`build_preference_pairs`, `export_dpo_dataset`),
`finetune/trainer.py` 전체가 src 내 호출자가 없다(테스트+수동 스모크만 존재).
EVALUATION_VS_COMMERCIAL.md가 "e2e 검증 완료"라고 쓴 것은 사실이지만, 그 경로는 **수동 실행**이다.

→ 머스크 관점: 자동화는 마지막 단계인데, 자동화됐다고 문서화된 부분이 실제로는 수동.
삭제 후보라기보다 **`agk train` 커맨드나 미션 루프 후크로 연결하는 것이 정답**.

### 5.3 "3층 패처" 신화 해소

이전 분석에서 회귀 위험으로 지적했던 robust_tool_parser+surgical_patcher+atomic_transaction_engine
다층 구조 — 실제로 **src 프로덕션 경로 참조가 0**이고 벤치마크 스크립트만 사용한다.
즉 신뢰성 위험은 아니었고, **유령 인프라**였다. tool_loop의 실제 패치 경로는 별도로 존재.

→ 조치: 벤치마크에서 실제 쓰는 파서 하나만 남기고 나머지는 B티어 정리 원칙에 따라 판단.

### 5.4 self_consistency_voter 이중 구현 의심

tool_loop.py는 config의 `amplification.self_consistency.enabled`를 읽어 SC를 제어하지만
`engine/self_consistency_voter.py`를 임포트하지 않는다. SC 로직이 tool_loop 내부에
재구현돼 있을 가능성 → voter는 삭제, 또는 tool_loop가 voter를 사용하도록 단일화.

---

## 6. 실행 계획 (권장 순서)

1. **즉시**: A티어 8개 + `team_manager.py` 삭제 → -1,628 LOC, 회귀 리스크 최소
   (각 삭제 전 `rg '<모듈명>'` 최종 재확인 + `make test-quick`)
2. **결정 완료**: `agent_api.py`는 미등록·중복 라우트로 유지하지 않는다. 현행
   canonical router와 테스트만 유지하고, 외부 import/entrypoint가 새로 발견될
   때에만 별도 호환성 검토를 연다.
3. **연결 결정**: finetune/lora_pipeline은 삭제 대신 `agk train` wired-in 검토 (§5.2)
4. **정리 원칙 적용**: B티어는 "직전 분기에서 실측 결과를 냈나?" 기준으로 개별 판단
5. **문서 동기화**: README 매트릭스의 coordinator 행 수정 (§5.1)

예상 효과: 최소 ~2,000 LOC 즉시 감소, 최대(전량 삭제 시) 6,882 LOC + 동반 테스트 —
단, §5.2 전략 자산 제외 시.

## 7. 감사 도구의 한계 (차기 개선)

- f-string 조합 임포트(`import_module(f".{name}")`)는 탐지 불가 → tools/ 외 동적 로딩 발견 시 보정 필요
- 로거 이름 문자열(`"antigravity_k.api.agent_api"` 등)을 임포트로 과대 계산 → 생존 쪽 편향(안전 방향)
- `search_benchmark.py`처럼 tools/ 소속 후보는 런타임 도구 목록 smoke로 재확인 필수
