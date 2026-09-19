"""Unit tests for StaticTypeSecurityGate."""

from antigravity_k.engine.static_type_security_gate import StaticTypeSecurityGate


def test_audit_clean_code():
    code = """
import os

def get_db_url():
    return os.getenv("DATABASE_URL", "sqlite:///default.db")
"""
    report = StaticTypeSecurityGate.audit_code(code, "config.py")
    assert report.passed is True


def test_audit_hardcoded_secret():
    code = """
API_KEY = "sk-live-123456789012345678"
"""
    report = StaticTypeSecurityGate.audit_code(code, "auth.py")
    assert report.passed is False
    assert any(i.category == "HardcodedSecret" for i in report.issues)


def test_audit_dangerous_eval():
    code = """
def run_dynamic(expr):
    return eval(expr)
"""
    report = StaticTypeSecurityGate.audit_code(code, "dynamic.py")
    assert report.passed is False
    assert any(i.category == "ArbitraryCodeExecution" for i in report.issues)
    feedback = report.format_for_model()
    assert "Security & Type Audit Failures" in feedback


def test_audit_os_system_call():
    report = StaticTypeSecurityGate.audit_code("import os\nos.system('ls')", "shell.py")

    assert report.passed is False
    assert any(issue.category == "CommandInjectionRisk" for issue in report.issues)
