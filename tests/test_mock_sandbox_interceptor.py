"""Unit tests for MockSandboxInterceptor."""

from antigravity_k.engine.mock_sandbox_interceptor import MockSandboxInterceptor


def test_mock_fixture_generation_for_requests():
    code = "import requests\ndef fetch(): return requests.get('https://api.stripe.com')\n"
    fixtures = MockSandboxInterceptor.generate_mock_fixture_for_code(code)

    assert len(fixtures) >= 1
    assert fixtures[0].target_library == "requests"
    assert "mock_requests" in fixtures[0].mock_code_snippet
