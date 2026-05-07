import pytest
from unittest.mock import MagicMock
from antigravity_k.agents.meta_evolution_agent import MetaEvolutionAgent, BackupManager


@pytest.fixture
def setup_test_env(tmp_path):
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # 더미 파일 생성
    src_dir = project_root / "src" / "antigravity_k"
    src_dir.mkdir(parents=True)
    test_file = src_dir / "target.py"
    test_file.write_text("print('original')")

    doc_file = project_root / "test_process.md"
    doc_file.write_text("# Test Proc")

    return project_root, test_file, doc_file


def test_backup_manager_snapshot_and_rollback(setup_test_env):
    project_root, test_file, doc_file = setup_test_env
    bm = BackupManager(str(project_root))

    # 1. Snapshot
    target_files = ["src/antigravity_k/target.py", "test_process.md"]
    bm.create_snapshot(target_files)

    assert bm.current_snapshot.exists()
    assert (bm.current_snapshot / "src" / "antigravity_k" / "target.py").exists()

    # 2. 파일 변조
    test_file.write_text("print('hacked')")
    assert test_file.read_text() == "print('hacked')"

    # 3. Rollback
    success = bm.rollback()
    assert success is True
    assert test_file.read_text() == "print('original')"


def test_meta_evolution_agent_failure_rollback(setup_test_env):
    project_root, test_file, doc_file = setup_test_env

    mock_manager = MagicMock()
    # Mocking generate to just return some dummy xml
    mock_resp = MagicMock()
    mock_resp.text = '<tool_call>{"name": "test_tool"}</tool_call>'
    mock_manager.generate.return_value = mock_resp

    mock_executor = MagicMock()

    # 에러 주입: pytest가 무조건 실패한다고 가정
    def mock_execute(name, args):
        if name == "shell_run":
            return "FAILED error trace"
        return "success"

    mock_executor.execute.side_effect = mock_execute

    agent = MetaEvolutionAgent(
        model_manager=mock_manager,
        tool_executor=mock_executor,
        project_root=str(project_root),
    )

    # 파일 변조 전 스냅샷 뜰 것
    # 실행! 실패해야 함
    list_of_yields = list(
        agent.evolve("고장내봐", target_files=["src/antigravity_k/target.py"])
    )

    full_output = "".join(list_of_yields)

    assert "테스트 실패 감지" in full_output
    assert "롤백 성공" in full_output
