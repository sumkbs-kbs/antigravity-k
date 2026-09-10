from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from antigravity_k.tools.terminal_tools import PersistentTerminalManager


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wait_and_collect(manager: PersistentTerminalManager, term_id: str) -> tuple[int, str]:
    process = manager.terminals[term_id]
    exit_code = process.wait(timeout=20)
    return exit_code, manager.get_output(term_id)


def main() -> None:
    sandbox_root = Path(tempfile.mkdtemp(prefix="ssak-rp02-manual-"))
    project_a = sandbox_root / "project-a"
    project_b = sandbox_root / "project-b"
    sentinel = sandbox_root / "external-sentinel.txt"
    try:
        project_a.mkdir()
        project_b.mkdir()
        (project_a / "space dir").mkdir()
        sentinel.write_text("OUTSIDE-SENTINEL", encoding="utf-8")
        before = _digest(sentinel)
        manager = PersistentTerminalManager()

        attack_id = manager.create_terminal(f"printf PWNED > '{sentinel}'", str(project_a))
        attack_exit, attack_output = _wait_and_collect(manager, attack_id)
        assert _digest(sentinel) == before

        rooted_id = manager.create_terminal(
            "sleep 1; printf ROOTED > 'space dir/inside file.txt'",
            str(project_a),
        )
        os.chdir(project_b)
        rooted_exit, rooted_output = _wait_and_collect(manager, rooted_id)
        in_root = project_a / "space dir" / "inside file.txt"
        assert in_root.read_text(encoding="utf-8") == "ROOTED"
        assert not (project_b / "space dir" / "inside file.txt").exists()

        print(
            json.dumps(
                {
                    "attack_exit": attack_exit,
                    "attack_output": attack_output.strip(),
                    "external_sentinel_digest_unchanged": _digest(sentinel) == before,
                    "rooted_exit": rooted_exit,
                    "rooted_output": rooted_output.strip(),
                    "request_root_pinned_after_cwd_change": in_root.read_text(encoding="utf-8") == "ROOTED",
                    "alternate_root_unchanged": not (project_b / "space dir" / "inside file.txt").exists(),
                    "terminal_registry_empty": manager.terminals == {},
                    "profile_registry_empty": manager._profiles == {},
                },
                sort_keys=True,
            )
        )
    finally:
        os.chdir(Path.cwd().anchor)
        shutil.rmtree(sandbox_root)


if __name__ == "__main__":
    main()
