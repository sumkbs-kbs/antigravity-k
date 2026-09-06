# WS-03 Adversarial notes

1. Concurrent create race for same project_id: registry prefers first inserted;
   duplicate is shut down (no double-live runtime).
2. Root path change for same project_id: existing handle shut down and replaced
   (never field-patch root onto live orchestrator).
3. Init explosion in factory: exception propagates; other projects remain.
4. LRU overflow: victim shutdown under lock; keep_project_id protected.
5. MemoryManager.bind_project_root still raises on foreign rebind for a single
   manager — isolation is achieved by separate managers per project_id, not by
   relaxing the bind guard.

6. Session DI: chat must use ProjectRuntime.session_manager + start_session(project_path=canonical_root).
7. Slash/job registries must be per-project (or rebound every request) — never freeze first runtime.
8. Durable clear hooks must close over project_root; Path.cwd() vector clear is a cross-project wipe.
9. Production factory must attach RAGIndexer + project vault; manually injecting indexer in tests is not proof.
