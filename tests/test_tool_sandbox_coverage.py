"""도구 계층 프로세스 실행 경로의 샌드박스 커버리지 감사.

P0 정책: 모델이 유발하는 프로세스 실행은 config의 sandbox_enabled를 존중해야 한다.
직접 subprocess/pty 실행은 아래 ALLOWLIST에 사유와 함께 등록된 파일로 한정하며,
새 파일이 추가되면 이 테스트가 실패한다 — Codex식 "전 경로 강제"의 회귀 방지선.
"""

import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "src" / "antigravity_k" / "tools"

_EXEC_PATTERN = re.compile(
    r"subprocess\.run|subprocess\.Popen|subprocess\.check_output"
    r"|create_subprocess_exec|create_subprocess_shell|pty\.fork",
)

ALLOWLIST: dict[str, str] = {
    # 샌드박스 라우팅을 구현한 파일
    "terminal_tools.py": "모델 명령을 build_sandbox_argv로 seatbelt 래핑 — P0 해소 본체",
    "system_tools.py": "_run_with_sandbox로 SandboxRunner 우선, 비활성 시에만 폴백",
    "docker_tools.py": "docker CLI 자체가 격리 경계인 컨테이너 관리 고정 호출",
    # 고정 argv 시스템 기능 도구 (모델이 임의 명령 주입 불가)
    "system_control.py": "고정 argv 시스템 제어(pbcopy/osascript/networksetup) — seatbelt 하 mach 서비스 차단으로 기능 불가",
    "os_drivers.py": "스크린샷/입력 드라이버 폴백(screencapture) 고정 argv",
    "media_gen_tools.py": "이미지/TTS 생성 CLI 고정 호출",
    "git_tools.py": "git 읽기 위주 고정 서브커맨드(status/log/diff 등)",
    "ci_tools.py": "CI 상태 조회용 고정 CLI 호출",
    "ast_grep_tool.py": "ast-grep 바이너리 고정 호출(스캔 전용)",
    "impact_analyzer.py": "분석 전용 고정 호출",
    "db_migration.py": "alembic 고정 서브커맨드 — 추후 _run_subprocess 단일 지점 샌드박스화 과제",
}


def test_all_process_execution_paths_are_accounted_for():
    unaccounted: list[str] = []
    for py_file in sorted(TOOLS_DIR.glob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        if not _EXEC_PATTERN.search(source):
            continue
        if py_file.name not in ALLOWLIST:
            unaccounted.append(py_file.name)

    assert not unaccounted, (
        "샌드박스 미경유 프로세스 실행 발견: "
        f"{unaccounted}. ALLOWLIST 등록(사유 필수) 또는 SandboxRunner/build_sandbox_argv 라우팅으로 이관하세요."
    )


def test_allowlist_entries_exist_on_disk():
    missing = [name for name in ALLOWLIST if not (TOOLS_DIR / name).exists()]
    assert not missing, f"ALLOWLIST에 존재하지 않는 파일: {missing} — 정리 필요"


def test_terminal_tools_routes_model_commands_through_sandbox_argv():
    """terminal_tools가 sandbox-exec 래핑 헬퍼를 실제로 사용하는지 확인."""
    source = (TOOLS_DIR / "terminal_tools.py").read_text(encoding="utf-8")
    assert "build_sandbox_argv" in source
    assert "sandbox-exec" in source
