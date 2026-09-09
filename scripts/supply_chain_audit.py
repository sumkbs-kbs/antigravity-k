#!/usr/bin/env python3
"""supply_chain_audit — REL-03 공급망 audit gate.

pip-audit / pnpm audit 출력을 정규화하고, 예외 레지스트리(owner/근거/만료/
대체 통제 4요소)로 판정하며, license/prohibited package gate를 SBOM에 대해
실행한다. 예외가 만료됐거나 계약 요소가 빠지면 gate는 실패한다 (deny-by-default).

사용:
    uv run --no-sync python scripts/supply_chain_audit.py \\
        --exceptions .omo/audit-exceptions.json \\
        --python-sbom src/antigravity_k/release/python.cdx.json \\
        --dashboard-sbom src/antigravity_k/release/dashboard.cdx.json

    # 감사 결과를 파일로 받아 판정만 (CI에서 도구 출력 재사용)
    pip-audit --format json -o /tmp/pip-audit.json
    pnpm --dir dashboard audit --prod --json > /tmp/pnpm-audit.json
    uv run --no-sync python scripts/supply_chain_audit.py --pip-audit /tmp/pip-audit.json --pnpm-audit /tmp/pnpm-audit.json ...

종료코드: 0 = 통과, 1 = 미해결 high/critical 또는 license/prohibited 위반,
          2 = 도구/입력 오류.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antigravity_k.engine.audit_exceptions import (  # noqa: E402
    AuditException,
    AuditExceptionError,
    audit_verdict_with_exceptions,
    expired_exceptions,
    license_gate_verdict,
    load_exceptions,
)

HIGH_CRITICAL = {"high", "critical"}


def normalize_pip_audit(payload: dict[str, Any]) -> tuple[dict[str, object], ...]:
    """pip-audit JSON ({"dependencies": [{name, version, vulns: [...]}]}) 정규화."""
    findings: list[dict[str, object]] = []
    for dep in payload.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            fix = vuln.get("fix_versions") or []
            findings.append(
                {
                    "id": str(vuln.get("id", "")),
                    "package": str(dep.get("name", "")),
                    "ecosystem": "pypi",
                    "installed_version": str(dep.get("version", "")),
                    "severity": str(vuln.get("severity") or _guess_severity_from_id(str(vuln.get("id", "")))),
                    "fixed_version": str(fix[0]) if fix else None,
                },
            )
    return tuple(findings)


def normalize_pnpm_audit(payload: dict[str, Any]) -> tuple[dict[str, object], ...]:
    """pnpm audit --json ({advisories: {...}}) 정규화."""
    findings: list[dict[str, object]] = []
    advisories = payload.get("advisories", payload.get("vulnerabilities", {}))
    if isinstance(advisories, dict):
        items = advisories.values()
    elif isinstance(advisories, list):
        items = advisories
    else:
        items = []
    for adv in items:
        if not isinstance(adv, dict):
            continue
        findings.append(
            {
                "id": str(adv.get("id") or adv.get("url") or adv.get("source", "")),
                "package": str(adv.get("module_name", "")),
                "ecosystem": "npm",
                "installed_version": str(adv.get("findings", [{}])[0].get("version", adv.get("version", "")))
                if adv.get("findings")
                else str(adv.get("version", "")),
                "severity": str(adv.get("severity", "")),
            },
        )
    return tuple(findings)


def _guess_severity_from_id(vuln_id: str) -> str:
    """pip-audit이 severity를 주지 않을 때의 보수적 기본값 — high로 간주해
    미해결로 보고한다 (예외 계약을 통과해야만 silent pass 가능)."""
    if vuln_id.startswith(("GHSA-", "PYSEC-", "CVE-")):
        return "high"
    return "unknown"


def run_pip_audit() -> tuple[dict[str, object], ...] | None:
    """현재 환경(uv.lock 해석 env)에 대해 pip-audit을 실행한다."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode not in {0, 1}:  # 1 = 취약점 발견 (정상 경로)
        return None
    try:
        return normalize_pip_audit(json.loads(proc.stdout))
    except json.JSONDecodeError:
        return None


def run_pnpm_audit(dashboard_dir: Path) -> tuple[dict[str, object], ...] | None:
    try:
        proc = subprocess.run(
            ["pnpm", "audit", "--prod", "--json"],
            capture_output=True,
            text=True,
            timeout=900,
            cwd=dashboard_dir,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode not in {0, 1}:
        return None
    try:
        return normalize_pnpm_audit(json.loads(proc.stdout))
    except json.JSONDecodeError:
        return None


def load_sbom(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuditExceptionError(f"SBOM을 읽을 수 없다: {path}") from error


def _marker_platform_packages(project_root: Path) -> tuple[str, ...]:
    """provenance의 marker_platform_packages를 읽는다 (없으면 빈 튜플)."""
    return _provenance_field(project_root, "marker_platform_packages")


def _prohibited_licenses(project_root: Path) -> tuple[str, ...]:
    """provenance의 prohibited_spdx (license 정책 단일 진실원)."""
    return _provenance_field(project_root, "prohibited_spdx")


def _provenance_field(project_root: Path, field: str) -> tuple[str, ...]:
    import tomllib

    provenance = project_root / "THIRD_PARTY_PROVENANCE.toml"
    if not provenance.is_file():
        return ()
    try:
        data = tomllib.loads(provenance.read_text(encoding="utf-8"))
        value = data.get("distribution", {}).get(field, ())
        return tuple(str(item) for item in value)
    except (OSError, tomllib.TOMLDecodeError):
        return ()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REL-03 supply chain audit gate")
    parser.add_argument("--exceptions", type=Path, default=Path("config/audit-exceptions.json"))
    parser.add_argument("--pip-audit", type=Path, default=None, help="pip-audit JSON 출력 파일 (없으면 직접 실행)")
    parser.add_argument("--pnpm-audit", type=Path, default=None, help="pnpm audit JSON 출력 파일 (없으면 직접 실행)")
    parser.add_argument("--python-sbom", type=Path, default=Path("src/antigravity_k/release/python.cdx.json"))
    parser.add_argument("--dashboard-sbom", type=Path, default=Path("src/antigravity_k/release/dashboard.cdx.json"))
    parser.add_argument("--skip-audits", action="store_true", help="도구 실행 생략 — license gate만")
    parser.add_argument("--report", type=Path, default=None, help="판정 JSON 리포트 저장 경로")
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parent.parent

    # ── 1. 예외 레지스트리 (만료/불완전 예외는 즉시 실패) ─────────────
    exceptions: tuple[AuditException, ...] = ()
    if args.exceptions.is_file():
        try:
            exceptions = load_exceptions(args.exceptions)
        except AuditExceptionError as error:
            print(f"FAIL: {error}", file=sys.stderr)
            return 2
    expired = expired_exceptions(exceptions)
    if expired:
        for item in expired:
            print(
                f"FAIL: 만료된 예외 {item.id} ({item.package}) — expired {item.expires}, "
                f"owner {item.owner}. 갱신 또는 제거 필요.",
                file=sys.stderr,
            )
        return 1

    # ── 2. 취약점 감사 ───────────────────────────────────────────
    findings: tuple[dict[str, object], ...] = ()
    if not args.skip_audits:
        pip_findings = (
            normalize_pip_audit(json.loads(args.pip_audit.read_text(encoding="utf-8")))
            if args.pip_audit
            else run_pip_audit()
        )
        pnpm_findings = (
            normalize_pnpm_audit(json.loads(args.pnpm_audit.read_text(encoding="utf-8")))
            if args.pnpm_audit
            else run_pnpm_audit(project_root / "dashboard")
        )
        if pip_findings is None or pnpm_findings is None:
            print("FAIL: 감사 도구 실행 실패 — 결과를 확인할 수 없다 (fail-closed)", file=sys.stderr)
            return 2
        findings = (*pip_findings, *pnpm_findings)

    verdict = audit_verdict_with_exceptions(findings=findings, exceptions=exceptions)

    # ── 3. license/prohibited gate (SBOM artifact 대상) ─────────────
    try:
        marker_packages = _marker_platform_packages(project_root)
        license_verdict = license_gate_verdict(
            load_sbom(project_root / args.python_sbom),
            load_sbom(project_root / args.dashboard_sbom),
            marker_platform_packages=marker_packages,
            prohibited_licenses=_prohibited_licenses(project_root),
        )
    except AuditExceptionError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2

    # ── 4. 리포트 ────────────────────────────────────────────────
    report = {
        "gate": "supply_chain_audit",
        "ok": bool(verdict["ok"]) and license_verdict.ok,
        "vulnerabilities": dict(verdict),
        "license_gate": license_verdict.model_dump(mode="json"),
        "exception_registry": {
            "path": str(args.exceptions),
            "tracked": args.exceptions.is_file(),
            "count": len(exceptions),
            "contract": "owner + justification + expires + compensating_controls (4요소 필수, 만료=실패)",
        },
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not report["ok"]:
        for vuln_id in verdict["unresolved"]:
            print(f"FAIL: 미해결 high/critical 취약점 {vuln_id}", file=sys.stderr)
        for note in license_verdict.notes:
            # marker-allowed는 승인된 정보성 기록 — 실패로 출력하지 않는다
            if "marker-allowed" in note:
                print(f"NOTE: license gate — {note}", file=sys.stderr)
            else:
                print(f"FAIL: license gate — {note}", file=sys.stderr)
        return 1

    print(
        f"OK: high/critical 미해결 0건 (excepted {len(verdict['excepted'])}, "
        f"medium/low 보고 {verdict['medium_low_count']}건), "
        f"license gate {license_verdict.checked_packages} packages 검사 통과",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
