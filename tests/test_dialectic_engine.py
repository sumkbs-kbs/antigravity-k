"""Tests for DialecticEngine (dialectic_engine.py)."""

import pytest

from antigravity_k.engine.dialectic_engine import (
    AutocodingPhase,
    AutocodingState,
    Contradiction,
    DialecticalPrompt,
    DialecticEngine,
    DialecticPhase,
    DialecticResult,
    ResearchProposal,
)


class TestDialecticEngine:
    def test_create_single_shot_prompt(self):
        engine = DialecticEngine()
        prompt = engine.create_single_shot_prompt("What is AI?")
        assert "THESIS" in prompt
        assert "ANTITHESIS" in prompt
        assert "SYNTHESIS" in prompt
        assert "What is AI?" in prompt

    def test_create_single_shot_prompt_with_council(self):
        engine = DialecticEngine()
        prompt = engine.create_single_shot_prompt("Test", use_council=True)
        assert "THE LOGICIAN" in prompt
        assert "THE EMPIRICIST" in prompt
        assert "THE ETHICIST" in prompt

    def test_create_single_shot_prompt_with_search(self):
        engine = DialecticEngine()
        prompt = engine.create_single_shot_prompt("Test", use_search=True)
        assert "search tools" in prompt

    def test_create_workflow(self):
        engine = DialecticEngine()
        workflow = engine.create_workflow("What is AI?")
        assert workflow["query"] == "What is AI?"
        assert len(workflow["steps"]) == 3  # thesis, antithesis, synthesis
        assert workflow["steps"][0]["name"] == "Generate Thesis"
        assert workflow["steps"][1]["name"] == "Generate Antithesis"
        assert workflow["steps"][2]["name"] == "Generate Synthesis"

    def test_create_workflow_with_council(self):
        engine = DialecticEngine()
        workflow = engine.create_workflow("Test", use_council=True)
        # thesis + 3 council + synthesis = 5 steps
        assert len(workflow["steps"]) == 5

    def test_parse_structured_response(self):
        engine = DialecticEngine()
        text = """## THESIS
This is the thesis.

## ANTITHESIS
This is the antithesis.
CONTRADICTION: Logical flaw
EVIDENCE: Missing premise

## SYNTHESIS
This is the synthesis.
RESEARCH_PROPOSAL: Test this
TESTABLE_PREDICTION: It will work
"""
        result = engine.parse_structured_response(text, "What is AI?")
        assert result.query == "What is AI?"
        assert "This is the thesis" in result.thesis
        assert "This is the antithesis" in result.antithesis
        assert "This is the synthesis" in result.synthesis
        assert len(result.contradictions) == 1
        assert result.contradictions[0].description == "Logical flaw"
        assert len(result.research_proposals) == 1
        assert result.research_proposals[0].proposal == "Test this"

    def test_parse_empty_response(self):
        engine = DialecticEngine()
        result = engine.parse_structured_response("", "query")
        assert result.thesis == ""
        assert result.antithesis == ""
        assert result.synthesis == ""

    def test_generate_player_prompt(self):
        state = AutocodingState.create("Build a tool", max_turns=3)
        engine = DialecticEngine()
        prompt = engine.generate_player_prompt(state)
        assert "PLAYER" in prompt
        assert "Build a tool" in prompt
        assert "1/3" in prompt

    def test_generate_player_prompt_with_feedback(self):
        state = AutocodingState.create("Build")
        state = state.advance_to_coach()
        state = state.advance_turn("Fix imports", False)
        engine = DialecticEngine()
        prompt = engine.generate_player_prompt(state)
        assert "PREVIOUS COACH FEEDBACK" in prompt

    def test_generate_coach_prompt(self):
        state = AutocodingState.create("Build")
        engine = DialecticEngine()
        prompt = engine.generate_coach_prompt(state, "player output here")
        assert "COACH" in prompt
        assert "player output here" in prompt

    def test_render_markdown(self):
        result = DialecticResult(query="test", thesis="T", antithesis="A", synthesis="S")
        md = DialecticEngine.render_markdown(result)
        assert "test" in md
        assert "T" in md
        assert "A" in md
        assert "S" in md

    def test_render_markdown_with_contradictions(self):
        result = DialecticResult(query="q")
        result.contradictions.append(Contradiction(description="Issue", evidence="Proof"))
        md = DialecticEngine.render_markdown(result)
        assert "Issue" in md
        assert "Proof" in md

    def test_render_markdown_with_proposals(self):
        result = DialecticResult(query="q")
        result.research_proposals.append(ResearchProposal(proposal="Research", testable_prediction="Works"))
        md = DialecticEngine.render_markdown(result)
        assert "Research" in md

    def test_council_members_config(self):
        assert len(DialecticEngine.COUNCIL_MEMBERS) == 3
        names = [m["name"] for m in DialecticEngine.COUNCIL_MEMBERS]
        assert "The Logician" in names
        assert "The Empiricist" in names
        assert "The Ethicist" in names


class TestAutocodingState:
    def test_create(self):
        state = AutocodingState.create("Build feature", max_turns=5, session_name="Test")
        assert state.requirements == "Build feature"
        assert state.max_turns == 5
        assert state.session_name == "Test"
        assert state.phase == AutocodingPhase.PLAYER.value

    def test_advance_to_coach(self):
        state = AutocodingState.create("Build")
        coach_state = state.advance_to_coach()
        assert coach_state.phase == AutocodingPhase.COACH.value
        assert coach_state.current_turn == 0

    def test_advance_to_coach_from_wrong_phase(self):
        state = AutocodingState.create("Build")
        state = state.advance_to_coach()
        with pytest.raises(ValueError, match="Cannot advance to coach"):
            state.advance_to_coach()

    def test_advance_turn_approved(self):
        state = AutocodingState.create("Build")
        state = state.advance_to_coach()
        next_state = state.advance_turn("Good job", approved=True)
        assert next_state.phase == AutocodingPhase.APPROVED.value
        assert next_state.turns_remaining() == 4

    def test_advance_turn_timeout(self):
        state = AutocodingState.create("Build", max_turns=1)
        state = state.advance_to_coach()
        next_state = state.advance_turn("Fix it", approved=False)
        assert next_state.phase == AutocodingPhase.TIMEOUT.value

    def test_advance_turn_continues(self):
        state = AutocodingState.create("Build", max_turns=3)
        state = state.advance_to_coach()
        next_state = state.advance_turn("Fix", approved=False)
        assert next_state.phase == AutocodingPhase.PLAYER.value
        assert next_state.current_turn == 1

    def test_is_complete(self):
        state = AutocodingState.create("Build")
        assert not state.is_complete()
        state = state.advance_to_coach()
        state = state.advance_turn("ok", approved=True)
        assert state.is_complete()

    def test_summary(self):
        state = AutocodingState.create("Build", session_name="MySession", max_turns=3)
        summary = state.summary()
        assert "MySession" in summary
        assert "Turn: 1/3" in summary


class TestEnums:
    def test_dialectic_phase_values(self):
        assert DialecticPhase.THESIS.value == "thesis"
        assert DialecticPhase.ANTITHESIS.value == "antithesis"
        assert DialecticPhase.SYNTHESIS.value == "synthesis"

    def test_autocoding_phase_values(self):
        assert AutocodingPhase.PLAYER.value == "player"
        assert AutocodingPhase.COACH.value == "coach"
        assert AutocodingPhase.APPROVED.value == "approved"
        assert AutocodingPhase.TIMEOUT.value == "timeout"


class TestContradiction:
    def test_contradiction_creation(self):
        c = Contradiction(description="desc", evidence="ev", severity="high")
        assert c.description == "desc"
        assert c.evidence == "ev"
        assert c.severity == "high"

    def test_contradiction_default_severity(self):
        c = Contradiction(description="d", evidence="e")
        assert c.severity == "medium"


class TestResearchProposal:
    def test_creation(self):
        r = ResearchProposal(proposal="prop", testable_prediction="pred")
        assert r.proposal == "prop"
        assert r.testable_prediction == "pred"


class TestDialecticalPrompt:
    def test_to_dict(self):
        dp = DialecticalPrompt(phase="thesis", prompt="prompt", instructions="instr", expected_format="text")
        d = dp.to_dict()
        assert d["phase"] == "thesis"
        assert d["prompt"] == "prompt"
