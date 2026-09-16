# Bounded independent review — 2026-09-15

Target and observed final HEAD: `ffb0ebb312b76d86742d3e4065628a9704f8268e`.
Read-only source audit; no source changes, no service/soak control, no subagents. TemporaryDirectory synthetic probes cleaned automatically. Retained evidence: this report and `/tmp/ssak-review-retry-tests.log`. Graph discovery preceded source inspection. Existing reports `/tmp/ssak-review-security.md` and `...backend.md` target 08b8bb2, so their historical findings are not asserted as current findings. Scope is the four requested claims, not whole-program certification.

## quality — FAIL

**P1: Deleted session content can be resurrected by an already-loaded writer.** `src/antigravity_k/engine/session_manager.py:438–469` unlinks session JSONs on clear(all), without a deletion tombstone. `_save_session` at :717–729 checks stale revision only when a disk revision exists; missing file becomes revision 1 regardless of the writer's nonzero base revision. Synthetic direct SessionManager probe: A creates/saves one marker message; B resumes same session; A clear_memory('all'); B save(). Observed `deleted=1`, `resurrected=true`, JSON messages contain `synthetic deleted marker`. This is sequential two-instance reproduction, not an unobserved timing theory. Fix needs deletion generation/tombstone or missing-file stale rejection plus clear/save lock coordination.

**P1: Repeated automatic compaction loses previously summarized requirements.** Independently code-confirmed: `conversation_store.py:485–524` replaces old messages with one role=system summary and retained tail; default compaction triggers after 64 (:600–604). `context_summary.py:37–52` fallback selects user/tool content, excluding the old system summary. Parent root supplied separately executed TemporaryDirectory evidence: initial `EARLY_REQUIREMENT_KEEP_OFFLINE` present at appends64/65/122, absent at123; counts64/7/64/7. This runtime evidence is parent-supplied, not independently rerun here. Preserve old summary in cumulative summarization and test repeated boundaries.

## security — FAIL for credential-revocation expectation; scope limited

**P2: Changing PIN leaves existing bearer tokens valid.** `api/auth_routes.py:354–367` persists and replaces the PIN hash but does not rotate/revoke tokens. `engine/auth.py:233–260` verifies signature/expiry/issuer only, without credential generation. Isolated direct route call with synthetic Request subject and temp hash/signing files observed `changed=True`, `old_token_valid=True`, service default `ttl_seconds=43200`. First probe failed before handler with missing Request path; corrected probe supplied full path/method and succeeded. No real credentials read or changed. This verifies the handler/token-service behavior, not a full network login test. Existing tokens surviving rotation may be deliberate session policy, but PIN change cannot currently be presented as compromised-session revocation; define policy and add revocation if that is the intended guarantee. Config TTL is configurable; 43200 is the TokenService default used in probe, not proof every deployed token has that TTL.

## QA — INCONCLUSIVE for full QA; bounded regressions PASS with contract gap

Executed current source: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest tests/test_val02_conversation_multiprocess.py tests/test_cr02_session_durability.py -q -p no:cacheprovider --override-ini addopts=''`.
Result: **21 passed, 1 warning in 3.77s**, exit0. Evidence `/tmp/ssak-review-retry-tests.log`.

**P2: Multiprocess final-count assertion conflicts with default compaction.** `tests/test_val02_conversation_multiprocess.py:47–71` runs (4,10)/(6,20), asserts final_count >= appended, and labels any deficit silent overwrite. Default `conversation_store.py:56–68,600–604` compacts after64. Independent single-writer probe using same default append path: 120 successful appends, final_count62, revision120, summary present. Therefore a deficit is not sufficient evidence of CAS overwrite, and the multiprocess test can pass only because its observed accepted-write count/scheduling avoids that condition (this run did pass; accepted count was not emitted). Do not claim an observed failing multiprocess run here. Test CAS with compaction disabled, and separately assert revision/success accounting and retained-tail/summary correctness under compaction.

These tests do not cover clear(all) versus a loaded writer or old-token revocation. Browser, installation, long soak, cluster and full gate execution were not done in this lane.

## context — FAIL for deploy instructions/readiness wiring; runtime cluster INCONCLUSIVE

**P2: Fresh-cluster documented namespace sequence is incomplete.** `deploy/README.md:58–64` creates secret in namespace antigravity-k before applying manifests; namespace is only provided by `deploy/k8s/namespace.yaml:18–21`. README prerequisites do not require this namespace already exists. Static finding: documented first command requires a namespace not yet created. Apply namespace manifest first, then secret, then remaining manifests. No kubectl deployment was attempted.

**P2: Kubernetes readiness checks general health rather than dependency readiness.** `deploy/k8s/deployment.yaml:73–80` targets /health. `api/routes/models_api.py:68–96` returns status ok, whereas `api/server.py:587–596` implements public /api/ready and returns503 for not_ready after dependency checks; public allowlist includes it at :385. A dependency readiness failure is therefore not represented by the configured readiness probe. Use /api/ready for readiness and retain process health for liveness. Static wiring evidence only; cluster outage behavior not executed.

Commercial context remains limited by target mismatch: historical complete gate results are not proof of this HEAD. The separate current context report `/tmp/ssak-review-20260915-goals.md` explains historical 23/23 candidate vs later code changes and soak evidence boundaries. No claim is made that pending soak has failed or passed.

### Parent-supplied additional current evidence

The root reviewer reports an earlier current-head batch outcome **58 passed / 1 failed**, specifically multiprocess `[6-20]` final-count regression. This lane's later **21 passed** outcome is a separate execution, not a correction or cancellation of that failure. Accepted CAS writes vary with scheduling; crossing the64-message compaction boundary makes the final-count assertion fail despite preserved revision accounting. The initial raw log was not recovered after the original agent hit its usage limit. Treat 58/1 as an unverified parent-reported outcome, excluded from retained execution totals. This lane did not execute or independently inspect that earlier batch; the retained executable total is 21 passed.

Root's latest soak observation at20:43KST: elapsed5h36, live RSS114192KiB, final JSON absent. This is parent-reported in-progress telemetry, not an8-hour PASS/FAIL result; the soak was left untouched.
