import os
import uuid
import logging
from typing import Dict, Any

from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)

class StoreKnowledgeTool(BaseTool):
    """지식을 벡터 저장소에 영구적으로 기록합니다."""
    category = ToolCategory.SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "💾"
    tags = ["memory", "knowledge", "save", "store"]

    def __init__(self, project_root: str = None):
        super().__init__()
        self._name = "store_knowledge"
        self._description = "Store a piece of knowledge permanently in the project's long-term memory (Vector Store). Useful for remembering user preferences, architectural decisions, or bugs across sessions."
        self._schema = {
            "type": "object",
            "properties": {
                "knowledge_text": {"type": "string", "description": "The information to remember."},
                "tags": {
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "Optional list of tags categorizing this knowledge."
                }
            },
            "required": ["knowledge_text"]
        }
        self.project_root = project_root or os.getcwd()
        self._vector_store = None

    def _get_vector_store(self):
        if not self._vector_store:
            from antigravity_k.engine.vector_store import VectorStore
            db_path = os.path.join(self.project_root, ".antigravity", "vault_data")
            self._vector_store = VectorStore(persist_directory=db_path, collection_name="agent_knowledge")
        return self._vector_store

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        knowledge_text = kwargs.get("knowledge_text", "")
        tags = kwargs.get("tags", [])
        
        try:
            store = self._get_vector_store()
            chunk_id = f"knowledge_{uuid.uuid4().hex[:8]}"
            metadata = {"type": "agent_knowledge"}
            if tags:
                metadata["tags"] = ", ".join(tags)
                
            chunk = {
                "id": chunk_id,
                "text": knowledge_text,
                "metadata": metadata
            }
            store.upsert_chunks([chunk])
            return f"Successfully stored knowledge. ID: {chunk_id}"
        except Exception as e:
            return f"Error storing knowledge: {e}"


class SearchKnowledgeTool(BaseTool):
    """벡터 저장소에서 지식을 검색합니다."""
    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "🧠"
    tags = ["memory", "knowledge", "search", "retrieve"]

    def __init__(self, project_root: str = None):
        super().__init__()
        self._name = "search_knowledge"
        self._description = "Search the project's long-term memory for previously stored knowledge using semantic search."
        self._schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query or concept to look for."},
                "max_results": {"type": "integer", "description": "Maximum number of results to return.", "default": 5}
            },
            "required": ["query"]
        }
        self.project_root = project_root or os.getcwd()
        self._vector_store = None

    def _get_vector_store(self):
        if not self._vector_store:
            from antigravity_k.engine.vector_store import VectorStore
            db_path = os.path.join(self.project_root, ".antigravity", "vault_data")
            self._vector_store = VectorStore(persist_directory=db_path, collection_name="agent_knowledge")
        return self._vector_store

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)
        
        try:
            store = self._get_vector_store()
            results = store.search(query, n_results=max_results)
            
            if not results:
                return "No relevant knowledge found."
                
            formatted = ["Found knowledge:"]
            for r in results:
                formatted.append(f"- {r['text']}")
                
            return "\n".join(formatted)
        except Exception as e:
            return f"Error searching knowledge: {e}"
