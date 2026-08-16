"""Unit tests for HybridReranker."""

from antigravity_k.engine.hybrid_reranker import HybridReranker, SearchCandidate


def test_rrf_rank_fusion():
    c1 = SearchCandidate(chunk_id="chunk_1", file_path="auth.py", content="def verify_jwt()")
    c2 = SearchCandidate(chunk_id="chunk_2", file_path="db.py", content="def connect_sql()")
    c3 = SearchCandidate(chunk_id="chunk_3", file_path="config.py", content="PORT = 8000")

    # Ranking list 1: Lexical (c1, c2, c3)
    ranking_lexical = [c1, c2, c3]
    # Ranking list 2: Vector (c1, c3, c2)
    ranking_vector = [c1, c3, c2]

    fused = HybridReranker.fuse_rankings([ranking_lexical, ranking_vector], top_n=2)
    assert len(fused) == 2
    # c1 is ranked #1 in both lists, so its RRF score is highest
    assert fused[0].chunk_id == "chunk_1"
    assert fused[0].score > fused[1].score
