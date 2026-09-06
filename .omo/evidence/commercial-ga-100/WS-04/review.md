# WS-04 Independent Review — REJECT

| Field | Value |
|---|---|
| Reviewer | `ws_04_verify` |
| Owner | `ws_04_frontend` |
| Verdict | **REJECT** |
| Tip reviewed | `7bac16dddec026c7b5329715c0424637fa512cac` (HEAD confirmed) |
| Impl / Result SHA | `1ca4ae6d37e98dd4f9a1eb884e69fa83ed64a920` |
| dashboard_dist tip (incl.) | `88ad512da3f7efc6bc71c8c460293df7c7ff8db1` |
| Branch / worktree | `codex/ws-04-dashboard-project` / `Ssak-Ai-ws-04` |
| Reviewed at | 2026-09-06T11:03+09:00 |
| Confidence | 0.94 |

**DONE 금지.** CTX-01 선행은 ARC-01(DONE)뿐이라 *이론상* 착수 가능하나, 본 review는 CTX를 시작하지 않음. WS-04 re-submit + re-review 전 DONE/APPROVE 금지.

## Scope checked

Must-verify from commercial GA WS-04:

1. Single project store SoT
2. ChatPage reloads context on project change
3. chat/task/file requests carry project identity
4. Pending prior-project requests cancelled/isolated on switch
5. Stale responses don't merge into new project store/UI
6. Tests prove label/payload consistency (vitest; e2e if runnable)
7. Re-run targeted vitest (reviewer)

## What passes (keep)

- `useProjectStore` owns id/name/path/revision/`switchEpoch`; Sidebar/`FolderBrowser` call `switchToProject` / `registerAndSwitch` (not ad-hoc localStorage writes as primary switch path).
- ChatPage subscribes to `switchEpoch`: aborts `AbortController`, clears queue/streaming/activity, `clearForProjectSwitch` + `loadFromStorage`, `reloadWorkspaceContext` with epoch gate.
- Chat stream path: `streamChatCompletion` attaches headers+body via `createProjectIdentityHeaders` / `withProjectIdentityPayload`; `onChunk` and post-await merge gated by `isIdentityCurrent(requestEpoch)`.
- `apiRequest` / `fileStore` list+mutate / `taskExecutionApi` attach project identity headers (and body/query where applicable).
- Vitest identity/label consistency: reviewer re-run **59 passed** / 5 files (`tests-verify-rerun.txt`). Desktop Playwright spec asserts label↔`project_id` after B→C (route-mocked).

## Blocking findings

### F1 — fileStore does not cancel/isolate; stale list merges into new UI (must-verify #4, #5) — BLOCKER

`dashboard/src/stores/fileStore.ts` has **zero** `switchEpoch` / `isIdentityCurrent` / `AbortController`.

```ts
refreshTree: async () => {
  ...
  const items = await loadDirectory('.');
  set({ treeData: items, workspacePath, isLoading: false }); // unguarded after await
},
getWorkspace: async () => {
  ...
  set({ workspacePath: wp }); // unguarded
},
```

**Adversarial race:** start refresh on project B → switch to C (Sidebar `refreshTree()` again) → B response resolves later → `treeData` shows B files under C label. Violates plan: “파일 … loading result가 새 project 화면에 합쳐지지 않는다” / “stale response는 store에 반영되지 않는다”.

Evidence: `adversarial-verify.txt` F1.

### F2 — Prior project file selection + change panel survive switch (must-verify #5) — BLOCKER

ChatPage WS-04 switch effect clears chat/activity only. It does **not**:

- close/clear `useEditorStore.openFiles` / preview
- `useChangeStore.clearChanges()`
- reset `useFileStore.treeData` / `expandedPaths` before refresh

Plan completion criterion explicitly includes **파일 선택**. Open tabs and pending diffs from B remain visible after label shows C. No `closeAll` API even exists on editor store — owner must add clear-for-switch.

Evidence: `adversarial-verify.txt` F2; ChatPage switch effect ~L331–373.

### F3 — File read/write surfaces skip project identity (must-verify #3) — BLOCKER

Checklist claim “chat/task/file request에 project identity가 있다” is **false** on editor save and ChatPage FS reads:

- `editorStore.saveFile`: `createAccessPinHeaders` only; body `{ path, content }` — no `X-AGK-Project-Id` / revision / `project_id` payload / session header via identity helpers.
- `ChatPage` `onFileOpened` / `onFileModified`: `fetch(\`/api/fs/read?file=...\`)` with **no** `createProjectIdentityHeaders` and **no** epoch gate → stale WS events can open prior-project file content into the new project UI.

`fileStore` paths that *do* attach identity do not cover these call sites.

### F4 — Mobile E2E does not hard-prove label↔payload (must-verify #6) — BLOCKER for plan E2E criterion

`dashboard/e2e/tests/ws-04-project-switch.spec.ts` mobile test:

```ts
if (chatPayload?.project_id) {
  expect(chatPayload.project_id).toBe('proj_mobile');
  ...
}
```

Missing `project_id` still **passes**. `__WS04` evaluate is a no-op. Plan requires desktop/**mobile** browser E2E that jointly verifies screen label and request payload. Desktop test is OK; mobile is not evidence.

E2E not executed in this review environment (no local playwright run required once spec defect is clear); vitest re-run completed.

## Must-verify scorecard

| # | Criterion | Result |
|---|---|---|
| 1 | Single project store SoT | **PASS** (minor residual: EnvironmentPanel localStorage path fallback) |
| 2 | ChatPage reloads context on change | **PASS** |
| 3 | chat/task/file requests carry project identity | **FAIL** — chat/task/fileStore OK; editor save + ChatPage `/api/fs/read` miss |
| 4 | Pending prior requests cancelled/isolated | **PARTIAL** — chat abort OK; fileStore in-flight not cancelled/gated |
| 5 | Stale responses don't merge into new store/UI | **FAIL** — file tree race; editor tabs + changes persist across switch |
| 6 | Tests prove label/payload (vitest; e2e) | **PARTIAL** — vitest strong; mobile e2e soft-pass |
| 7 | Reviewer re-run targeted vitest | **PASS** — 59/59 |

## Precise fixes required (owner)

1. **fileStore epoch isolation**
   - Capture `switchEpoch` (or project id) at start of `loadDirectory` / `refreshTree` / `getWorkspace`.
   - After `await`, apply `set(...)` only if `isIdentityCurrent(capturedEpoch)`.
   - Prefer AbortController per in-flight list/workspace fetch; abort on `agk:project-switched` or from Sidebar/ChatPage switch path before refresh.
   - Vitest: start slow B list → applyActiveProject(C) → resolve B → assert `treeData` is not B.

2. **Clear file selection + changes (+ tree) on switch**
   - On project switch (ChatPage effect and/or `agk:project-switched` listener): clear editor openFiles/active/preview; `clearChanges()`; reset `treeData`/`expandedPaths` then refresh for new project.
   - Add `clearForProjectSwitch` (or equivalent) on editor store; test B tabs gone after switch to C.

3. **Identity on all file surfaces**
   - `editorStore.saveFile` must use `createProjectIdentityHeaders` + `withProjectIdentityPayload`.
   - ChatPage `/api/fs/read` (and any other raw `fetch` to `/api/fs/*`) must use identity headers/query **and** ignore results when `!isIdentityCurrent(epoch)`.
   - Extend vitest/client tests to cover saveFile / fs read identity.

4. **Harden mobile E2E**
   - Remove soft `if (chatPayload?.project_id)` — always assert label text/id equals payload `project_id` (+ revision when set).
   - Prefer real hydrate/switch path (same as desktop) instead of no-op `__WS04` / localStorage-only seed.
   - Keep desktop B→C test.

5. **Evidence / checklist**
   - Uncheck failed WS-04 checklist lines until re-review.
   - Re-submit with new Result SHA; do not self-APPROVE.

## Non-blocking notes

- EnvironmentPanel `localStorage.getItem('agk_active_project')` fallback after store is acceptable residual if store remains authoritative for switch.
- `hydrateFromServer` not bumping epoch is OK for first paint; if hydrate can *change* active id vs pre-hydrate storage key, consider a one-shot reload of chat storage after hydrate when id changes (follow-up; not scored as primary blocker vs F1–F4).
- Task-execution SSE abort-on-unmount exists; project-switch abort for task panels is desirable follow-up if task UI stays mounted across switches.

## Verdict

**REJECT.** Chat SoT + stream abort/epoch gating are real progress, but file tree/editor/change isolation and file identity holes violate WS-04 completion criteria. Re-submit after fixes; `ws_04_verify` will re-run vitest + adversarial probes.
