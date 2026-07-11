class StalenessDetector:
    """Detects stale indexed content by comparing file mtimes/hashes to the graph."""

    def __init__(self, repo_manager=None):
        """Initialize the StalenessDetector.

        Args:
            repo_manager: repo manager.

        """
        self.repo_manager = repo_manager

    def check(self, repo_path: str) -> dict:
        """Check.

        Args:
            repo_path (str): str repo path.

        Returns:
            dict: The dict result.

        """
        # Mock implementation for tests
        return {
            "status": "UP_TO_DATE",
            "current_commit": "abcdef123456",
            "indexed_commit": "abcdef123456",
        }
