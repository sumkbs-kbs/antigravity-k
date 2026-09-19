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
  8. **다른 workdir 의 같은 이름 프로세스는 실행이 아니다** — 하네스는 `--workdir <감시 중인 디렉터리>` 로
     뜨므로 그 계약을 읽고 가른다(realpath 정규화). `--workdir` 선언이 없으면 이름이 같아도 후보가 아니고,
     맞는 후보가 하나도 없으면 **아무것도 채택하지 않는다**. 이 문이 없어서 2026-09-17 에 배치 리허설의 처리량
     프루브(5~60초짜리 하네스)가 후보의 첫 자리를 차지해 표본 한 행이 계열에 섞였고, 그 한 행이 **없는
     급강하**를 만들었다(`GATE_LEDGER` §25-9).

탐색 순서는 승격 선례를 따른다: 승격 위치(`scripts/`)를 먼저, 스테이징(`docs/qa/…/nx10/`)을 나중에.
그래서 이 파일은 이동 전에도 초록이고 이동 뒤에도 초록이다(이빨은 미러 리허설에서 확인한다 —
그때 스테이징 사본이 사라지므로 도구를 치우면 시험이 실패한다).
"""

from __future__ import annotations

import importlib.util
import json
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


def test_foreign_workdir_harness_is_not_a_run(tmp_path: Path):
    """같은 이름·같은 인터프리터라도 **감시 중인 workdir 이 아니면** 그 실행이 아니다.

    외부 픽스처를 **먼저** 띄워 pid 가 앞서게 해야 한다 — 실제 사고가 정확히 그 순서로 났다
    (`pgrep` 오름차순이 첫 후보를 먼저 내주었고, 감시가 막 시작해 붙잡은 pid 가 없을 때 그 후보가 채택됐다).
    """
    module = _load_watch()
    token = f"nx10-foreign-workdir-{os.getpid()}"
    mine_wd = tmp_path / "workdir-mine"
    other_wd = tmp_path / "workdir-other"
    mine_wd.mkdir()
    other_wd.mkdir()

    def _spawn(wd: Path) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)", token, "--workdir", str(wd)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    foreign = _spawn(other_wd)  # 먼저 띄운다 = pid 가 앞선다(사고의 순서를 재현)
    mine = _spawn(mine_wd)
    try:
        time.sleep(0.4)
        watch = module.Watch(
            workdir=mine_wd,
            soak_started=time.time() - 60,
            duration=28800,
            interval=1,
            min_ops_per_sec=133,
            rss_limit_mb=64,
            hard_cap_mib=8192,
            max_stall=600,
            pid_pattern=token,
        )
        watch.samples.append(watch.take(None))
        watch.samples.append(watch.take(None))
        assert watch.rejected_foreign_workdir == [foreign.pid], (
            f"다른 workdir 후보를 빼지 않았다: 뺀=[{watch.rejected_foreign_workdir}] 기대=[{foreign.pid}]"
        )
        assert watch.samples[-1].pid == mine.pid, (
            f"남의 workdir 을 채택했다: 고른 pid={watch.samples[-1].pid} 기대={mine.pid} (외부={foreign.pid})"
        )
        # 이 문은 **거부**다(종전에는 관대한 되돌림이었다): 감시 중인 workdir 을 선언한 후보가 하나도 없으면
        # 후보를 전부 남기는 대신 **아무것도 채택하지 않는다**. 2026-09-17 에 그 관대함이 리허설 프루브를
        # 계열에 앉혔다 — 없으면 없는 대로 말하는 편이 모르는 실행의 숫자로 추세를 만드는 것보다 옳다.
        fallback = module.Watch(
            workdir=tmp_path / "no-such-needle",
            soak_started=time.time() - 60,
            duration=28800,
            interval=1,
            min_ops_per_sec=133,
            rss_limit_mb=64,
            hard_cap_mib=8192,
            max_stall=600,
            pid_pattern=token,
        )
        assert fallback._candidates() == [], f"workdir 이 하나도 안 맞는데 후보를 남겼다: {fallback._candidates()}"
        assert sorted(fallback.rejected_foreign_workdir) == sorted([foreign.pid, mine.pid]), (
            f"뺐다면 그 사실을 남겨야 한다: {fallback.rejected_foreign_workdir}"
        )
        fallback.samples.append(fallback.take(None))
        fallback.samples.append(fallback.take(None))
        assert all(sample.pid is None for sample in fallback.samples), (
            f"맞는 하네스가 없는데 pid 를 채택했다: {[s.pid for s in fallback.samples]}"
        )
        reason = " | ".join(fallback.verdict()[1])
        assert "찾지 못했다" in reason and "후보를 뺐다" in reason, f"없는 까닭을 밝히지 않았다: {reason}"
    finally:
        for process in (mine, foreign):
            process.terminate()
            process.wait(timeout=10)


def test_python_without_a_workdir_declaration_is_not_the_soak(tmp_path: Path):
    """하네스의 계약은 `--workdir` 이다 — 선언이 없으면 이름이 같아도 **다른 실행**이다.

    왜 별도 시험인가: 종전 픽스처는 “진짜 하네스”를 `--workdir` 없이 띄웠고, 그래서 도구의 관대한
    되돌림이 시험에 **고정**돼 있었다(시험이 구현의 폭을 따라간 게 아니라 넓혀 둔 셈). 계약을 시험에도
    그대로 쓴다: 러너는 항상 `--workdir` 로 띄우므로, 그것이 없는 파이썬은 감시 대상이 아니다.
    """
    module = _load_watch()
    token = f"nx10-bare-contract-{os.getpid()}"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    bare = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)", token],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.4)
        watch = module.Watch(
            workdir=run_dir,
            soak_started=time.time() - 60,
            duration=28800,
            interval=1,
            min_ops_per_sec=133,
            rss_limit_mb=64,
            hard_cap_mib=8192,
            max_stall=600,
            pid_pattern=token,
        )
        watch.samples.append(watch.take(None))
        watch.samples.append(watch.take(None))
        assert watch.rejected_no_workdir == [bare.pid], (
            f"선언 없는 프로세스를 빼지 않았다: 뺀=[{watch.rejected_no_workdir}] 기대=[{bare.pid}]"
        )
        assert watch.samples[-1].pid is None, f"선언 없는 프로세스를 soak 으로 채택했다: pid={watch.samples[-1].pid}"
    finally:
        bare.terminate()
        bare.wait(timeout=10)


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


def test_loop_attaches_to_a_run_already_in_flight(tmp_path: Path):
    """돌고 있는 soak 에 감시를 **나중에 붙일 수 있다** — 첫 표본의 pid 없음을 “사라졌다”로 읽지 않는다.

    왜 계약인가: 감시를 재부착하는 일은 정상 운영이다(작업지시에 따라 화면을 다시 붙인다). 새 후보는 연속
    두 표본을 봐야 채택되므로(fresh 감시는 pid 가 없는 상태로 시작한다) 첫 표본은 **반드시** pid 가 없다 —
    종전에는 그 한 표본으로 루프가 즉사해, 돌고 있는 8시간을 아무 경보 없이 지나가게 두었다(실측 2026-09-17).
    이 시험은 **--pid 를 주지 않고** 붙여서 실제로 붙는지, 그리고 pid 없는 표본을 이력에 남기지 않는지 본다.
    """
    token = f"nx10-attach-{os.getpid()}"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "journal").write_bytes(b"x" * 4096)
    history = tmp_path / "history.jsonl"
    live = tmp_path / "live.html"
    harness = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)", token, "--workdir", str(run_dir)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.4)
        module = _load_watch()
        result = subprocess.run(
            [
                sys.executable,
                str(_loop_path()),
                "--samples",
                "1",
                "--interval",
                "1",
                "--workdir",
                str(run_dir),
                "--history",
                str(history),
                "--out-html",
                str(live),
            ],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env={**os.environ, "NX10_WATCH_PROC_PATTERN": token},
        )
        assert result.returncode != module.NO_RUN, (
            f"돌고 있는 실행에 붙지 못했다(exit {result.returncode}):\n{result.stdout[-800:]}"
        )
        rows = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert [row["pid"] for row in rows] == [harness.pid], (
            f"붙은 실행의 표본을 남기지 않았다: {[row.get('pid') for row in rows]}"
        )
        assert live.is_file() and 'data-badge="status"' in live.read_text(encoding="utf-8"), "화면을 갱신하지 않았다"
    finally:
        harness.terminate()
        harness.wait(timeout=10)
