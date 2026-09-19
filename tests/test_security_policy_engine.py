"""테스트: SecurityPolicyEngine — 선언적 보안 정책.
============================================
권한 결정 순서(오버라이드→시드→안전 폴백), 도구명 정규화,
Fail-Closed 동작, 커맨드/도메인 차단 규칙을 검증한다.
"""

from pathlib import Path
from typing import cast

import yaml

from antigravity_k.engine.security_policy import (
    PermissionState,
    SecurityPolicyEngine,
    effective_permission,
    seeded_default_permission,
)


class TestEffectivePermission:
    def test_known_tool_returns_seeded_default(self):
        assert seeded_default_permission("read_file") == PermissionState.ALWAYS_ALLOW
        assert seeded_default_permission("run_bash_command") == PermissionState.ASK_EACH_TIME

    def test_hyphen_names_resolve_to_canonical_seeded(self):
        assert seeded_default_permission("read-file") == PermissionState.ALWAYS_ALLOW

    def test_unknown_tool_returns_none_from_seed(self):
        assert seeded_default_permission("made_up_tool") is None

    def test_override_beats_seeded_default(self):
        resolved = effective_permission("read_file", {"read_file": PermissionState.DISABLED})

        assert resolved == PermissionState.DISABLED

    def test_override_matches_hyphen_variant_of_hyphen_input(self):
        resolved = effective_permission("read-file", {"read-file": PermissionState.DISABLED})

        assert resolved == PermissionState.DISABLED

    def test_fallback_is_ask_each_time_for_unknown_tools(self):
        assert effective_permission("brand_new_tool", {}) == PermissionState.ASK_EACH_TIME

    def test_resolution_order_override_then_seed_then_fallback(self):
        assert effective_permission("write_file", {}) == PermissionState.ASK_EACH_TIME
        assert (
            effective_permission("write_file", {"write_file": PermissionState.ALWAYS_ALLOW})
            == PermissionState.ALWAYS_ALLOW
        )


# ── Fail-Closed & 정책 로드 ───────────────────────────────────────


class TestFailClosed:
    def test_corrupt_policy_yaml_blocks_everything(self, tmp_path: Path):
        policy_file = tmp_path / "broken.yaml"
        _ = policy_file.write_text("process: [unclosed", encoding="utf-8")

        engine = SecurityPolicyEngine(policy_file=str(policy_file))

        assert engine.is_fail_closed is True
        assert engine.is_command_allowed("echo hi") is False
        assert engine.is_domain_allowed("example.com") is False

    def test_missing_policy_file_keeps_safe_defaults(self, tmp_path: Path):
        engine = SecurityPolicyEngine(policy_file=str(tmp_path / "absent.yaml"))

        assert engine.is_fail_closed is False
        assert engine.is_command_allowed("rm -rf /") is True  # 차단 목록이 비어 있으면 허용


# ── 커맨드/도메인 규칙 ────────────────────────────────────────────


def _engine_with(tmp_path: Path, policy: dict[str, object]) -> SecurityPolicyEngine:
    policy_file = tmp_path / "policy.yaml"
    _ = policy_file.write_text(yaml.safe_dump(policy), encoding="utf-8")
    return SecurityPolicyEngine(policy_file=str(policy_file))


class TestCommandRules:
    def test_blocked_command_substring_is_denied(self, tmp_path: Path):
        engine = _engine_with(tmp_path, {"process": {"blocked_commands": ["mkfs", "shutdown"]}})

        assert engine.is_command_allowed("sudo shutdown now") is False
        assert engine.is_command_allowed("echo mkfs.ext4") is False
        assert engine.is_command_allowed("ls -la") is True


class TestDomainRules:
    def test_blocked_domain_denied_even_in_allow_all_mode(self, tmp_path: Path):
        engine = _engine_with(
            tmp_path,
            {"network": {"allowed_domains": [], "blocked_domains": ["evil.io"]}},
        )

        assert engine.is_domain_allowed("sub.evil.io") is False
        assert engine.is_domain_allowed("example.com") is True

    def test_non_empty_allow_list_becomes_default_deny(self, tmp_path: Path):
        engine = _engine_with(
            tmp_path,
            {
                "network": {
                    "allowed_domains": ["github.com"],
                    "blocked_domains": [],
                }
            },
        )

        assert engine.is_domain_allowed("api.github.com") is True
        assert engine.is_domain_allowed("pypi.org") is False


# ── 도구 권한 엔진 ────────────────────────────────────────────────


class TestToolPermissionEngine:
    def test_set_permission_canonicalizes_name_and_get_returns_it(self, tmp_path: Path):
        engine = SecurityPolicyEngine(policy_file=str(tmp_path / "absent.yaml"))

        engine.set_tool_permission("write-file", PermissionState.ALWAYS_ALLOW)

        assert engine.get_tool_permission("write_file") == PermissionState.ALWAYS_ALLOW
        assert engine.is_tool_auto_allowed("write_file") is True

    def test_disabled_tool_is_not_allowed(self, tmp_path: Path):
        engine = SecurityPolicyEngine(policy_file=str(tmp_path / "absent.yaml"))
        engine.set_tool_permission("run_bash_command", PermissionState.DISABLED)

        assert engine.is_tool_allowed("run_bash_command") is False

    def test_ask_each_time_tool_is_allowed_but_not_auto(self, tmp_path: Path):
        engine = SecurityPolicyEngine(policy_file=str(tmp_path / "absent.yaml"))

        assert engine.is_tool_allowed("run_bash_command") is True
        assert engine.is_tool_auto_allowed("run_bash_command") is False

    def test_valid_policy_load_updates_rules(self, tmp_path: Path):
        engine = _engine_with(
            tmp_path,
            {
                "process": {"blocked_commands": ["danger"]},
                "network": {"allowed_domains": [], "blocked_domains": []},
                "filesystem": {"allowed_paths": ["/tmp"], "read_only_paths": []},
            },
        )

        assert engine.is_fail_closed is False
        filesystem = cast(dict[str, list[str]], engine.policy["filesystem"])
        assert filesystem["allowed_paths"] == ["/tmp"]
        assert engine.is_command_allowed("run danger script") is False
