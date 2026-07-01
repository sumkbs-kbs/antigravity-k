"""Web Scraper module."""

import logging
from typing import Any

import requests

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory

logger = logging.getLogger(__name__)


class WebScraperTool(BaseTool):
    """외부 웹사이트 또는 문서를 크롤링하여 Markdown 형식으로 반환하는 도구입니다."""

    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "🕸️"
    tags = ["crawl", "scrape", "documentation", "web"]

    def __init__(self):
        """Initialize the WebScraperTool."""
        super().__init__()
        self._name = "web_scrape"
        self._description = (
            "Fetches a web page by URL and extracts its main content as Markdown. "
            "Useful for reading external documentation or articles."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL of the web page to scrape."},
            },
            "required": ["url"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        url = kwargs.get("url")
        if not url:
            return "Error: 'url' parameter is required."

        try:
            import markdownify
            from bs4 import BeautifulSoup
        except ImportError:
            return "Error: Required libraries not installed. Run 'pip install beautifulsoup4 markdownify'."

        try:
            logger.info("Scraping URL: %s", url)
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; AntigravityAgent/1.0; +https://example.com)",
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                script.decompose()

            # Try to find main content
            main_content = soup.find("main") or soup.find("article") or soup.body

            if not main_content:
                return "Error: Could not find main content on the page."

            markdown_text = markdownify.markdownify(str(main_content), heading_style="ATX")

            # Simple cleanup of excessive newlines
            import re

            cleaned_md = re.sub(r"\n{3,}", "\n\n", markdown_text).strip()

            return f"Source: {url}\n\n{cleaned_md}"

        except requests.exceptions.RequestException as e:
            return f"Error fetching URL: {str(e)}"
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Error processing content: {str(e)}"
