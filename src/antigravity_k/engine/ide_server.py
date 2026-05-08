import os
import subprocess
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class IDEServer:
    """
    Manages the lifecycle of the code-server daemon to provide a Web IDE.
    """

    def __init__(self, port: int = 8080, workspace_dir: str = "."):
        self.port = port
        self.workspace_dir = workspace_dir
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self.process and self.process.poll() is None:
                logger.info(f"IDE Server is already running on port {self.port}.")
                return

            # Note: auth=none is used because we assume the dashboard handles authentication,
            # and the code-server is only bound to localhost for proxying.
            cmd = [
                "code-server",
                "--bind-addr",
                f"127.0.0.1:{self.port}",
                "--auth",
                "none",
                self.workspace_dir,
            ]

            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=os.environ.copy(),
                )
                logger.info(
                    f"Started IDE (code-server) on port {self.port} for {self.workspace_dir}"
                )
            except FileNotFoundError:
                logger.error("code-server executable not found in PATH.")
                # We do not raise here to prevent crashing the main orchestrator if code-server is missing
                self.process = None

    def stop(self):
        with self._lock:
            if self.process and self.process.poll() is None:
                logger.info("Stopping IDE Server...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                self.process = None
                logger.info("IDE Server stopped.")

    def is_running(self) -> bool:
        with self._lock:
            return self.process is not None and self.process.poll() is None
