"""Ide Sync module."""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

logger = logging.getLogger(__name__)


class IDEContextManager:
    """전역 IDE 상태 관리자 (싱글톤)."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Create a new instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(IDEContextManager, cls).__new__(cls)
                cls._instance._state = {
                    "active_file": None,
                    "cursor_line": None,
                    "open_files": [],
                }
        return cls._instance

    def update_state(self, new_state: dict[str, Any]):
        """Update state.

        Args:
            new_state (dict[str, Any]): dict[str, Any] new state.

        """
        with self._lock:
            self._state.update(new_state)
            logger.debug("IDE Context updated: %s", self._state)

    def get_state(self) -> dict[str, Any]:
        """Retrieve state.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        with self._lock:
            return dict(self._state)

    def format_prompt(self) -> str:
        """Format prompt.

        Returns:
            str: The str result.

        """
        state = self.get_state()
        if not state.get("active_file"):
            return ""

        prompt = "\n\n<ADDITIONAL_METADATA>\n"
        prompt += "The user's current state is as follows:\n"
        prompt += f"Active Document: {state['active_file']}\n"
        if state.get("cursor_line"):
            prompt += f"Cursor is on line: {state['cursor_line']}\n"
        if state.get("open_files"):
            prompt += "Other open documents:\n"
            for f in state["open_files"]:
                if f != state["active_file"]:
                    prompt += f"- {f}\n"
        prompt += "</ADDITIONAL_METADATA>\n"
        return prompt


class IDESyncHandler(BaseHTTPRequestHandler):
    """Idesynchandler.

    Bases: BaseHTTPRequestHandler
    """

    def do_POST(self):
        """Do Post."""
        if self.path == "/update":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                try:
                    payload = json.loads(post_data.decode("utf-8"))
                    IDEContextManager().update_state(payload)

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status": "ok"}')
                    return
                except json.JSONDecodeError as e:
                    logger.warning("Failed to decode IDE Sync JSON payload: %s", e)

        self.send_response(400)
        self.end_headers()
        self.wfile.write(b'{"status": "error", "message": "Invalid JSON"}')

    def log_message(self, format, *args):
        """Log Message.

        Args:
            format: format.
            *args: args.

        """
        # HTTP 로그 끄기
        pass


def start_ide_sync_server(port: int = 54321):
    """백그라운드 스레드에서 IDE Sync HTTP 서버를 시작합니다."""

    def run_server():
        try:
            server = HTTPServer(("127.0.0.1", port), IDESyncHandler)
            logger.info("IDE Sync Server started on port %s", port)
            server.serve_forever()
        except Exception:
            logger.exception("Failed to start IDE Sync Server on port %s", port)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread
