from antigravity_k.tools.web_scraper import WebScraperTool


def test_web_scraper_rejects_private_url_without_network_access():
    result = WebScraperTool().execute(url="http://127.0.0.1:8000/health")

    assert "차단됨" in result
