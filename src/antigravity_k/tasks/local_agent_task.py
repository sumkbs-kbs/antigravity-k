import threading
import logging
import traceback
from typing import Callable, Any, Tuple, Dict, Optional

logger = logging.getLogger(__name__)

class LocalAgentTask(threading.Thread):
    """
    A wrapper around threading.Thread for executing agent tasks in parallel.
    Captures the return value and any exceptions raised during execution.
    """
    def __init__(self, name: str, target: Callable, args: Tuple = (), kwargs: Optional[Dict] = None):
        super().__init__(name=name)
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.result: Any = None
        self.error: Optional[str] = None
        self.status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED

    def run(self) -> None:
        self.status = "RUNNING"
        try:
            self.result = self.target(*self.args, **self.kwargs)
            self.status = "COMPLETED"
        except Exception as e:
            self.error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            self.status = "FAILED"
            logger.error(f"Task '{self.name}' failed: {self.error}")
