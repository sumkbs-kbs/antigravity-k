class StalenessDetector:
    def __init__(self, repo_manager=None):
        self.repo_manager = repo_manager
        
    def check(self, repo_path: str) -> dict:
        # Mock implementation for tests
        return {
            "status": "UP_TO_DATE",
            "current_commit": "abcdef123456",
            "indexed_commit": "abcdef123456"
        }
