from pathlib import Path


class UnsafeProjectMemoryPathError(ValueError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"Project memory path escapes project root: {path}")


def project_memory_dir(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    memory_dir = (root / ".antigravity" / "memory").resolve()
    if not memory_dir.is_relative_to(root):
        raise UnsafeProjectMemoryPathError(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir
