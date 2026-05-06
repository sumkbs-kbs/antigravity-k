import os
import logging
from datetime import datetime
from typing import Any, Dict

from antigravity_k.tools.base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)


class WikiExportTool(BaseTool):
    """
    WikiExportTool: 에이전트가 학습한 내용이나 아키텍처 결정을
    사용자의 로컬 지식베이스(Wiki)에 마크다운 파일로 내보냅니다.
    """

    category = ToolCategory.FILE_SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "📝"
    tags = ["wiki", "knowledge", "export", "markdown", "obsidian"]

    def __init__(self):
        super().__init__()
        self._name = "export_to_wiki"
        self._description = (
            "Export structured knowledge, troubleshooting logs, or architectural "
            "decisions to a Markdown file in the user's Wiki directory."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title of the wiki page.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tags for the YAML frontmatter (e.g., ['architecture', 'troubleshooting']).",
                },
                "content": {
                    "type": "string",
                    "description": "The full Markdown content of the wiki page.",
                },
                "filename": {
                    "type": "string",
                    "description": "Optional specific filename (without .md). If not provided, title will be used.",
                },
            },
            "required": ["title", "content"],
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return self._schema

    def execute(self, **kwargs) -> Any:
        title = kwargs.get("title")
        tags = kwargs.get("tags", [])
        content = kwargs.get("content")
        filename_raw = kwargs.get("filename")

        # Create safe filename
        if not filename_raw:
            filename_raw = title.replace(" ", "_").replace("/", "-")

        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_filename = f"{date_str}_{filename_raw}.md"

        # Determine target directory
        # 1. Try to read from config.yaml if available
        project_root = os.getcwd()
        wiki_dir = os.path.join(
            project_root, "wiki_exports"
        )  # Default to workspace local folder to avoid permission errors

        try:
            import yaml

            config_path = os.path.join(project_root, "config.yaml")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    configured_dir = config.get("wiki_dir")
                    if configured_dir:
                        wiki_dir = configured_dir
        except Exception as e:
            logger.warning(f"Could not read wiki_dir from config: {e}")

        # Fallback if the configured absolute path isn't writable or doesn't exist
        if not os.path.exists(wiki_dir):
            try:
                os.makedirs(wiki_dir, exist_ok=True)
            except Exception:
                wiki_dir = project_root

        target_path = os.path.join(wiki_dir, safe_filename)

        # Build YAML Frontmatter
        frontmatter = f"---\ntitle: {title}\n"
        if tags:
            tags_str = ", ".join(tags)
            frontmatter += f"tags: [{tags_str}]\n"
        frontmatter += f"date: {date_str}\n---\n\n"

        full_content = frontmatter + content

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(full_content)
            return f"✅ Successfully exported knowledge to Wiki at: {target_path}"
        except Exception:
            # Fallback to root if permission denied
            fallback_path = os.path.join(project_root, safe_filename)
            try:
                with open(fallback_path, "w", encoding="utf-8") as f:
                    f.write(full_content)
                return f"⚠️ Permission denied to write to {wiki_dir}. Saved to fallback path: {fallback_path}"
            except Exception as e2:
                return f"❌ Failed to export wiki: {e2}"
