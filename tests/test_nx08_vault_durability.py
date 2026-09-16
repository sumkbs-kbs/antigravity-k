"""NX-08 — vault 저장의 **원자성**과 frontmatter 구분자 경계를 계약으로 고정한다.

NX-08 은 조사 카드다. 드라이버(`docs/qa/2026-09-16-followup/nx08/repro_nx08_vault_persistence.py`)가
임시 Git repo + 실패 주입 + 실제 프로세스 종료로 측정한 결과 중 **확정된 결함 셋**을 여기서 고정한다:

  NX-08-F01  `write_note` 가 `open(path, "w")` 로 **자르고 썼다** — fsync 가 실패하거나 프로세스가
             쓰기 도중 죽으면 이전 bytes 가 파일에서 사라졌다(CONFIRMED: 이전 sha256 ≠ 이후 sha256,
             자식 프로세스 exit 9). 이제 같은 디렉터리 임시 파일 → fsync → `os.replace` 순서다.
  NX-08-F02  `---\\r\\n` 구분자를 인식하지 못해 CRLF 파일의 frontmatter 가 통째로 본문이 됐다
             (CONFIRMED: metadata {} · body == 입력 전체).
  NX-08-F03  닫는 `---` 가 파일 끝이면 `content.index("\\n", ...)` 가 `ValueError` 로 죽었다
             (CONFIRMED: `ValueError: substring not found`).

미재현으로 판정한 것(프로세스 kill 뒤 lock, redact 잠금)과 INCONCLUSIVE(NFS)는 여기서 단정하지 않는다 —
그 판정과 증거는 드라이버 출력에 있다.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# NX-10: 원자적 저장의 실패 주입 지점은 leaf 모듈(`atomic_write`)로 옮겼다
# (`vault_privacy` 가 `vault` 를 임포트하지 않아도 되게 하려는 목적 — 순환 임포트 제거).
from antigravity_k.engine import atomic_write as atomic_write_module
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.engine.vault_git import VaultCommitError

REPO_ROOT = Path(__file__).resolve().parents[1]

_ORIGINAL_NOTE = "ORIGINAL-BODY\n"


@pytest.fixture(autouse=True)
def _no_wiki_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트가 사용자 홈의 LLM Wiki 를 건드리지 않게 막는다(vault 저장만 시험한다)."""
    monkeypatch.setattr(VaultEngine, "_sync_to_wiki", lambda *args, **kwargs: None)


def _engine(tmp_path: Path, name: str = "vault") -> VaultEngine:
    return VaultEngine(str(tmp_path / name), sync_rag=False)


def _note_bytes(engine: VaultEngine, relative: str = "note.md") -> bytes:
    return (Path(engine.vault_path) / relative).read_bytes()


def _temps(engine: VaultEngine) -> list[str]:
    return sorted(p.name for p in Path(engine.vault_path).glob(".*.tmp"))


def _default_mode() -> int:
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


# --------------------------------------------------------------------------- F01 원자성


def test_fsync_failure_preserves_previous_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """fsync 실패 → 이전 bytes 가 **그대로** 남고 임시 파일도 남지 않는다."""
    engine = _engine(tmp_path)
    engine.write_note("note.md", {"title": "v1"}, _ORIGINAL_NOTE, commit_message="v1")
    before = _note_bytes(engine)

    def broken_fsync(fd: int) -> None:  # noqa: ARG001
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(atomic_write_module, "_fsync_fd", broken_fsync)
    with pytest.raises(VaultCommitError):
        engine.write_note("note.md", {"title": "v2"}, "NEW-BODY\n", commit_message="v2")

    assert _note_bytes(engine) == before, "fsync 실패가 이전 bytes 를 지웠다 — 원자적 저장이 아니다"
    assert _temps(engine) == [], "실패한 저장이 임시 파일을 남겼다"


def test_replace_failure_preserves_previous_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """교체 단계 실패도 원본을 건드리지 않는다(임시 파일만 정리)."""
    engine = _engine(tmp_path)
    engine.write_note("note.md", {"title": "v1"}, _ORIGINAL_NOTE, commit_message="v1")
    before = _note_bytes(engine)

    def broken_replace(source: Path, destination: Path) -> None:  # noqa: ARG001
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(atomic_write_module, "_replace_file", broken_replace)
    with pytest.raises(VaultCommitError):
        engine.write_note("note.md", {"title": "v2"}, "NEW-BODY\n", commit_message="v2")

    assert _note_bytes(engine) == before
    assert _temps(engine) == []


def test_successful_write_is_byte_exact_and_leaves_no_temp(tmp_path: Path) -> None:
    """성공 경로 — 내용이 정확하고 임시 파일이 남지 않는다(원자성 도입의 회귀 기준)."""
    engine = _engine(tmp_path)
    engine.write_note("note.md", {"title": "T", "tags": ["a"]}, "BODY\n", commit_message="v1")

    text = _note_bytes(engine).decode("utf-8")
    metadata, body = engine.read_note("note.md")
    assert dict(metadata) == {"title": "T", "tags": ["a"]}
    assert body == "BODY\n"
    assert text.startswith("---\n")
    assert _temps(engine) == []


def test_write_preserves_existing_permissions_and_new_files_use_umask(tmp_path: Path) -> None:
    """기존 파일의 권한은 유지되고, 새 파일은 이전과 같은 umask 기본값을 따른다."""
    engine = _engine(tmp_path)
    note = Path(engine.vault_path) / "note.md"
    engine.write_note("note.md", {"title": "T"}, "v1\n", commit_message="v1")
    os.chmod(note, 0o600)

    engine.write_note("note.md", {"title": "T"}, "v2\n", commit_message="v2")

    assert stat.S_IMODE(note.stat().st_mode) == 0o600, "저장이 권한을 넓혔다"

    engine.write_note("fresh.md", {"title": "T"}, "v1\n", commit_message="v1")
    fresh = Path(engine.vault_path) / "fresh.md"
    assert stat.S_IMODE(fresh.stat().st_mode) == _default_mode()


KILLED_CHILD = textwrap.dedent(
    """
    import os
    import sys

    sys.path.insert(0, sys.argv[2])
    from antigravity_k.engine import atomic_write, vault

    def die(fd):  # noqa: ANN001, ARG001
        os._exit(9)

    atomic_write._fsync_fd = die
    vault_module = vault
    engine = vault_module.VaultEngine(sys.argv[1], sync_rag=False)
    engine._sync_to_wiki = lambda *a, **k: None  # type: ignore[method-assign]
    engine.write_note("note.md", {"title": "v2"}, "KILLED-BODY\\n", commit_message="v2")
    print("UNREACHABLE")
    """
)


def test_killed_process_during_write_keeps_previous_note(tmp_path: Path) -> None:
    """프로세스를 **실제로 죽여서** 확인한다 — 이전 note 는 살아 있고, 다음 저장은 성공한다."""
    engine = _engine(tmp_path)
    engine.write_note("note.md", {"title": "v1"}, _ORIGINAL_NOTE, commit_message="v1")
    before = _note_bytes(engine)

    child = tmp_path / "killed_child.py"
    child.write_text(KILLED_CHILD, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, str(child), str(engine.vault_path), str(REPO_ROOT / "src")],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    assert result.returncode == 9, f"자식이 fsync 지점에서 죽지 않았다: {result.returncode} {result.stderr[-300:]}"
    assert _note_bytes(engine) == before, "쓰기 도중 죽은 프로세스가 이전 note 를 지웠다"

    engine.write_note("note.md", {"title": "v3"}, "AFTER\n", commit_message="v3")
    assert b"AFTER" in _note_bytes(engine)


def test_orphan_temp_from_killed_process_is_swept_on_next_write(tmp_path: Path) -> None:
    """죽은 프로세스가 남긴 임시 파일은 다음 저장에서 치운다(원본은 그대로)."""
    engine = _engine(tmp_path)
    engine.write_note("note.md", {"title": "v1"}, _ORIGINAL_NOTE, commit_message="v1")
    before = _note_bytes(engine)

    orphan = Path(engine.vault_path) / ".note.md.999999.deadbeef.tmp"
    orphan.write_text("partial", encoding="utf-8")
    # PID 999999 는 살아 있지 않고, 60초 이상 지난 것으로 보이게 만든다.
    old = 1_600_000_000
    os.utime(orphan, (old, old))

    engine.write_note("note.md", {"title": "v2"}, "v2\n", commit_message="v2")

    assert not orphan.exists(), "죽은 프로세스의 잔여 임시 파일을 치우지 않았다"
    assert b"v2" in _note_bytes(engine)
    assert before != _note_bytes(engine)


def test_fresh_temp_of_live_process_is_not_swept(tmp_path: Path) -> None:
    """살아 있는 프로세스(같은 PID)의 갓 만든 임시 파일은 지우지 않는다 — 진행 중인 저장 보호."""
    engine = _engine(tmp_path)
    engine.write_note("note.md", {"title": "v1"}, "v1\n", commit_message="v1")

    live = Path(engine.vault_path) / f".note.md.{os.getpid()}.cafebabe.tmp"
    live.write_text("in-flight", encoding="utf-8")

    engine.write_note("note.md", {"title": "v2"}, "v2\n", commit_message="v2")

    assert live.exists(), "진행 중일 수 있는 임시 파일을 지웠다"


def test_directory_fsync_unavailable_is_not_fatal(tmp_path: Path) -> None:
    """디렉터리 fsync 가 불가능해도 저장을 되돌리지 않는다(내용은 이미 저장됐다)."""
    engine = _engine(tmp_path)
    engine.write_note("note.md", {"title": "T"}, "BODY\n", commit_message="v1")

    # 열 수 없는 디렉터리(미존재 경로)에서 디렉터리 fsync 는 예외를 올리지 않는다.
    atomic_write_module._fsync_directory(tmp_path / "does-not-exist")  # noqa: SLF001 — 예외가 없으면 통과
    assert b"BODY" in _note_bytes(engine)


def test_scoped_restore_restores_content_without_widening_permissions(tmp_path: Path) -> None:
    """NX-08-D1: 복구는 **내용만** 되돌리고 권한은 현재 값을 유지한다(git 은 실행 비트만 안다)."""
    engine = _engine(tmp_path)
    note = Path(engine.vault_path) / "note.md"
    engine.write_note("note.md", {"title": "T", "tags": ["a"], "schema": "v1"}, "ORIGINAL\n", commit_message="v1")
    snapshot_bytes = _note_bytes(engine)
    snapshot = engine.create_snapshot("before edit")
    assert snapshot is not None

    engine.write_note("note.md", {"title": "T"}, "MUTATED\n", commit_message="v2")
    os.chmod(note, 0o600)

    assert engine.restore_snapshot(snapshot, scope=["note.md"]) is True

    assert _note_bytes(engine) == snapshot_bytes, "복구가 스냅샷 내용을 되돌리지 못했다"
    assert stat.S_IMODE(note.stat().st_mode) == 0o600, "복구가 좁혀 둔 권한을 넓혔다"
    metadata, _ = engine.read_note("note.md")
    assert dict(metadata) == {"title": "T", "tags": ["a"], "schema": "v1"}


# --------------------------------------------------------------------------- F02/F03 frontmatter


def test_crlf_frontmatter_metadata_is_parsed(tmp_path: Path) -> None:
    """CRLF 파일도 frontmatter 를 인식한다(예전에는 metadata {} · body == 전체 입력)."""
    engine = _engine(tmp_path)
    content = "---\r\ntitle: T\r\ntags:\r\n  - a\r\n---\r\nbody\r\n"

    metadata, body = engine.parse_markdown(content)

    assert dict(metadata) == {"title": "T", "tags": ["a"]}
    assert body == "body\r\n"


def test_crlf_note_read_round_trip(tmp_path: Path) -> None:
    """CRLF 로 저장된 note 파일을 read_note 가 frontmatter 와 본문으로 나눈다."""
    engine = _engine(tmp_path)
    note = Path(engine.vault_path) / "crlf.md"
    note.write_bytes(b"---\r\ntitle: CRLF\r\n---\r\n\r\nbody\r\n")

    metadata, body = engine.read_note("crlf.md")

    assert metadata.get("title") == "CRLF"
    assert "title: CRLF" not in body


def test_frontmatter_at_eof_without_trailing_newline_does_not_raise(tmp_path: Path) -> None:
    """닫는 구분자가 파일 끝이어도 예외 없이 파싱된다(예전에는 ValueError)."""
    engine = _engine(tmp_path)

    metadata, body = engine.parse_markdown("---\ntitle: T\n---")

    assert dict(metadata) == {"title": "T"}
    assert body == ""

    crlf_metadata, crlf_body = engine.parse_markdown("---\r\ntitle: T\r\n---")
    assert dict(crlf_metadata) == {"title": "T"}
    assert crlf_body == ""


def test_delimiter_inside_body_is_not_a_closing_delimiter(tmp_path: Path) -> None:
    """본문의 수평선(`---`)은 frontmatter 를 닫지 않는다 — LF/CRLF 둘 다."""
    engine = _engine(tmp_path)

    lf_metadata, lf_body = engine.parse_markdown("---\ntitle: T\n---\nbody\n---\nrule\n")
    crlf_metadata, crlf_body = engine.parse_markdown("---\r\ntitle: T\r\n---\r\nbody\r\n---\r\nrule\r\n")

    assert lf_metadata.get("title") == "T"
    assert lf_body == "body\n---\nrule\n"
    assert crlf_metadata.get("title") == "T"
    assert crlf_body == "body\r\n---\r\nrule\r\n"


def test_writer_reader_round_trip_keeps_metadata(tmp_path: Path) -> None:
    """format → parse 왕복이 metadata 를 보존한다(회귀 기준)."""
    engine = _engine(tmp_path)
    formatted = engine.format_markdown({"title": "RT", "tags": ["x"]}, "body\n---\nrule\n")

    metadata, body = engine.parse_markdown(formatted)

    assert dict(metadata) == {"title": "RT", "tags": ["x"]}
    assert body == "body\n---\nrule\n"


def test_malformed_and_non_mapping_frontmatter_do_not_leak_frontmatter(tmp_path: Path) -> None:
    """미재현 확인 — 잘못된 YAML/비매핑도 metadata {} + 본문 보존으로 닫힌다."""
    engine = _engine(tmp_path)

    bad_metadata, bad_body = engine.parse_markdown("---\ntitle: [unclosed\n---\nbody\n")
    list_metadata, list_body = engine.parse_markdown("---\n- a\n- b\n---\nbody\n")

    assert dict(bad_metadata) == {}
    assert bad_body == "body\n"
    assert dict(list_metadata) == {}
    assert list_body == "body\n"


# --------------------------------------------------------------------------- privacy 경로


def test_privacy_redact_failure_keeps_original_and_no_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """마스킹도 같은 원자성 계약을 쓴다 — 실패하면 원본이 남고 임시 파일이 남지 않는다."""
    from antigravity_k.engine.vault_privacy import apply_vault_privacy_mutation
    from antigravity_k.engine.vault_privacy_contracts import (
        VaultPrivacyAction,
        VaultPrivacyMutation,
    )

    engine = _engine(tmp_path, "privacy")
    engine.write_note("secret.md", {"title": "S"}, "token = ABCDEF123456\n", commit_message="v1")
    before = _note_bytes(engine, "secret.md")

    def broken_fsync(fd: int) -> None:  # noqa: ARG001
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(atomic_write_module, "_fsync_fd", broken_fsync)
    mutation = VaultPrivacyMutation(
        action=VaultPrivacyAction.REDACT,
        paths=("secret.md",),
        values=("ABCDEF123456",),
    )
    with pytest.raises(Exception):
        apply_vault_privacy_mutation(
            vault_path=Path(engine.vault_path),
            acquire_lock=engine._acquire_vault_lock,  # noqa: SLF001
            resolve_path=engine._safe_resolve,  # noqa: SLF001
            mutation=mutation,
            sync_derivatives=lambda *args: None,
            is_safe_restore_target=engine._is_safe_restore_target,  # noqa: SLF001
        )

    assert _note_bytes(engine, "secret.md") == before, "실패한 마스킹이 원본을 잃었다"
    assert _temps(engine) == []


def test_privacy_redact_success_replaces_secret(tmp_path: Path) -> None:
    """성공 경로 회귀 — 마스킹이 실제로 값을 지우고 frontmatter 를 보존한다."""
    from antigravity_k.engine.vault_privacy import apply_vault_privacy_mutation
    from antigravity_k.engine.vault_privacy_contracts import (
        VaultPrivacyAction,
        VaultPrivacyMutation,
    )

    engine = _engine(tmp_path, "privacy-ok")
    engine.write_note("secret.md", {"title": "S"}, "token = ABCDEF123456\n", commit_message="v1")

    result = apply_vault_privacy_mutation(
        vault_path=Path(engine.vault_path),
        acquire_lock=engine._acquire_vault_lock,  # noqa: SLF001
        resolve_path=engine._safe_resolve,  # noqa: SLF001
        mutation=VaultPrivacyMutation(
            action=VaultPrivacyAction.REDACT,
            paths=("secret.md",),
            values=("ABCDEF123456",),
        ),
        sync_derivatives=lambda *args: None,
        is_safe_restore_target=engine._is_safe_restore_target,  # noqa: SLF001
    )

    text = _note_bytes(engine, "secret.md").decode("utf-8")
    assert result.replacement_count == 1
    assert "ABCDEF123456" not in text
    metadata, _ = engine.read_note("secret.md")
    assert metadata.get("title") == "S"
