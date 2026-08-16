from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from antigravity_k.engine.vault_privacy_contracts import VaultPrivacyAction, VaultPrivacyMutation

if TYPE_CHECKING:
    from antigravity_k.engine.vault import VaultEngine
    from antigravity_k.knowledge.wiki import LLMWiki


class DerivativeMetadata(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    title: str | None = None
    type: str = "vault"
    tags: list[str] = Field(default_factory=list)


def sync_vault_privacy_derivatives(
    vault: VaultEngine,
    mutation: VaultPrivacyMutation,
    replacements: Mapping[Path, str],
) -> None:
    from antigravity_k.knowledge.wiki import LLMWiki

    relative_paths = (
        mutation.paths
        if mutation.action is VaultPrivacyAction.PURGE
        else tuple(
            relative_path for relative_path in mutation.paths if vault.vault_path / relative_path in replacements
        )
    )
    source_urls = tuple(str(vault.vault_path / path) for path in relative_paths)
    wiki = LLMWiki()
    _ = wiki.delete_vault_sources(source_urls)

    if vault.sync_rag:
        for relative_path in relative_paths:
            vault.vector_store.delete_file_chunks_strict(relative_path)

    if mutation.action is VaultPrivacyAction.PURGE:
        return

    for relative_path in relative_paths:
        absolute_path = vault.vault_path / relative_path
        raw_content = replacements[absolute_path]
        raw_metadata, content = vault.parse_markdown(raw_content)
        raw_tags = raw_metadata.get("tags")
        if isinstance(raw_tags, str):
            raw_metadata["tags"] = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
        metadata = DerivativeMetadata.model_validate(raw_metadata)
        if vault.sync_rag:
            chunks = vault.chunker.chunk_document(relative_path, metadata.model_dump(), content)
            vault.vector_store.upsert_chunks(chunks)
        _add_wiki_derivative(wiki, vault.vault_path, relative_path, metadata, content)


def _add_wiki_derivative(
    wiki: LLMWiki,
    vault_path: Path,
    relative_path: str,
    metadata: DerivativeMetadata,
    content: str,
) -> None:
    path = Path(relative_path)
    parts = path.parts
    if "memory" in parts:
        category = "agent_memory"
    elif "decisions" in parts or "adr" in parts:
        category = "decision"
    else:
        category = metadata.type

    _ = wiki.add_entry(
        title=metadata.title or path.stem,
        content=content,
        category=category,
        tags=metadata.tags,
        source="vault",
        source_url=str(vault_path / relative_path),
    )
