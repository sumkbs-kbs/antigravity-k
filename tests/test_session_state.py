"""테스트: 공유 에이전트 세션 싱글톤 계약.
==================================
세션 리셋이 객체 정체를 유지하고, 모듈 간 값 복사 임포트 후에도
stale 바인딩이 발생하지 않음을 검증한다.
"""

from antigravity_k.api.routes import session_state


class TestSharedSessionBinding:
    def test_reset_preserves_identity_and_clears_fields(self):
        session = session_state.get_active_session()
        session.q = "이전 질문"
        session.is_active = True
        session.history.append("chunk")
        session.done = True

        same = session_state.reset_active_session()

        assert same is session  # 정체 유지 — 소비자의 값 복사 바인딩 보호
        assert session.q == ""
        assert session.is_active is False
        assert session.history == []
        assert session.done is False

    def test_agent_stream_uses_shared_singleton_not_private_copy(self):
        # 스트림 라우트가 세션을 교체(rebinding)하지 않고 공유 정체를 유지한다.
        before = session_state.get_active_session()
        import antigravity_k.api.routes.agent_stream_api as stream_api

        stream_api.reset_active_session()
        after = session_state.get_active_session()
        assert after is before

    def test_close_unauthorized_ws_importable_from_neutral_module(self):
        from antigravity_k.api.routes.session_state import close_unauthorized_ws

        assert callable(close_unauthorized_ws)
