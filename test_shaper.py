import sys
import logging
sys.path.insert(0, "./src")
from antigravity_k.engine.context_manager import ContextShaper
shaper = ContextShaper()
messages = [{"role": "user", "content": "내가 진행하는 여러 프로젝트들을 공유 할수 있는 인터넷 웹사이트를 만들고 싶어 Ssak AI Lab 이름으로 전체적인 구상을 먼저 해줄래?"}]
print(shaper.shape(messages))
