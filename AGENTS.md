# Antigravity-K Agent Protocol (AGENTS.md)

Welcome, AI Agent. This document outlines the core principles, architecture, and interaction protocols for the Antigravity-K system, inspired by the Tolaria project.

## Core Principles

1. **Files-first**: All knowledge, memories, and configuration should be stored as plain text, primarily Markdown (`.md`) files.
2. **Git-first**: The system uses a local Git repository to track all changes. Do not bypass Git; rely on the `vault.py` engine or use standard Git commands when modifying knowledge base files.
3. **Types as Lenses**: Use YAML frontmatter to categorize and tag files. Don't rely on rigid folder structures for classification; use metadata tags so that the system can filter and search them effectively.

## Architecture & Structure

- `src/antigravity_k/engine/`: Core logic including the dynamic model registry (`model_manager.py`, `model_registry.py`), Git-first vault (`vault.py`), and RAG utilities.
- `dashboard/`: A modern Web UI for visualizing system states, logs, and providing a Keyboard-first command palette.
- `.agent/skills/`: A directory containing various skills and specific AI agent protocols.

## Editing the Vault

When creating or updating notes in the vault, always include YAML frontmatter.

Example:
```yaml
---
title: System Architecture Update
tags: [architecture, tolaria, git-first]
date: 2026-04-26
---
```
Use the `VaultEngine` from `src/antigravity_k/engine/vault.py` programmatically to handle auto-commits. If you are interacting via terminal, you must commit your changes with a descriptive message.

## Command Palette Integration

The dashboard features a `Cmd+K` / `Ctrl+K` command palette. Any script or agent feature you add should ideally be accessible or discoverable via the command palette's search indexing.

Follow these rules to ensure maximum compatibility and maintainability.
