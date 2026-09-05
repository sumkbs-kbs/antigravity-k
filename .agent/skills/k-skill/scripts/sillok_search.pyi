import argparse
from typing import TypedDict

class SearchCategory:
    label: str
    count: int
    token: str

    def __init__(self, label: str, count: int, token: str) -> None: ...

class ResultTitleMetadata:
    king: str | None
    regnal_year: int | None
    gregorian_year: int | None
    article_title: str

    def __init__(
        self,
        king: str | None,
        regnal_year: int | None,
        gregorian_year: int | None,
        article_title: str,
    ) -> None: ...

class SearchResult:
    article_id: str
    url: str
    title: str
    article_title: str
    summary: str
    king: str | None
    regnal_year: int | None
    gregorian_year: int | None

    def __init__(
        self,
        article_id: str,
        url: str,
        title: str,
        article_title: str,
        summary: str,
        king: str | None,
        regnal_year: int | None,
        gregorian_year: int | None,
    ) -> None: ...

class SearchReport:
    query: str
    search_type: str
    total_results: int
    type_count: int
    categories: list[SearchCategory]
    items: list[SearchResult]

    def __init__(
        self,
        query: str,
        search_type: str,
        total_results: int,
        type_count: int,
        categories: list[SearchCategory],
        items: list[SearchResult],
    ) -> None: ...

class ArticleDetail:
    article_id: str
    url: str
    header: str
    title: str
    translated_text: str
    original_text: str
    classification: str | None

    def __init__(
        self,
        article_id: str,
        url: str,
        header: str,
        title: str,
        translated_text: str,
        original_text: str,
        classification: str | None,
    ) -> None: ...

class SerializedItem(TypedDict):
    article_id: str
    detail: dict[str, object]

class SearchPayload(TypedDict):
    query: str
    type: str
    filters: dict[str, object]
    total_results: int
    type_count: int
    returned_count: int
    categories: list[dict[str, object]]
    items: list[SerializedItem]

class Arguments(argparse.Namespace):
    query: str
    king: str | None
    year: int | None
    limit: int
    search_type: str
    timeout: int

def clean_text(value: str | None) -> str: ...
def clean_article_text(value: str | None) -> str: ...
def normalize_king_name(value: str | None) -> str | None: ...
def build_opener() -> object: ...
def build_http_client() -> object: ...
def fetch_text(
    opener: object | None,
    url: str,
    *,
    data: dict[str, str] | None = None,
    timeout: int = ...,
    referer: str | None = None,
) -> str: ...
def parse_result_title_metadata(title: str) -> ResultTitleMetadata: ...
def parse_search_results(html_text: str, *, query: str, search_type: str) -> SearchReport: ...
def filter_results(
    items: list[SearchResult],
    *,
    king: str | None = None,
    year: int | None = None,
) -> list[SearchResult]: ...
def parse_detail_page(html_text: str, *, article_id: str) -> ArticleDetail: ...
def fetch_detail_page(opener: object, *, article_id: str, timeout: int) -> ArticleDetail: ...
def search_sillok(
    query: str,
    *,
    king: str | None = None,
    year: int | None = None,
    limit: int = ...,
    search_type: str = ...,
    timeout: int = ...,
) -> SearchPayload: ...
def parse_args(argv: list[str] | None = None) -> Arguments: ...
def main(argv: list[str] | None = None) -> int: ...
