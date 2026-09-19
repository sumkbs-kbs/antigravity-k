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

# 빈 저장소에서 **동시에** 생성을 시작하는 자식들(2026-09-17 SC-3 경합의 축소 재현).
# 시작 시각을 인자로 받아 모든 자식이 같은 순간에 `ProjectRegistry(...)` 로 들어가게 한다.
_CONSTRUCT_CHILD = """
import sys, time
from antigravity_k.engine.project_registry import ProjectRegistry

storage, start_at = sys.argv[1], float(sys.argv[2])
while time.time() < start_at:
    time.sleep(0.001)
registry = ProjectRegistry(storage_path=storage)
print("ok", len(registry.list_projects()))
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


class TestConcurrentCreation:
    """빈 저장소를 여러 프로세스가 **동시에** 열 때 잃지 않는다 (2026-09-17 SC-3 실측 결함).

    종전 구현은 최초 생성 경로만 공유 lock 밖이었고, 백업 회전의 임시 파일 이름이
    고정(`projects.json.bak.tmp`)이었다 → 둘 다 같은 이름으로 쓰고 한 쪽이 먼저 옮기면
    다른 쪽이 `RegistrySaveError: … .bak.tmp -> .bak` 로 죽었다. 하네스 worker 가 그대로
    죽었고 부모는 결과 큐에서 무한 대기했다(그래서 실행 전체가 결과 0으로 멈췄다).
    """

    def test_creation_on_empty_store_takes_the_shared_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """최초 생성이 공유 lock 아래에서 저장되는가 — 이게 이 결함의 뿌리다."""
        from antigravity_k.engine import project_registry as pr

        acquired: list[str] = []
        real_lock = pr._RegistryFileLock

        class _SpyLock:
            def __init__(self, path: Path) -> None:
                self._inner = real_lock(path)

            def __enter__(self) -> object:
                acquired.append(str(self._inner))
                return self._inner.__enter__()

            def __exit__(self, *exc: object) -> object:
                return self._inner.__exit__(*exc)

        monkeypatch.setattr(pr, "_RegistryFileLock", _SpyLock)
        registry = ProjectRegistry(storage_path=tmp_path / "projects.json")

        assert registry.list_projects(), "기본 프로젝트가 없다"
        assert acquired, "최초 생성이 공유 lock 없이 저장됐다 — 동시 시작에서 서로의 파일을 깨뜨린다"

    def test_backup_temp_path_is_process_unique(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        storage = tmp_path / "projects.json"
        registry = ProjectRegistry(storage_path=storage)
        monkeypatch.setattr(os, "getpid", lambda: 11111)
        first = registry._backup_tmp_path()
        monkeypatch.setattr(os, "getpid", lambda: 22222)
        second = registry._backup_tmp_path()

        assert first != second, "백업 임시 파일 이름이 고정이면 동시 writer 가 서로의 파일을 옮겨 죽는다"
        assert first.name != storage.name + ".bak.tmp"

    def test_concurrent_creation_on_empty_store_does_not_raise(self, tmp_path: Path) -> None:
        """5개 프로세스가 같은 순간에 빈 저장소에서 생성을 시작해도 아무도 죽지 않아야 한다."""
        import time

        from tests._cli_subprocess import python_invocation

        storage = tmp_path / "projects.json"
        start_at = time.time() + 1.5
        procs = [
            subprocess.Popen(  # noqa: S603 — 시험 전용 자식 프로세스
                [*python_invocation(project=True), "-c", _CONSTRUCT_CHILD, str(storage), str(start_at)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(5)
        ]
        outcomes = [(p.wait(timeout=120), *p.communicate()) for p in procs]
        failures = [stderr[-400:] for code, _out, stderr in outcomes if code != 0]
        assert not failures, f"동시 생성에서 죽은 프로세스: {failures}"

        final = ProjectRegistry(storage_path=storage)
        assert final.list_projects(), "동시 생성 뒤 저장소가 비었다"
        assert json.loads(storage.read_text(encoding="utf-8")), "저장소가 유효한 JSON 이 아니다"


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
