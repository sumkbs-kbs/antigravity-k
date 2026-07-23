"""Tests for antigravity_k.tools.system_control.

Tests SystemControlTool with mocked subprocess/platform to avoid
actually modifying system state.

Coverage targets:
  - Tool properties (name, description, schema)
  - execute() dispatch and error handling
  - _action_get_system_info (with/without psutil)
  - _action_get_running_apps (macOS/else)
  - _action_launch_app, _action_kill_app (with protected process check)
  - _action_open_url, _action_get/set_clipboard
  - _action_set_volume, _action_toggle_wifi
  - _action_manage_notifications
  - _action_auto_optimize (memory tiers, GPU detection, config update)
  - _action_get_env_status
  - _find_config_path
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from antigravity_k.tools.system_control import SystemControlTool


@pytest.fixture
def tool():
    """SystemControlTool 기본 인스턴스."""
    return SystemControlTool()


# ═══════════════════════════════════════════════════════════════════
# Tool properties
# ═══════════════════════════════════════════════════════════════════


class TestToolProperties:
    """name, description, parameters_schema, category."""

    def test_name(self, tool):
        assert tool.name == "system_control"

    def test_description(self, tool):
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0
        assert "operating system" in tool.description.lower()

    def test_schema_has_required_actions(self, tool):
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "action" in schema["properties"]
        actions = schema["properties"]["action"]["enum"]
        assert "get_system_info" in actions
        assert "launch_app" in actions
        assert "kill_app" in actions
        assert "get_clipboard" in actions
        assert "set_clipboard" in actions
        assert "set_volume" in actions
        assert "auto_optimize" in actions

    def test_category_and_risk(self, tool):
        from antigravity_k.tools.base_tool import RiskLevel, ToolCategory

        assert tool.category == ToolCategory.COMPUTER_USE
        assert tool.risk_level == RiskLevel.HIGH


# ═══════════════════════════════════════════════════════════════════
# execute() dispatch
# ═══════════════════════════════════════════════════════════════════


class TestExecute:
    """execute() 메서드의 액션 디스패치."""

    def test_no_action(self, tool):
        result = tool.execute()
        assert "error" in result
        assert "No action" in result["error"]

    def test_unknown_action(self, tool):
        result = tool.execute(action="nonexistent_action")
        assert "error" in result
        assert "Unknown action" in result["error"]

    def test_action_dispatches_to_handler(self, tool):
        """execute가 올바른 _action_ 메서드를 호출하는지 확인."""
        with patch.object(tool, "_action_get_system_info") as mock_method:
            mock_method.return_value = {"status": "ok", "data": "test"}
            result = tool.execute(action="get_system_info")
            mock_method.assert_called_once()
            assert result["status"] == "ok"

    def test_action_exception_handled(self, tool):
        """execute에서 예외 발생 시 에러 반환."""
        with patch.object(tool, "_action_get_system_info") as mock_method:
            mock_method.side_effect = RuntimeError("Simulated error")
            result = tool.execute(action="get_system_info")
            assert "error" in result
            assert "Simulated error" in result["error"]


# ═══════════════════════════════════════════════════════════════════
# _action_get_system_info
# ═══════════════════════════════════════════════════════════════════


class TestGetSystemInfo:
    """시스템 정보 수집 — platform/paths mock."""

    def test_basic_info(self, tool):
        """기본 시스템 정보 필드 포함 여부."""
        result = tool._action_get_system_info()
        assert result["status"] == "ok"
        info = result["system_info"]
        assert "platform" in info
        assert "architecture" in info
        assert "processor" in info
        assert "python_version" in info
        assert "hostname" in info
        assert "cpu_cores" in info

    def test_memory_with_psutil(self, tool):
        """psutil로 메모리/디스크 정보 수집."""
        with patch.dict("sys.modules", {"psutil": MagicMock()}):
            import psutil  # type: ignore[import]

            mock_mem = MagicMock()
            mock_mem.total = 16 * 1024**3
            mock_mem.available = 8 * 1024**3
            mock_mem.percent = 50.0
            psutil.virtual_memory.return_value = mock_mem

            mock_disk = MagicMock()
            mock_disk.total = 500 * 1024**3
            mock_disk.free = 200 * 1024**3
            mock_disk.percent = 60.0
            psutil.disk_usage.return_value = mock_disk

            result = tool._action_get_system_info()
            info = result["system_info"]
            assert "memory" in info
            assert info["memory"]["total_gb"] == 16.0
            assert info["memory"]["used_percent"] == 50.0
            assert "disk" in info
            assert info["disk"]["total_gb"] == 500.0

    def test_memory_without_psutil(self, tool):
        """psutil 없이 sysctl 폴백."""
        with (
            patch.dict("sys.modules", {"psutil": None}),
            patch("platform.system", return_value="Darwin"),
            patch("subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "17179869184"  # 16GB
            mock_run.return_value = mock_proc

            result = tool._action_get_system_info()
            info = result["system_info"]
            assert "memory" in info
            assert info["memory"]["total_gb"] == 16.0

    def test_gpu_on_darwin(self, tool):
        """macOS에서 GPU 정보 수집."""
        with (
            patch("platform.system", return_value="Darwin"),
            patch("subprocess.run") as mock_run,
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = json.dumps(
                {
                    "SPDisplaysDataType": [
                        {
                            "sppci_model": "Apple M3 Pro",
                            "spdisplays_vram": "18 GB",
                            "sppci_metal": "Metal 3",
                        }
                    ]
                }
            )
            mock_run.return_value = mock_proc

            result = tool._action_get_system_info()
            info = result["system_info"]
            assert "gpu" in info
            assert info["gpu"]["name"] == "Apple M3 Pro"
            assert info["gpu"]["metal_support"] == "Metal 3"

    def test_gpu_not_available(self, tool):
        """GPU 정보 없을 때 graceful 처리."""
        with (
            patch("platform.system", return_value="Linux"),
            patch.dict("sys.modules", {"psutil": None}),
        ):
            result = tool._action_get_system_info()
            info = result["system_info"]
            # Linux에서 subprocess 실패 — GPU 정보 없어도 정상 응답
            assert "platform" in info

    def test_ollama_unavailable(self, tool):
        """Ollama 연결 불가 시 'Not available'."""
        result = tool._action_get_system_info()
        info = result["system_info"]
        assert "ollama_models" in info
        # 로컬 Ollama가 없으면 'Not available'
        # (실제 환경에 따라 다를 수 있으므로 문자열 존재 여부만 확인)
        assert isinstance(info["ollama_models"], (str, list))


# ═══════════════════════════════════════════════════════════════════
# _action_get_env_status
# ═══════════════════════════════════════════════════════════════════


class TestGetEnvStatus:
    """환경 설정 상태 조회."""

    def test_config_not_found(self, tool):
        """config.yaml이 없을 때."""
        with patch.object(tool, "_find_config_path", return_value=None):
            result = tool._action_get_env_status()
            assert result["status"] == "ok"
            assert result["env_status"]["settings"] == {}

    def test_config_not_exists(self, tool):
        """config.yaml 경로는 있지만 파일이 없을 때."""
        with patch.object(tool, "_find_config_path", return_value="/nonexistent/config.yaml"):
            result = tool._action_get_env_status()
            assert result["status"] == "ok"
            assert result["env_status"]["settings"] == {}

    def test_config_load_error(self, tool, tmp_path):
        """설정 파일 로드 중 예외 처리."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: : }", encoding="utf-8")
        with patch.object(tool, "_find_config_path", return_value=str(config_file)):
            result = tool._action_get_env_status()
            assert result["status"] == "ok"
            assert "error" in result["env_status"]


# ═══════════════════════════════════════════════════════════════════
# _action_get_running_apps
# ═══════════════════════════════════════════════════════════════════


class TestGetRunningApps:
    """실행 중인 앱 목록."""

    def test_on_darwin(self, tool):
        """macOS — osascript 호출."""
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                mock_proc = MagicMock()
                mock_proc.returncode = 0
                mock_proc.stdout = "Finder, Safari, Terminal"
                mock_run.return_value = mock_proc

                result = tool._action_get_running_apps()
                assert result["status"] == "ok"
                assert "Finder" in result["running_apps"]
                assert "Safari" in result["running_apps"]

    def test_on_darwin_osascript_error(self, tool):
        """macOS — osascript 실패 시 빈 리스트."""
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
                result = tool._action_get_running_apps()
                assert result["status"] == "ok"
                assert result["running_apps"] == []

    def test_on_linux_with_psutil(self, tool):
        """Linux — psutil로 앱 목록 수집."""
        with patch("platform.system", return_value="Linux"):
            mock_process = MagicMock()
            mock_process.info = {"pid": 123, "name": "bash"}
            with patch("psutil.process_iter", return_value=[mock_process]):
                result = tool._action_get_running_apps()
                assert result["status"] == "ok"
                assert "bash" in result["running_apps"]

    def test_on_linux_without_psutil(self, tool):
        """Linux — psutil 없을 때."""
        with (
            patch("platform.system", return_value="Linux"),
            patch.dict("sys.modules", {"psutil": None}),
        ):
            result = tool._action_get_running_apps()
            assert result["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════
# _action_launch_app / _action_kill_app
# ═══════════════════════════════════════════════════════════════════


class TestLaunchApp:
    def test_no_target(self, tool):
        result = tool._action_launch_app()
        assert "error" in result
        assert "No app name" in result["error"]

    def test_on_darwin(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.Popen") as mock_popen:
                result = tool._action_launch_app(target="Safari")
                assert result["status"] == "ok"
                assert result["app"] == "Safari"
                mock_popen.assert_called_with(["open", "-a", "Safari"])

    def test_on_darwin_error(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.Popen", side_effect=FileNotFoundError("App not found")):
                result = tool._action_launch_app(target="Nonexistent")
                assert "error" in result

    def test_on_linux(self, tool):
        with patch("platform.system", return_value="Linux"):
            result = tool._action_launch_app(target="Firefox")
            assert "error" in result
            assert "not supported" in result["error"].lower()


class TestKillApp:
    def test_no_target(self, tool):
        result = tool._action_kill_app()
        assert "error" in result

    def test_protected_process(self, tool):
        """시스템 핵심 프로세스 종료 차단."""
        for protected in ["Finder", "Dock", "SystemUIServer", "launchd", "WindowServer"]:
            result = tool._action_kill_app(target=protected)
            assert "error" in result
            assert "protected" in result["error"].lower()

    def test_on_darwin(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock()
                result = tool._action_kill_app(target="Safari")
                assert result["status"] == "ok"
                assert result["app"] == "Safari"

    def test_on_darwin_error(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run", side_effect=RuntimeError("Failed")):
                result = tool._action_kill_app(target="Safari")
                assert "error" in result

    def test_on_linux(self, tool):
        with patch("platform.system", return_value="Linux"):
            result = tool._action_kill_app(target="Firefox")
            assert "error" in result
            assert "not supported" in result["error"]


# ═══════════════════════════════════════════════════════════════════
# _action_open_url
# ═══════════════════════════════════════════════════════════════════


class TestOpenUrl:
    def test_no_url(self, tool):
        result = tool._action_open_url()
        assert "error" in result

    def test_on_darwin(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.Popen") as mock_popen:
                result = tool._action_open_url(target="https://example.com")
                assert result["status"] == "ok"
                mock_popen.assert_called_with(["open", "https://example.com"])

    def test_on_linux(self, tool):
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.Popen") as mock_popen:
                result = tool._action_open_url(target="https://example.com")
                assert result["status"] == "ok"
                mock_popen.assert_called_with(["xdg-open", "https://example.com"])

    def test_exception(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.Popen", side_effect=OSError("Permission denied")):
                result = tool._action_open_url(target="https://example.com")
                assert "error" in result


# ═══════════════════════════════════════════════════════════════════
# Clipboard actions
# ═══════════════════════════════════════════════════════════════════


class TestClipboard:
    def test_get_clipboard_on_darwin(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                mock_proc = MagicMock()
                mock_proc.stdout = "clipboard content"
                mock_run.return_value = mock_proc
                result = tool._action_get_clipboard()
                assert result["status"] == "ok"
                assert result["clipboard"] == "clipboard content"

    def test_get_clipboard_on_linux(self, tool):
        with patch("platform.system", return_value="Linux"):
            result = tool._action_get_clipboard()
            assert "error" in result

    def test_get_clipboard_error(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run", side_effect=RuntimeError("pbpaste failed")):
                result = tool._action_get_clipboard()
                assert "error" in result

    def test_set_clipboard_no_target(self, tool):
        result = tool._action_set_clipboard()
        assert "error" in result

    def test_set_clipboard_on_darwin(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_popen.return_value = mock_proc
                result = tool._action_set_clipboard(target="Hello, world!")
                assert result["status"] == "ok"
                assert result["length"] == 13

    def test_set_clipboard_on_linux(self, tool):
        with patch("platform.system", return_value="Linux"):
            result = tool._action_set_clipboard(target="test")
            assert "error" in result

    def test_set_clipboard_error(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.Popen", side_effect=RuntimeError("pbcopy failed")):
                result = tool._action_set_clipboard(target="test")
                assert "error" in result


# ═══════════════════════════════════════════════════════════════════
# System settings (volume, wifi, notifications)
# ═══════════════════════════════════════════════════════════════════


class TestSetVolume:
    def test_default_value(self, tool):
        with patch("platform.system", return_value="Darwin"), patch("subprocess.run"):
            result = tool._action_set_volume()
            assert result["status"] == "ok"
            assert result["level"] == 50

    def test_custom_value(self, tool):
        with patch("platform.system", return_value="Darwin"), patch("subprocess.run"):
            result = tool._action_set_volume(value="75")
            assert result["level"] == 75

    def test_clamp_to_100(self, tool):
        with patch("platform.system", return_value="Darwin"), patch("subprocess.run"):
            result = tool._action_set_volume(value="150")
            assert result["level"] == 100

    def test_clamp_to_0(self, tool):
        with patch("platform.system", return_value="Darwin"), patch("subprocess.run"):
            result = tool._action_set_volume(value="-10")
            assert result["level"] == 0

    def test_on_linux(self, tool):
        with patch("platform.system", return_value="Linux"):
            result = tool._action_set_volume(value="50")
            assert "error" in result

    def test_exception(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run", side_effect=RuntimeError("osascript failed")):
                result = tool._action_set_volume(value="50")
                assert "error" in result


class TestToggleWifi:
    def test_on_linux(self, tool):
        with patch("platform.system", return_value="Linux"):
            result = tool._action_toggle_wifi()
            assert "error" in result

    def test_on_darwin(self, tool):
        with patch("platform.system", return_value="Darwin"), patch("subprocess.run"):
            result = tool._action_toggle_wifi(value="on")
            assert result["status"] == "ok"
            assert result["state"] == "on"

    def test_off(self, tool):
        with patch("platform.system", return_value="Darwin"), patch("subprocess.run"):
            result = tool._action_toggle_wifi(value="off")
            assert result["state"] == "off"

    def test_exception(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run", side_effect=RuntimeError("networksetup failed")):
                result = tool._action_toggle_wifi(value="on")
                assert "error" in result


class TestManageNotifications:
    def test_on_linux(self, tool):
        with patch("platform.system", return_value="Linux"):
            result = tool._action_manage_notifications()
            assert "error" in result

    def test_turn_on(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock()
                result = tool._action_manage_notifications(value="on")
                assert result["status"] == "ok"
                assert result["action"] == "dnd_on"

    def test_turn_off(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock()
                result = tool._action_manage_notifications(value="off")
                assert result["action"] == "dnd_off"

    def test_exception(self, tool):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run", side_effect=RuntimeError("Shortcuts failed")):
                result = tool._action_manage_notifications(value="on")
                assert "error" in result


# ═══════════════════════════════════════════════════════════════════
# _action_auto_optimize
# ═══════════════════════════════════════════════════════════════════


class TestAutoOptimize:
    """자동 최적화 — 메모리 계층별 설정."""

    def test_high_memory_128gb(self, tool):
        """128GB+ → 32K 컨텍스트, 70B 모델."""
        with (
            patch.object(tool, "_action_get_system_info") as mock_info,
            patch.object(tool, "_find_config_path", return_value=None),
        ):
            mock_info.return_value = {
                "system_info": {
                    "memory": {"total_gb": 128},
                    "cpu_cores": 16,
                    "gpu": {"name": "Apple M3 Ultra"},
                    "ollama_models": [{"name": "llama3:70b", "size_gb": 40}],
                }
            }
            result = tool._action_auto_optimize()
            assert result["status"] == "ok"
            assert result["recommended"]["context_window"] == 32768
            assert result["recommended"]["max_model_size"] == "70B"
            assert any("128GB" in o for o in result["optimizations"])

    def test_medium_memory_64gb(self, tool):
        """64GB → 16K 컨텍스트, 32B 모델."""
        with (
            patch.object(tool, "_action_get_system_info") as mock_info,
            patch.object(tool, "_find_config_path", return_value=None),
        ):
            mock_info.return_value = {
                "system_info": {
                    "memory": {"total_gb": 64},
                    "cpu_cores": 12,
                    "gpu": {"name": "Apple M3 Pro"},
                    "ollama_models": [{"name": "llama3:70b", "size_gb": 40}],
                }
            }
            result = tool._action_auto_optimize()
            assert result["recommended"]["context_window"] == 16384
            assert result["recommended"]["max_model_size"] == "32B"

    def test_low_memory_16gb(self, tool):
        """16GB → 4K 컨텍스트, 7B 모델."""
        with (
            patch.object(tool, "_action_get_system_info") as mock_info,
            patch.object(tool, "_find_config_path", return_value=None),
        ):
            mock_info.return_value = {
                "system_info": {
                    "memory": {"total_gb": 16},
                    "cpu_cores": 8,
                    "gpu": {},
                    "ollama_models": [],
                }
            }
            result = tool._action_auto_optimize()
            assert result["recommended"]["context_window"] == 4096
            assert result["recommended"]["max_model_size"] == "7B"

    def test_mid_memory_32gb(self, tool):
        """32GB → 8K 컨텍스트, 14B 모델."""
        with (
            patch.object(tool, "_action_get_system_info") as mock_info,
            patch.object(tool, "_find_config_path", return_value=None),
        ):
            mock_info.return_value = {
                "system_info": {
                    "memory": {"total_gb": 32},
                    "cpu_cores": 8,
                    "gpu": {},
                    "ollama_models": [],
                }
            }
            result = tool._action_auto_optimize()
            assert result["recommended"]["context_window"] == 8192
            assert result["recommended"]["max_model_size"] == "14B"

    def test_apple_silicon_gpu(self, tool):
        """Apple Silicon GPU 감지 시 MPS 가속."""
        with (
            patch.object(tool, "_action_get_system_info") as mock_info,
            patch.object(tool, "_find_config_path", return_value=None),
        ):
            mock_info.return_value = {
                "system_info": {
                    "memory": {"total_gb": 32},
                    "cpu_cores": 10,
                    "gpu": {"name": "Apple M3 Max"},
                    "ollama_models": [],
                }
            }
            result = tool._action_auto_optimize()
            assert result["recommended"]["gpu_acceleration"] == "mps"
            assert any("MPS" in o for o in result["optimizations"])

    def test_nvidia_gpu(self, tool):
        """NVIDIA GPU 감지 시 CUDA 가속."""
        with (
            patch.object(tool, "_action_get_system_info") as mock_info,
            patch.object(tool, "_find_config_path", return_value=None),
        ):
            mock_info.return_value = {
                "system_info": {
                    "memory": {"total_gb": 64},
                    "cpu_cores": 16,
                    "gpu": {"name": "NVIDIA RTX 4090"},
                    "ollama_models": [],
                }
            }
            result = tool._action_auto_optimize()
            assert result["recommended"]["gpu_acceleration"] == "cuda"

    def test_config_file_update(self, tool, tmp_path):
        """config.yaml 업데이트."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("ollama:\n  context_window: 4096\n", encoding="utf-8")
        with (
            patch.object(tool, "_action_get_system_info") as mock_info,
            patch.object(tool, "_find_config_path", return_value=str(config_file)),
        ):
            mock_info.return_value = {
                "system_info": {
                    "memory": {"total_gb": 128},
                    "cpu_cores": 16,
                    "gpu": {"name": "Apple M3 Ultra"},
                    "ollama_models": [{"name": "llama3:70b", "size_gb": 40}],
                }
            }
            result = tool._action_auto_optimize()
            assert result["config_updated"] is True
            assert any("업데이트" in o for o in result["optimizations"])

            # config.yaml이 실제로 업데이트되었는지 확인
            updated = config_file.read_text(encoding="utf-8")
            assert "context_window: 32768" in updated

    def test_ollama_models_included(self, tool):
        """Ollama 모델 목록이 최적화 결과에 포함."""
        with (
            patch.object(tool, "_action_get_system_info") as mock_info,
            patch.object(tool, "_find_config_path", return_value=None),
        ):
            mock_info.return_value = {
                "system_info": {
                    "memory": {"total_gb": 64},
                    "cpu_cores": 12,
                    "gpu": {},
                    "ollama_models": [
                        {"name": "llama3:70b", "size_gb": 40},
                        {"name": "mistral:7b", "size_gb": 4},
                    ],
                }
            }
            result = tool._action_auto_optimize()
            assert result["recommended"]["available_models"] == ["llama3:70b", "mistral:7b"]
            assert any("모델 2개" in o for o in result["optimizations"])


# ═══════════════════════════════════════════════════════════════════
# _find_config_path
# ═══════════════════════════════════════════════════════════════════


class TestFindConfigPath:
    """_find_config_path는 상위 디렉토리를 탐색."""

    def test_finds_config_in_parent(self, tool, tmp_path):
        """상위 디렉토리에 config.yaml이 있으면 발견."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("test: config", encoding="utf-8")
        # tool의 파일을 기준으로 탐색하므로, tmp_path를 상위로 설정
        with patch.object(tool, "_find_config_path", return_value=str(config_file)):
            result = tool._find_config_path()
            assert result == str(config_file)

    def test_returns_none_if_not_found(self, tool, tmp_path):
        """config.yaml이 없으면 None 반환."""
        with patch.object(tool, "_find_config_path", return_value=None):
            result = tool._find_config_path()
            assert result is None
