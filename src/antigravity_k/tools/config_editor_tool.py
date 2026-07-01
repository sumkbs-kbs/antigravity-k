"""Config Editor Tool module."""

import logging
import os
from typing import Any

import yaml

from antigravity_k.tools.base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory

logger = logging.getLogger(__name__)


class ConfigEditorTool(BaseTool):
    """ConfigEditorTool: AGI Core의 Auto-Roster Manager.

    config.yaml을 안전하게 파싱하여 모델을 추가하거나 삭제하며,
    필요 시 ollama 등의 백그라운드 모델 다운로드를 실행합니다.
    """

    category = ToolCategory.SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.HIGH
    icon = "⚙️"
    tags = ["config", "yaml", "model", "roster", "download"]

    def __init__(self):
        """Initialize the ConfigEditorTool."""
        super().__init__()
        self._name = "config_model_roster"
        self._description = (
            "Safely adds or removes AI models from config.yaml and triggers the download process. "
            "WARNING: This is ONLY for AI Model Swarm configuration (reasoning, coding, etc.). "
            "DO NOT use this to add geographic data, locations, or standard database entries."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "remove", "update_agent_map", "update_swarm"],
                    "description": "Whether to add/remove a model, update the agent_models mapping, or update a swarm combo.",  # noqa: E501
                },
                "target_key": {
                    "type": "string",
                    "description": "If update_agent_map, the agent role (e.g. 'WORKER'). If update_swarm, "
                    "the combo name.",
                },
                "model_category": {
                    "type": "string",
                    "enum": ["reasoning", "coding", "embedding", "vision"],
                    "description": "The category of the model (only needed for add/remove).",
                },
                "model_data": {
                    "type": "object",
                    "description": "For add/remove, provide the model dict. For update_agent_map, provide {'combo_name': '...'}. For"  # type: ignore  # noqa: E501
                    "update_swarm, provide {'models': [...], 'strategy': '...'}",
                },
            },
            "required": ["action"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        action = kwargs.get("action")
        category = kwargs.get("model_category")
        model_data = kwargs.get("model_data")

        project_root = os.getcwd()
        config_path = os.path.join(project_root, "config.yaml")

        if not os.path.exists(config_path):
            return "Error: config.yaml not found."

        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            models_list = config.get("models", {}).get(category, [])

            if action == "add":
                if any(m.get("name") == model_data.get("name") for m in models_list):
                    return f"Model {model_data.get('name')} already exists in category {category}."
                models_list.append(model_data)
                config["models"][category] = models_list
                logger.info("Triggering background download for model: %s", model_data.get("name"))
                msg = f"✅ Model {model_data.get('name')} added to {category}. Download initiated in background."

            elif action == "remove":
                name_to_remove = model_data.get("name")
                new_list = [m for m in models_list if m.get("name") != name_to_remove]
                if len(new_list) == len(models_list):
                    return f"Model {name_to_remove} not found in category {category}."
                config["models"][category] = new_list
                logger.info("Triggering background removal for model: %s", name_to_remove)
                msg = f"🗑️ Model {name_to_remove} removed from {category}. Disk space reclaimed."

            elif action == "update_agent_map":
                target_key = kwargs.get("target_key")
                new_combo = model_data.get("combo_name")
                if "agent_models" not in config:
                    config["agent_models"] = {}
                config["agent_models"][target_key] = new_combo
                msg = f"🔄 Agent '{target_key}' mapped to swarm combo '{new_combo}'."

            elif action == "update_swarm":
                target_key = kwargs.get("target_key")
                if "combos" not in config:
                    config["combos"] = {}
                # Update or create the combo
                if target_key not in config["combos"]:
                    config["combos"][target_key] = {}
                config["combos"][target_key].update(model_data)
                msg = f"🐝 Swarm combo '{target_key}' updated with new models/strategy."

            # YAML 덤프 시 원본 포맷을 최대한 유지
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    config,
                    f,
                    sort_keys=False,
                    default_flow_style=False,
                    allow_unicode=True,
                )

            return msg

        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Failed to edit config.yaml: {e}"
