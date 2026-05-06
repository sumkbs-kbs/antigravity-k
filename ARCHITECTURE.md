# Antigravity-K Architecture

## 1. Overview
Antigravity-K is a local-first, autonomous engineering agent system running primarily on Apple Silicon. The system is designed to minimize dependencies on commercial external APIs, relying on a robust, cross-validating MoE (Mixture of Experts) Swarm Architecture.

## 2. The MoE Swarm Architecture
Unlike traditional systems that assign a single model to a single role (e.g., `WORKER` = `qwen-coder`), Antigravity-K assigns **Swarm Combos** to roles. This ensures that no single model's biases or hallucinations dictate the final outcome.

### Core Swarm Combos
- **`orchestrator-swarm`** (CEO / Manager): Combines models like `gemma4` and `qwen3.6` to orchestrate tasks with a balanced, global perspective.
- **`coding-swarm`** (Worker): Employs a round-robin or fallback rotation of top coding models (`qwen2.5-coder`, `llama4`, `deepseek-r1`) to write, review, and test code. This guarantees cross-validation across different training bases.
- **`architect-swarm`** (Architect): Merges logic-heavy models (`deepseek`) with highly critical analysis models (`nemotron`) to establish flawless system structures.
- **`supreme-court`** (Arbiter): Utilizes massive 70B+ parameter models only for resolving agent deadlocks.

## 3. The 9Router Pattern (ModelManager & Router)
The `ModelRouter` dynamically loads combos from `config.yaml` and executes routing strategies:
- **Fallback**: Sequential attempts; if a model fails or OOMs, the next takes over.
- **Round-Robin**: Rotates through models across turns, driving the internal debate and multi-model consensus.
- **Load-Balance**: Selects the lightest model available depending on current RAM pressure.

## 4. Agent Capabilities & Self-Evolution
Agents within Antigravity-K possess "Tools" allowing them to perform system-level tasks:
- **Config Management**: Dynamically altering `config.yaml` to restructure swarms.
- **Wiki Exporting**: Synthesizing session learnings and saving them to the user's Obsidian Vault.
- **Self-Healing**: Scanning codebase health (e.g., namespace hygiene, fixing parser bugs) automatically.
