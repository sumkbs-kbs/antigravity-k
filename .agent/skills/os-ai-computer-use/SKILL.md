---
name: OS_AI_COMPUTER_USE
description: OS AI Computer Use 프레임워크 아키텍처 분석 및 Antigravity-K 통합 가이드
tools:
  - computer_use
  - screenshot
---

# OS AI Computer Use — 아키텍처 분석 및 통합 스킬

**저장소**: https://github.com/777genius/os-ai-computer-use  
**라이선스**: Apache 2.0  
**벤치마크**: OSWorld 75.0% (인간 수준 초과)

## 1. 프로젝트 개요

데스크탑 자동화를 위한 오픈소스 AI 에이전트입니다.
AI가 사용자의 화면을 보고(스크린샷), 마우스를 움직이고, 키보드를 치고, 스크롤하는 등
**사람이 하는 컴퓨터 조작을 AI가 대신** 수행합니다.

## 2. 핵심 아키텍처 (모노레포 패키지 구조)

```
packages/
├── llm/            ← 도메인 타입 (Message, ToolCall, LLMClient 인터페이스)
├── llm_anthropic/  ← Anthropic Claude 어댑터
├── llm_openai/     ← OpenAI GPT-5.4 어댑터
├── core/           ← 비즈니스 로직 (Orchestrator, ToolRegistry)
│   └── tools/
│       ├── computer.py  ← 마우스/키보드/스크린샷 핵심 로직 (31KB)
│       └── registry.py  ← 도구 등록 및 실행 허브
├── os/             ← OS 추상화 (DriverSet 인터페이스)
├── os-windows/     ← Windows 전용 드라이버 (PyAutoGUI 기반)
├── os-macos/       ← macOS 전용 드라이버 (Quartz/AppKit)
├── os-linux/       ← Linux 전용 드라이버 (X11/scrot)
├── backend/        ← FastAPI WebSocket/REST 서버
├── cli/            ← CLI 인터페이스
frontend_flutter/   ← Flutter 크로스플랫폼 UI
```

### 2.1 LLMClient 인터페이스 (Provider-Agnostic)
```python
class LLMClient(ABC):
    def generate(messages, tools, system, ..., provider_context) -> LLMResponse
    def format_tool_result(result: ToolResult) -> Message
    def get_model_name() -> str
    def get_provider_name() -> str
```

### 2.2 Computer Tool 핵심 액션
| 액션 | 설명 |
|------|------|
| `mouse_move` | 좌표로 마우스 이동 (이징, 속도 조절) |
| `left_click` / `right_click` / `double_click` | 클릭 (수정자 키 지원) |
| `left_click_drag` | 드래그앤드롭 (다중 포인트 경로) |
| `key` / `hold_key` | 키 입력 / 키 홀드 |
| `type` | 텍스트 타이핑 |
| `scroll` | 스크롤 (상하좌우) |
| `screenshot` | 화면 캡처 (base64 반환) |

### 2.3 OS 드라이버 추상화
```
DriverSet:
  ├── MouseDriver   (이동, 클릭, 드래그)
  ├── KeyboardDriver (키 입력, 홀드)
  ├── ScreenDriver  (스크린샷, 해상도)
  ├── OverlayDriver (시각적 하이라이트)
  └── SoundDriver   (알림 사운드)
```

## 3. Antigravity-K 통합 현황

### 구현 완료
- `tools/computer_use.py` — ComputerUseTool (BaseTool 상속)
- `tools/os_drivers.py` — OS 드라이버 추상화 (Windows/Stub)
- `security/computer_use_guard.py` — 액션 보안 검증
- DEVOPS 에이전트에 `computer_use` 도구 권한 부여

### 빠른 시작 (Windows)
```bash
git clone https://github.com/777genius/os-ai-computer-use.git
cd os-ai-computer-use
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
set OPENAI_API_KEY=sk-...
python -m os_ai_cli --provider openai --task "메모장을 열고 Hello World를 입력하세요"
```
