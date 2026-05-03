"""
BackgroundTaskRunner — 장기 실행 태스크 비동기 처리 엔진
=======================================================
Codex 스타일의 long-horizon task 실행 및 Checkpoint/Resume 지원.

핵심 기능:
  1) submit_task() — 태스크를 백그라운드 스레드로 실행
  2) get_status()  — 진행 상태 조회 (running/done/failed)
  3) checkpoint()  — 현재 상태 스냅샷 저장 (SQLite)
  4) resume()      — 마지막 체크포인트에서 재개
"""
import json
import logging
import sqlite3
import threading
import time
import uuid
from typing import Dict, Any, List, Optional, Generator
from datetime import datetime
from pathlib import Path
from antigravity_k.engine.worktree_manager import WorktreeManager

logger = logging.getLogger(__name__)


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class TaskCheckpoint:
    """태스크 실행 중간 상태 스냅샷"""
    def __init__(self, task_id: str, step: int, context: Dict[str, Any], output_so_far: str):
        self.task_id = task_id
        self.step = step
        self.context = context
        self.output_so_far = output_so_far
        self.timestamp = datetime.now().isoformat()


class BackgroundTask:
    """백그라운드 태스크 상태 객체"""
    def __init__(self, task_id: str, prompt: str, context: Optional[Dict] = None):
        self.task_id = task_id
        self.prompt = prompt
        self.context = context or {}
        self.status = TaskStatus.PENDING
        self.progress = 0.0
        self.output = ""
        self.error = None
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.cancel_event = threading.Event()
        self.checkpoints: List[TaskCheckpoint] = []
        self._thread: Optional[threading.Thread] = None
        self.worktree_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt[:100] + "..." if len(self.prompt) > 100 else self.prompt,
            "status": self.status,
            "progress": self.progress,
            "output_length": len(self.output),
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "checkpoint_count": len(self.checkpoints),
        }


class BackgroundTaskRunner:
    """
    장기 실행 태스크의 비동기 실행 및 Checkpoint 관리.
    
    Codex의 durable execution 패턴을 로컬 환경에 이식:
    - 태스크를 백그라운드 스레드에서 실행
    - 중간 체크포인트를 SQLite에 저장
    - 중단 시 마지막 체크포인트에서 재개 가능
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent / "data"
            base_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(base_dir / "tasks.db")
        
        self.db_path = db_path
        self._tasks: Dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()
        self.worktree_manager = WorktreeManager()
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    context_json TEXT NOT NULL,
                    output_so_far TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            conn.commit()

    def submit_task(
        self,
        prompt: str,
        context: Optional[Dict] = None,
        orchestrator=None,
        target_model: str = "",
        use_worktree: bool = False,
    ) -> str:
        """
        태스크를 백그라운드 스레드에 제출합니다.
        
        Returns:
            task_id: 고유 태스크 ID
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = BackgroundTask(task_id, prompt, context)

        if use_worktree:
            try:
                task.worktree_path = self.worktree_manager.create_worktree(task_id)
            except Exception as e:
                logger.error(f"Failed to create worktree: {e}")

        with self._lock:
            self._tasks[task_id] = task

        # DB에 기록
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO task_history (task_id, prompt, status, created_at) VALUES (?, ?, ?, ?)",
                (task_id, prompt, TaskStatus.PENDING, task.created_at)
            )
            conn.commit()

        # 백그라운드 스레드 시작
        thread = threading.Thread(
            target=self._run_task,
            args=(task, orchestrator, target_model),
            name=f"bg-{task_id}",
            daemon=True,
        )
        task._thread = thread
        thread.start()

        logger.info(f"Background task submitted: {task_id}")
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """현재 실행 중인 태스크에 중단 시그널을 보냅니다."""
        with self._lock:
            task = self._tasks.get(task_id)

        if not task:
            # Check DB
            status_info = self.get_status(task_id)
            if status_info and status_info["status"] in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                self._update_db_status(task_id, TaskStatus.CANCELLED, error="Task was cancelled before it started executing or it was lost in memory.")
                return True
            return False

        if task.status in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False

        logger.info(f"Sending cancel signal to task {task_id}")
        task.cancel_event.set()
        task.status = TaskStatus.CANCELLED
        self._update_db_status(task_id, TaskStatus.CANCELLED, error="Task was manually cancelled by the user.")
        return True

    def _run_task(self, task: BackgroundTask, orchestrator, target_model: str):
        """백그라운드 스레드에서 실제 태스크 실행."""
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now().isoformat()
        self._update_db_status(task.task_id, TaskStatus.RUNNING)

        try:
            if orchestrator is None:
                raise ValueError("Orchestrator is required for task execution")

            # ─── Snapshot (Filesystem Checkpoint) 생성 ───
            from antigravity_k.api.server import get_vault_engine
            vault_engine = getattr(self, "vault_engine", None) or get_vault_engine()
            
            if vault_engine:
                try:
                    snapshot_hash = vault_engine.create_snapshot(f"Pre-task checkpoint for {task.task_id}")
                    if snapshot_hash:
                        task.context["snapshot_hash"] = snapshot_hash
                        logger.info(f"Created pre-task snapshot: {snapshot_hash}")
                except Exception as e:
                    logger.warning(f"Failed to create pre-task snapshot: {e}")

            messages = [{"role": "user", "content": task.prompt}]
            if task.context:
                context_str = json.dumps(task.context, ensure_ascii=False)
                messages[0]["content"] += f"\n\nContext: {context_str}"

            # target_model이 빈 문자열이면 오케스트레이터 기본 모델로 폴백
            if not target_model:
                target_model = orchestrator._get_model_for_role("default")

            output_parts = []
            step = 0
            for chunk in orchestrator.run_stream(messages, target_model=target_model):
                if task.cancel_event.is_set():
                    logger.info(f"Task {task.task_id} interrupted by cancel event.")
                    task.status = TaskStatus.CANCELLED
                    self._update_db_status(task.task_id, TaskStatus.CANCELLED, error="Task was manually cancelled.")
                    
                    # Worktree 정리
                    if task.context.get("use_worktree", False):
                        try:
                            self.worktree_manager.remove_worktree(task.task_id)
                        except Exception as e:
                            logger.error(f"Failed to cleanup worktree on cancellation: {e}")
                    return

                output_parts.append(chunk)
                step += 1

                # 매 10스텝마다 자동 체크포인트
                if step % 10 == 0:
                    task.output = "".join(output_parts)
                    task.progress = min(0.95, step / 100)  # 추정 진행률
                    task.updated_at = datetime.now().isoformat()
                    self._save_checkpoint(task.task_id, step, task.context, task.output)

            task.output = "".join(output_parts)
            task.progress = 1.0
            task.status = TaskStatus.DONE
            task.updated_at = datetime.now().isoformat()

            self._update_db_status(task.task_id, TaskStatus.DONE, output=task.output)
            logger.info(f"Background task completed: {task.task_id}, output length: {len(task.output)}")

            # ─── LLM Wiki (Vault) 자동 기록: 세컨드 브레인 축적 ───
            self._save_to_vault(task, orchestrator)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.updated_at = datetime.now().isoformat()
            self._update_db_status(task.task_id, TaskStatus.FAILED, error=str(e))
            logger.error(f"Background task failed: {task.task_id}, error: {e}")
        
        finally:
            if task.worktree_path:
                self.worktree_manager.remove_worktree(task.task_id)

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """태스크 진행 상태를 조회합니다."""
        with self._lock:
            task = self._tasks.get(task_id)
        
        if task:
            return task.to_dict()

        # 메모리에 없으면 DB에서 조회 (이전 세션의 태스크)
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM task_history WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row:
                return {
                    "task_id": row["task_id"],
                    "prompt": row["prompt"][:100],
                    "status": row["status"],
                    "output_length": len(row["output"] or ""),
                    "error": row["error"],
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                }
        return None

    def list_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """최근 태스크 목록을 반환합니다."""
        results = []
        
        # 메모리의 활성 태스크
        with self._lock:
            for task in self._tasks.values():
                results.append(task.to_dict())

        # DB의 히스토리 (활성 태스크와 중복 제거)
        active_ids = {r["task_id"] for r in results}
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM task_history ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            for row in rows:
                if row["task_id"] not in active_ids:
                    results.append({
                        "task_id": row["task_id"],
                        "prompt": row["prompt"][:100],
                        "status": row["status"],
                        "error": row["error"],
                        "created_at": row["created_at"],
                    })

        return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

    def get_output(self, task_id: str) -> Optional[str]:
        """완료된 태스크의 전체 출력을 반환합니다."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                return task.output

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT output FROM task_history WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row:
                return row["output"]
        return None

    def _save_checkpoint(self, task_id: str, step: int, context: Dict, output: str):
        """체크포인트를 DB에 저장합니다."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO task_checkpoints (task_id, step, context_json, output_so_far, created_at) VALUES (?, ?, ?, ?, ?)",
                    (task_id, step, json.dumps(context, ensure_ascii=False), output, datetime.now().isoformat())
                )
                conn.commit()
            logger.debug(f"Checkpoint saved: {task_id} at step {step}")
        except Exception as e:
            logger.warning(f"Checkpoint save failed: {e}")

    def _save_to_vault(self, task: BackgroundTask, orchestrator=None):
        """태스크 완료 결과를 Vault에 기록하여 세컨드 브레인 메모리로 축적.
        Orchestrator가 주어지면 LLM을 통해 기억을 정제(Consolidation)합니다.
        """
        try:
            # VaultEngine을 동적으로 가져옵니다 (순환 참조 방지)
            from antigravity_k.api.server import get_vault_engine
            vault_engine = get_vault_engine()
            
            if not vault_engine:
                logger.warning("VaultEngine is not available. Skipping vault record.")
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f".agent/tasks/task_{task.task_id[:8]}_{timestamp}.md"
            
            # 컨텍스트와 결과를 마크다운으로 포맷팅
            context_md = ""
            if task.context:
                context_md = "## Context\n```json\n" + json.dumps(task.context, ensure_ascii=False, indent=2) + "\n```\n\n"
                
            # --- 1. Memory Consolidation (기억 정제 및 도구 이력 추출) ---
            summary_content = ""
            if orchestrator and hasattr(orchestrator, 'manager') and task.output:
                try:
                    import re
                    summary_prompt = (
                        "당신은 에이전트의 작업 로그를 분석하여 세컨드 브레인(Wiki)에 저장할 핵심 기억(Memory)을 추출하는 전문가입니다.\n"
                        f"아래는 에이전트가 수행한 작업의 로그입니다.\n\n"
                        f"<task_prompt>\n{task.prompt}\n</task_prompt>\n\n"
                        f"<task_output>\n{task.output[-6000:]}\n</task_output>\n\n"
                        "다음 항목을 마크다운 포맷으로 작성해주세요:\n"
                        "1. **핵심 요약 (Lessons Learned)**: 이 작업에서 성공적으로 해결한 문제와 배운 점을 3~4줄로 요약.\n"
                        "2. **도구 및 에러 이력 (Tool Trajectory)**: 사용한 주요 도구들과 직면했던 에러, 그리고 어떻게 극복했는지 간략히 기록."
                    )
                    
                    summarizer_model = orchestrator._get_model_for_role("default")
                    
                    response_gen = orchestrator.manager.stream_generate(
                        prompt=summary_prompt,
                        target=summarizer_model,
                        raw_messages=[{"role": "user", "content": summary_prompt}],
                        system_prompt="출력은 오직 마크다운으로 작성된 분석 결과여야 합니다. 불필요한 서론/결론은 생략하세요. /no_think"
                    )
                    
                    extracted_text = ""
                    for chunk in response_gen:
                        extracted_text += chunk
                        
                    extracted_text = re.sub(r'<think>.*?</think>', '', extracted_text, flags=re.DOTALL).strip()
                    
                    if extracted_text:
                        summary_content = f"## 🧠 Memory Consolidation (자가 학습)\n\n{extracted_text}\n\n"
                except Exception as llm_e:
                    logger.warning(f"Memory consolidation failed: {llm_e}")
                    summary_content = "## 🧠 Memory Consolidation\n\n*(요약 생성에 실패했습니다)*\n\n"

            # --- 2. 최종 마크다운 조합 ---
            content = f"# Task: {task.prompt[:50]}...\n\n"
            content += f"**Task ID**: {task.task_id}\n"
            content += f"**Status**: {task.status}\n"
            content += f"**Date**: {task.updated_at}\n\n"
            content += f"## Prompt\n{task.prompt}\n\n"
            content += context_md
            content += summary_content
            content += f"## Raw Result\n\n<details>\n<summary>전체 로그 보기</summary>\n\n{task.output}\n\n</details>\n"

            metadata = {
                "type": "background_task",
                "task_id": task.task_id,
                "date": task.updated_at,
                "tags": ["task", "history", "memory"]
            }

            vault_engine.write_note(
                relative_path=filename,
                metadata=metadata,
                content=content,
                commit_message=f"Agent memory recorded with consolidation for task {task.task_id}"
            )
            logger.info(f"Task memory saved to vault: {filename}")
        except Exception as e:
            logger.error(f"Failed to save task result to vault: {e}")

    def get_last_checkpoint(self, task_id: str) -> Optional[Dict[str, Any]]:
        """마지막 체크포인트를 조회합니다."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM task_checkpoints WHERE task_id = ? ORDER BY step DESC LIMIT 1",
                (task_id,)
            ).fetchone()
            if row:
                return {
                    "task_id": row["task_id"],
                    "step": row["step"],
                    "context": json.loads(row["context_json"]),
                    "output_so_far": row["output_so_far"],
                    "created_at": row["created_at"],
                }
        return None

    def resume_task(
        self,
        task_id: str,
        orchestrator=None,
        target_model: str = "",
    ) -> bool:
        """마지막 체크포인트에서 태스크를 재개합니다."""
        checkpoint = self.get_last_checkpoint(task_id)
        if not checkpoint:
            logger.warning(f"No checkpoint found for task {task_id}")
            return False

        # 원래 프롬프트 조회
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT prompt FROM task_history WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not row:
                return False

        # 체크포인트 컨텍스트로 새 태스크 생성
        resume_prompt = (
            f"{row['prompt']}\n\n"
            f"[RESUMING FROM CHECKPOINT at step {checkpoint['step']}]\n"
            f"Previous output:\n{checkpoint['output_so_far'][-2000:]}\n"
            f"Continue from where you left off."
        )
        
        task = BackgroundTask(task_id, resume_prompt, checkpoint["context"])
        task.output = checkpoint["output_so_far"]

        with self._lock:
            self._tasks[task_id] = task

        thread = threading.Thread(
            target=self._run_task,
            args=(task, orchestrator, target_model),
            name=f"bg-resume-{task_id}",
            daemon=True,
        )
        task._thread = thread
        thread.start()

        logger.info(f"Task resumed from checkpoint: {task_id} at step {checkpoint['step']}")
        return True

    def _update_db_status(self, task_id: str, status: str, output: str = None, error: str = None):
        """DB에 태스크 상태를 업데이트합니다."""
        try:
            with self._get_connection() as conn:
                if status in (TaskStatus.DONE, TaskStatus.FAILED):
                    conn.execute(
                        "UPDATE task_history SET status = ?, output = ?, error = ?, completed_at = ? WHERE task_id = ?",
                        (status, output, error, datetime.now().isoformat(), task_id)
                    )
                else:
                    conn.execute(
                        "UPDATE task_history SET status = ? WHERE task_id = ?",
                        (status, task_id)
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"DB status update failed: {e}")


# ── 싱글톤 인스턴스 ──
_task_runner: Optional[BackgroundTaskRunner] = None

def get_task_runner() -> BackgroundTaskRunner:
    global _task_runner
    if _task_runner is None:
        _task_runner = BackgroundTaskRunner()
    return _task_runner
