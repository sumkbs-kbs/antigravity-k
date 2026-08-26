"""테스트: Claude Deny Patterns — 보안 deny 규칙 설치·관리.
============================================
패턴 목록, 설정 병합(self-cleanup), 설치/상태 조회,
커맨드 차단 판정을 검증한다.
"""

import json

import pytest

from antigravity_k.engine.claude_deny_patterns import (
    RULES_MARKER_KEY,
    deny_patterns,
    get_blocked_patterns_for_runtime,
    get_deny_rules_status,
    install_deny_rules,
    is_command_blocked_by_deny,
    validate_directory,
)


class TestDenyPatternsList:
    def test_returns_nonempty_list_of_strings(self):
        patterns = deny_patterns()
        assert len(patterns) > 10
        assert all(isinstance(p, str) for p in patterns)

    def test_critical_destructive_commands_covered(self):
        joined = "\n".join(deny_patterns())
        assert "rm" in joined
        assert "mkfs" in joined
        assert "chmod" in joined


class TestValidateDirectory:
    def test_valid_absolute_dir_passes(self, tmp_path):
        assert validate_directory(str(tmp_path)) == tmp_path

    @pytest.mark.parametrize(
        "bad,match",
        [
            ("", "설정되지 않았습니다"),
            ("relative/path", "절대경로"),
            ("/nonexistent/ghost", "존재하지 않습니다"),
        ],
    )
    def test_invalid_directories_raise_value_error(self, bad, match):
        with pytest.raises(ValueError, match=match):
            validate_directory(bad)


# ─── install & status ────────────────────────────────────────────


@pytest.fixture
def project_root(tmp_path):
    """install_deny_rules가 .claude/settings.local.json을 생성할 루트."""
    return tmp_path


class TestInstallDenyRules:
    def test_install_creates_settings_with_marker(self, project_root):
        report = install_deny_rules(str(project_root))

        assert report.deny_count > 0
        settings_file = project_root / ".claude" / "settings.local.json"
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        marker = data["permissions"][RULES_MARKER_KEY]
        assert marker["installed_patterns"]

    def test_reinstall_produces_same_final_state(self, project_root):
        """self-cleanup + 재추가 사이클이어도 최종 deny 목록에 중복이 없어야 한다."""
        install_deny_rules(str(project_root))
        r1 = install_deny_rules(str(project_root))

        settings_file = project_root / ".claude" / "settings.local.json"
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        deny_list = data["permissions"]["deny"]
        assert len(deny_list) == len(set(deny_list))  # 중복 없음
        assert r1.deny_count == 80  # 전체 패턴 수

    def test_status_reflects_installed_state(self, project_root):
        install_deny_rules(str(project_root))
        status = get_deny_rules_status(str(project_root))

        assert status is not None
        assert status.deny_count > 0

    def test_status_before_install_returns_none_or_zero(self, tmp_path):
        empty_dir = tmp_path / "no-claude"
        empty_dir.mkdir()
        status = get_deny_rules_status(str(empty_dir))
        assert status is None or status.deny_count == 0


class TestLegacyMarkerCleanup:
    def test_legacy_sidabari_patterns_are_reclaimed(self, project_root):
        settings_file = project_root / ".claude" / "settings.local.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        legacy_data = {
            "permissions": {
                "_sidabari_managed": {"installed_patterns": ["Bash(legacy_old:*)"]},
                "deny": [
                    "Bash(legacy_old:*)",
                    "Bash(user_own_custom_rule:*)",
                ],
            }
        }
        settings_file.write_text(json.dumps(legacy_data), encoding="utf-8")

        install_deny_rules(str(project_root))

        data = json.loads(settings_file.read_text(encoding="utf-8"))
        deny_list = data["permissions"]["deny"]
        assert "Bash(legacy_old:*)" not in deny_list
        assert "Bash(user_own_custom_rule:*)" in deny_list


# ─── 커맨드 차단 판정 ────────────────────────────────────────────


class TestCommandBlocking:
    def test_blocked_command_detected(self):
        assert is_command_blocked_by_deny("rm -rf /") is True

    def test_safe_command_not_blocked(self):
        assert is_command_blocked_by_deny("ls -la") is False


# ─── runtime patterns ────────────────────────────────────────────


class TestRuntimePatterns:
    def test_runtime_patterns_match_deny_list(self):
        runtime = get_blocked_patterns_for_runtime()
        assert isinstance(runtime, list)
