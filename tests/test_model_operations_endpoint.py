from unittest.mock import MagicMock


def test_model_operations_status_exposes_provider_capabilities_and_task_metrics() -> None:
    from antigravity_k.api.routes.legacy import model_operations_status

    manager = MagicMock()
    manager.provider_capabilities.return_value = {
        "qwen3.6:latest": {
            "model": "qwen3.6:latest",
            "provider": "ollama",
            "runtime_status": "available",
            "native_tool_calling": "supported",
        }
    }
    manager.router.status.return_value = {
        "quality_calibration": {
            "enabled": True,
            "eligible_models": ["qwen3.6:latest"],
            "ineligible_models": [],
            "operational_metrics": [
                {
                    "model": "qwen3.6:latest",
                    "outcome_count": 3,
                    "task_success_rate": 1.0,
                    "tool_accuracy": 1.0,
                    "retry_rate": 0.0,
                }
            ],
        }
    }

    result = model_operations_status(manager)

    assert result["provider_capabilities"]["qwen3.6:latest"]["runtime_status"] == "available"
    assert result["quality_calibration"]["operational_metrics"][0]["outcome_count"] == 3
    manager.provider_capabilities.assert_called_once_with(refresh=False)
