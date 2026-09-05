"""mlx-lm 플래그 드리프트 검사 (Phase 22).

lora_pipeline이 생성하는 mlx 학습/병합 명령의 플래그가 설치된 mlx-lm에서
실제로 유효한지 검증한다. 배경: mlx-lm은 버전 간 플래그 이름을 바꾼 적이 있고
(Phase 11: --lora-layers → --num-layers), 생성된 명령이 런타임에 실패하면
사용자만 피해를 본다.

검증 방법: `python -m mlx_lm.lora --help` 출력에서 유효 플래그를 열거해
생성 명령의 --flags와 대조. --help는 모델 로딩 없이 빠르고, 존재하지 않는
플래그는 argparse가 거부하므로 도움말에도 나타나지 않는다.

mlx-lm 미설치 환경(Linux CI base)에서는 전체 스킵.
"""

from __future__ import annotations

import re
import subprocess

import pytest

from antigravity_k.engine.lora_pipeline import LoRAPipeline
from tests._cli_subprocess import python_invocation


def _mlx_lm_missing() -> bool:
    try:
        import mlx_lm  # noqa: F401

        return False
    except ImportError:
        return True


pytestmark = pytest.mark.skipif(_mlx_lm_missing(), reason="mlx-lm 미설치 (mlx 환경에서만 실행)")


def _valid_flags(module: str) -> set[str]:
    """`python -m <module> --help`에서 유효한 --플래그 집합을 열거한다.

    인터프리터는 tests/_cli_subprocess 헬퍼로 고정한다 (Phase 57) —
    AGK_TEST_PYTHON > uv run > sys.executable 순. CI에서 AGK_TEST_PYTHON을
    지정하면 드리프트 체크와 스모크 테스트가 같은 인터프리터를 공유한다.
    """
    result = subprocess.run(
        [*python_invocation(project=True), "-m", module, "--help"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = result.stdout + result.stderr
    # 사용법 블록과 옵션 목록 모두에서 --flag 토큰을 추출한다
    return set(re.findall(r"(?<![\w-])(--[a-z0-9][a-z0-9-]*)", output))


def _flags_from_command(command: str) -> set[str]:
    """생성된 명령 문자열에서 --플래그 토큰만 추출한다 (값 제외)."""
    return set(re.findall(r"(?<![\w-])(--[a-z0-9][a-z0-9-]*)", command))


def _lora_flags() -> set[str]:
    return _valid_flags("mlx_lm.lora")


def _fuse_flags() -> set[str]:
    return _valid_flags("mlx_lm.fuse")


@pytest.fixture(scope="module")
def lora_flags() -> set[str]:
    return _lora_flags()


@pytest.fixture(scope="module")
def fuse_flags() -> set[str]:
    return _fuse_flags()


def test_mlx_lora_help_enumerates_flags(lora_flags: set[str]) -> None:
    """헬프 파싱이 실제로 동작하는지 — 알려진 핵심 플래그가 보여야 한다."""
    assert {"--model", "--train", "--data"} <= lora_flags


def test_sft_command_flags_exist(lora_flags: set[str]) -> None:
    config = LoRAPipeline._mlx_lora_config("test/model", "data.jsonl", "out")
    used = _flags_from_command(str(config["command"]))
    unknown = used - lora_flags
    assert not unknown, (
        f"생성된 SFT 명령의 플래그가 설치된 mlx-lm에 없습니다: {sorted(unknown)}. "
        "mlx-lm이 플래그를 개정했을 가능성 — lora_pipeline._mlx_lora_config를 수정하세요."
    )


def test_dpo_command_flags_exist(lora_flags: set[str]) -> None:
    pipeline = LoRAPipeline(harvest_dir="data/harvest")
    config = pipeline.generate_dpo_config(
        base_model="test/model",
        dataset_path="data/dpo.jsonl",
        output_dir="data/dpo_out",
        platform="mlx",
    )
    used = _flags_from_command(str(config["command"]))
    unknown = used - lora_flags
    assert not unknown, (
        f"생성된 DPO(DoRA 근사) 명령의 플래그가 설치된 mlx-lm에 없습니다: {sorted(unknown)}. "
        "mlx-lm이 플래그를 개정했을 가능성 — generate_dpo_config의 mlx 분기를 수정하세요."
    )


def test_fuse_command_flags_exist(fuse_flags: set[str]) -> None:
    config = LoRAPipeline._mlx_lora_config("test/model", "data.jsonl", "out")
    used = _flags_from_command(str(config["merge_command"]))
    unknown = used - fuse_flags
    assert not unknown, (
        f"생성된 merge(fuse) 명령의 플래그가 설치된 mlx-lm에 없습니다: {sorted(unknown)}. "
        "mlx-lm이 fuse 플래그를 개정했을 가능성 — merge_command 생성부를 수정하세요."
    )
