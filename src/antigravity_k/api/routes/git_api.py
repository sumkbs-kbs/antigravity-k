"""Git API routes for the dashboard Git GUI.

Provides structured JSON endpoints for common Git operations:
status, log, diff, add, commit, branch, stash, and graph.
"""

import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from antigravity_k.engine.api_cache import TAG_GIT, api_cache, cached

logger = logging.getLogger("antigravity_k.api.git_api")
router = APIRouter()


# ─── Helpers ────────────────────────────────────────────────────


def _git(args: list[str], cwd: str = ".", timeout: int = 30) -> str:
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Git is not installed or not in PATH.")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Git command timed out.")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _parse_status_line(line: str) -> Optional[dict]:
    """Parse a single git status --short line into structured data."""
    line = line.rstrip("\n")
    if not line or line.startswith("#"):
        return None

    # Handle copied/renamed files with ->
    if "->" in line:
        # Renamed/copied: R  old -> new
        parts = line[3:].split(" -> ")
        x = line[0]
        y = line[1]
        old_path = parts[0].strip()
        new_path = parts[1].strip() if len(parts) > 1 else old_path
        return {
            "x": x,
            "y": y,
            "staged_status": _status_char(x),
            "unstaged_status": _status_char(y),
            "file_path": new_path,
            "old_path": old_path,
            "is_renamed": True,
        }

    # Normal file
    x = line[0]
    y = line[1]
    file_path = line[3:]

    return {
        "x": x,
        "y": y,
        "staged_status": _status_char(x),
        "unstaged_status": _status_char(y),
        "file_path": file_path,
        "old_path": None,
        "is_renamed": False,
    }


def _status_char(c: str) -> str:
    """Convert status character to human-readable label."""
    mapping = {
        "M": "modified",
        "A": "added",
        "D": "deleted",
        "R": "renamed",
        "C": "copied",
        "U": "updated",
        "?": "untracked",
        "!": "ignored",
        " ": "unchanged",
    }
    return mapping.get(c, "unknown")


@dataclass
class BranchInfo:
    name: str
    is_current: bool
    is_remote: bool = False
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0


# ─── API Endpoints ──────────────────────────────────────────────


@router.get("/api/git/status")
@cached(ttl=10, tags=[TAG_GIT])
async def git_status(path: str = Query(".", description="Repository path")):
    """Get git status with structured file changes."""
    try:
        # Status short
        status_output = _git(["status", "--short", "--branch"], cwd=path)

        # Parse files
        lines = status_output.split("\n")
        files = []
        branch_line = ""

        for line in lines:
            if line.startswith("##"):
                branch_line = line
            else:
                parsed = _parse_status_line(line)
                if parsed:
                    files.append(parsed)

        # Parse branch line: "## main...origin/main [ahead 1, behind 2]"
        branch_parts = branch_line.replace("## ", "").split("...")
        current_branch = branch_parts[0]
        upstream = branch_parts[1] if len(branch_parts) > 1 else None

        ahead = 0
        behind = 0
        if upstream and "[" in upstream:
            bracket = upstream[upstream.index("[") :]
            upstream = upstream[: upstream.index("[")].strip()
            if "ahead" in bracket:
                ahead = int(bracket.split("ahead")[1].split()[0].replace("]", ""))
            if "behind" in bracket:
                behind = int(bracket.split("behind")[1].split()[0].replace("]", ""))

        # Count by status
        staged = sum(1 for f in files if f["x"] != " " and f["x"] != "?")
        unstaged = sum(1 for f in files if f["y"] != " " and f["y"] != "?")
        untracked = sum(1 for f in files if f["x"] == "?" or f["y"] == "?")

        return {
            "ok": True,
            "branch": current_branch,
            "upstream": upstream,
            "ahead": ahead,
            "behind": behind,
            "files": files,
            "counts": {
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "total": len(files),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git status error")
        return {"ok": False, "error": str(e)}


@router.post("/api/git/log")
async def git_log(request: Request):
    """Get commit log with structured data."""
    try:
        body = await request.json()
        path = body.get("path", ".")
        count = body.get("count", 20)
        branch = body.get("branch", "")

        args = ["log", f"-n{count}", "--format=%H||%h||%an||%ae||%ai||%s||%D"]
        if branch:
            args.extend([branch, "--"])

        output = _git(args, cwd=path)
        commits = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("||", 6)
            if len(parts) >= 6:
                commits.append(
                    {
                        "hash": parts[0],
                        "short_hash": parts[1],
                        "author_name": parts[2],
                        "author_email": parts[3],
                        "date": parts[4],
                        "message": parts[5],
                        "refs": parts[6] if len(parts) > 6 else "",
                    }
                )

        return {"ok": True, "commits": commits, "count": len(commits)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git log error")
        return {"ok": False, "error": str(e)}


@router.post("/api/git/diff")
async def git_diff(request: Request):
    """Get diff for a file or all changes."""
    try:
        body = await request.json()
        path = body.get("path", ".")
        file_path = body.get("file", "")
        staged = body.get("staged", False)
        unified = body.get("unified", 3)

        args = ["diff", f"--unified={unified}"]
        if staged:
            args.append("--cached")
        if file_path:
            args.extend(["--", file_path])

        output = _git(args, cwd=path)

        # Parse diff stats
        stat_args = ["diff", "--stat"]
        if staged:
            stat_args.append("--cached")
        if file_path:
            stat_args.extend(["--", file_path])
        stat_output = _git(stat_args, cwd=path)

        return {
            "ok": True,
            "diff": output,
            "stat": stat_output,
            "staged": staged,
            "file": file_path,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git diff error")
        return {"ok": False, "error": str(e)}


@router.post("/api/git/add")
async def git_add(request: Request):
    """Stage files."""
    try:
        body = await request.json()
        path = body.get("path", ".")
        files = body.get("files", [])
        all_files = body.get("all", False)

        if all_files:
            _git(["add", "-A"], cwd=path)
            await api_cache.invalidate_tag(TAG_GIT)
            return {"ok": True, "message": "All files staged.", "all": True}
        elif files:
            _git(["add", "--"] + files, cwd=path)
            await api_cache.invalidate_tag(TAG_GIT)
            return {"ok": True, "message": f"{len(files)} file(s) staged.", "files": files}
        else:
            return {"ok": False, "error": "No files specified."}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git add error")
        return {"ok": False, "error": str(e)}


@router.post("/api/git/unstage")
async def git_unstage(request: Request):
    """Unstage files."""
    try:
        body = await request.json()
        path = body.get("path", ".")
        files = body.get("files", [])

        if files:
            _git(["restore", "--staged", "--"] + files, cwd=path)
            await api_cache.invalidate_tag(TAG_GIT)
            return {"ok": True, "message": f"{len(files)} file(s) unstaged.", "files": files}
        else:
            # Unstage all
            _git(["restore", "--staged", "."], cwd=path)
            await api_cache.invalidate_tag(TAG_GIT)
            return {"ok": True, "message": "All files unstaged.", "all": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git unstage error")
        return {"ok": False, "error": str(e)}


@router.post("/api/git/commit")
async def git_commit(request: Request):
    """Create a commit."""
    try:
        body = await request.json()
        path = body.get("path", ".")
        message = body.get("message", "")
        stage_all = body.get("stage_all", True)

        if not message.strip():
            return {"ok": False, "error": "Commit message is required."}

        if stage_all:
            _git(["add", "-A"], cwd=path)

        output = _git(["commit", "-m", message], cwd=path)
        await api_cache.invalidate_tag(TAG_GIT)
        return {"ok": True, "message": "Commit created.", "output": output}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git commit error")
        return {"ok": False, "error": str(e)}


@router.get("/api/git/branches")
@cached(ttl=30, tags=[TAG_GIT])
async def git_branches(path: str = Query(".", description="Repository path")):
    """List branches with current indicator."""
    try:
        output = _git(["branch", "-a", "--format=%(refname:short)|%(HEAD)|%(upstream:short)"], cwd=path)

        branches = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            name = parts[0]
            is_head = parts[1] == "*"
            upstream = parts[2] if len(parts) > 2 and parts[2] else None

            branches.append(
                {
                    "name": name,
                    "is_current": is_head,
                    "is_remote": name.startswith("remotes/"),
                    "upstream": upstream,
                }
            )

        # Get current branch
        current = _git(["branch", "--show-current"], cwd=path).strip()

        return {"ok": True, "branches": branches, "current": current}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git branches error")
        return {"ok": False, "error": str(e)}


@router.post("/api/git/branch/create")
async def git_branch_create(request: Request):
    """Create a new branch."""
    try:
        body = await request.json()
        path = body.get("path", ".")
        name = body.get("name", "")
        from_branch = body.get("from", "")

        if not name.strip():
            return {"ok": False, "error": "Branch name is required."}

        if from_branch:
            _git(["checkout", from_branch], cwd=path)

        _git(["checkout", "-b", name], cwd=path)
        await api_cache.invalidate_tag(TAG_GIT)
        return {"ok": True, "message": f"Branch '{name}' created and checked out.", "branch": name}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git branch create error")
        return {"ok": False, "error": str(e)}


@router.post("/api/git/checkout")
async def git_checkout(request: Request):
    """Checkout a branch."""
    try:
        body = await request.json()
        path = body.get("path", ".")
        name = body.get("name", "")

        if not name.strip():
            return {"ok": False, "error": "Branch name is required."}

        _git(["checkout", name], cwd=path)
        await api_cache.invalidate_tag(TAG_GIT)
        return {"ok": True, "message": f"Switched to branch '{name}'.", "branch": name}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git checkout error")
        return {"ok": False, "error": str(e)}


@router.post("/api/git/branch/delete")
async def git_branch_delete(request: Request):
    """Delete a branch."""
    try:
        body = await request.json()
        path = body.get("path", ".")
        name = body.get("name", "")
        force = body.get("force", False)

        if not name.strip():
            return {"ok": False, "error": "Branch name is required."}

        flag = "-D" if force else "-d"
        _git(["branch", flag, name], cwd=path)
        await api_cache.invalidate_tag(TAG_GIT)
        return {"ok": True, "message": f"Branch '{name}' deleted."}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git branch delete error")
        return {"ok": False, "error": str(e)}


@router.get("/api/git/graph")
@cached(ttl=30, tags=[TAG_GIT])
async def git_graph(
    path: str = Query(".", description="Repository path"), count: int = Query(30, description="Number of commits")
):
    """Get branch graph visualization data."""
    try:
        output = _git(
            [
                "log",
                "--all",
                f"-n{count}",
                "--format=%H||%h||%an||%s||%ai||%D",
                "--graph",
            ],
            cwd=path,
        )

        nodes = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            # Extract graph characters prefix
            graph_chars = ""
            content = line
            for ch in line:
                if ch in "*|/\\ _.-":
                    graph_chars += ch
                    content = content[1:]
                else:
                    break
            content = content.strip()
            parts = content.split("||", 5)
            if len(parts) >= 4:
                nodes.append(
                    {
                        "graph": graph_chars,
                        "hash": parts[0],
                        "short_hash": parts[1],
                        "author": parts[2],
                        "message": parts[3],
                        "date": parts[4] if len(parts) > 4 else "",
                        "refs": parts[5] if len(parts) > 5 else "",
                    }
                )

        return {"ok": True, "nodes": nodes, "count": len(nodes)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git graph error")
        return {"ok": False, "error": str(e)}


@router.get("/api/git/file-content")
async def git_file_content(
    path: str = Query(".", description="Repository path"),
    file: str = Query(..., description="File path"),
    ref: str = Query("HEAD", description="Git ref"),
):
    """Get file content from a specific git ref."""
    try:
        output = _git(["show", f"{ref}:{file}"], cwd=path)
        return {"ok": True, "content": output, "ref": ref, "file": file}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git file content error")
        return {"ok": False, "error": str(e)}


@router.get("/api/git/stash/list")
@cached(ttl=30, tags=[TAG_GIT])
async def git_stash_list(path: str = Query(".", description="Repository path")):
    """List stashes."""
    try:
        output = _git(["stash", "list", "--format=%h||%ai||%s"], cwd=path)
        stashes = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("||", 2)
            if len(parts) >= 2:
                stashes.append(
                    {
                        "short_hash": parts[0],
                        "date": parts[1],
                        "message": parts[2] if len(parts) > 2 else "",
                    }
                )
        return {"ok": True, "stashes": stashes}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Git stash list error")
        return {"ok": False, "error": str(e)}
