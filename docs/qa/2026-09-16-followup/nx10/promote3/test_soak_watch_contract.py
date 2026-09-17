"""돌고 있는 soak 의 **조기 경보**가 계약대로 판정하는지 고정한다(승격 3차 배치).

왜 승격하는가: 이 판정식은 `docs/` 안에 있는 동안 **어떤 게이트도 지키지 않았다**(정적 검사는
`src/ tests/ scripts/`, 스위트는 `tests/` 만 본다). 오늘 이 판정식이 세 번 틀렸고 매번 사람이
알아챘다 — 시작 계단을 8시간으로 증폭한 가짜 경보 2회, 그리고 **표본 하나로 판정해 실제 위험을
침묵한** 1회. 그 자리를 이 시험이 지킨다.

고정하는 것:

  1. 저장소 루트 탐색이 **승격으로 깊이가 바뀌어도** 산다(1차 승격이 실제로 밟은 함정).
  2. `--selftest` 가 실제로 문을 걸고 있다 — 검사 수가 0 이면 “초록”이 아니다.
  3. **판정 산술**: 허용 증가율 = 남은 예산 ÷ 남은 시간. 숫자를 시험에 박아 둔다.
  4. 예산을 넘는 최근 기울기는 **경보**하고, 한계 안이면 경보하지 않는다.
  5. 워밍업(실행 25% 전)에는 경보를 보류하되 **숫자는 밝힌다**(침묵하지 않는다).
  6. **읽기 전용** — 실행 디렉터리에 아무것도 쓰지 않는다(측정을 오염시키면 그 8시간이 무효다).
  7. 실행이 없으면 **판정하지 않는다**(exit 3) — 없는 숫자를 발명하지 않는다.

탐색 순서는 승격 선례를 따른다: 승격 위치(`scripts/`)를 먼저, 스테이징(`docs/qa/…/nx10/`)을 나중에.
그래서 이 파일은 이동 전에도 초록이고 이동 뒤에도 초록이다(이빨은 미러 리허설에서 확인한다 —
그때 스테이징 사본이 사라지므로 도구를 치우면 시험이 실패한다).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest


def _repo_root() -> Path:
    """루트를 **걸어 올라가며** 찾는다 — 스테이징(`docs/…/promote3/`)과 승격 위치(`tests/`) 둘 다에서 산다."""
    override = os.environ.get("AGK_REPO_ROOT")
    if override:
        return Path(override).resolve()
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "antigravity_k").is_dir():
            return candidate
    raise RuntimeError("저장소 루트를 찾지 못했다 — AGK_REPO_ROOT 로 지정한다")


REPO_ROOT = _repo_root()
_NX10 = REPO_ROOT / "docs" / "qa" / "2026-09-16-followup" / "nx10"
WATCH_CANDIDATES = (REPO_ROOT / "scripts" / "soak_watch.py", _NX10 / "soak_watch.py")
LOOP_CANDIDATES = (REPO_ROOT / "scripts" / "soak_watch_loop.py", _NX10 / "soak_watch_loop.py")

# 자기시험 검사 수의 하한 — 문을 지우면 “ALL OK” 가 아니라 **여기서** 걸리게 한다(빈 껍데기 방지).
WATCH_MIN_CHECKS = 15
LOOP_MIN_CHECKS = 12
NOT_A_RUN_PID = "999999"


def _first_existing(candidates: tuple[Path, ...], label: str) -> Path:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    pytest.fail(
        f"{label} 을(를) 찾지 못했다 — 승격 위치/스테이징 어디에도 없다: " + ", ".join(str(path) for path in candidates)
    )


def _watch_path() -> Path:
    return _first_existing(WATCH_CANDIDATES, "조기 경보 도구(soak_watch.py)")


def _loop_path() -> Path:
    return _first_existing(LOOP_CANDIDATES, "상시 감시 도구(soak_watch_loop.py)")


def _load_watch() -> ModuleType:
    spec = importlib.util.spec_from_file_location("agk_soak_watch_under_test", _watch_path())
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(path: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path), *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _fixture_watch(module: ModuleType, tmp_path: Path, *, series: list[tuple[float, float]]):
    """표본을 **직접** 넣어 산술만 본다(ps·저널에 의존하지 않는다 — 그건 시험 환경마다 다르다)."""
    duration = 14400.0  # 4시간 → 워밍업 = max(600, 25%) = 1시간
    now = time.time()
    watch = module.Watch(
        workdir=tmp_path,
        soak_started=now - 7200,
        duration=duration,
        interval=1,
        min_ops_per_sec=133,
        rss_limit_mb=64,
        hard_cap_mib=8192,
        max_stall=600,
        pid_pattern="val02_staging.py",
    )
    for at, rss in series:
        watch.samples.append(
            module.Sample(
                at=at,
                pid=os.getpid(),
                alive=True,
                cpu_seconds=1.0,
                rss_mb=rss,
                journal_bytes=100_000_000,
                last_write_age_s=0.0,
            )
        )
    watch.baseline_rss_mb, watch.baseline_at = series[0][1], series[0][0]
    watch.rss_series = list(series)
    return watch


def test_repo_root_walk_up_survives_the_move():
    """도구가 저장소 루트를 걸어 올라가며 찾는가 — `parents[N]` 하드코딩이면 승격 뒤에 깨진다."""
    module = _load_watch()
    root = Path(module.REPO_ROOT)
    assert (root / "pyproject.toml").is_file() and (root / "src" / "antigravity_k").is_dir(), (
        f"저장소 루트를 잘못 계산했다: {root} — 승격 위치에서 src 경로가 어긋난다"
    )
    assert root == REPO_ROOT, f"루트가 시험과 다르다: 도구={root} 시험={REPO_ROOT}"


def test_selftests_actually_check_something():
    """두 도구의 자기시험이 초록이고 **검사 수가 0 이 아니다**(문을 지우면 여기서 걸린다)."""
    watch = _run(_watch_path(), "--selftest")
    assert watch.returncode == 0, f"soak_watch --selftest 실패:\n{watch.stdout[-1500:]}"
    watch_checks = watch.stdout.count("[OK ]")
    assert watch_checks >= WATCH_MIN_CHECKS, f"검사가 {watch_checks}개뿐이다(하한 {WATCH_MIN_CHECKS})"

    loop = _run(_loop_path(), "--selftest")
    assert loop.returncode == 0, f"soak_watch_loop --selftest 실패:\n{loop.stdout[-1500:]}"
    loop_checks = loop.stdout.count("[OK ]")
    assert loop_checks >= LOOP_MIN_CHECKS, f"검사가 {loop_checks}개뿐이다(하한 {LOOP_MIN_CHECKS})"


def test_allowance_arithmetic_is_pinned(tmp_path: Path):
    """허용 증가율 = 남은 예산 ÷ 남은 시간 — 숫자로 박아 둔다.

    4시간 실행 · 경과 2시간 · 증가 +21 MB(기준 64) → 예산 43 MB ÷ 120분 = **+0.358 MB/분**.
    최근 기울기(0.150)가 그보다 작으므로 경보하지 않는다.
    """
    module = _load_watch()
    now = time.time()
    watch = _fixture_watch(
        module,
        tmp_path,
        series=[(now - 7200, 100.0), (now - 1200, 118.0), (now - 600, 120.0), (now, 121.0)],
    )
    code, lines = watch.verdict()
    joined = " | ".join(lines)
    assert "동안 허용 **+0.358 MB/분**" in joined, joined
    assert "최근 실측 +0.150 MB/분" in joined, joined
    assert "이내" in joined, joined
    assert code == module.OK, f"한계 안인데 경보했다(exit {code}):\n{joined}"


def test_budget_over_run_is_flagged(tmp_path: Path):
    """최근 기울기가 허용을 넘고 워밍업·감속이 아니면 **경보**한다(오늘 침묵했던 자리).

    같은 4시간 실행에서 증가 +25 MB → 예산 39 ÷ 120분 = 허용 **+0.325 MB/분** 인데
    최근 25분이 **+0.600 MB/분** — 누적 외삼(+50 MB)은 아직 한계 안이라 **예산 신호가 단독으로** 세운다.
    """
    module = _load_watch()
    now = time.time()
    watch = _fixture_watch(
        module,
        tmp_path,
        series=[(now - 7200, 100.0), (now - 1500, 110.0), (now - 700, 118.0), (now, 125.0)],
    )
    code, lines = watch.verdict()
    joined = " | ".join(lines)
    assert "외삼 +50 MB <" in joined, f"외삼이 한계 안이라는 사실을 밝히지 않았다:\n{joined}"
    assert "최근 실측 +0.600 MB/분 > 허용 +0.325 MB/분" in joined, joined
    assert "SC-6 추세" in joined, joined
    assert code == module.WARN, f"예산 초과 추세를 경보하지 않았다(exit {code}):\n{joined}"


def test_warmup_holds_the_alarm_but_still_prints_the_numbers(tmp_path: Path):
    """워밍업(실행 25% 전)에는 경보하지 않되 숫자는 밝힌다 — 침묵도 거짓 경보도 아닌 중간이 있다."""
    module = _load_watch()
    now = time.time()
    watch = module.Watch(
        workdir=tmp_path,
        soak_started=now - 2700,
        duration=28800,
        interval=1,
        min_ops_per_sec=133,
        rss_limit_mb=64,
        hard_cap_mib=8192,
        max_stall=600,
        pid_pattern="val02_staging.py",
    )
    series = [(now - 2700, 100.0), (now - 1800, 120.0), (now - 600, 131.0), (now, 133.0)]
    for at, rss in series:
        watch.samples.append(
            module.Sample(
                at=at,
                pid=os.getpid(),
                alive=True,
                cpu_seconds=1.0,
                rss_mb=rss,
                journal_bytes=100_000_000,
                last_write_age_s=0.0,
            )
        )
    watch.baseline_rss_mb, watch.baseline_at = 100.0, now - 2700
    watch.rss_series = list(series)
    code, lines = watch.verdict()
    joined = " | ".join(lines)
    assert code == module.OK, f"워밍업 중인데 경보했다:\n{joined}"
    assert "SC-6 예산:" in joined and "허용" in joined, f"예산 수치를 감췄다:\n{joined}"
    assert "워밍업" in joined, f"보류 이유를 말하지 않았다:\n{joined}"


def test_reading_a_run_does_not_write_into_it(tmp_path: Path):
    """**읽기 전용** — 도는 실행의 디렉터리를 건드리면 그 8시간의 측정이 오염된다."""
    run_dir = tmp_path / "nx10-soak-work-fixture"
    run_dir.mkdir()
    (run_dir / "journal").write_bytes(b"x" * 4096)
    (run_dir / "soak.db").write_bytes(b"sqlite")
    before = {path.name: (path.stat().st_size, path.stat().st_mtime_ns) for path in run_dir.iterdir()}

    result = _run(_watch_path(), "--once", "--workdir", str(run_dir), "--pid", str(os.getpid()), cwd=tmp_path)

    after = {path.name: (path.stat().st_size, path.stat().st_mtime_ns) for path in run_dir.iterdir()}
    assert after == before, f"실행 디렉터리가 바뀌었다: {before} → {after}"
    assert result.returncode in (0, 2), f"표본을 읽지 못했다(exit {result.returncode}):\n{result.stdout[-800:]}"
    assert list(tmp_path.iterdir()) == [run_dir], "도구가 실행 밖에 파일을 만들었다"


def test_no_run_means_no_verdict(tmp_path: Path):
    """실행이 없으면 판정하지 않는다 — 없는 숫자를 발명하지 않는다(exit 3)."""
    empty = tmp_path / "no-run"
    empty.mkdir()
    module = _load_watch()
    result = _run(_watch_path(), "--once", "--workdir", str(empty), "--pid", NOT_A_RUN_PID, cwd=tmp_path)
    assert result.returncode == module.NO_RUN, (
        f"실행이 없는데 exit {result.returncode} (기대 {module.NO_RUN}):\n{result.stdout[-800:]}"
    )
    assert "RSS 증가 +" not in result.stdout, "실행이 없는데 증가율을 말했다(발명한 숫자다)"
    assert "SC-6 예산:" not in result.stdout, "실행이 없는데 예산을 계산했다"


def test_loop_writes_only_where_it_is_told(tmp_path: Path):
    """상시 감시의 **파생물 위치를 인자로 통제**할 수 있고, 화면이 실제로 그려진다."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "journal").write_bytes(b"x" * 8192)
    history = tmp_path / "history.jsonl"
    live = tmp_path / "live.html"

    result = _run(
        _loop_path(),
        "--once",
        "--workdir",
        str(run_dir),
        "--pid",
        str(os.getpid()),
        "--history",
        str(history),
        "--out-html",
        str(live),
        cwd=tmp_path,
    )

    assert result.returncode in (0, 2, 6), f"감시가 판정하지 못했다(exit {result.returncode}):\n{result.stdout[-800:]}"
    assert history.is_file(), "이력을 지정한 경로에 쓰지 않았다"
    assert live.is_file(), "화면을 지정한 경로에 쓰지 않았다"
    html = live.read_text(encoding="utf-8")
    assert 'data-badge="status"' in html, "화면에 경보 등급 배지가 없다"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["history.jsonl", "live.html", "run"], (
        f"지정하지 않은 곳에 파일을 만들었다: {sorted(p.name for p in tmp_path.iterdir())}"
    )
