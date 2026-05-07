from antigravity_k.engine.harness import TestHarness as Harness


def test_harness_derives_terminal_ws_url_from_base_url():
    harness = Harness(
        base_url="http://127.0.0.1:8010",
        dashboard_url="http://127.0.0.1:5174",
    )

    assert harness.base_url == "http://127.0.0.1:8010"
    assert harness.dashboard_url == "http://127.0.0.1:5174"
    assert harness.ws_url == "ws://127.0.0.1:8010/ws/terminal"


def test_harness_reads_urls_from_environment(monkeypatch):
    monkeypatch.setenv("AGK_HARNESS_BASE_URL", "https://qa.example.test:9443")
    monkeypatch.setenv("AGK_HARNESS_DASHBOARD_URL", "http://127.0.0.1:5175")

    harness = Harness()

    assert harness.base_url == "https://qa.example.test:9443"
    assert harness.dashboard_url == "http://127.0.0.1:5175"
    assert harness.ws_url == "wss://qa.example.test:9443/ws/terminal"


def test_harness_uses_access_pin_for_protected_api_calls(monkeypatch):
    monkeypatch.setenv("AGK_HARNESS_ACCESS_PIN", "test-pin")

    harness = Harness()

    assert harness._request_headers() == {"X-Access-Pin": "test-pin"}
    assert harness._request_headers({"Content-Type": "application/json"}) == {
        "Content-Type": "application/json",
        "X-Access-Pin": "test-pin",
    }
