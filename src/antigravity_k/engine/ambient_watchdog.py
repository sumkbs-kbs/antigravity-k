import time
import logging
import threading
import subprocess
from typing import Optional, List

from .model_manager import ModelManager
from .vault import VaultEngine

logger = logging.getLogger(__name__)


class AmbientWatchdog:
    """
    Phase 3: Ambient Partner (자율적 개입 데몬)
    사용자가 명시적으로 명령하지 않아도, 백그라운드에서 파일 변경(git diff)을 감시하다가
    에러나 개선점을 발견하면 스스로 분석하고 제안을 준비합니다.
    """

    def __init__(
        self,
        project_root: str,
        model_manager: ModelManager,
        vault_engine: Optional[VaultEngine],
    ):
        self.project_root = project_root
        self.model_manager = model_manager
        self.vault_engine = vault_engine

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._poll_interval = 5.0
        self._debounce_time = 10.0

        self._last_diff_hash = ""
        self._last_change_time = 0.0
        self._analyzing = False

        # 콜백 큐 (오케스트레이터로 메시지 전달용)
        self.notification_queue: List[str] = []

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="AmbientWatchdog"
        )
        self._thread.start()
        logger.info(
            "Ambient Watchdog daemon started. Watching for background changes..."
        )

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _get_current_diff(self) -> str:
        try:
            result = subprocess.run(
                ["git", "diff"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout
        except Exception:
            return ""

    def _watch_loop(self):
        while self._running:
            try:
                time.sleep(self._poll_interval)
                if self._analyzing:
                    continue

                current_diff = self._get_current_diff()

                if not current_diff:
                    self._last_diff_hash = ""
                    continue

                current_hash = str(hash(current_diff))

                if current_hash != self._last_diff_hash:
                    # 변경 발생
                    self._last_diff_hash = current_hash
                    self._last_change_time = time.time()
                else:
                    # 변경이 멈추고 디바운스 시간이 지났는가?
                    if (
                        time.time() - self._last_change_time > self._debounce_time
                        and self._last_change_time > 0
                    ):
                        self._analyzing = True
                        self._analyze_proactively(current_diff)
                        self._last_change_time = 0.0  # 초기화
                        self._analyzing = False

            except Exception as e:
                logger.error(f"Watchdog error: {e}")

    def _analyze_proactively(self, diff_content: str):
        """
        사용자가 코드를 저장하고 잠깐 쉴 때(Debounce) 백그라운드에서 코드를 분석합니다.
        """
        # 아주 큰 diff는 무시 (CPU 보호)
        if len(diff_content) > 10000:
            return

        logger.info("Ambient Watchdog proactively analyzing recent changes...")

        prompt = f"""You are the Proactive Ambient Watchdog.
The user just saved some changes to the codebase, but hasn't asked you anything yet.
Look at this git diff and silently check for obvious syntax errors, logic bugs, or severe code smells.

DIFF:
{diff_content}

If the code looks fine, output exactly: 'OK'
If you spot a critical bug or an obvious typo that will crash, generate a proactive notification message that we will subtly show to the user.
Format your warning starting with '⚠️ [Proactive Notice] ...'
Keep it very brief, like a friend tapping them on the shoulder.
"""
        try:
            response = self.model_manager.generate(
                prompt, target="reasoning-balanced", model_id="default"
            )
            response = response.strip()

            if response != "OK" and response.startswith("⚠️"):
                # 알림 큐에 삽입
                self.notification_queue.append(response)
                logger.info("Proactive Watchdog queued a notification.")
        except Exception as e:
            logger.error(f"Proactive analysis failed: {e}")

    def pop_notifications(self) -> List[str]:
        """오케스트레이터가 주기적으로 호출하여 알림을 가져갑니다."""
        if not self.notification_queue:
            return []
        notifs = list(self.notification_queue)
        self.notification_queue.clear()
        return notifs
