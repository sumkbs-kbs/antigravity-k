from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from antigravity_k.engine.meta_architect import ArchitectureProposal, MetaArchitect
from antigravity_k.engine.rsi_sandbox import RSISandbox


class FaultyArchitect(MetaArchitect):
    def _generate_with_self_reward(
        self,
        filename: str,
        original_code: str,
        proposal: ArchitectureProposal,
    ) -> str:
        return "def broken(:\n"


def run(argv: list[str], cwd: Path) -> None:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr)


temp_root = Path(tempfile.mkdtemp(prefix="ssak-rp04-manual-source-"))
try:
    repo = temp_root / "repo"
    engine = repo / "src" / "antigravity_k" / "engine"
    engine.mkdir(parents=True)
    owned = engine / "owned.py"
    owned.write_text("value = 'committed'\n", encoding="utf-8")
    dirty = repo / "B.py"
    dirty.write_text("value = 'committed'\n", encoding="utf-8")
    run(["git", "init", "-q"], repo)
    run(["git", "config", "user.email", "rp04@example.test"], repo)
    run(["git", "config", "user.name", "RP04"], repo)
    run(["git", "add", "."], repo)
    run(["git", "commit", "-q", "-m", "baseline"], repo)
    dirty.write_text("value = 'user-dirty'\n", encoding="utf-8")
    untracked = repo / "C.py"
    untracked.write_text("value = 'untracked'\n", encoding="utf-8")
    original_cwd = os.getcwd()
    os.chdir(repo)
    try:
        architect = FaultyArchitect(project_root=str(repo))
        proposal = ArchitectureProposal("manual", "manual", ["owned.py"], "manual", "manual")
        execute_result = architect.execute_proposal(proposal)
    finally:
        os.chdir(original_cwd)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=False
    ).stdout.splitlines()
    observed = {
        "source_rsi_sandbox": RSISandbox.__module__,
        "execute_proposal": execute_result,
        "owned_restored": owned.read_text(encoding="utf-8") == "value = 'committed'\n",
        "dirty_preserved": dirty.read_text(encoding="utf-8") == "value = 'user-dirty'\n",
        "untracked_preserved": untracked.read_text(encoding="utf-8") == "value = 'untracked'\n",
        "git_status_has_dirty_B": " M B.py" in status,
        "git_status_has_untracked_C": "?? C.py" in status,
    }
finally:
    shutil.rmtree(temp_root)

observed["temp_repo_removed"] = not temp_root.exists()
print(json.dumps(observed, sort_keys=True))
if not (
    observed["execute_proposal"] is False
    and all(value for key, value in observed.items() if key not in {"execute_proposal", "source_rsi_sandbox"})
):
    raise SystemExit(1)
