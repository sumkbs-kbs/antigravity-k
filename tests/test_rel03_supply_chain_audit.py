"""REL-03 — 실제 배포 의존성 보안 audit.

GA-100 plan §REL-03 수용기준:
  AC-1  exact production lock에서 high/critical 미해결이 0건이다.
  AC-2  dev dependency 결과는 별도 보고하되 숨기지 않는다.
  AC-3  license/NOTICE/prohibited package gate가 artifact에 대해 실행된다.
  AC-4  예외에 owner/근거/만료/대체 통제가 있고, 만료 시 gate가 실패한다.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from antigravity_k.engine.audit_exceptions import (
    AuditException,
    AuditExceptionError,
    audit_verdict_with_exceptions,
    expired_exceptions,
    license_gate_verdict,
    load_exceptions,
)

# ─── 예외 4요소 계약 ─────────────────────────────────────────────


def _exception(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "GHSA-1111-2222-3333",
        "package": "vulnerable-pkg",
        "ecosystem": "pypi",
        "installed_version": "1.0.0",
        "owner": "security-team",
        "justification": "transitive dep, upstream fix pending, non-network code path only",
        "expires": "2099-12-31",
        "compensating_controls": ("egress blocked for this process",),
    }
    base.update(overrides)
    return base


def test_exception_requires_all_four_elements(tmp_path: Path) -> None:
    incomplete = _exception()
    del incomplete["compensating_controls"]
    path = tmp_path / "ex.json"
    path.write_text(json.dumps({"exceptions": [incomplete]}), encoding="utf-8")
    with pytest.raises(AuditExceptionError, match="계약"):
        load_exceptions(path)


def test_expired_exception_fails_the_gate() -> None:
    """만료 시 CI가 실패한다 — deny-by-default."""
    expired = AuditException.model_validate(_exception(expires="2020-01-01"))
    findings = (
        {
            "id": "GHSA-1111-2222-3333",
            "package": "vulnerable-pkg",
            "ecosystem": "pypi",
            "installed_version": "1.0.0",
            "severity": "high",
        },
    )
    verdict = audit_verdict_with_exceptions(findings=findings, exceptions=(expired,), today=date(2099, 1, 1))
    assert verdict["ok"] is False
    assert verdict["unresolved"] == ("GHSA-1111-2222-3333",)
    assert expired_exceptions((expired,), today=date(2020, 1, 2))


def test_valid_exception_excepts_finding() -> None:
    valid = AuditException.model_validate(_exception())
    findings = (
        {
            "id": "GHSA-1111-2222-3333",
            "package": "vulnerable-pkg",
            "ecosystem": "pypi",
            "installed_version": "1.0.0",
            "severity": "critical",
        },
    )
    verdict = audit_verdict_with_exceptions(findings=findings, exceptions=(valid,), today=date(2099, 1, 1))
    assert verdict["ok"] is True
    assert verdict["excepted"] == ("GHSA-1111-2222-3333",)


def test_exception_is_exact_match_not_prefix() -> None:
    """같은 CVE라도 버전/패키지가 다르면 예외가 적용되지 않는다."""
    valid = AuditException.model_validate(_exception())
    findings = (
        {
            "id": "GHSA-1111-2222-3333",
            "package": "vulnerable-pkg",
            "ecosystem": "pypi",
            "installed_version": "2.0.0",  # 다른 버전
            "severity": "high",
        },
    )
    verdict = audit_verdict_with_exceptions(findings=findings, exceptions=(valid,), today=date(2099, 1, 1))
    assert verdict["ok"] is False


# ─── dev dependency는 숨기지 않는다 ──────────────────────────────


def test_medium_low_findings_are_reported_not_hidden() -> None:
    findings = (
        {"id": "X1", "package": "a", "ecosystem": "pypi", "installed_version": "1", "severity": "medium"},
        {"id": "X2", "package": "b", "ecosystem": "npm", "installed_version": "1", "severity": "low"},
        {"id": "X3", "package": "c", "ecosystem": "pypi", "installed_version": "1", "severity": "critical"},
    )
    verdict = audit_verdict_with_exceptions(findings=findings, exceptions=())
    assert verdict["ok"] is False  # critical은 차단
    assert verdict["medium_low_count"] == 2  # medium/low는 보고에 남는다


# ─── license/prohibited gate ────────────────────────────────────


_POLICY = frozenset(
    {
        "AGPL-3.0",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "SSPL-1.0",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
    }
)


def _sbom(components: list[dict[str, object]]) -> dict[str, object]:
    return {"bomFormat": "CycloneDX", "components": components}


def test_license_gate_passes_with_licenses_present() -> None:
    python = _sbom(
        [
            {"name": "fastapi", "version": "0.115.0", "licenses": [{"license": {"id": "MIT"}}]},
        ],
    )
    dashboard = _sbom(
        [
            {"name": "react", "version": "18.3.1", "licenses": [{"license": {"id": "MIT"}}]},
        ],
    )
    verdict = license_gate_verdict(python, dashboard, prohibited_licenses=_POLICY)
    assert verdict.ok is True
    assert verdict.checked_packages == 2


def test_license_gate_rejects_missing_license() -> None:
    python = _sbom([{"name": "mystery", "version": "1.0"}])
    dashboard = _sbom([])
    verdict = license_gate_verdict(python, dashboard, prohibited_licenses=_POLICY)
    assert verdict.ok is False
    assert verdict.unknown_license == ("pypi:mystery@1.0",)


def test_license_gate_rejects_prohibited_license() -> None:
    python = _sbom([{"name": "copyleft", "version": "2.0", "licenses": [{"license": {"id": "AGPL-3.0"}}]}])
    dashboard = _sbom([])
    verdict = license_gate_verdict(python, dashboard, prohibited_licenses=_POLICY)
    assert verdict.ok is False
    assert verdict.prohibited == ("pypi:copyleft@2.0",)


def test_license_gate_rejects_known_malicious_package() -> None:
    dashboard = _sbom([{"name": "event-stream", "version": "3.3.6", "licenses": [{"license": {"id": "MIT"}}]}])
    verdict = license_gate_verdict(_sbom([]), dashboard, prohibited_licenses=_POLICY)
    assert verdict.ok is False
    assert verdict.prohibited == ("npm:event-stream@3.3.6",)


def test_license_gate_expression_form_supported() -> None:
    dashboard = _sbom([{"name": "dual", "version": "1", "licenses": [{"expression": "MIT OR Apache-2.0"}]}])
    verdict = license_gate_verdict(_sbom([]), dashboard, prohibited_licenses=_POLICY)
    assert verdict.ok is True


# ─── 정규화 + 스크립트 계약 ──────────────────────────────────────


def test_pip_audit_normalization() -> None:
    from scripts.supply_chain_audit import normalize_pip_audit  # noqa: PLC0415

    payload = {
        "dependencies": [
            {
                "name": "starlette",
                "version": "0.39.0",
                "vulns": [{"id": "GHSA-9999", "fix_versions": ["0.40.0"]}],
            },
        ],
    }
    findings = normalize_pip_audit(payload)
    assert findings == (
        {
            "id": "GHSA-9999",
            "package": "starlette",
            "ecosystem": "pypi",
            "installed_version": "0.39.0",
            "severity": "high",  # 미제공 시 보수적으로 high
            "fixed_version": "0.40.0",
        },
    )


def test_pnpm_audit_normalization() -> None:
    from scripts.supply_chain_audit import normalize_pnpm_audit  # noqa: PLC0415

    payload = {
        "advisories": {
            "100": {
                "id": 100,
                "module_name": "minimist",
                "severity": "low",
                "findings": [{"version": "1.2.0"}],
            },
        },
    }
    findings = normalize_pnpm_audit(payload)
    assert findings[0]["package"] == "minimist"
    assert findings[0]["severity"] == "low"
    assert findings[0]["installed_version"] == "1.2.0"


def test_real_sbom_artifacts_pass_license_gate() -> None:
    """실제 release artifact(SBOM)에 gate를 실행한다 — AC-3 실측.

    provenance의 marker_platform_packages(colorama/pywin32 — win32 전용으로
    현재 플랫폼에 미설치)는 marker-allowed로 판정된다.
    """
    project_root = Path(__file__).resolve().parent.parent
    python = json.loads((project_root / "src/antigravity_k/release/python.cdx.json").read_text(encoding="utf-8"))
    dashboard = json.loads((project_root / "src/antigravity_k/release/dashboard.cdx.json").read_text(encoding="utf-8"))
    verdict = license_gate_verdict(
        python, dashboard, marker_platform_packages=("colorama", "pywin32"), prohibited_licenses=_POLICY
    )
    # 현재 lock 상태에서 gate 통과 — 실패하면 이 테스트가 그 사실을 고정한다
    assert verdict.ok is True, f"license gate 위반: {verdict.notes[:5]}"


def test_default_exception_registry_is_absent_or_valid() -> None:
    """기본 레지스트리가 존재하면 계약을 통과해야 한다 (없으면 0건으로 통과)."""
    project_root = Path(__file__).resolve().parent.parent
    registry = project_root / ".omo" / "audit-exceptions.json"
    if registry.is_file():
        exceptions = load_exceptions(registry)
        assert not expired_exceptions(exceptions), "기본 레지스트리에 만료 예외가 있다"
