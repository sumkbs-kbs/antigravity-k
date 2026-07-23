"""Tests for the Hardware Analyst module."""

import json
from unittest import mock

import pytest

from antigravity_k.agents.hardware_analyst import HardwareAnalystAgent


@pytest.fixture
def mock_model_manager():
    """ModelManager 목 객체."""
    mm = mock.MagicMock()
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
def analyst(mock_model_manager):
    """HardwareAnalystAgent 인스턴스."""
    return HardwareAnalystAgent(model_manager=mock_model_manager)


class TestHardwareAnalystAgent:
    """Tests for HardwareAnalystAgent class."""

    def test_init(self, analyst, mock_model_manager):
        """초기화 시 model_manager가 설정되어야 함."""
        assert analyst.model_manager is mock_model_manager

    def test_get_system_specs(self, analyst):
        """_get_system_specs가 시스템 스펙을 반환해야 함."""
        with mock.patch("antigravity_k.agents.hardware_analyst.platform.system", return_value="Darwin"):
            with mock.patch("antigravity_k.agents.hardware_analyst.platform.release", return_value="24.0"):
                with mock.patch("antigravity_k.agents.hardware_analyst.platform.machine", return_value="arm64"):
                    with mock.patch("antigravity_k.agents.hardware_analyst.psutil.cpu_count") as mock_cpu:
                        mock_cpu.side_effect = lambda logical=False: 8 if not logical else 16
                        with mock.patch(
                            "antigravity_k.agents.hardware_analyst.psutil.virtual_memory",
                        ) as mock_mem:
                            mock_mem.return_value.total = 32 * 1024**3  # 32GB
                            mock_mem.return_value.available = 16 * 1024**3  # 16GB

                            specs = analyst._get_system_specs()

                            assert specs["os"] == "Darwin"
                            assert specs["architecture"] == "arm64"
                            assert specs["cpu_cores"] == 8
                            assert specs["logical_cores"] == 16
                            assert specs["total_ram_gb"] == 32.0
                            assert specs["available_ram_gb"] == 16.0

    def test_propose_upgrade_success(self, analyst, mock_model_manager):
        """업그레이드 제안이 성공하면 기안서를 반환해야 함."""
        result = analyst.propose_upgrade("test-model", 64.0)
        assert "HardwareAnalystAgent" in result
        assert "Upgrade" in result or "기안" in result or "upgrade" in result.lower()

    def test_propose_upgrade_api_error_fallback(self, analyst, mock_model_manager):
        """API 에러 시 fallback 제안을 반환해야 함."""
        mock_model_manager.generate.return_value = "[API Error] The API returned an error"
        result = analyst.propose_upgrade("big-model", 128.0)
        assert "HardwareAnalystAgent" in result
        assert "API" in result or "기안" in result or "proposal" in result.lower()

    def test_propose_upgrade_json_decode_error(self, analyst, mock_model_manager):
        """JSON 디코드 에러 시 적절한 오류 메시지를 반환해야 함."""
        mock_model_manager.generate.return_value = "not json at all {{{"
        result = analyst.propose_upgrade("test", 16.0)
        assert "failed" in result.lower()

    def test_propose_upgrade_general_exception(self, analyst, mock_model_manager):
        """일반 예외 발생 시 적절한 오류 메시지를 반환해야 함."""
        mock_model_manager.generate.side_effect = RuntimeError("API timeout")
        result = analyst.propose_upgrade("test", 16.0)
        assert "failed" in result.lower()

    def test_propose_upgrade_with_code_block(self, analyst, mock_model_manager):
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

    def test_propose_upgrade_empty_response(self, analyst, mock_model_manager):
        """빈 응답 시 오류 처리가 되어야 함."""
        mock_model_manager.generate.return_value = ""
        result = analyst.propose_upgrade("test", 16.0)
        assert "failed" in result.lower() or "Error" in result or "error" in result

    def test_propose_upgrade_invalid_json_format(self, analyst, mock_model_manager):
        """JSON 형식이지만 필드가 누락된 경우에도 처리되어야 함."""
        mock_model_manager.generate.return_value = '{"invalid": "structure"}'
        result = analyst.propose_upgrade("model", 32.0)
        assert "HardwareAnalystAgent" in result or "failed" in result.lower()
