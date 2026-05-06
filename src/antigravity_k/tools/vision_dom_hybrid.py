"""
Antigravity-K: Vision + DOM 하이브리드 인식 엔진
=================================================
스크린샷(Vision)과 DOM 구조를 동시에 분석하여
인간 수준의 시각적 맥락을 AI 에이전트에게 제공합니다.

핵심 기능:
1. Set-of-Mark (SoM): 스크린샷에 인터랙티브 요소 번호 마킹
2. 장애물 감지: 팝업, 모달, 쿠키 배너 자동 인식
3. DOM + Vision 융합 분석: 텍스트 + 시각적 레이아웃 통합
4. Bounding Box 기반 시맨틱 클릭 좌표 계산

사용법:
    hybrid = VisionDOMHybrid()
    analysis = await hybrid.analyze(page, snapshot)
    som_image = await hybrid.render_som(page, snapshot)  # base64 PNG
"""

import base64
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .semantic_dom import SemanticDOMParser, SemanticSnapshot, BoundingBox

logger = logging.getLogger("antigravity_k.tools.vision_dom")


# ─── 데이터 모델 ─────────────────────────────────────────────────


@dataclass
class Obstacle:
    """화면 장애물 (팝업, 모달, 쿠키 배너 등)."""

    type: str  # "modal", "popup", "cookie_banner", "overlay"
    description: str
    bbox: Optional[BoundingBox] = None
    close_ref: str = ""  # 닫기 버튼의 @ref
    blocking: bool = True  # 다른 요소와의 상호작용을 방해하는지


@dataclass
class HybridAnalysis:
    """Vision + DOM 융합 분석 결과."""

    snapshot: Optional[SemanticSnapshot] = None
    screenshot_base64: str = ""
    som_image_base64: str = ""  # Set-of-Mark 마킹된 이미지
    obstacles: List[Obstacle] = field(default_factory=list)
    page_state: str = "normal"  # normal, loading, error, blocked
    viewport_size: Tuple[int, int] = (0, 0)

    def has_obstacles(self) -> bool:
        return len(self.obstacles) > 0

    def blocking_obstacles(self) -> List[Obstacle]:
        return [o for o in self.obstacles if o.blocking]

    def to_llm_summary(self) -> str:
        """LLM 컨텍스트용 분석 요약."""
        lines = [f"Page State: {self.page_state}"]

        if self.obstacles:
            lines.append(f"\n⚠️ Obstacles ({len(self.obstacles)}):")
            for obs in self.obstacles:
                close_info = f" → 닫기: {obs.close_ref}" if obs.close_ref else ""
                lines.append(f"  - [{obs.type}] {obs.description}{close_info}")

        if self.snapshot:
            lines.append(f"\nViewport: {self.viewport_size[0]}x{self.viewport_size[1]}")
            lines.append(f"Interactable: {self.snapshot.interactable_count} elements")

        return "\n".join(lines)


# ─── Set-of-Mark 렌더러 ──────────────────────────────────────────

# JS: 인터랙티브 요소 위에 번호 오버레이 추가
_SOM_OVERLAY_JS = """
(refs) => {
    // 기존 SoM 오버레이 제거
    document.querySelectorAll('.antigravity-som-marker').forEach(el => el.remove());

    const style = document.createElement('style');
    style.textContent = `
        .antigravity-som-marker {
            position: fixed !important;
            z-index: 999999 !important;
            border: 2px solid #FF4444 !important;
            background: rgba(255, 68, 68, 0.15) !important;
            pointer-events: none !important;
            box-sizing: border-box !important;
        }
        .antigravity-som-label {
            position: absolute !important;
            top: -2px !important;
            left: -2px !important;
            background: #FF4444 !important;
            color: white !important;
            font-size: 10px !important;
            font-weight: bold !important;
            font-family: monospace !important;
            padding: 1px 4px !important;
            border-radius: 2px !important;
            line-height: 1.2 !important;
        }
    `;
    document.head.appendChild(style);

    const results = [];

    for (const [refId, selector] of Object.entries(refs)) {
        try {
            let el;
            if (selector.startsWith('#')) {
                el = document.querySelector(selector);
            } else if (selector.startsWith('[')) {
                el = document.querySelector(selector);
            } else {
                el = document.querySelector(selector);
            }

            if (!el) continue;

            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) continue;

            const marker = document.createElement('div');
            marker.className = 'antigravity-som-marker';
            marker.style.left = rect.x + 'px';
            marker.style.top = rect.y + 'px';
            marker.style.width = rect.width + 'px';
            marker.style.height = rect.height + 'px';

            const label = document.createElement('span');
            label.className = 'antigravity-som-label';
            label.textContent = refId.replace('@', '');
            marker.appendChild(label);

            document.body.appendChild(marker);

            results.push({
                ref: refId,
                bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
            });
        } catch (e) {}
    }

    return results;
}
"""

# JS: SoM 오버레이 제거
_SOM_CLEANUP_JS = """
() => {
    document.querySelectorAll('.antigravity-som-marker').forEach(el => el.remove());
    const styles = document.querySelectorAll('style');
    styles.forEach(s => {
        if (s.textContent.includes('antigravity-som-marker')) s.remove();
    });
}
"""

# JS: 장애물(모달/팝업) 감지
_OBSTACLE_DETECT_JS = """
() => {
    const obstacles = [];

    // 1. 모달/다이얼로그 감지
    const dialogs = document.querySelectorAll(
        'dialog[open], [role="dialog"], [role="alertdialog"], ' +
        '.modal.show, .modal.active, [class*="modal"][class*="open"], ' +
        '[class*="popup"][class*="visible"], [class*="overlay"][class*="active"]'
    );

    for (const d of dialogs) {
        const rect = d.getBoundingClientRect();
        if (rect.width < 50 || rect.height < 50) continue;

        // 닫기 버튼 찾기
        const closeBtn = d.querySelector(
            '[aria-label="close"], [aria-label="닫기"], ' +
            'button.close, .close-btn, [class*="close"], ' +
            'button[data-dismiss], .modal-close'
        );

        let closeBtnInfo = null;
        if (closeBtn) {
            const cr = closeBtn.getBoundingClientRect();
            closeBtnInfo = {
                text: (closeBtn.textContent || '').trim().slice(0, 20),
                bbox: { x: cr.x, y: cr.y, width: cr.width, height: cr.height }
            };
        }

        obstacles.push({
            type: 'modal',
            description: (d.textContent || '').trim().slice(0, 100),
            bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
            closeBtn: closeBtnInfo,
        });
    }

    // 2. 쿠키 배너 감지
    const cookieBanners = document.querySelectorAll(
        '[class*="cookie"], [class*="consent"], [id*="cookie"], [id*="consent"], ' +
        '[class*="gdpr"], [id*="gdpr"], [class*="privacy-banner"]'
    );

    for (const banner of cookieBanners) {
        const rect = banner.getBoundingClientRect();
        const style = window.getComputedStyle(banner);
        if (rect.width < 100 || style.display === 'none') continue;

        const acceptBtn = banner.querySelector(
            'button[class*="accept"], button[class*="agree"], ' +
            '[class*="accept"], [id*="accept"], button:first-of-type'
        );

        let acceptInfo = null;
        if (acceptBtn) {
            const ar = acceptBtn.getBoundingClientRect();
            acceptInfo = {
                text: (acceptBtn.textContent || '').trim().slice(0, 20),
                bbox: { x: ar.x, y: ar.y, width: ar.width, height: ar.height }
            };
        }

        obstacles.push({
            type: 'cookie_banner',
            description: '쿠키/개인정보 동의 배너',
            bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
            closeBtn: acceptInfo,
        });
    }

    // 3. 전체 화면 오버레이 감지
    const overlays = document.querySelectorAll(
        '[class*="overlay"]:not([class*="som"]), [class*="backdrop"]'
    );

    for (const overlay of overlays) {
        const rect = overlay.getBoundingClientRect();
        const style = window.getComputedStyle(overlay);
        const isFullScreen = (
            rect.width > window.innerWidth * 0.8 &&
            rect.height > window.innerHeight * 0.8 &&
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            parseFloat(style.opacity) > 0
        );

        if (isFullScreen) {
            obstacles.push({
                type: 'overlay',
                description: '전체 화면 오버레이',
                bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                closeBtn: null,
            });
        }
    }

    return obstacles;
}
"""


class VisionDOMHybrid:
    """
    Vision + DOM 하이브리드 인식 엔진.

    스크린샷과 DOM을 동시에 분석하여:
    1. Set-of-Mark: 인터랙티브 요소에 번호 마킹
    2. 장애물 감지: 팝업/모달/쿠키 배너 자동 인식
    3. 융합 분석: 텍스트 + 시각적 맥락 통합
    """

    def __init__(self, dom_parser: SemanticDOMParser = None):
        self.dom_parser = dom_parser or SemanticDOMParser()

    # ─── 메인 분석 ────────────────────────────────────────────

    async def analyze_async(
        self, page, snapshot: SemanticSnapshot = None
    ) -> HybridAnalysis:
        """비동기: DOM + Vision 융합 분석."""
        analysis = HybridAnalysis()

        # 1. 스냅샷 (없으면 생성)
        if snapshot is None:
            snapshot = await self.dom_parser.snapshot_async(page)
        analysis.snapshot = snapshot

        # 2. 뷰포트 크기
        try:
            vp = page.viewport_size
            if vp:
                analysis.viewport_size = (vp["width"], vp["height"])
        except Exception:
            pass

        # 3. 장애물 감지
        analysis.obstacles = await self._detect_obstacles_async(page, snapshot)

        # 4. 스크린샷 (원본)
        try:
            screenshot_bytes = await page.screenshot(type="png")
            analysis.screenshot_base64 = base64.b64encode(screenshot_bytes).decode(
                "utf-8"
            )
        except Exception as e:
            logger.warning(f"[VisionDOM] Screenshot failed: {e}")

        # 5. 페이지 상태 판정
        analysis.page_state = self._judge_page_state(analysis)

        return analysis

    def analyze_sync(self, page, snapshot: SemanticSnapshot = None) -> HybridAnalysis:
        """동기: DOM + Vision 융합 분석."""
        analysis = HybridAnalysis()

        if snapshot is None:
            snapshot = self.dom_parser.snapshot_sync(page)
        analysis.snapshot = snapshot

        try:
            vp = page.viewport_size
            if vp:
                analysis.viewport_size = (vp["width"], vp["height"])
        except Exception:
            pass

        analysis.obstacles = self._detect_obstacles_sync(page, snapshot)

        try:
            screenshot_bytes = page.screenshot(type="png")
            analysis.screenshot_base64 = base64.b64encode(screenshot_bytes).decode(
                "utf-8"
            )
        except Exception as e:
            logger.warning(f"[VisionDOM] Screenshot failed: {e}")

        analysis.page_state = self._judge_page_state(analysis)
        return analysis

    # ─── Set-of-Mark (SoM) 렌더링 ────────────────────────────

    async def render_som_async(self, page, snapshot: SemanticSnapshot) -> str:
        """비동기: 스크린샷에 @ref 번호를 마킹하여 base64 PNG로 반환."""
        # 인터랙티브 요소의 ref → cssSelector 매핑
        ref_selectors = {}
        for ref, el in snapshot.elements.items():
            if el.is_interactable and el.css_selector:
                ref_selectors[ref] = el.css_selector

        if not ref_selectors:
            # 마킹할 요소가 없으면 일반 스크린샷 반환
            raw = await page.screenshot(type="png")
            return base64.b64encode(raw).decode("utf-8")

        try:
            # SoM 오버레이 추가
            await page.evaluate(_SOM_OVERLAY_JS, ref_selectors)

            # 마킹된 스크린샷 캡처
            raw = await page.screenshot(type="png")

            # 오버레이 제거
            await page.evaluate(_SOM_CLEANUP_JS)

            return base64.b64encode(raw).decode("utf-8")

        except Exception as e:
            logger.error(f"[VisionDOM] SoM rendering failed: {e}")
            raw = await page.screenshot(type="png")
            return base64.b64encode(raw).decode("utf-8")

    def render_som_sync(self, page, snapshot: SemanticSnapshot) -> str:
        """동기: SoM 마킹 스크린샷."""
        ref_selectors = {}
        for ref, el in snapshot.elements.items():
            if el.is_interactable and el.css_selector:
                ref_selectors[ref] = el.css_selector

        if not ref_selectors:
            raw = page.screenshot(type="png")
            return base64.b64encode(raw).decode("utf-8")

        try:
            page.evaluate(_SOM_OVERLAY_JS, ref_selectors)
            raw = page.screenshot(type="png")
            page.evaluate(_SOM_CLEANUP_JS)
            return base64.b64encode(raw).decode("utf-8")
        except Exception as e:
            logger.error(f"[VisionDOM] SoM rendering failed: {e}")
            raw = page.screenshot(type="png")
            return base64.b64encode(raw).decode("utf-8")

    # ─── 장애물 감지 ──────────────────────────────────────────

    async def _detect_obstacles_async(
        self, page, snapshot: SemanticSnapshot
    ) -> List[Obstacle]:
        """비동기: 장애물 감지."""
        try:
            raw_obstacles = await page.evaluate(_OBSTACLE_DETECT_JS)
            return self._parse_obstacles(raw_obstacles, snapshot)
        except Exception as e:
            logger.debug(f"[VisionDOM] Obstacle detection failed: {e}")
            return []

    def _detect_obstacles_sync(
        self, page, snapshot: SemanticSnapshot
    ) -> List[Obstacle]:
        """동기: 장애물 감지."""
        try:
            raw_obstacles = page.evaluate(_OBSTACLE_DETECT_JS)
            return self._parse_obstacles(raw_obstacles, snapshot)
        except Exception as e:
            logger.debug(f"[VisionDOM] Obstacle detection failed: {e}")
            return []

    def _parse_obstacles(
        self, raw_list: list, snapshot: SemanticSnapshot
    ) -> List[Obstacle]:
        """JS 결과를 Obstacle 객체로 변환."""
        obstacles = []
        for raw in raw_list:
            bbox = None
            if raw.get("bbox"):
                b = raw["bbox"]
                bbox = BoundingBox(
                    x=b.get("x", 0),
                    y=b.get("y", 0),
                    width=b.get("width", 0),
                    height=b.get("height", 0),
                )

            # 닫기 버튼의 @ref 찾기
            close_ref = ""
            close_btn = raw.get("closeBtn")
            if close_btn and close_btn.get("bbox"):
                cb = close_btn["bbox"]
                # 스냅샷에서 가장 가까운 요소 찾기
                close_ref = self._find_closest_ref(
                    snapshot,
                    cb.get("x", 0) + cb.get("width", 0) / 2,
                    cb.get("y", 0) + cb.get("height", 0) / 2,
                )

            obstacles.append(
                Obstacle(
                    type=raw.get("type", "unknown"),
                    description=raw.get("description", "")[:100],
                    bbox=bbox,
                    close_ref=close_ref,
                    blocking=raw.get("type") in ("modal", "overlay"),
                )
            )

        return obstacles

    def _find_closest_ref(self, snapshot: SemanticSnapshot, x: float, y: float) -> str:
        """좌표에 가장 가까운 요소의 @ref를 반환."""
        best_ref = ""
        best_dist = float("inf")

        for ref, el in snapshot.elements.items():
            if not el.bbox:
                continue
            cx, cy = el.bbox.center
            dist = ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_ref = ref

        return best_ref if best_dist < 50 else ""

    def _judge_page_state(self, analysis: HybridAnalysis) -> str:
        """페이지 상태를 판정합니다."""
        if analysis.blocking_obstacles():
            return "blocked"
        if analysis.snapshot and analysis.snapshot.total_count == 0:
            return "loading"
        return "normal"
