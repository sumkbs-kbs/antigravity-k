# Antigravity-K Agentic Instructions

This repository follows the **Tolaria** philosophy.
As an AI interacting with this repository, adhere to the following rules:

1. **Read `AGENTS.md`**: Treat `AGENTS.md` as the primary protocol for understanding the project structure and your operational boundaries.
2. **Markdown & YAML Frontmatter**: When managing knowledge, strictly use Markdown files. Always include YAML frontmatter at the top of the file to classify the content using tags, dates, and types.
3. **Automated Versioning (Git-first)**: Use `vault.py` located at `src/antigravity_k/engine/vault.py` whenever you need to programmatically read or write to the knowledge vault. It handles Git auto-commits behind the scenes.
4. **Security**: Ensure that no sensitive information (API keys, secrets) is written to plain text markdown files or logs. The system uses `audit_logger.py` for API requests, which masks sensitive data. Apply similar caution to vault files.
5. **No destructive actions without consent**: Do not arbitrarily rewrite Git history. Always append or commit new versions.
