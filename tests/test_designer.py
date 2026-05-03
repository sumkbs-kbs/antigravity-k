import sys
import logging
import asyncio
logging.basicConfig(level=logging.DEBUG)
sys.path.insert(0, "./src")

from antigravity_k.engine.model_manager import ModelManager, ModelRegistry

registry = ModelRegistry()
manager = ModelManager(registry)

prompt = """/no_think
System: You are DESIGNER.
User: 내가 진행하는 여러 프로젝트들을 공유 할수 있는 인터넷 웹사이트를 만들고 싶어 Ssak AI Lab 이름으로 전체적인 구상을 먼저 해줄래?
Assistant: """

stream = manager.stream_generate(prompt, target="qwen3.6:latest")
print("Got stream generator")
try:
    for chunk in stream:
        print(f"CHUNK: {repr(chunk)}")
except Exception as e:
    print(f"EXCEPTION: {e}")
print("Done")
