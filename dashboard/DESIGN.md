# Antigravity-K Dashboard Design System

## 1. Atmosphere & Identity

Antigravity-K is a dense, developer-first command center. It should feel calm under load: dark neutral surfaces, restrained violet focus, compact operational typography, and clear status semantics. The signature is traceable execution: every task, agent, step, and tool result reads as one connected run rather than a collection of unrelated cards.

## 2. Color

The implementation source of truth is `src/styles/index.css`. New components use these semantic CSS custom properties rather than raw color values.

| Role | Token | Current value | Usage |
|---|---|---:|---|
| Surface / primary | `--bg-primary` | `#0a0c10` | App shell background |
| Surface / secondary | `--bg-secondary` | `#111318` | Recessed regions |
| Surface / tertiary | `--bg-tertiary` | `#181b22` | Rows and grouped content |
| Surface / elevated | `--bg-elevated` | `#1e222a` | Selected or elevated content |
| Glass / default | `--glass-bg` | `rgba(17, 19, 24, 0.85)` | Operational panels |
| Glass / strong | `--glass-bg-strong` | `rgba(24, 27, 34, 0.92)` | Popovers and emphasized panels |
| Border / default | `--glass-border` | `rgba(255, 255, 255, 0.06)` | Surface separation |
| Border / strong | `--glass-border-strong` | `rgba(255, 255, 255, 0.1)` | Hover and selected states |
| Text / primary | `--text-primary` | `#e4e6eb` | Primary labels and values |
| Text / secondary | `--text-secondary` | `#b0b4c0` | Supporting copy |
| Text / muted | `--text-muted` | `#7a7f8e` | Metadata and placeholders |
| Text / dim | `--text-dim` | `#5a5e6c` | Disabled content |
| Accent / primary | `--accent-color` | `#7c6aef` | Focus, selection, active state |
| Accent / hover | `--accent-hover` | `#6b5ad8` | Interactive hover |
| Accent / light | `--accent-light` | `#9b8ef5` | High-contrast accent text |
| Status / success | `--success-color` | `#10b981` | Completed and healthy |
| Status / warning | `--warning-color` | `#f59e0b` | Paused and attention |
| Status / error | `--error-color` | `#ef4444` | Failed and disconnected |
| Status / info | `--info-color` | `#06b6d4` | Live and informational |

Rules:

- Violet communicates interaction, selection, and the primary running state. It is not decorative.
- Status colors communicate real state only.
- New color roles are added here and to `index.css` before use.
- Both supported themes retain the same semantic hierarchy. The current product default is dark.

## 3. Typography

| Level | Token | Size | Weight | Line height | Usage |
|---|---|---:|---:|---:|---|
| Page title | `--text-5xl` | 36px | 700 | `--leading-tight` | Primary page heading |
| Section title | `--text-3xl` | 22px | 600 | `--leading-tight` | Major panel heading |
| Panel title | `--text-xl` | 16px | 600 | `--leading-normal` | Panel and group heading |
| Body | `--text-md` | 14px | 400 | `--leading-normal` | Readable prose and controls |
| Compact body | `--text-base` | 13px | 400 | `--leading-normal` | Dense operational rows |
| Metadata | `--text-sm` | 12px | 500 | `--leading-normal` | Timestamps and secondary labels |
| Micro label | `--text-xs` | 11px | 600 | `--leading-tight` | Short status labels only |

Font stacks:

- Primary: `--font-sans`, currently Inter with system fallbacks.
- Monospace: `--font-mono`, currently JetBrains Mono with code-oriented fallbacks.
- Operational output, IDs, sequence numbers, and durations use the monospace stack.
- User-facing body copy does not go below 14px. Compact 11-13px text is reserved for metadata and dense monitoring data.

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
- Task execution uses an intrinsic grid that reflows to one readable column without horizontal page scroll.
- Agent tree and checklist are content regions. Terminal output is the only nested scroll owner in a terminal card.
- Grid tracks use overflow-safe intrinsic sizing. Long IDs and output use `overflow-wrap: anywhere`.
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
