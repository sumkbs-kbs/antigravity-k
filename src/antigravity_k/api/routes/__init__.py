"""Routes package — OpenAPI 태그가 포함된 API 라우트 집계.

각 라우터는 적절한 tags와 함께 등록되어 Swagger UI에서 그룹화됩니다.
"""

from fastapi import APIRouter

from .agent_activity import router as agent_activity_router
from .agent_tools import router as agent_tools_router
from .approval_api import router as approval_router
from .chat import router as chat_router
from .code_api import router as code_router
from .events import router as events_router
from .filesystem import router as filesystem_router
from .git_api import router as git_router
from .legacy import router as legacy_router
from .system_api import router as system_api_router
from .workspace_links import router as workspace_links_router

api_router = APIRouter()

# ─── OpenAPI 태그 그룹 — Swagger UI에서 라우트 그룹화 ───

api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(events_router, tags=["events"])
api_router.include_router(filesystem_router, tags=["filesystem"])
api_router.include_router(system_api_router, tags=["system"])
api_router.include_router(legacy_router, tags=["legacy"])
api_router.include_router(agent_tools_router, tags=["agent_tools"])
api_router.include_router(agent_activity_router, tags=["agent_activity"])
api_router.include_router(workspace_links_router, tags=["workspaces"])
api_router.include_router(approval_router, tags=["approval"])
api_router.include_router(git_router, tags=["git"])
api_router.include_router(code_router, tags=["code"])
