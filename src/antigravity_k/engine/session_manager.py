"""SessionManager — 세션 영속성 관리.

==================================
Claw Code의 Session Persistence 아키텍처 이식.

3-Tier 메모리 모델:
- Turn Memory   : 현재 턴의 메시지 (즉시 사용)
- Session Memory: 세션 전체 히스토리 (압축 적용)
- Working Memory: 프로젝트별 장기 기억 (세션 간 유지)

세션은 .antigravity/sessions/ 디렉토리에 JSON 파일로 저장됩니다.
프로젝트 디렉토리 기반으로 세션을 자동 매칭합니다.
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SessionManager:
    """세션 영속성 관리자.

    Claw Code의 세션 패턴:
    - 프로젝트별 세션 자동 생성/복원
    - 세션 메타데이터 (시작 시간, 턴 수, 토큰 사용)
    - Working Memory (프로젝트별 장기 기억)
    """

    def __init__(self, base_dir: str | None = None):
        """Initialize the SessionManager.

        Args:
            base_dir (str | None): str | None base dir.

        """
        self.base_dir = base_dir or os.path.join(
            os.path.expanduser("~"),
            ".antigravity",
            "sessions",
        )
        os.makedirs(self.base_dir, exist_ok=True)

        self._current_session: dict | None = None
        self._session_id: str | None = None

    # ─────────── 세션 라이프사이클 ───────────

    def start_session(
        self,
        project_path: str | None = None,
        resume: bool = True,
    ) -> str:
        """새 세션을 시작하거나, 기존 세션을 이어갑니다.

        Args:
            project_path: 프로젝트 루트 경로 (세션 매칭용)
            resume: True이면 기존 세션을 이어갈 수 있음

        Returns:
            session_id

        """
        project_path = project_path or os.getcwd()

        # 프로젝트 기반 세션 ID 생성
        # P0 수정: MD5 → SHA256 (보안 감사 대응)
        project_hash = hashlib.sha256(os.path.abspath(project_path).encode()).hexdigest()[:8]

        if resume:
            # 최근 세션 찾기
            existing = self._find_latest_session(project_hash)
            if existing:
                self._load_session(existing)
                logger.info("Resumed session: %s", self._session_id)
                return self._session_id

        # 새 세션 생성
        self._session_id = f"{project_hash}_{int(time.time())}"
        self._current_session = {
            "id": self._session_id,
            "project_path": os.path.abspath(project_path),
            "project_hash": project_hash,
            "created_at": time.time(),
            "updated_at": time.time(),
            "turn_count": 0,
            "messages": [],  # Session Memory
            "working_memory": {},  # Working Memory (장기)
            "metadata": {
                "total_tokens_used": 0,
                "tools_used": [],
                "files_modified": [],
            },
        }

        self._save_session()
        logger.info("Created new session: %s", self._session_id)
        return self._session_id

    def save(self):
        """현재 세션을 디스크에 저장합니다."""
        if self._current_session:
            self._current_session["updated_at"] = time.time()
            self._save_session()

    def end_session(self):
        """현재 세션을 종료하고 저장합니다."""
        if self._current_session:
            self._current_session["metadata"]["ended_at"] = time.time()
            self._save_session()
            logger.info("Session ended: %s", self._session_id)
            self._current_session = None
            self._session_id = None

    # ─────────── Turn Memory ───────────

    def add_turn(
        self, messages: list[dict[str, str]] | None = None, *, role: str | None = None, content: str | None = None
    ):
        """턴(사용자 입력 + 어시스턴트 응답)을 세션에 추가합니다.

        두 가지 호출 패턴을 지원:
          1. add_turn([{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}])
          2. add_turn(role="user", content="...")  (단일 메시지, BuiltinMemoryProvider 호환)
        """
        if not self._current_session:
            self.start_session()
            assert self._current_session is not None

        # role/content 키워드 인자로 단일 메시지 추가 (호환성)
        if role is not None and content is not None:
            messages = [{"role": role, "content": content}]
        elif messages is None:
            return

        self._current_session["messages"].extend(messages)
        self._current_session["turn_count"] += 1
        self._current_session["updated_at"] = time.time()

        # 자동 저장 (5턴마다)
        if self._current_session["turn_count"] % 5 == 0:
            self._save_session()

    def get_messages(self) -> list[dict[str, str]]:
        """현재 세션의 전체 메시지를 반환합니다."""
        if not self._current_session:
            return []
        return self._current_session.get("messages", [])

    def get_recent_messages(self, count: int = 10) -> list[dict[str, str]]:
        """최근 N개 메시지를 반환합니다."""
        messages = self.get_messages()
        return messages[-count:] if len(messages) > count else messages

    # ─────────── Working Memory (장기 기억) ───────────

    def set_memory(self, key: str, value: Any):
        """Working Memory에 값을 저장합니다."""
        if not self._current_session:
            self.start_session()
            assert self._current_session is not None
        self._current_session["working_memory"][key] = {
            "value": value,
            "last_accessed": time.time(),
            "access_count": 1,
        }

    def get_memory(self, key: str, default: Any = None) -> Any:
        """Working Memory에서 값을 조회합니다."""
        if not self._current_session:
            return default
        if key in self._current_session["working_memory"]:
            mem = self._current_session["working_memory"][key]
            # 만약 예전 포맷의 단순 값이면
            if not isinstance(mem, dict) or "last_accessed" not in mem:
                mem = {"value": mem, "last_accessed": time.time(), "access_count": 1}
                self._current_session["working_memory"][key] = mem
            else:
                mem["last_accessed"] = time.time()
                mem["access_count"] += 1
            return mem["value"]
        return default

    def get_all_memory(self) -> dict[str, Any]:
        """모든 Working Memory를 반환합니다."""
        if not self._current_session:
            return {}
        result = {}
        for k, v in self._current_session.get("working_memory", {}).items():
            if isinstance(v, dict) and "value" in v:
                result[k] = v["value"]
            else:
                result[k] = v
        return result

    def get_working_memory(self) -> dict[str, Any]:
        """Working Memory를 반환합니다 (get_all_memory의 별칭 — BuiltinMemoryProvider 호환)."""
        return self.get_all_memory()

    # ─────────── 메타데이터 추적 ───────────

    def record_tool_use(self, tool_name: str):
        """도구 사용을 기록합니다."""
        if self._current_session:
            tools = self._current_session["metadata"]["tools_used"]
            if tool_name not in tools:
                tools.append(tool_name)

    def record_file_modified(self, file_path: str):
        """파일 수정을 기록합니다."""
        if self._current_session:
            files = self._current_session["metadata"]["files_modified"]
            if file_path not in files:
                files.append(file_path)

    def record_tokens(self, count: int):
        """토큰 사용량을 기록합니다."""
        if self._current_session:
            self._current_session["metadata"]["total_tokens_used"] += count

    # ─────────── 세션 조회 ───────────

    def list_sessions(self, limit: int = 10) -> list[dict]:
        """최근 세션 목록을 반환합니다."""
        sessions = []
        for fname in os.listdir(self.base_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(self.base_dir, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append(
                        {
                            "id": data.get("id", fname),
                            "project_path": data.get("project_path", "?"),
                            "created_at": data.get("created_at", 0),
                            "updated_at": data.get("updated_at", 0),
                            "turn_count": data.get("turn_count", 0),
                        },
                    )
                except (json.JSONDecodeError, KeyError):
                    continue

        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return sessions[:limit]

    def load_session(self, session_id: str) -> bool:
        """특정 세션을 로드합니다."""
        fpath = os.path.join(self.base_dir, f"{session_id}.json")
        if os.path.exists(fpath):
            self._load_session(fpath)
            return True
        return False

    def get_session_info(self) -> dict[str, Any] | None:
        """현재 세션 정보를 반환합니다."""
        if not self._current_session:
            return None
        return {
            "id": self._session_id or "",
            "project_path": self._current_session.get("project_path", ""),
            "turn_count": self._current_session.get("turn_count", 0),
            "created_at": self._current_session.get("created_at", 0.0),
            "updated_at": self._current_session.get("updated_at", 0.0),
            "message_count": len(self._current_session.get("messages", [])),
            "memory_keys": list(self._current_session.get("working_memory", {}).keys()),
            "metadata": self._current_session.get("metadata", {}),
        }

    # ─────────── 내부 메서드 ───────────

    def _save_session(self):
        """세션을 디스크에 저장합니다."""
        if not self._current_session or not self._session_id:
            return
        fpath = os.path.join(self.base_dir, f"{self._session_id}.json")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(self._current_session, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("Failed to save session")

    def _load_session(self, fpath: str):
        """디스크에서 세션을 로드합니다."""
        try:
            with open(fpath, encoding="utf-8") as f:
                self._current_session = json.load(f)
            self._session_id = self._current_session.get("id")
        except Exception:
            logger.exception("Failed to load session")
            self._current_session = None
            self._session_id = None

    def _find_latest_session(self, project_hash: str) -> str | None:
        """프로젝트 해시로 최근 세션 파일을 찾습니다."""
        candidates: list[tuple[str, float]] = []
        for fname in os.listdir(self.base_dir):
            if fname.startswith(project_hash) and fname.endswith(".json"):
                fpath = os.path.join(self.base_dir, fname)
                mtime = os.path.getmtime(fpath)
                candidates.append((fpath, mtime))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            fpath = candidates[0][0]
            if fpath is None:
                return None
            return str(fpath)
        return None

    # ─────────── 자동 컨텍스트 복원 (P1-5) ───────────

    def auto_restore(self, project_path: str | None = None) -> str | None:
        """이전 세션의 핵심 컨텍스트를 자동 복원합니다.

        자동화 핵심:
        - 마지막 세션의 요약 생성 (수정 파일, 사용 도구, 핵심 대화)
        - 에이전트 시스템 프롬프트에 주입하여 연속성 보장
        - '빈 칸판' 문제 해결

        Returns:
            복원된 컨텍스트 문자열 (없으면 None)

        """
        project_path = project_path or os.getcwd()
        project_hash = hashlib.sha256(os.path.abspath(project_path).encode()).hexdigest()[:8]

        session_path = self._find_latest_session(project_hash)
        if not session_path:
            return None

        try:
            with open(session_path, encoding="utf-8") as f:
                prev_session = json.load(f)
        except Exception:
            logger.exception("Unhandled exception")
            return None

        # 세션 메타데이터 추출
        meta = prev_session.get("metadata", {})
        files_modified = meta.get("files_modified", [])
        tools_used = meta.get("tools_used", [])
        working_mem = prev_session.get("working_memory", {})
        messages = prev_session.get("messages", [])
        turn_count = prev_session.get("turn_count", 0)

        if turn_count == 0:
            return None

        # 마지막 사용자 메시지 3개 요약
        recent_user_msgs = [m["content"][:200] for m in messages if m.get("role") == "user"][-3:]

        # 컨텍스트 문자열 생성
        parts = ["\n[SESSION CONTEXT RESTORE]"]
        parts.append(f"Previous session: {turn_count} turns")

        if recent_user_msgs:
            parts.append("Recent topics:")
            for msg in recent_user_msgs:
                parts.append(f"  - {msg}")

        # 작업 2: 실제 최근 대화 내용 복원 — 에이전트가 이전 대화를 "기억"하도록
        recent_msgs = messages[-10:] if len(messages) > 10 else messages
        if recent_msgs:
            parts.append("\nRecent conversation:")
            for msg in recent_msgs:
                role = msg.get("role", "?")
                content = str(msg.get("content", ""))[:300]
                if role in ("user", "assistant") and content.strip():
                    parts.append(f"  {role}: {content}")

        if files_modified:
            parts.append(f"Modified files: {', '.join(files_modified[-10:])}")

        if tools_used:
            parts.append(f"Tools used: {', '.join(tools_used)}")

        # Staleness Tracker (P2-12)
        if working_mem:
            active_keys = []
            now = time.time()
            for k, v in working_mem.items():
                last_accessed = now
                if isinstance(v, dict) and "last_accessed" in v:
                    last_accessed = v["last_accessed"]
                # 7일 이상 경과된 메모리는 Staleness 처리 (배제)
                if (now - last_accessed) < 7 * 24 * 3600:
                    active_keys.append(k)

            if active_keys:
                parts.append("Working memory keys: " + ", ".join(active_keys[:10]))
                if len(active_keys) < len(working_mem):
                    parts.append(
                        f"  *(Note: {len(working_mem) - len(active_keys)} old items were purged due to staleness)*",
                    )

        # 자율 행동/수복 메모리 주입 (Hermes 차용)
        memory_dir = Path(project_path) / ".agent" / "memory"
        immune_dir = memory_dir / "immune_patches"
        if immune_dir.exists():
            patches = list(immune_dir.glob("*.json"))
            if patches:
                parts.append("\n[AUTONOMOUS LEARNINGS & PATCHES]")
                # 최근 3개의 패치 이력만 컨텍스트에 주입
                for p in sorted(patches, key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
                    try:
                        with open(p, encoding="utf-8") as f:
                            data = json.load(f)
                        parts.append(
                            f"  - Self-Patched {data.get('target_file')}: {data.get('explanation')}",
                        )
                    except Exception:
                        logger.exception("Unhandled exception")
                        continue

        parts.append("[END SESSION CONTEXT]\n")

        context = "\n".join(parts)
        logger.info("[AutoRestore] Restored context from session with %s turns", turn_count)
        return context
