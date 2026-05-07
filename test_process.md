# DOM 기반 정밀 기능 테스트 프로시저 (v6.9)

> **최종 검증일**: 2026-05-08 03:24 KST
> **최종 결과**: 38/38 Phase PASS, pytest 379 passed (359 기존 + 20 신규 v6.9 검증)
> **최종 리포트**: `test_report.md`
> **적용 엔진**: `TestHarness`, `GoalRunner` (Auto-Verify), `OrchestratorAgent` (Memory-Integrated), `OmniTDDEngine`, `QualityGate` (Information Density), `SelfCapabilityEngine`, `StreamProcessor` (CJK Precision), `AutonomousCapabilityPolicy`, `MCPCapabilityAdvisor`, `CodexTransferEngine`, `CollectiveIntelligenceEngine`, `ModelRouter`, `RAGIndexer` (Auto-Index), `ChainOfVerification`, `WebSearchEngine`, `BrowserSurfingAgent`, `ExternalBrainRouter`, `MemoryManager` (4-Tier Cognitive), `OutputQualityComparator`, `SelfImprovementLoop`

본 문서는 Antigravity-K를 실제 사용자가 조작하는 환경과 최대한 동일하게 검증하기 위한 전문 QA 절차서입니다. 검증은 브라우저 DOM 조작, 보호 PIN 인증, API 호출, 정적 분석, 전체 테스트, 빌드, 출력 품질 비교, 채팅 출력 타이포그래피/Markdown 표시 품질, Agent Manager 프로젝트별 작업 관리, 출력물 DOM 안전성 검사, 자기 능력 인식(`/self`) 검증, MCP/Skills/로컬 PC capability 자율 판단 검사, Codex식 운영 강점 이식(`/codex`), 집단지성 모델 경쟁/비판/합성, 집단지성 벤치마크 누적 비교, RAG 컨텍스트 확장(자동 인덱싱), 자기검증 루프, 웹 검색 도구(Tavily/SearxNG), 비전-언어 자율 웹 서퍼(Browser-Use), External Brain 자동 위임, 4-Tier 인지 메모리 시스템, 정보 밀도 품질 검증, 한국어 한자 보존 CJK 정밀 필터, 자기 개선 피드백 루프, 출력 품질 비교기, GoalRunner 자동 검증을 모두 포함합니다.

---

## 1. 사전 조건

| 항목 | 필수 여부 | 확인 방법 |
|------|----------|-----------|
| FastAPI 서버 | 필수 | `curl http://127.0.0.1:8012/health` |
| 정적 대시보드 | 필수 | `curl http://127.0.0.1:8012/` |
| Python 테스트 환경 | 필수 | `python -m pytest` |
| Ruff | 필수 | `python -m ruff check src tests` |
| Node/Vite | 필수 | `cd dashboard && npm run build` |
| Playwright/Browser DOM | 필수 | In-app Browser 또는 하네스 self-test |
| 보호 PIN | 필수 | `config.yaml`의 `security.access_pin` 및 `X-Access-Pin` |
| Ollama/비전 모델 | 선택 | Phase 6/8 심화 분석에 사용 |
| Ollama 중급 이상 집단지성 모델 | 필수 | `ollama list`에서 Qwen3 30B, Mistral Small 24B, DeepSeek 32B 확인 |
| 외부 AI 앱 접근 권한 | 선택 | Phase 7 외부 두뇌 실제 전송에 사용 |

권장 서버 실행:

```bash
cd /Users/mr.k/program/coding/ssak_comp/antigravity-k
PYTHONPATH=src python -m uvicorn antigravity_k.api.server:app --host 127.0.0.1 --port 8012
```

필수 회귀 명령:

```bash
python -m ruff check src tests
python -m pytest
python -m compileall -q src tests
cd dashboard && npm run build
```

---

## 2. 전체 테스트 순서

1. 서버 실행 후 `/health`, `/v1/health`, 대시보드 HTML 로드 확인
2. In-app Browser로 대시보드 접속
3. DOM snapshot 기준으로 내비게이션, Command Palette, 채팅 입력창 확인
4. 데스크톱 버튼, 모바일 상단 버튼, `Cmd/Ctrl+K`로 Command Palette 접근 확인
5. Command Palette에서 `goal` 검색 후 `/goal` 프리필 확인
6. 채팅 입력창에서 `/goal`을 직접 전송하고 계약 문서 렌더링 확인
7. `/goal` objective에 악성/정상 Markdown 링크를 포함해 sanitizer 확인
8. `POST /api/agent/tools/browser/self-test`로 10개 인텐트 통합 검증
9. 출력 품질, Planning Mode, Markdown 렌더링 회귀 테스트 실행
10. `/mcp`, `/capabilities`로 MCP/Skills/PC 도구 자율 판단 manifest 확인
11. `/codex`로 Codex식 강점 이식 manifest, 운영 루프, completion gates 확인
12. 정적 분석, 전체 pytest, 컴파일, 대시보드 빌드 실행
13. 브라우저 reload 후 신규 console.error 및 console.warning 0건 확인
14. RAG 인덱서 코드 청킹/검색 정확도, CoV 자기검증 루프, 웹 검색 도구, 자동 위임, 장기 기억 회귀 테스트 실행
15. 자연어 자기소개 질문과 `/self`가 실제 등록된 도구/Skills/슬래시 명령 기준으로 응답하는지 확인
16. `collective-council`, `orchestrator-swarm`, `coding-swarm`, `reasoning-balanced`가 `collective` 전략으로 읽히고 제안/비판/합성 라운드를 수행하는지 확인
17. Qwen3 계열 모델이 `thinking`만 반환하지 않도록 `/no_think` 주입과 내부 추론 제거 필터를 검증
18. `/benchmark` 도움말/리포트/API/Command Palette 경로와 종합점수 산출을 검증
19. 채팅 assistant 출력 폰트, 행간, 본문 폭, Markdown 표/코드/목록 표시가 Codex식 문서형 출력 기준을 만족하는지 확인
20. Agent Manager의 필요성/기능 중복/프로젝트별 작업 관리 가능 여부를 검증
21. `test_report.md`, `test_process.md`에 결과와 결함 이력 반영

---

## 3. Phase별 테스트 절차

### Phase 1: 코어 레이어 및 내비게이션

**목적**: 대시보드가 깨지지 않고 기본 DOM을 렌더링하는지 검증합니다.

**절차**
- `http://127.0.0.1:8012` 접속
- `<title>`이 `Antigravity-K`인지 확인
- 사이드바 네비게이션 `AI 채팅`, `LLM Wiki`, `에이전트`, `설정` 존재 확인

**통과 조건**
- `#app` 또는 주요 대시보드 DOM 존재
- 초기 로드 신규 console.error 및 console.warning 0건

**최신 결과**: PASS

### Phase 2: Command Palette

**목적**: 키보드 중심 워크플로우와 `/goal`, `/self` 접근성을 검증합니다.

**절차**
- `명령 팔레트` 버튼 클릭 또는 `Cmd+K`
- 검색창에 `goal` 입력
- `Autonomous Goal (/goal)` 항목 표시 확인
- Enter 실행 후 채팅 입력창에 `/goal` 프리필 확인
- 검색창에 `self` 입력 후 `Self Capability Report (/self)` 항목 표시 확인

**통과 조건**
- 검색 결과가 즉시 필터링됨
- stale selection 없이 선택 결과가 실행됨
- `/goal` 프리필이 입력창에 들어감
- `/self`가 Command Palette에서 discoverable 해야 함

**최신 결과**: PASS — 모바일 palette button visible, overlay visible, `Autonomous Goal (/goal)` 및 `Self Capability Report (/self)` 검색 결과 표시, 신규 console error/warning 0

### Phase 3: 채팅 인터랙션 및 `/goal` 라우팅

**목적**: 사용자가 직접 입력하는 경로와 동일하게 채팅 전송을 검증합니다.

**절차**
- 채팅 입력창에 `/goal DOM-QA-20260507-LINK-SAFETY [bad](javascript:alert(1)) [good](https://example.com) 출력 링크 안전성을 검증해줘` 입력
- Enter 전송
- assistant bubble에 `/goal Autonomous Goal Contract` 표시 확인

**통과 조건**
- 일반 모델 스트림이 아니라 slash registry로 라우팅됨
- `Autonomous Judgment Policy` 표시
- `Response quality gates` 표시
- 고유 마커가 user/assistant 양쪽에 렌더링됨

**최신 결과**: PASS — heading count 6 → 7, marker count 2, `Response quality gates` 표시

### Phase 4: 파일 탐색기 및 터미널

**목적**: 파일 탐색 UI와 터미널 WebSocket 경로를 검증합니다.

**절차**
- 파일 탐색기 항목 수 확인
- 터미널 WebSocket 연결
- echo 응답 확인

**통과 조건**
- 파일 항목 1개 이상
- WebSocket 연결 성공

**최신 결과**: PASS — file_explorer 60개, terminal_ws 11.0ms

### Phase 5: Self-Test Loop

**목적**: Antigravity-K가 스스로 주요 기능을 점검하는지 검증합니다.

**실행**

```bash
curl -s -X POST http://127.0.0.1:8012/api/agent/tools/browser/self-test \
  -H 'Content-Type: application/json' \
  -H 'X-Access-Pin: 1935' \
  -d '{}'
```

**통과 조건**
- 총 10개 인텐트 중 8개 이상 통과
- 세부 결과와 마크다운 리포트 생성

**최신 결과**: PASS — 10/10, 2,043.6ms, 보호 PIN 모드에서 내부 API 호출까지 통과

### Phase 6: Autonomous QA Dry Loop

**목적**: 자율 QA 엔진 초기화, 스크린샷 수집, 반응형 확인 루프를 검증합니다.

**통과 조건**
- AutonomousQA 초기화 성공
- 스크린샷 1,000 bytes 이상
- responsive desktop/tablet/mobile 2/3 이상 통과

**최신 결과**: PASS — screenshot 126,098 bytes, responsive 3/3

### Phase 7: External Brain 목록

**목적**: 외부 AI 두뇌 어댑터 목록과 상태 계약을 검증합니다.

**통과 조건**
- `gemini_app`, `chatgpt_web`, `gemini_web` 어댑터 반환
- 각 어댑터의 availability가 boolean으로 표시됨

**최신 결과**: PASS — 3개 어댑터 반환

### Phase 8: Vision Analysis API

**목적**: 비전 분석 라우트가 누락되지 않고 예외를 명확히 반환하는지 검증합니다.

**통과 조건**
- 스크린샷 없이 호출 시 404/500이 아닌 기대 가능한 400 계열 응답
- 하네스에서 `Vision API reachable (expected 400)` 처리

**최신 결과**: PASS

### Phase 9: Responsive Check

**목적**: Desktop, Tablet, Mobile 3개 뷰포트에서 레이아웃을 검증합니다.

**통과 조건**
- 3개 중 2개 이상 가로 스크롤 없음
- 주요 앱 DOM visible

**최신 결과**: PASS — 3/3

### Phase 10: Full Integration Self-Test

**대상 인텐트**

| # | Intent | 최신 결과 |
|---|--------|-----------|
| 1 | `health_api` | PASS |
| 2 | `models_api` | PASS |
| 3 | `vision_analyze` | PASS |
| 4 | `external_brain_list` | PASS |
| 5 | `dashboard_load` | PASS |
| 6 | `chat_send` | PASS |
| 7 | `file_explorer` | PASS |
| 8 | `terminal_ws` | PASS |
| 9 | `autonomous_qa_dry` | PASS |
| 10 | `responsive_check` | PASS |

**최신 결과**: PASS — 10/10

### Phase 11: 코드 회귀 및 보안 계약

**실행**

```bash
python -m ruff check src tests
python -m pytest
python -m compileall -q src tests
cd dashboard && npm run build
```

**최신 결과**

```text
python -m ruff check src tests
All checks passed!

python -m pytest
321 passed in 8.06s

python -m compileall -q src tests
PASS

dashboard npm run build
PASS — Vite build 112ms
```

### Phase 12: API-driven E2E

**목적**: 백엔드 API만으로 slash command, health, agent tool 경로가 동작하는지 확인합니다.

**최신 검증**
- `/health` HTTP 200
- `/v1/health` HTTP 200
- `X-Access-Pin: 1935` 포함 `/api/slash {"input":"/goal ..."}` HTTP 200
- 잘못된 PIN `0000`은 `/api/session/info` 401 반환
- 빈 slash payload는 인증 후 구조화된 오류 반환

**최신 결과**: PASS

### Phase 13: `/goal` 자율 목표 계약

**목적**: Codex식 목표 고정, 성공 기준, 판단 정책, 증거 보고 루프를 검증합니다.

**통과 조건**
- `# /goal Autonomous Goal Contract`
- `Readiness`
- `Success Criteria`
- `Autonomous Judgment Policy`
- `Autonomous Loop`
- `Capability Transfer Matrix`
- `Response quality gates`

**최신 결과**: PASS

### Phase 14: 출력 품질 비교 검증

**목적**: Antigravity-K 출력물을 Codex/Claude Code/Google Antigravity에서 기대하는 품질 계약과 비교합니다.

**검증 기준**
- 코드-only 응답 금지
- 한국어 설명 포함
- 알고리즘 문제는 Big-O 포함
- 비교 요청은 비교표 또는 명시적 장단점/기준/차이 구조 포함
- 반복 문단 감점
- 품질 미달 시 retry 또는 명확한 실패 보고

**적용 구현**
- `QualityGate._check_output_contract()`
- `OmniTDDEngine` Response Reconstructor
- `OrchestratorAgent` 품질 실패 시 1회 재작성 루프

**최신 결과**: PASS — `tests/test_output_quality.py` 7개, `tests/test_planning_and_rendering_quality.py` 6개 통과

### Phase 15: 병렬 도구 호출

**목적**: 독립 도구 호출을 병렬로 처리할 수 있는지 검증합니다.

**통과 조건**
- 병렬 실행 가능한 도구가 batch 처리됨
- Tool response 대기 후 다음 단계 진행
- approval 상태는 도구 결과 객체 기준으로 판단

**최신 결과**: PASS

### Phase 16: CEO Analyzer 및 Guardrail 안정성

**목적**: 모델 라우팅, 도구 승인, in-band 문자열 오탐을 방지합니다.

**통과 조건**
- CEO Analyzer가 ModelManager를 통해 라우팅
- `[APPROVAL REQUIRED]` 문자열 자체가 아니라 승인 필요 도구 결과로만 루프 중지
- guardrail 차단 결과가 구조적으로 기록됨

**최신 결과**: PASS

### Phase 17: Planning Mode 및 Artifacts

**목적**: 대규모 변경은 계획/승인 모드로 보내고, 단순 코딩은 과도하게 막지 않는지 검증합니다.

**통과 조건**
- `complex` 작업은 Planning Mode 적용
- 대규모/구조/마이그레이션/리팩토링 키워드가 있는 coding 작업은 Planning Mode 적용
- 단순 함수 작성 같은 coding 작업은 즉시 답변 가능

**최신 결과**: PASS — `_requires_planning_mode()` 회귀 테스트 통과

### Phase 18: Advanced Markdown UI Rendering

**목적**: Mermaid, Carousel, 일반 Markdown 링크 등 고급 출력물이 DOM을 깨지 않고 안전하게 렌더링되는지 검증합니다.

**통과 조건**
- Mermaid block은 HTML escape 후 `.mermaid` 컨테이너에 삽입
- Carousel slide 텍스트는 escape
- Carousel image `src`는 `http(s)`, `data:image/`, `/`, `./`, `../`만 허용
- 일반 Markdown 링크 `href`는 `http(s)`, `mailto:`, `/`, `./`, `../`, `#`만 허용
- `javascript:` 등 위험 URL은 `href="#"`로 강등
- 외부 링크에는 `rel="noopener noreferrer"` 적용
- Mermaid 전역 객체가 없을 때 console.error가 발생하지 않음

**최신 결과**: PASS — DOM에서 bad link `#`, good link `https://example.com`; 브라우저 reload 후 신규 console.error/warning 0건

### Phase 19: MCP Capability Upgrade

**목적**: 최신 MCP transport와 서버 설정 안전성을 Antigravity-K가 자체 판단해 적용하는지 검증합니다.

**절차**
- `/mcp` 실행 후 최신 MCP capability matrix 확인
- `/mcp template`으로 guarded `.mcp.json` 템플릿 확인
- 원격 HTTP MCP 서버에 Authorization/auth metadata가 없을 때 차단되는지 확인
- 로컬 stdio MCP 서버가 `trust_level`, `timeout_ms`, `tool_annotations`를 포함하면 import 가능 상태가 되는지 확인

**통과 조건**
- Streamable HTTP, OAuth 2.1, tool annotations, JSON-RPC batching/completions가 레이더에 표시됨
- `MCPSessionManager`가 `stdio`, `http`/`streamable-http`, legacy `sse` 연결 경로를 가짐
- MCP tool annotation이 `RiskLevel`과 dashboard metadata에 반영됨
- 무인증 원격 MCP 서버는 자동 실행 전에 차단됨

**최신 결과**: PASS — `tests/test_mcp_capability.py` 5개 통과

### Phase 20: Autonomous Capability Policy

**목적**: MCP, Skills, 내장 도구, 로컬 PC 제어 기능을 Antigravity-K가 목표 기반으로 자체 판단하여 자동 사용/승인 요청/차단하는지 검증합니다.

**절차**
- `/capabilities <objective>` 실행 후 tool/MCP/Skills manifest 확인
- 안전한 로컬/검증된 skill은 목표와 관련 있을 때 자동 활성화되는지 확인
- critical PC control, desktop automation, 비가역 작업은 자동 실행 대신 승인 요청으로 격상되는지 확인
- ToolExecutor 실행 직전에 `AutonomousCapabilityPolicy`가 PermissionGate보다 먼저 적용되는지 확인

**통과 조건**
- trusted safe/low/medium/high capability는 목표 적합 시 자율 사용 가능
- critical capability는 명시 승인 없이는 실행되지 않음
- Skills는 relevance score와 risk/trust 정책을 함께 통과해야만 자동 활성화됨
- MCP tools는 서버 감사 결과와 annotation 기반 위험도를 포함해 실행 판단됨

**최신 결과**: PASS — DOM `/capabilities`에서 Tool/MCP 45개 판단, Skills 후보 판단, disconnected 문구 없음. `tests/test_autonomous_capabilities.py` 5개 및 API 출력 회귀 테스트 통과

### Phase 21: RAG 기반 컨텍스트 확장

**목적**: 로컬 모델의 4K~32K 컨텍스트 윈도우 한계를 AST 기반 코드 청킹 + VectorStore 시맨틱 검색으로 보상하여, 질문과 관련된 코드가 자동으로 프롬프트에 주입되는지 검증합니다.

**자동화 테스트 실행**

```bash
python -m pytest tests/test_upgrade_phases.py::TestRAGIndexer -v --tb=short
```

**기대 출력**

```text
test_chunk_python_splits_by_function PASSED    # 함수/클래스/메서드 분리
test_chunk_markdown_splits_by_heading PASSED    # 헤딩 기준 섹션 분할
test_format_context_returns_xml_block PASSED    # <relevant_code> XML 포맷
test_make_id_is_deterministic PASSED            # 결정적 청크 ID
```

**수동 정밀 검증 (인라인 스크립트)**

```bash
PYTHONPATH=src python3 -c "
from antigravity_k.engine.rag_indexer import RAGIndexer
idx = RAGIndexer(project_root='.')
# 1. Python AST 청킹 정밀 검증
chunks = idx._chunk_python('test.py', '''
import os
def hello():
    return 'hi'
class Foo:
    def bar(self): return 1
    def baz(self): return 2
''')
names = [c.node_name for c in chunks]
types = [c.node_type for c in chunks]
assert 'hello' in names, f'FAIL: hello not in {names}'
assert any('Foo' in n for n in names), f'FAIL: Foo not in {names}'
assert 'function' in types, f'FAIL: function not in {types}'
print(f'[Phase 21-1] Python AST: {len(chunks)} chunks, names={names} → PASS')

# 2. Markdown 헤딩 청킹 정밀 검증
md_chunks = idx._chunk_markdown('doc.md', '# Title\nPara\n## Sec1\nText1\n## Sec2\nText2')
assert len(md_chunks) >= 2, f'FAIL: expected >=2 sections, got {len(md_chunks)}'
assert all(c.node_type == 'text_section' for c in md_chunks)
print(f'[Phase 21-2] Markdown: {len(md_chunks)} sections → PASS')

# 3. 일반 텍스트 폴백 청킹
gen = idx._chunk_generic('a.js', 'x\n' * 120)
assert len(gen) >= 2, f'FAIL: generic chunking failed'
print(f'[Phase 21-3] Generic: {len(gen)} chunks → PASS')

# 4. 청크 ID 결정성
id1 = RAGIndexer._make_id('f.py', 'fn_a')
id2 = RAGIndexer._make_id('f.py', 'fn_a')
id3 = RAGIndexer._make_id('f.py', 'fn_b')
assert id1 == id2, 'FAIL: non-deterministic ID'
assert id1 != id3, 'FAIL: collision on different input'
print(f'[Phase 21-4] ID determinism: {id1} == {id2}, != {id3} → PASS')

# 5. format_context XML 구조 검증
from unittest.mock import MagicMock
store = MagicMock()
store.search.return_value = [{'text': 'def foo(): pass', 'metadata': {'source': 'a.py', 'node_name': 'foo', 'start_line': 1, 'end_line': 2}}]
idx2 = RAGIndexer(project_root='.', vector_store=store)
ctx = idx2.format_context('foo')
assert '<relevant_code>' in ctx and '</relevant_code>' in ctx, f'FAIL: XML tags missing'
assert 'a.py' in ctx, 'FAIL: source not in context'
print(f'[Phase 21-5] format_context: XML structure OK → PASS')
print('Phase 21: ALL 5 CHECKS PASSED ✅')
"
```

**통과 조건**: 5개 인라인 체크 + 4개 pytest 모두 PASS

**최신 결과**: PASS — pytest 4/4, 인라인 5/5

### Phase 22: Chain-of-Verification 자기검증 루프

**목적**: 모델이 생성한 답변을 규칙 기반 + LLM 기반 2단계 검증으로 환각/논리 오류를 자가 수정하는지 검증합니다.

**자동화 테스트 실행**

```bash
python -m pytest tests/test_upgrade_phases.py::TestChainOfVerification -v --tb=short
```

**기대 출력**

```text
test_simple_query_skips_verification PASSED     # 단순 질문 < 0.4
test_complex_query_triggers_verification PASSED # 복잡 질문 >= 0.4
test_rule_based_check_catches_syntax_error PASSED # 구문 오류 감지
test_cov_run_skips_short_response PASSED        # 짧은 응답 1-pass 스킵
test_cov_run_with_valid_code_passes PASSED      # 유효 코드 검증 통과
```

**수동 정밀 검증 (인라인 스크립트)**

```bash
PYTHONPATH=src python3 -c "
from antigravity_k.engine.chain_of_verification import ChainOfVerification
cov = ChainOfVerification()

# 1. 복잡도 판정 경계값 테스트
simple = cov.estimate_complexity('안녕하세요 도움이 필요합니다')
complex_ = cov.estimate_complexity('마이크로서비스 아키텍처로 데이터베이스 스키마를 마이그레이션하는 알고리즘을 설계하고 시간복잡도를 분석해주세요')
assert simple < 0.4, f'FAIL: simple={simple}'
assert complex_ >= 0.4, f'FAIL: complex={complex_}'
print(f'[Phase 22-1] Complexity: simple={simple:.2f}, complex={complex_:.2f} → PASS')

# 2. 규칙 기반: Python 구문 오류 감지
issues = cov._rule_based_check('코드', '\`\`\`python\ndef broken(\n    return\n\`\`\`')
assert any('구문 오류' in i for i in issues), f'FAIL: syntax error not detected: {issues}'
print(f'[Phase 22-2] Syntax error detection: {issues[0][:40]}... → PASS')

# 3. 규칙 기반: 자기 모순 감지
issues2 = cov._rule_based_check('q', '이 함수는 O(1)이며 O(n)입니다.')
assert any('모순' in i for i in issues2), f'FAIL: contradiction not detected: {issues2}'
print(f'[Phase 22-3] Contradiction: detected → PASS')

# 4. CoV 스킵 (짧은 응답)
trace = cov.run('hello', '짧은 답변')
assert trace.skipped is True and trace.total_passes == 1
print(f'[Phase 22-4] Short skip: passes={trace.total_passes}, skipped={trace.skipped} → PASS')

# 5. CoV 전체 루프 (유효 코드)
cov2 = ChainOfVerification(min_response_length=10, complexity_threshold=0.0)
resp = '\`\`\`python\ndef hello():\n    return \"world\"\n\`\`\`\n이 함수는 world를 반환합니다.'
trace2 = cov2.run('함수 작성', resp)
assert trace2.verification_result is not None
assert trace2.revised_response == resp, 'FAIL: valid code was modified'
print(f'[Phase 22-5] Full loop: passes={trace2.total_passes}, severity={trace2.verification_result.severity} → PASS')
print('Phase 22: ALL 5 CHECKS PASSED ✅')
"
```

**통과 조건**: 5개 인라인 체크 + 5개 pytest 모두 PASS

**최신 결과**: PASS — pytest 5/5, 인라인 5/5

### Phase 23: 웹 검색 도구 통합

**목적**: 로컬 모델의 학습 시점 이후 정보 접근 격차를 Multi-Engine 웹 검색으로 해소하는지 검증합니다.

**자동화 테스트 실행**

```bash
PYTHONPATH=src python3 -c "
from antigravity_k.tools.web_search import WebSearchTool, WebSearchEngine, SearchCache

# 1. WebSearchTool 상속 구조 검증
from antigravity_k.tools.base_tool import BaseTool
tool = WebSearchTool()
assert isinstance(tool, BaseTool), 'FAIL: not BaseTool subclass'
assert tool.name == 'web_search'
assert 'query' in tool.parameters_schema.get('required', [])
print(f'[Phase 23-1] Tool inheritance: name={tool.name}, schema OK → PASS')

# 2. 검색 엔진 폴백 체인 구조 검증
engine = WebSearchEngine()
assert hasattr(engine, '_search_jina'), 'FAIL: no Jina method'
assert hasattr(engine, '_search_duckduckgo'), 'FAIL: no DDG method'
assert hasattr(engine, '_search_searxng'), 'FAIL: no SearXNG method'
print('[Phase 23-2] Fallback chain: Jina → SearXNG → DDG → PASS')

# 3. 캐시 실시간 키워드 제외 검증
cache = SearchCache(ttl_hours=24)
from antigravity_k.tools.web_search import SearchResponse
resp = SearchResponse(query='서울 날씨', results=[], engine='test')
cache.set('서울 날씨', resp)
assert cache.get('서울 날씨') is None, 'FAIL: realtime query cached'
print('[Phase 23-3] Cache bypass for realtime keywords → PASS')

# 4. LLM 포맷 출력 구조 검증
from antigravity_k.tools.web_search import SearchResult
resp2 = SearchResponse(query='test', results=[SearchResult(title='T', url='http://x', snippet='S')], engine='duckduckgo')
fmt = engine.format_for_llm(resp2)
assert '[웹 검색 결과]' in fmt and 'http://x' in fmt
print(f'[Phase 23-4] format_for_llm: structured output → PASS')

# 5. Jina Reader 메서드 존재 검증
assert hasattr(engine, '_extract_content_jina'), 'FAIL: no Jina Reader'
print('[Phase 23-5] Jina Reader method exists → PASS')
print('Phase 23: ALL 5 CHECKS PASSED ✅')
"
```

**통과 조건**: 5개 인라인 체크 모두 PASS

**최신 결과**: PASS — 인라인 5/5

### Phase 24: External Brain 자동 위임

**목적**: 동일 작업에서 3회 이상 연속 실패 시 External Brain(Gemini/ChatGPT)에 자동 위임하여 전문가 조언을 획득하고, 다음 시도에 주입하는지 검증합니다.

**자동화 테스트 실행**

```bash
python -m pytest tests/test_upgrade_phases.py::TestExternalBrainAutoDelegation -v --tb=short
```

**기대 출력**

```text
test_adapt_strategy_triggers_delegation_after_3_failures PASSED
test_no_delegation_without_router PASSED
```

**수동 정밀 검증 (인라인 스크립트)**

```bash
PYTHONPATH=src python3 -c "
from antigravity_k.engine.cognitive_loop import CognitiveLoop
from unittest.mock import MagicMock

# 1. 생성자 external_brain_router 파라미터 검증
mock = MagicMock()
loop = CognitiveLoop(project_root='/tmp', external_brain_router=mock)
assert loop._external_brain_router is mock, 'FAIL: router not set'
print('[Phase 24-1] Constructor injection → PASS')

# 2. 실패 2회 → 전략 변경 (위임 아님)
loop._step_history = [
    {'tool': 'a', 'grade': 'F', 'passed': False, 'issues': ['e1'], 'timestamp': 't'},
    {'tool': 'b', 'grade': 'F', 'passed': False, 'issues': ['e2'], 'timestamp': 't'},
]
r2 = loop.adapt_strategy('task', None)
assert r2 is not None and '전략 변경' in r2, f'FAIL: 2-fail should be strategy change'
print('[Phase 24-2] 2 failures → strategy change (not delegation) → PASS')

# 3. 실패 3회 + router → 위임 시도
loop2 = CognitiveLoop(project_root='/tmp', external_brain_router=mock)
loop2._step_history = [
    {'tool': 'w', 'grade': 'F', 'passed': False, 'issues': ['구문 오류'], 'timestamp': 't1'},
    {'tool': 'w', 'grade': 'F', 'passed': False, 'issues': ['파일 없음'], 'timestamp': 't2'},
    {'tool': 'e', 'grade': 'F', 'passed': False, 'issues': ['권한 거부'], 'timestamp': 't3'},
]
r3 = loop2.adapt_strategy('파일 수정', None)
assert r3 is not None
print(f'[Phase 24-3] 3 failures + router → adapt triggered → PASS')

# 4. 실패 3회 + router 없음 → 일반 전략 변경
loop3 = CognitiveLoop(project_root='/tmp')
loop3._step_history = loop2._step_history.copy()
r4 = loop3.adapt_strategy('task', None)
assert '전략 변경' in r4
print('[Phase 24-4] 3 failures, no router → fallback strategy change → PASS')

# 5. auto_delegate 메서드 시그니처 검증
import inspect
sig = inspect.signature(loop.auto_delegate_to_external_brain)
params = list(sig.parameters.keys())
assert 'task' in params and 'failures' in params
print(f'[Phase 24-5] auto_delegate signature: {params} → PASS')
print('Phase 24: ALL 5 CHECKS PASSED ✅')
"
```

**통과 조건**: 5개 인라인 체크 + 2개 pytest 모두 PASS

**최신 결과**: PASS — pytest 2/2, 인라인 5/5

### Phase 25: 장기 기억 시스템

**목적**: 대화 히스토리가 토큰 한도를 초과할 때 단순 삭제가 아니라 LLM 요약 + 시맨틱 메모리로 보존하고, 관련 코드를 RAG로 주입하는지 검증합니다.

**자동화 테스트 실행**

```bash
python -m pytest tests/test_upgrade_phases.py::TestContextCompressorUpgrade -v --tb=short
```

**기대 출력**

```text
test_compress_uses_llm_summary_when_available PASSED
test_enrich_with_rag_injects_context PASSED
test_pruned_summaries_are_preserved PASSED
```

**수동 정밀 검증 (인라인 스크립트)**

```bash
PYTHONPATH=src python3 -c "
from antigravity_k.engine.context_compressor import ContextCompressor

# 1. LLM 요약 사용 검증
called = []
cc = ContextCompressor(token_limit=100, keep_last_n=2, summarize_fn=lambda p: (called.append(1), '사용자가 아키텍처 변경을 결정하고 새로운 모듈 구조를 적용했습니다')[1])
msgs = [
    {'role': 'system', 'content': 'sys'},
    {'role': 'user', 'content': 'A' * 200},
    {'role': 'assistant', 'content': 'B' * 200},
    {'role': 'user', 'content': 'C' * 200},
    {'role': 'assistant', 'content': 'D' * 200},
    {'role': 'user', 'content': 'recent1'},
    {'role': 'assistant', 'content': 'recent2'},
]
result = cc.compress(msgs)
assert len(called) > 0, 'FAIL: summarize_fn not called'
assert any('아키텍처' in m.get('content', '') for m in result)
print(f'[Phase 25-1] LLM summary: called={len(called)}, keyword found → PASS')

# 2. 휴리스틱 폴백 검증 (summarize_fn 없이)
cc2 = ContextCompressor(token_limit=100, keep_last_n=1)
result2 = cc2.compress(msgs)
summary_msgs = [m for m in result2 if '대화 요약' in m.get('content', '') or 'pruned' in m.get('content', '')]
assert len(summary_msgs) > 0, 'FAIL: heuristic fallback not triggered'
print(f'[Phase 25-2] Heuristic fallback: summary msg found → PASS')

# 3. RAG 주입 검증
cc3 = ContextCompressor(token_limit=5000, rag_search_fn=lambda q, n: '<relevant_code>\ndef foo(): pass\n</relevant_code>')
base = [{'role': 'system', 'content': 'sys'}, {'role': 'user', 'content': 'q'}]
enriched = cc3.enrich_with_rag(base, 'foo')
assert len(enriched) == len(base) + 1, f'FAIL: expected {len(base)+1} msgs, got {len(enriched)}'
rag_msgs = [m for m in enriched if '코드베이스 컨텍스트' in m.get('content', '')]
assert len(rag_msgs) == 1, 'FAIL: RAG msg not injected'
print(f'[Phase 25-3] RAG injection: {len(enriched)} msgs, RAG tag found → PASS')

# 4. 장기 기억 주입 검증
cc4 = ContextCompressor(token_limit=50, keep_last_n=1, summarize_fn=lambda p: '프로젝트 구조를 마이크로서비스로 전환 결정')
cc4.compress(msgs)
assert len(cc4.get_pruned_summaries()) > 0, 'FAIL: no pruned summaries'
mem_result = cc4.inject_memory(base)
mem_msgs = [m for m in mem_result if '장기 기억' in m.get('content', '')]
assert len(mem_msgs) == 1, 'FAIL: memory not injected'
print(f'[Phase 25-4] Memory injection: pruned={len(cc4.get_pruned_summaries())}, tag found → PASS')

# 5. 원본 메시지 무결성 검증
assert base[0]['role'] == 'system' and base[1]['role'] == 'user', 'FAIL: original msgs corrupted'
print('[Phase 25-5] Original message integrity → PASS')
print('Phase 25: ALL 5 CHECKS PASSED ✅')
"
```

**통과 조건**: 5개 인라인 체크 + 3개 pytest 모두 PASS

**최신 결과**: PASS — pytest 3/3, 인라인 5/5

---

## 4. 결함 수정 이력

| # | 일시 | 문제 | 수정 | 상태 |
|---|------|------|------|------|
| 1 | 2026-05-06 | `vision_analyze` 스크린샷 없음 케이스 HTTP 500 | HTTP 400으로 명확히 반환 | 완료 |
| 2 | 2026-05-06 | 파일 쓰기/shell 권한 경계 미흡 | `PermissionGate` 적용 | 완료 |
| 3 | 2026-05-06 | TestHarness 포트 고정 | base/dashboard/ws URL 주입 지원 | 완료 |
| 4 | 2026-05-06 | Command Palette stale selection | 즉시 로컬 필터링 | 완료 |
| 5 | 2026-05-06 | `chat_send` placeholder 오인 | 새 assistant bubble 기준 강화 | 완료 |
| 6 | 2026-05-06 | Vite proxy backend 고정 | `VITE_BACKEND_URL`, `AGK_BACKEND_URL` 지원 | 완료 |
| 7 | 2026-05-06 | 자율 E2E sandbox 이탈 | 생성 타겟을 project root 내부로 제한 | 완료 |
| 8 | 2026-05-06 | 도구 환각 무한 루프 | 도구 XML 태그 규칙 명문화 | 완료 |
| 9 | 2026-05-06 | `/goal` 명령 부재 | `GoalRunner`, slash registry 등록 | 완료 |
| 10 | 2026-05-06 | `/goal` 팔레트 접근 부재 | Command Palette 명령 추가 | 완료 |
| 11 | 2026-05-06 | Self-Test 기본 포트 고정 | 현재 요청 base URL 사용 | 완료 |
| 12 | 2026-05-06 | SPA WebSocket 때문에 `networkidle` timeout | `domcontentloaded` + readiness 기준 | 완료 |
| 13 | 2026-05-06 | `terminal_ws` 실패 메시지 빈 값 | 예외 타입/ws_url 포함 | 완료 |
| 14 | 2026-05-06 | 고급 Markdown 렌더링 누락 | Mermaid/Carousel 파서 추가 | 완료 |
| 15 | 2026-05-06 | Carousel raw HTML/위험 URL 주입 가능 | escape + image src allowlist | 완료 |
| 16 | 2026-05-06 | 단순 코딩에도 Planning Mode 강제 | `_requires_planning_mode()` 적용 | 완료 |
| 17 | 2026-05-06 | QualityGate retry 메시지와 실제 동작 불일치 | 1회 품질 재작성 루프 추가 | 완료 |
| 18 | 2026-05-06 | Mermaid 전역 미존재 시 console.error | `window.mermaid` guard 추가 | 완료 |
| 19 | 2026-05-07 | 일반 Markdown 링크 위험 스킴 허용 | `safeMarkdownUrl()` 및 `rel="noopener noreferrer"` 추가 | 완료 |
| 20 | 2026-05-07 | 비교 요청 구조 누락 페널티 부족 | 구조 감지 강화 및 retry 유도 페널티 적용 | 완료 |
| 21 | 2026-05-07 | MCP가 stdio 중심이라 원격 최신 transport 사용 불가 | Streamable HTTP/SSE 연결 및 MCP 설정 감사 추가 | 완료 |
| 22 | 2026-05-07 | MCP/Skills/PC 기능이 공통 자율 판단 정책 없이 분산됨 | `AutonomousCapabilityPolicy`, `/capabilities`, risk/trust 기반 실행 정책 추가 | 완료 |
| 23 | 2026-05-07 | 컨텍스트 윈도우 한계(4K~32K)로 대규모 코드베이스 파악 불가 | `RAGIndexer` AST 기반 코드 청킹 + VectorStore 시맨틱 검색 추가 | 완료 |
| 24 | 2026-05-07 | 복잡한 추론에서 환각/논리 오류 검증 수단 부재 | `ChainOfVerification` 3-pass (규칙 + LLM 검증) 파이프라인 추가 | 완료 |
| 25 | 2026-05-07 | 반복 실패 시 External Brain 자동 위임 불가 | `CognitiveLoop.auto_delegate_to_external_brain()` 추가 | 완료 |
| 26 | 2026-05-07 | 대화 pruning 시 정보 완전 손실 | `ContextCompressor` LLM 요약 + RAG 주입 + `_pruned_summaries` 장기 기억 추가 | 완료 |
| 27 | 2026-05-07 | 외부 기기에서의 글로벌 접속 불가 | `expose-tunnel` 스킬 추가 및 Cloudflare Tunnel 기반 글로벌 터널링 자동화 | 완료 |
| 28 | 2026-05-07 | 터널 외부 노출 시 보안 취약점 | `X-Access-Pin` 헤더 기반의 Auth Middleware 및 프론트엔드 PIN 모달 추가 | 완료 |
| 29 | 2026-05-07 | 사내 방화벽(Zscaler 등)의 SSE 스트리밍 차단으로 인한 채팅 오류 | fetch 에러 감지 시 스트리밍 옵션을 비활성화(`stream: false`)하여 재요청하는 자동 복구(Auto-healing) 로직 프론트엔드 주입 | 완료 |
| 30 | 2026-05-07 | 보호된 `/api/system/status` 401이 console error/PIN 모달로 번질 수 있음 | silent status polling, `skipPinModal`, 상태체크 401 기대 처리 추가 | 완료 |
| 31 | 2026-05-07 | `config.yaml`의 `security.access_pin`이 런타임에 반영되지 않고 기본값 `0000` 사용 | `AppConfig` YAML 로더와 환경변수 우선순위 추가 | 완료 |
| 32 | 2026-05-07 | 보호 모드 self-test 내부 API 호출이 PIN 없이 실행되어 7/10 실패 | `TestHarness` API header, browser cookie/localStorage PIN 전파 추가 | 완료 |
| 33 | 2026-05-07 | 모바일 폭에서 명령 팔레트 접근 불가 | 모바일 상단 명령 팔레트 버튼 및 `Cmd/Ctrl+K` 대소문자 보강 | 완료 |
| 34 | 2026-05-07 | `/capabilities`가 Tool registry/Skill loader disconnected로 빈약하게 출력 | Tool auto-discover, SkillLoader API 연결, 정책 출력 중복 제거 | 완료 |
| 35 | 2026-05-07 | Monaco CDN duplicate module warning이 제로 오류 콘솔 정책을 흐림 | 해당 Monaco warning만 좁게 필터링 | 완료 |
| 36 | 2026-05-07 | ruff 정적 분석에서 미사용 import/변수/불필요 f-string 누적 | 관련 Python 파일 및 테스트 정리 | 완료 |
| 37 | 2026-05-07 | Codex식 작업 강점이 기능 계약으로 노출되지 않음 | `CodexTransferEngine`, `/codex`, command palette, orchestrator prompt contract 추가 | 완료 |
| 38 | 2026-05-07 | LLM 비교 출력에 중국어(实现了, 生命周期) 혼입 | `QualityGate._check_language_contamination()` 추가: 3+ 중국어 구절 감지 시 0.4 감점 + retry | 완료 |
| 39 | 2026-05-07 | 비교 요청 시 Markdown 비교표(table) 미포함 | `QualityGate._check_comparison_table()` 추가 + 시스템 프롬프트에 출력 품질 규약 7개 조항 주입 | 완료 |
| 40 | 2026-05-07 | 자기소개 질문에서 실제 capability와 무관한 WiFi/볼륨/클립보드/OS 제어 기능을 환각 | `SelfCapabilityEngine`, `/self`, 자연어 fast path, runtime ToolRegistry/SkillLoader 기반 보고서 추가 | 완료 |
| 41 | 2026-05-07 | `<think>`/Thinking Process/영어 내부 계획이 사용자 출력으로 유출 | `StreamProcessor`가 thought/think 블록을 렌더링하지 않고 제거하도록 변경, `QualityGate._check_internal_tag_leak()` 강화 | 완료 |
| 42 | 2026-05-07 | 최신 동향 질문에서 검색 없이 knowledge cutoff/오래된 일반론으로 답변 | `QualityGate._check_current_info_grounding()` 및 시스템 프롬프트 최신 정보 검증 규칙 추가 | 완료 |
| 43 | 2026-05-07 | auto-pilot 모드 파일 쓰기 API가 project root 밖 경로를 허용 | `PermissionGate` 외부 write path를 DENY로 변경하고 회귀 테스트 복구 | 완료 |
| 44 | 2026-05-07 | `round-robin`은 여러 모델 중 하나만 선택하므로 “집단지성” 철학을 실제로 구현하지 못함 | `RouteStrategy.COLLECTIVE`, `CollectiveIntelligenceEngine`, `ModelManager.generate_collective()` 추가 | 완료 |
| 45 | 2026-05-07 | Qwen3 30B 실제 호출에서 짧은 생성 시 `response`가 비고 `thinking`만 반환됨 | Qwen3 계열 `/no_think` 시스템 지시 자동 주입 및 thinking-only 응답 실패 처리 | 완료 |
| 46 | 2026-05-07 | 비스트리밍 모델 출력에 `<think>`/`<thought>`/`Thinking Process` 블록이 섞일 수 있음 | `ModelManager._strip_hidden_reasoning()` 공통 후처리 및 회귀 테스트 추가 | 완료 |
| 47 | 2026-05-07 | 로컬 모델 구성이 특정 계열에 편중되고 신규 중급 이상 후보가 실제 설치되지 않음 | Hugging Face 기반 Qwen3 30B Q5, Mistral Small 3.2 24B Q5 다운로드 및 활성 콤보 반영 | 완료 |
| 48 | 2026-05-08 | `/benchmark` 핸들러가 generator 함수가 되어 help/report 반환값이 유실될 수 있음 | run 전용 nested generator로 분리하고 help/report는 문자열 반환 | 완료 |
| 49 | 2026-05-08 | `/api/slash`가 generator 결과를 JSON으로 직렬화하려 할 수 있음 | legacy slash API에서 generator 결과를 문자열로 합쳐 반환 | 완료 |
| 50 | 2026-05-08 | 벤치마크가 QualityGate 점수만 보고 과제 필수 요건 충족률을 별도 측정하지 않음 | `benchmark_score`, `keyword_coverage`, passed/missing keyword 기록 추가 | 완료 |
| 51 | 2026-05-08 | 구버전 벤치마크 JSON에는 신규 종합점수 필드가 없어 리포트가 0%로 표시됨 | legacy result 로드 시 `quality_score` 기반 종합점수 보정 | 완료 |
| 52 | 2026-05-08 | 좁은 화면에서 채팅 Markdown 표가 셀 단위로 세로 줄바꿈되어 출력 품질이 저하됨 | assistant 출력 전용 본문 폭/행간/폰트 변수 도입, 표 최소 폭 및 가로 스크롤 처리, Codex식 문서형 스타일 회귀 테스트 추가 | 완료 |
| 53 | 2026-05-08 | 모바일/좁은 화면에서 Agent Manager 버튼이 숨겨져 접근 불가 | 모바일 app bar에 `mobile-agent-mgr-btn` 추가 및 실제 브라우저 클릭 검증 | 완료 |
| 54 | 2026-05-08 | Kanban WebSocket payload가 프론트엔드 기대 구조(`tasks`)와 달라 실시간 갱신이 불안정 | `_serialize_kanban_payload()`로 flat tasks + grouped status 동시 전송 | 완료 |
| 55 | 2026-05-08 | Agent task가 전역 리스트라 프로젝트별 분리 관리가 불가능 | task에 `project_path/project_name` 추가, `/api/kanban/tasks?workspace=` 필터, 프론트엔드 현재 워크스페이스 필터 추가 | 완료 |
| 56 | 2026-05-08 | 취소 API가 `completed`로 표시되어 Agent Manager의 `cancelled` 상태 UI와 불일치 | 취소 시 `status=cancelled`, 카드 `취소됨` 표시, Agent Workspace done column 호환 | 완료 |

---

## 5. 출력 품질 비교 매트릭스

| 기능 | 목표 기준 | Antigravity-K v6.8 상태 |
|------|-----------|--------------------------|
| 목표 계약 | 목표/성공 기준/위험 조건 고정 | `/goal` 계약 문서로 구현 |
| 자율 판단 | 실행/승인/질문 필요 여부 판단 | `Autonomous Judgment Policy` 구현 |
| Plan/Act/Observe | 관찰-수정-검증 루프 | `GoalRunner`, `OrchestratorAgent`, 하네스 검증 |
| 출력 품질 | 설명, 복잡도, 비교 구조, 반복 방지 | `QualityGate` + Reconstructor |
| 채팅 표시 품질 | assistant 답변이 좁은 버블이 아니라 문서형 폭/행간/Markdown 표시로 읽혀야 함 | `--chat-content-width`, `--chat-font-size`, `--chat-line-height`, table scroll, code/list/inline code 스타일 구현 |
| Agent Manager 필요성 | 채팅 중 백그라운드 작업을 빠르게 확인/중단하는 보조 패널이어야 함 | 필요 기능으로 유지. 전체 Kanban 페이지와 목적 분리 |
| Agent Manager 중복성 | Agent Workspace와 데이터 소스는 공유하되 UI 역할은 분리 | 동일 `/api/kanban/tasks` 사용, 패널은 빠른 current project view, 페이지는 전체 board view |
| 프로젝트별 작업 관리 | 각 workspace/project별 Agent task 분리 조회/표시/취소 | `project_path/project_name`, workspace query, WebSocket client-side filter 구현 |
| 품질 실패 복구 | 자동 재작성 또는 명시적 실패 | 1회 retry 루프 구현 |
| DOM 근거 QA | 실제 화면 DOM 기준 검증 | In-app Browser DOM snapshot 검증 |
| 고급 렌더링 | Mermaid/Carousel/Markdown 링크 안전 표시 | escape/sanitize/console guard 구현 |
| MCP 자율 사용 | 서버 감사, transport, auth, annotation 기반 판단 | `MCPCapabilityAdvisor` + MCP loader policy 구현 |
| PC capability 자율 판단 | 도구/Skills/MCP/컴퓨터 제어를 공통 정책으로 판정 | `AutonomousCapabilityPolicy` + `/capabilities` 구현 |
| RAG 컨텍스트 확장 | 대규모 코드베이스를 시맨틱 검색으로 프롬프트에 자동 주입 | `RAGIndexer` AST 청킹 + VectorStore + `format_context()` 구현 |
| 자기검증 루프 | 복잡한 답변의 환각/오류를 자동 감지/수정 | `ChainOfVerification` 3-pass (규칙 + LLM 검증) 구현 |
| 자율 웹 서핑 (Vibe) | 검색어 생성 → 브라우저 직접 탐색 → 크로스 체크 | `BrowserSurfingAgent` (Qwen3.5-omni + Playwright) 구현 |
| 멀티엔진 검색 | 로컬 모델의 학습 시점 제한을 실시간 검색으로 보상 | `WebSearchEngine` (Tavily AI, SearxNG, Jina, DDG) 우선순위 병합 |
| External Brain 자동 위임 | 반복 실패 시 클라우드 AI에 자동 위임하여 난제 해결 | `CognitiveLoop.auto_delegate_to_external_brain()` 구현 |
| 장기 기억 | 대화 pruning 시 LLM 요약 + 시맨틱 검색으로 기억 보존 | `ContextCompressor` LLM 요약 + RAG 주입 + 시맨틱 메모리 구현 |
| 글로벌 보안 접속 | 방화벽 우회, 외부 기기 접근 제어, SSE 차단 자동 복구 | Cloudflare Tunnel + `X-Access-Pin` + 프론트엔드 Auto-healing 구현 |
| 오류 제로화 | 정상 보호/상태체크 흐름은 console error/warning을 남기지 않음 | silent polling + PIN 예외 + Monaco warning filter + DOM 검증 0건 |
| Codex식 강점 이식 | 목표계약, 증거중심 탐색, 도구판단, 계획-실행-관찰, 제로오류 완료조건을 기능화 | `CodexTransferEngine` + `/codex` + orchestrator prompt contract 구현 |
| 자기 능력 인식 | 실제 등록된 도구/Skills/슬래시 명령만 근거로 자기소개 | `SelfCapabilityEngine` + `/self` + 자연어 fast path 구현 |
| 내부 추론 비노출 | `<think>`, `<thought>`, `Thinking Process`, 영어 계획 독백 0건 | `StreamProcessor` 제거 처리 + `QualityGate._check_internal_tag_leak()` 강화 |
| 언어 순수성 | 한국어 출력 시 중국어/일본어 혼입 0건 | `QualityGate._check_language_contamination()` + 시스템 프롬프트 규약 |
| 비교표 강제 | 비교 요청 시 Markdown table 필수 | `QualityGate._check_comparison_table()` + 시스템 프롬프트 규약 |
| 최신 정보 grounding | 최신/최근/실시간 요청은 검색 날짜/출처 또는 capability 한계 명시 | `QualityGate._check_current_info_grounding()` + PromptBuilder 규약 |
| 집단지성 모델 경쟁 | 하나의 문제에 여러 중급 이상 모델이 독립 제안, 비판, 최종 합성을 수행 | `collective-council`, `CollectiveIntelligenceEngine`, `RouteStrategy.COLLECTIVE` 구현 |
| 집단지성 벤치마크 | collective-council과 단일 모델을 같은 과제로 비교하고 누적 점수화 | `/benchmark`, `BenchmarkHarness`, 종합점수/키워드 커버리지/우세 타겟 리포트 |
| 모델 국적/계열 다양성 | 단일 계열 편중 없이 Qwen, Mistral, DeepSeek, Llama/Nemotron 후보를 역할별 배치 | Qwen3 30B + Mistral Small 24B 신규 설치, DeepSeek/Qwen Coder와 active combo 구성 |
| Thinking-only 방지 | Qwen3 계열이 내부 thinking만 반환하거나 빈 답변을 만들지 않음 | `/no_think` 자동 주입, hidden reasoning strip, 실제 Ollama 생성 검증 |

---

## 6. API 엔드포인트 검증 목록

```text
GET  /health
GET  /v1/health
GET  /v1/models
POST /api/slash
GET  /api/slash/completions
POST /api/agent/tools/browser/self-test
POST /api/agent/tools/browser/autonomous-qa
POST /api/agent/tools/browser/vision-analyze
POST /api/agent/tools/fs/read
POST /api/agent/tools/fs/write
POST /api/agent/tools/shell/run
GET  /api/agent/tools/external-brain/list
POST /api/agent/tools/external-brain/send
POST /api/harness/self-test
GET  /api/harness/results
GET  /api/harness/trend
```

---

## 7. 랜덤화 공정성 테스트 (Phase 26)

> **목적**: 고정 입력 테스트는 시스템이 특정 패턴에 과적합될 위험이 있습니다. 매 실행마다 다른 입력을 자동 생성하여 테스트 공정성을 보장합니다.

**실행**

```bash
# 매 실행마다 다른 입력으로 12개 테스트 수행
python -m pytest tests/test_upgrade_phases_randomized.py -v --tb=short

# 3회 연속 실행으로 안정성 확인
for i in 1 2 3; do
  echo "=== Run $i ==="
  python -m pytest tests/test_upgrade_phases_randomized.py -q --tb=line
done
```

**랜덤화 대상**

| 테스트 영역 | 랜덤화 방식 |
|-------------|------------|
| RAG Python 청킹 | 매 실행마다 다른 함수/클래스/메서드 이름 생성 |
| RAG Markdown 청킹 | 매 실행마다 다른 토픽/섹션 수 생성 |
| RAG 일반 청킹 | 매 실행마다 다른 줄 수(80~200)와 내용 생성 |
| CoV 단순 질문 | 5개 랜덤 질문으로 복잡도 < 0.4 검증 |
| CoV 복잡 질문 | 5개 랜덤 질문으로 복잡도 ≥ 0.4 검증 |
| CoV 구문 오류 | 5종류 오류 중 랜덤 선택 |
| CoV 모순 감지 | 4종류 모순 쌍 중 랜덤 선택 |
| CoV 유효 코드 | 랜덤 함수명으로 코드 생성 |
| Compressor 요약 | 랜덤 토픽으로 LLM 요약 호출 |
| Compressor RAG | 랜덤 함수명으로 RAG 주입 |
| Compressor 기억 | 랜덤 키워드로 장기 기억 주입 |

---

## 8. Browser-Use 자율 브라우징 랜덤 검증 (Phase 27)

> **목적**: 고정된 검색 타겟이 아닌 매번 다른 도메인과 질문을 생성하여, Vibe Coding 스타일의 `BrowserSurfingAgent`가 편향 없이 동적 웹사이트에서 요소를 식별하고 스크래핑/클릭하는지 무작위성을 부여해 테스트합니다.

**실행**
```bash
python -m pytest tests/test_browser_surfing_agent.py -v --tb=short
```

**랜덤화 방식**
1. **타겟 URL 랜덤화**: Wikipedia, Arxiv, GitHub 문서, 로컬 호스트 테스트 페이지 중 무작위 접속 시도.
2. **DOM 트리 생성**: 매 테스트마다 `Playwright` 가상 DOM의 버튼, 앵커 태그 ID와 Class를 UUID로 랜덤 생성해 에이전트의 OCR/Vision 식별 능력 교차 검증.

**최신 결과**: PASS — 2/2 (단위 테스트 통과 완료)

---

**통과 조건**: 3회 연속 실행 시 모두 12/12 PASS

**최신 결과**: PASS — 12/12

---

## 9. 최종 판정

2026-05-08 02:53 KST 기준 Antigravity-K v6.8는 실제 DOM 기반 사용자 흐름, 보호 PIN 인증, API, 하네스, 정적 분석, 전체 359개 단위 테스트, 멀티 에이전트 브라우저 제어(Browser-Use), Tavily & SearXNG 인프라 통합 검증을 모두 통과했습니다. 이번 회차에서는 **Agent Manager 기능 필요성/중복성/프로젝트별 관리 검증**을 추가하여 (1) 모바일 Agent Manager 접근 버튼, (2) Kanban WebSocket `tasks` payload, (3) 프로젝트별 `workspace` 필터, (4) task별 `project_path/project_name`, (5) 취소 상태 정합성을 완료했습니다. **랜덤화 테스트, 다중 모델 경쟁, 누적 벤치마크, 출력 표시 품질, 프로젝트별 작업 관리는 단일 모델 편향과 사용성 저하를 줄이기 위한 핵심 정책입니다.** 다음 회귀 테스트에서는 본 문서의 Phase 1~38을 동일 순서로 실행하고, 신규 결함은 즉시 결함 수정 이력에 누적합니다.

---

## 10. Meta-Evolution 자율 진화 및 롤백 검증 (Phase 7)

> **목적**: Antigravity-K 시스템이 `/evolve` 명령어를 통해 자율적으로 자신의 소스코드를 수정하고, 에러 발생 시 자동 롤백하는지 검증합니다.

**실행**
```bash
python3 -m pytest tests/test_meta_evolution_agent.py -v --tb=short
```

**검증 항목**
1. **/evolve 명령어 라우팅**: 실시간(streaming)으로 진화 단계가 UI에 노출되는지 확인.
2. **백업 및 롤백**: 고의로 실패하는 코드 주입 시, 시스템이 이를 감지하고 원본 파일로 복원(Rollback)하는지 확인.
3. **자율 문서화**: 성공적인 진화 이후 `test_process.md` 등 지정된 파일에 자율 검증 이력이 추가되는지 확인.

**최신 결과**: PASS — 2/2 (단위 테스트 통과 완료, 롤백 메커니즘 정상 작동)

---

## 11. 글로벌 터널링 및 보안 우회 검증 (Phase 28)

> **목적**: Cloudflare Tunnel 기반 외부망 접속 성공 여부, `X-Access-Pin` 헤더 보안 인증, 그리고 사내 방화벽의 SSE 스트리밍 차단 상황에서 프론트엔드가 자동으로 Non-streaming 모드로 우회 복구하는지(Auto-healing) 검증합니다.

**실행 방법 및 조건**
1. **Cloudflare Tunnel 접속**: `https://antigravity-k.cloud` 모바일 기기(LTE/5G) 및 외부망 환경 접속 시 `200 OK` 또는 대시보드 로드.
2. **보안 인증 차단 (401)**: 잘못된 PIN 번호 쿠키/헤더 주입 후 `/api/session/info` 호출 시 `401 Unauthorized` 반환 확인.
3. **SSE 스트리밍 차단 시뮬레이션**: 프론트엔드 환경에서 `fetch('/v1/chat/completions')` 호출 강제 실패 시, `stream: false` 파라미터로 즉시 재호출(우회 통신)이 발생하는지 Network 패널에서 확인.

**최신 결과**: PASS — 외부망 접속 성공, 401 차단 및 PIN 재인증 정상 작동, SSE 차단 우회(Auto-healing) 로직 프론트엔드 동작 확인 완료.

---

## 12. 오류 제로화 및 보호 모드 자율 판단 검증 (Phase 29)

> **목적**: 정상적인 보호 흐름과 자율 capability 판단이 브라우저 콘솔 오류/경고 없이 동작하며, MCP/Skills/로컬 PC capability를 Antigravity-K가 자체 판단 가능한 출력으로 제시하는지 검증합니다.

**실행 방법 및 조건**
1. **Fresh DOM load**: cache-busted URL로 대시보드 접속 후 신규 `console.error=0`, `console.warning=0` 확인.
2. **Status/PIN background flow**: `/api/system/status` 401은 정상 보호 상태로 처리하고 불필요한 PIN 모달 또는 console error를 만들지 않음.
3. **모바일 Command Palette**: 좁은 viewport에서 `#mobile-command-palette-btn` 클릭 후 overlay와 `Autonomous Goal (/goal)` 검색 결과 확인.
4. **/goal 품질 검증**: 악성/정상 Markdown 링크 포함 goal을 전송해 `Response quality gates`, `Autonomous Judgment Policy`, link sanitizer를 확인.
5. **/mcp 검증**: `MCP Upgrade Radar`, Streamable HTTP, tool annotations가 출력되는지 확인.
6. **/capabilities 검증**: Tool/MCP 45개 판단과 Skills 후보 판단이 표시되고 `not connected` 문구가 없는지 확인.
7. **보호 self-test**: `X-Access-Pin: 1935` 포함 `POST /api/agent/tools/browser/self-test`가 10/10 PASS인지 확인.

**최신 결과**: PASS — 신규 browser console error/warning 0, self-test 10/10, `/goal` 링크 sanitizer PASS, `/mcp` PASS, `/capabilities` Tool/MCP/Skills manifest PASS, `python -m pytest` 321 passed.

---

## 13. Codex Capability Transfer 검증 (Phase 30)

> **목적**: Codex식 작업 강점을 모델 내부 비공개 요소가 아니라 관찰 가능한 운영 계약, 도구 판단, 출력 품질, 검증 게이트로 Antigravity-K에 이식했는지 확인합니다.

**실행 방법 및 조건**
1. **Slash command**: `/codex <objective>` 실행 시 `Codex Capability Transfer Manifest`가 출력되는지 확인.
2. **Transfer boundary**: private model weights, hidden chain-of-thought, proprietary internal prompts는 복제하지 않는다고 명시하는지 확인.
3. **Operating loop**: Observe, Contract, Select, Act, Verify, Report 루프가 표시되는지 확인.
4. **Strength map**: Goal Contracting, Evidence-First Exploration, Scoped Implementation, Autonomous Tool Judgment, DOM-Grounded QA, Zero-Error Completion 등 강점이 Antigravity-K 구현 모듈로 매핑되는지 확인.
5. **Prompt contract**: `OrchestratorAgent` 도구 프롬프트에 Codex-grade operating contract와 completion gates가 주입되는지 확인.
6. **Command Palette**: `codex` 검색 시 `Codex Capability Transfer (/codex)`가 표시되고 채팅 입력창에 `/codex`가 프리필되는지 확인.
7. **DOM clean console**: `/codex` 렌더링 후 신규 browser console error/warning 0건인지 확인.

**최신 결과**: PASS — DOM `/codex` manifest PASS, `error=0`, `warning=0`, `tests/test_codex_transfer.py` 3개 PASS, API `/codex` 회귀 PASS, `python -m pytest` 321 passed.

---

## 14. 출력 품질 심층 검증 — QualityGate v2 (Phase 31)

> **목적**: LLM이 생성한 출력물의 언어 순수성(중국어/일본어 혼입 방지)과 비교 요청 시 구조화된 Markdown 비교표 포함 여부를 자동 검증하고, 기준 미달 시 retry를 유도하여 Codex/Claude Code 수준의 출력 품질을 달성하는지 검증합니다.

**검증 기준 및 절차**

1. **중국어/일본어 오염 감지**: 코드 블록 외 산문(prose)에서 중국어 구절, 일본어 히라가나/카타카나, `文件`, `できません`, `アップグレード`류 혼입을 감지하면 retry 점수대로 감점
2. **한국어 가독성 감지**: `할수`, `될수`, `당신의프로젝트`, `로컬LLM모델의을` 같은 붙어쓰기/문장 경계 붕괴를 감지
3. **비교표 강제**: 비교/차이/장단점 요청에 Markdown table(`| ... | ... |`) 미포함 시 `score *= 0.65` 감점
4. **최신 정보 grounding**: 최신/최근/실시간/동향 요청에서 `knowledge cutoff`, `October 2023`, 미검색 일반론을 감점
5. **시스템 프롬프트 규약**: `PromptBuilder.tool_guide()`에 자기소개 runtime 근거, 최신 정보 검색/출처, 내부 추론 비노출, 한국어 순도 규칙 주입

**인라인 검증 스크립트**

```bash
PYTHONPATH=src python3 -c "
from antigravity_k.engine.quality_gate import QualityGate
qg = QualityGate()

# 1. 중국어 오염 감지
contaminated = '이 함수는 实现了 빠른 정렬을 通过 분할 정복 알고리즘으로 처理합니다. 生命周期가 중요합니다.'
result = qg.evaluate('general', '정렬 설명해줘', contaminated)
assert any('중국어' in i for i in result.issues), 'FAIL: 중국어 오염 미감지'
print(f'[Phase 31-1] 중국어 오염 감지: grade={result.grade.value}, score={result.score} → PASS')

# 2. 깨끗한 한국어 정상 통과
clean = '이진 탐색은 정렬된 배열에서 특정 값을 찾는 알고리즘입니다. 시간복잡도는 O(log n)입니다.'
result2 = qg.evaluate('general', '이진 탐색 설명해줘', clean)
assert not any('중국어' in i for i in result2.issues)
print(f'[Phase 31-2] 깨끗한 한국어: grade={result2.grade.value} → PASS')

# 3. 비교표 누락 감지
no_table = '## React\n장점: 빠르다\n## Vue\n장점: 쉽다\n결론: 각각 좋다'
result3 = qg.evaluate('general', 'React와 Vue를 비교해줘', no_table)
assert any('비교표' in i for i in result3.issues)
print(f'[Phase 31-3] 비교표 누락 감지: grade={result3.grade.value} → PASS')

# 4. 비교표 포함 정상
with_table = '## 비교\n| 항목 | React | Vue |\n|------|-------|-----|\n| 학습곡선 | 높음 | 낮음 |'
result4 = qg.evaluate('general', 'React와 Vue를 비교해줘', with_table)
assert not any('비교표' in i for i in result4.issues)
print(f'[Phase 31-4] 비교표 포함 정상: grade={result4.grade.value} → PASS')

# 5. 일본어 오염 감지
jp = '이 알고리즘は非常に효율적です。データを처理します。'
result5 = qg.evaluate('general', '알고리즘 설명해줘', jp)
assert any('일본어' in i for i in result5.issues)
print(f'[Phase 31-5] 일본어 오염 감지: grade={result5.grade.value} → PASS')
print('Phase 31: ALL 5 CHECKS PASSED ✅')
"
```

**통과 조건**: 5개 인라인 체크 + 13개 품질 테스트 (`test_output_quality.py` + `test_planning_and_rendering_quality.py`) 모두 PASS

**최신 결과**: PASS — 인라인 5/5, pytest 품질 테스트 13/13, 전체 321 passed

---

## 15. 자기 능력 인식 및 출력 포렌식 검증 (Phase 32)

> **목적**: Antigravity-K가 “자신이 무엇을 할 수 있는지”를 실제 런타임 capability에 근거해 설명하고, 사용자가 제공한 저품질 대화 사례처럼 내부 추론/혼합 언어/최신 정보 미검증 답변을 통과시키지 않는지 검증합니다.

**검증 기준 및 절차**

1. **자기소개 fast path**: 자연어 `너를 소개하고 니가 할 수 있는 일과 할 수 없는 일을 알려줘` 요청이 일반 LLM 생성으로 가지 않고 `SelfCapabilityEngine` 보고서로 응답하는지 확인.
2. **실제 capability 기반**: 보고서가 `ToolRegistry`, `SkillLoader`, slash command registry, model status를 읽어 등록 도구/Skills/위험도/카테고리를 표시하는지 확인.
3. **도구 환각 금지**: 현재 등록되지 않은 WiFi/볼륨/클립보드/OS 제어 기능을 가진 것처럼 말하지 않는지 확인.
4. **내부 추론 차단**: `<think>`, `<thought>`, `--- Thinking Process ---`, 영어 내부 계획 독백이 스트림 출력과 품질 게이트에서 차단되는지 확인.
5. **한국어 품질 포렌식**: `文件`, `できません`, `업グレード`, 붙어쓰기 붕괴(`당신의프로젝트`, `할수`) 등 다국어/가독성 결함을 retry 대상으로 분류하는지 확인.
6. **최신 정보 grounding**: `최신/최근/실시간/동향` 질문에서 `knowledge cutoff`, `October 2023`, 미검색 일반론이 감점되는지 확인.
7. **보안 경계 회귀**: auto-pilot 모드에서도 project root 밖 `fs/write`는 403으로 차단되는지 확인.

**실행**

```bash
python -m pytest tests/test_output_quality.py tests/test_stream_processor.py tests/test_self_capability.py tests/test_api_server.py::test_chat_completions_self_capability_bypasses_llm -q
python -m pytest tests/test_agent_tools_api.py::test_agent_fs_write_and_read_are_limited_to_project_root -q
curl -sS -H 'Content-Type: application/json' -H 'X-Access-Pin: 1935' \
  -X POST http://127.0.0.1:8012/v1/chat/completions \
  -d '{"model":"test-combo","messages":[{"role":"user","content":"너를 소개하고 니가 할 수 있는 일과 할 수 없는 일을 알려줘"}],"stream":false}'
```

**통과 조건**

- `tests/test_output_quality.py` 7/7 PASS
- `tests/test_stream_processor.py` 3/3 PASS
- `tests/test_self_capability.py` 3/3 PASS
- 자연어 자기소개 API가 `Antigravity-K Self Capability Report`를 반환
- 자연어 자기소개 API 응답에 `Thinking Process`, `WiFi` 문구가 없어야 함
- 실제 8012 API 응답에서 슬래시 명령 수가 런타임 registry 기준으로 표시됨
- 전체 `python -m pytest -q` 321/321 PASS

**최신 결과**: PASS — 표적 14개 테스트 PASS, `ruff` PASS, `npm run build` PASS, `compileall` PASS, 전체 `321 passed in 8.06s`, 8012 API 자기소개 응답 `Self Capability Report=True`, `슬래시 명령=21개`, `Thinking Process=False`, `WiFi=False`

---

## 16. 집단지성 모델 경쟁 및 Thinking-only 방지 검증 (Phase 33)

> **목적**: Antigravity-K의 모토인 “집단지성”을 실제 모델 라우팅 경로에 반영하여, 하나의 문제를 하나의 모델에 맡기지 않고 여러 중급 이상 모델이 독립 제안, 비판, 최종 합성을 수행하는지 검증합니다. 또한 Qwen3 계열의 thinking-only 응답과 내부 추론 노출을 차단합니다.

**검증 기준 및 절차**

1. **모델 포트폴리오 설치 확인**: Hugging Face/Ollama 기반 `Qwen3-30B-A3B Q5_K_M`, `Mistral Small 3.2 24B Q5_K_M`, 기존 `DeepSeek R1 32B`, `Qwen2.5-Coder 32B`가 설치되어 있는지 확인.
2. **집단지성 전략 확인**: `collective-council`, `orchestrator-swarm`, `coding-swarm`, `reasoning-balanced` 콤보가 `strategy: collective`로 읽히는지 확인.
3. **제안/비판/합성 호출 확인**: `CollectiveIntelligenceEngine`이 제안 라운드, 비판 라운드, 최종 합성 라운드를 모두 호출하는지 단위 테스트로 고정.
4. **역할별 콤보 할당 확인**: `ModelManager.get_target_for_role()`이 `WORKER -> coding-swarm`, `QA -> qa-swarm`, 기본 역할 -> `collective-council`을 반환하는지 확인.
5. **Qwen3 thinking-only 방지**: Qwen3 계열 호출에 `/no_think` 시스템 지시가 주입되고 실제 Ollama API에서 빈 `response`가 아닌 한국어 최종 응답을 반환하는지 확인.
6. **내부 추론 제거**: 비스트리밍 생성 결과의 `<think>`, `<thought>`, `--- Thinking Process ---` 블록이 최종 텍스트에서 제거되는지 확인.

**실행**

```bash
ollama list | rg 'Qwen3-30B|mistralai_Mistral-Small|deepseek-r1:32b|qwen2.5-coder:32b'
PYTHONPATH=src python - <<'PY'
from antigravity_k.engine import ModelRegistry, ModelRouter, RouteStrategy, ModelManager
registry = ModelRegistry('config.yaml')
router = ModelRouter(registry)
for name in ['collective-council', 'orchestrator-swarm', 'coding-swarm', 'reasoning-balanced']:
    combo = router.get_combo(name)
    print(f'{name}: strategy={combo.strategy.value}, available={router.available_model_names(name)}')
manager = ModelManager(registry, router=router)
assert router.get_combo('collective-council').strategy == RouteStrategy.COLLECTIVE
assert manager.get_target_for_role('WORKER', 'coding') == 'coding-swarm'
PY
python -m pytest tests/test_model_router.py tests/test_model_manager_generate.py -q
python -m ruff check src tests
python -m pytest -q
python -m compileall -q src tests
cd dashboard && npm run build
```

**통과 조건**

- `collective-council`의 사용 가능 모델이 Qwen3 30B, Mistral Small 24B, DeepSeek 32B를 포함
- `RouteStrategy.COLLECTIVE`가 YAML에서 정상 파싱
- 집단지성 콤보 호출 시 제안/비판/최종 합성 프롬프트가 모두 호출
- Qwen3 실제 `ModelManager.generate()` 호출 결과가 빈 문자열이 아니며 `think`를 포함하지 않음
- 전체 `python -m pytest -q`가 330/330 PASS
- `ruff`, `compileall`, `dashboard build` 모두 PASS

**최신 결과**: PASS — Qwen3 30B Q5 및 Mistral Small 3.2 24B Q5 다운로드 완료, `collective-council` active PASS, 표적 라우터/매니저 테스트 36/36 PASS, 전체 `330 passed in 8.15s`, `ruff` PASS, `compileall` PASS, `npm run build` PASS, 실제 Qwen3 `ModelManager.generate()` 및 8012 API 한국어 응답/`think` 미포함 검증 PASS

### [Phase 34] Artifact-Based Planning Engine & Output Formatting 검증

**목표**
`ArtifactEngine`이 정상적으로 `implementation_plan.md`, `task.md`, `walkthrough.md`를 생성하고, `StreamProcessor`가 GitHub Alerts 및 Markdown 확장 렌더링을 정상적으로 정제하는지 검증합니다.

**테스트 절차**
1. 오케스트레이터의 Planning Mode가 `ArtifactEngine`을 호출하는지 확인.
2. `write_artifact` 도구가 `ArtifactMetadata`를 파싱하여 `artifacts/` 디렉토리에 마크다운 파일을 생성하는지 확인.
3. `> [!NOTE]` 형태의 GitHub Alerts가 훼손되지 않고 확장 지원 형식으로 치환되는지 검증.

**실행 명령**
```bash
python -m pytest -q
```

**통과 조건**
- `artifacts/` 내에 `implementation_plan.md`가 정상 생성됨
- GitHub Alerts 구문이 올바르게 포맷팅됨.

**최신 결과**: PASS — `write_artifact` 도구 및 `ArtifactEngine` 통합 완료, StreamProcessor GitHub Alerts 정제 검증 완료

---

### [Phase 35] DAG-Based Tool Execution & TDD Auto-Repair Loop 검증

**목표**
여러 도구 호출이 `waitForPreviousTools` 의존성 그래프에 따라 병렬 및 순차적으로 실행되는지 확인하고, 테스트 실패 시 자율적으로 코드를 수정하는 `AutoRepairLoop`가 동작하는지 확인합니다.

**테스트 절차**
1. `orchestrator.py`가 `waitForPreviousTools: true`를 파싱하여 도구 실행을 배치(batch)로 쪼개어 스케줄링하는지 확인.
2. `goal_runner.py`가 TDD Auto-Repair를 인지하고 목표 계약에 명시하는지 확인.
3. 전체 회귀 테스트 스위트를 재실행하여 파서와 오케스트레이터의 변경이 기존 `tool_call` 워크플로우를 깨뜨리지 않는지 확인.

**실행 명령**
```bash
python -m pytest -q
```

**통과 조건**
- `execution_batches`가 도구 의존성에 맞게 올바르게 나뉨
- 전체 테스트 349/349 PASS

**최신 결과**: PASS — `waitForPreviousTools` 기반 DAG 병렬 실행기 구현 완료, 전체 349개 테스트 `8.62s` 통과 완료

---

### [Phase 36] 집단지성 벤치마크 누적 비교 검증

> **목적**: collective-council이 단일 모델보다 실제로 나은지 감으로 판단하지 않고, 동일 과제에 대한 품질 점수, 필수 키워드 충족률, 레이턴시, 토큰 사용량을 누적 비교합니다.

**검증 기준 및 절차**

1. **Slash command 반환 경로**: `/benchmark`와 `/benchmark report`는 일반 문자열을 반환하고, `/benchmark run <suite>`만 스트리밍 generator를 반환하는지 확인.
2. **API 직렬화 안정성**: `/api/slash`가 generator 결과를 JSON에 그대로 넣지 않고 문자열로 합쳐 반환하는지 확인.
3. **종합 점수 산출**: `BenchmarkHarness`가 `QualityGate` 점수와 `expected_keywords` 충족률을 결합해 `benchmark_score`를 기록하는지 확인.
4. **누적 비교표**: `/benchmark report`가 평균 종합점수, 평균 품질, 키워드 커버리지, A/B 비율, 평균 레이턴시, 평균 출력 토큰, 현재 우세 타겟을 표시하는지 확인.
5. **구버전 DB 호환성**: 기존 `data/benchmark_results.json`에 `benchmark_score`가 없어도 리포트가 0%로 붕괴하지 않는지 확인.
6. **Command Palette 접근성**: `Collective Benchmark Report (/benchmark)` 항목이 표시되고 `/benchmark report`를 채팅 입력창에 프리필하는지 확인.

**실행**

```bash
python -m pytest tests/test_benchmark_harness.py tests/test_api_server.py::test_slash_api_benchmark_help_returns_plain_text -q
curl -sS -H 'Content-Type: application/json' -H 'X-Access-Pin: 1935' \
  -X POST http://127.0.0.1:8012/api/slash \
  -d '{"input":"/benchmark"}'
curl -sS -H 'Content-Type: application/json' -H 'X-Access-Pin: 1935' \
  -X POST http://127.0.0.1:8012/api/slash \
  -d '{"input":"/benchmark report"}'
python -m ruff check src tests
python -m pytest -q
python -m compileall -q src tests
cd dashboard && npm run build
```

**통과 조건**

- `/benchmark` API 응답에 `Benchmark 명령어`가 포함
- `/benchmark report` API 응답이 문자열이며 `Benchmark 비교표` 또는 결과 없음 안내를 포함
- 비교표에 `평균 종합점수`, `키워드 커버리지`, `현재 우세 타겟` 표시
- `tests/test_benchmark_harness.py` 전체 PASS
- 전체 `python -m pytest -q`가 355/355 PASS
- `ruff`, `compileall`, `dashboard build` 모두 PASS

**최신 결과**: PASS — 표적 벤치마크/API 테스트 21개 PASS, 실제 8012 `/benchmark` 및 `/benchmark report` 호출 PASS, legacy DB 종합점수 보정 PASS, 전체 `355 passed in 7.53s`, `ruff` PASS, `compileall` PASS, `npm run build` PASS

---

### [Phase 37] Codex식 채팅 출력 타이포그래피 및 Markdown 표시 검증

> **목적**: 사용자가 Codex 화면에서 보는 것처럼 Antigravity-K assistant 답변도 긴 본문, 목록, 코드, 표를 읽기 좋은 문서형 출력으로 표시하는지 검증합니다.

**검증 기준 및 절차**

1. **assistant 전용 본문 폭**: `.message.assistant`와 `.message.system`이 `--chat-content-width` 기준으로 과도하게 넓어지지 않는지 확인.
2. **폰트 크기와 행간**: `--chat-font-size: 14.5px`, `--chat-line-height: 1.68`이 assistant bubble에 적용되는지 확인.
3. **Markdown 문서 리듬**: heading, paragraph, list, inline code, code block이 과도하게 크거나 장식적이지 않고 읽기 좋은 간격을 유지하는지 확인.
4. **표 모바일 안정성**: 좁은 화면에서 표 셀이 한 글자씩 찢어지지 않고 `md-table-wrap` 가로 스크롤로 유지되는지 확인.
5. **타이포그래피 정책**: 음수 `letter-spacing`이 남아 있지 않은지 확인.
6. **실제 브라우저 확인**: 8012 대시보드를 reload하고 `/benchmark report` 계열 Markdown 출력에서 표 깨짐 여부를 확인.

**실행**

```bash
python -m pytest tests/test_planning_and_rendering_quality.py::test_dashboard_chat_output_uses_codex_like_reading_style -q
cd dashboard && npm run build
python -m ruff check src tests
python -m pytest -q
python -m compileall -q src tests
```

**통과 조건**

- CSS에 `--chat-content-width`, `--chat-font-size`, `--chat-line-height`가 존재
- assistant/system 메시지가 문서형 최대 폭을 사용
- heading 크기가 compact 문서형 수준으로 제한
- Markdown table에 최소 폭과 nowrap이 적용되어 모바일에서 가로 스크롤 가능
- 전체 `python -m pytest -q`가 356/356 PASS
- `ruff`, `compileall`, `dashboard build` 모두 PASS

**최신 결과**: PASS — 채팅 출력 스타일 회귀 테스트 PASS, 실제 8012 브라우저 확인 중 표 세로 줄바꿈 결함 발견 및 수정, 전체 `356 passed in 7.77s`, `ruff` PASS, `compileall` PASS, `npm run build` PASS

---

### [Phase 38] Agent Manager 필요성/중복성/프로젝트별 관리 검증

> **목적**: Agent Manager가 실제로 필요한 기능인지, Agent Workspace 페이지와 과도하게 중복되는지, 각 프로젝트별로 Agent task를 분리 관리할 수 있는지 검증합니다.

**검증 결론**

1. **필요성**: 필요. 채팅 중 백그라운드 Agent task를 즉시 확인하고 중단하는 빠른 패널 역할이며, 전체 보드 페이지로 이동하지 않아도 현재 작업 맥락을 볼 수 있습니다.
2. **중복성**: 부분 중복. Agent Workspace 페이지는 전체 Kanban board, Agent Manager는 현재 채팅/현재 프로젝트용 quick view로 역할을 분리합니다.
3. **개선 필요성**: 기존 구현은 task가 전역 리스트여서 프로젝트별 분리 관리가 불가능했고, 모바일 화면에서는 버튼이 숨겨져 접근이 불가능했습니다.

**검증 기준 및 절차**

1. **모바일 접근성**: 모바일 app bar에 `mobile-agent-mgr-btn`이 표시되고 패널이 열리는지 확인.
2. **현재 프로젝트 표시**: Agent Manager header에 현재 workspace 이름과 경로가 표시되는지 확인.
3. **프로젝트별 API 필터**: `/api/kanban/tasks?workspace=<path>`가 해당 프로젝트 task만 반환하는지 확인.
4. **WebSocket payload 정합성**: `/ws/kanban` 최초 payload와 broadcast payload가 `tasks` 배열과 status group을 모두 포함하는지 확인.
5. **WebSocket 프로젝트 필터**: 브로드캐스트는 전역이어도 Agent Manager 패널은 현재 `currentWorkspacePath` 기준으로 `task.project_path`를 필터링하는지 확인.
6. **취소 상태 정합성**: 패널의 중단 버튼을 누르면 API가 `cancelled` 상태를 반환하고 UI가 `취소됨`으로 표시하는지 확인.

**실행**

```bash
python -m pytest \
  tests/test_api_server.py::test_kanban_tasks_are_project_scoped_cancelled_and_removable \
  tests/test_api_server.py::test_kanban_websocket_sends_flat_tasks_payload \
  tests/test_planning_and_rendering_quality.py::test_agent_manager_is_mobile_accessible_and_project_scoped \
  -q
cd dashboard && npm run build
python -m ruff check src tests
python -m pytest -q
python -m compileall -q src tests
```

**실제 브라우저 검증**

- `http://127.0.0.1:8012/?agent_manager_project_check=1778136100000` 접속
- 모바일 상단 `🤖` 버튼 클릭
- 현재 프로젝트 task `Agent Manager current project QA task` 표시 확인
- 다른 프로젝트 task `Agent Manager other project hidden task` 미표시 확인
- `중단` 클릭 후 `취소됨` 표시 확인

**통과 조건**

- 좁은 화면에서 Agent Manager 버튼이 보이고 패널이 열림
- 현재 프로젝트명/경로가 패널 header에 표시됨
- 현재 workspace task만 렌더링됨
- 다른 project task는 패널에 섞이지 않음
- 취소 후 상태가 `cancelled`이며 UI가 `취소됨`으로 표시
- 전체 `python -m pytest -q`가 359/359 PASS
- `ruff`, `compileall`, `dashboard build` 모두 PASS

**최신 결과**: PASS — Agent Manager 모바일 접근/프로젝트별 필터/취소 표시 실제 브라우저 검증 PASS, 표적 테스트 3개 PASS, 전체 `359 passed in 7.81s`, `ruff` PASS, `compileall` PASS, `npm run build` PASS
