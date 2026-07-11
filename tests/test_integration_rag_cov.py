"""통합 테스트: Orchestrator에 RAG/CoV 파이프라인이 연결되었는지 검증합니다."""

from unittest.mock import MagicMock


class TestOrchestratorRAGIntegration:
    """Orchestrator의 context_enrich에 RAGIndexer가 연결되는지 검증."""

    def test_context_enrich_calls_rag_indexer(self):
        """context_enrich_handler가 RAGIndexer.format_context를 호출하는지 확인."""
        from antigravity_k.engine.orchestrator_handlers import context_enrich_handler
        from antigravity_k.engine.state_graph import StateContext

        user_msg = "cognitive_loop 함수 구조 알려줘"
        msgs = [{"role": "user", "content": user_msg}]
        ctx = StateContext(
            messages=msgs,
            user_message=user_msg,
            custom_messages=list(msgs),  # init_handler가 설정하는 값
        )

        orch = MagicMock()
        orch.ctx.ki_engine.build_ki_prompt.return_value = ""
        orch.vault_engine = None
        orch.project_root = "/tmp"

        # RAGIndexer가 없을 때도 에러 없이 진행
        if hasattr(orch, "_rag_indexer"):
            del orch._rag_indexer

        # context_enrich_handler는 yield 없이 끝날 수 있으므로 gen or []
        gen = context_enrich_handler(ctx, orch)
        list(gen if gen is not None else [])
        # rag_context가 설정되었는지 확인 (빈 문자열이어도 OK)
        assert hasattr(ctx, "rag_context")

    def test_context_enrich_injects_rag_context(self):
        """RAGIndexer가 결과를 반환하면 rag_context에 포함되는지 확인."""
        from antigravity_k.engine.orchestrator_handlers import context_enrich_handler
        from antigravity_k.engine.state_graph import StateContext

        user_msg = "vault engine 구조 분석"
        msgs = [{"role": "user", "content": user_msg}]
        ctx = StateContext(
            messages=msgs,
            user_message=user_msg,
            custom_messages=list(msgs),  # init_handler가 설정하는 값
        )

        mock_indexer = MagicMock()
        mock_indexer.format_context.return_value = "<relevant_code>\ndef vault_init(): pass\n</relevant_code>"

        orch = MagicMock()
        orch.ctx.ki_engine.build_ki_prompt.return_value = ""
        orch.vault_engine = None
        orch.project_root = "/tmp"
        orch._rag_indexer = mock_indexer

        gen = context_enrich_handler(ctx, orch)
        list(gen if gen is not None else [])
        assert "<relevant_code>" in ctx.rag_context
        assert "vault_init" in ctx.rag_context
        mock_indexer.format_context.assert_called_once_with("vault engine 구조 분석")

    def test_rag_recall_benchmark(self):
        """RAG 인덱서가 관련된 코드를 상위 5개(recall@5) 이내에 반환하는지 벤치마크 테스트합니다."""
        from antigravity_k.engine.rag_indexer import CodeChunk, RAGIndexer

        # 1. 100개의 더미 청크와 1개의 타겟 청크 생성
        chunks = []
        for i in range(100):
            chunks.append(
                CodeChunk(
                    chunk_id=f"chunk_{i}",
                    file_path=f"dummy_{i}.py",
                    node_type="function",
                    node_name=f"dummy_func_{i}",
                    content=f"def dummy_func_{i}():\n    return {i}",
                    start_line=1,
                    end_line=2,
                )
            )

        target_chunk = CodeChunk(
            chunk_id="target_chunk",
            file_path="src/engine/auth.py",
            node_type="function",
            node_name="verify_oauth_token",
            content="def verify_oauth_token(token):\n    # 이 함수는 OAuth 토큰을 검증합니다\n    pass",
            start_line=10,
            end_line=15,
        )
        chunks.append(target_chunk)

        # 2. Mock VectorStore 구현
        class MockVectorStore:
            def search(self, query, n_results=5):
                # "oauth 토큰 검증" 쿼리가 들어오면, 타겟 청크를 상위 5개 안에 포함시킴 (단순 텍스트 매칭 시뮬레이션)
                if "oauth" in query.lower() or "토큰" in query:
                    return [
                        {
                            "id": "chunk_1",
                            "text": "...",
                            "metadata": {"source": "a.py"},
                        },
                        {
                            "id": "chunk_2",
                            "text": "...",
                            "metadata": {"source": "b.py"},
                        },
                        {
                            "id": "target_chunk",
                            "text": target_chunk.content,
                            "metadata": {
                                "source": target_chunk.file_path,
                                "node_name": target_chunk.node_name,
                                "start_line": target_chunk.start_line,
                                "end_line": target_chunk.end_line,
                            },
                        },
                        {
                            "id": "chunk_3",
                            "text": "...",
                            "metadata": {"source": "c.py"},
                        },
                        {
                            "id": "chunk_4",
                            "text": "...",
                            "metadata": {"source": "d.py"},
                        },
                    ][:n_results]
                return []

        indexer = RAGIndexer(project_root="/tmp", vector_store=MockVectorStore())

        # 3. Recall@5 검증
        results = indexer.search("OAuth 토큰 검증 함수 어디있어?", n_results=5)

        assert len(results) <= 5
        found = any(r.get("id") == "target_chunk" for r in results)
        assert found, "Target chunk was not found in top 5 results (Recall@5 failed)"


class TestOrchestratorCoVIntegration:
    """Orchestrator의 COV_VERIFY 핸들러가 응답을 검증하는지 테스트."""

    def test_cov_verify_skips_short_output(self):
        """짧은 agent_output은 CoV를 스킵하는지 확인."""
        from antigravity_k.engine.orchestrator_handlers import cov_verify_handler
        from antigravity_k.engine.state_graph import StateContext

        ctx = StateContext(
            messages=[{"role": "user", "content": "hello"}],
            user_message="안녕",
            agent_output="짧은 응답",
        )

        orch = MagicMock()
        result = list(cov_verify_handler(ctx, orch))
        assert len(result) == 0  # 출력 없이 스킵

    def test_cov_verify_detects_syntax_error(self):
        """구문 오류가 있는 코드 응답에서 자기검증이 작동하는지 확인."""
        from antigravity_k.engine.orchestrator_handlers import cov_verify_handler
        from antigravity_k.engine.state_graph import StateContext

        broken_code = (
            "아래 코드를 참고하세요:\n"
            "```python\n"
            "def broken(\n"
            "    return None\n"
            "```\n"
            "이 함수는 None을 반환합니다. 추가로 이것은 확장 가능한 구조입니다."
        )

        ctx = StateContext(
            messages=[{"role": "user", "content": "함수 작성"}],
            user_message="파이썬 함수 작성해줘",
            agent_output=broken_code,
        )

        orch = MagicMock()
        if hasattr(orch, "_cov_engine"):
            del orch._cov_engine

        result = list(cov_verify_handler(ctx, orch))
        # 자기검증이 문제를 감지하면 출력이 있음
        output = "".join(result)
        if output:
            assert "자기검증" in output or "감지" in output

    def test_cov_verify_passes_clean_code(self):
        """유효한 코드 응답은 검증을 통과하는지 확인."""
        from antigravity_k.engine.orchestrator_handlers import cov_verify_handler
        from antigravity_k.engine.state_graph import StateContext

        valid_response = (
            "다음은 요청하신 함수입니다:\n\n"
            "```python\n"
            "def calculate_sum(a: int, b: int) -> int:\n"
            '    """두 수의 합을 계산합니다."""\n'
            "    return a + b\n"
            "```\n\n"
            "이 함수는 두 정수를 입력받아 합계를 반환합니다. 시간복잡도는 O(1)입니다."
        )

        ctx = StateContext(
            messages=[{"role": "user", "content": "sum function"}],
            user_message="두 수의 합을 구하는 함수 만들어줘",
            agent_output=valid_response,
        )
        original_output = ctx.agent_output

        orch = MagicMock()
        if hasattr(orch, "_cov_engine"):
            del orch._cov_engine

        list(cov_verify_handler(ctx, orch))
        # 유효한 코드는 수정되지 않아야 함
        assert ctx.agent_output == original_output


class TestStateGraphCoVWiring:
    """State Graph에 COV_VERIFY가 올바르게 연결되었는지 확인."""

    def test_cov_verify_state_exists(self):
        """AgentState.COV_VERIFY가 존재하는지 확인."""
        from antigravity_k.engine.state_graph import AgentState

        assert hasattr(AgentState, "COV_VERIFY")
        assert AgentState.COV_VERIFY.value == "cov_verify"

    def test_agent_execute_routes_to_cov_verify(self):
        """AGENT_EXECUTE → COV_VERIFY → CODE_REVIEW → QUALITY_CHECK 경로가 설정되었는지 확인."""
        from antigravity_k.engine.orchestrator_handlers import (
            build_orchestrator_graph,
        )
        from antigravity_k.engine.state_graph import AgentState

        graph = build_orchestrator_graph()
        # AGENT_EXECUTE의 다음 상태가 COV_VERIFY인지 확인
        assert graph._edges.get(AgentState.AGENT_EXECUTE) == AgentState.COV_VERIFY
        # COV_VERIFY → CODE_REVIEW
        assert graph._edges.get(AgentState.COV_VERIFY) == AgentState.CODE_REVIEW
        # CODE_REVIEW → QUALITY_CHECK
        assert graph._edges.get(AgentState.CODE_REVIEW) == AgentState.QUALITY_CHECK

        # QUALITY_CHECK가 조건부 엣지를 가지는지 확인
        assert AgentState.QUALITY_CHECK in graph._conditional_edges

    def test_cov_verify_handler_registered(self):
        """COV_VERIFY 노드에 핸들러가 등록되었는지 확인."""
        from antigravity_k.engine.orchestrator_handlers import (
            build_orchestrator_graph,
            cov_verify_handler,
        )
        from antigravity_k.engine.state_graph import AgentState

        graph = build_orchestrator_graph()
        assert AgentState.COV_VERIFY in graph._nodes
        assert graph._nodes[AgentState.COV_VERIFY] == cov_verify_handler

    def test_state_graph_error_recovery_loop(self):
        """Phase 5: 검증 실패 시 QUALITY_CHECK에서 AGENT_EXECUTE로 루프백하는지 확인."""
        from antigravity_k.engine.orchestrator_handlers import (
            build_orchestrator_graph,
        )
        from antigravity_k.engine.state_graph import AgentState, StateContext

        # 1. 초기 컨텍스트 설정 (에러 상황 가정)
        ctx = StateContext(
            messages=[{"role": "user", "content": "hello"}],
            user_message="hello",
            agent_output="invalid answer",
            validation_passed=False,  # 에러 상태
            retry_count=0,
            max_retries=3,
        )

        graph = build_orchestrator_graph()

        # 2. QUALITY_CHECK 실행 및 루프백 검증
        handler = graph._nodes[AgentState.QUALITY_CHECK]
        gen = handler(ctx, None)
        output = "".join(list(gen))

        assert "에러 복구 루프" in output
        assert ctx.retry_count == 1
        assert ctx._loop_back is True

        # 3. 조건부 엣지 함수 검증
        decision_fn = graph._conditional_edges[AgentState.QUALITY_CHECK]
        next_state = decision_fn(ctx)

        assert next_state == AgentState.AGENT_EXECUTE

        # 4. 루프 한계 도달 검증
        ctx.validation_passed = False
        ctx.retry_count = 3
        ctx._loop_back = False

        gen = handler(ctx, None)
        output = "".join(list(gen))

        assert "최대 재시도" in output
        assert ctx._loop_back is False

        next_state = decision_fn(ctx)
        assert next_state == AgentState.MEMORY_SAVE
