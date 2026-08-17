"""Mock Sandbox Interceptor — Autonomous network mocking for sandboxed TDD.

Detects external HTTP/cloud API dependencies in code and generates automated
`unittest.mock` / `pytest_httpx` mocking fixtures so TDD tests pass 100% cleanly
without requiring live API keys or external network connections.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MockFixture:
    """A generated mock fixture for a specific third-party library."""

    target_library: str  # "requests", "httpx", "boto3", "stripe"
    mock_code_snippet: str
    fixture_decorator: str


class MockSandboxInterceptor:
    """Generates synthetic mocking fixtures for external network I/O."""

    @staticmethod
    def generate_mock_fixture_for_code(source_code: str) -> list[MockFixture]:
        """Inspect source code and return appropriate mock fixtures."""
        fixtures: list[MockFixture] = []

        # Check for HTTP clients
        if "requests." in source_code:
            fixtures.append(
                MockFixture(
                    target_library="requests",
                    mock_code_snippet="""
@pytest.fixture(autouse=True)
def mock_requests(monkeypatch):
    class MockResponse:
        status_code = 200
        def json(self): return {"status": "success", "id": "mock_123"}
        def text(self): return '{"status": "success"}'
    monkeypatch.setattr("requests.get", lambda *a, **kw: MockResponse())
    monkeypatch.setattr("requests.post", lambda *a, **kw: MockResponse())
""",
                    fixture_decorator="@pytest.fixture(autouse=True)",
                )
            )

        if "httpx." in source_code or "AsyncClient" in source_code:
            fixtures.append(
                MockFixture(
                    target_library="httpx",
                    mock_code_snippet="""
@pytest.fixture(autouse=True)
def mock_httpx(monkeypatch):
    class MockAsyncResponse:
        status_code = 200
        def json(self): return {"status": "ok"}
    # Mock AsyncClient
    pass
""",
                    fixture_decorator="@pytest.fixture(autouse=True)",
                )
            )

        return fixtures
