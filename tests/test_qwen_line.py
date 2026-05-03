import sys
import logging
import asyncio
logging.basicConfig(level=logging.DEBUG)
sys.path.insert(0, "./src")

from antigravity_k.engine.model_manager import ModelManager, ModelRegistry
import urllib.request
import json
from antigravity_k.config import config

registry = ModelRegistry()
manager = ModelManager(registry)

api_msgs = [
  {
    "role": "system",
    "content": "You are an expert UI/UX Designer. You specialize in creating premium, modern interfaces. Provide feedback on visual elements, color palettes, spacing, typography, and micro-animations. Always respond in Korean."
  },
  {
    "role": "user",
    "content": "Create a comprehensive conceptual blueprint for a project-sharing website named 'Ssak AI Lab'. The concept should include: 1) Core product positioning & target audience, 2) Information architecture & site structure (sitemap), 3) Key features for project showcasing, collaboration, and sharing, 4) UI/UX direction & visual branding guidelines for 'Ssak AI Lab', 5) Recommended tech stack (frontend, backend, database, hosting), and 6) A phased development roadmap from MVP to scaling."
  }
]

url = "http://localhost:11434/v1/chat/completions"
data = {
    "model": "qwen3.6:latest",
    "stream": True,
    "messages": api_msgs
}

req = urllib.request.Request(
    url, 
    data=json.dumps(data).encode("utf-8"), 
    headers={
        "Content-Type": "application/json",
    }
)

with urllib.request.urlopen(req) as response:
    for line in response:
        line = line.decode("utf-8").strip()
        if line:
            print(f"LINE: {line}")
