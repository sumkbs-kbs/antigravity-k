import subprocess
import os
import uuid
import logging
from typing import Dict, Any, Optional

from .base_tool import BaseTool, ToolCategory, RenderIn, RiskLevel

logger = logging.getLogger(__name__)

class PersistentTerminalManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PersistentTerminalManager, cls).__new__(cls)
            cls._instance.terminals = {}
        return cls._instance

    def create_terminal(self, command: str, cwd: str) -> str:
        term_id = str(uuid.uuid4())[:8]
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        # Using non-blocking IO for stdout/stderr would be better, but for simplicity:
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stderr.fileno(), False)
        
        self.terminals[term_id] = process
        return term_id

    def get_output(self, term_id: str) -> str:
        if term_id not in self.terminals:
            return f"Error: Terminal {term_id} not found."
        
        process = self.terminals[term_id]
        output = ""
        try:
            while True:
                line = process.stdout.readline()
                if not line: break
                output += line
        except Exception as e:
            logger.debug(f"Failed to read stdout for term_id {term_id}: {e}")
            
        try:
            while True:
                line = process.stderr.readline()
                if not line: break
                output += line
        except Exception as e:
            logger.debug(f"Failed to read stderr for term_id {term_id}: {e}")
            
        if process.poll() is not None:
            output += f"\n[Process exited with code {process.returncode}]"
            del self.terminals[term_id]
            
        return output

    def send_input(self, term_id: str, text: str) -> str:
        if term_id not in self.terminals:
            return f"Error: Terminal {term_id} not found."
        
        process = self.terminals[term_id]
        if process.poll() is not None:
            return "Error: Process already exited."
            
        try:
            process.stdin.write(text + "\n")
            process.stdin.flush()
            return "Input sent."
        except Exception as e:
            return f"Error sending input: {e}"


class RunPersistentCommandTool(BaseTool):
    """Run a long-running command in a persistent terminal."""
    category = ToolCategory.SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.HIGH
    icon = "🖥️"
    tags = ["terminal", "bash", "shell", "run", "background"]

    def __init__(self):
        super().__init__()
        self._name = "run_persistent_command"
        self._description = "Run a long-running bash command in the background (e.g., servers, watchers). Returns a Terminal ID."
        self._schema = {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to run."},
                "cwd": {"type": "string", "description": "Working directory. Default is current.", "default": "."}
            },
            "required": ["command"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        command = kwargs.get("command", "")
        cwd = kwargs.get("cwd", ".")
        
        manager = PersistentTerminalManager()
        try:
            term_id = manager.create_terminal(command, os.path.abspath(cwd))
            return f"Started command '{command}' in background. Terminal ID: {term_id}\nUse check_command_status tool to view output."
        except Exception as e:
            return f"Error starting command: {e}"


class CheckCommandStatusTool(BaseTool):
    """Check output of a persistent terminal."""
    category = ToolCategory.SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "👁️"
    tags = ["terminal", "status", "output", "log"]

    def __init__(self):
        super().__init__()
        self._name = "check_command_status"
        self._description = "Check the recent standard output and error of a persistent terminal by its Terminal ID."
        self._schema = {
            "type": "object",
            "properties": {
                "terminal_id": {"type": "string", "description": "The Terminal ID returned by run_persistent_command."}
            },
            "required": ["terminal_id"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        term_id = kwargs.get("terminal_id", "")
        manager = PersistentTerminalManager()
        output = manager.get_output(term_id)
        return output if output.strip() else "[No new output]"


class SendCommandInputTool(BaseTool):
    """Send input to a persistent terminal."""
    category = ToolCategory.SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.MEDIUM
    icon = "⌨️"
    tags = ["terminal", "input", "stdin"]

    def __init__(self):
        super().__init__()
        self._name = "send_command_input"
        self._description = "Send standard input (stdin) to a running persistent terminal."
        self._schema = {
            "type": "object",
            "properties": {
                "terminal_id": {"type": "string", "description": "The Terminal ID."},
                "input_text": {"type": "string", "description": "The text to send."}
            },
            "required": ["terminal_id", "input_text"]
        }

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        term_id = kwargs.get("terminal_id", "")
        text = kwargs.get("input_text", "")
        manager = PersistentTerminalManager()
        return manager.send_input(term_id, text)


class InteractivePTYTool(BaseTool):
    """
    PTY(가상 터미널)를 할당하여 대화형 프로그램(GDB, python -i 등)을 실행하고 상호작용합니다.
    단순 subprocess 파이프에서 발생하는 출력 깨짐이나 행(Hang) 현상을 방지합니다.
    """
    category = ToolCategory.SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.MEDIUM
    icon = "📟"
    tags = ["pty", "interactive", "gdb", "shell"]

    def __init__(self):
        super().__init__()
        self._name = "interactive_pty"
        self._description = (
            "Execute an interactive command (like GDB, radare2, or python REPL) within a pseudo-terminal (PTY) "
            "and wait for its output. Automatically strips ANSI escape sequences so the output is clean for the LLM. "
            "You can send continuous input to an ongoing session."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The interactive command to run (e.g., 'gdb ./a.out'). If a session is already running, this creates a NEW session."
                },
                "input_text": {
                    "type": "string",
                    "description": "Text to send to the running PTY session. Include \n if you want to press Enter. Use this instead of 'command' to interact with an active session."
                },
                "wait_ms": {
                    "type": "integer",
                    "description": "Milliseconds to wait for the output to settle. Default is 500ms.",
                    "default": 500
                }
            }
        }
        # Class-level state for simplicity. In a real system, use a manager.
        if not hasattr(InteractivePTYTool, '_active_pid'):
            InteractivePTYTool._active_pid = None
            InteractivePTYTool._active_fd = None

    @property
    def name(self) -> str: return self._name
    @property
    def description(self) -> str: return self._description
    @property
    def parameters_schema(self) -> Dict[str, Any]: return self._schema

    def execute(self, **kwargs) -> Any:
        command = kwargs.get("command")
        input_text = kwargs.get("input_text")
        wait_time = kwargs.get("wait_ms", 500) / 1000.0
        
        if not command and not input_text:
            return "Error: You must provide either 'command' (to start) or 'input_text' (to interact)."
            
        import os, pty, select, time, re
        
        # Start a new session
        if command:
            if InteractivePTYTool._active_pid:
                self._cleanup_session()
                
            pid, fd = pty.fork()
            if pid == 0:
                # Child process
                import sys, shlex
                try:
                    cmd_args = shlex.split(command)
                    os.execvp(cmd_args[0], cmd_args)
                except Exception as e:
                    print(f"Exec failed: {e}")
                    sys.exit(1)
            else:
                # Parent process
                InteractivePTYTool._active_pid = pid
                InteractivePTYTool._active_fd = fd
                return self._read_until_settled(wait_time)
                
        # Interact with existing session
        if input_text:
            if not InteractivePTYTool._active_pid or not InteractivePTYTool._active_fd:
                return "Error: No active PTY session. Start one by providing a 'command'."
                
            try:
                os.write(InteractivePTYTool._active_fd, input_text.encode('utf-8'))
                return self._read_until_settled(wait_time)
            except OSError as e:
                self._cleanup_session()
                return f"Error writing to PTY: {e}. Session closed."

    def _read_until_settled(self, timeout: float) -> str:
        import os, select, time, re
        output = b""
        start_time = time.time()
        
        while True:
            r, _, _ = select.select([InteractivePTYTool._active_fd], [], [], timeout)
            if not r: break
            try:
                data = os.read(InteractivePTYTool._active_fd, 4096)
                if not data: break
                output += data
            except OSError as e:
                logger.debug(f"PTY read interrupted or finished: {e}")
                break
            if time.time() - start_time > 5.0: break
                
        text = output.decode('utf-8', errors='replace')
        return self._strip_ansi(text)

    def _strip_ansi(self, text: str) -> str:
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
        
    def _cleanup_session(self):
        import os
        if InteractivePTYTool._active_pid:
            try: os.kill(InteractivePTYTool._active_pid, 9)
            except OSError as e: logger.debug(f"Failed to kill pid: {e}")
            InteractivePTYTool._active_pid = None
        if InteractivePTYTool._active_fd:
            try: os.close(InteractivePTYTool._active_fd)
            except OSError as e: logger.debug(f"Failed to close fd: {e}")
            InteractivePTYTool._active_fd = None
