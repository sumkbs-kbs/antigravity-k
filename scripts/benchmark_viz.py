#!/usr/bin/env python3
"""Freebuff-Style Proactive Pipeline — 벤치마크 결과 시각화 대시보드.

JSON 벤치마크 결과를 읽어 matplotlib 기반 차트를 생성합니다.

생성 차트:
  1. 개요 대시보드 — 스테이지별 Latency 비교 (막대 + P95 에러바)
  2. 스테이지별 Latency Trend — 반복 횟수별 지연시간 변동
  3. 스테이지별 세부 분석 — 서브 컴포넌트별 Latency Breakdown
  4. 통계 히트맵 — 스테이지별 통계 요약
  5. 서브 컴포넌트 그룹 비교 — 모든 스테이지의 주요 서브 항목 비교

사용법:
  python scripts/benchmark_viz.py benchmark_results.json [--output-dir ./charts] [--format png]
  python scripts/benchmark_viz.py benchmark_results.json --format svg
  python scripts/benchmark_viz.py benchmark_results.json --show    # GUI로 표시
"""

import argparse
import importlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Protocol, TypedDict, cast


class _Axis(Protocol):
    def set_major_formatter(self, formatter: object) -> None: ...


class _Bar(Protocol):
    def get_height(self) -> float: ...

    def get_width(self) -> float: ...

    def get_x(self) -> float: ...

    def get_y(self) -> float: ...


class _Cell(Protocol):
    def set_facecolor(self, color: str) -> None: ...

    def set_text_props(self, **kwargs: object) -> None: ...


class _Table(Protocol):
    def auto_set_font_size(self, value: bool) -> None: ...

    def get_celld(self) -> Mapping[tuple[int, int], _Cell]: ...

    def scale(self, x: float, y: float) -> None: ...

    def set_fontsize(self, size: float) -> None: ...


class _Axes(Protocol):
    xaxis: _Axis
    yaxis: _Axis

    def annotate(self, *args: object, **kwargs: object) -> None: ...

    def axhline(self, *args: object, **kwargs: object) -> None: ...

    def axis(self, *args: object, **kwargs: object) -> None: ...

    def bar(self, *args: object, **kwargs: object) -> Sequence[_Bar]: ...

    def barh(self, *args: object, **kwargs: object) -> Sequence[_Bar]: ...

    def errorbar(self, *args: object, **kwargs: object) -> None: ...

    def fill_between(self, *args: object, **kwargs: object) -> None: ...

    def imshow(self, *args: object, **kwargs: object) -> object: ...

    def legend(self, *args: object, **kwargs: object) -> None: ...

    def margins(self, *args: object, **kwargs: object) -> None: ...

    def plot(self, *args: object, **kwargs: object) -> None: ...

    def scatter(self, *args: object, **kwargs: object) -> None: ...

    def set_title(self, *args: object, **kwargs: object) -> None: ...

    def set_xlabel(self, *args: object, **kwargs: object) -> None: ...

    def set_ylabel(self, *args: object, **kwargs: object) -> None: ...

    def set_xticklabels(self, *args: object, **kwargs: object) -> None: ...

    def set_xticks(self, *args: object, **kwargs: object) -> None: ...

    def set_yticklabels(self, *args: object, **kwargs: object) -> None: ...

    def set_yticks(self, *args: object, **kwargs: object) -> None: ...

    def table(self, *args: object, **kwargs: object) -> _Table: ...

    def text(self, *args: object, **kwargs: object) -> None: ...


class _Figure(Protocol):
    def savefig(self, path: str) -> None: ...

    def suptitle(self, *args: object, **kwargs: object) -> None: ...


class _Style(Protocol):
    def use(self, style: str) -> None: ...


class _FontManager(Protocol):
    def findfont(self, font_name: str, *, fallback_to_default: bool) -> str: ...


class _MatplotlibModule(Protocol):
    font_manager: _FontManager

    def use(self, backend: str) -> None: ...


class _PyplotModule(Protocol):
    rcParams: dict[str, object]
    style: _Style

    def close(self, figure: _Figure) -> None: ...

    def colorbar(self, *args: object, **kwargs: object) -> None: ...

    def show(self) -> None: ...

    def subplots(self, *args: object, **kwargs: object) -> tuple[_Figure, _Axes | Sequence[_Axes]]: ...

    def tight_layout(self) -> None: ...


class _TickerModule(Protocol):
    def FormatStrFormatter(self, format_string: str) -> object: ...


class _SampleData(TypedDict):
    iteration: int
    elapsed_ms: float
    metadata: dict[str, object]


class _StageData(TypedDict):
    stage: str
    samples: list[_SampleData]
    stats: dict[str, float]


BenchmarkData = dict[str, _StageData]

try:
    matplotlib = cast(_MatplotlibModule, cast(object, importlib.import_module("matplotlib")))
    matplotlib.use("Agg")
    plt = cast(_PyplotModule, cast(object, importlib.import_module("matplotlib.pyplot")))
    mticker = cast(_TickerModule, cast(object, importlib.import_module("matplotlib.ticker")))
except ImportError as exc:
    raise SystemExit("benchmark_viz.py requires matplotlib; install it with `uv pip install matplotlib`") from exc
import numpy as np

# ─── 스타일 설정 ──────────────────────────────────────────────────

plt.style.use("seaborn-v0_8-darkgrid")

COLORS = {
    "context_enrich": "#2196F3",  # Blue
    "code_review": "#FF9800",  # Orange
    "rag_indexing": "#9C27B0",  # Purple
    "max_engine": "#4CAF50",  # Green
}

# 한국어 폰트 설정 (Apple SD Gothic Neo / 나눔고딕)
for font_name in ["Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR"]:
    try:
        _ = matplotlib.font_manager.findfont(font_name, fallback_to_default=False)
        plt.rcParams["font.family"] = font_name
        break
    except Exception:
        continue

plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["savefig.bbox"] = "tight"


# ─── 데이터 로드 ──────────────────────────────────────────────────


_REQUIRED_STATS = ("avg_ms", "median_ms", "min_ms", "max_ms", "p95_ms", "stddev_ms", "n")


def _validate_benchmark_data(data: object, path: str) -> BenchmarkData:
    if not isinstance(data, dict) or not data:
        raise ValueError(f"{path}: expected a non-empty stage mapping")

    raw_mapping: dict[str, object] = cast(dict[str, object], data)
    for stage, payload in raw_mapping.items():
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: each stage must map to an object")
        payload_mapping = cast(dict[str, object], payload)
        stats = payload_mapping.get("stats")
        samples = payload_mapping.get("samples")
        if not isinstance(stats, dict) or not isinstance(samples, list) or not samples:
            raise ValueError(f"{path}: stage '{stage}' needs non-empty 'stats' and 'samples'")
        stats_mapping = cast(dict[str, object], stats)
        samples_list = cast(list[object], samples)
        missing_stats = [key for key in _REQUIRED_STATS if key not in stats]
        if missing_stats:
            missing = ", ".join(missing_stats)
            raise ValueError(f"{path}: stage '{stage}' is missing stats: {missing}")
        if any(not isinstance(stats_mapping[key], (int, float)) for key in _REQUIRED_STATS):
            raise ValueError(f"{path}: stage '{stage}' stats must be numeric")
        for sample_index, sample in enumerate(samples_list):
            if not isinstance(sample, dict):
                raise ValueError(f"{path}: stage '{stage}' sample {sample_index} must be an object")
            sample_mapping = cast(dict[str, object], sample)
            if not isinstance(sample_mapping.get("iteration"), int) or isinstance(
                sample_mapping.get("iteration"), bool
            ):
                raise ValueError(f"{path}: stage '{stage}' sample {sample_index} has invalid iteration")
            if not isinstance(sample_mapping.get("elapsed_ms"), (int, float)):
                raise ValueError(f"{path}: stage '{stage}' sample {sample_index} has invalid elapsed_ms")
            if not isinstance(sample_mapping.get("metadata"), dict):
                raise ValueError(f"{path}: stage '{stage}' sample {sample_index} needs metadata")

    return cast(BenchmarkData, data)


def load_benchmark(path: str) -> BenchmarkData:
    """JSON 벤치마크 파일을 로드합니다."""
    try:
        with open(path, encoding="utf-8") as f:
            raw_data = cast(object, json.load(f))
    except OSError as exc:
        raise ValueError(f"{path}: unable to read input ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}") from exc

    return _validate_benchmark_data(raw_data, path)


def _metric(values: Mapping[str, object], key: str) -> float:
    value = values.get(key)
    return float(value) if isinstance(value, (int, float)) else 0.0


# ─── 색상 / 레이블 헬퍼 ──────────────────────────────────────────


def _stage_color(stage: str) -> str:
    return COLORS.get(stage, "#9E9E9E")


def _stage_label(stage: str) -> str:
    labels = {
        "context_enrich": "Context Enrich\n(P1+P2)",
        "code_review": "Code Review\n(P3)",
        "rag_indexing": "RAG Indexing\n(Vector + Context)",
        "max_engine": "MAX Engine\n(P4)",
    }
    return labels.get(stage, stage)


# ─── 차트 1: 개요 대시보드 ────────────────────────────────────────


def plot_overview(data: BenchmarkData, output_dir: str, fmt: str):
    """스테이지별 평균/최소/최대/P95 latency 비교 대시보드."""
    stages = list(data.keys())
    if not stages:
        return

    fig, axes_result = plt.subplots(1, 2, figsize=(14, 6))
    axes = cast(Sequence[_Axes], axes_result)

    # --- Bar Chart: Avg + P95 ---
    ax = axes[0]
    names = [_stage_label(s) for s in stages]
    colors = [_stage_color(s) for s in stages]
    avg_vals = [data[s]["stats"]["avg_ms"] for s in stages]
    p95_vals = [data[s]["stats"]["p95_ms"] for s in stages]
    min_vals = [data[s]["stats"]["min_ms"] for s in stages]
    max_vals = [data[s]["stats"]["max_ms"] for s in stages]

    x = np.arange(len(stages))
    width = 0.35

    bars_avg = ax.bar(
        x - width / 2,
        avg_vals,
        width,
        label="평균 (Avg)",
        color=colors,
        edgecolor="white",
        linewidth=0.5,
    )

    # P95 점선 오버레이
    ax.scatter(
        x - width / 2,
        p95_vals,
        marker="D",
        color="darkred",
        zorder=5,
        s=60,
        label="P95",
    )

    # Min-Max 에러바
    ax.errorbar(
        x - width / 2,
        avg_vals,
        yerr=[
            [avg_vals[i] - min_vals[i] for i in range(len(stages))],
            [max_vals[i] - avg_vals[i] for i in range(len(stages))],
        ],
        fmt="none",
        capsize=4,
        color="gray",
        alpha=0.6,
    )

    # 막대 위 값 표시
    for bar, val, _p95 in zip(bars_avg, avg_vals, p95_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_vals[0] * 0.02,
            f"{val:.0f} ms",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=10)
    ax.set_ylabel("Latency (ms)", fontsize=11)
    ax.set_title("스테이지별 Latency 비교", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f ms"))

    # --- Table: Statistics ---
    ax2 = axes[1]
    ax2.axis("off")

    table_data: list[list[str]] = []
    row_labels: list[str] = []
    for s in stages:
        stats = data[s]["stats"]
        table_data.append(
            [
                f"{stats['avg_ms']:.1f}",
                f"{stats['median_ms']:.1f}",
                f"{stats['min_ms']:.1f}",
                f"{stats['max_ms']:.1f}",
                f"{stats['p95_ms']:.1f}",
                f"{stats['stddev_ms']:.1f}",
                str(stats["n"]),
            ]
        )
        row_labels.append(_stage_label(s).replace("\n", " "))

    col_labels = ["평균", "중앙값", "최소", "최대", "P95", "표준편차", "샘플수"]

    table = ax2.table(
        cellText=table_data,
        rowLabels=row_labels,
        colLabels=col_labels,
        cellLoc="center",
        rowLoc="center",
        loc="center",
        colWidths=[0.12] * 7,
    )

    # 테이블 스타일링
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#2c3e50")
            cell.set_text_props(color="white", fontweight="bold")
        elif col == -1:
            cell.set_facecolor("#ecf0f1")
            cell.set_text_props(fontweight="bold")
        else:
            cell.set_facecolor("#f8f9fa")

    ax2.set_title("상세 통계 (ms)", fontsize=13, fontweight="bold")

    plt.tight_layout()
    save_path = os.path.join(output_dir, f"01_overview.{fmt}")
    fig.savefig(save_path)
    plt.close(fig)
    print(f"  ✅ 개요 대시보드 → {save_path}")


# ─── 차트 2: 스테이지별 Latency Trend ─────────────────────────────


def plot_trends(data: BenchmarkData, output_dir: str, fmt: str):
    """각 스테이지의 반복 횟수별 지연시간 추이."""
    stages = list(data.keys())
    if not stages:
        return

    n_stages = len(stages)
    fig, axes_result = plt.subplots(1, n_stages, figsize=(6 * n_stages, 5))
    if n_stages == 1:
        axes: Sequence[_Axes] = [cast(_Axes, axes_result)]
    else:
        axes = cast(Sequence[_Axes], axes_result)

    for ax, stage in zip(axes, stages):
        samples = data[stage]["samples"]
        stats = data[stage]["stats"]

        iterations = [s["iteration"] for s in samples]
        elapsed = [s["elapsed_ms"] for s in samples]

        color = _stage_color(stage)

        # Line + scatter
        ax.plot(
            iterations,
            elapsed,
            color=color,
            marker="o",
            linewidth=2,
            markersize=8,
            zorder=3,
        )
        ax.fill_between(
            iterations,
            elapsed,
            stats["avg_ms"],
            alpha=0.15,
            color=color,
        )

        # 평균선
        ax.axhline(
            stats["avg_ms"],
            color=color,
            linestyle="--",
            alpha=0.5,
            linewidth=1,
            label=f"평균: {stats['avg_ms']:.1f} ms",
        )

        # P95 영역
        ax.axhline(
            stats["p95_ms"],
            color="red",
            linestyle=":",
            alpha=0.4,
            linewidth=1,
            label=f"P95: {stats['p95_ms']:.1f} ms",
        )

        # 값 레이블
        for i, v in zip(iterations, elapsed):
            ax.annotate(
                f"{v:.0f}",
                (i, v),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=8,
                color=color,
                fontweight="bold",
            )

        ax.set_xlabel("반복 횟수", fontsize=10)
        ax.set_ylabel("Latency (ms)", fontsize=10)
        ax.set_title(
            f"{_stage_label(stage).replace('\n', ' ')}\nn={stats['n']}, StdDev={stats['stddev_ms']:.1f} ms",
            fontsize=12,
            fontweight="bold",
        )
        ax.legend(fontsize=8, loc="upper right")
        ax.set_xticks(iterations)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f ms"))

    plt.tight_layout()
    save_path = os.path.join(output_dir, f"02_trends.{fmt}")
    fig.savefig(save_path)
    plt.close(fig)
    print(f"  ✅ Latency Trend → {save_path}")


# ─── 차트 3: 세부 컴포넌트 분석 ───────────────────────────────────


def plot_breakdown(data: BenchmarkData, output_dir: str, fmt: str):
    """각 스테이지의 서브 컴포넌트별 Latency Breakdown."""
    stages = list(data.keys())
    if not stages:
        return

    # context_enrich 서브 항목
    if "context_enrich" in data:
        fig, ax_result = plt.subplots(1, 1, figsize=(8, 5))
        ax = cast(_Axes, ax_result)
        sample = data["context_enrich"]["samples"][0]
        meta = sample["metadata"]

        components = ["build_first_ms", "search_avg_ms", "summarize_ms"]
        labels = ["build_tree (최초)", "search (평균)", "summarize_files"]
        values = [_metric(meta, c) for c in components]
        colors_ce = ["#1565C0", "#42A5F5", "#90CAF9"]

        bars = ax.barh(labels, values, color=colors_ce, edgecolor="white", height=0.6)
        for bar, v in zip(bars, values):
            ax.text(
                bar.get_width() + 1,
                bar.get_y() + bar.get_height() / 2,
                f"{v:.1f} ms",
                va="center",
                fontsize=10,
                fontweight="bold",
            )

        ax.set_xlabel("Latency (ms)", fontsize=11)
        ax.set_title(
            f"Context Enrich — 세부 Breakdown\n({meta.get('files_indexed', '?')} files, {meta.get('tree_size_kb', '?')} KB tree)",
            fontsize=12,
            fontweight="bold",
        )
        ax.margins(y=0.2)
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f ms"))

        plt.tight_layout()
        save_path = os.path.join(output_dir, f"03a_breakdown_context_enrich.{fmt}")
        fig.savefig(save_path)
        plt.close(fig)
        print(f"  ✅ Context Enrich 세부 분석 → {save_path}")

    # code_review 서브 항목
    if "code_review" in data:
        fig, ax_result = plt.subplots(1, 1, figsize=(8, 5))
        ax = cast(_Axes, ax_result)
        sample = data["code_review"]["samples"][0]
        meta = sample["metadata"]

        components = ["diff_stat_ms", "diff_detail_ms", "llm_mock_ms"]
        labels = ["git diff --stat", "git diff (상세)", "LLM Mock 호출"]
        values = [_metric(meta, c) for c in components]
        colors_cr = ["#E65100", "#FF9800", "#FFCC80"]

        bars = ax.barh(labels, values, color=colors_cr, edgecolor="white", height=0.6)
        for bar, v in zip(bars, values):
            ax.text(
                bar.get_width() + 0.5,
                bar.get_y() + bar.get_height() / 2,
                f"{v:.2f} ms" if v < 1 else f"{v:.1f} ms",
                va="center",
                fontsize=10,
                fontweight="bold",
            )

        ax.set_xlabel("Latency (ms)", fontsize=11)
        ax.set_title(
            f"Code Review — 세부 Breakdown\n({meta.get('changed_files', '?')} files, {meta.get('diff_size_bytes', '?')} bytes diff)",
            fontsize=12,
            fontweight="bold",
        )
        ax.margins(y=0.2)
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f ms"))

        plt.tight_layout()
        save_path = os.path.join(output_dir, f"03b_breakdown_code_review.{fmt}")
        fig.savefig(save_path)
        plt.close(fig)
        print(f"  ✅ Code Review 세부 분석 → {save_path}")

    # rag_indexing 서브 항목
    if "rag_indexing" in data:
        fig, axes_result = plt.subplots(1, 2, figsize=(14, 5))
        axes = cast(Sequence[_Axes], axes_result)

        sample = data["rag_indexing"]["samples"][0]
        meta = sample["metadata"]

        # Main pipeline breakdown (horizontal bar)
        ax = axes[0]
        components = ["index_project_ms", "search_unified_ms", "format_context_ms"]
        labels = ["index_project\n(전체 인덱싱)", "search (hybrid)", "format_context"]
        values = [_metric(meta, c) for c in components]
        colors_rag_main = ["#7B1FA2", "#AB47BC", "#CE93D8"]

        bars = ax.barh(labels, values, color=colors_rag_main, edgecolor="white", height=0.5)
        for bar, v in zip(bars, values):
            ax.text(
                bar.get_width() + 1,
                bar.get_y() + bar.get_height() / 2,
                f"{v:.1f} ms",
                va="center",
                fontsize=10,
                fontweight="bold",
            )
        ax.set_xlabel("Latency (ms)", fontsize=11)
        ax.set_title(
            f"RAG Pipeline — 주요 단계\n({meta.get('total_chunks', '?')} chunks indexed)",
            fontsize=12,
            fontweight="bold",
        )
        ax.margins(y=0.2)
        ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f ms"))

        # Search mode comparison (vertical bar)
        ax = axes[1]
        search_modes = ["search_semantic_ms", "search_keyword_ms", "search_hybrid_ms"]
        search_labels = ["Semantic\n(VectorStore)", "Keyword\n(식별자 매칭)", "Hybrid\n(RRF Fusion)"]
        search_vals = [_metric(meta, k) for k in search_modes]
        search_colors = ["#9C27B0", "#E040FB", "#7C4DFF"]

        bars = ax.bar(search_labels, search_vals, color=search_colors, edgecolor="white", width=0.5)
        for bar, v in zip(bars, search_vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(search_vals) * 0.02,
                f"{v:.2f} ms",
                ha="center",
                fontsize=9,
                fontweight="bold",
            )
        ax.set_ylabel("Latency (ms)", fontsize=11)
        ax.set_title("검색 모드별 비교\n(Semantic / Keyword / Hybrid)", fontsize=12, fontweight="bold")

        fig.suptitle(
            "RAG Indexing — 세부 Breakdown",
            fontsize=14,
            fontweight="bold",
            y=1.02,
        )
        plt.tight_layout()
        save_path = os.path.join(output_dir, f"03d_breakdown_rag_indexing.{fmt}")
        fig.savefig(save_path)
        plt.close(fig)
        print(f"  ✅ RAG Indexing 세부 분석 → {save_path}")

    # max_engine 서브 항목
    if "max_engine" in data:
        fig, axes_result = plt.subplots(1, 3, figsize=(16, 5))
        axes = cast(Sequence[_Axes], axes_result)

        sample = data["max_engine"]["samples"][0]
        meta = sample["metadata"]

        # Config comparison
        ax = axes[0]
        config_keys = ["config_1_model_ms", "config_2_models_ms", "config_3_models_ms"]
        config_labels = ["1 model", "2 models", "3 models"]
        config_vals = [_metric(meta, k) for k in config_keys]
        _ = ax.bar(config_labels, config_vals, color=["#66BB6A", "#4CAF50", "#2E7D32"], edgecolor="white")
        for i, v in enumerate(config_vals):
            ax.text(i, v + 0.001, f"{v:.3f} ms", ha="center", fontsize=8, fontweight="bold")
        ax.set_title("Worker Config", fontsize=11, fontweight="bold")
        ax.set_ylabel("ms")

        # Prompt comparison
        ax = axes[1]
        prompt_keys = ["prompt_default_ms", "prompt_creative_ms", "prompt_safe_ms", "prompt_balanced_ms"]
        prompt_labels = ["default", "creative", "safe", "balanced"]
        prompt_vals = [_metric(meta, k) for k in prompt_keys]
        _ = ax.bar(
            prompt_labels,
            prompt_vals,
            color=["#A5D6A7", "#81C784", "#66BB6A", "#4CAF50"],
            edgecolor="white",
        )
        for i, v in enumerate(prompt_vals):
            ax.text(i, v + 0.001, f"{v:.3f} ms", ha="center", fontsize=8, fontweight="bold")
        ax.set_title("Worker Prompt 전략별", fontsize=11, fontweight="bold")

        # Selector comparison
        ax = axes[2]
        select_keys = ["select_2_candidates_ms", "select_3_candidates_ms", "trace_format_ms"]
        select_labels = ["2 candidates", "3 candidates", "Format trace"]
        select_vals = [_metric(meta, k) for k in select_keys]
        colors_sl = ["#43A047", "#2E7D32", "#1B5E20"]
        _ = ax.bar(select_labels, select_vals, color=colors_sl, edgecolor="white")
        for i, v in enumerate(select_vals):
            ax.text(i, v + 0.001, f"{v:.3f} ms", ha="center", fontsize=8, fontweight="bold")
        ax.set_title("Selector + Trace", fontsize=11, fontweight="bold")

        fig.suptitle(
            "MAX Engine — 세부 Breakdown",
            fontsize=14,
            fontweight="bold",
            y=1.02,
        )
        plt.tight_layout()
        save_path = os.path.join(output_dir, f"03c_breakdown_max_engine.{fmt}")
        fig.savefig(save_path)
        plt.close(fig)
        print(f"  ✅ MAX Engine 세부 분석 → {save_path}")


# ─── 차트 4: 통계 히트맵 ─────────────────────────────────────────


def plot_heatmap(data: BenchmarkData, output_dir: str, fmt: str):
    """스테이지별 통계를 컬러 히트맵으로 표시."""
    stages = list(data.keys())
    if not stages:
        return

    metrics = ["avg_ms", "median_ms", "min_ms", "max_ms", "p95_ms", "stddev_ms"]
    metric_labels = ["Avg", "Median", "Min", "Max", "P95", "StdDev"]

    matrix = np.array([[data[s]["stats"][m] for m in metrics] for s in stages])

    fig, ax_result = plt.subplots(1, 1, figsize=(10, 4 + len(stages) * 0.8))
    ax = cast(_Axes, ax_result)

    # 로그 스케일 히트맵 (값 차이가 크므로)
    log_matrix = np.log10(np.maximum(matrix, 0.01))

    im = ax.imshow(log_matrix, cmap="YlOrRd", aspect="auto", interpolation="nearest")

    # 값 표시
    for i in range(len(stages)):
        for j in range(len(metrics)):
            val = data[stages[i]]["stats"][metrics[j]]
            text_color = "white" if log_matrix[i, j] > log_matrix.max() * 0.6 else "black"
            ax.text(
                j,
                i,
                f"{val:.2f}" if val < 10 else f"{val:.0f}",
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
                color=text_color,
            )

    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(metric_labels, fontsize=10)
    ax.set_yticks(range(len(stages)))
    ax.set_yticklabels([_stage_label(s) for s in stages], fontsize=10)
    ax.set_title("스테이지별 Latency 통계 히트맵 (ms)", fontsize=13, fontweight="bold")

    plt.colorbar(im, ax=ax, shrink=0.8, label="log10(ms)")

    plt.tight_layout()
    save_path = os.path.join(output_dir, f"04_heatmap.{fmt}")
    fig.savefig(save_path)
    plt.close(fig)
    print(f"  ✅ 통계 히트맵 → {save_path}")


#  ─── 차트 5: 서브 컴포넌트 그룹 비교 (모든 스테이지) ──────────────


def plot_subcomponent_comparison(data: BenchmarkData, output_dir: str, fmt: str):
    """모든 스테이지의 주요 서브 컴포넌트를 하나의 차트에 그룹 비교."""
    stages = list(data.keys())
    if len(stages) < 2:
        return

    fig, ax_result = plt.subplots(1, 1, figsize=(10, 6))
    ax = cast(_Axes, ax_result)

    # 각 스테이지의 첫 번째 샘플 metadata 기반 서브항목 추출
    stage_groups: dict[str, dict[str, float]] = {}
    for s in stages:
        meta = data[s]["samples"][0]["metadata"]
        group = {}

        if s == "context_enrich":
            group["build_tree"] = _metric(meta, "build_first_ms")
            group["search"] = _metric(meta, "search_avg_ms")
            group["summarize"] = _metric(meta, "summarize_ms")
        elif s == "code_review":
            group["git diff\n(stat)"] = _metric(meta, "diff_stat_ms")
            group["git diff\n(detail)"] = _metric(meta, "diff_detail_ms")
            group["LLM mock"] = _metric(meta, "llm_mock_ms")
        elif s == "max_engine":
            group["config\nbuild"] = _metric(meta, "config_3_models_ms")
            group["prompt\nbuild"] = _metric(meta, "prompt_default_ms")
            group["selector"] = _metric(meta, "select_3_candidates_ms")
        elif s == "rag_indexing":
            group["index\nproject"] = _metric(meta, "index_project_ms")
            group["chunk\npython"] = _metric(meta, "chunk_python_ms")
            group["chunk\nmd"] = _metric(meta, "chunk_markdown_ms")
            group["search\nhybrid"] = _metric(meta, "search_hybrid_ms")
            group["format\nctx"] = _metric(meta, "format_context_ms")

        stage_groups[s] = group

    # 그룹 바 차트
    n_groups = len(stage_groups)
    group_labels: list[str] = list(stage_groups.keys())
    _ = [_stage_color(g) for g in group_labels]

    # 각 스테이지의 서브 컴포넌트
    all_sub_labels: list[str] = sorted({k for g in stage_groups.values() for k in g})
    x = np.arange(len(all_sub_labels))
    width = 0.8 / n_groups

    for i, (stage, subs) in enumerate(stage_groups.items()):
        offsets = x + (i - n_groups / 2 + 0.5) * width
        vals = [subs.get(label, 0) for label in all_sub_labels]
        _ = ax.bar(
            offsets,
            vals,
            width,
            label=_stage_label(stage).replace("\n", " "),
            color=_stage_color(stage),
            alpha=0.85,
            edgecolor="white",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(all_sub_labels, fontsize=9)
    ax.set_ylabel("Latency (ms)", fontsize=11)
    ax.set_title("스테이지별 서브 컴포넌트 비교", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9, loc="upper right")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f ms"))

    plt.tight_layout()
    save_path = os.path.join(output_dir, f"05_subcomponent_comparison.{fmt}")
    fig.savefig(save_path)
    plt.close(fig)
    print(f"  ✅ 서브 컴포넌트 비교 → {save_path}")


# ─── 메인 ─────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Freebuff-Style Proactive Pipeline — 벤치마크 시각화",
    )
    _ = parser.add_argument(
        "input",
        help="JSON 벤치마크 결과 파일 경로",
    )
    _ = parser.add_argument(
        "--output-dir",
        default="charts",
        help="차트 출력 디렉토리 (기본: ./charts)",
    )
    _ = parser.add_argument(
        "--format",
        default="png",
        choices=["png", "svg", "pdf"],
        help="출력 이미지 포맷 (기본: png)",
    )
    _ = parser.add_argument(
        "--show",
        action="store_true",
        help="GUI로 차트 표시 (png 저장 안 함)",
    )
    _ = parser.add_argument(
        "--skip-charts",
        nargs="*",
        choices=["overview", "trends", "breakdown", "heatmap", "subcomponent"],
        help="건너뛸 차트",
    )
    parsed_args = cast(dict[str, object], cast(object, vars(parser.parse_args())))
    input_path = cast(str, parsed_args["input"])
    output_dir = cast(str, parsed_args["output_dir"])
    output_format = cast(str, parsed_args["format"])
    show = cast(bool, parsed_args["show"])
    skip_charts = cast(list[str] | None, parsed_args["skip_charts"])

    if not os.path.exists(input_path):
        print(f"❌ 입력 파일 없음: {input_path}")
        sys.exit(1)

    if show:
        matplotlib.use("TkAgg")

    print("📊 Proactive Pipeline Benchmark Visualization")
    print(f"   입력: {input_path}")
    print(f"   포맷: {output_format}")
    print(f"   출력: {output_dir}/")
    print()

    try:
        data = load_benchmark(input_path)
    except ValueError as exc:
        parser.error(str(exc))
    stages = list(data.keys())

    print(f"   로드된 스테이지: {', '.join(stages)}")
    print()

    skip = set(skip_charts or [])

    os.makedirs(output_dir, exist_ok=True)

    if "overview" not in skip:
        plot_overview(data, output_dir, output_format)
    if "trends" not in skip:
        plot_trends(data, output_dir, output_format)
    if "breakdown" not in skip:
        plot_breakdown(data, output_dir, output_format)
    if "heatmap" not in skip:
        plot_heatmap(data, output_dir, output_format)
    if "subcomponent" not in skip:
        plot_subcomponent_comparison(data, output_dir, output_format)

    print()
    print(f"✅ 모든 차트 생성 완료 → {os.path.abspath(output_dir)}/")

    if show:
        plt.show()


if __name__ == "__main__":
    main()
