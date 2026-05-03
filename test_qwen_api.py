import sys
import logging
import asyncio
logging.basicConfig(level=logging.DEBUG)
sys.path.insert(0, "./src")

from antigravity_k.engine.model_manager import ModelManager, ModelRegistry

registry = ModelRegistry()
manager = ModelManager(registry)

api_msgs = [
  {
    "role": "system",
    "content": "/no_think\nSystem: You are an expert UI/UX Designer. You specialize in creating premium, modern interfaces. Provide feedback on visual elements, color palettes, spacing, typography, and micro-animations. Always respond in Korean. /no_think\n"
  },
  {
    "role": "user",
    "content": "Create a comprehensive conceptual blueprint for a project-sharing website named 'Ssak AI Lab'. The concept should include: 1) Core product positioning & target audience, 2) Information architecture & site structure (sitemap), 3) Key features for project showcasing, collaboration, and sharing, 4) UI/UX direction & visual branding guidelines for 'Ssak AI Lab', 5) Recommended tech stack (frontend, backend, database, hosting), and 6) A phased development roadmap from MVP to scaling."
  }
]

stream = manager.stream_generate("fallback", target="qwen3.6:latest", raw_messages=api_msgs)
print("Got stream generator")
try:
    for chunk in stream:
        print(f"RAW CHUNK: {repr(chunk)}")
except Exception as e:
    print(f"EXCEPTION: {e}")
print("Done")
