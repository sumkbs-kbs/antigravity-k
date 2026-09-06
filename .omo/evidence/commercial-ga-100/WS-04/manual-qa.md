# WS-04 Manual QA (owner)

## Desktop
1. Open ChatPage with project Beta active — crumb `data-testid=active-project-label` shows Beta.
2. Start a long chat stream; mid-stream switch to Gamma in Sidebar.
3. Expect: toast about cancel; Beta assistant chunks do not appear under Gamma;
   label shows Gamma; next send body includes `project_id=proj_gamma` (+ revision).
4. File tree refresh targets Gamma workspace path.

## Mobile (narrow viewport)
1. Same switch B→C; label and subsequent chat payload project_id match.

## Automated
- vitest projectStore + projectIdentity: label/store id == payload project_id.
- Playwright spec present: `dashboard/e2e/tests/ws-04-project-switch.spec.ts`.
