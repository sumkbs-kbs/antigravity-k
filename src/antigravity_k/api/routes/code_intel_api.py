"""Code Intel API — 코드 저장소 인덱싱·하이브리드 검색·영향도 분석."""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
logger = logging.getLogger("antigravity_k.api.routes.code_intel")


@router.post("/api/code-intel/index")
async def code_intel_index(request: Request):
    """코드 저장소를 인덱싱합니다."""
    try:
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline

        data = await request.json()
        repo_path = data.get("repo_path", ".")
        force = data.get("force", False)
        pipeline = CodeIndexPipeline()
        result = pipeline.run(repo_path, force=force)
        return result
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Code Intel 모듈이 설치되지 않았습니다 (pip install networkx rank-bm25)",
        )
    except (json.JSONDecodeError, FileNotFoundError, ValueError, RuntimeError) as e:
        logger.error("Code Intel index error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/code-intel/search")
async def code_intel_search(q: str, repo_path: str, top_k: int = 10):
    """코드 심볼을 하이브리드 검색합니다."""
    try:
        from antigravity_k.engine.code_intel.hybrid_search import HybridSearchEngine
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline

        pipeline = CodeIndexPipeline()
        loaded = pipeline.load_existing(repo_path)
        if not loaded:
            raise HTTPException(
                status_code=404,
                detail=f"'{repo_path}'의 인덱스가 없습니다. 먼저 인덱싱해주세요.",
            )
        search = HybridSearchEngine(pipeline.graph)
        search.build_index()
        results = search.search(q, top_k=top_k)
        return {"query": q, "results": results}
    except HTTPException:
        raise
    except (ValueError, KeyError, RuntimeError) as e:
        logger.error("Code Intel search error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/code-intel/impact")
async def code_intel_impact(request: Request):
    """심볼의 Blast Radius 영향도를 분석합니다."""
    try:
        from antigravity_k.engine.code_intel.impact_analyzer import ImpactAnalyzer
        from antigravity_k.engine.code_intel.pipeline import CodeIndexPipeline

        data = await request.json()
        repo_path = data.get("repo_path", ".")
        symbol_id = data.get("symbol_id", "")
        max_depth = data.get("max_depth", 5)
        pipeline = CodeIndexPipeline()
        loaded = pipeline.load_existing(repo_path)
        if not loaded:
            raise HTTPException(status_code=404, detail=f"'{repo_path}'의 인덱스가 없습니다.")
        analyzer = ImpactAnalyzer(pipeline.graph)
        result = analyzer.analyze(symbol_id, max_depth=max_depth)
        return result
    except HTTPException:
        raise
    except (ValueError, KeyError, RuntimeError) as e:
        logger.error("Code Intel impact error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
