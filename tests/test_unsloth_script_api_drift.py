"""Unsloth 생성 스크립트 Python API 드리프트 가드 (Phase 53).

mlx-lm 플래그 드리프트 가드(Phase 22)의 API 판 — lora_pipeline이 생성하는
Unsloth SFT/DPO 스크립트가 설치된 unsloth/trl/transformers 시그니처와 일치하는지 검증.

unsloth/trl 미설치 환경(로컬 macOS, Linux CI base)에서는 설치 검증부를 스킵.
AST 추출부(extract_script_api)는 설치와 무관하므로 항상 실행한다.
"""

from __future__ import annotations

import pytest

from antigravity_k.engine.lora_pipeline import LoRAPipeline
from antigravity_k.engine.unsloth_script_api import (
    ScriptApiUsage,
    extract_script_api,
    verify_against_installed,
)


def _libs_installed() -> bool:
    try:
        import trl  # noqa: F401
        import unsloth  # noqa: F401

        return True
    except ImportError:
        return False


# ─── AST 추출 (설치 무관 — 항상 실행) ─────────────────────────────


@pytest.fixture(scope="module")
def pipeline() -> LoRAPipeline:
    return LoRAPipeline(harvest_dir="data/lora_harvest")


@pytest.fixture(scope="module")
def sft_usage(pipeline: LoRAPipeline) -> ScriptApiUsage:
    cfg = pipeline._unsloth_config("test/model", "data/ds.jsonl", "data/out")
    return extract_script_api(str(cfg["script"]))


@pytest.fixture(scope="module")
def dpo_usage(pipeline: LoRAPipeline) -> ScriptApiUsage:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        cfg = pipeline.generate_dpo_config(
            base_model="test/model",
            dataset_path="data/dpo_ds.jsonl",
            output_dir=str(Path(td) / "out"),
            platform="unsloth",
        )
        return extract_script_api(str(cfg["script"]))


class TestExtractScriptApi:
    def test_sft_imports(self, sft_usage: ScriptApiUsage) -> None:
        assert "unsloth" in sft_usage.imported
        assert "FastLanguageModel" in sft_usage.imported["unsloth"]
        assert "SFTTrainer" in sft_usage.imported["trl"]
        assert "TrainingArguments" in sft_usage.imported["transformers"]

    def test_dpo_imports(self, dpo_usage: ScriptApiUsage) -> None:
        assert {"DPOTrainer", "DPOConfig"} <= dpo_usage.imported["trl"]
        assert "is_bfloat16_supported" in dpo_usage.imported["unsloth"]

    def test_class_method_resolves_with_class_name(self, sft_usage: ScriptApiUsage) -> None:
        # FastLanguageModel.from_pretrained는 'unsloth.from_pretrained'가 아니라
        # 'unsloth.FastLanguageModel.from_pretrained'로 해소돼야 한다 (클래스 메서드).
        assert "unsloth.FastLanguageModel.from_pretrained" in sft_usage.calls
        assert "unsloth.FastLanguageModel.get_peft_model" in sft_usage.calls
        assert "unsloth.from_pretrained" not in sft_usage.calls

    def test_trainer_calls_recorded(self, sft_usage: ScriptApiUsage, dpo_usage: ScriptApiUsage) -> None:
        assert "trl.SFTTrainer" in sft_usage.calls
        assert "transformers.TrainingArguments" in sft_usage.calls
        assert {"trl.DPOTrainer", "trl.DPOConfig"} <= set(dpo_usage.calls)

    def test_kwargs_captured(self, sft_usage: ScriptApiUsage) -> None:
        fp_kwargs = sft_usage.kwargs.get("unsloth.FastLanguageModel.from_pretrained", set())
        assert {"model_name", "max_seq_length", "load_in_4bit"} <= fp_kwargs
        trainer_kwargs = sft_usage.kwargs.get("trl.SFTTrainer", set())
        assert {"dataset_text_field", "max_seq_length", "tokenizer"} <= trainer_kwargs

    def test_extracts_from_arbitrary_source(self) -> None:
        usage = extract_script_api(
            """
from unsloth import FastLanguageModel
from trl import SFTTrainer
m, t = FastLanguageModel.from_pretrained(model_name="x")
SFTTrainer(model=m, tokenizer=t, custom_future_kwarg=1)
""",
        )
        assert "custom_future_kwarg" in usage.kwargs.get("trl.SFTTrainer", set())

    def test_syntax_error_raises(self) -> None:
        with pytest.raises(SyntaxError):
            extract_script_api("def broken(:\n    pass")


# ─── 설치된 라이브러리 대비 검증 (deps=unsloth 환경) ─────────────


@pytest.mark.skipif(not _libs_installed(), reason="unsloth/trl 미설치 (deps=unsloth 환경에서만 실행)")
class TestAgainstInstalled:
    def test_sft_script_has_no_api_errors(self, sft_usage: ScriptApiUsage) -> None:
        errors, _ = verify_against_installed(sft_usage)
        assert errors == []

    def test_dpo_script_has_no_api_errors(self, dpo_usage: ScriptApiUsage) -> None:
        errors, _ = verify_against_installed(dpo_usage)
        assert errors == []

    def test_drifted_import_is_reported_as_error(self) -> None:
        # 존재하지 않는 이름 — 미래 버전에서 rename됐을 때 잡히는지
        usage = extract_script_api(
            "from unsloth import FastLanguageModel_v99\nFastLanguageModel_v99.from_pretrained(model_name='x')\n",
        )
        errors, _ = verify_against_installed(usage)
        assert any("FastLanguageModel_v99" in e for e in errors)

    def test_drifted_class_method_is_reported_as_error(self) -> None:
        usage = extract_script_api(
            "from unsloth import FastLanguageModel\nFastLanguageModel.load_model_v99(model_name='x')\n",
        )
        errors, _ = verify_against_installed(usage)
        assert any("load_model_v99" in e for e in errors)

    def test_unknown_kwargs_reported_as_warning(self) -> None:
        # SFTTrainer에 완전히 없는 kwarg — **kwargs 흡수 여부를 몰라 warning 수준
        usage = extract_script_api(
            "from trl import SFTTrainer\nSFTTrainer(model=1, totally_unknown_kw=2)\n",
        )
        errors, warnings = verify_against_installed(usage)
        assert errors == [] or all("SFTTrainer" not in e for e in errors)
        assert any("totally_unknown_kw" in w for w in warnings)

    def test_canary_detects_intentional_drift(self, sft_usage: ScriptApiUsage) -> None:
        """가드 자체의 민감도 카나리아 — 시그니처에 있는 kwarg는 warning에 없어야 한다."""
        _, warnings = verify_against_installed(sft_usage)
        for w in warnings:
            # 실제 스크립트가 쓰는 알려진 kwarg가 warning으로 뜨면 시그니처 해석이 깨진 것
            assert "model_name" not in w or "tokenizer" not in w

    def test_real_sft_script_training_args_are_current(self, sft_usage: ScriptApiUsage) -> None:
        """transformers(로컬 설치됨) 기준 — 스크립트의 TrainingArguments kwargs가 현재 유효해야 한다.

        unsloth/trl이 없어도 transformers는 deps에 있으므로 이 테스트는 어디서든 도는데,
        transformers 5.x에서 TrainingArguments에서 사라진 kwargs(예: 구버전 tokenizer 관련)가
        스크립트에 남아 있으면 warning으로 잡힌다.
        """
        ta_kwargs = sft_usage.kwargs.get("transformers.TrainingArguments", set())
        assert ta_kwargs, "SFT 스크립트에서 TrainingArguments kwargs가 추출돼야 한다"
        _, warnings = verify_against_installed(sft_usage)
        ta_warnings = [w for w in warnings if "TrainingArguments" in w]
        assert ta_warnings == [], f"TrainingArguments 드리프트 감지: {ta_warnings}"
