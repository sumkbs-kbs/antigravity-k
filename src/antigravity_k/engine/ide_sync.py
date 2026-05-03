import os
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class IDEContextManager:
    """전역 IDE 상태 관리자 (싱글톤)"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(IDEContextManager, cls).__new__(cls)
                cls._instance._state = {
                    "active_file": None,
                    "cursor_line": None,
                    "open_files": []
                }
        return cls._instance
        
    def update_state(self, new_state: Dict[str, Any]):
        with self._lock:
            self._state.update(new_state)
            logger.debug(f"IDE Context updated: {self._state}")
            
    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._state)
            
    def format_prompt(self) -> str:
        state = self.get_state()
        if not state.get("active_file"):
            return ""
            
        prompt = "\n\n=== IDE CONTEXT ===\n"
        prompt += f"Active File: {state['active_file']}\n"
        if state.get("cursor_line"):
            prompt += f"Cursor Line: {state['cursor_line']}\n"
        if state.get("open_files"):
            prompt += f"Open Files: {', '.join(state['open_files'])}\n"
        prompt += "===================\n"
        return prompt


class IDESyncHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/update":
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                try:
                    payload = json.loads(post_data.decode('utf-8'))
                    IDEContextManager().update_state(payload)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "ok"}')
                    return
                except json.JSONDecodeError:
                    pass
                    
        self.send_response(400)
        self.end_headers()
        self.wfile.write(b'{"status": "error", "message": "Invalid JSON"}')
        
    def log_message(self, format, *args):
        # HTTP 로그 끄기
        pass


def start_ide_sync_server(port: int = 54321):
    """백그라운드 스레드에서 IDE Sync HTTP 서버를 시작합니다."""
    def run_server():
        try:
            server = HTTPServer(('127.0.0.1', port), IDESyncHandler)
            logger.info(f"IDE Sync Server started on port {port}")
            server.serve_forever()
        except Exception as e:
            logger.error(f"Failed to start IDE Sync Server on port {port}: {e}")
            
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread
