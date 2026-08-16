from pathlib import Path

import pytest

from antigravity_k.knowledge import wiki as wiki_module
from antigravity_k.knowledge.wiki import LLMWiki


def test_delete_vault_sources_removes_only_exact_mirrors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: exact, unrelated, and non-Vault Wiki entries with similar data.
    wiki_dir = tmp_path / "wiki_entries"
    monkeypatch.setattr(wiki_module, "WIKI_DIR", wiki_dir)
    wiki = LLMWiki(db_path=tmp_path / "wiki.db")
    selected_url = str(tmp_path / "vault" / "private.md")
    wiki.add_entry("Private", "selected secret", source="vault", source_url=selected_url)
    wiki.add_entry("Other", "other secret", source="vault", source_url=str(tmp_path / "other.md"))
    wiki.add_entry("Private", "manual content", source="manual", source_url=selected_url)

    # When: the selected Vault source mirror is deleted.
    deleted = wiki.delete_vault_sources((selected_url,))

    # Then: only the exact Vault mirror and its Markdown derivative disappear.
    entries = wiki.export_all()
    assert deleted == 1
    assert {entry["content"] for entry in entries} == {"other secret", "manual content"}
    remaining_markdown = wiki_dir / "general" / "Private.md"
    assert remaining_markdown.exists()
    assert "manual content" in remaining_markdown.read_text(encoding="utf-8")
