"""테스트: KIEngine persistent_context 예산.
====================================
KI 누적과 무관하게 프롬프트 크기가 상한 내로 유한함을 검증한다.
최신 KI 우선 포함, 생략 표시, 첫 KI 강제 포함을 잠근다.
"""

import json
import os
import time

from antigravity_k.engine.knowledge import MAX_KI_PROMPT_CHARS, KIEngine


def _write_ki(engine: KIEngine, ki_id: str, title: str, summary: str, mtime: float | None = None):
    engine.save_ki(ki_id, {"title": title, "summary": summary})
    if mtime is not None:
        os.utime(os.path.join(engine.ki_dir, f"{ki_id}_metadata.json"), (mtime, mtime))


class TestBuildKiPromptBudget:
    def test_empty_knowledge_returns_empty_prompt(self, tmp_path):
        engine = KIEngine(project_root=str(tmp_path))

        assert engine.build_ki_prompt() == ""

    def test_small_kis_all_included_with_header(self, tmp_path):
        engine = KIEngine(project_root=str(tmp_path))
        _write_ki(engine, "a", "패턴 A", "요약 A")
        _write_ki(engine, "b", "패턴 B", "요약 B")

        prompt = engine.build_ki_prompt()

        assert "<persistent_context>" in prompt
        assert "패턴 A" in prompt
        assert "패턴 B" in prompt

    def test_budget_bounds_total_and_marks_skipped(self, tmp_path):
        engine = KIEngine(project_root=str(tmp_path))
        now = time.time()
        for idx in range(12):
            _write_ki(
                engine,
                f"ki{idx}",
                f"지식 {idx}",
                "내용이 긴 요약입니다. " * 40,
                mtime=now - idx * 100,
            )

        prompt = engine.build_ki_prompt()

        assert len(prompt) < MAX_KI_PROMPT_CHARS + 200
        assert "예산 초과로 생략됨" in prompt
        assert "지식 0" in prompt  # 최신 KI는 포함
        assert "지식 11" not in prompt  # 가장 오래된 KI는 생략

    def test_newest_ki_wins_when_all_exceed_budget_alone(self, tmp_path):
        engine = KIEngine(project_root=str(tmp_path))
        now = time.time()
        _write_ki(engine, "old", "오래된 지식", "old-summary", mtime=now - 9999)
        _write_ki(engine, "new", "최신 지식", "x" * (MAX_KI_PROMPT_CHARS * 2), mtime=now)

        prompt = engine.build_ki_prompt()

        assert "최신 지식" in prompt
        assert len(prompt) <= MAX_KI_PROMPT_CHARS + 120

    def test_mtime_missing_sorts_last(self, tmp_path):
        engine = KIEngine(project_root=str(tmp_path))
        now = time.time()
        _write_ki(engine, "with_time", "시간 있음", "s1", mtime=now)
        path = os.path.join(engine.ki_dir, "no_time_metadata.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"title": "시간 없음", "summary": "s2"}, f)
        os.chmod(path, 0o644)
        os.utime(path, (1, 1))  # 매우 오래된 mtime

        prompt = engine.build_ki_prompt()

        assert prompt.index("시간 있음") < prompt.index("시간 없음")

    def test_load_kis_reports_count_for_analysis_handler(self, tmp_path):
        engine = KIEngine(project_root=str(tmp_path))
        _write_ki(engine, "a", "제목", "요약")

        assert len(engine.load_kis()) == 1
