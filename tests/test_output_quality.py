import pytest

from antigravity_k.engine.prompt_builder import PromptBuilder
from antigravity_k.engine.quality_gate import QualityGate, QualityGrade
from antigravity_k.engine.tdd_engine import OmniTDDEngine


def test_quality_gate_retries_code_only_complexity_response():
    gate = QualityGate()

    output = """```python
def gcd(a, b):
    while b:
        a, b = b, a % b
    return abs(a)
```"""

    result = gate.evaluate(
        "coding",
        "Python으로 GCD 함수를 유클리드 호제법으로 작성하고 시간복잡도를 비교해줘",
        output,
    )

    assert result.should_retry is True
    assert result.grade in (QualityGrade.C, QualityGrade.F)
    assert "코드-only 응답" in result.issues
    assert "Big-O 복잡도 누락" in result.issues
    assert "비교 구조 부족" in result.issues


def test_quality_gate_accepts_explained_complexity_response():
    gate = QualityGate()

    output = """### 분석

GCD는 두 정수의 최대공약수를 구하는 문제입니다. 유클리드 호제법은 나머지 연산으로
입력 크기를 빠르게 줄이기 때문에 일반적인 단순 반복 탐색보다 효율적입니다.

```python
def gcd_euclid(a, b):
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a

def gcd_scan(a, b):
    a, b = abs(a), abs(b)
    best = 1
    for candidate in range(1, min(a, b) + 1):
        if a % candidate == 0 and b % candidate == 0:
            best = candidate
    return best
```

| 방법 | 시간복잡도 | 공간복잡도 | 특징 |
| --- | --- | --- | --- |
| 유클리드 호제법 | `O(log(min(a, b)))` | `O(1)` | 큰 입력에 적합 |
| 단순 반복 탐색 | `O(min(a, b))` | `O(1)` | 이해하기 쉽지만 느림 |

💡 팁: 실제 사용 시에는 0 입력과 음수 입력도 함께 테스트하세요.
"""

    result = gate.evaluate(
        "coding",
        "Python으로 GCD 함수를 유클리드 호제법과 반복문 2가지로 작성 + 시간복잡도 비교",
        output,
    )

    assert result.should_retry is False
    assert result.grade in (QualityGrade.A, QualityGrade.B)
    assert "코드-only 응답" not in result.issues
    assert "Big-O 복잡도 누락" not in result.issues


def test_quality_gate_retries_unstructured_comparison_response():
    gate = QualityGate()

    output = """### 분석

GCD 구현은 유클리드 호제법과 반복 탐색을 모두 사용할 수 있습니다. 유클리드 호제법은
나머지 연산을 쓰고 반복 탐색은 모든 후보를 훑습니다.

```python
def gcd_euclid(a, b):
    while b:
        a, b = b, a % b
    return abs(a)
```

시간복잡도는 `O(log(min(a, b)))`, 공간복잡도는 `O(1)`입니다.
"""

    result = gate.evaluate(
        "coding",
        "Python GCD 구현 방법을 비교하고 장단점도 알려줘",
        output,
    )

    assert result.should_retry is True
    assert result.grade is QualityGrade.C
    assert "비교 구조 부족" in result.issues


def test_quality_gate_retries_exposed_thinking_and_mixed_language_intro():
    gate = QualityGate()

    output = """--- Thinking Process ---
Okay, I need to help the user by introducing myself.
Looking at the persistent context, I should list tools.
--- End of Thinking ---

Antigravity-K AI 파트너입니다.당신의프로젝트를지원합니다.
read_file: 읽기, write_file: 文件 작성, 미래 예측은 정확히 답변できません.
로컬LLM모델의을확인하고어떻게 내가업グレード될수 있는지 검토합니다.
"""

    result = gate.evaluate(
        "reasoning",
        "너를 소개하고 니가 할 수 있는 일과 할 수 없는 일을 알려줘",
        output,
    )

    assert result.should_retry is True
    assert result.grade in (QualityGrade.C, QualityGrade.F)
    assert any("Thinking Process" in issue for issue in result.issues)
    assert any("일본어" in issue or "외국어 오염" in issue for issue in result.issues)
    assert any("가독성" in issue or "띄어쓰기" in issue for issue in result.issues)


def test_quality_gate_retries_stale_latest_trend_answer():
    gate = QualityGate()

    output = """로컬 LLM 최신 동향은 제 지식 cutoff인 October 2023 기준으로 설명하겠습니다.
Mistral과 LLaMA 계열이 좋고 Ollama로 받을 수 있습니다. 실시간 데이터는 없습니다.
"""

    result = gate.evaluate(
        "reasoning",
        "로컬 LLM 모델의 최신 동향을 실시간으로 확인해서 업그레이드 방향을 알려줘",
        output,
    )

    assert result.should_retry is True
    assert result.grade in (QualityGrade.C, QualityGrade.F)
    assert "최신 정보 요청에서 지식 cutoff/비검증 답변" in result.issues


def test_quality_gate_retries_bad_markdown_extensions():
    gate = QualityGate()

    output = """여기에 결과를 출력합니다.

```mermaid
graph TD
    A[<div class='node'>Start</div>] --> B[End]
```

그리고 캐러셀을 보여줍니다.
<!-- slide -->
슬라이드 1
<!-- slide -->

참고로 파일은 [`test.py`](file:///test.py) 입니다.

**Note**: 이것은 구형 노트 형식입니다.
"""

    result = gate.evaluate("reasoning", "마크다운 테스트", output)

    assert result.should_retry is True
    assert any("Mermaid 다이어그램 내 HTML 태그 포함" in issue for issue in result.issues)
    assert any("Carousel 마크다운 문법 오류" in issue for issue in result.issues)
    assert any("파일 링크 텍스트에 백틱 사용" in issue for issue in result.issues)
    assert any("구형 경고 블록 감지" in issue for issue in result.issues)


def test_prompt_builder_includes_output_quality_contract():
    guide = PromptBuilder().tool_guide([], current_time=None)

    assert "출력 품질 게이트" in guide
    assert "코드 요청에도 반드시 한국어 설명" in guide
    assert "Big-O" in guide
    assert "비교 표" in guide
    assert "200자 미만" in guide
    assert "자기소개/능력 설명은 실제 등록된 도구와 Skills만 근거" in guide
    assert "최신/최근/실시간 동향 질문" in guide
    assert "Thinking Process" in guide


@pytest.mark.asyncio
async def test_tdd_reconstructor_falls_back_when_llm_returns_code_only():
    engine = OmniTDDEngine(coding_model="unused")

    async def fake_call_llm(sys_prompt: str, user_prompt: str) -> str:
        return """```python
def gcd(a, b):
    while b:
        a, b = b, a % b
    return abs(a)
```"""

    engine._call_llm = fake_call_llm

    response = await engine._reconstruct_response(
        "Python으로 GCD 함수를 유클리드 호제법과 반복문 2가지로 작성 + 시간복잡도 비교",
        "def gcd(a, b):\n    while b:\n        a, b = b, a % b\n    return abs(a)\n",
    )

    assert "### 🔍 분석" in response
    assert "### 💻 구현 코드" in response
    assert "### 📊 설명" in response
    assert "O(log(min(a, b)))" in response
    assert "| 방법 | 시간복잡도 | 공간복잡도 | 특징 |" in response
    assert "💡 팁" in response
