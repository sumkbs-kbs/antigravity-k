from pathlib import Path
from typing import Protocol

import pytest

from antigravity_k.agents.meta_evolution_agent import BackupManager, MetaEvolutionAgent


class _ModelResponse:
    text: str

    def __init__(self, text: str) -> None:
        self.text = text


class _ModelManager(Protocol):
    def generate(self, **kwargs: object) -> _ModelResponse: ...


class _ToolExecutor:
    def execute(self, name: str, args: object) -> str:
        _ = args
        if name == "shell_run":
            return "FAILED error trace"
        return "success"


class _FakeModelManager:
    def generate(self, **kwargs: object) -> _ModelResponse:
        _ = kwargs
        return _ModelResponse('<tool_call>{"name": "test_tool"}</tool_call>')


@pytest.fixture
def setup_test_env(tmp_path: Path) -> tuple[Path, Path, Path]:
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # 더미 파일 생성
    src_dir = project_root / "src" / "antigravity_k"
    src_dir.mkdir(parents=True)
    test_file = src_dir / "target.py"
    _ = test_file.write_text("print('original')")

    doc_file = project_root / "test_process.md"
    _ = doc_file.write_text("# Test Proc")

    return project_root, test_file, doc_file


def test_backup_manager_snapshot_and_rollback(setup_test_env: tuple[Path, Path, Path]) -> None:
    project_root, test_file, _ = setup_test_env
    bm = BackupManager(str(project_root))

    # 1. Snapshot
    target_files = ["src/antigravity_k/target.py", "test_process.md"]
    _ = bm.create_snapshot(target_files)

    assert bm.current_snapshot is not None
    assert bm.current_snapshot.exists()
    assert (bm.current_snapshot / "src" / "antigravity_k" / "target.py").exists()

    # 2. 파일 변조
    _ = test_file.write_text("print('hacked')")
    assert test_file.read_text() == "print('hacked')"

    # 3. Rollback
    success = bm.rollback()
    assert success is True
    assert test_file.read_text() == "print('original')"


def test_meta_evolution_agent_failure_rollback(setup_test_env: tuple[Path, Path, Path]) -> None:
    project_root, _, _ = setup_test_env

    mock_manager: _ModelManager = _FakeModelManager()
    mock_executor = _ToolExecutor()

    agent = MetaEvolutionAgent(
        model_manager=mock_manager,
        tool_executor=mock_executor,
        project_root=str(project_root),
    )

    # 파일 변조 전 스냅샷 뜰 것
    # 실행! 실패해야 함
    list_of_yields = list(agent.evolve("고장내봐", target_files=["src/antigravity_k/target.py"]))

    full_output = "".join(list_of_yields)

    assert "테스트 실패 감지" in full_output
    assert "롤백 성공" in full_output
