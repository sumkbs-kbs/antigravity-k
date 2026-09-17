"""돌고 있는 8시간 soak 의 **조기 경보** — 도중에 읽는 도구(끝나야 판정하는 회수 도구와 다르다).

왜 필요한가(오늘의 두 실패가 같은 모양이었다): 회수 도구 `harvest` 는 **끝난 실행**을 판정하고,
무응답 상한(기본 1800초)까지 기다려야 “멈춤”을 안다. 그래서

  ① 1차 재실행은 47분에야 journal 이 **기본 hard cap 을 8분 뒤 넘긴다**는 것을 알았고(설정 때문의 거짓 FAIL),
  ② 2차 재실행은 7분에 멈춘 뒤에도 30분을 더 기다려야 그 사실을 말할 수 있었다.

이 도구는 매 표본(기본 60초)마다 **살아 있음 · 쓰기 진행 · journal 증가율 vs 보존 cap · RSS 기울기 vs 기준**을
한 화면으로 보고, 위험하면 **그 자리에서** exit code 로 알린다. 읽기만 한다(제품·실행을 건드리지 않는다).

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
        docs/qa/2026-09-16-followup/nx10/soak_watch.py            # 끝날 때까지 감시
    … soak_watch.py --once                                        # 지금 한 표본
    … soak_watch.py --samples 3 --interval 30                     # 30초 간격 3표본
    … soak_watch.py --selftest                                    # 픽스처로 문이 실제로 걸리는지

exit: 0 정상 · 2 경고 · 3 실행을 찾지 못함 · 6 멈춤(살아 있지만 진행 없음)

환경변수(기본값): `NX10_WATCH_PID` · `NX10_WATCH_WORKDIR`(없으면 최신 `/tmp/nx10-soak-work-*`) ·
`NX10_WATCH_INTERVAL`(60) · `NX10_WATCH_MIN_OPS_PER_SEC`(133 — preflight 하한과 같은 값) ·
`NX10_WATCH_RSS_LIMIT_MB`(64 — SC-6 기준) · `NX10_WATCH_HARD_CAP_MIB`(8192 — 러너가 export 한 값, 기록이 있으면 그 값을 읽는다) ·
`NX10_WATCH_MAX_STALL`(600) · `NX10_WATCH_PROC_PATTERN`(val02_staging.py)

**한계를 먼저 적는다**: append 수는 journal 바이트에서 **추정**한다(실측 상수 `B_PER_EVENT` = 8시간 FAIL 실행의
24.4 MB / 70,431 = 346.6 B). 이 도구는 정확한 계수가 아니라 **경보**가 목적이므로, 판정(회수)은 여전히
`collect_soak_result.py` 가 한다. 표본 비용은 `stat` 몇 번이라 측정을 거의 건드리지 않는다(저널을 읽지 않는다).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
NX10_OUT = REPO_ROOT / "docs" / "qa" / "2026-09-16-followup" / "nx10"

B_PER_EVENT = 346.6  # 8시간 FAIL 실행 실측(24.4 MB / 70,431 이벤트)

OK, WARN, NO_RUN, STALLED = 0, 2, 3, 6


@dataclass
class Sample:
    at: float
    pid: int | None
    alive: bool
    cpu_seconds: float | None
    rss_mb: float | None
    journal_bytes: int | None
    last_write_age_s: float | None

    @property
    def est_events(self) -> float | None:
        return None if self.journal_bytes is None else self.journal_bytes / B_PER_EVENT


@dataclass
class Watch:
    workdir: Path
    soak_started: float  # 실행 자체의 시작 시각(감시 시작이 아니다)
    duration: int
    interval: int
    min_ops_per_sec: float
    rss_limit_mb: float
    hard_cap_mib: float
    max_stall: int
    pid_pattern: str
    samples: list[Sample] = field(default_factory=list)
    # RSS 기준선은 **이 프로세스가 아니라 실행 첫 표본**에 둔다 — 감시가 재시작되더라도
    # “실행 시작 이후 얼마나 자랐나”가 흔들리면 안 된다(실측: 재시작 직후 +0.0 MB 로 보였다).
    baseline_rss_mb: float | None = None
    baseline_at: float | None = None
    # 실행 첫 표본부터의 (시각, RSS) 계열 — 회수가 **감속 여부**를 보려면 표본 두 개로는 부족하다.
    rss_series: list[tuple[float, float]] = field(default_factory=list)

    # ── 측정 ────────────────────────────────────────────────────────────
    def _find_pid(self, override: str | None) -> int | None:
        if override:
            try:
                return int(override)
            except ValueError:
                return None
        try:
            out = subprocess.run(
                ["pgrep", "-f", self.pid_pattern], capture_output=True, text=True, check=False
            ).stdout.split()
        except OSError:
            return None
        return int(out[0]) if out else None

    @staticmethod
    def _ps(pid: int, column: str) -> str:
        out = subprocess.run(["ps", "-o", f"{column}=", "-p", str(pid)], capture_output=True, text=True, check=False)
        return out.stdout.strip()

    @staticmethod
    def _parse_cputime(text: str) -> float | None:
        """`ps -o cputime` 형식(`MM:SS.ss` 또는 `HH:MM:SS`)을 초로."""
        if not text:
            return None
        parts = text.split(":")
        try:
            numbers = [float(p) for p in parts]
        except ValueError:
            return None
        seconds = 0.0
        for value in numbers:
            seconds = seconds * 60 + value
        return seconds

    def _journal_bytes(self) -> int:
        total = 0
        for path in self.workdir.rglob("*"):
            try:
                if path.is_file():
                    total += path.stat().st_size
            except OSError:
                continue
        return total

    def _last_write_age(self) -> float | None:
        newest = 0.0
        for path in (self.workdir, *self.workdir.rglob("*")):
            try:
                newest = max(newest, path.stat().st_mtime)
            except OSError:
                continue
        return None if newest == 0.0 else max(0.0, time.time() - newest)

    def take(self, pid_override: str | None, *, rss_override: float | None = None) -> Sample:
        now = time.time()
        pid = self._find_pid(pid_override)
        alive = False
        cpu: float | None = None
        rss: float | None = rss_override
        if pid is not None:
            alive = bool(self._ps(pid, "stat"))
            if alive:
                cpu = self._parse_cputime(self._ps(pid, "cputime"))
                if rss is None:
                    raw_rss = self._ps(pid, "rss")
                    rss = float(raw_rss) / 1024 if raw_rss.isdigit() else None
        return Sample(
            at=now,
            pid=pid,
            alive=alive,
            cpu_seconds=cpu,
            rss_mb=rss,
            journal_bytes=self._journal_bytes(),
            last_write_age_s=self._last_write_age(),
        )

    # ── 판정 ────────────────────────────────────────────────────────────
    def _rss_decelerating(self) -> bool:
        """최근 구간 RSS 증가율이 앞 구간보다 뚜렷이 낮은가(워밍업이면 참). 판단 근거가 부족하면 거짓.

        계열이 처음부터 있으면 그것을(감시 재시작에도 유지), 없으면 이 프로세스의 표본을 쓴다.
        """
        series = self.rss_series or [(s.at, s.rss_mb) for s in self.samples if s.rss_mb is not None]
        if len(series) < 4:
            return False
        middle = len(series) // 2
        first, second = series[:middle], series[middle:]
        first_rate = (first[-1][1] - first[0][1]) / max(1.0, first[-1][0] - first[0][0])
        second_rate = (second[-1][1] - second[0][1]) / max(1.0, second[-1][0] - second[0][0])
        if first_rate <= 0:
            return False
        return second_rate < 0.5 * first_rate

    def verdict(self) -> tuple[int, list[str]]:
        """(exit code, 사람이 읽는 줄들). 표본이 하나뿐이면 추세 판단은 보류한다."""
        lines: list[str] = []
        warns: list[str] = []
        last = self.samples[-1]
        if not last.alive:
            return NO_RUN, [f"실행을 찾지 못했다(pid {last.pid}) — 패턴 `{self.pid_pattern}`"]
        elapsed = max(0.0, last.at - self.soak_started)
        lines.append(
            f"pid {last.pid} · 실행 경과 {_hms(elapsed)} / {_hms(self.duration)}"
            f" · CPU {last.cpu_seconds:.1f}s · RSS {last.rss_mb:.0f} MB"
            f" · journal {(last.journal_bytes or 0) / 1048576:.1f} MiB · 마지막 쓰기 {last.last_write_age_s:.0f}s 전"
        )

        previous = self.samples[-2] if len(self.samples) >= 2 else None
        if previous is not None:
            progress = (last.journal_bytes or 0) - (previous.journal_bytes or 0)
            cpu_delta = (last.cpu_seconds or 0) - (previous.cpu_seconds or 0)
            stall_ref = last.last_write_age_s or 0.0
            if progress <= 0 and cpu_delta <= 0.05 and stall_ref > self.max_stall:
                return STALLED, lines + [
                    f"멈춤: {stall_ref:.0f}s 동안 쓰기도 CPU 도 진행 없음(상한 {self.max_stall}s) — "
                    "`soak_control.sh harvest` 는 종료를 기다리므로 이 상태로는 8시간이 결과 0 이 된다"
                ]
            # **외삼은 순간 기울기가 아니라 누적 평균으로 한다.** 왜인가: 순간 기울기는 표본 하나의 작은
            # 계단(할당 high-water)을 8시간으로 증폭해 **가짜 경보**를 만든다(실측: 29분에 RSS 가 1.9 MB
            # 올랐다고 “8시간 외삼 +305 MB, SC-6 빨개진다”가 떴다 — 그대로 두면 다음 사람이 배지를 안 믿는다).
            # 누적 평균은 경과 시간이 길수록 안정되고, 고장난 코드의 **선형 누수**는 여전히 크게 잡힌다
            # (tail() 결함 실행: 29분 시점 이미 +100 MB → 외삼 +1,700 MB 로 경보가 떴다).
            if progress > 0 and elapsed > 0:
                avg_rate = (last.journal_bytes or 0) / elapsed
                rate_events = avg_rate / B_PER_EVENT
                lines.append(
                    f"평균 증가 {avg_rate / 1024:.0f} KiB/s ≈ {rate_events:.0f} ops/s(추정, 바이트 기반)"
                    f" — 직전 표본 +{progress / 1024:.0f} KiB"
                )
                if rate_events < self.min_ops_per_sec:
                    warns.append(
                        f"추정 처리량 {rate_events:.0f} ops/s < 하한 {self.min_ops_per_sec:.0f} ops/s"
                        " — 이대로면 8시간에 요청한 양을 못 채운다"
                    )
                remaining = max(0, self.duration - elapsed)
                projected_bytes = (last.journal_bytes or 0) + avg_rate * remaining
                cap_bytes = self.hard_cap_mib * 1048576
                if projected_bytes > cap_bytes:
                    warns.append(
                        f"보존 cap 위험: 평균 증가율대로면 종료 시 {projected_bytes / 1048576:.0f} MiB > hard cap "
                        f"{self.hard_cap_mib:.0f} MiB — 넘긴 뒤의 쓰기 거절(507)은 하네스가 `errors` 로 세므로 "
                        "설정 때문의 거짓 FAIL 이 된다"
                    )
                else:
                    lines.append(
                        f"cap 여유: 종료 시 추정 {projected_bytes / 1048576:.0f} MiB / cap {self.hard_cap_mib:.0f} MiB"
                    )
            baseline_rss = self.baseline_rss_mb
            baseline_at = self.baseline_at
            if baseline_rss is None and self.samples and self.samples[0].rss_mb is not None:
                baseline_rss, baseline_at = self.samples[0].rss_mb, self.samples[0].at
            if last.rss_mb is not None and baseline_rss is not None and baseline_at is not None:
                growth = last.rss_mb - baseline_rss
                span = last.at - baseline_at
                if growth > 0 and span > 0:
                    projected_growth = growth * (self.duration / span)
                    lines.append(
                        f"RSS 증가 +{growth:.1f} MB(실행 {_hms(span)} 경과) → 8시간 외삼 +{projected_growth:.0f} MB"
                        f" {'<' if projected_growth <= self.rss_limit_mb else '>'} 기준 {self.rss_limit_mb:.0f} MB"
                    )
                    # 두 가지를 더 요구한다. 이유는 둘 다 실측 오탐에서 나왔다:
                    #  ① **워밍업**: 실행 초기에는 할당·캐시가 차오르며 RSS 가 계단식으로 오르고
                    #     나중에 평탄해진다. 33분에 2 MB 오른 것을 8시간으로 늘리면 +126 MB 라는
                    #     경보가 떴다(실측 10:53Z) — 그 실행은 이후 평탄해졌다(10분 리허설 기울기 0.004 KB/op).
                    #  ② **감속**: 뒤 구간 증가율이 앞 구간보다 확실히 낮으면 회수가 아니라 워밍업이다.
                    warmup = max(600.0, 0.25 * self.duration)
                    decelerating = self._rss_decelerating()
                    if projected_growth <= self.rss_limit_mb:
                        pass
                    elif elapsed < warmup:
                        lines.append(
                            f"(외삼 +{projected_growth:.0f} MB 은 기준 초과지만 실행 {_hms(elapsed)} 가 워밍업 "
                            f"{_hms(warmup)}(실행 25%) 보다 짧다 — 경보하지 않고 기다린다)"
                        )
                    elif decelerating:
                        lines.append(
                            f"(외삼 +{projected_growth:.0f} MB 이지만 **감속 중** — 최근 구간 증가율이 앞 구간의 "
                            "절반 미만이다. 워밍업으로 보고 경보하지 않는다)"
                        )
                    else:
                        warns.append(
                            f"RSS 외삼 +{projected_growth:.0f} MB > SC-6 기준 {self.rss_limit_mb:.0f} MB"
                            " — 워밍업이 지났는데도 증가세가 유지된다면 SC-6 가 빨개진다"
                        )
        for warn in warns:
            lines.append(f"경고: {warn}")
        return (WARN if warns else OK), lines


def _hms(seconds: float) -> str:
    seconds = int(max(0, seconds))
    return f"{seconds // 3600:d}h{(seconds % 3600) // 60:02d}m{seconds % 60:02d}s"


def _default_workdir() -> Path | None:
    candidates = sorted(Path("/tmp").glob("nx10-soak-work-*"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    return candidates[-1] if candidates else None


def _hard_cap_from_record() -> float | None:
    """러너가 남긴 `retention_caps:` 줄에서 실제 설정을 읽는다(추측보다 기록이 우선)."""
    record = NX10_OUT / "soak-exit.txt"
    if not record.is_file():
        return None
    blocks = record.read_text(encoding="utf-8").split("retention_caps:")
    if len(blocks) < 2:
        return None
    match = re.search(r"hard=(\d+)MiB", blocks[-1])
    return float(match.group(1)) if match else None


def _soak_start(workdir: Path) -> float:
    """실행 시작 시각 — 기록(`soak-exit.txt` 의 마지막 `start_time:`) > 작업디렉터리 이름 순으로 믿는다."""
    override = os.environ.get("NX10_WATCH_STARTED")
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    record = NX10_OUT / "soak-exit.txt"
    if record.is_file():
        starts = re.findall(r"^start_time: (.+)$", record.read_text(encoding="utf-8"), flags=re.MULTILINE)
        if starts:
            try:
                return time.mktime(time.strptime(starts[-1].strip(), "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
            except ValueError:
                pass
    match = re.search(r"nx10-soak-work-(\d{8}T\d{6})Z", workdir.name)
    if match:
        try:
            return time.mktime(time.strptime(match.group(1), "%Y%m%dT%H%M%S")) - time.timezone
        except ValueError:
            pass
    return time.time()


def _make_watch(args: argparse.Namespace) -> Watch | None:
    explicit = args.workdir or os.environ.get("NX10_WATCH_WORKDIR")
    workdir = Path(explicit) if explicit else _default_workdir()
    if workdir is None or not workdir.exists():
        return None
    return Watch(
        workdir=workdir,
        soak_started=_soak_start(workdir),
        duration=int(os.environ.get("NX10_WATCH_DURATION") or args.duration),
        interval=int(os.environ.get("NX10_WATCH_INTERVAL") or args.interval),
        min_ops_per_sec=float(os.environ.get("NX10_WATCH_MIN_OPS_PER_SEC") or 133),
        rss_limit_mb=float(os.environ.get("NX10_WATCH_RSS_LIMIT_MB") or 64),
        hard_cap_mib=float(os.environ.get("NX10_WATCH_HARD_CAP_MIB") or _hard_cap_from_record() or 8192),
        max_stall=int(os.environ.get("NX10_WATCH_MAX_STALL") or 600),
        pid_pattern=os.environ.get("NX10_WATCH_PROC_PATTERN") or "val02_staging.py",
    )


def run_watch(args: argparse.Namespace) -> int:
    watch = _make_watch(args)
    if watch is None:
        print("실행 작업디렉터리를 찾지 못했다 — `--workdir` 또는 `NX10_WATCH_WORKDIR` 로 지정한다")
        return NO_RUN
    print(
        f"감시: {watch.workdir} · 실행 시작 {time.strftime('%H:%M:%SZ', time.gmtime(watch.soak_started))}"
        f" · 간격 {watch.interval}s · 기준 처리량 {watch.min_ops_per_sec:.0f} ops/s · cap {watch.hard_cap_mib:.0f} MiB"
    )
    total = 1 if args.once else max(1, args.samples)
    code = OK
    for index in range(total):
        if index:
            time.sleep(watch.interval)
        watch.samples.append(watch.take(args.pid))
        code, lines = watch.verdict()
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for line in lines:
            print(f"  [{stamp}] {line}")
        if code in (STALLED, NO_RUN):
            print(f"  [{stamp}] 판정: {'멈춤' if code == STALLED else '실행 없음'} — 감시를 끝낸다")
            break
        if args.samples and index + 1 >= args.samples:
            break
    if code not in (STALLED, NO_RUN):
        print(f"판정: {'경고' if code == WARN else '정상'}")
    if args.json and watch.samples:
        last = watch.samples[-1]
        print(
            json.dumps(
                {
                    "exit": code,
                    "workdir": str(watch.workdir),
                    "pid": last.pid,
                    "elapsed_s": round(max(0.0, last.at - watch.soak_started), 1),
                    "rss_mb": last.rss_mb,
                    "journal_bytes": last.journal_bytes,
                    "last_write_age_s": None if last.last_write_age_s is None else round(last.last_write_age_s, 1),
                },
                ensure_ascii=False,
            )
        )
    return code


def run_selftest() -> int:
    """문이 실제로 걸리는지 — 정상 · 멈춤 · cap 초과 세 픽스처."""
    failures: list[str] = []

    def check(name: str, got: int, want: int) -> None:
        print(f"  [{'OK ' if got == want else 'FAIL'}] {name} — exit {got} (기대 {want})")
        if got != want:
            failures.append(name)

    def check_bool(name: str, condition: bool, detail: str = "") -> None:
        print(f"  [{'OK ' if condition else 'FAIL'}] {name}{'' if condition else f' — {detail}'}")
        if not condition:
            failures.append(name)

    with tempfile.TemporaryDirectory(prefix="nx10-watch-") as tmp:
        root = Path(tmp)

        # ① 정상: 살아 있는 프로세스(sleep) + 자라는 파일
        live = subprocess.Popen(["sleep", "300"])
        try:
            good = root / "good"
            good.mkdir()
            (good / "journal").write_bytes(b"x" * 400_000)
            watch = Watch(
                workdir=good,
                soak_started=time.time() - 600,
                duration=28800,
                interval=1,
                min_ops_per_sec=1,
                rss_limit_mb=64,
                hard_cap_mib=8192,
                max_stall=600,
                pid_pattern="sleep",
            )
            os.environ["NX10_WATCH_PID"] = str(live.pid)
            watch.samples.append(watch.take(str(live.pid)))
            # 실측에 가까운 증가율(라이브 실행 ≈150 KB/s)로 자라게 한다 — cap 8 GiB 안에 들어간다.
            (good / "journal").write_bytes(b"x" * 560_000)  # +160 KB ≈ 460 이벤트/표본
            watch.samples.append(watch.take(str(live.pid)))
            check("정상 표본은 경고 없음", watch.verdict()[0], OK)

            # ② 멈춤: 살아 있지만 쓰기·CPU 진행 없음(1표본 간격에서도 잡히게 last_write_age 를 크게)
            stalled = root / "stalled"
            stalled.mkdir()
            (stalled / "journal").write_bytes(b"y" * 1000)
            old = time.time() - 5000
            os.utime(stalled / "journal", (old, old))
            os.utime(stalled, (old, old))
            watch2 = Watch(
                workdir=stalled,
                soak_started=time.time() - 600,
                duration=28800,
                interval=1,
                min_ops_per_sec=1,
                rss_limit_mb=64,
                hard_cap_mib=8192,
                max_stall=600,
                pid_pattern="sleep",
            )
            watch2.samples.append(watch2.take(str(live.pid)))
            watch2.samples.append(watch2.take(str(live.pid)))
            check("정지한 실행은 멈춤으로 본다", watch2.verdict()[0], STALLED)

            # ③ cap 초과 투영: 증가율이 크고 cap 이 작고 남은 시간이 길다
            fast = root / "fast"
            fast.mkdir()
            (fast / "journal").write_bytes(b"z" * 1_000_000)
            watch3 = Watch(
                workdir=fast,
                soak_started=time.time() - 60,
                duration=28800,
                interval=1,
                min_ops_per_sec=133,
                rss_limit_mb=64,
                hard_cap_mib=8,  # 8 MiB
                max_stall=600,
                pid_pattern="sleep",
            )
            watch3.samples.append(watch3.take(str(live.pid)))
            (fast / "journal").write_bytes(b"z" * 8_000_000)  # +7 MB/표본 → 8시간이면 cap 초과
            watch3.samples.append(watch3.take(str(live.pid)))
            check("cap 초과 투영은 경고", watch3.verdict()[0], WARN)

            # ④ 이빨 — **작은 RSS 계단 하나를 8시간으로 증폭하지 않는다**(실측 오탐의 재현):
            #   순간 기울기 규칙이었다면 2 MB/1초 × 28,800초 = +57,600 MB 로 경보가 뗐다
            #   (2026-09-17 10:48Z 실측: 경과 29분의 1.9 MB 계단이 “8시간 외삼 +305 MB, SC-6 빨개진다”를 냈다).
            step = root / "step"
            step.mkdir()
            (step / "journal").write_bytes(b"w" * 300_000_000)
            watch4 = Watch(
                workdir=step,
                soak_started=time.time() - 1740,
                duration=28800,
                interval=1,
                min_ops_per_sec=133,
                rss_limit_mb=64,
                hard_cap_mib=8192,
                max_stall=600,
                pid_pattern="sleep",
            )
            watch4.samples.append(watch4.take(str(live.pid), rss_override=100.0))
            watch4.samples.append(watch4.take(str(live.pid), rss_override=102.0))
            watch4.baseline_rss_mb, watch4.baseline_at = 100.0, watch4.soak_started
            code4, lines4 = watch4.verdict()
            check("RSS 계단 하나를 8시간으로 증폭하지 않는다", code4, OK)
            check_bool(
                "대신 누적 평균 외삼을 문장으로 남긴다",
                any("8시간 외삼" in line for line in lines4),
                " | ".join(lines4),
            )

            # ⑤ 이빨 — 워밍업이 지난 뒤에도 **지속** 증가하면 경보해야 한다(진짜 누수를 놓치지 않는다):
            #   tail() 결함 실행은 29분에 이미 +100 MB 였다. 그 모양을 워밍업으로 넘기면 안 된다.
            now = time.time()
            sustained = Watch(
                workdir=step,
                soak_started=now - 10800,
                duration=28800,
                interval=1,
                min_ops_per_sec=133,
                rss_limit_mb=64,
                hard_cap_mib=8192,
                max_stall=600,
                pid_pattern="sleep",
            )
            sustained.samples.append(sustained.take(str(live.pid), rss_override=100.0))
            sustained.baseline_rss_mb, sustained.baseline_at = 100.0, now - 10800
            sustained.rss_series = [(now - 10800, 100.0), (now - 7200, 120.0), (now - 3600, 140.0)]
            sustained.samples.append(sustained.take(str(live.pid), rss_override=160.0))
            sustained.rss_series.append((now, 160.0))
            check("워밍업 지난 지속 증가는 경보", sustained.verdict()[0], WARN)

            # ⑥ 이빨 — 감속하면(워밍업) 경보하지 않는다: 앞 구간 +30 MB, 뒤 구간 +3 MB.
            calm = Watch(
                workdir=step,
                soak_started=now - 5400,
                duration=14400,
                interval=1,
                min_ops_per_sec=133,
                rss_limit_mb=64,
                hard_cap_mib=8192,
                max_stall=600,
                pid_pattern="sleep",
            )
            calm.samples.append(calm.take(str(live.pid), rss_override=100.0))
            calm.baseline_rss_mb, calm.baseline_at = 100.0, now - 5400
            calm.rss_series = [(now - 5400, 100.0), (now - 3600, 130.0), (now - 1800, 132.0)]
            calm.samples.append(calm.take(str(live.pid), rss_override=133.0))
            calm.rss_series.append((now, 133.0))
            check("감속 중이면 경보하지 않는다", calm.verdict()[0], OK)
        finally:
            live.terminate()
            live.wait(timeout=10)
    print(f"자기시험: {'ALL OK' if not failures else '실패 ' + str(failures)}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="돌고 있는 8시간 soak 조기 경보(읽기 전용)")
    parser.add_argument("--workdir", default=None, help="실행 작업디렉터리(기본: 최신 /tmp/nx10-soak-work-*)")
    parser.add_argument("--pid", default=None, help="감시할 pid(기본: 패턴으로 찾기)")
    parser.add_argument("--once", action="store_true", help="한 표본만")
    parser.add_argument("--samples", type=int, default=0, help="표본 수(기본: 끝날 때까지)")
    parser.add_argument("--interval", type=int, default=60, help="표본 간격(초)")
    parser.add_argument("--duration", type=int, default=28800, help="실행 전체 길이(초)")
    parser.add_argument("--json", action="store_true", help="마지막 표본을 JSON 한 줄로도 출력")
    parser.add_argument("--selftest", action="store_true", help="픽스처로 문을 확인")
    args = parser.parse_args()
    if args.selftest:
        return run_selftest()
    return run_watch(args)


if __name__ == "__main__":
    raise SystemExit(main())
