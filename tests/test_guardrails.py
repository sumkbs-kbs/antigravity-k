import pytest
from antigravity_k.engine.tool_guardrail_manager import ToolGuardrailManager, GuardrailDecision

class BrokenGuard:
    def check_tool_boundary(self, name):
        raise ValueError("Simulated Exception")
        
    def check_tool_plan(self, name):
        raise ValueError("Simulated Exception")
        
    def before_call(self, name, args):
        raise ValueError("Simulated Exception")

def test_guardrail_default_deny():
    # If a guard component crashes, it should default to deny (allowed=False)
    broken = BrokenGuard()
    
    # Test Harness (check_tool_boundary)
    mgr1 = ToolGuardrailManager(harness=broken)
    dec1 = mgr1.check_before("run_bash", {})
    assert dec1.allowed is False
    assert "harness" in dec1.source
    
    # Test PlanGuard (check_tool_plan)
    mgr2 = ToolGuardrailManager(plan_guard=broken)
    dec2 = mgr2.check_before("run_bash", {})
    assert dec2.allowed is False
    assert "plan_guard" in dec2.source
    
    # Test ToolGuardrail (before_call)
    mgr3 = ToolGuardrailManager(tool_guardrail=broken)
    dec3 = mgr3.check_before("run_bash", {})
    assert dec3.allowed is False
    assert "tool_guardrail" in dec3.source
