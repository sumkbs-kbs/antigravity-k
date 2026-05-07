---
title: Agentic Technology Upgrade Review
tags: [agentic, github, huggingface, upgrade, antigravity-k]
date: 2026-05-07
---

# Agentic Technology Upgrade Review (2026-05-07)

## 조사 범위

GitHub와 Hugging Face의 최신 에이전틱 프레임워크 흐름을 실시간 검색하여 Antigravity-K에 이식 가능한 구조만 선별했다. 외부 프레임워크를 그대로 끌어오기보다는 현재 코드베이스의 `StateGraph`, `ToolRegistry`, `QualityGate`, `SessionManager`, `AgentTracer`에 맞는 결정론적 업그레이드 레이더로 반영했다.

## 핵심 관찰

| 출처 | 관찰한 최신 흐름 | Antigravity-K 반영 방향 |
|------|------------------|--------------------------|
| LangGraph | durable execution, human-in-the-loop, memory, tracing/observability | `StateContext` 체크포인트 영속화와 resume/replay 명령이 최우선 |
| Hugging Face smolagents | CodeAgent, sandboxed execution, model/tool agnostic, MCP tool support | 별도 CodeAction lane은 sandbox/import allowlist/timeout/diff gate 없이는 열지 않음 |
| Hugging Face Hub MCP | `MCPClient`, local stdio/remote http/sse tool server, Tiny Agent chat loop | MCP 도구를 `ToolRegistry`에 transport/trust/teardown 메타데이터로 등록 |
| OpenAI Agents SDK | handoffs, tools, guardrails, sessions, tracing, realtime agents | handoff/guardrail/session/tracing을 하나의 readiness score로 집계 |
| Microsoft AutoGen / MAF | Magentic-One식 multi-agent team, AutoGen Bench, MAF 장기 지원 전환 | 벤치마크 모드와 agentic run profile 기록 강화 |

## 반영 완료

| 파일 | 반영 내용 |
|------|----------|
| `src/antigravity_k/engine/agentic_tech_radar.py` | 최신 에이전틱 기술을 Antigravity-K 업그레이드 우선순위로 변환하는 결정론적 레이더 추가 |
| `src/antigravity_k/engine/slash_commands.py` | `/agentic [objective]` 명령 추가 |
| `dashboard/src/command_palette.js` | Command Palette에 `Agentic Upgrade Radar (/agentic)` 추가 |
| `tests/test_agentic_tech_radar.py` | 레이더, Markdown 출력, slash command 회귀 테스트 추가 |
| `tests/test_claw_integration.py` | `/help`, completion, `/agentic` 통합 테스트 보강 |

## 현재 `/agentic` 명령 출력 계약

- `# Agentic Upgrade Radar`
- `Upgrade Decision Matrix`
- `Transfer Plan`
- `Guardrails`
- `Evidence Sources`
- P0/P1 우선순위 집계

## 다음 고도화 후보

1. `StateContext` 체크포인트를 파일/SQLite에 저장하고 `/resume`, `/replay` 명령으로 복구한다.
2. MCP adapter를 `ToolRegistry`에 추가하고 외부 tool trust label을 강제한다.
3. CodeAction sandbox lane을 별도 도구로 만들고, 실행 전 artifact diff를 표시한다.
4. AgentTracer와 QualityGate 결과를 결합해 Agentic Readiness Score를 산출한다.
5. DOM self-test와 pytest 결과를 agentic run benchmark profile로 누적한다.

## 참고 출처

- LangGraph: https://github.com/langchain-ai/langgraph
- Microsoft AutoGen: https://github.com/microsoft/autogen
- OpenAI Agents SDK: https://github.com/openai/openai-agents-python
- Hugging Face smolagents: https://github.com/huggingface/smolagents
- Hugging Face MCP Client: https://huggingface.co/docs/huggingface_hub/package_reference/mcp
- Hugging Face Agents on the Hub: https://huggingface.co/docs/hub/en/agents
