from fastapi import APIRouter
from .events import router as events_router
from .chat import router as chat_router
from .legacy import router as legacy_router
from .agent_tools import router as agent_tools_router
from .agent_activity import router as agent_activity_router

api_router = APIRouter()

api_router.include_router(events_router, tags=["events"])
api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(legacy_router, tags=["legacy"])
api_router.include_router(agent_tools_router, tags=["agent_tools"])
api_router.include_router(agent_activity_router, tags=["agent_activity"])
