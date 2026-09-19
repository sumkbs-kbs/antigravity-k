#!/usr/bin/env python3
"""NX-07 before/after 측정 — 문서·지원 범위가 하나의 현재 상태를 가리키는가.

**같은 자로 두 나무를 잰다.** 검사 로직은 작업 트리의 계약 시험
(`tests/test_nx07_doc_consistency.py`)에서 불러오고, 데이터만 `--root` 가 가리키는 나무에서
읽는다. 그래야 "before 가 실패한 이유"가 로직 차이가 아니라 **문서 차이**임이 보인다.

before 나무는 `git archive HEAD` 로 뜬 별도 디렉터리다(작업 트리 무변경).

사용:
    python3 docs/qa/2026-09-16-followup/nx07/repro_nx07_doc_consistency.py --root <tree>

종료 코드: 0 = 전부 통과, 3 = 위반 있음(측정은 완료), 2 = 계측 실패(검사기를 못 읽음).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def load_checker(repo_root: Path):
    """작업 트리의 계약 시험을 검사기로 쓴다(복사하지 않는다 — 자가 갈라지지 않게)."""
    path = repo_root / "tests" / "test_nx07_doc_consistency.py"
    spec = importlib.util.spec_from_file_location("nx07_checker", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"검사기를 읽지 못했다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Recorder:
    def __init__(self, root: Path, checker) -> None:
        self.root = root
        self.checker = checker
        self.checks: list[dict[str, object]] = []

    def text(self, relative: str) -> str | None:
        path = self.root / relative
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def add(self, name: str, problems: list[str], *, note: str = "") -> None:
        entry: dict[str, object] = {
            "check": name,
            "pass": not problems,
            "problem_count": len(problems),
            "problems": problems[:8],
        }
        if note:
            entry["note"] = note
        self.checks.append(entry)

    # -- 검사들 --------------------------------------------------------------
    def check_ports(self) -> None:
        text = self.text("README.md")
        if text is None:
            self.add("readme_port_guidance", ["README.md 없음"])
            return
        code_port = self.checker.code_default_port(self.root)
        ui_port = self.checker.dev_ui_port(self.root)
        problems = self.checker.readme_port_violations(text, code_port, ui_port)
        self.add(
            "readme_port_guidance",
            problems,
            note=f"code_default_port={code_port} dev_ui_port={ui_port}",
        )

    def check_port_roles_documented(self) -> None:
        relative = self.checker.CURRENT_STATUS
        text = self.text(relative)
        if text is None:
            self.add("port_roles_documented", [f"{relative} 없음"])
            return
        code_port = self.checker.code_default_port(self.root)
        ui_port = self.checker.dev_ui_port(self.root)
        missing = [
            token
            for token in (str(code_port), str(ui_port), "SSAK_HOST_URL", "ServerConfig", "vite.config.ts")
            if token not in text
        ]
        problems = [f"포트 역할 표기가 빠졌다: {token}" for token in missing]
        if "AGK_VLLM_API_BASE" not in text:
            problems.append("8000 을 다른 서비스도 쓴다는 사실(무조건 치환 금지의 근거)이 없다")
        self.add("port_roles_documented", problems)

    def check_owner_links(self) -> None:
        problems: list[str] = []
        for relative in self.checker.HISTORY_DOCUMENTS:
            text = self.text(relative)
            if text is None:
                problems.append(f"{relative} 없음")
                continue
            problems.extend(self.checker.owner_link_violations(relative, text, root=self.root))
        self.add("single_status_owner_links", problems)

    def check_gate_count_scope(self) -> None:
        named = (
            "README.md",
            self.checker.CURRENT_STATUS,
            self.checker.SUPPORT_MATRIX,
            self.checker.LEDGER,
            self.checker.CHECKLIST,
            "docs/08_CHANGELOG.md",
            "docs/10_FINAL_READINESS_REPORT.md",
            "docs/13_COMMERCIAL_GA_100_PROGRESS.md",
            "docs/16_COMMERCIAL_RELIABILITY_DEVELOPMENT_PLAN.md",
            "docs/17_COMMERCIAL_RELIABILITY_CHECKLIST.md",
        )
        problems: list[str] = []
        for relative in named:
            text = self.text(relative)
            if text is None:
                continue
            problems.extend(self.checker.gate_count_context_violations(text, relative))
        ga_dir = self.root / "docs" / "ga"
        for path in sorted(ga_dir.glob("*.md")):
            relative = str(path.relative_to(self.root))
            problems.extend(self.checker.gate_count_context_violations(path.read_text(encoding="utf-8"), relative))
        self.add("gate_count_scope", problems)

    def check_human_axis(self) -> None:
        """열린 카드 목록은 **자(yardstick)의 입력**이다 — 대상 나무에 없다고 면제되지 않는다.

        baseline(HEAD)에는 `docs/19` 가 없다(미커밋). 그 때 면제해 버리면 "정말 열린 기술 TODO 가
        있는가"라는 조건이 사라져 before 가 조용히 통과한다 — 조건을 자 쪽에서 고정한다.
        """
        readme = self.text("README.md")
        if readme is None:
            self.add("human_axis_not_only", ["README.md 없음"])
            return
        checklist = (REPO_ROOT / self.checker.CHECKLIST).read_text(encoding="utf-8")
        open_ids = self.checker.open_cards(checklist)
        problems = self.checker.human_axis_violations(readme, open_ids)
        self.add(
            "human_axis_not_only",
            problems,
            note=f"열린 카드 {len(open_ids)}개(작업 트리 docs/19 기준): {', '.join(sorted(open_ids))}",
        )

    def check_open_axes_documented(self) -> None:
        relative = self.checker.CURRENT_STATUS
        text = self.text(relative)
        if text is None:
            self.add("open_axes_documented", [f"{relative} 없음"])
            return
        checklist = (REPO_ROOT / self.checker.CHECKLIST).read_text(encoding="utf-8")
        open_ids = self.checker.open_cards(checklist)
        problems: list[str] = []
        for heading in (
            "## 1. 제품 접속",
            "## 2. 판정",
            "## 3. 8시간 soak",
            "## 4. 열려 있는 기술 TODO",
            "## 5. 사람",
        ):
            if heading not in text:
                problems.append(f"절 없음: {heading}")
        mentioned = {card for card in open_ids if card in text}
        if len(mentioned) < 3:
            problems.append(f"열린 카드 나열 부족: {sorted(mentioned)} (전체 {len(open_ids)})")
        self.add("open_axes_documented", problems)

    def check_support_matrix(self) -> None:
        text = self.text(self.checker.SUPPORT_MATRIX)
        if text is None:
            self.add("support_matrix_levels", [f"{self.checker.SUPPORT_MATRIX} 없음"])
            return
        self.add("support_matrix_levels", self.checker.support_matrix_violations(text))

    def check_soak_phases(self) -> None:
        status = self.text(self.checker.CURRENT_STATUS)
        ledger = self.text(self.checker.LEDGER)
        if status is None or ledger is None:
            missing = [
                name
                for name, value in ((self.checker.CURRENT_STATUS, status), (self.checker.LEDGER, ledger))
                if value is None
            ]
            self.add("soak_phase_separation", [f"{name} 없음" for name in missing])
            return
        self.add("soak_phase_separation", self.checker.soak_phase_violations(status, ledger))


def _all_checks(recorder: "Recorder") -> None:
    for name in (
        "check_ports",
        "check_port_roles_documented",
        "check_owner_links",
        "check_gate_count_scope",
        "check_human_axis",
        "check_open_axes_documented",
        "check_support_matrix",
        "check_soak_phases",
    ):
        getattr(recorder, name)()


def main() -> int:
    parser = argparse.ArgumentParser(description="NX-07 문서 정합성 before/after 측정")
    parser.add_argument("--root", default=str(REPO_ROOT), help="측정할 나무(기본: 저장소 루트)")
    parser.add_argument("--label", default="", help="보고서에 붙일 이름(예: before / after)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        checker = load_checker(REPO_ROOT)
    except Exception as exc:  # noqa: BLE001 — 계측 실패는 측정 실패와 구분한다
        print(json.dumps({"error": f"checker load failed: {exc}"}, ensure_ascii=False))
        return 2

    recorder = Recorder(root, checker)
    try:
        _all_checks(recorder)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"measurement failed: {exc}", "root": str(root)}, ensure_ascii=False))
        return 2

    failed = [check for check in recorder.checks if not check["pass"]]
    report = {
        "check": "nx07_doc_consistency",
        "label": args.label,
        "root": str(root),
        "check_count": len(recorder.checks),
        "failed_count": len(failed),
        "pass": not failed,
        "checks": recorder.checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        f"[{args.label or root.name}] {len(recorder.checks) - len(failed)}/{len(recorder.checks)} checks pass",
        file=sys.stderr,
    )
    return 0 if report["pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
