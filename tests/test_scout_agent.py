"""Tests for the Scout Agent module."""

import json
from unittest import mock

import pytest

from antigravity_k.agents.scout_agent import ScoutAgent


@pytest.fixture
def mock_model_manager():
    """ModelManager 목 객체."""
    mm = mock.MagicMock()
    mm.generate.return_value = json.dumps(
        {
            "propose_add": {
                "name": "llama-4:latest",
                "repo": "meta/llama-4",
                "description": "New model for reasoning tasks",
                "estimated_memory_gb": 8,
            },
            "propose_remove": None,
        }
    )
    return mm


@pytest.fixture
def mock_tool_registry():
    """ToolRegistry 목 객체."""
    return mock.MagicMock()


@pytest.fixture
def scout_agent(mock_model_manager, mock_tool_registry):
    """ScoutAgent 인스턴스."""
    return ScoutAgent(
        model_manager=mock_model_manager,
        tool_registry=mock_tool_registry,
    )


class TestScoutAgent:
    """Tests for ScoutAgent class."""

    def test_init(self, scout_agent, mock_model_manager, mock_tool_registry):
        """초기화 시 model_manager와 tool_registry가 설정되어야 함."""
        assert scout_agent.model_manager is mock_model_manager
        assert scout_agent.tool_registry is mock_tool_registry

    def test_propose_model_scout_success(self, scout_agent, mock_model_manager):
        """모델 제안이 성공하면 기안서를 반환해야 함."""
        result = scout_agent.propose_model_scout("latest AI models")
        assert "ScoutAgent" in result
        assert "llama-4" in result or "영입" in result
        mock_model_manager.generate.assert_called_once()

    def test_propose_json_with_code_block(self, scout_agent, mock_model_manager):
        """JSON이 코드 블록(```json ... ```)으로 감싸져 있어도 파싱되어야 함."""
        mock_model_manager.generate.return_value = (
            '```json\n{\n    "propose_add": {\n        "name": "qwen-2.5:latest",\n'
            '        "repo": "qwen/qwen-2.5",\n        "description": "Lightweight model",\n'
            '        "estimated_memory_gb": 4\n    },\n    "propose_remove": null\n}\n```'
        )
        result = scout_agent.propose_model_scout("lightweight model")
        assert "qwen-2.5" in result or "에이전트" in result

    def test_propose_with_remove(self, scout_agent, mock_model_manager):
        """propose_remove가 있을 때 해고 제안이 포함되어야 함."""
        mock_model_manager.generate.return_value = json.dumps(
            {
                "propose_add": {
                    "name": "gpt-5:latest",
                    "repo": "openai/gpt-5",
                    "description": "Latest GPT",
                    "estimated_memory_gb": 16,
                },
                "propose_remove": "gpt-3.5:latest",
            }
        )
        result = scout_agent.propose_model_scout("upgrade models")
        assert "gpt-3.5" in result or "해고" in result or "제거" in result

    def test_propose_add_only(self, scout_agent, mock_model_manager):
        """propose_remove가 null일 때 추가 제안만 포함되어야 함."""
        mock_model_manager.generate.return_value = json.dumps(
            {
                "propose_add": {
                    "name": "claude-4:latest",
                    "repo": "anthropic/claude-4",
                    "description": "Safe AI",
                    "estimated_memory_gb": 12,
                },
                "propose_remove": None,
            }
        )
        result = scout_agent.propose_model_scout("safe AI")
        assert "propose" in result.lower() or "claude" in result

    def test_propose_model_scout_low_memory(self, scout_agent, mock_model_manager):
        """메모리 요구사항이 시스템 RAM의 80% 미만이면 정상 제안."""
        mock_model_manager.generate.return_value = json.dumps(
            {
                "propose_add": {
                    "name": "small-model:latest",
                    "repo": "test/small",
                    "description": "Small model",
                    "estimated_memory_gb": 4,
                },
                "propose_remove": None,
            }
        )
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch("builtins.open", mock.mock_open(read_data="memory:\n  total_system_gb: 32.0")):
                result = scout_agent.propose_model_scout("small model")
                assert "ScoutAgent" in result

    def test_propose_high_memory_no_config(self, scout_agent, mock_model_manager):
        """config.yaml이 없으면 기본 메모리 128GB로 계산되어야 함."""
        mock_model_manager.generate.return_value = json.dumps(
            {
                "propose_add": {
                    "name": "huge-model:latest",
                    "repo": "big/huge",
                    "description": "Needs lots of RAM",
                    "estimated_memory_gb": 200,
                },
                "propose_remove": None,
            }
        )
        with mock.patch("os.path.exists", return_value=False):
            result = scout_agent.propose_model_scout("large model")
            # 200 > 128*0.8 = 102.4 이므로 HardwareAnalystAgent로 넘어감
            assert "HardwareAnalyst" in result

    def test_propose_model_scout_api_error(self, scout_agent, mock_model_manager):
        """API 에러 시 적절한 오류 메시지를 반환해야 함."""
        mock_model_manager.generate.side_effect = RuntimeError("API connection failed")
        result = scout_agent.propose_model_scout("test")
        assert "failed" in result.lower()

    def test_propose_invalid_json(self, scout_agent, mock_model_manager):
        """잘못된 JSON 응답 시 오류 메시지를 반환해야 함."""
        mock_model_manager.generate.return_value = "This is not JSON at all"
        result = scout_agent.propose_model_scout("test")
        assert "failed" in result.lower() or "Error" in result or "error" in result

    def test_propose_json_extract_no_code_block(self, scout_agent, mock_model_manager):
        """코드 블록 없이 순수 JSON만 반환되어도 파싱되어야 함."""
        mock_model_manager.generate.return_value = (
            '{"propose_add": {"name": "test:latest", "repo": "test/repo",'
            '"description": "test", "estimated_memory_gb": 2}, "propose_remove": null}'
        )
        result = scout_agent.propose_model_scout("test")
        assert "ScoutAgent" in result or "test" in result.lower()
