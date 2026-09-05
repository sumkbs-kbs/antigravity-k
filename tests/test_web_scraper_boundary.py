from collections.abc import Callable
from typing import cast

from antigravity_k.tools.web_scraper import WebScraperTool


def _execute_scraper(tool: WebScraperTool, url: str) -> str:
    execute = cast(Callable[..., str], cast(object, getattr(tool, "execute")))
    return execute(url=url)


def test_web_scraper_rejects_private_url_without_network_access():
    result = _execute_scraper(WebScraperTool(), "http://127.0.0.1:8000/health")

    assert "차단됨" in result
