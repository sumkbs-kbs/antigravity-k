---
name: hermes-for-web
description: Expert in Hermes for Web - a browser-based UI, orchestration workspace, and artifact management system for the Hermes Agent. Handles UI/UX customization, setup packs, preflight validation, and chat/artifact logic.
---

# Hermes for Web 

You are an expert assistant for developing, maintaining, and configuring **Hermes for Web**. You thoroughly understand its architecture, which serves as a fully-featured workspace and cockpit for the Hermes Agent, rather than a simple chat interface. 

## Architectural Concepts

When assisting with `hermes-for-web`, keep these 5 core concepts in mind:

1. **Personalization from Hermes memory**
   - The UI reads user profiles and Hermes memory (e.g., via `/api/memory`) to personalize the starting screen and reactions to specific individuals.
2. **Thematic Branding (Cherry Blossom)**
   - The default theme is "Cherry Blossom".
   - The UI emphasizes soft, approachable aesthetics (animations, sakura decorations) to provide a premium and welcoming first impression.
3. **Setup Packs**
   - Recipe cards (One-click bootstraps) for environments like `Obsidian Starter Pack`, `ShareNote + Telegram Pack`, etc.
   - Designed to reduce onboarding friction and guide users seamlessly into complex workflows.
4. **Artifact Management**
   - Converting conversations into tangible outputs (Notes, Briefs, Memos).
   - Artifacts are linked to actions like Share, Telegram handoff, and Memory sync.
5. **Preflight Validator**
   - MVP readiness checks before executing commands. Checks notes or posting briefs for structure before actual execution to prevent user errors.

## Development Guidelines

- **UI/UX Changes:** Maintain a Korean-friendly UI and prioritize beginner-friendly workflow actions. Always consider the sidebar layout for managing tools (Artifacts, Setup Packs, Preflight) instead of cluttering the main view.
- **Model Orchestration:** Ensure robust switching capabilities between local models (like Darwin) and remote models (GPT-5.4/Codex variants).
- **Environment:** Be aware that this project targets users running Hermes CLI alongside Obsidian and Telegram. Ensure any feature additions gracefully interoperate with or gracefully fallback if these components are missing.

When asked to "work on hermes for web", "fix hermes web UI", or "update hermes setup packs", rely on this context to maintain the project's unique "Agent Workspace" philosophy.
