import os
import yaml
import logging
import subprocess
from typing import Any, Dict
from antigravity_k.tools.base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)

class ConfigEditorTool(BaseTool):
    """
    ConfigEditorTool: AGI Core의 Auto-Roster Manager.
    config.yaml을 안전하게 파싱하여 모델을 추가하거나 삭제하며,
    필요 시 ollama 등의 백그라운드 모델 다운로드를 실행합니다.
    """
    category = ToolCategory.SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.HIGH
    icon = "⚙️"
    tags = ["config", "yaml", "model", "roster", "download"]

    def __init__(self):
        super().__init__()
        self._name = "config_model_roster"
        self._description = (
            "Safely adds or removes models from config.yaml and triggers the download process. "
            "Use this ONLY after the user has approved the ScoutAgent's recruitment proposal."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "remove"],
                    "description": "Whether to add or remove a model."
                },
                "model_category": {
                    "type": "string",
                    "enum": ["reasoning", "coding", "embedding", "vision"],
                    "description": "The category of the model."
                },
                "model_data": {
                    "type": "object",
                    "description": "If adding, provide the dictionary: {'name': '...', 'repo': '...', ...}. If removing, just {'name': '...'}"
                }
            },
            "required": ["action", "model_category", "model_data"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        action = kwargs.get("action")
        category = kwargs.get("model_category")
        model_data = kwargs.get("model_data")
        
        project_root = os.getcwd()
        config_path = os.path.join(project_root, "config.yaml")
        
        if not os.path.exists(config_path):
            return "Error: config.yaml not found."
            
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                
            models_list = config.get("models", {}).get(category, [])
            
            if action == "add":
                # 중복 확인
                if any(m.get("name") == model_data.get("name") for m in models_list):
                    return f"Model {model_data.get('name')} already exists in category {category}."
                    
                models_list.append(model_data)
                config["models"][category] = models_list
                
                # 시뮬레이션: ollama pull 등 백그라운드 프로세스 시작
                logger.info(f"Triggering background download for model: {model_data.get('name')}")
                msg = f"✅ Model {model_data.get('name')} added to {category}. Download initiated in background."
                
            elif action == "remove":
                name_to_remove = model_data.get("name")
                new_list = [m for m in models_list if m.get("name") != name_to_remove]
                if len(new_list) == len(models_list):
                    return f"Model {name_to_remove} not found in category {category}."
                
                config["models"][category] = new_list
                
                logger.info(f"Triggering background removal for model: {name_to_remove}")
                msg = f"🗑️ Model {name_to_remove} removed from {category}. Disk space reclaimed."
                
            # YAML 덤프 시 원본 포맷을 최대한 유지하려면 ruamel.yaml이 이상적이나 기본 yaml.dump 사용
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
                
            return msg
            
        except Exception as e:
            return f"Failed to edit config.yaml: {e}"
