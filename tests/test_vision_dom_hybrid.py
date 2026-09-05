"""Tests for antigravity_k.tools.vision_dom_hybrid.

Coverage targets:
  - Obstacle dataclass: construction, default values
  - HybridAnalysis: has_obstacles(), blocking_obstacles(), to_llm_summary()
  - VisionDOMHybrid._parse_obstacles(): raw JS list → Obstacle objects
  - VisionDOMHybrid._find_closest_ref(): nearest element distance calc
  - VisionDOMHybrid._judge_page_state(): state determination
"""

from collections.abc import Callable
from typing import cast

import pytest

from antigravity_k.tools.semantic_dom import BoundingBox, SemanticSnapshot
from antigravity_k.tools.vision_dom_hybrid import (
    HybridAnalysis,
    Obstacle,
    VisionDOMHybrid,
)


def _parse_obstacles(
    hybrid: VisionDOMHybrid,
    raw_list: object,
    snapshot: SemanticSnapshot,
) -> list[Obstacle]:
    parser = cast(
        Callable[[object, SemanticSnapshot], list[Obstacle]],
        getattr(hybrid, "_parse_obstacles"),
    )
    return parser(raw_list, snapshot)


def _find_closest_ref(
    hybrid: VisionDOMHybrid,
    snapshot: SemanticSnapshot,
    x: float,
    y: float,
) -> str:
    finder = cast(
        Callable[[SemanticSnapshot, float, float], str],
        getattr(hybrid, "_find_closest_ref"),
    )
    return finder(snapshot, x, y)


def _judge_page_state(hybrid: VisionDOMHybrid, analysis: HybridAnalysis) -> str:
    judge = cast(Callable[[HybridAnalysis], str], getattr(hybrid, "_judge_page_state"))
    return judge(analysis)

# ═══════════════════════════════════════════════════════════════════
# Obstacle dataclass tests
# ═══════════════════════════════════════════════════════════════════


class TestObstacle:
    """Obstacle dataclass — 기본 데이터 모델."""

    def test_minimal_construction(self):
        """필수 필드만으로 생성."""
        obs = Obstacle(type="modal", description="Test modal")
        assert obs.type == "modal"
        assert obs.description == "Test modal"
        assert obs.bbox is None
        assert obs.close_ref == ""
        assert obs.blocking is True

    def test_with_bbox(self):
        """BoundingBox 포함 생성."""
        bbox = BoundingBox(x=10, y=20, width=100, height=200)
        obs = Obstacle(type="popup", description="Test popup", bbox=bbox)
        assert obs.bbox == bbox
        obs_bbox = obs.bbox
        assert obs_bbox is not None
        assert obs_bbox.x == 10
        assert obs_bbox.y == 20

    def test_cookie_banner_not_blocking(self):
        """쿠키 배너는 blocking=False (다른 요소와 상호작용 가능)."""
        obs = Obstacle(type="cookie_banner", description="Cookie consent", blocking=False)
        assert obs.blocking is False

    def test_description_truncation(self):
        """_parse_obstacles에서 description은 100자로 제한됨."""
        obs = Obstacle(type="modal", description="A" * 200)
        assert len(obs.description) == 200  # dataclass 자체는 제한 없음

    def test_close_ref_string(self):
        """닫기 버튼 @ref 문자열."""
        obs = Obstacle(type="modal", description="Test", close_ref="@3")
        assert obs.close_ref == "@3"


# ═══════════════════════════════════════════════════════════════════
# HybridAnalysis dataclass tests
# ═══════════════════════════════════════════════════════════════════


class TestHybridAnalysis:
    """HybridAnalysis — 분석 결과 컨테이너."""

    def test_default_values(self):
        """기본값 확인."""
        analysis = HybridAnalysis()
        assert analysis.snapshot is None
        assert analysis.screenshot_base64 == ""
        assert analysis.obstacles == []
        assert analysis.page_state == "normal"
        assert analysis.viewport_size == (0, 0)

    def test_has_obstacles_empty(self):
        """장애물이 없으면 False."""
        analysis = HybridAnalysis()
        assert analysis.has_obstacles() is False

    def test_has_obstacles_present(self):
        """장애물이 있으면 True."""
        analysis = HybridAnalysis(
            obstacles=[Obstacle(type="modal", description="Test")],
        )
        assert analysis.has_obstacles() is True

    def test_blocking_obstacles_filters_correctly(self):
        """blocking=True인 장애물만 반환."""
        analysis = HybridAnalysis(
            obstacles=[
                Obstacle(type="modal", description="Blocking modal", blocking=True),
                Obstacle(type="cookie_banner", description="Non-blocking", blocking=False),
                Obstacle(type="overlay", description="Blocking overlay", blocking=True),
            ],
        )
        blocking = analysis.blocking_obstacles()
        assert len(blocking) == 2
        assert all(o.blocking for o in blocking)

    def test_blocking_obstacles_empty(self):
        """blocking 장애물이 없으면 빈 리스트."""
        analysis = HybridAnalysis(
            obstacles=[
                Obstacle(type="cookie_banner", description="Not blocking", blocking=False),
            ],
        )
        assert analysis.blocking_obstacles() == []

    def test_to_llm_summary_normal(self):
        """정상 페이지 — 간결한 요약."""
        analysis = HybridAnalysis(page_state="normal")
        summary = analysis.to_llm_summary()
        assert "Page State: normal" in summary
        assert "Obstacles" not in summary

    def test_to_llm_summary_with_obstacles(self):
        """장애물이 있을 때 요약에 포함됨."""
        analysis = HybridAnalysis(
            obstacles=[
                Obstacle(type="modal", description="Login popup", close_ref="@3", blocking=True),
                Obstacle(type="cookie_banner", description="Cookie consent", blocking=False),
            ],
        )
        summary = analysis.to_llm_summary()
        assert "⚠️" in summary
        assert "modal" in summary
        assert "Login popup" in summary
        assert "@3" in summary
        assert "cookie_banner" in summary

    def test_to_llm_summary_with_snapshot(self):
        """스냅샷 정보가 있을 때 요약에 포함됨."""
        analysis = HybridAnalysis(
            snapshot=SemanticSnapshot(elements={}),
            viewport_size=(1920, 1080),
        )
        summary = analysis.to_llm_summary()
        assert "1920x1080" in summary
        assert "Interactable" in summary

    def test_to_llm_summary_obstacles_with_close_btn(self):
        """닫기 버튼 정보가 있는 장애물 요약."""
        analysis = HybridAnalysis(
            obstacles=[
                Obstacle(type="modal", description="Welcome popup", close_ref="@5", blocking=True),
            ],
        )
        summary = analysis.to_llm_summary()
        assert "→ 닫기: @5" in summary


# ═══════════════════════════════════════════════════════════════════
# VisionDOMHybrid._parse_obstacles tests
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def hybrid() -> VisionDOMHybrid:
    """VisionDOMHybrid 인스턴스."""
    return VisionDOMHybrid()


@pytest.fixture
def empty_snapshot() -> SemanticSnapshot:
    """빈 스냅샷."""
    return SemanticSnapshot(elements={})


class TestParseObstacles:
    """_parse_obstacles — JS 결과를 Obstacle 객체로 변환."""

    def test_empty_list(self, hybrid: VisionDOMHybrid, empty_snapshot: SemanticSnapshot):
        """빈 리스트 — 빈 결과."""
        assert _parse_obstacles(hybrid, [], empty_snapshot) == []

    def test_modal_without_close(self, hybrid: VisionDOMHybrid, empty_snapshot: SemanticSnapshot):
        """모달 (닫기 버튼 없음)."""
        raw = [
            {
                "type": "modal",
                "description": "Login required",
                "bbox": {"x": 100, "y": 200, "width": 300, "height": 400},
            },
        ]
        obstacles = _parse_obstacles(hybrid, raw, empty_snapshot)
        assert len(obstacles) == 1
        assert obstacles[0].type == "modal"
        assert obstacles[0].description == "Login required"
        assert obstacles[0].blocking is True
        obstacle_bbox = obstacles[0].bbox
        assert obstacle_bbox is not None
        assert obstacle_bbox.x == 100
        assert obstacle_bbox.y == 200
        assert obstacles[0].close_ref == ""  # closeBtn 없음

    def test_modal_with_close_btn(self, hybrid: VisionDOMHybrid, empty_snapshot: SemanticSnapshot):
        """모달 (닫기 버튼 있음)."""
        raw = [
            {
                "type": "modal",
                "description": "Confirm",
                "bbox": {"x": 0, "y": 0, "width": 500, "height": 500},
                "closeBtn": {
                    "text": "✕",
                    "bbox": {"x": 450, "y": 10, "width": 30, "height": 30},
                },
            },
        ]
        obstacles = _parse_obstacles(hybrid, raw, empty_snapshot)
        assert len(obstacles) == 1
        # close_ref는 빈 스냅샷에서는 항상 ""
        assert obstacles[0].close_ref == ""

    def test_cookie_banner_not_blocking(self, hybrid: VisionDOMHybrid, empty_snapshot: SemanticSnapshot):
        """쿠키 배너 — blocking=False."""
        raw = [
            {
                "type": "cookie_banner",
                "description": "Accept cookies",
                "bbox": {"x": 0, "y": 900, "width": 1200, "height": 100},
            },
        ]
        obstacles = _parse_obstacles(hybrid, raw, empty_snapshot)
        assert len(obstacles) == 1
        assert obstacles[0].type == "cookie_banner"
        assert obstacles[0].blocking is False  # cookie_banner는 blocking=False

    def test_overlay_blocking(self, hybrid: VisionDOMHybrid, empty_snapshot: SemanticSnapshot):
        """오버레이 — blocking=True."""
        raw = [
            {
                "type": "overlay",
                "description": "Full screen overlay",
                "bbox": {"x": 0, "y": 0, "width": 1920, "height": 1080},
            },
        ]
        obstacles = _parse_obstacles(hybrid, raw, empty_snapshot)
        assert obstacles[0].blocking is True

    def test_unknown_type_default_blocking(self, hybrid: VisionDOMHybrid, empty_snapshot: SemanticSnapshot):
        """알 수 없는 타입 — 기본적으로 blocking=False."""
        raw = [
            {
                "type": "unknown",
                "description": "Something",
                "bbox": {"x": 10, "y": 10, "width": 100, "height": 100},
            },
        ]
        obstacles = _parse_obstacles(hybrid, raw, empty_snapshot)
        assert obstacles[0].blocking is False

    def test_description_truncation(self, hybrid: VisionDOMHybrid, empty_snapshot: SemanticSnapshot):
        """description이 100자로 제한됨."""
        raw = [
            {
                "type": "modal",
                "description": "X" * 200,
                "bbox": {"x": 0, "y": 0, "width": 100, "height": 100},
            },
        ]
        obstacles = _parse_obstacles(hybrid, raw, empty_snapshot)
        assert len(obstacles[0].description) <= 100
        assert obstacles[0].description == "X" * 100

    def test_missing_bbox(self, hybrid: VisionDOMHybrid, empty_snapshot: SemanticSnapshot):
        """bbox 누락 — Obstacle.bbox는 None."""
        raw = [
            {
                "type": "modal",
                "description": "No bbox",
            },
        ]
        obstacles = _parse_obstacles(hybrid, raw, empty_snapshot)
        assert obstacles[0].bbox is None

    def test_partial_bbox(self, hybrid: VisionDOMHybrid, empty_snapshot: SemanticSnapshot):
        """부분적인 bbox 정보."""
        raw = [
            {
                "type": "modal",
                "description": "Partial",
                "bbox": {"x": 10, "y": 20},  # width, height 없음
            },
        ]
        obstacles = _parse_obstacles(hybrid, raw, empty_snapshot)
        assert obstacles[0].bbox is not None
        assert obstacles[0].bbox.x == 10
        assert obstacles[0].bbox.y == 20
        assert obstacles[0].bbox.width == 0  # 기본값
        assert obstacles[0].bbox.height == 0  # 기본값


# ═══════════════════════════════════════════════════════════════════
# VisionDOMHybrid._find_closest_ref tests
# ═══════════════════════════════════════════════════════════════════


class TestFindClosestRef:
    """_find_closest_ref — 좌표에 가장 가까운 요소의 @ref."""

    @pytest.fixture
    def snapshot(self) -> SemanticSnapshot:
        """요소가 여러 개 있는 스냅샷 (@1과 @2는 가깝게 배치)."""
        from antigravity_k.tools.semantic_dom import ElementInfo

        elements = {
            "@1": ElementInfo(
                ref="@1",
                tag="button",
                name="Submit",
                bbox=BoundingBox(x=100, y=100, width=50, height=30),
                is_interactable=True,
            ),
            "@2": ElementInfo(
                ref="@2",
                tag="a",
                name="Link",
                bbox=BoundingBox(x=110, y=100, width=80, height=20),
                is_interactable=True,
            ),
            "@3": ElementInfo(
                ref="@3",
                tag="input",
                name="",
                bbox=BoundingBox(x=500, y=500, width=200, height=40),
                is_interactable=True,
            ),
        }
        return SemanticSnapshot(elements=elements)

    def test_closest_to_center(self, hybrid: VisionDOMHybrid, snapshot: SemanticSnapshot):
        """가장 가까운 요소의 @ref 반환."""
        # @1의 중심 (125, 115)에 가까운 좌표
        ref = _find_closest_ref(hybrid, snapshot, 125, 115)
        assert ref == "@1"

    def test_closest_to_second(self, hybrid: VisionDOMHybrid, snapshot: SemanticSnapshot):
        """@2에 가장 가까운 좌표 (@2 중심: 150, 110)."""
        ref = _find_closest_ref(hybrid, snapshot, 150, 110)
        assert ref == "@2"

    def test_closest_to_third(self, hybrid: VisionDOMHybrid, snapshot: SemanticSnapshot):
        """@3에 가장 가까운 좌표 (@3 중심: 600, 520)."""
        ref = _find_closest_ref(hybrid, snapshot, 600, 520)
        assert ref == "@3"

    def test_exact_center(self, hybrid: VisionDOMHybrid, snapshot: SemanticSnapshot):
        """요소 정중앙 좌표."""
        ref = _find_closest_ref(hybrid, snapshot, 125, 115)  # @1 center
        assert ref == "@1"

    def test_no_elements(self, hybrid: VisionDOMHybrid):
        """요소가 없는 스냅샷 — 빈 문자열."""
        empty = SemanticSnapshot(elements={})
        ref = _find_closest_ref(hybrid, empty, 100, 100)
        assert ref == ""

    def test_far_away_returns_empty(self, hybrid: VisionDOMHybrid, snapshot: SemanticSnapshot):
        """모든 요소에서 50px 이상 떨어짐 — 빈 문자열."""
        ref = _find_closest_ref(hybrid, snapshot, 9999, 9999)
        assert ref == ""

    def test_midpoint_between_two(self, hybrid: VisionDOMHybrid, snapshot: SemanticSnapshot):
        """두 요소 중간 지점 — 더 가까운 쪽 (50px 이내)."""
        # @1 중심: (125, 115), @2 중심: (150, 110)
        # 중간: (137.5, 112.5), 거리 ≈ 12.75px (50px 이내)
        midpoint_x = (125 + 150) / 2
        midpoint_y = (115 + 110) / 2
        ref = _find_closest_ref(hybrid, snapshot, midpoint_x, midpoint_y)
        assert ref in ("@1", "@2")

    def test_elements_without_bbox_skipped(self, hybrid: VisionDOMHybrid):
        """bbox가 없는 요소는 건너뜀."""
        from antigravity_k.tools.semantic_dom import ElementInfo

        elements = {
            "@1": ElementInfo(ref="@1", tag="div", name="", bbox=None, is_interactable=True),
            "@2": ElementInfo(
                ref="@2",
                tag="button",
                name="OK",
                bbox=BoundingBox(x=100, y=100, width=50, height=30),
                is_interactable=True,
            ),
        }
        snap = SemanticSnapshot(elements=elements)
        ref = _find_closest_ref(hybrid, snap, 125, 115)
        assert ref == "@2"  # @1은 bbox 없어서 제외


# ═══════════════════════════════════════════════════════════════════
# VisionDOMHybrid._judge_page_state tests
# ═══════════════════════════════════════════════════════════════════


class TestJudgePageState:
    """_judge_page_state — 페이지 상태 결정."""

    def test_normal_no_obstacles(self, hybrid: VisionDOMHybrid):
        """장애물 없음 — normal."""
        analysis = HybridAnalysis()
        assert _judge_page_state(hybrid, analysis) == "normal"

    def test_blocked_by_modal(self, hybrid: VisionDOMHybrid):
        """모달 장애물 — blocked."""
        analysis = HybridAnalysis(
            obstacles=[Obstacle(type="modal", description="Popup", blocking=True)],
        )
        assert _judge_page_state(hybrid, analysis) == "blocked"

    def test_blocked_by_overlay(self, hybrid: VisionDOMHybrid):
        """오버레이 — blocked."""
        analysis = HybridAnalysis(
            obstacles=[Obstacle(type="overlay", description="Full overlay", blocking=True)],
        )
        assert _judge_page_state(hybrid, analysis) == "blocked"

    def test_not_blocked_by_cookie_banner(self, hybrid: VisionDOMHybrid):
        """쿠키 배너만 있음 — normal (blocking=False)."""
        analysis = HybridAnalysis(
            obstacles=[Obstacle(type="cookie_banner", description="Cookies", blocking=False)],
        )
        assert _judge_page_state(hybrid, analysis) == "normal"

    def test_loading_no_elements(self, hybrid: VisionDOMHybrid):
        """스냅샷에 요소가 없음 — loading."""
        analysis = HybridAnalysis(snapshot=SemanticSnapshot(elements={}))
        assert _judge_page_state(hybrid, analysis) == "loading"

    def test_loading_overrides_blocked(self, hybrid: VisionDOMHybrid):
        """장애물 + 요소 없음 — blocked 우선."""
        analysis = HybridAnalysis(
            obstacles=[Obstacle(type="modal", description="Popup", blocking=True)],
            snapshot=SemanticSnapshot(elements={}),
        )
        assert _judge_page_state(hybrid, analysis) == "blocked"

    def test_normal_with_nonblocking_and_elements(self, hybrid: VisionDOMHybrid):
        """blocking=False 장애물 + 요소 있음 — normal."""
        from antigravity_k.tools.semantic_dom import ElementInfo

        analysis = HybridAnalysis(
            obstacles=[Obstacle(type="cookie_banner", description="Cookies", blocking=False)],
            snapshot=SemanticSnapshot(
                total_count=1,
                elements={
                    "@1": ElementInfo(
                        ref="@1",
                        tag="button",
                        name="OK",
                        bbox=BoundingBox(x=10, y=10, width=50, height=30),
                        is_interactable=True,
                    ),
                },
            ),
        )
        assert _judge_page_state(hybrid, analysis) == "normal"
