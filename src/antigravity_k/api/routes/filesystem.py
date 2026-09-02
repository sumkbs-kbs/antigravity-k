"""Antigravity-K API: 파일시스템 라우터.

====================================
I-6 리팩터링: server.py에서 분리된 /api/fs/* 및 /api/workspace/* 라우트.
"""

import asyncio
import logging
import os
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Protocol, TypedDict, runtime_checkable

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from antigravity_k.api.path_security import PathSecurityError, resolve_allowed_path
from antigravity_k.engine.api_cache import TAG_FILESYSTEM, api_cache, cached
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.tools.tool_contracts import Permission, ToolInvocation, ToolSpec

logger = logging.getLogger(__name__)

router = APIRouter(tags=["filesystem"])

# 전역 워크스페이스 상태 (서버 실행 시 기본값은 현재 폴더)
WORKSPACE_ROOT = os.path.abspath(".")


class FileMatch(TypedDict):
    line: int
    content: str


class FileSearchResult(TypedDict):
    file_path: str
    file_name: str
    matches: list[FileMatch]
    match_count: int


class WorkspaceResponse(TypedDict):
    ok: bool
    workspace: str


class FilesystemListResponse(TypedDict):
    ok: bool
    items: list[dict[str, str | bool]]


class FilesystemSearchResponse(TypedDict):
    ok: bool
    query: str
    results: list[FileSearchResult]
    total_files: int
    total_matches: int


class _PermissionGateLike(Protocol):
    def set_project_root(self, new_root: str) -> None: ...


@runtime_checkable
class _ToolExecutorLike(Protocol):
    permission_gate: _PermissionGateLike


class _OrchestratorContextLike(Protocol):
    tool_executor: _ToolExecutorLike


@runtime_checkable
class _OrchestratorLike(Protocol):
    ctx: _OrchestratorContextLike


def get_workspace_root() -> str:
    """Retrieve workspace root.

    Returns:
        str: The str result.

    """
    return WORKSPACE_ROOT


def _permission_gate() -> PermissionGate:
    return PermissionGate(project_root=WORKSPACE_ROOT, mode="auto-pilot")


def _require_allowed(tool_name: str, args: Mapping[str, str], risk_level: str) -> None:
    decision = _permission_gate().decide(
        ToolInvocation(ToolSpec(name=tool_name, risk_level=risk_level, category="api"), args),
    )
    if decision.permission != Permission.ALLOW:
        raise HTTPException(status_code=403, detail=f"Permission denied for {tool_name}: {decision.permission.value}")


def _resolve_workspace_path(path: str) -> str:
    root = Path(WORKSPACE_ROOT).resolve()
    raw_path = Path(path).expanduser()
    candidate = (raw_path if raw_path.is_absolute() else root / raw_path).resolve()
    try:
        _ = candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access denied outside of workspace root.") from exc
    return str(candidate)


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


class WriteFileRequest(BaseModel):
    """Writefilerequest.

    Bases: BaseModel
    """

    path: str
    content: str


class RenameRequest(BaseModel):
    """Renamerequest.

    Bases: BaseModel
    """

    path: str
    new_name: str


class SearchRequest(BaseModel):
    """Searchrequest.

    Bases: BaseModel
    """

    query: str
    max_results: int = 100


@router.get("/api/fs/workspace")
async def get_workspace():
    """Retrieve workspace."""
    return {"ok": True, "workspace": WORKSPACE_ROOT}


@router.post("/api/fs/workspace")
async def set_workspace(req: WorkspaceRequest):
    """Set workspace — 프로젝트 전환 시 PermissionGate와 config를 함께 업데이트.

    에이전트가 새 프로젝트 폴더 내에서만 작업하도록 격리합니다.
    """
    try:
        target = str(resolve_allowed_path(req.path))
    except PathSecurityError as exc:
        raise HTTPException(status_code=403, detail="Workspace is outside the configured workspace roots.") from exc
    _require_allowed("set_workspace", {"path": target}, "critical")
    if not (os.path.exists(target) and os.path.isdir(target)):
        # 디렉토리가 없으면 생성
        try:
            os.makedirs(target, exist_ok=True)
        except OSError:
            raise HTTPException(status_code=400, detail=f"Invalid directory: {target}")

    globals()["WORKSPACE_ROOT"] = target

    # PermissionGate 업데이트 — 에이전트 파일 접근을 새 프로젝트로 제한
    try:
        import antigravity_k.api.dependencies as deps

        orchestrator = deps.__dict__.get("_orchestrator")
        if isinstance(orchestrator, _OrchestratorLike):
            tool_executor = orchestrator.ctx.tool_executor
            tool_executor.permission_gate.set_project_root(target)
            logger.info("PermissionGate project_root 업데이트: %s", target)
    except Exception:
        logger.warning("PermissionGate 업데이트 실패 (non-critical)", exc_info=True)

    # config의 project_root 업데이트
    try:
        from antigravity_k.config import config

        config.paths.project_root = Path(target)
    except Exception:
        logger.warning("config.paths.project_root 업데이트 실패 (non-critical)", exc_info=True)

    logger.info("Workspace 변경: %s", target)
    return {"ok": True, "workspace": WORKSPACE_ROOT}


# ─── 프로젝트 관리 API ──────────────────────────────────────────


@router.get("/api/projects")
async def list_projects():
    """등록된 프로젝트 목록을 반환합니다. localStorage 기반 (프론트엔드에서 관리)."""
    return {"ok": True, "workspace": WORKSPACE_ROOT}


@router.post("/api/projects/switch")
async def switch_project(req: WorkspaceRequest):
    """프로젝트를 전환합니다 — workspace, PermissionGate, config를 모두 업데이트."""
    return await set_workspace(req)


def _run_workspace_ingestion(workspace_path: str, vault_engine: VaultEngine) -> None:
    """Background task to ingest workspace."""
    try:
        _ = vault_engine.ingest_workspace(workspace_path)
        logger.info("Background ingestion completed for %s", workspace_path)
    except Exception:
        logger.exception("Background ingestion failed")


@router.post("/api/workspace/ingest")
async def ingest_workspace(
    background_tasks: BackgroundTasks,
    path: Annotated[str | None, Query(description="Target path to index")] = None,
):
    """Ingest Workspace.

    Args:
        background_tasks (BackgroundTasks): BackgroundTasks background tasks.
        path (str | None): str | None path.

    """
    from antigravity_k.api.dependencies import get_vault_engine

    vault = get_vault_engine()
    if not vault:
        raise HTTPException(status_code=500, detail="VaultEngine not initialized")

    try:
        target_path = str(resolve_allowed_path(path if path else WORKSPACE_ROOT))
    except PathSecurityError as exc:
        raise HTTPException(
            status_code=403,
            detail="Ingestion path is outside the configured workspace roots.",
        ) from exc

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=400, detail="Workspace not set or invalid")

    background_tasks.add_task(_run_workspace_ingestion, target_path, vault)
    return {"ok": True, "message": "Workspace indexing started in background"}


@router.get("/api/fs/browse")
@cached(ttl=15, tags=[TAG_FILESYSTEM])
async def fs_browse(dir: str = "."):
    """시스템 전체를 브라우징하는 전용 API (보안 제한 없음, 로컬 구동 전제)."""
    try:
        target_dir = _resolve_workspace_path(dir)
        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            raise HTTPException(status_code=404, detail="Directory not found")
        _require_allowed("fs_browse", {"path": target_dir}, "safe")

        items: list[dict[str, str | bool]] = []
        try:
            for entry in os.scandir(target_dir):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    items.append({"name": entry.name, "path": entry.path, "is_dir": True})
        except PermissionError:
            logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)

        items.sort(key=lambda x: str(x["name"]).lower())

        parent_dir: str | None = os.path.dirname(target_dir)
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
        if req.path in {".", ""}:
            raise HTTPException(status_code=400, detail="Invalid path for folder creation")

        target_dir = _resolve_workspace_path(req.path)
        _require_allowed("fs_mkdir", {"path": target_dir}, "medium")

        if os.path.exists(target_dir):
            return {"ok": False, "detail": "Folder already exists"}

        os.makedirs(target_dir, exist_ok=True)
        # Invalidate filesystem cache on directory creation
        _ = await api_cache.invalidate_tag(TAG_FILESYSTEM)
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
        if req.path in {".", ""}:
            raise HTTPException(status_code=400, detail="Cannot delete workspace root")

        target_path = _resolve_workspace_path(req.path)
        _require_allowed("fs_delete", {"path": target_path}, "high")

        if not os.path.exists(target_path):
            return {"ok": False, "detail": "Path does not exist"}

        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)

        # Invalidate filesystem cache on delete
        _ = await api_cache.invalidate_tag(TAG_FILESYSTEM)
        return {"ok": True, "path": target_path}
    except HTTPException:
        raise
    except OSError as e:
        logger.error("FS delete error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/fs/list")
@cached(ttl=15, tags=[TAG_FILESYSTEM])
async def fs_list(dir: str = ".") -> FilesystemListResponse:
    """디렉토리 목록을 반환합니다 (WORKSPACE_ROOT로 제한)."""
    try:
        target_dir = _resolve_workspace_path(dir)
        _require_allowed("fs_list", {"path": target_dir}, "safe")

        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            return {"ok": False, "items": []}

        items: list[dict[str, str | bool]] = []
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

        items.sort(key=lambda x: (not x["is_dir"], str(x["name"]).lower()))
        return {"ok": True, "items": items}
    except HTTPException:
        raise
    except OSError as e:
        logger.error("FS list error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/fs/write")
async def fs_write(req: WriteFileRequest):
    """파일 내용을 저장합니다 (POST /api/fs/write)."""
    try:
        target_file = _resolve_workspace_path(req.path)
        _require_allowed("fs_write", {"path": target_file}, "medium")

        target_dir = os.path.dirname(target_file)
        os.makedirs(target_dir, exist_ok=True)

        _ = await asyncio.to_thread(
            Path(target_file).write_text,
            req.content,
            encoding="utf-8",
        )

        logger.info("파일 저장 완료: %s", req.path)
        # Invalidate filesystem cache on write
        _ = await api_cache.invalidate_tag(TAG_FILESYSTEM)
        return {"ok": True, "path": req.path}
    except OSError as e:
        logger.error("FS write error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/fs/rename")
async def fs_rename(req: RenameRequest):
    """파일/폴더 이름을 변경합니다 (POST /api/fs/rename)."""
    try:
        target_path = _resolve_workspace_path(req.path)
        new_path = _resolve_workspace_path(os.path.join(os.path.dirname(target_path), req.new_name))
        _require_allowed("fs_rename", {"path": target_path, "new_path": new_path}, "medium")

        if not os.path.exists(target_path):
            raise HTTPException(status_code=404, detail="Path does not exist")

        if os.path.exists(new_path):
            return {"ok": False, "detail": "A file or folder with that name already exists"}

        os.rename(target_path, new_path)
        logger.info("파일 이름 변경: %s → %s", req.path, req.new_name)
        _ = await api_cache.invalidate_tag(TAG_FILESYSTEM)

        rel_new_path = os.path.relpath(new_path, WORKSPACE_ROOT)
        return {"ok": True, "path": rel_new_path, "old_path": req.path, "new_name": req.new_name}
    except HTTPException:
        raise
    except OSError as e:
        logger.error("FS rename error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── 글로벌 무시 패턴 (바이너리, .git, node_modules 등) ────────────
_IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "coverage",
    "target",
    "vendor",
    "bower_components",
}

_IGNORE_EXTS = {
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    ".o",
    ".a",
    ".lib",
    ".obj",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wav",
    ".min.js",
    ".min.css",
    ".bundle.js",
}

_MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB limit per file


def _should_ignore(path: str) -> bool:
    """Check if a path should be ignored during search."""
    name = os.path.basename(path)
    parts = path.replace(os.sep, "/").split("/")
    if any(p.startswith(".") and p not in (".", "..", ".env", ".env.example", ".gitignore") for p in parts):
        return True
    if any(p in _IGNORE_DIRS for p in parts):
        return True
    ext = os.path.splitext(name)[1].lower()
    return ext in _IGNORE_EXTS


def _search_in_file(file_path: str, query: str, max_matches: int = 50) -> list[FileMatch]:
    """Search for query in a single file. Returns list of {line, content}."""
    matches: list[FileMatch] = []
    try:
        size = os.path.getsize(file_path)
        if size > _MAX_FILE_SIZE or size == 0:
            return []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                if query.lower() in line.lower():
                    matches.append(
                        {
                            "line": line_no,
                            "content": line.rstrip("\n"),
                        }
                    )
                    if len(matches) >= max_matches:
                        break
    except (OSError, UnicodeDecodeError):
        pass
    return matches


def _walk_and_search(root: str, query: str, max_results: int = 100) -> list[FileSearchResult]:
    """Walk directory tree and search files. Returns list of {file_path, file_name, matches}."""
    results: list[FileSearchResult] = []
    matched_files = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip ignored directories in-place
            dirnames[:] = [d for d in dirnames if not _should_ignore(os.path.join(dirpath, d))]

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)

                if _should_ignore(full_path):
                    continue

                matches = _search_in_file(full_path, query)
                if matches:
                    rel_path = os.path.relpath(full_path, WORKSPACE_ROOT)
                    results.append(
                        {
                            "file_path": rel_path,
                            "file_name": filename,
                            "matches": matches,
                            "match_count": len(matches),
                        }
                    )
                    matched_files += 1
                    if matched_files >= max_results:
                        return results
    except OSError:
        pass
    return results


@router.post("/api/fs/search")
async def fs_search(req: SearchRequest) -> FilesystemSearchResponse:
    """워크스페이스 파일 내용에서 검색합니다 (POST /api/fs/search).

    Case-insensitive, binary/.git/node_modules 제외, 1MB 파일 제한.
    """
    query = req.query.strip()
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    try:
        results = _walk_and_search(WORKSPACE_ROOT, query, max_results=req.max_results)
        total_matches = sum(r["match_count"] for r in results)
        return {
            "ok": True,
            "query": query,
            "results": results,
            "total_files": len(results),
            "total_matches": total_matches,
        }
    except OSError as e:
        logger.error("FS search error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/fs/read")
@cached(ttl=30, tags=[TAG_FILESYSTEM])
async def fs_read(file: str):
    """파일 내용을 반환합니다."""
    try:
        target_file = _resolve_workspace_path(file)
        _require_allowed("fs_read", {"path": target_file}, "safe")

        if not os.path.exists(target_file) or not os.path.isfile(target_file):
            raise HTTPException(status_code=404, detail="File not found.")

        content = await asyncio.to_thread(Path(target_file).read_text, encoding="utf-8")

        return {"ok": True, "content": content}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Cannot read binary file.")
    except HTTPException:
        raise
    except OSError as e:
        logger.error("FS read error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
