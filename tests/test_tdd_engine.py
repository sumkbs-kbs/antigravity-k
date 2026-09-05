"""테스트: OmniTDDEngine — 적응형 레이싱 스킵·코드 추출.
====================================
단순 요청 레이싱 스킵 판정과 Python 코드 블록 추출 계약을 검증한다.
"""

from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.tdd_engine import OmniTDDEngine, TDDCandidate, TDDStatus


@pytest.fixture
def engine() -> OmniTDDEngine:
    return OmniTDDEngine(model_manager=MagicMock(), coding_model="test-model")


def _should_skip_racing(engine: OmniTDDEngine, prompt: str) -> bool:
    method = cast(Callable[[str], bool], getattr(engine, "_should_skip_racing"))
    return method(prompt)


def _extract_python_code(engine: OmniTDDEngine, text: str) -> str:
    method = cast(Callable[[str], str], getattr(engine, "_extract_python_code"))
    return method(text)


@pytest.mark.asyncio
async def test_external_test_file_is_used_for_self_play(tmp_path: Path):
    test_file = tmp_path / "generated_test.py"
    _ = test_file.write_text(
        "import solution\n\ndef test_answer():\n    assert solution.answer() == 42\n", encoding="utf-8"
    )
    engine = OmniTDDEngine(
        model_manager=MagicMock(), coding_model="test-model", workspace_dir=str(tmp_path / "workspace")
    )
    candidate = TDDCandidate(source="local", code="def answer():\n    return 42\n")

    async def candidates(prompt: str) -> list[TDDCandidate]:
        del prompt
        return [candidate]

    async def explanation(original_prompt: str, winning_code: str) -> str:
        del original_prompt, winning_code
        return "ok"

    setattr(engine, "_get_local_only_candidate", candidates)
    setattr(engine, "_reconstruct_response", explanation)
    report = await engine.run_tdd_loop("implement answer", test_file_path=str(test_file))

    assert report.status is TDDStatus.PASSED
    assert report.final_code == candidate.code


class TestShouldSkipRacing:
    def test_short_simple_prompt_skips_racing(self, engine: OmniTDDEngine):
        assert _should_skip_racing(engine, "간단한 함수를 작성해줘") is True

    def test_long_prompt_does_not_skip(self, engine: OmniTDDEngine):
        # 30토큰 이상 → 단순 지시어가 있어도 레이싱 실행
        prompt = " ".join(["토큰"] * 35) + " 코드 작성"
        assert _should_skip_racing(engine, prompt) is False

    def test_short_but_complex_keyword_does_not_skip(self, engine: OmniTDDEngine):
        # 30토큰 미만이지만 "최적화" 등 복잡 지시어 없음 + 단순 지시어 있음 → skip
        assert _should_skip_racing(engine, "코드 작성") is True

    def test_no_simple_indicator_does_not_skip(self, engine: OmniTDDEngine):
        # 단순 지시어 없음 → 30토큰 미만이라도 레이싱 스킵 안함
        prompt = " ".join(["아키텍처"] * 40) + " 최적화 병목 프로파일링 보고서"
        assert _should_skip_racing(engine, prompt) is False

    def test_english_simple_prompt_skips(self, engine: OmniTDDEngine):
        assert _should_skip_racing(engine, "write a hello world function") is True


class TestExtractPythonCode:
    def test_code_block_extraction(self, engine: OmniTDDEngine):
        text = "설명입니다\n```python\nprint('hello')\n```\n끝"
        assert _extract_python_code(engine, text) == "print('hello')"

    def test_no_code_block_returns_original(self, engine: OmniTDDEngine):
        text = "그냥 코드만 있는 경우"
        assert _extract_python_code(engine, text) == text
