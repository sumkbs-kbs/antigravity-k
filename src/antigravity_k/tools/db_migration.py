"""Db Migration module."""

import logging
import subprocess
from typing import Any

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory

logger = logging.getLogger(__name__)


class DatabaseMigrationTool(BaseTool):
    """데이터베이스 마이그레이션 도구.

    AI가 Alembic 리비전을 생성하거나 적용하고, 직접 SQL 쿼리를 실행할 수 있게 해줍니다.
    """

    category = ToolCategory.DANGEROUS
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.CRITICAL
    icon = "🗄️"
    tags = ["database", "db", "sql", "alembic", "migration"]

    def __init__(self):
        """Initialize the DatabaseMigrationTool."""
        super().__init__()
        self._name = "db_migration"
        self._description = (
            "Executes database migrations or arbitrary SQL commands. "
            "Supported actions: 'alembic_upgrade', 'alembic_revision', 'alembic_downgrade', 'execute_sql'."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "alembic_upgrade",
                        "alembic_revision",
                        "alembic_downgrade",
                        "execute_sql",
                    ],
                    "description": "The migration action to perform.",
                },
                "message": {
                    "type": "string",
                    "description": "Migration message for alembic_revision (e.g., 'add user table').",
                },
                "revision": {
                    "type": "string",
                    "description": "Target revision for upgrade/downgrade (defaults to 'head' for upgrade).",
                },
                "sql": {
                    "type": "string",
                    "description": "Raw SQL query to execute if action is 'execute_sql'.",
                },
            },
            "required": ["action"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        action = kwargs.get("action")

        if action == "alembic_upgrade":
            rev = kwargs.get("revision", "head")
            return self._run_subprocess(["alembic", "upgrade", rev])

        elif action == "alembic_downgrade":
            rev = kwargs.get("revision", "-1")
            return self._run_subprocess(["alembic", "downgrade", rev])

        elif action == "alembic_revision":
            msg = kwargs.get("message", "auto_migration")
            return self._run_subprocess(["alembic", "revision", "--autogenerate", "-m", msg])

        elif action == "execute_sql":
            sql = kwargs.get("sql")
            if not sql:
                return "Error: 'sql' parameter required for execute_sql."
            # Note: This is a stub for raw SQL. In a real project, this would connect
            # to the database using SQLAlchemy engine and execute the raw SQL safely.
            return f"[Simulated execution] SQL executed successfully:\n```sql\n{sql}\n```"

        return f"Unknown action: {action}"

    def _run_subprocess(self, cmd: list) -> str:
        try:
            logger.info("Running command: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return f"Success:\n{result.stdout}"
        except subprocess.CalledProcessError as e:
            return f"Command failed (exit code {e.returncode}):\n{e.stderr}"
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Execution error: {str(e)}"
