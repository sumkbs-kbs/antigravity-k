"""soak 감시를 **상시 실행**으로 붙이고, 추세를 한눈에 보는 **자체 완결 HTML** 을 계속 다시 쓴다.

`soak_watch.py` 는 “지금 한 표본” 을 묻는 도구다. 이 파일은 그 표본을 **주기적으로 쌓아**
(`soak-watch-history.jsonl`) 추세를 그리고, 페이지가 스스로 새로고침하는 HTML(`soak-watch-live.html`)
을 갱신한다 — 서버 없이도 브라우저/Preview 탭에서 열린다(외부 자산 0, 인라인 SVG).

    # 상시 실행(프로젝트 방식대로 screen)
    screen -dmS nx10watch caffeinate -i bash -c \
      'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/qa/2026-09-16-followup/nx10/soak_watch_loop.py \
         >> docs/qa/2026-09-16-followup/nx10/soak-watch-loop.log 2>&1'

    # 한 번만: 표본 1개 기록 + HTML 갱신(다른 도구/훅에서 호출하기 좋다)
    … soak_watch_loop.py --once
    # 픽스처로 그림·문구가 실제로 바뀌는지
    … soak_watch_loop.py --selftest

exit: 0 정상 종료(실행이 끝남/표본 소진) · 2 경고가 있었음 · 6 멈춤을 봤음

설계 원칙(이 창이 계속 지킨 것):
* **읽기 전용**: 저널을 읽지 않고 `stat`/`ps` 만 쓴다(측정 간섭 최소).
* **판정은 회수 도구가 한다**: 이 화면은 경보이고, 최종 판정은 `collect_soak_result.py` 다.
* **추세를 정직하게**: 처리량은 바이트에서 **추정**한다(상수 `B_PER_EVENT`). 라벨에 “추정”을 붙인다.
* **그림도 시험한다**: `--selftest` 가 픽스처 3종(정상·경고·멈춤)으로 배지·색·문구가 실제로 바뀌는지 본다.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import soak_watch  # noqa: E402  (같은 디렉터리의 표본기 — 판정 규칙을 복제하지 않는다)

# 파생물(이력·화면)은 **카드 레인의 디렉터리**에 둔다 — 도구가 `scripts/` 로 승격돼도 증거는 한 곳에
# 모이고, 그 디렉터리의 `.gitignore` 가 이 파생물을 제외한다(도구 위치와 증거 위치는 다를 수 있다).
DEFAULT_HISTORY = soak_watch.NX10_OUT / "soak-watch-history.jsonl"
DEFAULT_HTML = soak_watch.NX10_OUT / "soak-watch-live.html"
BADGE = {
    soak_watch.OK: ("정상", "#1a7f37", "#e6f4ea"),
    soak_watch.WARN: ("경고", "#9a6700", "#fff8e1"),
    soak_watch.STALLED: ("멈춤", "#b42318", "#fde8e8"),
    soak_watch.NO_RUN: ("실행 없음", "#57606a", "#eef1f4"),
}


def _hms(seconds: float) -> str:
    seconds = int(max(0, seconds))
    return f"{seconds // 3600:d}시간 {(seconds % 3600) // 60:02d}분"


def sample_to_row(sample: soak_watch.Sample, soak_started: float, workdir: object = None) -> dict[str, object]:
    return {
        "workdir": None if workdir is None else str(workdir),
        "at": round(sample.at, 1),
        "elapsed_s": round(max(0.0, sample.at - soak_started), 1),
        "pid": sample.pid,
        "alive": sample.alive,
        "cpu_s": sample.cpu_seconds,
        "rss_mb": sample.rss_mb,
        "journal_mb": None if sample.journal_bytes is None else round(sample.journal_bytes / 1048576, 1),
        "last_write_age_s": sample.last_write_age_s,
    }


def split_rows_by_pid(
    rows: list[dict[str, object]], pid: int | None
) -> tuple[list[dict[str, object]], dict[object, list[dict[str, object]]]]:
    """(이번 실행의 표본, 다른 실행의 표본들).

    왜 pid 로 가르는가: 새 실행이 시작되면 journal 은 **0 에서 자라므로**, 이전 실행의 꼬리를 같은 선에
    이어 그리면 화면이 “journal 이 861.8 MiB → 1.4 MiB 로 줄었다” 처럼 **사실이 아닌 급강하**를 보여 준다
    (2026-09-17 4차 시작 직후 실측 — 그대로 두면 다음 사람이 “보존이 돌았나?” 를 먼저 의심하게 된다).
    그래서 표본 묶음은 **실행(pid) 단위**다. pid 를 모르면(실행 없음) 가르지 않는다 — 빈손으로 단정하지 않는다.
    """
    if pid is None:
        return list(rows), {}
    mine: list[dict[str, object]] = []
    others: dict[object, list[dict[str, object]]] = {}
    for row in rows:
        if row.get("pid") == pid:
            mine.append(row)
        else:
            others.setdefault(row.get("pid"), []).append(row)
    return mine, others


def _seed_state(watch: soak_watch.Watch, rows: list[dict[str, object]]) -> None:
    """RSS 기준선을 **그 실행의 첫 표본**에 고정한다(감시를 재시작해도 “실행 시작 이후”가 0 으로 안 돌아간다)."""
    watch.rss_series = [(float(row["at"]), float(row["rss_mb"])) for row in rows if row.get("rss_mb") is not None]  # type: ignore[arg-type]
    if watch.rss_series:
        watch.baseline_rss_mb = watch.rss_series[0][1]
        watch.baseline_at = watch.rss_series[0][0]


def _polyline(values: list[float | None], *, width: int, height: int, pad: int = 8) -> tuple[str, float, float]:
    """(points, 최소, 최대) — None 은 선에서 빠진다(빈 표본을 0 으로 그리지 않는다)."""
    numbers = [v for v in values if v is not None]
    if len(numbers) < 2:
        return "", 0.0, 0.0
    low, high = min(numbers), max(numbers)
    span = high - low or 1.0
    usable = max(1, len(values) - 1)
    points = []
    for index, value in enumerate(values):
        if value is None:
            continue
        x = pad + (width - 2 * pad) * index / usable
        y = height - pad - (height - 2 * pad) * (value - low) / span
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points), low, high


def _chart(title: str, values: list[float | None], *, unit: str, color: str) -> str:
    width, height = 640, 120
    points, low, high = _polyline(values, width=width, height=height)
    body = (
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" />'
        if points
        else '<text x="8" y="60" fill="#8b949e" font-size="12">표본이 아직 부족하다</text>'
    )
    return f"""
      <figure style="margin:0 0 18px 0">
        <figcaption style="font-size:13px;color:#57606a;margin-bottom:4px">
          {html.escape(title)} <span style="color:#8b949e">— 최근 {len(values)}표본 · 범위 {low:.1f}~{high:.1f} {unit}</span>
        </figcaption>
        <svg viewBox="0 0 {width} {height}" width="100%" height="{height}"
             style="background:#fff;border:1px solid #d8dee4;border-radius:8px">{body}</svg>
      </figure>"""


def _derive_meta(meta: dict[str, object], lines: list[str]) -> dict[str, object]:
    """판정 줄에서 화면에 올릴 값을 뽑는다 — 루프와 자기시험이 **같은 경로**를 쓰게 한다."""
    derived = dict(meta)
    derived.setdefault("warning_text", "")
    for line in lines:
        if line.startswith("경고:") and not derived["warning_text"]:
            derived["warning_text"] = line
        if "cap 여유" in line and "/" in line:
            try:
                derived["cap_projection_mib"] = line.split("종료 시 추정")[1].split("MiB")[0].strip()
            except IndexError:
                pass
    return derived


def render_html(rows: list[dict[str, object]], code: int, lines: list[str], meta: dict[str, object]) -> str:
    meta = _derive_meta(meta, lines)
    label, fg, bg = BADGE.get(code, ("알 수 없음", "#57606a", "#eef1f4"))
    journal = [row.get("journal_mb") for row in rows]  # type: ignore[list-item]
    rss = [row.get("rss_mb") for row in rows]  # type: ignore[list-item]
    ops: list[float | None] = []
    for index, row in enumerate(rows):
        if index == 0:
            continue
        previous = rows[index - 1]
        delta = (row.get("journal_mb") or 0) - (previous.get("journal_mb") or 0)
        span = max(1.0, float(row["at"]) - float(previous["at"]))  # type: ignore[arg-type]
        ops.append(delta * 1048576 / soak_watch.B_PER_EVENT / span)
    latest = rows[-1] if rows else {}

    def _cell(value: object, digits: int) -> str:
        return "" if value is None else f"{float(value):.{digits}f}"  # type: ignore[arg-type]

    def _bar(title: str, used: float | None, limit: float | None, unit: str, warn_color: str = "#b42318") -> str:
        """기준 대비 사용률 — 선그래프가 못 보여 주는 “기준까지 얼마나 남았나”를 보여 준다."""
        if used is None or not limit:
            return ""
        ratio = max(0.0, min(1.0, used / limit))
        color = "#1a7f37" if ratio < 0.6 else ("#9a6700" if ratio < 0.9 else warn_color)
        return (
            f'<div style="margin:0 0 12px 0">'
            f'<div style="font-size:12px;color:#57606a;margin-bottom:3px">{html.escape(title)}</div>'
            f'<div style="background:#eef1f4;border-radius:6px;height:10px;overflow:hidden">'
            f'<div data-bar="{html.escape(title)}" style="width:{ratio * 100:.1f}%;height:10px;background:{color}"></div></div>'
            f'<div style="font-size:11px;color:#8b949e;margin-top:2px">{used:,.1f} / {limit:,.0f} {unit} ({ratio * 100:.1f}%)</div>'
            "</div>"
        )

    cap_used = None if not latest.get("journal_mb") else float(latest["journal_mb"])  # type: ignore[arg-type]
    rss_growth = None
    if len(rows) >= 2 and rows[0].get("rss_mb") is not None and latest.get("rss_mb") is not None:
        rss_growth = float(latest["rss_mb"]) - float(rows[0]["rss_mb"])  # type: ignore[arg-type]
    bars = _bar("journal 사용량 vs 보존 cap", cap_used, float(meta.get("hard_cap_mib") or 0), "MiB") + _bar(
        "RSS 증가 vs SC-6 기준", rss_growth, float(meta.get("rss_limit_mb") or 0), "MB"
    )
    rows_html = "\n".join(
        "<tr>"
        + f"<td>{time.strftime('%H:%M:%S', time.localtime(float(row['at'])))}</td>"
        + f"<td>{_hms(float(row['elapsed_s']))}</td>"
        + f"<td>{_cell(row.get('rss_mb'), 0)}</td>"
        + f"<td>{_cell(row.get('journal_mb'), 1)}</td>"
        + f"<td>{_cell(row.get('last_write_age_s'), 0)}</td>"
        + "</tr>"
        for row in rows[-30:][::-1]
    )
    detail = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
    cap = meta.get("hard_cap_mib")
    projection = meta.get("cap_projection_mib")
    warning_banner = meta.get("warning_text") or ""
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="{int(meta.get("refresh_seconds", 30))}">
<title>NX-10 soak 라이브 ({html.escape(label)})</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:16px;color:#1f2328;background:#fbfcfd">
  <header style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
    <span data-badge="status" style="white-space:nowrap;background:{bg};color:{fg};border:1px solid {fg}33;padding:4px 10px;border-radius:999px;font-weight:700">{html.escape(label)}</span>
    <h1 style="font-size:16px;margin:0">8시간 soak 라이브 감시 — {html.escape(str(meta.get("workdir", "")))}</h1>
  </header>
  <p style="font-size:13px;color:#57606a;margin:0 0 12px 0">
    표본 {len(rows)}개 · 갱신 {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}
    · 실행 경과 {_hms(float(latest.get("elapsed_s") or 0))} / {_hms(float(meta.get("duration", 28800)))}
    · 기준 처리량 {float(meta.get("min_ops_per_sec", 133)):.0f} ops/s
    · RSS 기준 {float(meta.get("rss_limit_mb", 64)):.0f} MB · cap {cap} MiB
    {f"· 종료 시 cap 추정 {projection} MiB" if projection else ""}
  </p>
  {f'<p data-banner="warning" style="background:#fff8e1;border:1px solid #9a670033;padding:8px 10px;border-radius:8px;font-size:13px">{html.escape(str(warning_banner))}</p>' if warning_banner else ""}
  {bars}
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px">
    <section>
      {_chart("journal 크기 (MiB)", journal, unit="MiB", color="#0969da")}
      {_chart("RSS (MB)", rss, unit="MB", color="#8250df")}
      {_chart("추정 처리량 (ops/s, 바이트 기반 추정)", ops, unit="ops/s", color="#1a7f37")}
    </section>
    <section>
      <h2 style="font-size:14px;margin:0 0 6px 0">최근 표본(위가 최신)</h2>
      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead><tr style="text-align:left;color:#57606a">
          <th style="border-bottom:1px solid #d8dee4;padding:4px">시각</th>
          <th style="border-bottom:1px solid #d8dee4;padding:4px">경과</th>
          <th style="border-bottom:1px solid #d8dee4;padding:4px">RSS MB</th>
          <th style="border-bottom:1px solid #d8dee4;padding:4px">journal MiB</th>
          <th style="border-bottom:1px solid #d8dee4;padding:4px">쓰기 지연 s</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <h2 style="font-size:14px;margin:12px 0 6px 0">지금 판정 근거</h2>
      <ul style="font-size:12px;color:#57606a;margin:0;padding-left:18px">{detail}</ul>
    </section>
  </div>
  <p style="font-size:11px;color:#8b949e;margin-top:16px">
    이 화면은 경보이고 <b>판정이 아니다</b> — 최종 판정은 실행이 끝난 뒤
    <code>soak_control.sh harvest</code> → <code>scripts/collect_soak_result.py</code> 가 한다.
    처리량은 journal 바이트에서 추정한다(상수 {soak_watch.B_PER_EVENT} B/이벤트).
  </p>
</body></html>"""


def _write_view(
    rows: list[dict[str, object]], code: int, lines: list[str], watch: soak_watch.Watch, html_path: Path
) -> None:
    meta: dict[str, object] = {
        "workdir": str(watch.workdir),
        "duration": watch.duration,
        "min_ops_per_sec": watch.min_ops_per_sec,
        "rss_limit_mb": watch.rss_limit_mb,
        "hard_cap_mib": int(watch.hard_cap_mib),
        "refresh_seconds": 30,
    }
    html_path.write_text(render_html(rows, code, lines, meta), encoding="utf-8")


def run_loop(args: argparse.Namespace) -> int:
    watch = soak_watch._make_watch(args)
    if watch is None:
        print("실행 작업디렉터리를 찾지 못했다 — `--workdir` 로 지정한다")
        return soak_watch.NO_RUN
    history = Path(args.history)
    html_path = Path(args.out_html)
    rows: list[dict[str, object]] = []
    if history.is_file():
        for line in history.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    code = soak_watch.OK
    sample_budget = 1 if args.once else args.samples
    index = 0
    seen_run = False
    while True:
        if index:
            time.sleep(watch.interval)
        sample = watch.take(args.pid)
        watch.samples.append(sample)
        if not seen_run:
            seen_run = True
            rows, others = split_rows_by_pid(rows, sample.pid)
            for old_pid, stale in others.items():
                archive = history.with_name(f"{history.stem}-pid{old_pid}{history.suffix}")
                archive.write_text(
                    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in stale), encoding="utf-8"
                )
                print(
                    f"  이전 실행(pid {old_pid})의 표본 {len(stale)}개를 {archive.name} 으로 옮겼다 — 같은 추세선에 잇지 않는다"
                )
            _seed_state(watch, rows)
            if rows:
                history.write_text(
                    "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
                )
        code, lines = watch.verdict()
        rows.append(sample_to_row(sample, watch.soak_started, watch.workdir))
        if sample.rss_mb is not None:
            watch.rss_series.append((sample.at, sample.rss_mb))
        with history.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
        _write_view(rows[-400:], code, lines, watch, html_path)
        stamp = time.strftime("%H:%M:%S", time.localtime())
        print(f"  [{stamp}] {lines[0] if lines else ''}")
        for line in lines[1:]:
            print(f"  [{stamp}] {line}")
        index += 1
        if sample_budget and index >= sample_budget:
            break
        if code == soak_watch.NO_RUN:
            print("  실행이 사라졌다 — 감시를 끝낸다(화면은 마지막 상태를 유지한다)")
            break
        if watch.duration and (sample.at - watch.soak_started) > watch.duration + watch.interval * 2:
            print("  실행 시간을 넘겼다 — 감시를 끝낸다")
            break
    print(f"판정: {'정지 감시 완료' if code == soak_watch.STALLED else ('정상' if code == soak_watch.OK else '경고')}")
    return code


def run_selftest() -> int:
    """그림과 문구가 **픽스처에 따라 실제로 달라지는지** — 정상·경고·멈춤 3종."""
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        print(f"  [{'OK ' if condition else 'FAIL'}] {name}{'' if condition else f' — {detail}'}")
        if not condition:
            failures.append(name)

    def rows_series(step_mb: float, count: int = 4, rss_step: float = 1.0) -> list[dict[str, object]]:
        base = time.time() - count * 60
        return [
            {
                "at": base + i * 60,
                "elapsed_s": i * 60,
                "pid": 1,
                "alive": True,
                "cpu_s": float(i * 40),
                "rss_mb": 100.0 + i * rss_step,
                "journal_mb": 200.0 + i * step_mb,
                "last_write_age_s": 0.0,
            }
            for i in range(count)
        ]

    ok_html = render_html(
        rows_series(9.0),
        soak_watch.OK,
        ["pid 1 · 실행 경과 0시간 03분 / 8시간 00분 · RSS 103 MB · journal 227.0 MiB · 마지막 쓰기 0s 전"],
        {"workdir": "/tmp/fixture", "hard_cap_mib": 8192, "duration": 28800},
    )
    check("정상 배지", 'data-badge="status"' in ok_html and "정상" in ok_html)
    check("정상에는 경고 배너가 없다", 'data-banner="warning"' not in ok_html)
    check("추세 그림에 폴리라인이 그려진다", ok_html.count("<polyline") >= 3, f"{ok_html.count('<polyline')}개")

    warn_lines = [
        "pid 1 · 실행 경과 0시간 05분 / 8시간 00분 · RSS 103 MB · journal 400.0 MiB · 마지막 쓰기 0s 전",
        "cap 여유: 종료 시 추정 6396 MiB / cap 8192 MiB",
        "경고: 보존 cap 위험: 증가율대로면 종료 시 9000 MiB > hard cap 8192 MiB — 넘긴 뒤의 쓰기 거절(507)은 하네스가 `errors` 로 세므로 설정 때문의 거짓 FAIL 이 된다",
    ]
    warn_html = render_html(
        rows_series(60.0),
        soak_watch.WARN,
        warn_lines,
        {"workdir": "/tmp/fixture", "hard_cap_mib": 8192, "duration": 28800},
    )
    check("경고 배지와 배너", "경고" in warn_html and 'data-banner="warning"' in warn_html)
    check("cap 추정이 화면에 실린다", "종료 시 cap 추정 6396 MiB" in warn_html, "투영 문구 누락")
    check(
        "읽기 표면이 실행 없음/멈춤에서 다르다",
        "멈춤"
        in render_html(
            rows_series(0.0), soak_watch.STALLED, ["멈춤: 5000s 동안 진행 없음"], {"workdir": "/tmp/fixture"}
        ),
    )
    check(
        "표본이 1개면 선을 그리지 않는다",
        "<polyline" not in render_html(rows_series(9.0, count=1), soak_watch.OK, [], {"workdir": "/tmp/fixture"}),
    )

    bars_html = render_html(
        rows_series(9.0), soak_watch.OK, [], {"workdir": "/tmp/fixture", "hard_cap_mib": 8192, "rss_limit_mb": 64}
    )
    check("기준 대비 막대가 그려진다", bars_html.count("data-bar=") == 2, f"{bars_html.count('data-bar=')}개")
    check(
        "RSS 증가가 기준을 넘으면 막대가 빨개진다",
        "#b42318"
        in render_html(
            rows_series(9.0, rss_step=80.0),
            soak_watch.WARN,
            [],
            {"workdir": "/tmp/fixture", "hard_cap_mib": 8192, "rss_limit_mb": 64},
        ),
    )

    # ── 실행 정체성(pid)으로 표본을 가르는가 — 이빨 포함 ─────────────────────────────────
    mixed = [dict(row, pid=pid) for pid, row in ((11, r) for r in rows_series(9.0, count=2))]
    mixed += [dict(row, pid=22) for row in rows_series(9.0, count=3)]
    mine, others = split_rows_by_pid(mixed, 22)
    check("이번 실행(pid 22) 표본만 남는다", len(mine) == 3 and all(r["pid"] == 22 for r in mine))
    check("이전 실행(pid 11) 표본은 따로 모인다", sorted(others) == [11] and len(others[11]) == 2)
    check(
        "가르면서 표본을 잃지 않는다",
        len(mine) + sum(len(v) for v in others.values()) == len(mixed),
        "나눈 합이 원본과 다르다",
    )
    check("pid 를 모르면 가르지 않는다(빈손으로 단정 금지)", split_rows_by_pid(mixed, None) == (mixed, {}))
    # 이 관측이 이 규칙의 이유다: 이전 실행(861.8 MiB)과 새 실행(1.4 MiB)을 섞어 그리면 화면에
    # 존재하지 않는 **급강하**가 생긴다(실제 4차 시작 직후에 보인 것). 갈라 두면 사라진다.
    hot = [dict(row, pid=11, journal_mb=861.8) for row in rows_series(9.0, count=3)]
    cold = [dict(row, pid=22, journal_mb=1.4) for row in rows_series(0.0, count=3)]
    mixed_html = render_html(hot + cold, soak_watch.OK, [], {"workdir": "/tmp/fixture"})
    split_html = render_html(split_rows_by_pid(hot + cold, 22)[0], soak_watch.OK, [], {"workdir": "/tmp/fixture"})
    check(
        "섞인 이력은 급강하로 그려지고, 가른 이력은 그렇지 않다",
        "861.8 MiB" in mixed_html and "861.8 MiB" not in split_html,
        "급강하 재현/제거가 확인되지 않았다",
    )

    print(f"자기시험: {'ALL OK' if not failures else '실패 ' + str(failures)}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="soak 상시 감시 + 라이브 추세 화면")
    parser.add_argument("--workdir", default=None)
    parser.add_argument("--pid", default=None)
    parser.add_argument("--once", action="store_true", help="표본 1개만 기록하고 화면을 갱신")
    parser.add_argument("--samples", type=int, default=0, help="표본 수(기본: 실행이 끝날 때까지)")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--duration", type=int, default=28800)
    parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    parser.add_argument("--out-html", default=str(DEFAULT_HTML))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return run_selftest()
    return run_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
