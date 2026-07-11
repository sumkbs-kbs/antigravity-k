#!/usr/bin/env python3
"""Ingest Obsidian module."""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from antigravity_k.config import config
from antigravity_k.knowledge.wiki import LLMWiki


def main():
    """Run the main program."""
    if len(sys.argv) < 2:
        print("Usage: python -m antigravity_k.scripts.ingest_obsidian <obsidian_vault_path>")
        sys.exit(1)
    obsidian_path = sys.argv[1]
    print(f"Starting ingestion of Obsidian Vault from: {obsidian_path}")
    print(f"Target LLMWiki DB: {config.paths.wiki_dir.parent / 'wiki.db'}")

    wiki = LLMWiki()
    count = wiki.import_obsidian_vault(obsidian_path)

    print(f"\n✅ Ingestion complete! Successfully ingested {count} markdown files into LLMWiki.")


if __name__ == "__main__":
    main()
