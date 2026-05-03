"""
Code Intel 파이프라인 통합 테스트
================================
Antigravity-K 자체 코드베이스를 분석하여 전 파이프라인 동작을 검증합니다.
"""
import sys
import os
import json

# 프로젝트 src를 PYTHONPATH에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def main():
    print("=" * 60)
    print("  Code Intel Pipeline 통합 테스트")
    print("=" * 60)
    
    repo_path = os.path.dirname(__file__)  # antigravity-k 루트
    
    # 1. 파이프라인 임포트 테스트
    print("\n[1/6] 모듈 임포트 테스트...")
    try:
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline
        from antigravity_k.engine.code_intel.hybrid_search import HybridSearchEngine
        from antigravity_k.engine.code_intel.impact_analyzer import ImpactAnalyzer
        from antigravity_k.engine.code_intel.staleness import StalenessDetector
        from antigravity_k.engine.code_intel.knowledge_graph import KnowledgeGraph, NodeType
        print("  ✅ 모든 모듈 임포트 성공")
    except ImportError as e:
        print(f"  ❌ 임포트 실패: {e}")
        return
    
    # 2. 파이프라인 실행
    print("\n[2/6] 파이프라인 실행 (자체 코드베이스 분석)...")
    pipeline = CodeIndexPipeline()
    result = pipeline.run(repo_path, force=True)
    
    print(f"  상태: {result['status']}")
    print(f"  소요 시간: {result['elapsed_seconds']}s")
    print(f"  스캔된 파일: {result['phases']['scan']['total_files']}")
    print(f"  언어: {result['phases']['scan']['languages']}")
    print(f"  추출된 심볼: {result['phases']['parse']['symbols']}")
    print(f"  호출 관계: {result['phases']['parse']['calls']}")
    print(f"  해석된 호출: {result['phases']['resolve']['resolved_calls']}")
    print(f"  커뮤니티: {result['phases']['cluster']['communities']}")
    print(f"  프로세스: {result['phases']['cluster']['processes']}")
    
    # 3. 그래프 통계
    print("\n[3/6] 그래프 통계...")
    stats = pipeline.graph.stats()
    print(f"  총 노드: {stats['total_nodes']}")
    print(f"  총 관계: {stats['total_edges']}")
    for nt, count in stats['node_types'].items():
        print(f"    {nt}: {count}")
    
    # 4. 하이브리드 검색 테스트
    print("\n[4/6] 하이브리드 검색 테스트...")
    search = HybridSearchEngine(pipeline.graph)
    search.build_index()
    
    queries = ["orchestrator", "knowledge graph", "pipeline"]
    for q in queries:
        results = search.search(q, top_k=3)
        print(f"  '{q}' → {len(results)}개 결과")
        for r in results[:2]:
            print(f"    - {r.get('name', '?')} ({r.get('node_type', '?')}) @ {r.get('file', '?')}")
    
    # 5. 영향도 분석 테스트
    print("\n[5/6] 영향도 분석 테스트...")
    analyzer = ImpactAnalyzer(pipeline.graph)
    # 첫 번째 Function 노드로 테스트
    functions = pipeline.graph.get_nodes_by_type(NodeType.FUNCTION)
    if functions:
        target = functions[0]
        impact = analyzer.analyze(target['id'])
        print(f"  대상: {target.get('name', '?')} ({target.get('file', '?')})")
        print(f"  상류: {len(impact.get('upstream', []))}개")
        print(f"  하류: {len(impact.get('downstream', []))}개")
        print(f"  위험도: {impact.get('risk_level', '?')}")
        print(f"  Blast Radius: {impact.get('blast_radius', 0)}")
    
    # 6. Staleness 테스트
    print("\n[6/6] Staleness 감지 테스트...")
    detector = StalenessDetector(pipeline.repo_manager)
    staleness = detector.check(repo_path)
    print(f"  상태: {staleness.get('status', '?')}")
    print(f"  현재 커밋: {staleness.get('current_commit', '?')}")
    print(f"  인덱스 커밋: {staleness.get('indexed_commit', '?')}")
    
    print("\n" + "=" * 60)
    print("  ✅ 모든 테스트 통과!")
    print("=" * 60)


if __name__ == "__main__":
    main()
