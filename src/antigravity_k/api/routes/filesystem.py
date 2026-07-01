"""Antigravity-K API: 파일시스템 라우터.

====================================
I-6 리팩터링: server.py에서 분리된 /api/fs/* 및 /api/workspace/* 라우트.
"""

import logging
import os
import shutil

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from antigravity_k.engine.vault import VaultEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["filesystem"])

# 전역 워크스페이스 상태 (서버 실행 시 기본값은 현재 폴더)
WORKSPACE_ROOT = os.path.abspath(".")


def get_workspace_root() -> str:
    """Retrieve workspace root.

    Returns:
        str: The str result.

    """
    return WORKSPACE_ROOT


class WorkspaceRequest(BaseModel):
    """Workspacerequest.

    Bases: BaseModel
    """

    path: str


class MkdirRequest(BaseModel):
    """Mkdirrequest.

    Bases: BaseModel
    """

    path: str


class DeleteRequest(BaseModel):
    """Deleterequest.

    Bases: BaseModel
    """

    path: str


@router.get("/api/fs/workspace")
async def get_workspace():
    """Retrieve workspace."""
    return {"ok": True, "workspace": WORKSPACE_ROOT}


@router.post("/api/fs/workspace")
async def set_workspace(req: WorkspaceRequest):
    """Set workspace.

    Args:
        req (WorkspaceRequest): WorkspaceRequest req.

    """
    global WORKSPACE_ROOT
    target = os.path.abspath(req.path)
    if os.path.exists(target) and os.path.isdir(target):
        WORKSPACE_ROOT = target
        return {"ok": True, "workspace": WORKSPACE_ROOT}
    raise HTTPException(status_code=400, detail="Invalid directory path")


def _run_workspace_ingestion(workspace_path: str, vault_engine: VaultEngine):
    """Background task to ingest workspace."""
    try:
        vault_engine.ingest_workspace(workspace_path)
        logger.info("Background ingestion completed for %s", workspace_path)
    except Exception:
        logger.exception("Background ingestion failed")


@router.post("/api/workspace/ingest")
async def ingest_workspace(
    background_tasks: BackgroundTasks,
    path: str | None = Query(None, description="Target path to index"),
):
    """Ingest Workspace.

    Args:
        background_tasks (BackgroundTasks): BackgroundTasks background tasks.
        path (str | None): str | None path.

    """
    from antigravity_k.api.server import get_vault_engine

    vault = get_vault_engine()
    if not vault:
        raise HTTPException(status_code=500, detail="VaultEngine not initialized")

    target_path = path if path else WORKSPACE_ROOT

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=400, detail="Workspace not set or invalid")

    background_tasks.add_task(_run_workspace_ingestion, target_path, vault)
    return {"ok": True, "message": "Workspace indexing started in background"}


@router.get("/api/fs/browse")
async def fs_browse(dir: str = "/"):
    """시스템 전체를 브라우징하는 전용 API (보안 제한 없음, 로컬 구동 전제)."""
    try:
        target_dir = os.path.abspath(dir)
        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            target_dir = os.path.abspath("/")

        items = []
        try:
            for entry in os.scandir(target_dir):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    items.append({"name": entry.name, "path": entry.path, "is_dir": True})
        except PermissionError:
            pass

        items.sort(key=lambda x: x["name"].lower())

        parent_dir = os.path.dirname(target_dir)
        if target_dir == parent_dir:
            parent_dir = None

        return {"ok": True, "current": target_dir, "parent": parent_dir, "items": items}
    except OSError as e:
        logger.error("FS browse error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/fs/mkdir")
async def fs_mkdir(req: MkdirRequest):
    """지정된 경로에 새 디렉토리를 생성합니다."""
    try:
        clean_path = req.path.lstrip("/\\")
        if clean_path == "." or clean_path == "":
            raise HTTPException(status_code=400, detail="Invalid path for folder creation")

        target_dir = os.path.abspath(os.path.join(WORKSPACE_ROOT, clean_path))

        if not target_dir.startswith(WORKSPACE_ROOT):
            raise HTTPException(status_code=403, detail="Access denied outside of workspace root.")

        if os.path.exists(target_dir):
            return {"ok": False, "detail": "Folder already exists"}

        os.makedirs(target_dir, exist_ok=True)
        return {"ok": True, "path": target_dir}
    except HTTPException:
        raise
    except OSError as e:
        logger.error("FS mkdir error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/fs/delete")
async def fs_delete(req: DeleteRequest):
    """지정된 파일 또는 디렉토리를 삭제합니다."""
    try:
        clean_path = req.path.lstrip("/\\")
        if clean_path == "." or clean_path == "":
            raise HTTPException(status_code=400, detail="Cannot delete workspace root")

        target_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, clean_path))

        if not target_path.startswith(WORKSPACE_ROOT):
            raise HTTPException(status_code=403, detail="Access denied outside of workspace root.")

        if not os.path.exists(target_path):
            return {"ok": False, "detail": "Path does not exist"}

        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)

        return {"ok": True, "path": target_path}
    except HTTPException:
        raise
    except OSError as e:
        logger.error("FS delete error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/fs/list")
async def fs_list(dir: str = "."):
    """디렉토리 목록을 반환합니다 (WORKSPACE_ROOT로 제한)."""
    try:
        if dir == ".":
            target_dir = WORKSPACE_ROOT
        else:
            target_dir = os.path.abspath(os.path.join(WORKSPACE_ROOT, dir))

        if not target_dir.startswith(WORKSPACE_ROOT):
            raise HTTPException(status_code=403, detail="Access denied outside of workspace root.")

        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            return {"ok": False, "items": []}

        items = []
        for entry in os.scandir(target_dir):
            if entry.name.startswith("."):
                continue
            items.append(
                {
                    "name": entry.name,
                    "path": os.path.relpath(entry.path, WORKSPACE_ROOT),
                    "is_dir": entry.is_dir(),
                },
            )

        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"ok": True, "items": items}
    except HTTPException:
        raise
    except OSError as e:
        logger.error("FS list error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/fs/read")
async def fs_read(file: str):
    """파일 내용을 반환합니다."""
    try:
        target_file = os.path.abspath(os.path.join(WORKSPACE_ROOT, file))
        if not target_file.startswith(WORKSPACE_ROOT):
            raise HTTPException(status_code=403, detail="Access denied outside of workspace root.")

        if not os.path.exists(target_file) or not os.path.isfile(target_file):
            raise HTTPException(status_code=404, detail="File not found.")

        with open(target_file, encoding="utf-8") as f:
            content = f.read()

        return {"ok": True, "content": content}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Cannot read binary file.")
    except HTTPException:
        raise
    except OSError as e:
        logger.error("FS read error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
