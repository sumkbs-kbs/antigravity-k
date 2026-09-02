"""삭제 감사(Dead-code audit) — 머스크 알고리즘 2단계 '삭제' 지원 도구.

AST로 src/antigravity_k 전체의 임포트 그래프를 만들고,
진입점(agk CLI)에서 정적 도달 불가능한 모듈을 찾아
참조 근거(tests/scripts/dashboard/docs)와 함께 안전도 등급으로 분류한다.

동적 임포트 대비: 문자열 리터럴 안의 'antigravity_k.*' 패턴도 엣지로 취급한다.

사용법: uv run python scripts/audit_dead_code.py [--json out.json]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict, cast

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "antigravity_k"
ENTRY_POINTS = ["antigravity_k.cli"]

# 참조 근거를 수집할 디렉터리 (거대한 node_modules/.venv/.git 등은 제외)
EVIDENCE_DIRS = [
    ("tests", ROOT / "tests", {"*.py"}),
    ("scripts", ROOT / "scripts", {"*.py"}),
    ("dashboard", ROOT / "dashboard" / "src", {"*.ts", "*.tsx", "*.js"}),
    ("docs", ROOT / "docs", {"*.md"}),
]


@dataclass
class ModuleInfo:
    name: str  # dotted module name, e.g. antigravity_k.engine.tool_loop
    path: Path
    loc: int
    is_init: bool = False  # 패키지 __init__.py 여부 (상대 임포트 기준점이 다름)
    imports: set[str] = field(default_factory=set)


class CandidateRow(TypedDict):
    module: str
    loc: int
    tier: str
    refs: dict[str, int]


class AuditReport(TypedDict):
    total_modules: int
    reachable_from_entry: int
    unreachable_count: int
    unreachable_loc: int
    tiers: dict[str, int]
    candidates: list[CandidateRow]


def _findall_text(pattern: re.Pattern[str], text: str) -> list[str]:
    return cast(list[str], cast(object, pattern.findall(text)))


def discover() -> dict[str, ModuleInfo]:
    mods: dict[str, ModuleInfo] = {}
    # "antigravity_k.api.server:app" 같은 uvicorn/importlib 문자열도 잡도록 :attr 허용
    dyn_pattern = re.compile(r"[\"']((?:antigravity_k)(?:\.[A-Za-z_]\w*)+(?::[\w.]+)?)[\"']")
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(ROOT / "src")
        parts = list(rel.with_suffix("").parts)
        is_init = parts[-1] == "__init__"
        if is_init:
            parts = parts[:-1]
        name = ".".join(parts)  # rel 경로가 이미 'antigravity_k/...'로 시작함
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        tree = ast.parse(source)
        info = ModuleInfo(name=name, path=path, loc=len(source.splitlines()), is_init=is_init)
        # 문자열 리터럴 동적 임포트도 엣지로 취급 (FastAPI include_router 문자열,
        # importlib, 레지스트리 키 등 방어)
        for hit in _findall_text(dyn_pattern, source):
            info.imports.add(hit)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    info.imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    if node.module:
                        info.imports.add(node.module)
                else:
                    # relative import:
                    #  - 일반 모듈: level=1 -> 자신의 패키지 (마지막 부분 제거)
                    #  - __init__: level=1 -> 자기 자신(패키지) 그대로
                    parts_d = name.split(".")
                    drop = node.level - (1 if info.is_init else 0)
                    base = parts_d[: len(parts_d) - drop] if drop > 0 else parts_d
                    if not base:
                        continue
                    if node.module:
                        info.imports.add(".".join(base + [node.module]))
                    for alias in node.names:
                        if node.module:
                            info.imports.add(".".join(base + [node.module, alias.name]))
                        else:
                            info.imports.add(".".join(base + [alias.name]))
        mods[name] = info
    return mods


def resolve_candidates(imp: str) -> list[str]:
    """임포트 문자열을 실제 모듈 후보들로 확장."""
    # uvicorn 스타일 "module.path:attr" -> 모듈 경로만 추출
    if ":" in imp:
        imp = imp.split(":", 1)[0]
    cands = [imp]
    parts = imp.split(".")
    # 심볼 임포트 폴백: antigravity_k.pkg.mod.Symbol -> mod
    if len(parts) >= 2:
        cands.append(".".join(parts[:-1]))
    # 부모 패키지 __init__ 실행 트리거
    for i in range(1, len(parts) + 1):
        cands.append(".".join(parts[:i]))
    return cands


def dynamic_load_packages(mods: dict[str, ModuleInfo], reach: set[str]) -> set[str]:
    """도달 가능한 모듈 안의 auto_discover("패키지") 호출로 로드되는 패키지 트리 반환.

    tool_registry.auto_discover()는 pkgutil.iter_modules로 패키지 내 모든 모듈을
    런타임 임포트하므로, 정적 임포트가 없어도 살아있는 것으로 취급해야 한다.
    """
    pattern = re.compile(r"auto_discover\(\s*[\"']([\w.]+)[\"']")
    loaded: set[str] = set()
    for name in reach:
        info = mods.get(name)
        if not info:
            continue
        try:
            text = info.path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pkg in _findall_text(pattern, text):
            for mod_name in mods:
                if mod_name == pkg or mod_name.startswith(pkg + "."):
                    loaded.add(mod_name)
    return loaded


def reachable(mods: dict[str, ModuleInfo]) -> set[str]:
    seen: set[str] = set()
    stack = [e for e in ENTRY_POINTS if e in mods]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        info = mods.get(current)
        if not info:
            continue
        for imp in info.imports:
            for cand in resolve_candidates(imp):
                if cand in mods and cand not in seen:
                    stack.append(cand)
    return seen


def load_evidence() -> list[tuple[str, str]]:
    """(출처라벨, 파일내용) 목록을 한 번만 읽는다."""
    corpus: list[tuple[str, str]] = []
    for label, base, patterns in EVIDENCE_DIRS:
        if not base.exists():
            continue
        for pattern in patterns:
            for f in base.rglob(pattern):
                try:
                    corpus.append((f"{label}/{f.relative_to(base)}", f.read_text(encoding="utf-8")))
                except UnicodeDecodeError:
                    continue
    # 저장소 루트의 md/plans 도 참조 근거로 사용
    for f in ROOT.glob("*.md"):
        try:
            corpus.append((f"root/{f.name}", f.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    return corpus


def count_refs(name: str, corpus: list[tuple[str, str]]) -> dict[str, int]:
    """모듈 참조 수 계산: 점선 풀네임 또는 마지막 두 세그먼트('pkg.mod') 매칭."""
    parts = name.split(".")
    keys = {name}
    if len(parts) >= 2:
        keys.add(".".join(parts[-2:]))  # e.g. routes.legacy
    else:
        keys.add(parts[-1])
    counts: defaultdict[str, int] = defaultdict(int)
    for label, text in corpus:
        for key in keys:
            if key in text:
                counts[label.split("/")[0]] += 1
                break
    return dict(counts)


def main() -> None:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--json", dest="json_out", default=None)
    parsed_args = parser.parse_args()
    raw_json_out = cast(object, getattr(parsed_args, "json_out", None))
    json_out = raw_json_out if isinstance(raw_json_out, str) else None

    mods = discover()
    reach = reachable(mods)
    dyn_loaded = dynamic_load_packages(mods, reach)
    reach |= dyn_loaded
    unreachable = sorted(set(mods) - reach)

    corpus = load_evidence()
    rows: list[CandidateRow] = []
    for name in unreachable:
        info = mods[name]
        refs = count_refs(name, corpus)
        has_test = refs.get("tests", 0) > 0
        has_script = refs.get("scripts", 0) > 0
        has_doc = (refs.get("docs", 0) + refs.get("root", 0)) > 0
        has_dash = refs.get("dashboard", 0) > 0
        if has_script or has_dash:
            tier = "B"
        elif has_test and not has_doc:
            tier = "B+"
        elif has_test or has_doc:
            tier = "C"
        else:
            tier = "A"
        rows.append(
            {
                "module": name,
                "loc": info.loc,
                "tier": tier,
                "refs": refs,
            }
        )

    tier_counts = {tier: sum(1 for row in rows if row["tier"] == tier) for tier in {row["tier"] for row in rows}}
    report: AuditReport = {
        "total_modules": len(mods),
        "reachable_from_entry": len(reach),
        "unreachable_count": len(rows),
        "unreachable_loc": sum(r["loc"] for r in rows),
        "tiers": dict(sorted(tier_counts.items())),
        "candidates": sorted(rows, key=lambda r: (-r["loc"], r["module"])),
    }

    print(f"전체 모듈: {report['total_modules']}개")
    print(f"진입점({', '.join(ENTRY_POINTS)})에서 정적 도달: {len(reach) - len(dyn_loaded)}개")
    print(f"동적 로드(auto_discover)로 생존: {len(dyn_loaded)}개")
    print(f"도달 불가 삭제 후보: {len(rows)}개 모듈 / {report['unreachable_loc']} LOC")
    print()
    hdr = f"{'tier':4} {'LOC':>6}  refs(tests/scripts/dashboard/docs)  module"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        refs = ",".join(f"{k}:{v}" for k, v in sorted(r["refs"].items())) or "-"
        print(f"{r['tier']:4} {r['loc']:>6}  {refs:<34}  {r['module']}")
    print()
    print("등급 요약:", report["tiers"])
    print(
        "tier 설명: A=즉시 삭제 안전(참조 0) | B=scripts/dashboard 전용 참조(함께 정리) | "
        + "B+=테스트 전용(테스트 동반 삭제) | C=문서·테스트 언급(판단 필요)"
    )

    if json_out:
        _ = Path(json_out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nJSON 저장: {json_out}")


if __name__ == "__main__":
    sys.exit(main())
