"""Tests for the Hardware Analyst module."""

import json
from types import SimpleNamespace
from typing import Protocol, cast
from unittest import mock

import pytest

from antigravity_k.agents.hardware_analyst import HardwareAnalystAgent
from antigravity_k.engine.model_manager import ModelManager


class _MockMethod(Protocol):
    return_value: object
    side_effect: object


class _ModelManagerDouble(Protocol):
    generate: _MockMethod


def _system_specs(analyst: HardwareAnalystAgent) -> dict[str, object]:
    return cast(dict[str, object], getattr(analyst, "_get_system_specs")())


@pytest.fixture
def mock_model_manager() -> _ModelManagerDouble:
    """ModelManager 목 객체."""
    mm = cast(_ModelManagerDouble, mock.MagicMock())
    mm.generate.return_value = json.dumps(
        {
            "title": "Hardware Upgrade Proposal for test-model",
            "current_bottleneck": "Insufficient RAM",
            "target_capabilities": "Run large models locally",
            "recommended_hardware": "Mac Studio M4 Ultra 192GB",
            "roi_justification": "Saves developer time",
        }
    )
    return mm


@pytest.fixture
def analyst(mock_model_manager: _ModelManagerDouble) -> HardwareAnalystAgent:
    """HardwareAnalystAgent 인스턴스."""
    return HardwareAnalystAgent(model_manager=cast(ModelManager, cast(object, mock_model_manager)))


class TestHardwareAnalystAgent:
    """Tests for HardwareAnalystAgent class."""

    def test_init(self, analyst: HardwareAnalystAgent, mock_model_manager: _ModelManagerDouble) -> None:
        """초기화 시 model_manager가 설정되어야 함."""
        assert analyst.model_manager is mock_model_manager

    def test_get_system_specs(self, analyst: HardwareAnalystAgent, monkeypatch: pytest.MonkeyPatch) -> None:
        """_get_system_specs가 시스템 스펙을 반환해야 함."""
        monkeypatch.setattr("antigravity_k.agents.hardware_analyst.platform.system", lambda: "Darwin")
        monkeypatch.setattr("antigravity_k.agents.hardware_analyst.platform.release", lambda: "24.0")
        monkeypatch.setattr("antigravity_k.agents.hardware_analyst.platform.machine", lambda: "arm64")

        def cpu_count(logical: bool = True) -> int:
            return 16 if logical else 8

        monkeypatch.setattr("antigravity_k.agents.hardware_analyst.psutil.cpu_count", cpu_count)

        def virtual_memory() -> SimpleNamespace:
            return SimpleNamespace(total=32 * 1024**3, available=16 * 1024**3)

        monkeypatch.setattr("antigravity_k.agents.hardware_analyst.psutil.virtual_memory", virtual_memory)

        specs = _system_specs(analyst)

        assert specs["os"] == "Darwin"
        assert specs["architecture"] == "arm64"
        assert specs["cpu_cores"] == 8
        assert specs["logical_cores"] == 16
        assert specs["total_ram_gb"] == 32.0
        assert specs["available_ram_gb"] == 16.0

    def test_propose_upgrade_success(self, analyst: HardwareAnalystAgent) -> None:
        """업그레이드 제안이 성공하면 기안서를 반환해야 함."""
        result = analyst.propose_upgrade("test-model", 64.0)
        assert "HardwareAnalystAgent" in result
        assert "Upgrade" in result or "기안" in result or "upgrade" in result.lower()

    def test_propose_upgrade_api_error_fallback(
        self, analyst: HardwareAnalystAgent, mock_model_manager: _ModelManagerDouble
    ) -> None:
        """API 에러 시 fallback 제안을 반환해야 함."""
        mock_model_manager.generate.return_value = "[API Error] The API returned an error"
        result = analyst.propose_upgrade("big-model", 128.0)
        assert "HardwareAnalystAgent" in result
        assert "API" in result or "기안" in result or "proposal" in result.lower()

    def test_propose_upgrade_json_decode_error(
        self, analyst: HardwareAnalystAgent, mock_model_manager: _ModelManagerDouble
    ) -> None:
        """JSON 디코드 에러 시 적절한 오류 메시지를 반환해야 함."""
        mock_model_manager.generate.return_value = "not json at all {{{"
        result = analyst.propose_upgrade("test", 16.0)
        assert "failed" in result.lower()

    def test_propose_upgrade_general_exception(
        self, analyst: HardwareAnalystAgent, mock_model_manager: _ModelManagerDouble
    ) -> None:
        """일반 예외 발생 시 적절한 오류 메시지를 반환해야 함."""
        mock_model_manager.generate.side_effect = RuntimeError("API timeout")
        result = analyst.propose_upgrade("test", 16.0)
        assert "failed" in result.lower()

    def test_propose_upgrade_with_code_block(
        self, analyst: HardwareAnalystAgent, mock_model_manager: _ModelManagerDouble
    ) -> None:
        """JSON이 코드 블록으로 감싸져 있어도 파싱되어야 함."""
        mock_model_manager.generate.return_value = (
            '```json\n{\n    "title": "Upgrade Proposal",\n'
            '    "current_bottleneck": "RAM limit",\n'
            '    "target_capabilities": "Run models",\n'
            '    "recommended_hardware": "128GB RAM upgrade",\n'
            '    "roi_justification": "Productivity boost"\n}\n```'
        )
        result = analyst.propose_upgrade("model", 64.0)
        assert "HardwareAnalystAgent" in result or "RAM" in result or "제안" in result

    def test_propose_upgrade_empty_response(
        self, analyst: HardwareAnalystAgent, mock_model_manager: _ModelManagerDouble
    ) -> None:
        """빈 응답 시 오류 처리가 되어야 함."""
        mock_model_manager.generate.return_value = ""
        result = analyst.propose_upgrade("test", 16.0)
        assert "failed" in result.lower() or "Error" in result or "error" in result

    def test_propose_upgrade_invalid_json_format(
        self, analyst: HardwareAnalystAgent, mock_model_manager: _ModelManagerDouble
    ) -> None:
        """JSON 형식이지만 필드가 누락된 경우에도 처리되어야 함."""
        mock_model_manager.generate.return_value = '{"invalid": "structure"}'
        result = analyst.propose_upgrade("model", 32.0)
        assert "HardwareAnalystAgent" in result or "failed" in result.lower()
