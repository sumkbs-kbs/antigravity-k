import sys
import logging
logging.basicConfig(level=logging.DEBUG)
sys.path.insert(0, "./src")

from antigravity_k.engine.model_manager import ModelManager, ModelRegistry

registry = ModelRegistry()
manager = ModelManager(registry)
stream = manager.stream_generate("Hello", target="qwen3.6:latest")
print("Got stream generator")
try:
    for chunk in stream:
        print(f"CHUNK: {chunk}")
except Exception as e:
    print(f"EXCEPTION: {e}")
print("Done")
