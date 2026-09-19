from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import override
from zipfile import ZipFile


class _LocalResourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.resources: set[str] = set()

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"src", "href"} and value is not None and value.startswith("/"):
                self.resources.add(value)


def test_wheel_contains_dashboard_and_runtime_resources(tmp_path: Path) -> None:
    # Given: the project is built as the same wheel artifact installed by end users.
    uv = shutil.which("uv")
    assert uv is not None
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path), str(repository)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

    # When: the installed-package dashboard entrypoint is inspected inside the wheel.
    wheels = tuple(tmp_path.glob("*.whl"))
    assert len(wheels) == 1
    with ZipFile(wheels[0]) as wheel:
        members = frozenset(wheel.namelist())
        entrypoint = "antigravity_k/dashboard_dist/index.html"
        assert entrypoint in members
        html = wheel.read(entrypoint).decode("utf-8")

        hashed_asset_pattern = re.compile(r"^antigravity_k/dashboard_dist/assets/(.+)-[A-Za-z0-9_-]{8}\.(css|js)$")
        logical_assets = [
            f"{match.group(1)}.{match.group(2)}"
            for member in members
            if (match := hashed_asset_pattern.match(member)) is not None
        ]
        duplicate_assets = sorted(name for name, count in Counter(logical_assets).items() if count > 1)
        assert duplicate_assets == []

        source_prompts = tuple(path for path in (repository / "prompts").rglob("*") if path.is_file())
        assert source_prompts
        for source in source_prompts:
            relative_path = source.relative_to(repository / "prompts")
            packaged_path = f"antigravity_k/prompts/{relative_path.as_posix()}"
            assert packaged_path in members
            assert wheel.read(packaged_path) == source.read_bytes()

        for artifact_name in ("local-model-stable-simple.json", "local-model-frontier.json"):
            source = repository / "data" / "benchmarks" / artifact_name
            if not source.is_file():
                source = repository / "src" / "antigravity_k" / "data" / "benchmarks" / artifact_name
            assert source.is_file()
            packaged_path = f"antigravity_k/data/benchmarks/{artifact_name}"
            assert packaged_path in members
            assert wheel.read(packaged_path) == source.read_bytes()

    # Then: every local resource needed to bootstrap the dashboard ships with it.
    parser = _LocalResourceParser()
    parser.feed(html)
    local_resources = frozenset(parser.resources)
    assert local_resources
    assert {f"antigravity_k/dashboard_dist/{resource.removeprefix('/')}" for resource in local_resources} <= members
