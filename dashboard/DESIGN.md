# Ssak-Ai Dashboard Design System

## 1. Atmosphere & Identity

Inspired by **TERMINAL-7 — Cold-blooded engineering for warm-blooded users**.
Ssak-Ai is a dense, developer-first command center with a distinctive aesthetic: **Brutalist Terminal Precision meets Warm Editorial Serif Elegance**. Deep obsidian charcoal surfaces, restrained warm amber gold focus, terminal radar green status telemetrics, and high-contrast editorial typography. The signature is traceable execution and telemetric observability: every task, agent, step, and tool result reads as one connected, precision-engineered run.

## 2. Color

The implementation source of truth is `src/styles/index.css`. New components use these semantic CSS custom properties rather than raw color values.

| Role | Token | Current value | Usage |
|---|---|---:|---|
| Surface / primary | `--bg-primary` | `#080908` | Deep obsidian app shell background |
| Surface / secondary | `--bg-secondary` | `#0d0f0d` | Recessed regions & sidebar |
| Surface / tertiary | `--bg-tertiary` | `#131613` | Rows, cards, and grouped content |
| Surface / elevated | `--bg-elevated` | `#1a1e1a` | Selected or elevated content |
| Glass / default | `--glass-bg` | `rgba(13, 16, 13, 0.88)` | Operational panels |
| Glass / strong | `--glass-bg-strong` | `rgba(19, 23, 19, 0.94)` | Popovers and emphasized panels |
| Border / default | `--glass-border` | `rgba(255, 255, 255, 0.08)` | Surface separation |
| Border / strong | `--glass-border-strong` | `rgba(229, 169, 59, 0.25)` | Hover and selected states |
| Border / terminal | `--terminal-border` | `#1e241e` | Terminal hairline borders |
| Text / primary | `--text-primary` | `#eef0eb` | Primary bone-white labels and values |
| Text / secondary | `--text-secondary` | `#a6aca1` | Supporting sage-tinted copy |
| Text / muted | `--text-muted` | `#666e63` | Terminal comments (`//`) & metadata |
| Text / dim | `--text-dim` | `#41483e` | Disabled content |
| Accent / primary | `--accent-color` | `#e5a93b` | Warm amber focus, italic accents, CTA |
| Accent / hover | `--accent-hover` | `#f59e0b` | Interactive hover |
| Accent / light | `--accent-light` | `#fde68a` | High-contrast accent text |
| Telemetrics / radar | `--terminal-green` | `#00ff66` | Radar indicators, NOMINAL tags, prompts |
| Status / success | `--success-color` | `#10b981` | Completed and healthy |
| Status / warning | `--warning-color` | `#e5a93b` | Paused and attention |
| Status / error | `--error-color` | `#ef4444` | Failed and disconnected |
| Status / info | `--info-color` | `#38bdf8` | Live and informational (code cyan) |

Rules:

- Warm Amber (`#e5a93b`) communicates primary user intention, interactive focus, and editorial italic highlights.
- Terminal Radar Green (`#00ff66` / `#10b981`) communicates machine health, boot nominal status, and terminal prompt prefixes (`$`).
- All technical metadata prefixes use the comment syntax (`// 01 · CHAT`, `// PROJECTS`).
- Status colors communicate real state only.

## 3. Typography

| Level | Token | Size | Weight | Line height | Usage |
|---|---|---:|---:|---:|---|
| Page title | `--text-5xl` | 38px | 400 | `1.15` | Editorial Serif primary page heading |
| Section title | `--text-3xl` | 24px | 400 | `1.2` | Editorial Serif major panel heading |
| Panel title | `--text-xl` | 16px | 600 | `--leading-normal` | Panel and group heading |
| Body | `--text-md` | 14px | 400 | `--leading-normal` | Readable prose and controls |
| Compact body | `--text-base` | 13px | 400 | `--leading-normal` | Dense operational rows |
| Metadata | `--text-sm` | 12px | 500 | `--leading-normal` | Timestamps and secondary labels |
| Micro label | `--text-xs` | 11px | 600 | `--leading-tight` | Terminal status labels & telemetrics |

Font stacks:

- Display / Editorial: `--font-serif`, Newsreader and Instrument Serif with Georgia fallbacks. Key words use *Italic Amber* (`.editorial-accent`).
- Primary UI: `--font-sans`, Inter with system fallbacks.
- Monospace: `--font-mono`, JetBrains Mono with code/terminal fallbacks.
- Operational output, IDs, sequence numbers, durations, telemetric bars, and buttons use the monospace stack.

## 4. Spacing & Layout

The base unit is 4px. Intent uses `--space-1` through `--space-20` from `index.css`.

| Token | Value | Usage |
|---|---:|---|
| `--space-1` | 4px | Icon-to-label, compact row gap |
| `--space-2` | 8px | Inline clusters and row padding |
| `--space-3` | 12px | Dense panel gap |
| `--space-4` | 16px | Standard panel padding |
| `--space-5` | 20px | Comfortable separation |
| `--space-6` | 24px | Section padding |
| `--space-8` | 32px | Major panel separation |
| `--space-10` | 40px | Page-level gap |
| `--space-12` | 48px | Large region separation |
| `--space-16` | 64px | Shell-level spacing |

Layout rules:

- The page shell owns vertical scrolling. Internal scroll regions are named and bounded.
- Wide operational pages use `--content-wide` as their maximum inline size.
- Task execution uses an intrinsic grid that reflows to one readable column without horizontal page scroll.
- Agent tree and checklist are content regions. Terminal output is the only nested scroll owner in a terminal card.
- Grid tracks use overflow-safe intrinsic sizing. Long IDs and output use `overflow-wrap: anywhere`.
- Korean prose wraps at spaces and keeps Korean words/endings intact (`word-break: keep-all`). Unbroken code, path, and identifier text retains `overflow-wrap: anywhere` and may break as needed.
- Viewport breakpoints remain `640px`, `768px`, `1024px`, `1280px`, and `1536px`. Components prefer intrinsic and container-local adaptation.

## 5. Components

### Glass Panel

- **Structure**: semantic section or article with `.glass-panel`.
- **Variants**: default, elevated.
- **Spacing**: caller chooses `--space-3`, `--space-4`, or `--space-6` by density.
- **States**: default, hover, `focus-within`.
- **Accessibility**: does not replace semantic heading or landmark structure.
- **Motion**: border, shadow, transform using declared transition tokens.
- **Layout**: content wrapper; never owns scroll by default.

### Execution Run Selector

- **Structure**: labelled native `select`, live connection label, last-sequence metadata.
- **Variants**: loading, connected, reconnecting, complete, error, empty.
- **Spacing**: cluster with `--space-2` and `--space-3`.
- **States**: hover, focus-visible, disabled, loading, empty, error.
- **Accessibility**: persistent label, native keyboard support, live status announced politely.
- **Motion**: none beyond existing micro-transition tokens.
- **Layout**: wrapping cluster; page shell remains scroll owner.

### Agent Tree

- **Structure**: nested semantic list with agent label, relationship, status, and latest sequence.
- **Variants**: root-only, parallel children, metadata unavailable, empty.
- **Spacing**: dense stack using `--space-1` and `--space-2`.
- **States**: active, completed, failed, paused, unknown.
- **Accessibility**: nested lists preserve hierarchy; status is text, not color alone.
- **Motion**: none. Streaming updates preserve stable row identity.
- **Layout**: stack; no internal scrolling.

### Execution Checklist

- **Structure**: ordered list of step or task milestones with text status and optional tool metadata.
- **Variants**: planned, running, completed, failed, cancelled, blocked, unknown.
- **Spacing**: dense stack using `--space-2`.
- **States**: default, live update, empty.
- **Accessibility**: status has a visible label; sequence order matches DOM order.
- **Motion**: none.
- **Layout**: stack; no internal scrolling.

### Terminal Event Card

- **Structure**: article header, command/tool metadata, bounded preformatted output, sequence footer.
- **Variants**: running, completed, failed, approval-required, output-truncated.
- **Spacing**: `--space-3` header and footer, `--space-4` output.
- **States**: default, focus-within, empty output, truncated output.
- **Accessibility**: output is selectable text, status is not color-only, long content wraps without moving primary layout.
- **Motion**: none.
- **Layout**: stack. Output preview owns vertical scrolling and is height-bounded.

### Execution Block Stack

- **Structure**: an ordered list of typed projection blocks; each block delegates to one documented execution primitive.
- **Variants**: agent tree, checklist, terminal evidence.
- **Spacing**: intrinsic two-column grid for agent/checklist blocks followed by a full-width terminal block.
- **States**: each delegated primitive owns loading, empty, running, waiting, completed, failed, and cancelled states.
- **Accessibility**: block order matches event comprehension order; every block retains its semantic heading and landmark.
- **Motion**: none. Event projection updates preserve stable block and row identity.
- **Layout**: the stack never owns page scrolling; terminal output remains the only bounded nested scroll region.

### Command Palette Item

- **Structure**: native button with a semantic SVG icon, title, optional category, and selected state.
- **Variants**: built-in action, note search result, plugin action, unavailable/error row.
- **Spacing**: `--space-3` vertical padding, `--space-4` horizontal padding, `--space-2` internal gap.
- **States**: default, hover, keyboard-selected, focus-visible, disabled.
- **Accessibility**: listbox owns `aria-activedescendant`; each option has a stable ID and is operable with Enter or click.
- **Motion**: background and icon-color feedback use `--transition-fast`; no layout property animates.
- **Layout**: title truncates without hiding the category; the result list is the bounded scroll owner.

### Task Queue Panel

- **Structure**: labelled submit form followed by server-owned task rows and lifecycle controls.
- **Variants**: empty, pending, running, resuming, completed, failed, paused, cancelled.
- **Spacing**: compact operational stack using `--space-2` and `--space-3`.
- **States**: selected task, submitting, cancelling, resuming, disabled invalid action.
- **Accessibility**: prompt has a persistent label; each cancel/resume control includes the task title in its accessible name.
- **Motion**: color feedback only; streamed state changes do not move focus.
- **Layout**: task rows are the named bounded scroll region; task status remains a server projection.

### Session History / Fork

- **Structure**: the canonical task-history rows inside Task Queue, with source status, selection, lifecycle controls, and an explicit fork action.
- **Variants**: active source, terminal source, paused/failed source, fork request pending, fork failure.
- **Spacing**: history heading uses `--space-3`; row actions retain the compact `--space-2` cluster.
- **States**: selected source, fork pending, fork created and selected, source preserved.
- **Accessibility**: the fork control includes the source task title in its accessible name; creating a fork does not move or remove the source row.
- **Motion**: none. The new session appears through the normal server-list refresh without an optimistic clone.
- **Layout**: history reuses the Task Queue bounded list; no second scroll owner or session store is introduced.

### Approval Queue

- **Structure**: pending request list, selected request metadata, existing DiffViewer preview, and explicit deny/always-allow/approve controls.
- **Variants**: empty, pending request, no-diff request, resolving, request error.
- **Spacing**: compact list beside a flexible detail region using `--space-3`.
- **States**: selected, resolving, rejected, approved, always allowed.
- **Accessibility**: risk and tool name are visible text; each decision control includes the request description in its accessible name.
- **Motion**: none. Resolution removes only the server-confirmed request.
- **Layout**: queue and detail collapse to one column below tablet width; DiffViewer owns its bounded editor viewport.

### Job Operations Console

- **Structure**: health summary, policy alert, schedule list, and selected execution history.
- **Variants**: loading, empty, healthy, needs-attention, API error, retry pending.
- **Spacing**: metric grid uses `--space-3`; panels use `--space-4`; run rows use `--space-2`.
- **States**: selected schedule, failed run, retrying run, refresh pending.
- **Accessibility**: policy failures use an alert landmark and visible text; schedule selection uses native buttons; retry controls name the run ID.
- **Motion**: none; refresh and retry state changes do not animate layout or steal focus.
- **Layout**: `job-operations-layout` is a responsive two-column `list-detail` primitive that collapses to one column below `768px`; the page shell remains the only vertical scroll owner.

### Persistent Agency Console

- **Structure**: labelled objective form, scheduler state summary, durable context preview, and objective lifecycle list.
- **Variants**: loading, unavailable, idle, objective-ready, paused, and API error.
- **Spacing**: panel uses `--space-4`; form controls and objective rows use `--space-2` and `--space-3`.
- **States**: submitting, refreshing, paused, resumed, validation error, and completed objective.
- **Accessibility**: objective title has a persistent label; pause/resume is a named button; scheduler state is exposed through `role="status"` text and not color alone.
- **Motion**: no layout animation; state feedback uses existing control transitions and reduced-motion behavior.
- **Layout**: intrinsic single-column stack inside the agent page; context preview and long objective text wrap without horizontal overflow.

### Mutation Snapshot Console

- **Structure**: provenance summary, aggregate metrics, filter controls, and per-target historical result cards.
- **Variants**: historical snapshot, stale snapshot, invalid snapshot, and empty filter result.
- **Spacing**: summary and cards use `--space-5`; compact metric clusters use `--space-2` and `--space-4`.
- **States**: snapshot metadata, threshold comparison, stale warning, parse error, and no-match empty state.
- **Accessibility**: provenance and freshness are visible text with `role="status"`; threshold state is text plus color and cards remain keyboard operable.
- **Motion**: only the existing card border/hover transition; no motion implies live data.
- **Layout**: single-column stack with wrapping metric clusters; the page shell remains the scroll owner.

## 6. Motion & Interaction

| Type | Token | Usage |
|---|---|---|
| Micro | `--transition-fast` | Hover, active, focus feedback |
| Standard | `--transition-normal` | Surface and control state change |
| Slow | `--transition-slow` | Reserved for deliberate panel transitions |

- Streaming data updates do not animate layout or steal focus.
- Interactive controls include hover, active, focus-visible, disabled, loading, empty, and error states where applicable.
- Only transform and opacity may animate. Reduced-motion preference disables nonessential effects.

## 7. Depth & Surface

Strategy: mixed tonal shift plus restrained glass borders.

- Primary depth comes from `--bg-primary` through `--bg-elevated`.
- `.glass-panel` supplies a subtle border and blur for operational grouping.
- Shadows are reserved for overlays, selected elevated content, and hover feedback. Dense nested rows use tonal shifts instead of a card inside every card.
- Border radii follow the existing three-level system: `--border-radius`, `--border-radius-lg`, and `--border-radius-xl`. Pill radius is limited to badges and compact controls.

## 8. Accessibility Constraints & Accepted Debt

Constraints:

- Target WCAG 2.2 AA.
- Body text contrast is at least 4.5:1; large text and graphical controls are at least 3:1.
- Every interactive element is keyboard reachable and has a visible focus indicator.
- Status is communicated with text plus color.
- Live connection changes use polite announcements and do not interrupt current reading.
- Primary content has no horizontal page scroll at 375px.
- Korean and English labels remain legible without clipping or forced letter spacing.

Accepted debt:

| Item | Location | Why accepted | Owner / Exit |
|---|---|---|---|
| None | - | New debt requires explicit user approval | - |

Known pre-existing inconsistencies, not accepted as debt: the legacy stylesheet contains raw colors, emoji icons, undersized operational text, and repeated one-off spacing. New task-execution components do not extend those patterns; consolidation remains a separate refactor.
