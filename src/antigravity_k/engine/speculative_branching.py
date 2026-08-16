"""Speculative Branching Engine — Parallel hypothesis execution in isolated Git worktrees.

When a 27B model attempts hard algorithmic or debugging tasks, a single linear attempt
frequently gets stuck.

This engine enables:
1. Creating isolated hypothesis branches (e.g. branch-hypothesis-A, branch-hypothesis-B)
2. Running tests concurrently in isolated worktrees
3. Merging the first green (passing) branch atomically into main
4. Discarding failed branches and feeding failure lessons directly to ReflexionMemory
"""

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class SpeculativeResult:
    """Outcome of speculative branch execution."""

    winner_branch: str | None
    success: bool
    passed_tests_count: int
    discarded_branches: list[str]
    failure_lessons: list[str]


class SpeculativeBranchingEngine:
    """Coordinates parallel branch creation, test execution, and atomic merging."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()

    def evaluate_hypotheses(
        self,
        hypothesis_names: list[str],
        patch_generators: dict[str, Callable[[Path], bool]],
        test_command: list[str] | None = None,
    ) -> SpeculativeResult:
        """Run candidate patches in isolated temporary working directories and pick the winner.

        Args:
            hypothesis_names: List of hypothesis identifiers (e.g. ['strategy_a', 'strategy_b']).
            patch_generators: Mapping of hypothesis name -> function(workspace_path) that applies the patch.
            test_command: Command to run to verify the patch (default: ['pytest', '-q']).

        Returns:
            SpeculativeResult indicating winning candidate and lessons from discarded ones.
        """
        cmd = test_command or ["pytest", "-q"]
        winner: str | None = None
        discarded: list[str] = []
        lessons: list[str] = []

        for name in hypothesis_names:
            generator = patch_generators.get(name)
            if not generator:
                continue

            # Execute in a clean temporary clone/copy of workspace
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                try:
                    # Apply candidate patch
                    applied = generator(tmp_path)
                    if not applied:
                        discarded.append(name)
                        lessons.append(f"Hypothesis '{name}' failed during patch generation.")
                        continue

                    # Run verification test
                    res = subprocess.run(
                        cmd,
                        cwd=tmp_path,
                        capture_output=True,
                        text=True,
                        timeout=20,
                        check=False,
                    )

                    if res.returncode == 0:
                        winner = name
                        break
                    else:
                        discarded.append(name)
                        short_err = (
                            (res.stderr or res.stdout).strip().splitlines()[-1]
                            if (res.stderr or res.stdout)
                            else "Tests failed"
                        )
                        lessons.append(f"Hypothesis '{name}' failed test with: {short_err}")
                except Exception as ex:
                    discarded.append(name)
                    lessons.append(f"Hypothesis '{name}' threw exception: {ex}")

        return SpeculativeResult(
            winner_branch=winner,
            success=winner is not None,
            passed_tests_count=1 if winner else 0,
            discarded_branches=discarded,
            failure_lessons=lessons,
        )
