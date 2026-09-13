"""CR-14 F-03 — release 라이선스 판독의 결정성 계약.

F-03 의 등록 서술은 "release 문서의 파이썬 라이선스가 `importlib.metadata` 로 실행
환경에서 읽혀 환경에 따라 달라진다"였다. 실측으로 원인은 두 갈래로 분해됐다.

1. **판독 실패(환경과 무관하게 틀린다)** — `THIRD_PARTY_NOTICES.txt` 의 파이썬 절만
   `License` 필드를 직접 읽었고, `python.cdx.json` 은 PEP 639 `License-Expression` →
   `License` → 분류기 → 별명표 순으로 읽었다. 그래서 **같은 실행의 두 산출물이 같은
   패키지에 대해 다른 답**(`MIT` ↔ `license metadata unavailable`)을 했다. 실측:
   파이썬 구성요소 61개 중 42건 불일치, 그중 35건은 메타데이터가 있는데도 미상으로
   적힌 판독 실패였다(attempt-005/logs/f03-witness-before.txt).
2. **환경 의존(남는 부분)** — 현재 플랫폼에 설치되지 않는 마커 패키지는 메타데이터가
   아예 없어 두 문서 모두 미상이 된다. 그 집합이 저장소 정책과 정확히 같아야 한다.

이 파일은 (1)이 다시 생기지 않게 하고, (2)가 "선언된 집합"을 벗어나지 않게 고정한다.
검증 대상은 저장소에 커밋된 실제 산출물(`src/antigravity_k/release/*`)이다 — 두 문서가
서로 일치하는지는 실행 환경이 아니라 저장소 내용만으로 판정된다.

실행: uv run --no-sync pytest tests/test_cr14_python_license_determinism.py -q
"""

from __future__ import annotations

import json
import shutil
import tomllib
from email.message import Message
from importlib import metadata
from pathlib import Path
from typing import Any

import pytest

from antigravity_k.engine.release_sbom import (
    _python_license,
    _python_license_id,
    generate_release_documents,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RELEASE_ROOT = _REPO_ROOT / "src" / "antigravity_k" / "release"
_UNAVAILABLE = "license metadata unavailable"

# 생성기가 읽는 입력은 lockfile 두 개와 provenance 정책 하나뿐이다.
_GENERATOR_INPUTS = ("uv.lock", "dashboard/package-lock.json", "THIRD_PARTY_PROVENANCE.toml")


def _isolated_project(root: Path) -> Path:
    """생성기 입력만 복사한 임시 프로젝트 루트 (저장소 사본을 덮어쓰지 않는다)."""
    for relative in _GENERATOR_INPUTS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_REPO_ROOT / relative, target)
    return root


def _notices_python_block(text: str) -> dict[str, str]:
    lines = text.splitlines()
    start = lines.index("Python dependencies (uv.lock):") + 1
    parsed: dict[str, str] = {}
    for line in lines[start:]:
        if not line.startswith("- "):
            break
        name_version, _, license_text = line[2:].partition(" — ")
        name, _, version = name_version.rpartition(" ")
        parsed[f"{name}@{version}"] = license_text
    return parsed


def _sbom_licenses(document: dict[str, Any]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for component in document["components"]:
        ids = [item["license"]["id"] for item in component.get("licenses", [])]
        parsed[f"{component['name']}@{component['version']}"] = ids[0] if ids else _UNAVAILABLE
    return parsed


def _declared_platform_markers() -> set[str]:
    provenance = tomllib.loads((_REPO_ROOT / "THIRD_PARTY_PROVENANCE.toml").read_text(encoding="utf-8"))
    markers = provenance.get("distribution", {}).get("marker_platform_packages", ())
    return {str(item) for item in markers}


def _committed_notices() -> dict[str, str]:
    return _notices_python_block((_RELEASE_ROOT / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8"))


def _committed_sbom() -> dict[str, str]:
    return _sbom_licenses(json.loads((_RELEASE_ROOT / "python.cdx.json").read_text(encoding="utf-8")))


class _FakeMetadata:
    """`importlib.metadata` 대역 — `metadata.metadata(name)` 만 흉내 낸다.

    실제 배포 메타데이터는 `email.message.Message` 이므로 같은 타입을 쓴다
    (`get_all("Classifier")` 동작까지 동일하게 유지된다).
    """

    PackageNotFoundError = metadata.PackageNotFoundError

    def __init__(self, packages: dict[str, Message]) -> None:
        self._packages = packages

    def metadata(self, name: str) -> Message:
        try:
            return self._packages[name]
        except KeyError:
            raise metadata.PackageNotFoundError(name) from None


def _message(**fields: str) -> Message:
    message = Message()
    for key, value in fields.items():
        message[key.replace("_", "-")] = value
    return message


def _install_fake_metadata(monkeypatch: pytest.MonkeyPatch, packages: dict[str, Message]) -> None:
    monkeypatch.setattr("antigravity_k.engine.release_sbom.metadata", _FakeMetadata(packages))


class TestResolutionChain:
    """판독 체인 자체의 계약 — 고지문과 SBOM 이 **같은 함수 계열**을 쓴다."""

    def test_license_expression_wins_over_license_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PEP 639 이 있는 배포물에서 예전 판독기는 미상을 적었다(F-03 의 원형)."""
        _install_fake_metadata(
            monkeypatch,
            {"pep639-lib": _message(License="MIT License", License_Expression="Apache-2.0")},
        )
        assert _python_license_id("pep639-lib") == "Apache-2.0"
        assert _python_license("pep639-lib") == "Apache-2.0"

    def test_license_field_is_read_when_no_expression(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_metadata(monkeypatch, {"legacy-lib": _message(License="BSD 3-Clause License")})
        assert _python_license_id("legacy-lib") == "BSD-3-Clause"
        assert _python_license("legacy-lib") == "BSD-3-Clause"

    def test_classifier_is_used_as_last_resort(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_metadata(
            monkeypatch,
            {"classifier-lib": _message(Classifier="License :: OSI Approved :: BSD License")},
        )
        assert _python_license_id("classifier-lib") == "BSD-3-Clause"
        assert _python_license("classifier-lib") == "BSD-3-Clause"

    def test_unidentifiable_license_field_is_preserved_on_one_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SPDX id 로 정규화할 수 없어도 원문을 버리지 않고, 한 줄 형식만 지킨다."""
        raw = "Proprietary notice\nsee LICENSE.txt for details"
        _install_fake_metadata(monkeypatch, {"private-lib": _message(License=raw)})
        assert _python_license_id("private-lib") is None
        assert _python_license("private-lib") == "Proprietary notice see LICENSE.txt for details"

    def test_missing_metadata_reports_the_marker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_metadata(monkeypatch, {})
        assert _python_license_id("absent-lib") is None
        assert _python_license("absent-lib") == _UNAVAILABLE

    @pytest.mark.parametrize(
        "package",
        [
            {"License_Expression": "MIT"},
            {"License": "BSD 3-Clause License"},
            {"Classifier": "License :: OSI Approved :: Apache Software License"},
            {"License": "Proprietary notice\nsecond line"},
            {},
        ],
    )
    def test_notices_text_never_contradicts_the_sbom_id(
        self, monkeypatch: pytest.MonkeyPatch, package: dict[str, str]
    ) -> None:
        """불변식: `_python_license` 는 `_python_license_id` 와 모순되지 않는다.

        고지문 문장은 (a) SBOM 과 같은 SPDX id, (b) 정규화 불가한 원문, (c) 미상 표기
        중 하나여야 한다. (a) 가 아닌데도 id 가 있는 상태가 바로 F-03 이다.
        """
        _install_fake_metadata(monkeypatch, {"sample-lib": _message(**package)})
        license_id = _python_license_id("sample-lib")
        notice = _python_license("sample-lib")

        if license_id is not None:
            assert notice == license_id
        else:
            assert notice == _UNAVAILABLE or notice != ""


class TestCommittedDocumentsAgree:
    """커밋된 산출물끼리 모순되지 않는다 — 실행 환경과 무관한 판정."""

    def test_notices_and_python_sbom_agree_on_every_dependency(self) -> None:
        notices = _committed_notices()
        sbom = _committed_sbom()
        disagreements = {key: (value, sbom.get(key)) for key, value in notices.items() if sbom.get(key) != value}
        assert not disagreements, (
            "THIRD_PARTY_NOTICES.txt 와 python.cdx.json 이 같은 패키지에 다른 라이선스를 적는다 — "
            "두 문서가 모두 갱신되었는지 확인하라 "
            "(uv run --no-sync python -m antigravity_k.engine.release_sbom generate "
            "--project-root . --release-root src/antigravity_k/release)\n"
            f"{disagreements}"
        )

    def test_sbom_has_no_component_missing_from_the_notices_except_the_application(self) -> None:
        notices = _committed_notices()
        sbom = _committed_sbom()
        sbom_only = {key.partition("@")[0] for key in set(sbom) - set(notices)}
        assert sbom_only <= {"antigravity-k"}, f"고지문에 없는 파이썬 구성요소: {sorted(sbom_only)}"

    def test_unavailable_licenses_are_declared_platform_markers(self) -> None:
        """환경이 정하는 미지 집합은 저장소 정책이 선언한 마커 패키지를 넘지 않는다."""
        unresolved = {key.partition("@")[0] for key, value in _committed_notices().items() if value == _UNAVAILABLE}
        assert unresolved <= _declared_platform_markers(), (
            "정책에 선언되지 않은 미해결 라이선스가 있다 — 라이선스 판독이 열화되었거나 "
            f"플랫폼 마커 목록 갱신이 필요하다: {sorted(unresolved - _declared_platform_markers())}"
        )

    def test_every_other_dependency_has_a_resolved_license(self) -> None:
        """미상이 아닌 항목은 실제 SPDX id 또는 원문이어야 한다(빈 값 금지)."""
        for key, value in _committed_notices().items():
            assert value.strip(), f"{key} 의 라이선스가 비어 있다"
            assert value != "-", f"{key} 의 라이선스가 자리표시자다"


class TestRegenerationContract:
    """다시 생성해도 현재 산출물보다 나빠지지 않는다 (열화 감지)."""

    def test_regeneration_is_deterministic(self, tmp_path: Path) -> None:
        first = generate_release_documents(_isolated_project(tmp_path / "first"))
        second = generate_release_documents(_isolated_project(tmp_path / "second"))
        assert first.notices.read_bytes() == second.notices.read_bytes()
        assert first.python_sbom.read_bytes() == second.python_sbom.read_bytes()

    def test_regeneration_does_not_introduce_new_unknown_licenses(self, tmp_path: Path) -> None:
        """생성 환경이 잠금 환경보다 부실하면 문서가 조용히 열화된다 — 그때 실패한다.

        F-03 의 남은 환경 의존은 여기서 잡힌다: 표준 잠금 환경(`uv run --no-sync`)에서는
        미해결 집합이 정책 마커와 같고, 부실한 환경에서는 그보다 커져 이 단언이 깨진다.
        """
        generated = generate_release_documents(_isolated_project(tmp_path / "project"))
        produced = _notices_python_block(generated.notices.read_text(encoding="utf-8"))
        committed = _committed_notices()

        produced_unresolved = {key.partition("@")[0] for key, value in produced.items() if value == _UNAVAILABLE}
        assert produced_unresolved <= _declared_platform_markers(), (
            f"생성 환경에서 라이선스를 못 읽은 패키지: {sorted(produced_unresolved - _declared_platform_markers())} — "
            "잠금 환경(uv run --no-sync)에서 생성하라"
        )

        regressions = {
            key: (committed.get(key), produced.get(key))
            for key in committed
            if committed.get(key) != _UNAVAILABLE and produced.get(key) == _UNAVAILABLE
        }
        assert not regressions, f"재생성이 커밋된 라이선스를 미상으로 되돌렸다: {regressions}"

    def test_regenerated_and_committed_licenses_agree_where_both_resolve(self, tmp_path: Path) -> None:
        generated = generate_release_documents(_isolated_project(tmp_path / "project"))
        produced = _notices_python_block(generated.notices.read_text(encoding="utf-8"))
        committed = _committed_notices()

        drift = {
            key: (committed.get(key), produced.get(key))
            for key in committed
            if committed.get(key) != _UNAVAILABLE
            and produced.get(key) != _UNAVAILABLE
            and committed.get(key) != produced.get(key)
        }
        assert not drift, f"저장소 사본이 lockfile과 어긋난다 — 재생성 필요: {drift}"
