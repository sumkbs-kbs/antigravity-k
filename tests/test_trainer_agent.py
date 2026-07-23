"""Tests for the Trainer Agent module."""

import json
from unittest import mock

import pytest

from antigravity_k.agents.trainer_agent import TrainerAgent


@pytest.fixture
def mock_model_manager():
    """ModelManager 목 객체."""
    mm = mock.MagicMock()
    mm.generate.return_value = json.dumps(
        {
            "dataset_url": "huggingface/code-alpaca",
            "target_model": "llama-4:latest",
            "training_method": "LoRA",
            "estimated_hours": 4,
            "rationale": "Improve code generation capabilities",
        }
    )
    return mm


@pytest.fixture
def mock_tool_registry():
    """ToolRegistry 목 객체."""
    return mock.MagicMock()


@pytest.fixture
def trainer(mock_model_manager, mock_tool_registry):
    """TrainerAgent 인스턴스."""
    return TrainerAgent(
        model_manager=mock_model_manager,
        tool_registry=mock_tool_registry,
    )


class TestTrainerAgent:
    """Tests for TrainerAgent class."""

    def test_init(self, trainer, mock_model_manager, mock_tool_registry):
        """초기화 시 model_manager와 tool_registry가 설정되어야 함."""
        assert trainer.model_manager is mock_model_manager
        assert trainer.tool_registry is mock_tool_registry

    def test_propose_training_success(self, trainer, mock_model_manager):
        """훈련 제안이 성공하면 기안서를 반환해야 함."""
        result = trainer.propose_training("code generation")
        assert "TrainerAgent" in result
        assert "huggingface/code-alpaca" in result or "훈련" in result or "training" in result.lower()
        mock_model_manager.generate.assert_called_once()

    def test_propose_training_with_code_block(self, trainer, mock_model_manager):
        """JSON이 코드 블록(```json ... ```)으로 감싸져 있어도 파싱되어야 함."""
        mock_model_manager.generate.return_value = (
            '```json\n{\n    "dataset_url": "huggingface/math-dataset",\n'
            '    "target_model": "qwen-2.5:latest",\n'
            '    "training_method": "QLoRA",\n'
            '    "estimated_hours": 8,\n'
            '    "rationale": "Improve math reasoning"\n}\n```'
        )
        result = trainer.propose_training("math reasoning")
        assert "TrainerAgent" in result or "훈련" in result or "training" in result.lower()

    def test_propose_training_no_code_block(self, trainer, mock_model_manager):
        """코드 블록 없이 순수 JSON만 반환되어도 파싱되어야 함."""
        mock_model_manager.generate.return_value = (
            '{"dataset_url": "huggingface/test",'
            '"target_model": "test:latest",'
            '"training_method": "Full",'
            '"estimated_hours": 2,'
            '"rationale": "Test"}'
        )
        result = trainer.propose_training("test")
        assert "TrainerAgent" in result or "huggingface" in result or "훈련" in result or "training" in result.lower()

    def test_propose_training_api_exception(self, trainer, mock_model_manager):
        """API 예외 발생 시 적절한 오류 메시지를 반환해야 함."""
        mock_model_manager.generate.side_effect = RuntimeError("API unavailable")
        result = trainer.propose_training("test")
        assert "failed" in result.lower()

    def test_propose_training_invalid_json(self, trainer, mock_model_manager):
        """잘못된 JSON 응답 시 오류 메시지를 반환해야 함."""
        mock_model_manager.generate.return_value = "This is not JSON {{{"
        result = trainer.propose_training("test")
        assert "failed" in result.lower()

    def test_propose_training_empty_response(self, trainer, mock_model_manager):
        """빈 응답 시 오류 처리가 되어야 함."""
        mock_model_manager.generate.return_value = ""
        result = trainer.propose_training("test")
        assert "failed" in result.lower() or "Error" in result or "error" in result

    def test_propose_training_custom_domain(self, trainer, mock_model_manager):
        """다양한 도메인에 대한 훈련 제안이 동작해야 함."""
        result = trainer.propose_training("korean language understanding")
        assert "TrainerAgent" in result or "한국어" in result or "korean" in result.lower()
