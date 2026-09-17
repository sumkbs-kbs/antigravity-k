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
# 상시 감시(`soak_watch_loop.py`)가 쌓는 표본일 — 기준선을 찾을 때 이 파일을 읽는다(같은 사실을 두 곳에 두지 않는다).
DEFAULT_HISTORY = NX10_OUT / "soak-watch-history.jsonl"

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

    def _rss_recent_rate(self, window_s: float = 1800.0) -> float | None:
        """최근 구간 RSS 증가율(MB/분). 표본이 부족하거나 진행이 없으면 None(모델을 발명하지 않는다).

        누적 평균이 아니라 **최근 구간**이 필요한 이유: SC-6 예산 판정은 “지금 이 속도가 남은 시간을
        버티는가” 를 묻는다. 시작 계단을 섮은 누적 평균은 그 질문에 답하지 못한다.
        """
        series = self.rss_series or [(s.at, s.rss_mb) for s in self.samples if s.rss_mb is not None]
        if len(series) < 3:
            return None
        end_at = series[-1][0]
        tail = [(t, v) for t, v in series if t >= end_at - window_s]
        if len(tail) < 3:
            tail = series[-3:]
        span_min = (tail[-1][0] - tail[0][0]) / 60.0
        if span_min <= 0:
            return None
        return (tail[-1][1] - tail[0][1]) / span_min

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
                    # 예산 분석 — 외삼(“이대로면 얼마가 되는가”)과 달리 **이 질문**에 답한다:
                    # “지금 속도를 남은 시간 동안 유지하면 기준을 넘는가?” 남은 예산을 남은 시간으로 나눠
                    # 허용 증가율을 내고, 그것을 실측 최근 증가율과 나란히 놓는다 — 판단을 사람의 머리
                    # 안에 두지 않는다(이 창은 손으로 나눗셈을 해서 “기준 초과 쪽”이라고 말했다).
                    # 기준의 모양도 적어 둔다: 하네스는 `ru_maxrss`(최고수위)를 50 op 마다 샘플해
                    # **마지막 − 처음을** `rss_growth_mb` 로 쓴다. 첫 표본은 SC-1~5 뒤라도
                    # 고작 ~67 MB 였다(60초 리허설 첫 표본 67.2 · 이 도구의 첫 `ps` 표본은 71.7)
                    # — 즉 시작 계단은 **기준에 포함**되고, 이 도구의 증가는 하네스 값과 같은 것을 잔다.
                    remaining_s = max(0.0, self.duration - elapsed)
                    budget_left = self.rss_limit_mb - growth
                    if remaining_s > 0 and budget_left > 0:
                        allowed_rate = budget_left / (remaining_s / 60.0)
                        recent_rate = self._rss_recent_rate()
                        lines.append(
                            f"SC-6 예산: 증가 +{growth:.1f} / 기준 {self.rss_limit_mb:.0f} MB — 남은 {_hms(remaining_s)} "
                            f"동안 허용 **+{allowed_rate:.3f} MB/분**"
                            + (
                                f" · 최근 실측 +{recent_rate:.3f} MB/분"
                                f" ({'초과 — 이 속도면 넘는다' if recent_rate > allowed_rate else '이내'})"
                                if recent_rate is not None
                                else " (최근 증가율: 표본 부족)"
                            )
                        )
                    # 두 신호를 **따로** 본다 — 서로 다른 질문이라서다:
                    #  ① 누적 평균 외삼(“지금까지의 평균이 계속되면 얼마가 되는가”) — 둔하지만 안정적
                    #  ② 예산 대 최근 증가율(“지금 이 속도가 남은 시간을 버티는가”) — 기울기 변화에 빠르다
                    # 둘 다 요구하지 않고 **하나라도 서면** 경보하되, 워밍업·감속은 위와 같이 봐준다.
                    signals: list[str] = []
                    if projected_growth > self.rss_limit_mb:
                        signals.append(f"누적 평균 외삼 +{projected_growth:.0f} MB > 기준 {self.rss_limit_mb:.0f} MB")
                    recent_now = self._rss_recent_rate()
                    if remaining_s > 0 and budget_left > 0 and recent_now is not None and recent_now > allowed_rate:
                        signals.append(
                            f"최근 실측 +{recent_now:.3f} MB/분 > 허용 +{allowed_rate:.3f} MB/분"
                            f"(증가 +{growth:.1f} / 기준 {self.rss_limit_mb:.0f} MB · 남은 {_hms(remaining_s)})"
                        )
                    if elapsed < warmup:
                        if signals:
                            lines.append(
                                f"({' · '.join(signals)}) — 다만 실행 {_hms(elapsed)} 는 워밍업 "
                                f"{_hms(warmup)}(실행 25%) 보다 짧다: 경보하지 않고 기다린다"
                            )
                    elif decelerating:
                        if signals:
                            lines.append(
                                f"({' · '.join(signals)}) — 다만 **감속 중**이다(최근 구간 증가율이 앞 구간의 "
                                "절반 미만). 워밍업으로 보고 경보하지 않는다"
                            )
                    elif signals:
                        warns.append(
                            "SC-6 추세 — "
                            + " · ".join(signals)
                            + " — 워밍업도 지나고 감속도 아니다. 이 추세가 유지되면 SC-6 가 빨개진다"
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


def seed_baseline(watch: Watch, override_mb: float | None, history: Path | None = None) -> str:
    """RSS 기준선을 **실행 첫 표본**에 맞춘다(돌아온 문장은 사람에게 이유를 밝힌다).

    왜 필요한가: 기준선이 “이 호출의 첫 표본”이면 `--once` 의 증가는 항상 0 이고, SC-6 예산도 안 나온다
    (실측 2026-09-17: 한 표본만 묻던 도구가 경과·저널 크기만 보여 주고 “정상”이라고 말했다).
    기준선의 근거 순서: ① 호출자가 준 값(하네스 첫 표본을 알 때) ② 감시 루프가 쌓은 이력의 **같은 pid**
    첫 표본(실행 시작 기준선) ③ 둘 다 없으면 이 호출의 첫 표본 — 그리고 그 사실을 문장으로 적는다.
    """
    if override_mb is not None:
        watch.baseline_rss_mb = override_mb
        watch.baseline_at = watch.soak_started
        return f"RSS 기준선 {override_mb:.1f} MB(호출자가 준 값) — 이 값이 하네스 첫 표본이면 증가는 SC-6 와 같다"
    path = history or DEFAULT_HISTORY
    if path.is_file():
        current_pid = watch.samples[-1].pid if watch.samples else None
        rows: list[tuple[float, float]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("rss_mb") is None or (current_pid is not None and row.get("pid") != current_pid):
                continue
            rows.append((float(row["at"]), float(row["rss_mb"])))
        if rows:
            rows.sort()
            watch.baseline_rss_mb, watch.baseline_at = rows[0][1], rows[0][0]
            watch.rss_series = rows
            return (
                f"RSS 기준선 {rows[0][1]:.1f} MB = 이 실행(pid {current_pid})의 첫 표본 — "
                f"{path.name} 에서 읽었다(증가율·SC-6 예산의 기준)"
            )
    if watch.samples and watch.samples[0].rss_mb is not None:
        watch.baseline_rss_mb, watch.baseline_at = watch.samples[0].rss_mb, watch.samples[0].at
    return (
        "RSS 기준선이 이 호출의 첫 표본이다(실행 시작 기준선 아님) — 실행 시작부터의 증가·SC-6 예산은 "
        "`--rss-baseline-mb` 로 주거나 감시 루프(`soak_watch_loop.py`)를 쓴다"
    )


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
    # `--once` 는 **표본 두 개**를 뜻한다: 분석(증가율·cap 투영·SC-6 예산)은 두 점이 있어야 성립하고,
    # 한 점만 찍으면 운영자가 가장 자주 묻는 이 명령이 **위험을 침묵**한다(실측 2026-09-17: `--once` 가
    # 경과·저널 크기만 보여 주고 “정상”이라고 말했다 — 그 출력에는 증가율도 예산도 없었다).
    total = 2 if args.once else max(1, args.samples)
    interval = 1 if args.once else watch.interval
    code = OK
    for index in range(total):
        if index:
            time.sleep(interval)
        watch.samples.append(watch.take(args.pid))
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if index == 0:
            print(f"  [{stamp}] {seed_baseline(watch, args.rss_baseline_mb)}")
        code, lines = watch.verdict()
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

            # ⑦ 이빨 — **예산 분석**: “지금 속도를 남은 시간 유지하면 넘는가”.
            #   근거의 모양은 하네스 지표다(ru_maxrss 최고수위 · 마지막 − 처음 · 50 op 마다 샘플).
            #   실행 4시간 · 증가 +40/기준 64 MB → 남은 4시간에 허용 +0.100 MB/분.
            budget = Watch(
                workdir=step,
                soak_started=now - 14400,
                duration=28800,
                interval=1,
                min_ops_per_sec=133,
                rss_limit_mb=64,
                hard_cap_mib=8192,
                max_stall=600,
                pid_pattern="sleep",
            )
            budget.baseline_rss_mb, budget.baseline_at = 100.0, now - 14400
            budget.rss_series = [(now - 14400, 100.0), (now - 9000, 108.0), (now - 3600, 118.0)]
            budget.samples.append(budget.take(str(live.pid), rss_override=100.0))
            budget.samples.append(budget.take(str(live.pid), rss_override=120.0))
            budget.rss_series.append((now, 120.0))
            code7, lines7 = budget.verdict()
            # 증가 +20 / 기준 64 → 남은 4시간에 허용 (64−20)/240분 = +0.183 MB/분.
            check_bool(
                "허용 증가율을 숫자로 내놓는다",
                any("동안 허용 **+0.183 MB/분**" in line for line in lines7),
                " | ".join(lines7),
            )
            check("한계 안이면 경보하지 않는다", code7, OK)

            # ⑧ 이빨 — 단 시작 계단은 **기준에 포함**된다: 60초 리허설의 증가는 이미 +21.2 MB 였다.
            #   그러면 예산은 43 MB 뿐이고 허용 증가율이 급격히 좁아진다(같은 +30 MB 라도 넘는다).
            tight = Watch(
                workdir=step,
                soak_started=now - 14400,
                duration=28800,
                interval=1,
                min_ops_per_sec=133,
                rss_limit_mb=64,
                hard_cap_mib=8192,
                max_stall=600,
                pid_pattern="sleep",
            )
            tight.baseline_rss_mb, tight.baseline_at = 100.0, now - 14400
            # 누적 평균으로는 한계 안(증가 +20 × 2 = 외삼 +40 < 64)인데 **최근 기울기는 가파르다** —
            # 이 경우가 예산 신호가 필요한 이유다(누적 평균은 기울기 변화에 둔하다).
            tight.rss_series = [(now - 14400, 100.0), (now - 1700, 115.0), (now - 800, 118.0)]
            tight.samples.append(tight.take(str(live.pid), rss_override=100.0))
            tight.samples.append(tight.take(str(live.pid), rss_override=125.0))
            tight.rss_series.append((now, 125.0))
            code8, lines8 = tight.verdict()
            check("워밍업 뒤 가파른 최근 기울기는 예산 초과로 경보", code8, WARN)
            check_bool(
                "경보가 두 숫자(실측·허용)를 같이 든다",
                any("SC-6 추세" in line and "최근 실측" in line and "허용" in line for line in lines8),
                " | ".join(lines8),
            )
            check_bool(
                "외삼이 한계 안이라는 사실도 같이 밝힌다(조용히 넘기지 않는다)",
                any("외삼 +50 MB <" in line for line in lines8),
                " | ".join(lines8),
            )

            # ⑨ 이빨 — 워밍업(실행 25% 전)에는 **예산 수치만 정보로 남기고 경보는 보류**한다.
            early = Watch(
                workdir=step,
                soak_started=now - 2700,
                duration=28800,
                interval=1,
                min_ops_per_sec=133,
                rss_limit_mb=64,
                hard_cap_mib=8192,
                max_stall=600,
                pid_pattern="sleep",
            )
            early.baseline_rss_mb, early.baseline_at = 100.0, now - 2700
            early.rss_series = [(now - 2700, 100.0), (now - 1800, 120.0), (now - 600, 131.0)]
            early.samples.append(early.take(str(live.pid), rss_override=100.0))
            early.samples.append(early.take(str(live.pid), rss_override=133.0))
            early.rss_series.append((now, 133.0))
            code9, lines9 = early.verdict()
            check("워밍업 중에는 예산 초과율이어도 경보하지 않는다", code9, OK)
            check_bool(
                "대신 예산·허용율을 문장으로 남긴다",
                any("SC-6 예산:" in line and "허용" in line for line in lines9)
                and any("워밍업" in line for line in lines9),
                " | ".join(lines9),
            )

            # ⑩ 이빨 — **기준선의 출처**. 기준선이 “이 호출의 첫 표본”이면 증가는 항상 0 이고
            #   예산도 안 나온다(실측 2026-09-17: 한 표본만 묻는 명령이 경과·저널만 보여 주고 “정상” 이라 했다).
            hist = step / "history.jsonl"
            hist.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in (
                        {"at": now - 3600, "pid": 111, "rss_mb": 70.0, "journal_mb": 10.0},
                        {"at": now - 1800, "pid": 111, "rss_mb": 80.0, "journal_mb": 20.0},
                        {"at": now - 60, "pid": 222, "rss_mb": 300.0, "journal_mb": 30.0},
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            seeded = Watch(
                workdir=step,
                soak_started=now - 3600,
                duration=28800,
                interval=1,
                min_ops_per_sec=133,
                rss_limit_mb=64,
                hard_cap_mib=8192,
                max_stall=600,
                pid_pattern="sleep",
            )
            seeded.samples.append(seeded.take("111", rss_override=90.0))
            note = seed_baseline(seeded, None, hist)
            check_bool(
                "기준선을 **같은 pid** 의 첫 표본으로 잡는다",
                seeded.baseline_rss_mb == 70.0 and "첫 표본" in note,
                f"baseline={seeded.baseline_rss_mb} note={note}",
            )
            check_bool(
                "다른 pid 의 표본은 섞지 않는다",
                all(v != 300.0 for _, v in seeded.rss_series),
                str(seeded.rss_series),
            )
            override_note = seed_baseline(seeded, 66.8, hist)
            check_bool(
                "호출자가 준 값이 이력보다 우선한다",
                seeded.baseline_rss_mb == 66.8 and "호출자가 준 값" in override_note,
                f"baseline={seeded.baseline_rss_mb} note={override_note}",
            )
            check_bool(
                "근거가 없으면 없다고 말한다",
                "이 호출의 첫 표본" in seed_baseline(seeded, None, step / "none.jsonl"),
                "기준선 출처를 밝히지 않았다",
            )
        finally:
            live.terminate()
            live.wait(timeout=10)
    print(f"자기시험: {'ALL OK' if not failures else '실패 ' + str(failures)}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="돌고 있는 8시간 soak 조기 경보(읽기 전용)")
    parser.add_argument("--workdir", default=None, help="실행 작업디렉터리(기본: 최신 /tmp/nx10-soak-work-*)")
    parser.add_argument("--pid", default=None, help="감시할 pid(기본: 패턴으로 찾기)")
    parser.add_argument("--once", action="store_true", help="지금 한 번 판정(내부적으로 1초 간격 두 표본)")
    parser.add_argument("--samples", type=int, default=0, help="표본 수(기본: 끝날 때까지)")
    parser.add_argument("--interval", type=int, default=60, help="표본 간격(초)")
    parser.add_argument("--duration", type=int, default=28800, help="실행 전체 길이(초)")
    parser.add_argument(
        "--rss-baseline-mb",
        type=float,
        default=float(os.environ.get("NX10_WATCH_RSS_BASELINE_MB") or 0) or None,
        help="RSS 기준선(하네스 첫 표본을 알 때 — 모르면 감시 이력의 첫 표본을 쓴다)",
    )
    parser.add_argument("--json", action="store_true", help="마지막 표본을 JSON 한 줄로도 출력")
    parser.add_argument("--selftest", action="store_true", help="픽스처로 문을 확인")
    args = parser.parse_args()
    if args.selftest:
        return run_selftest()
    return run_watch(args)


if __name__ == "__main__":
    raise SystemExit(main())
