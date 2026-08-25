"""Vault API — Wiki 노트 CRUD·검색·동기화 엔드포인트."""

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from antigravity_k.api.dependencies import get_vault_engine
from antigravity_k.config import config
from antigravity_k.engine.audit_logger import get_audit_logger
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.tool_contracts import ToolInvocation, ToolSpec

router = APIRouter()
logger = logging.getLogger("antigravity_k.api.routes.vault")


def _permission_gate() -> PermissionGate:
    return PermissionGate(project_root=str(config.paths.project_root), mode="auto-pilot")


def _require_allowed(tool_name: str, args: dict[str, Any], risk_level: str) -> None:
    decision = _permission_gate().decide(
        ToolInvocation(ToolSpec(name=tool_name, risk_level=risk_level, category="api"), args),
    )
    if decision.permission != Permission.ALLOW:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied for {tool_name}: {decision.permission.value}",
        )


@router.get("/api/vault/config")
def vault_config(engine: VaultEngine = Depends(get_vault_engine)):
    """현재 Vault 설정 조회."""
    if not engine:
        return {"ok": False, "vault_path": None, "message": "VaultEngine not available"}
    return {"ok": True, "vault_path": str(engine.vault_path)}


@router.post("/api/vault/config")
async def set_vault_config(request: Request):
    """Vault 경로를 동적으로 변경 (Wiki + Chat 공유용).

    새 VaultEngine을 생성하고 dependencies.py의 싱글톤을 업데이트합니다.
    이후 /api/vault/tree 등의 모든 Vault API가 새 경로를 사용합니다.
    """
    body = await request.json()
    new_path = body.get("vault_path", "")
    if not new_path:
        raise HTTPException(status_code=400, detail="'vault_path' is required")
    target = os.path.abspath(new_path)
    _require_allowed("set_vault_config", {"vault_path": target}, "critical")
    if not os.path.isdir(target):
        # 디렉토리가 없으면 생성 시도
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as e:
            raise HTTPException(status_code=400, detail=f"Cannot create directory: {e}")
    new_engine: VaultEngine
    try:
        new_engine = VaultEngine(vault_path=target, sync_rag=True)
    except (OSError, RuntimeError, ValueError) as e:
        logger.warning("Vault 재초기화 실패 (RAG 비활성): %s", e)
        try:
            new_engine = VaultEngine(vault_path=target, sync_rag=False)
        except (OSError, RuntimeError, ValueError) as e2:
            raise HTTPException(status_code=500, detail=f"Vault init failed: {e2}")

    # 싱글톤 업데이트 — 이후 모든 Vault API가 새 경로를 사용
    import antigravity_k.api.dependencies as deps

    deps.vault_engine = new_engine

    logger.info("Vault 경로 변경됨: %s", target)
    return {"ok": True, "vault_path": str(new_engine.vault_path)}


@router.get("/api/vault/tree")
def vault_tree(engine: VaultEngine = Depends(get_vault_engine)):
    """Return the vault directory tree as a nested JSON structure."""
    if not engine:
        raise HTTPException(status_code=503, detail="VaultEngine not available")

    def build_tree(base_path: Path, rel_prefix: str = "") -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            entries = sorted(base_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return items
        for entry in entries:
            if entry.name.startswith("."):
                continue
            rel = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
            if entry.is_dir():
                children = build_tree(entry, rel)
                items.append(
                    {
                        "name": entry.name,
                        "path": rel,
                        "type": "folder",
                        "children": children,
                    },
                )
            elif entry.suffix.lower() in (".md", ".txt", ".yaml", ".yml"):
                items.append(
                    {
                        "name": entry.name,
                        "path": rel,
                        "type": "file",
                        "size": entry.stat().st_size,
                    },
                )
        return items

    tree = build_tree(engine.vault_path)
    return {"tree": tree, "vault_path": str(engine.vault_path)}


@router.get("/api/vault/read")
def vault_read(path: str, engine: VaultEngine = Depends(get_vault_engine)):
    """Read a note from the vault. Returns metadata + content."""
    if not engine:
        raise HTTPException(status_code=503, detail="VaultEngine not available")
    # Security: prevent path traversal
    clean = Path(path)
    if ".." in clean.parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    try:
        metadata, content = engine.read_note(path)
        return {"path": path, "metadata": metadata, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/vault/write")
async def vault_write(request: Request, engine: VaultEngine = Depends(get_vault_engine)):
    """Create or update a note in the vault."""
    if not engine:
        raise HTTPException(status_code=503, detail="VaultEngine not available")
    body = await request.json()
    path = body.get("path", "")
    content = body.get("content", "")
    metadata = body.get("metadata", {})
    if not path:
        raise HTTPException(status_code=400, detail="'path' is required")
    clean = Path(path)
    if ".." in clean.parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    _require_allowed("vault_write", {"path": path}, "medium")
    try:
        engine.write_note(path, metadata, content, commit_message=f"Wiki edit: {path}")
        return {"ok": True, "path": path}
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/vault/sync")
async def vault_sync(engine: VaultEngine = Depends(get_vault_engine)):
    """현재 Vault 상태를 Git 스냅샷으로 저장."""
    if not engine:
        raise HTTPException(status_code=503, detail="VaultEngine not available")
    _require_allowed("vault_sync", {}, "high")
    try:
        commit_hash = engine.create_snapshot("Manual sync via Command Palette")
        return {"ok": True, "commit": commit_hash}
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/notes/search")
def search_notes(q: str, engine: VaultEngine = Depends(get_vault_engine)):
    """Search for notes.

    Args:
        q (str): str q.
        engine (VaultEngine): VaultEngine engine.

    """
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    audit = get_audit_logger()
    audit.log_event("search_notes", {"query": q})

    try:
        # 1. Semantic search via RAG (ChromaDB)
        semantic_results = engine.vector_store.search(q, n_results=5)

        # 2. Keyword search via Vault text match
        keyword_results = engine.search_notes(q)

        return {
            "query": q,
            "semantic_results": semantic_results,
            "keyword_results": keyword_results,
        }
    except (ValueError, KeyError) as e:
        logger.error("Search error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
