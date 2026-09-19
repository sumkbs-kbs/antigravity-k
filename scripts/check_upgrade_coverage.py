"""벤치마크 업그레이드 신규 파일 커버리지 게이트 (Phase 59).

=====================================================================
BENCHMARK_UPGRADE_PLAN_2026-09.md의 신규 파일들이 90% 미만으로
떨어지면 실패한다 — Phase 25(bridge/disclosure)와 Phase 58
(lora_pipeline/messages_api)에서 달성한 커버리지가 회귀하지 않게.

사용법:
    # 1) 프로젝트 전체 커버리지 측정 (pyproject [tool.coverage.run] 사용)
    uv run --no-sync pytest tests/ -q -m "not slow and not benchmark" --cov=src/antigravity_k

    # 2) 게이트 실행 (기본 .coverage 읽음)
    uv run --no-sync python scripts/check_upgrade_coverage.py

    # 명시적 데이터 파일/JSON 지정도 가능
    uv run --no-sync python scripts/check_upgrade_coverage.py --coverage-json cov.json
    uv run --no-sync python scripts/check_upgrade_coverage.py --data-file .coverage_msg

종료 코드: 모든 파일 90% 이상이면 0, 하나라도 미달이면 1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 게이트 대상: 계획서(Phase 1~58)에서 신규 추가된 소스 파일.
# 커버리지 측정 대상이 늘면 여기 한 줄만 추가하면 된다.
UPGRADE_FILES: tuple[str, ...] = (
    "src/antigravity_k/api/routes/messages_api.py",
    "src/antigravity_k/api/routes/disclosure_api.py",
    "src/antigravity_k/api/routes/responses_api.py",
    "src/antigravity_k/engine/anthropic_tool_bridge.py",
    "src/antigravity_k/engine/openai_tool_bridge.py",
    "src/antigravity_k/engine/openai_responses_bridge.py",
    "src/antigravity_k/engine/agent_bridges.py",
    "src/antigravity_k/engine/data_recipes.py",
    "src/antigravity_k/engine/pdf_source_options.py",
    "src/antigravity_k/engine/lora_pipeline.py",
    "src/antigravity_k/engine/quant_quality.py",
    "src/antigravity_k/engine/session_disclosure.py",
    # unsloth_script_api.py는 제외 — 설치 검증 절반이 unsloth 미설치 환경에서 스킵되어
    # CI base 레그에서 정직하게 90%에 도달할 수 없다. 대신 weekly-drift job이 이 파일의
    # 드리프트를 직접 검증한다 (Phase 54).
)

THRESHOLD = 90.0

# 백분율 산정 방식: 기본 statement 기반 (CI pytest-cov --cov-report= 와 동일).
# branch 데이터가 .coverage에 있으면 coverage가 percent_covered에 반영하므로
# branch 포함 측정 시 기준이 더 엄격해진다 (90% 유지가 오히려 안전).


def _percent(stmts: int, missing: int) -> float:
    if stmts <= 0:
        return 100.0
    return round(100.0 * (stmts - missing) / stmts, 1)


def collect_results(coverage_json: Path) -> dict[str, float]:
    """coverage json의 파일별 퍼센트 집계 (게이트 대상만)."""
    import json

    data = json.loads(coverage_json.read_text(encoding="utf-8"))
    files = data.get("files", {})
    results: dict[str, float] = {}
    for rel in UPGRADE_FILES:
        info = files.get(rel)
        if info is None:
            # source 필터로 측정되지 않은 파일 — 게이트에서 제외 (측정 범위 문서화)
            continue
        summary = info["summary"]
        results[rel] = _percent(summary["num_statements"], summary["missing_lines"])
    return results


def collect_from_data_file(data_file: Path) -> dict[str, float]:
    """.coverage 데이터를 coverage API로 정확히 분석해 퍼센트 집계 (게이트 대상만).

    CoverageData.lines()는 "실행된 라인"이지 statements가 아니므로 직접 쓰면
    전부 100%로 오판한다. Coverage.json_report가 문 statements/branch 분석을
    수행하게 하여 CLI와 동일한 숫자를 보장한다.
    """
    import json
    import tempfile  # noqa: PLC0415 — CLI 진입점 지연 임포트

    from coverage import Coverage  # noqa: PLC0415

    if not data_file.is_file():
        raise SystemExit(f"coverage data file not found: {data_file}")

    cov = Coverage(data_file=str(data_file))
    cov.load()
    morfs = [str(REPO_ROOT / rel) for rel in UPGRADE_FILES]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cov.json"
        cov.json_report(morfs=morfs, outfile=str(out))
        payload = json.loads(out.read_text(encoding="utf-8"))

    files = payload.get("files", {})
    results: dict[str, float] = {}
    for rel in UPGRADE_FILES:
        info = files.get(rel)
        if info is None:
            continue
        summary = info["summary"]
        results[rel] = round(summary["percent_covered"], 1)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--coverage-json", type=Path, help="coverage json 출력 파일 (기본: .coverage 사용)")
    parser.add_argument("--data-file", type=Path, default=REPO_ROOT / ".coverage", help=".coverage 데이터 파일")
    args = parser.parse_args()

    if args.coverage_json is not None:
        results = collect_results(args.coverage_json)
    else:
        results = collect_from_data_file(args.data_file)

    if not results:
        print("게이트 대상 파일이 커버리지 데이터에 없다 — 측정 범위 확인 필요")
        return 1

    failures: list[str] = []
    print(f"{'파일':<64} {'커버리지':>8}  판정")
    for rel, pct in sorted(results.items()):
        ok = pct >= THRESHOLD
        print(f"{rel:<64} {pct:>7}%  {'OK' if ok else 'FAIL (<90%)'}")
        if not ok:
            failures.append(rel)

    measured_missing = sorted(set(UPGRADE_FILES) - set(results))
    if measured_missing:
        print(f"\n(측정 제외: {len(measured_missing)}개 — 이번 측정 범위에 없음: {', '.join(measured_missing)})")

    if failures:
        print(f"\n커버리지 게이트 실패: {len(failures)}개 파일이 {THRESHOLD}% 미만")
        return 1
    print(f"\n커버리지 게이트 통과: {len(results)}개 파일 모두 {THRESHOLD}% 이상")
    return 0


if __name__ == "__main__":
    sys.exit(main())
