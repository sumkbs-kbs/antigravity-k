# Final manual QA — 2026-09-10

- Reviewed HEAD: `8794aaecabf5664a7ee560b104e0115d915aabb7`
- Overall verdict: **FAIL** — focused backend QA has one reproducible package-data/config-drift failure at this exact SHA.
- Surface scope: workspace/project switching, workspace context, conversation compaction/CAS, auth boundary, dashboard build/test gates, focused backend contracts.
- Runtime refs: Python 3.13.12 via `uv`; Node 22.23.1; Playwright Chromium headless 1440×1000.
- ulw-loop status: no plan (`ULW_LOOP_PLAN_MISSING`), so artifacts are under this requested QA directory.
- Existing repository state before QA: dirty `vault_data` submodule; no product source edits made.

## Overall verdict: FAIL

Backend config consistency fails at the reviewed SHA. Browser results below are the QA executor’s reported observations; the referenced raw browser action transcript was not preserved. Screenshots alone cannot prove compact response values. Live provider and eight-hour soak remain required GA evidence, not waived criteria.

## manualQa

### surfaceEvidence

| scenario id | criterion reference | surface | exact invocation | verdict | artifactRefs |
|---|---|---|---|---|---|
| AUTH-01 | SEC-01/SEC-02 auth boundary | HTTP + browser bootstrap | `curl -i --max-time 5 http://127.0.0.1:8000/api/workspace/context`; Playwright `goto('http://127.0.0.1:8000/')` | PASS — missing credential returned HTTP 401 and the browser rendered the lock screen | A1, A4 |
| WS-01 | workspace switch and active identity | Browser UI + HTTP readback | Playwright: seed `/api/projects` in a temporary server, reload, click `.project-folder-box` containing `ssak-qa.OZYbgH`, wait for `/api/projects/switch`, then GET `/api/workspace/context` | PASS — 200 switch, active label changed `QA Beta` → `ssak-qa.OZYbgH`, context and localStorage matched | A2, A3, A4 |
| CTX-01 | authoritative compact/revision contract | Browser-origin HTTP API (no compact UI button flow) | Playwright page `fetch`: 8 sequential `POST /v1/conversations/append`, `POST /v1/conversations/compact`, then `GET /v1/conversations/qa-browser-compact-live?project_id=default` | PASS — append 200×8; compact 200; revision 8→9; messages 8→4; estimated tokens 480→276 | A3, A4 |
| GA-01 | declared dashboard release checks | Dashboard CLI | `pnpm run typecheck`; `pnpm run test`; `pnpm run lint`; `pnpm run build` in `dashboard/` | PASS — typecheck 0; 70 files/750 tests pass; lint 0 errors; build 890 modules | A6 |
| BE-01 | focused workspace/context/auth/task/registry contracts | Backend pytest | `uv run python -m pytest -q --tb=short` with the focused test list in A5 | FAIL — 196 passed, 1 failed: bundled installed config does not equal repository config | A5 |

### adversarialCases

| scenario id | criterion reference | adversarial class | expected behavior | verdict | artifactRefs |
|---|---|---|---|---|---|
| ADV-CTX-01 | CTX-01 CAS | stale revision | A compact request using revision 8 after authoritative revision 9 must be rejected with conflict metadata | PASS — HTTP 409, `stale_conversation_revision`, `current_revision: 9` | A3, A4 |
| ADV-CTX-02 | ARC-01 project-root authority | root escape / unregistered temp workspace | Requests bound to a project outside configured workspace roots must fail closed | PASS — HTTP 403 `project_root_invalid`; no compaction occurred | A3, A4 |
| ADV-AUTH-01 | SEC-01 | missing credential | Protected workspace API must fail closed | PASS — HTTP 401; lock screen rendered | A1, A4 |
| ADV-PROVIDER-01 | external-provider execution | live provider / non-mock model | Real provider usage must be observed before claiming an LLM pass | NOT_RUN — required live provider credential and provider target were unavailable; no mock is treated as proof | A4 |
| ADV-SOAK-01 | runtime endurance | 8-hour soak / long-running daemon | A bounded final review must not infer endurance from a short run | NOT_RUN — required long-duration execution was not performed in this bounded review | A4 |

## artifactRefs

| id | kind | description | path |
|---|---|---|---|
| A1 | captured browser execution summary (raw transcript unavailable) | Existing live server auth boundary: `/api/workspace/context` returned 401 | [browser-actions.json](logs/browser-actions.json) |
| A2 | captured browser execution summary (raw transcript unavailable) | Playwright workspace seed, switch, context readback, and screenshots | [browser-actions.json](logs/browser-actions.json) |
| A3 | browser screenshot | Fresh 1440×1000 dashboard captures after workspace switch and compact flow | [browser-workspace-switched.png](browser-workspace-switched.png), [browser-after-compact-repo.png](browser-after-compact-repo.png) |
| A4 | browser screenshot + captured execution summary | Initial lock-screen and live dashboard captures; browser events and response evidence | [browser-workspace-initial.png](browser-workspace-initial.png), [browser-actions.json](logs/browser-actions.json) |
| A5 | test log | Focused backend pytest output and model-registry isolation result | [backend-focused.txt](logs/backend-focused.txt) |
| A6 | test/build log | Dashboard typecheck, unit tests, lint, and production build output | [dashboard-gates.txt](logs/dashboard-gates.txt) |

## Limits and follow-up

The package-data/config mismatch in BE-01 is a real failure for this HEAD and was not changed: `tests/test_model_registry.py:66` compares `src/antigravity_k/config.yaml` with the repository-root `config.yaml`, and the package-data copy lacks `agent.default_entry`, `headroom`, `max_repairs`, and `adaptive`. Live provider execution, the full repository suite, and long-duration soak were not run; no PASS is inferred for them. The dashboard lint gate passed with 30 warnings and 0 errors.

## Root verification addendum

Root independently reproduced the config failure at the same SHA. `importlib.resources` resolves `src/antigravity_k/config.yaml` in this repository, not a stale installed site-packages copy. The bundled file lacks the root config’s `agent` defaults. Exact output: [bundled-config-root-recheck.txt](logs/bundled-config-root-recheck.txt). The compact scenario used browser-origin HTTP fetch, not a compact UI button or a full provider-backed request. CLI logs A5/A6 are executor summaries, not complete raw stdout. Browser transcript recovery was not completed; no transcript was synthesized.
