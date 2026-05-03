import sys
import logging
import asyncio
logging.basicConfig(level=logging.DEBUG)
sys.path.insert(0, "./src")

from antigravity_k.engine.model_manager import ModelManager, ModelRegistry

registry = ModelRegistry()
manager = ModelManager(registry)

sys_prompt = "/no_think\nSystem: You are DESIGNER."
raw_messages = [{"role": "user", "content": "웹사이트 만들고 싶어"}]

stream = manager.stream_generate("fallback", target="qwen3.6:latest", raw_messages=raw_messages, system_prompt=sys_prompt)
print("Got stream generator")
try:
    for chunk in stream:
        print(f"CHUNK: {repr(chunk)}")
except Exception as e:
    print(f"EXCEPTION: {e}")
print("Done")
