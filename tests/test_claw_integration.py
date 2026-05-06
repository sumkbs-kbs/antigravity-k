"""
Claw Code 아키텍처 통합 테스트 — Phase 1~3 전체 검증
=====================================================
테스트 범위:
  1. PermissionGate     : 3-Tier 권한 결정 로직
  2. ContextShaper      : 5-Stage 압축 파이프라인
  3. SessionManager     : 세션 생성/저장/복원/메모리
  4. SlashCommandRegistry: 커맨드 등록/실행/자동완성
  5. ToolRegistry 연동  : 권한 게이트 통과 후 도구 실행
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)


# ─────────── 1. PermissionGate 테스트 ───────────


class TestPermissionGate(unittest.TestCase):
    """3-Tier 권한 모델 테스트."""

    def setUp(self):
        from antigravity_k.tools.permission_gate import PermissionGate

        self.gate = PermissionGate(project_root=tempfile.mkdtemp(), mode="balanced")

    def test_allow_safe_tool(self):
        """안전한 도구(safe)는 ALLOW."""
        from antigravity_k.tools.permission_gate import Permission

        result = self.gate.check("read_file", {"path": "test.py"}, risk_level="safe")
        self.assertEqual(result, Permission.ALLOW)

    def test_prompt_medium_risk(self):
        """medium 위험도는 PROMPT."""
        from antigravity_k.tools.permission_gate import Permission

        result = self.gate.check("write_file", {"path": "test.py"}, risk_level="medium")
        self.assertEqual(result, Permission.PROMPT)

    def test_deny_dangerous_command(self):
        """rm -rf / 같은 위험 명령은 DENY."""
        from antigravity_k.tools.permission_gate import Permission

        result = self.gate.check(
            "run_bash_command",
            {"command": "rm -rf /"},
            risk_level="high",
        )
        self.assertEqual(result, Permission.DENY)

    def test_deny_protected_path(self):
        """보호 경로(C:\\Windows 등) 접근은 DENY."""
        from antigravity_k.tools.permission_gate import Permission

        result = self.gate.check(
            "write_file",
            {"path": "C:\\Windows\\system32\\test.exe"},
            risk_level="low",
        )
        self.assertEqual(result, Permission.DENY)

    def test_override(self):
        """명시적 오버라이드가 risk_level보다 우선."""
        from antigravity_k.tools.permission_gate import Permission

        self.gate.set_override("write_file", Permission.ALLOW)
        result = self.gate.check("write_file", {"path": "x.py"}, risk_level="high")
        self.assertEqual(result, Permission.ALLOW)

    def test_approval_cache(self):
        """승인 캐시: PROMPT → 승인 기록 → 다음 요청 ALLOW."""
        from antigravity_k.tools.permission_gate import Permission

        result = self.gate.check("write_file", {}, risk_level="medium")
        self.assertEqual(result, Permission.PROMPT)
        self.gate.record_approval("write_file", "medium")
        result2 = self.gate.check("write_file", {}, risk_level="medium")
        self.assertEqual(result2, Permission.ALLOW)


# ─────────── 2. ContextShaper 테스트 ───────────


class TestContextShaper(unittest.TestCase):
    """5-Stage 컨텍스트 압축 파이프라인 테스트."""

    def setUp(self):
        from antigravity_k.engine.context_shaper import ContextShaper

        self.tmp_dir = tempfile.mkdtemp()
        self.shaper = ContextShaper(
            max_tokens=500,  # 작은 예산으로 테스트
            reserve_tokens=50,
            collapse_threshold=100,
            storage_dir=self.tmp_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_shape_within_budget(self):
        """예산 내이면 원본 그대로 반환."""
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = self.shaper.shape(msgs)
        self.assertEqual(len(result), len(msgs))

    def test_snip_removes_old_messages(self):
        """예산 초과 시 오래된 메시지가 절삭됨."""
        msgs = [{"role": "system", "content": "sys"}]
        for i in range(30):
            msgs.append({"role": "user", "content": f"question {i} " * 20})
            msgs.append({"role": "assistant", "content": f"answer {i} " * 20})
        result = self.shaper.shape(msgs)
        self.assertLess(len(result), len(msgs))

    def test_context_collapse_stores_reference(self):
        """긴 도구 출력이 참조 ID로 교체되고 파일 저장됨."""
        long_content = "x" * 500  # collapse_threshold(100) 초과
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "tool", "content": long_content, "name": "test_tool"},
        ]
        result = self.shaper._context_collapse(msgs)
        tool_msg = [m for m in result if m["role"] == "tool"][0]
        self.assertIn("ref:", tool_msg["content"])
        # 저장된 파일 확인
        json_files = [f for f in os.listdir(self.tmp_dir) if f.endswith(".json")]
        self.assertGreater(len(json_files), 0)

    def test_restore_collapsed(self):
        """참조 ID로 원본 복원 가능."""
        import hashlib

        content = "important data " * 50
        ref_id = hashlib.md5(content.encode()).hexdigest()[:12]
        ref_path = os.path.join(self.tmp_dir, f"{ref_id}.json")
        with open(ref_path, "w") as f:
            json.dump({"content": content, "ts": 0}, f)
        restored = self.shaper.restore_collapsed(ref_id)
        self.assertEqual(restored, content)

    def test_micro_compact_merges_tools(self):
        """연속 도구 결과가 하나로 병합됨."""
        msgs = [
            {"role": "user", "content": "q"},
            {"role": "tool", "content": "result1", "name": "t1"},
            {"role": "tool", "content": "result2", "name": "t2"},
            {"role": "tool", "content": "result3", "name": "t3"},
            {"role": "assistant", "content": "a"},
        ]
        result = self.shaper._micro_compact(msgs)
        tool_msgs = [m for m in result if m["role"] == "tool"]
        self.assertEqual(len(tool_msgs), 1)  # 3개 → 1개로 병합

    def test_stats_tracking(self):
        """압축 통계가 누적됨."""
        msgs = [{"role": "system", "content": "s"}]
        for i in range(20):
            msgs.append({"role": "user", "content": f"q{i} " * 30})
            msgs.append({"role": "assistant", "content": f"a{i} " * 30})
        self.shaper.shape(msgs)
        stats = self.shaper.get_stats()
        self.assertGreaterEqual(stats["total_shaped"], 1)

    def test_token_usage_report(self):
        """토큰 사용량 리포트가 올바른 키를 포함."""
        msgs = [
            {"role": "user", "content": "hello world"},
            {"role": "assistant", "content": "hi there"},
        ]
        usage = self.shaper.get_token_usage(msgs)
        self.assertIn("total_tokens", usage)
        self.assertIn("usage_pct", usage)
        self.assertIn("by_role", usage)


# ─────────── 3. SessionManager 테스트 ───────────


class TestSessionManager(unittest.TestCase):
    """3-Tier 메모리 모델 + 세션 영속성 테스트."""

    def setUp(self):
        from antigravity_k.engine.session_manager import SessionManager

        self.tmp_dir = tempfile.mkdtemp()
        self.sm = SessionManager(base_dir=self.tmp_dir)
        self.project_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        shutil.rmtree(self.project_dir, ignore_errors=True)

    def test_start_new_session(self):
        """새 세션이 생성되고 ID 반환."""
        sid = self.sm.start_session(project_path=self.project_dir)
        self.assertIsNotNone(sid)
        self.assertIn("_", sid)

    def test_add_turn_and_get_messages(self):
        """턴 추가 후 메시지 조회 가능."""
        self.sm.start_session(project_path=self.project_dir)
        self.sm.add_turn(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]
        )
        msgs = self.sm.get_messages()
        self.assertEqual(len(msgs), 2)

    def test_working_memory(self):
        """Working Memory 저장/조회."""
        self.sm.start_session(project_path=self.project_dir)
        self.sm.set_memory("project_type", "python")
        self.sm.set_memory("main_file", "app.py")
        self.assertEqual(self.sm.get_memory("project_type"), "python")
        mem = self.sm.get_all_memory()
        self.assertIn("main_file", mem)

    def test_session_save_and_resume(self):
        """세션 저장 후 같은 프로젝트에서 이어가기."""
        sid1 = self.sm.start_session(project_path=self.project_dir)
        self.sm.add_turn([{"role": "user", "content": "Hi"}])
        self.sm.set_memory("key1", "val1")
        self.sm.save()

        # 새 SessionManager로 같은 프로젝트 열기
        from antigravity_k.engine.session_manager import SessionManager

        sm2 = SessionManager(base_dir=self.tmp_dir)
        sid2 = sm2.start_session(project_path=self.project_dir, resume=True)
        self.assertEqual(sid1, sid2)
        self.assertEqual(sm2.get_memory("key1"), "val1")
        self.assertEqual(len(sm2.get_messages()), 1)

    def test_list_sessions(self):
        """세션 목록 조회."""
        self.sm.start_session(project_path=self.project_dir)
        self.sm.save()
        sessions = self.sm.list_sessions()
        self.assertGreaterEqual(len(sessions), 1)

    def test_session_info(self):
        """세션 정보에 필요 키 포함."""
        self.sm.start_session(project_path=self.project_dir)
        info = self.sm.get_session_info()
        self.assertIn("id", info)
        self.assertIn("turn_count", info)
        self.assertIn("message_count", info)

    def test_metadata_tracking(self):
        """도구/파일/토큰 메타데이터 추적."""
        self.sm.start_session(project_path=self.project_dir)
        self.sm.record_tool_use("write_file")
        self.sm.record_file_modified("app.py")
        self.sm.record_tokens(1500)
        info = self.sm.get_session_info()
        meta = info["metadata"]
        self.assertIn("write_file", meta["tools_used"])
        self.assertIn("app.py", meta["files_modified"])
        self.assertEqual(meta["total_tokens_used"], 1500)


# ─────────── 4. SlashCommandRegistry 테스트 ───────────


class TestSlashCommands(unittest.TestCase):
    """슬래시 커맨드 레지스트리 테스트."""

    def setUp(self):
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        self.registry = SlashCommandRegistry()

    def test_is_command(self):
        """/help은 커맨드, 일반 텍스트는 아님."""
        self.assertTrue(self.registry.is_command("/help"))
        self.assertTrue(self.registry.is_command("/tools"))
        self.assertFalse(self.registry.is_command("hello"))
        self.assertFalse(self.registry.is_command("/unknown_cmd"))

    def test_help_command(self):
        """/help 실행 시 커맨드 목록 반환."""
        result = self.registry.execute("/help")
        self.assertIn("슬래시 커맨드", result)
        self.assertIn("/tools", result)
        self.assertIn("/goal", result)

    def test_status_command(self):
        """/status 실행."""
        result = self.registry.execute("/status")
        self.assertIn("Antigravity-K", result)

    def test_unknown_command(self):
        """알 수 없는 커맨드는 에러 메시지."""
        result = self.registry.execute("/xyz123")
        self.assertIn("Unknown command", result)

    def test_completions(self):
        """자동완성 후보 반환."""
        completions = self.registry.get_completions("/he")
        self.assertIn("/help", completions)

        goal_completions = self.registry.get_completions("/go")
        self.assertIn("/goal", goal_completions)

    def test_completions_empty(self):
        """매칭 없으면 빈 리스트."""
        completions = self.registry.get_completions("/zzz")
        self.assertEqual(len(completions), 0)

    def test_memory_without_session(self):
        """/memory — 세션 없을 때 안전하게 동작."""
        result = self.registry.execute("/memory")
        self.assertIn(
            "not connected", result.lower() if isinstance(result, str) else ""
        )

    def test_context_without_shaper(self):
        """/context — 셰이퍼 없을 때 안전하게 동작."""
        result = self.registry.execute("/context")
        self.assertIn(
            "not connected", result.lower() if isinstance(result, str) else ""
        )

    def test_goal_command(self):
        """/goal — 목표를 자율 실행 계약으로 변환."""
        result = self.registry.execute(
            "/goal 테스트 리포트를 만들고 DOM 기능을 검증해줘"
        )
        self.assertIn("/goal Autonomous Goal Contract", result)
        self.assertIn("Success Criteria", result)
        self.assertIn("Autonomous Judgment Policy", result)
        self.assertIn("Capability Transfer Matrix", result)


# ─────────── 5. 통합 E2E 흐름 테스트 ───────────


class TestE2EWorkflow(unittest.TestCase):
    """전체 워크플로우: 세션 → 컨텍스트 관리 → 슬래시 커맨드."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.session_dir = os.path.join(self.tmp_dir, "sessions")
        self.context_dir = os.path.join(self.tmp_dir, "context")
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.context_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_session_context_slash_integration(self):
        """세션 생성 → 메시지 추가 → 압축 → 슬래시 커맨드 조회."""
        from antigravity_k.engine.session_manager import SessionManager
        from antigravity_k.engine.context_shaper import ContextShaper
        from antigravity_k.engine.slash_commands import SlashCommandRegistry

        # 1. 세션 생성
        sm = SessionManager(base_dir=self.session_dir)
        sm.start_session(project_path=self.tmp_dir)
        sm.set_memory("lang", "python")

        # 2. 대화 추가
        for i in range(10):
            sm.add_turn(
                [
                    {"role": "user", "content": f"question {i}"},
                    {"role": "assistant", "content": f"answer {i}" * 10},
                ]
            )

        # 3. 컨텍스트 셰이퍼
        shaper = ContextShaper(
            max_tokens=200,
            reserve_tokens=20,
            storage_dir=self.context_dir,
        )
        messages = sm.get_messages()
        shaped = shaper.shape(messages)
        self.assertLessEqual(len(shaped), len(messages))

        # 4. 슬래시 커맨드 (세션 + 셰이퍼 연동)
        slash = SlashCommandRegistry(
            session_manager=sm,
            context_shaper=shaper,
        )
        help_result = slash.execute("/help")
        self.assertIn("/help", help_result)
        status_result = slash.execute("/status")
        self.assertIn("세션", status_result)

    def test_permission_gate_path_sandbox(self):
        """경로 샌드박싱: 프로젝트 내부 vs 외부."""
        from antigravity_k.tools.permission_gate import PermissionGate, Permission

        project = os.path.join(self.tmp_dir, "myproject")
        os.makedirs(project, exist_ok=True)
        gate = PermissionGate(project_root=project, mode="strict")

        # 프로젝트 내부 읽기 = ALLOW
        result = gate.check("read_file", {"path": os.path.join(project, "app.py")})
        self.assertEqual(result, Permission.ALLOW)

        # 프로젝트 외부 쓰기 = DENY (strict)
        result = gate.check("write_file", {"path": "/tmp/outside.py"}, risk_level="low")
        self.assertEqual(result, Permission.DENY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
