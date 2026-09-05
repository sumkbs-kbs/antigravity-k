#!/usr/bin/env python3
"""qwen3 thinking on/off A/B 품질·지연 실측 (직접 Ollama /api/chat).

복잡도 게이트 thinking(model.complex_task_thinking) 전환 근거를 확보한다.
하네스 전체를 거치지 않고 Ollama 네이티브 API로 think 파라미터만 토글해
순수 thinking 효과를 격리 측정한다.

각 문제는 결정적 검증기(정답 포함/일치)로 채점하므로 LLM 심판이 필요 없다.

사용:
    uv run python scripts/measure_thinking_ab.py [--model qwen3.8:latest] [--repeats 2]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

OLLAMA_URL = "http://localhost:11434/api/chat"


@dataclass(frozen=True)
class Question:
    qid: str
    prompt: str
    verify: Callable[[str], bool]
    category: str


def _norm(text: str) -> str:
    lowered = text.lower()
    # LaTeX 분수 표기 정규화: \frac{a}{b} / \dfrac{a}{b} → a/b
    lowered = re.sub(r"\\d?frac\{([^{}]+)\}\{([^{}]+)\}", r"\1/\2", lowered)
    return re.sub(r"\s+", "", lowered)


def _any_of(*needles: str) -> Callable[[str], bool]:
    def check(answer: str) -> bool:
        n = _norm(answer)
        return any(_norm(x) in n for x in needles)

    return check


def _contains(*needles: str) -> Callable[[str], bool]:
    def check(answer: str) -> bool:
        n = _norm(answer)
        return all(_norm(x) in n for x in needles)

    return check


QUESTIONS: list[Question] = [
    Question(
        "arith-1",
        "철수에게 사과 23개, 배 19개가 있다. 영희가 사과 15개와 배 7개를 더 가져왔다. "
        "이제 사과가 배보다 몇 개 더 많은가? 숫자만 답하라.",
        _contains("12"),
        "산술",
    ),
    Question(
        "logic-1",
        "어떤 수에 3을 곱하고 7을 더하면 25가 된다. 그 수는 얼마인가? 숫자만 답하라.",
        _contains("6"),
        "논리",
    ),
    Question(
        "code-1",
        "다음 파이썬 함수는 버그가 있다:\n\n"
        "def sum_to(n):\n    total = 0\n    for i in range(n):\n        total += i\n    return total\n\n"
        "1부터 n까지의 합을 반환하도록 하려면 range를 무엇으로 바꿔야 하는가? 정확한 코드만 답하라.",
        _any_of("range(1,n+1)", "range(n+1)"),
        "코드",
    ),
    Question(
        "date-1",
        "2026년 9월 1일은 화요일이다. 2026년 9월의 두 번째 일요일은 며칠인가? 숫자(일)만 답하라.",
        _contains("13"),
        "추론",
    ),
    Question(
        "prob-1",
        "주머니에 빨간 공 3개, 파란 공 5개가 있다. 임의로 하나 꺼낼 때 파란 공일 확률을 " "기약분수로 답하라.",
        lambda answer: _contains("5/8")(answer) or _contains("0.625")(answer),
        "확률",
    ),
    Question(
        "codeout-1",
        "다음 파이썬 코드의 출력을 정확히 답하라:\n\n" "x = [1, 2, 3, 4, 5]\nprint([v * 2 for v in x if v % 2 == 1])\n",
        _contains("[2,6,10]"),
        "코드",
    ),
    Question(
        "korean-1",
        "다음 문장에서 '그'가 가리키는 것을 한 단어로 답하라:\n\n"
        "민수는 준호에게 노트를 빌려달라고 했다. 그는 시험 공부가 필요했다.\n"
        "노트가 필요한 사람은 누구인가?",
        _contains("민수"),
        "독해",
    ),
    Question(
        "multistep-1",
        "상점에서 연필 1개는 300원이고, 지우개 1개는 250원이다. 5,000원으로 연필 7개와 지우개 9개를 "
        "샀다. 거스름돈은 얼마인가? 숫자만 답하라.",
        _contains("650"),
        "산술",
    ),
]


@dataclass
class ArmResult:
    think: bool
    correct: int = 0
    latencies: list[float] = field(default_factory=list)
    per_question: dict[str, bool] = field(default_factory=dict)


def call_ollama(model: str, prompt: str, think: bool, timeout: int = 600) -> str:
    payload = {
        "model": model,
        "stream": False,
        "keep_alive": "30m",
        "think": think,
        "options": {"temperature": 0.2, "num_predict": 4096, "num_ctx": 16384},
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    message = data.get("message", {})
    content = str(message.get("content", "") or "")
    # thinking이 content에 인라인으로 새는 구버전 템플릿 방어
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if not content:
        content = str(message.get("thinking", "") or "")[:0]  # 빈 답은 그대로 빈 값
    return content


def run_arm(model: str, think: bool, repeats: int) -> ArmResult:
    result = ArmResult(think=think)
    for q in QUESTIONS:
        ok_runs = 0
        for _ in range(repeats):
            start = time.perf_counter()
            answer = call_ollama(model, q.prompt, think)
            result.latencies.append(time.perf_counter() - start)
            if q.verify(answer):
                ok_runs += 1
        passed = ok_runs >= (repeats + 1) // 2  # 과반 정답 = 해당 문제 정답 처리
        result.per_question[q.qid] = passed
        if passed:
            result.correct += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3.8:latest")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    print(f"🧪 thinking A/B 측정 (model={args.model}, questions={len(QUESTIONS)}, repeats={args.repeats})")
    print()

    off = run_arm(args.model, think=False, repeats=args.repeats)
    print(f"think=OFF: {off.correct}/{len(QUESTIONS)} 정답, " f"평균 {statistics.mean(off.latencies):.1f}초/호출")

    on = run_arm(args.model, think=True, repeats=args.repeats)
    print(f"think=ON : {on.correct}/{len(QUESTIONS)} 정답, " f"평균 {statistics.mean(on.latencies):.1f}초/호출")

    print()
    print("| 문제 | 카테고리 | OFF | ON |")
    print("|:--|:--|:--:|:--:|")
    for q in QUESTIONS:
        print(
            f"| {q.qid} | {q.category} | "
            f"{'✅' if off.per_question[q.qid] else '❌'} | "
            f"{'✅' if on.per_question[q.qid] else '❌'} |"
        )

    delta = on.correct - off.correct
    latency_ratio = statistics.mean(on.latencies) / max(statistics.mean(off.latencies), 0.001)
    print()
    print(f"품질 델타: {delta:+d}문제 | 지연 배율: {latency_ratio:.2f}x")

    if args.output:
        payload = {
            "model": args.model,
            "repeats": args.repeats,
            "off": {
                "correct": off.correct,
                "mean_latency": statistics.mean(off.latencies),
                "per_question": off.per_question,
            },
            "on": {
                "correct": on.correct,
                "mean_latency": statistics.mean(on.latencies),
                "per_question": on.per_question,
            },
            "delta": delta,
            "latency_ratio": latency_ratio,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"결과 저장: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
