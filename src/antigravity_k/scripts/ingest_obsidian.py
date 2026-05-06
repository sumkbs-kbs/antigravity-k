#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from antigravity_k.knowledge.wiki import LLMWiki
from antigravity_k.config import config


def main():
    obsidian_path = "/Users/mr.k/wiki"
    print(f"Starting ingestion of Obsidian Vault from: {obsidian_path}")
    print(f"Target LLMWiki DB: {config.paths.wiki_dir.parent / 'wiki.db'}")

    wiki = LLMWiki()
    count = wiki.import_obsidian_vault(obsidian_path)

    print(
        f"\n✅ Ingestion complete! Successfully ingested {count} markdown files into LLMWiki."
    )


if __name__ == "__main__":
    main()
