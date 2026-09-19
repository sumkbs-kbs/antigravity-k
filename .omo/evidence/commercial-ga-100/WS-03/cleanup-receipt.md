# WS-03 Cleanup receipt

- `OrchestratorAgent.shutdown()` stops AmbientWatchdog, closes RAG `vector_store`
  if present, clears model compressor / trajectory / prompt / skill-learner caches.
- `ProjectRuntime.shutdown()` delegates to orchestrator.shutdown and drops
  `agent_runtime` reference.
- `ProjectRuntimeRegistry.evict` / `shutdown_all` / `reset_project_runtime_registry`
  clear process maps.
- `DELETE /api/projects/{project_id}` calls `evict_project_runtime` after registry remove.
- Test fixtures call `reset_runtime_dependencies()` in autouse teardown.
