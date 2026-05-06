---
id: 119
category: note
tags: []
created: 2026-05-04T09:42:52.365354
---

# README.en.md

```markdown
# Hermes for Web

[![Private Repo Ready](https://img.shields.io/badge/release-private%20repo%20ready-f4a6c1?style=for-the-badge)](https://github.com/reallygood83/hermes-for-web)
[![Default Theme](https://img.shields.io/badge/theme-cherry%20blossom-ffb7d5?style=for-the-badge)](#theme--personalization)
[![Setup Packs](https://img.shields.io/badge/workflows-setup%20packs-9ec5ff?style=for-the-badge)](#setup-packs)
[![YouTube](https://img.shields.io/badge/YouTube-배움의%20달인-ff4b5c?style=for-the-badge&logo=youtube)](https://www.youtube.com/@%EB%B0%B0%EC%9B%80%EC%9D%98%EB%8B%AC%EC%9D%B8-p5v)
[![X](https://img.shields.io/badge/X-@reallygood83-111111?style=for-the-badge&logo=x)](https://x.com/reallygood83)

Hermes for Web is a browser workbench for Hermes Agent.

If Hermes CLI is your engine room, Hermes for Web is the cockpit.
If Telegram is your walkie-talkie, Hermes for Web is your control tower.
If Obsidian is your bookshelf, Hermes for Web is the desk where you turn scattered notes into finished work.

This fork focuses on:
- Korean-first UX
- Korean as the default UI language/tone on first launch
- beginner-friendly workflow buttons
- personalized startup based on each user's Hermes memory
- local + remote model orchestration (Darwin + GPT family)
- artifact creation and management inside the UI
- setup packs for reusable workflows such as Obsidian, ShareNote, and Telegram handoff

## Landing copy

Hermes for Web is a personalized AI workspace that remembers, creates, and hands work off across surfaces.

Korean version:
Hermes for Web 은 기억하고, 만들고, 이어주는 개인화 AI 작업실입니다.

---

## What this project is trying to be

Most agent UIs are just a chat box with a model picker.
Hermes for Web is trying to be something more practical:

- a place to talk to Hermes
- a place to create artifacts
- a place to install common workflow packs
- a place to sanity-check work before running it
- a place that remembers how you work

In plain language:
this is not just “ask an AI a question.”
This is “set up an AI workspace that starts to feel like your own.”

---

## Who this is for

This project is especially useful if you are:
- a Hermes CLI user who wants a friendlier web front-end
- an Obsidian user who wants note-first workflows
- a Telegram Hermes user who wants better handoff and continuity
- a researcher / creator / solo operator who wants artifacts, memory, and setup flows in one place

---

## Core ideas

### 1. Personalization from Hermes memory

On startup, Hermes for Web reads the user's Hermes memory/profile and reflects that in the UI.

Think of it like this:
- normal chat UIs greet everyone the same way
- Hermes for Web tries to greet each user like a returning regular

Current direction:
- reads `/api/memory`
- shows a lightweight personalization card on the home screen
- uses the user's saved preferences and profile context as a first-class input

This is designed to work for any user who already has Hermes memory, not just one specific machine.

### 2. Cherry Blossom by default

This fork uses Cherry Blossom as the default theme.

Why?
Because the UI should feel calm, gentle, and memorable the moment someone opens it.
A default theme is the emotional handshake of a product.

Current theme work includes:
- Cherry Blossom (default)
- Neo Brutalism
- Gucci style
- sidebar falling petals for Cherry Blossom
- sakura image accents around header/sidebar areas

### 3. Setup Packs

Setup Packs are one-click bootstrap tasks.

They are like recipe cards for common Hermes workflows.
Instead of saying:
“go install these five things, check these three configs, and remember this prompt pattern,”
we let the UI launch a guided Hermes task.

Current packs include:
- Obsidian Starter Pack
- ShareNote + Telegram Pack
- Obsidian Power Workflow
- Memory Sync Pack
- Telegram Onboarding Pack
- last30days Pack
- AutoResearch Pack

If someone has never used Hermes before, Telegram Onboarding Pack should act like a gentle first guide:
not “here are 17 settings,” but “here is the next small step.”

### 4. Artifacts

Artifacts are lightweight outputs you create and manage from the UI.

Think of them as work-in-progress documents:
- notes
- briefs
- posting drafts
- memos
- research stubs

The UI lets users:
- create artifacts
- open them
- delete them
- trigger Share / Telegram / Memory actions from them
- optionally ask AI to help refine them

### 5. Preflight Validator

Preflight is a checklist before takeoff.

Before a user launches a note, posting, or cron workflow, the UI can do lightweight checks.
This reduces avoidable mistakes and makes the product feel more trustworthy.

---

## Feature overview

### Chat + model orchestration
- Darwin local model support
- GPT-5.4 / GPT-5.4 Mini / Codex model support
- session-scoped model switching
- provider-aware routing fixes for local/custom models

### Workspace panel
- browse session files
- preview markdown / code / images
- create files and folders
- treat artifacts as real files, not just chat output

### Artifact workflow
- artifact shelf
- add / open / delete artifacts
- artifact creation modal
- optional AI follow-up prompt after creation
- artifact-level actions:
  - Share
  - Telegram
  - Memory

### Setup Packs
- one-click workflow bootstrap prompts
- setup history cards
- rerun / status controls

### Preflight Validator
- note check
- posting check
- cron check
- lightweight status cards for workflow readiness

### UX polish
- Korean-first labels and messaging
- premium themes
- sakura accents and falling petals
- favicon
- sidebar-first tool organization

---

## Screens in one sentence each

- Main chat: where you think with Hermes
- Sidebar tools: where you manage workflows
- Workspace: where files become visible and editable
- Artifact shelf: where chat turns into reusable outputs
- Setup packs: where “how do I install this?” becomes one click
- Preflight: where “will this probably work?” gets answered early

---

## Quick start

### Prerequisite
You need a working Hermes installation first.

### Start locally

```bash
git clone https://github.com/reallygood83/hermes-for-web.git
cd hermes-for-web
./start.sh 8788
```

Then open:

```text
http://localhost:8788
```

If you already use LaunchAgent or background startup, use the port you configured there.

---

## Suggested screenshots for the repo page

If you want the GitHub page to feel more like a product page than a source dump,
start with 3–4 screenshots in this order:

1. Home
   - first-run onboarding
   - personalization card
   - Cherry Blossom default theme

2. Setup Packs
   - workflow starter cards
   - hover/expanded explanations
   - research packs like last30days and AutoResearch

3. Artifacts
   - artifact creation modal
   - AI recommendation button
   - generated artifact highlighted in the list

4. Workspace
   - file preview/editing
   - generated files as real outputs

Suggested captions live in `docs/launch-copy.md`.

---

## Installation philosophy

Hermes for Web tries to act like a good host, not a demanding appliance.

That means:
- auto-detect Hermes paths where possible
- reuse the user's existing Hermes memory and config
- avoid hardcoded personal assumptions
- make setup packs guided instead of silent

It should feel like moving into a furnished workspace,
not assembling furniture from a bag of screws.

---

## Theme & personalization

### Default theme
Cherry Blossom is the default theme in this fork.

### What personalization means here
When available, Hermes for Web reads the user's Hermes memory and user profile through the WebUI API.
That allows the home screen and future workflow surfaces to adapt to the user's saved preferences.

In practice, this means the UI can evolve from:
- generic assistant shell
into:
- a workspace that feels like it already knows your habits

---

## Setup Packs

Setup Packs are for users who do not want to memorize setup steps.

### Obsidian Starter Pack
Use this when you want Hermes to become note-friendly first.

Typical goals:
- verify vault path
- check Obsidian-related tools
- validate note-writing workflow

### ShareNote + Telegram Pack
Use this when you want:
- note creation
- ShareNote link generation
- Telegram handoff or delivery

### Obsidian Power Workflow
Use this when you want the full loop:
- note
- posting
- ShareNote
- Telegram continuation

### Memory Sync Pack
Use this when you want CLI, WebUI, and Telegram usage to feel more connected.

---

## Artifacts

Artifacts are where the UI starts to feel like a studio rather than a chat app.

### Create
Use the artifact modal to create:
- note
- posting brief
- brief
- memo
- research brief

### Refine
Check “AI 도움 프롬프트도 함께 준비” if you want Hermes to help expand the artifact right after creation.

### Manage
Artifacts can be:
- reopened
- deleted
- used as the base for Share / Telegram / Memory workflows

Artifacts are intentionally flexible.
The built-in types are examples, not a cage.
Users can now choose a custom artifact type when the default categories do not fit their work.

The quick artifact shortcut for `/posting brief` was intentionally removed from the top quick-action strip
to keep the primary surface simpler and less crowded.

---

## Preflight Validator

Preflight is your “look both ways before crossing” feature.

It currently gives lightweight checks for:
- notes
- posting workflows
- cron jobs

This is intentionally simple but useful.
Over time it can grow into:
- smarter readiness checks
- suggested fixes
- one-click repair actions

---

## Why the sidebar was redesigned

Early versions put too many cards in the main canvas.
That made the UI feel like a kitchen counter covered in every tool at once.

The redesign moves heavier workflow controls into sidebar tool panels:
- Artifacts
- Setup Packs
- Preflight

This keeps the main chat area cleaner while still keeping powerful features one click away.

---

## Social links

If you want to follow the creator/workflow context behind this fork:

- YouTube: https://www.youtube.com/@%EB%B0%B0%EC%9B%80%EC%9D%98%EB%8B%AC%EC%9D%B8-p5v
- X: https://x.com/reallygood83

These are also linked as badges at the top of this README.

---

## Private repo release notes

You mentioned this will first go to a private repository:

- target repo: `https://github.com/reallygood83/hermes-for-web`
- recommended first step: push privately, validate on a clean machine, then decide what to make public

Before sharing more broadly, test on:
- a machine with Hermes already installed
- a machine with a different memory/profile setup
- a machine using local Darwin only
- a machine using remote GPT only

Why?
Because a good fork should not secretly depend on your exact desk layout.
It should work like a borrowed notebook that still makes sense in someone else's hands.

---

## Suggested private release checklist

Before the first private push, verify:
- Darwin works from WebUI
- GPT models work from WebUI
- Cherry Blossom is default
- personalization card loads safely when memory exists
- personalization degrades gracefully when memory is empty
- Setup Packs run without breaking the session
- Artifact creation/open/delete works
- sidebar tool panels render correctly
- no personal absolute paths are exposed in README examples unless clearly labeled as examples

Additional docs:
- `README.ko.md` — Korean guide
- `docs/onboarding.md` — onboarding notes and bot naming direction
- `docs/private-beta-guide.md` — what early users should try first
- `docs/voice-troubleshooting.md` — browser/microphone troubleshooting
- `docs/promo-kit-ko.md` — Korean launch / beta / X copy set
- `docs/install-with-hermes.md` — one-prompt install guide for Hermes CLI or bot
- `docs/full-install-from-web.md` — beginner path from zero Hermes install to WebUI
- `docs/final-release-checklist.md` — final polish checklist before wider sharing

---

## Recommended next steps after private upload

1. Push to the private GitHub repo
2. Open issues for:
   - setup pack execution results
   - richer preflight fix actions
   - artifact versioning
   - onboarding screenshots / GIFs
3. Test with at least one non-you Hermes user
4. Simplify anything that still requires explanation twice

A good product feels obvious in use.
A great product feels like it was waiting for the user before they arrived.
That is the direction of this fork.

---

## License / upstream note

This repository is a derivative workflow-focused fork of Hermes WebUI.
If you publish publicly later, keep upstream credits clear and document which features are fork-specific.
```
