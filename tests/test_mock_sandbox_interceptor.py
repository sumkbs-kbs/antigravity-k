"""Unit tests for MockSandboxInterceptor."""

from antigravity_k.engine.mock_sandbox_interceptor import MockSandboxInterceptor


def test_mock_fixture_generation_for_requests():
    code = "import requests\ndef fetch(): return requests.get('https://api.stripe.com')\n"
    fixtures = MockSandboxInterceptor.generate_mock_fixture_for_code(code)

    assert len(fixtures) >= 1
    assert fixtures[0].target_library == "requests"
    assert "mock_requests" in fixtures[0].mock_code_snippet


def test_mock_fixture_generation_for_httpx_is_executable() -> None:
    fixtures = MockSandboxInterceptor.generate_mock_fixture_for_code(
        "import httpx\nasync def fetch(): return await httpx.AsyncClient().get('https://example.com')\n",
    )

    assert len(fixtures) == 1
    snippet = fixtures[0].mock_code_snippet
    assert fixtures[0].target_library == "httpx"
    assert "MockAsyncClient" in snippet
    assert 'monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)' in snippet
    assert "pass" not in snippet
