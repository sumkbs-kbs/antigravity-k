---
title: MCP Capability Upgrade Report
tags: [mcp, agentic, protocol, testing, upgrade]
date: 2026-05-07
---

# MCP Capability Upgrade Report

## 1. 최신 기술 조사 근거

| 출처 | 확인한 핵심 변화 | Antigravity-K 반영 |
|---|---|---|
| https://modelcontextprotocol.io/specification/2025-11-25/basic/transports | 최신 MCP는 `stdio`와 `Streamable HTTP`를 표준 transport로 정의하고, HTTP 서버의 Origin 검증/localhost 바인딩/인증을 요구 | `MCPSessionManager.connect_streamable_http()` 추가, 원격 서버 인증 감사 추가 |
| https://modelcontextprotocol.io/specification/2025-03-26/changelog | OAuth 2.1 authorization, Streamable HTTP, JSON-RPC batching, tool annotations, completions 추가 | `/mcp` 레이더에 capability matrix 반영, tool annotation을 위험도에 매핑 |
| https://github.com/modelcontextprotocol/python-sdk | Python SDK가 stdio 및 Streamable HTTP 클라이언트 패턴 제공 | 기존 SDK 의존성을 활용해 transport 확장 |
| https://huggingface.co/docs/huggingface_hub/package_reference/mcp | Hugging Face MCPClient가 로컬 stdio 및 원격 HTTP/SSE 서버 연결 패턴 제공 | `.mcp.json` 호환 템플릿과 `http`/`sse` 설정 로딩 지원 |
| https://huggingface.co/docs/hub/en/agents | Hugging Face Hub Agents는 MCP 서버로 노출되어 외부 에이전트와 도구 상호운용 가능 | MCP 서버 구성을 agentic tool ecosystem의 1급 기능으로 승격 |

## 2. 구현 반영 사항

| 영역 | 변경 파일 | 반영 내용 |
|---|---|---|
| 최신 MCP 레이더 | `src/antigravity_k/engine/mcp_capability.py` | MCP capability matrix, 설정 감사, 안전 템플릿 렌더링 추가 |
| Transport 확장 | `src/antigravity_k/tools/mcp_session_manager.py` | `stdio` 외 `Streamable HTTP`, legacy `SSE` 연결 지원 |
| 서버 로딩 안전성 | `src/antigravity_k/tools/mcp_tool_loader.py` | 연결 전 MCP config 감사, 원격 무인증 서버 차단, timeout/trust/tool annotation 경고 |
| 도구 품질/권한 | `src/antigravity_k/tools/mcp_tool_loader.py` | MCP `readOnlyHint`, `destructiveHint`, `openWorldHint`를 `RiskLevel`로 매핑 |
| 자율 실행 정책 | `src/antigravity_k/engine/capability_policy.py` | MCP/Skills/내장 도구/PC control을 `allow/prompt/deny`로 공통 판정 |
| 실행 직전 게이트 | `src/antigravity_k/tools/tool_registry.py`, `src/antigravity_k/engine/tool_executor.py` | 모델이 도구 호출을 생성해도 Antigravity-K가 자체 정책으로 재판정 |
| 사용자 접근성 | `src/antigravity_k/engine/slash_commands.py` | `/mcp [radar|audit <path>|template]` 추가 |
| 전체 capability manifest | `src/antigravity_k/engine/slash_commands.py` | `/capabilities [objective]`로 도구/MCP/Skills 자율 사용 가능성 확인 |
| UI 검색성 | `dashboard/src/command_palette.js` | Command Palette에 `MCP Upgrade Radar (/mcp)`, `Autonomous Capabilities (/capabilities)` 추가 |

## 3. 전문 테스터 관점 점검 결과

| 점검 항목 | 기대 기준 | 결과 |
|---|---|---|
| 최신 transport 대응 | 원격 MCP는 Streamable HTTP를 우선 지원 | PASS |
| 레거시 호환 | 기존 SSE 서버를 완전히 배제하지 않음 | PASS |
| 원격 서버 안전성 | 인증 없는 외부 HTTP MCP 서버는 import 전 차단 | PASS |
| 로컬 stdio 호환 | 기존 `.mcp.json` command/args 패턴 유지 | PASS |
| 도구 위험도 품질 | MCP tool annotation을 승인 게이트 메타데이터로 반영 | PASS |
| MCP 자체 판단 | 감사 통과, 인증, trust, annotation이 모두 실행 판단에 반영 | PASS |
| Skills 자체 판단 | relevance score와 risk/trust 정책을 통과한 skill만 자동 활성화 | PASS |
| PC capability 자체 판단 | critical desktop/computer control은 자동 실행 대신 승인 요청 | PASS |
| 사용자 조작 경로 | 채팅 슬래시 커맨드와 팔레트에서 접근 가능 | PASS |

## 4. 추가 고도화 후보

| 우선순위 | 후보 | 설명 |
|---|---|---|
| P1 | OAuth 2.1 interactive flow | 현재는 Authorization header/auth metadata 유무를 감사한다. 다음 단계는 실제 OAuth client flow와 token refresh를 붙이는 것이다. |
| P1 | JSON-RPC batching scheduler | 여러 MCP tool discovery/call을 batch로 묶어 latency를 줄인다. |
| P1 | MCP completions bridge | MCP 서버가 제공하는 argument completion을 Command Palette와 tool form에 연결한다. |
| P2 | server health cache | MCP 서버별 initialize/list_tools 결과와 실패 원인을 캐시해 대시보드에 표시한다. |

## 5. 회귀 검증

```text
python -m pytest tests/test_autonomous_capabilities.py tests/test_mcp_capability.py tests/test_claw_integration.py
43 passed

python -m ruff check src tests
All checks passed

python -m pytest
261 passed

python -m compileall -q src tests
PASS

cd dashboard && npm run build
PASS
```
