class DummyOrch:
    def _ceo_analyze(self, msg, model):
        yield "abc"


class DummyCtx:
    user_message = "hello"
    target_model = "test"

    def __init__(self):
        self.analysis = {}


import sys

sys.path.append("src")
from antigravity_k.engine.orchestrator_handlers import ceo_analyze_handler

ctx = DummyCtx()
orch = DummyOrch()
for chunk in ceo_analyze_handler(ctx, orch):
    print(chunk)
