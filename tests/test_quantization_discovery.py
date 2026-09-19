"""Phase 2 테스트: GGUF 양자화 인식 디스커버리.

벤치마킹 출처: unsloth Dynamic GGUF 네이밍 규약 (UD-Q4_K_XL 등).
파일명/디렉터리명에서 양자화 토큰을 정확히 추출하는지 검증한다.
"""

from __future__ import annotations

import pytest

from antigravity_k.engine.local_model_discovery import _quantization


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        # unsloth Dynamic GGUF (UD 접두사)
        ("Qwen3.8-27B-UD-Q4_K_XL.gguf", "UD-Q4_K_XL"),
        ("unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL", "UD-Q4_K_XL"),
        ("DeepSeek-V4-UD-Q2_K_XL.gguf", "UD-Q2_K_XL"),
        # 표준 K-quant
        ("Qwen3.8-27B-Q4_K_M.gguf", "Q4_K_M"),
        ("model-Q8_0.gguf", "Q8_0"),
        ("gemma-4-9b-it-Q5_K_S.gguf", "Q5_K_S"),
        ("llama-3.1-8b-Q6_K.gguf", "Q6_K"),
        ("DeepSeek-R1-Q3_K_L.gguf", "Q3_K_L"),
        # I-quant
        ("Mistral-7B-IQ4_XS.gguf", "IQ4_XS"),
        ("minimax-m3-IQ2_M.gguf", "IQ2_M"),
        # 소문자 혼용 정규화
        ("qwen3.8-27b-q4_k_m.gguf", "Q4_K_M"),
        ("deepseek-v4-ud-q4_k_xl.gguf", "UD-Q4_K_XL"),
        # 레거시 Nbit 표기
        ("mlx-community/Qwen2.5-Coder-32B-Instruct-4bit", "4bit"),
        ("model-8bit.gguf", "8bit"),
    ],
)
def test_quantization_extraction(filename: str, expected: str) -> None:
    assert _quantization(filename) == expected


@pytest.mark.parametrize(
    "filename",
    [
        "Qwen3.8-27B-Instruct.gguf",  # 양자 토큰 없음
        "plain-model.bin",
        "MLX-Qwen-Model",  # Q 단독 문자열 (토큰 아님)
        "IdeaProjects",  # I + 숫자 아님
        "Q3",  # 언더스코어 없는 미완성 토큰 (K-quant 아님)
    ],
)
def test_quantization_no_false_positive(filename: str) -> None:
    """양자 토큰이 아닌 문자열에서 오탐이 없어야 한다."""
    assert _quantization(filename) == ""


def test_quantization_priority_over_ollama_details() -> None:
    """파일명 파싱이 Ollama details(예: Q4_0)보다 구체적이면 우선한다.

    _build_hf_model/_filesystem_model 모두 `_quantization_from_config(metadata) or _quantization(name)`
    순서이며, GGUF 파일은 config가 비어 있으므로 파일명 파싱 결과를 사용한다.
    """
    # GGUF 파일명의 구체적 양자가 우선됨을 정적 검증
    from antigravity_k.engine.local_model_discovery import _quantization_from_config

    assert _quantization_from_config({}) == ""
    assert _quantization("model-UD-Q4_K_XL.gguf") == "UD-Q4_K_XL"
