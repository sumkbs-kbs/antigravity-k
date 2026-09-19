#!/usr/bin/env python3
"""보안 표면(security surface) 리포트 — 감사 카테고리별 현황 + PR 증감.

tests/test_tool_sandbox_coverage.py의 AST 스캐너와 ALLOWLIST를 **단일 진실공급원으로
직접 임포트**해 사용한다(사본 없음 → 게이트와 리포트의 드리프트 원천 차단).

출력:
  - 카테고리별 실행 지점 현황 (sandboxed / gated_fallback / fixed_argv /
    model_code_exec / internal_fixed / infra_runner / 미분류)
  - --base <ref> 지정 시: 베이스 커밋을 git archive로 익스포트해 동일 스캔 후
    카테고리 증감 + 신규/제거 실행 지점 목록 산출 (PR마다 보안 표면 변화 가시화)
  - report.md (job summary용) + report.json (아티팩트)

사용법:
    python3 scripts/security_surface_report.py
    python3 scripts/security_surface_report.py --base origin/main --out-dir .tmp/security-surface

표준 라이브러리만 사용(CI에서 의존성 설치 불필요).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Protocol, TypedDict, cast

ROOT = Path(__file__).resolve().parent.parent
TEST_MODULE = ROOT / "tests" / "test_tool_sandbox_coverage.py"

CATEGORY_ORDER = [
    "sandboxed",
    "gated_fallback",
    "fixed_argv",
    "model_code_exec",
    "internal_fixed",
    "infra_runner",
]
UNCLASSIFIED = "미분류"


class AuditRule(Protocol):
    category: str
    reason: str


class AuditModule(Protocol):
    SRC_DIR: Path
    ALLOWLIST: Mapping[str, AuditRule]

    def scan_source(self) -> dict[str, tuple[list[str], bool]]: ...


class Snapshot(TypedDict):
    sites: dict[str, tuple[list[str], bool]]
    by_cat: dict[str, list[str]]
    calls: Counter[tuple[str, str]]
    model_code: dict[str, str]


def load_audit_module(path: Path, name: str = "agk_sandbox_coverage") -> tuple[ModuleType | None, str | None]:
    """감사 테스트 모듈을 pytest 없이 임포트해 (module, error) 반환.

    주의: dataclass 처리를 위해 반드시 sys.modules에 등록한 뒤 exec 해야 한다.

    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None, f"spec 로드 실패: {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        _ = spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 — 리포트는 게이트가 아니므로 유연하게
        _ = sys.modules.pop(name, None)
        return None, f"{type(exc).__name__}: {exc}"
    return mod, None


def snapshot(mod: AuditModule) -> Snapshot:
    """스캐너+ALLOWLIST 모듈에서 카테고리별 스냅샷을 뽑는다."""
    sites = mod.scan_source()  # {rel_path: ([calls], has_shell_true)}
    by_cat: dict[str, list[str]] = defaultdict(list)
    for rel_path, (calls, _shell) in sorted(sites.items()):
        rule = mod.ALLOWLIST.get(rel_path)
        cat = rule.category if rule else UNCLASSIFIED
        by_cat[cat].append(rel_path)
    call_counter: Counter[tuple[str, str]] = Counter()
    for rel_path, (calls, _shell) in sites.items():
        for c in calls:
            call_counter[(rel_path, c)] = 1
    model_code = {k: r.reason for k, r in mod.ALLOWLIST.items() if r.category == "model_code_exec"}
    return {"sites": sites, "by_cat": dict(by_cat), "calls": call_counter, "model_code": model_code}


def scan_tree_at(ref: str | None) -> tuple[Snapshot, str | None]:
    """ref가 주어지면 git archive 익스포트 트리를, 아니면 현재 작업 트리를 스캔한다."""
    if ref is None:
        mod, err = load_audit_module(TEST_MODULE)
        if mod is None:
            raise SystemExit(f"감사 모듈 로드 실패: {err}")
        return snapshot(cast(AuditModule, cast(object, mod))), None
    tmp = tempfile.mkdtemp(prefix="agk-surface-base-")
    archive = subprocess.run(["git", "archive", "--format=tar", ref], cwd=ROOT, check=True, capture_output=True)
    tar_path = Path(tmp) / "base.tar"
    _ = tar_path.write_bytes(archive.stdout)
    _ = subprocess.run(["tar", "-xf", str(tar_path), "-C", tmp], check=True)
    base_test = Path(tmp) / "tests" / "test_tool_sandbox_coverage.py"
    mod, err = load_audit_module(base_test, name="agk_sandbox_coverage_base")
    if mod is not None and callable(getattr(mod, "scan_source", None)):
        snap = snapshot(cast(AuditModule, cast(object, mod)))
        return snap, tmp
    # 베이스에 구버전/부재 감사 모듈 → 현재 스캐너로만 사이트 수집(카테고리는 현재 기준)
    cur_mod, _ = load_audit_module(TEST_MODULE)
    assert cur_mod is not None
    current = cast(AuditModule, cast(object, cur_mod))
    old_src = current.SRC_DIR
    current.SRC_DIR = Path(tmp) / "src" / "antigravity_k"
    try:
        snap = snapshot(current)
        snap["model_code"] = {}
    finally:
        current.SRC_DIR = old_src
    return snap, tmp


def category_table(now: Snapshot, base: Snapshot | None) -> list[dict[str, int | str | None]]:
    cats: set[str] = set(now["by_cat"])
    if base:
        cats.update(base["by_cat"])
    rows: list[dict[str, int | str | None]] = []
    for cat in CATEGORY_ORDER + sorted(cats - set(CATEGORY_ORDER)):
        n_now = len(now["by_cat"].get(cat, []))
        n_base = len(base["by_cat"].get(cat, [])) if base else None
        delta = (n_now - n_base) if n_base is not None else None
        rows.append({"category": cat, "now": n_now, "base": n_base, "delta": delta})
    return rows


def site_diff(now: Snapshot, base: Snapshot) -> tuple[list[str], list[str]]:
    """실행 지점(파일×호출심볼) 다중집합 차집합 → (신규, 제거) 목록."""
    added = sorted((f"{p} :: {c}" for (p, c), n in now["calls"].items() if n > base["calls"].get((p, c), 0)))
    removed = sorted((f"{p} :: {c}" for (p, c), n in base["calls"].items() if n > now["calls"].get((p, c), 0)))
    return added, removed


def render_md(
    rows: list[dict[str, int | str | None]],
    now: Snapshot,
    added: list[str],
    removed: list[str],
    ref: str | None,
    base_commit: str | None,
    load_note: str | None,
) -> str:
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["## 🛡️ 보안 표면 리포트 (프로세스 실행 경로 감사)", ""]
    head = f"> 생성: {ts} · 기준: 현재 작업 트리"
    if ref:
        head += f" · 비교 베이스: `{ref}`" + (f" ({base_commit[:12]})" if base_commit else "")
    if load_note:
        head += f" · ⚠️ 베이스 감사 모듈: {load_note}"
    lines += [head, ""]
    header, sep = "| 카테고리 | 현재 파일 수 |", "|---|---:|"
    if ref:
        header += " 베이스 | 증감 |"
        sep += "---:|---:|"
    lines.append(header)
    lines.append(sep)
    for r in rows:
        line = f"| {r['category']} | {r['now']} |"
        if ref:
            delta_txt = "—" if r["delta"] is None else f"{r['delta']:+d}"
            line += f" {r['base'] if r['base'] is not None else '—'} | {delta_txt} |"
        lines.append(line)
    total_now = sum(len(v) for v in now["by_cat"].values())
    unclassified = now["by_cat"].get(UNCLASSIFIED, [])
    lines += [
        "",
        f"**총 실행 지점 파일**: {total_now}개 · 미분류: {len(unclassified)}개"
        + (" — 🚨 ALLOWLIST 등록 필요!" if unclassified else ""),
        "",
    ]

    if now["model_code"]:
        lines += [
            "### 🔴 model_code_exec — 샌드박스 미경유 모델 코드 실행기 (이관 과제)",
            "",
            "| 파일 | 사유 |",
            "|---|---|",
        ]
        for k in sorted(now["model_code"]):
            reason = now["model_code"][k].replace("\n", " ")
            lines.append(f"| `{k}` | {reason} |")
        lines.append("")

    if ref and (added or removed):

        def block(title: str, items: list[str]) -> None:
            nonlocal lines
            emoji = "🆕" if "신규" in title else "🗑️"
            lines += [f"### {emoji} {title}", ""]
            lines += [f"- `{i}`" for i in items] or ["- (없음)"]
            lines.append("")

        if added:
            block("실행 지점 (베이스 대비 추가)", added)
        if removed:
            block("실행 지점 (베이스 대비 제거)", removed)
    elif ref:
        lines += ["### ✅ 베이스 대비 실행 지점 변화 없음", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--base", default=None, help="비교할 베이스 ref (예: origin/main)")
    _ = parser.add_argument("--out-dir", default=".tmp/security-surface")
    args = parser.parse_args()
    base_ref = cast(str | None, args.base)
    out_dir_name = cast(str, args.out_dir)

    now_snap, _ = scan_tree_at(None)
    base_snap, tmp = (None, None)
    base_commit = None
    load_note = None
    if base_ref:
        base_snap, tmp = scan_tree_at(base_ref)
        cp = subprocess.run(["git", "rev-parse", base_ref], cwd=ROOT, capture_output=True, text=True)
        base_commit = cp.stdout.strip() if cp.returncode == 0 else None
        if not base_snap.get("model_code"):
            load_note = "구버전 — 카테고리는 현재 ALLOWLIST 기준 추정"
        # 현재 ALLOWLIST 키가 베이스 사이트에 그대로 적용된 상태라 카테고리 열은 참고용

    rows = category_table(now_snap, base_snap)
    added, removed = ([], [])
    if base_snap is not None:
        added, removed = site_diff(now_snap, base_snap)

    md = render_md(rows, now_snap, added, removed, base_ref, base_commit, load_note)
    print(md)

    out_dir = ROOT / out_dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "base_ref": base_ref,
        "base_commit": base_commit,
        "categories": rows,
        "total_files": sum(len(v) for v in now_snap["by_cat"].values()),
        "unclassified": now_snap["by_cat"].get(UNCLASSIFIED, []),
        "model_code_exec": now_snap["model_code"],
        "new_sites_vs_base": added,
        "removed_sites_vs_base": removed,
        "sites_detail": {p: {"calls": c, "shell": s} for p, (c, s) in now_snap["sites"].items()},
    }
    _ = (out_dir / "report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _ = (out_dir / "report.md").write_text(md + "\n", encoding="utf-8")
    print(f"\n아티팩트 저장: {out_dir}/report.md · report.json", file=sys.stderr)

    if tmp:
        _ = subprocess.run(["rm", "-rf", tmp], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
