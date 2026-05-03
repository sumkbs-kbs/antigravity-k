import sys
import logging
import asyncio
logging.basicConfig(level=logging.DEBUG)
sys.path.insert(0, "./src")

from antigravity_k.engine.model_manager import ModelManager, ModelRegistry
from antigravity_k.engine.orchestrator import OrchestratorAgent

registry = ModelRegistry()
manager = ModelManager(registry)
orchestrator = OrchestratorAgent(model_manager=manager)

# Mock _do_ollama_stream
def mock_stream(loaded, prompt, **kwargs):
    import json
    sys_msg = kwargs.get("system_prompt", "")
    if sys_msg:
        api_msgs = [{"role": "system", "content": sys_msg}] + kwargs["raw_messages"]
    else:
        api_msgs = kwargs["raw_messages"]
    print("API MSGS:", json.dumps(api_msgs, indent=2, ensure_ascii=False))
    yield "mock"

manager._do_ollama_stream = mock_stream
messages = [{"role": "user", "content": "내가 진행하는 여러 프로젝트들을 공유 할수 있는 인터넷 웹사이트를 만들고 싶어 Ssak AI Lab 이름으로 전체적인 구상을 먼저 해줄래?"}]

for chunk in orchestrator.run_stream(messages, target_model="deepseek-r1:70b"):
    pass
