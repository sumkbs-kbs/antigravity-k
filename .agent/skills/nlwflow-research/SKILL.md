---
name: nlwflow-research
description: "Run NotebookLM research, structure into LLM Wiki, and store in Obsidian"
---

# NLW Flow Research Skill

This skill allows you (the agent) to proactively use the NotebookLM -> LLM Wiki -> Obsidian -> qmd pipeline whenever the user asks you to "research", "compare", or "investigate" URLs or topics deeply.

## When to use this skill
- When the user asks to "compare policies", "investigate URLs", "analyze these links", or "research this topic deeply".
- When the user specifically requests to use NotebookLM or LLM Wiki for research.
- **Do NOT** use this skill for simple factual queries or general coding tasks.

## How to use this skill

1. **Ask for Clarification (if needed):**
   If the user did not provide specific URLs, ask them which URLs or documents they want to include in the research.

2. **Execute the nlwflow note-wiki command:**
   Use the `run_command` tool to execute the `nlwflow note-wiki` command, passing the user's prompt and the target URLs. Make sure to use the correct absolute paths.

   **Command Format:**
   ```powershell
   c:\Python\wiki\notebooklm-llm-wiki-flow\.venv\Scripts\nlwflow.exe note-wiki "[User Prompt]" [URL 1] [URL 2] ... --json
   ```
   *Example:*
   ```powershell
   c:\Python\wiki\notebooklm-llm-wiki-flow\.venv\Scripts\nlwflow.exe note-wiki "Anthropic과 OpenAI의 개인정보 처리 방침을 비교 분석해줘" https://policies.google.com/privacy https://openai.com/policies/privacy-policy --json
   ```

3. **Monitor the Command:**
   The `nlwflow note-wiki` command coordinates the headless NotebookLM interaction, structures the LLM Wiki response, saves it to the Obsidian workspace (`c:\Python\wiki\My_Wiki`), and indexes it via `qmd`. Wait for it to finish.

4. **Report Back to the User:**
   Do NOT attempt to read the entire output directory unless asked.
   Summarize the completion, state that the research was successfully structured via the LLM Wiki and saved into the Obsidian workspace (`c:\Python\wiki\My_Wiki`), and is now searchable using `qmd`.
