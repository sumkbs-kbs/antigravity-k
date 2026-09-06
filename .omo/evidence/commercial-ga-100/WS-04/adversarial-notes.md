# WS-04 Adversarial notes (implementer)

- Single source: `useProjectStore` owns id/name/path/revision/switchEpoch.
  Sidebar + FolderBrowser call `switchToProject` / `registerAndSwitch` only.
- ChatPage subscribes to `switchEpoch`: abort pending, clear queue/messages,
  `clearForProjectSwitch` + `loadFromStorage`, reload workspace context.
- Stale isolation: capture `switchEpoch` at request start; ignore onChunk and
  skip store merge when `!isIdentityCurrent(epoch)`.
- Identity attach: `createProjectIdentityHeaders` + `withProjectIdentityPayload`
  on chat stream, apiRequest, fileStore, task submit.
- Do not mark DONE / write APPROVE as implementer (owner ≠ reviewer).
- E2E: `e2e/tests/ws-04-project-switch.spec.ts` (route-mocked label↔payload).
  Strong vitest covers label/payload identity without live backend.
