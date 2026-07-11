from antigravity_k.engine.agentic_tech_radar import AgenticTechRadar
from antigravity_k.engine.slash_commands import SlashCommandRegistry


def test_agentic_radar_prioritizes_durable_mcp_and_code_actions():
    radar = AgenticTechRadar(last_reviewed="2026-05-07")
    report = radar.evaluate("GitHub와 Hugging Face 최신 에이전틱 기술을 반영해줘")

    capabilities = {signal.capability for signal in report.signals}

    assert "Durable state graph execution" in capabilities
    assert "MCP-native tool ecosystem" in capabilities
    assert "Code-action agents with sandboxed execution" in capabilities
    assert report.high_priority_count >= 3
    assert any("Persist StateContext checkpoints" in item for item in report.transfer_plan)


def test_agentic_radar_markdown_contains_sources_and_guardrails():
    radar = AgenticTechRadar(last_reviewed="2026-05-07")
    markdown = radar.render_markdown(radar.evaluate())

    assert "# Agentic Upgrade Radar" in markdown
    assert "LangGraph" in markdown
    assert "Hugging Face smolagents" in markdown
    assert "OpenAI Agents SDK" in markdown
    assert "https://github.com/langchain-ai/langgraph" in markdown
    assert "Do not run code-action snippets outside the project sandbox." in markdown


def test_agentic_slash_command_and_completion():
    registry = SlashCommandRegistry()

    assert registry.is_command("/agentic")
    assert "/agentic" in registry.get_completions("/ag")

    result = registry.execute("/agentic 최신 agentic framework 비교")

    assert "Agentic Upgrade Radar" in result
    assert "Upgrade Decision Matrix" in result
    assert "MCP-native tool ecosystem" in result
