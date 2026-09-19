from types import SimpleNamespace
from unittest import mock

import pytest

from antigravity_k.engine.agent_definition import (
    AgentContractViolation,
    AgentDefinition,
    AgentSpawnContract,
    AgentToolRegistry,
    default_agent_spawn_contract,
)
from antigravity_k.engine.engine_context import EngineContext
from antigravity_k.engine.subagent_spawner import SubagentSpawner
from antigravity_k.tools.agent_spawn import AgentSpawnTool
from antigravity_k.tools.file_tools import WriteFileTool
from antigravity_k.tools.system_tools import ReadFileTool
from antigravity_k.tools.tool_contracts import Permission
from antigravity_k.tools.tool_registry import ToolRegistry


@pytest.fixture
def agent_contract() -> AgentSpawnContract:
    return AgentSpawnContract.model_validate(
        {
            "parent": {
                "name": "ORCHESTRATOR",
                "role": "ORCHESTRATOR",
                "system_prompt": "Coordinate work.",
                "allowed_tools": ["agent_spawn"],
                "spawnable_agents": ["WORKER"],
            },
            "definitions": [
                {
                    "name": "WORKER",
                    "role": "WORKER",
                    "system_prompt": "Implement the task.",
                    "allowed_tools": ["read_file"],
                },
            ],
        },
    )


def test_agent_spawn_rejects_an_agent_outside_the_parent_contract(
    agent_contract: AgentSpawnContract,
) -> None:
    tool = AgentSpawnTool(contract=agent_contract)

    result = tool.execute(task="inspect files", agent="QA", tools=["read_file"])

    assert result == "[DENIED] Agent 'ORCHESTRATOR' cannot spawn 'QA'."


def test_agent_spawn_blocks_a_tool_outside_the_child_execution_scope(
    agent_contract: AgentSpawnContract,
) -> None:
    parent_registry = mock.MagicMock(spec=ToolRegistry)
    parent_registry.execute_with_permission.return_value = (Permission.ALLOW, "executed")
    captured_registry: list[AgentToolRegistry] = []

    class FakeOrchestrator:
        def __init__(
            self,
            model_manager,
            vault_engine,
            tool_registry: AgentToolRegistry,
        ) -> None:
            del model_manager, vault_engine
            captured_registry.append(tool_registry)

        def _get_model_for_role(self, role: str) -> str:
            return role

    tool = AgentSpawnTool(
        model_manager=mock.MagicMock(),
        tool_registry=parent_registry,
        contract=agent_contract,
    )

    with (
        mock.patch(
            "antigravity_k.api.dependencies.get_vault_engine",
            return_value=mock.MagicMock(),
        ),
        mock.patch(
            "antigravity_k.engine.orchestrator.OrchestratorAgent",
            FakeOrchestrator,
        ),
        mock.patch(
            "antigravity_k.tools.agent_spawn.start_subagent_stream",
            return_value=SimpleNamespace(chunks=iter(["done"])),
        ),
    ):
        result = tool.execute(task="inspect files", agent="WORKER", tools=["read_file"])

    permission, denial = captured_registry[0].execute_with_permission("write_file", {})

    assert result.startswith("[Sub-Agent Result]")
    assert permission is Permission.DENY
    assert "WORKER" in denial
    parent_registry.execute_with_permission.assert_not_called()


@pytest.mark.asyncio
async def test_parallel_spawner_rejects_an_agent_outside_the_parent_contract(
    agent_contract: AgentSpawnContract,
) -> None:
    spawner = SubagentSpawner(
        model_manager=mock.MagicMock(),
        tool_registry=mock.MagicMock(spec=ToolRegistry),
        contract=agent_contract,
    )

    with mock.patch(
        "antigravity_k.engine.subagent_spawner.OrchestratorAgent",
        autospec=True,
    ) as orchestrator:
        results = await spawner.spawn_parallel(
            [{"task": "inspect files", "agent": "QA", "tools": ["read_file"]}],
        )

    assert results == ["[Sub-Agent #0 Error] [DENIED] Agent 'ORCHESTRATOR' cannot spawn 'QA'."]
    orchestrator.assert_not_called()


def test_engine_context_preserves_an_empty_agent_registry_view(tmp_path) -> None:
    source = ToolRegistry(project_root=str(tmp_path))
    definition = AgentDefinition(
        name="WORKER",
        role="WORKER",
        system_prompt="Inspect only.",
        allowed_tools=frozenset(),
    )
    view = AgentToolRegistry(source, definition, ())

    context = EngineContext(
        model_manager=None,
        project_root=str(tmp_path),
        tool_registry=view,
    )

    assert context.tool_registry is view


def test_agent_registry_view_never_exposes_a_definition_denied_tool(tmp_path) -> None:
    source = ToolRegistry(project_root=str(tmp_path))
    source.install_many(ReadFileTool(), WriteFileTool())
    definition = AgentDefinition(
        name="WORKER",
        role="WORKER",
        system_prompt="Inspect only.",
        allowed_tools=frozenset({"read_file"}),
    )
    view = AgentToolRegistry(source, definition, ("read_file", "write_file"))

    names = view.get_names()

    assert names == ["read_file"]


def test_default_worker_contract_rejects_recursive_agent_spawn() -> None:
    contract = default_agent_spawn_contract()

    with pytest.raises(AgentContractViolation) as caught:
        contract.resolve("WORKER", ("agent_spawn",))

    assert str(caught.value) == "Agent 'WORKER' cannot use tool 'agent_spawn'."
