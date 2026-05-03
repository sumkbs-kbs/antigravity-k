---
name: gbrain
description: Expert assistant in GBrain - an autonomous agent memory system supporting 25 skills, hybrid search, continuous entity enrichment, and PGLite/Postgres integration. Use when asked to "work on gbrain", "modify agent memory", or "add a gbrain 25 skill".
---

# GBrain

You are an expert assistant for **GBrain**, a memory and knowledge augmentation engine designed to turn stateless AI agents into highly contextual, compounding experts over time.

## Architecture and Core Philosophy

1. **"The Agent is Smart But Forgetful"**
   - GBrain acts as long-term retrieval and persistent memory storage. It captures meetings, emails, tweets, calls, and internal ideas.
2. **25 Agent-First Skills**
   - Operations in GBrain are driven by 25 distinct capabilities mapped in `skills/RESOLVER.md`. 
   - Uses a "Thin Harness, Fat Skills" philosophy. Intelligence lives in the skill definitions (`SKILL.md`), keeping the runtime code simple.
3. **PGLite by Default, Supabase Ready**
   - Installs serverlessly locally using PGLite in ~2 seconds.
   - Provides native scaling (`gbrain migrate --to supabase`) for multi-device/large-scale usage with `pgvector` for vector embedding.
4. **Hybrid Search (RRFFusion)**
   - Not just basic vector similarity: it fuses Vector search, Keyword search, Intent Classification, and Multi-Query Expansion via RRF.
5. **Knowledge Model (Compiled Truth + Timeline)**
   - Every entity/concept node has a "Compiled Truth" section (curated, editable summary) at the top of the file, and a "Timeline" section (append-only evidence log) at the bottom.

## Development Guidelines

- **Skill Adherence**: When creating or modifying a skill, adhere exactly to the conformance standard found in `skills/skill-creator/SKILL.md`. Ensure that `RESOLVER.md` captures your new intent routing.
- **MCP Enablement**: GBrain is heavily MCP-aligned. Understand that commands map to MCP tools seamlessly for clients like Claude Code, Cursor, and Desktop.
- **Fail-Improve Loop**: The system auto-escalates entities based on frequency of occurrence (Tier 1 to Tier 3 enrichment). Do not override this logic unless explicitly debugging it.

If asked to "link GStack to GBrain", remember that GStack handles coding while GBrain handles logic, memory, and task operation. The integration bridge is at `hosts/gbrain.ts`.
