#!/usr/bin/env python3
"""
실전 벤치마크 실행 스크립트.
collective-council vs 개별 모델 A/B 비교를 수행합니다.
"""
import sys
import os
import logging

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("benchmark_runner")


def main():
    from antigravity_k.engine.model_registry import ModelRegistry
    from antigravity_k.engine.model_manager import ModelManager
    from antigravity_k.engine.benchmark_harness import BenchmarkHarness
    from antigravity_k.engine.benchmark_cases import get_suite

    # 1. 모델 매니저 초기화
    logger.info("=== ModelManager 초기화 ===")
    registry = ModelRegistry()
    manager = ModelManager(registry)

    # 2. 벤치마크 하네스 생성
    harness = BenchmarkHarness(model_manager=manager)

    # 3. 비교 대상 결정
    # collective-council + 개별 모델 3개
    targets = harness._default_targets()
    logger.info(f"비교 대상: {targets}")

    # 4. 먼저 sim-001 단일 과제로 파이프라인 검증
    logger.info("\n" + "=" * 60)
    logger.info("Phase 1: sim-001 파이프라인 검증")
    logger.info("=" * 60)

    cases = get_suite("sim-001")
    for case in cases:
        logger.info(f"과제: {case.id} — {case.description} (난이도 {case.difficulty})")

    try:
        results = harness.run_case(cases[0], targets=targets)
        for r in results:
            grade_icon = {
                "excellent": "🟢",
                "good": "🔵",
                "retry": "🟡",
                "fail": "🔴",
            }.get(r.quality_grade, "⚪")
            logger.info(
                f"  {grade_icon} {r.target}: "
                f"품질={r.quality_score:.0%} ({r.quality_grade}), "
                f"시간={r.latency_ms/1000:.1f}s, "
                f"토큰(out)={r.tokens_out}"
            )
            if r.error:
                logger.warning(f"    에러: {r.error}")
    except Exception as e:
        logger.error(f"sim-001 실행 실패: {e}", exc_info=True)
        return

    # 5. 비교표 출력
    logger.info("\n" + "=" * 60)
    logger.info("sim-001 비교표:")
    logger.info("=" * 60)
    table = harness.comparison_table("sim-001")
    print(table)

    # 6. 전체 simple 스위트 실행 (sim-001 + sim-002)
    logger.info("\n" + "=" * 60)
    logger.info("Phase 2: simple 카테고리 전체 실행")
    logger.info("=" * 60)

    try:
        report = harness.run_suite("simple", targets=targets)
        logger.info(f"완료: {len(report.results)}건, {report.duration_s:.1f}s")
    except Exception as e:
        logger.error(f"simple 스위트 실행 실패: {e}", exc_info=True)

    # 7. 최종 비교표 출력
    logger.info("\n" + "=" * 60)
    logger.info("최종 비교표:")
    logger.info("=" * 60)
    table = harness.comparison_table("simple")
    print(table)

    logger.info("\n✅ 벤치마크 완료! 결과: data/benchmark_results.json")


if __name__ == "__main__":
    main()
