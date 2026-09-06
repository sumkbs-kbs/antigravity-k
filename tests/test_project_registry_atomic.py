"""ProjectRegistry 원자성·내구성 테스트 (DAT-03 / BR-03).

plan §DAT-03 수용기준:
1. 2 process × 100 project 추가 → 200개 모두 존재 (lock + reload-modify-save)
2. disk-full / permission / interrupted write → typed failure (조용한 성공 금지)
3. truncated primary → 마지막 정상 backup 복구 + 손상본 보존
4. registry API 응답 == 재시작 후 상태
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from antigravity_k.engine.project_registry import (
    ProjectRegistry,
    RegistrySaveError,
)

_CHILD_SCRIPT = """
import sys
from antigravity_k.engine.project_registry import ProjectRegistry

registry = ProjectRegistry(storage_path=sys.argv[1])
tag = sys.argv[2]
for i in range(100):
    registry.add_project(name=f"{tag}-{i}", path=f"/tmp/ws-{tag}-{i}")
print("done", tag)
"""


def _spawn_writer(storage: Path, tag: str) -> None:
    from tests._cli_subprocess import python_invocation

    result = subprocess.run(
        [*python_invocation(project=True), "-c", _CHILD_SCRIPT, str(storage), tag],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"writer {tag} failed: {result.stderr[-500:]}"


class TestMultiProcessDurability:
    def test_two_processes_200_projects_survive(self, tmp_path: Path) -> None:
        """BR-03: 두 프로세스가 각 100개씩 추가 → 200개 전부 존재해야 한다."""
        storage = tmp_path / "projects.json"
        _spawn_writer(storage, "alpha")
        _spawn_writer(storage, "beta")

        registry = ProjectRegistry(storage_path=storage)
        names = [p["name"] for p in registry.list_projects()]
        alpha = [n for n in names if n.startswith("alpha-")]
        beta = [n for n in names if n.startswith("beta-")]
        assert len(alpha) == 100, f"alpha 손실: {len(alpha)}/100"
        assert len(beta) == 100, f"beta 손실: {len(beta)}/100 (last-writer-wins 잃어버림)"


class TestTypedSaveFailures:
    def test_disk_full_raises_typed_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """ENOSPC: 저장 실패는 typed error여야 한다 — 조용한 성공 금지."""
        storage = tmp_path / "projects.json"
        registry = ProjectRegistry(storage_path=storage)

        real_replace = os.replace

        def enospc_replace(src: object, dst: object) -> None:
            raise OSError(28, "No space left on device")

        monkeypatch.setattr("antigravity_k.engine.project_registry.os.replace", enospc_replace)
        with pytest.raises(RegistrySaveError):
            registry.add_project(name="x", path="/tmp/ws-x")
        _ = real_replace

    def test_permission_error_raises_typed_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins

        storage = tmp_path / "projects.json"
        registry = ProjectRegistry(storage_path=storage)

        def perm_open(*args: object, **kwargs: object) -> object:
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(builtins, "open", perm_open)
        with pytest.raises(RegistrySaveError):
            registry.add_project(name="y", path="/tmp/ws-y")


class TestCorruptionRecovery:
    def test_truncated_primary_recovers_from_backup_and_preserves_corrupt(self, tmp_path: Path) -> None:
        """truncated primary → backup에서 복구, 손상본은 .corrupt-* 로 보존."""
        storage = tmp_path / "projects.json"
        backup = tmp_path / "projects.json.bak"

        # 1) 정상 상태에서 2개 저장 (backup이 생기는지도 함께 검증)
        r1 = ProjectRegistry(storage_path=storage)
        r1.add_project(name="keep-me", path="/tmp/ws-keep")
        r1.add_project(name="keep-me-2", path="/tmp/ws-keep2")
        assert backup.exists(), "정상 save 후 backup 파일이 생성되어야 한다"
        good = json.loads(backup.read_text(encoding="utf-8"))

        # 2) primary를 truncate (interrupted write 시뮬레이션) — backup 전체 중 일부만 남김
        storage.write_text(json.dumps(good, indent=2)[:-5], encoding="utf-8")
        assert storage.read_text(encoding="utf-8")

        # 3) 새 인스턴스 = 재시작 → backup에서 복구
        r2 = ProjectRegistry(storage_path=storage)
        names = [p["name"] for p in r2.list_projects()]
        assert "keep-me" in names, "backup에서 keep-me 복구 실패"
        # 참고: .bak은 '직전 정상 상태'이므로 마지막 저장(keep-me-2)은 손실될 수 있다 —
        # 단일 backup 회전의 명시적 내구성 계약.

        # 4) 손상본 보존
        corrupts = list(tmp_path.glob("projects.json.corrupt-*"))
        assert corrupts, "손상된 primary가 보존되지 않았다"
        assert any(c.read_text(encoding="utf-8").strip() for c in corrupts)

    def test_corrupt_without_backup_starts_clean(self, tmp_path: Path) -> None:
        storage = tmp_path / "projects.json"
        storage.write_text("{not-json", encoding="utf-8")
        registry = ProjectRegistry(storage_path=storage)
        assert len(registry.list_projects()) >= 1  # default project로 부트스트랩


class TestRestartConsistency:
    def test_api_response_matches_post_restart_state(self, tmp_path: Path) -> None:
        """수용기준 4: add 반환값 == 재시작(새 인스턴스) 후 상태."""
        storage = tmp_path / "projects.json"
        r1 = ProjectRegistry(storage_path=storage)
        rec = r1.add_project(name="persist", path="/tmp/ws-persist", tasks=["t1"])

        r2 = ProjectRegistry(storage_path=storage)
        loaded = r2.get_project(rec.id)
        assert loaded is not None
        assert loaded.name == "persist"
        assert loaded.path == "/tmp/ws-persist"
        assert loaded.tasks == ["t1"]
        assert any(p.is_active for p in ProjectRegistry(storage_path=storage)._projects.values())
