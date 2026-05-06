---
id: 192
category: note
tags: []
created: 2026-05-04T09:42:52.626783
---

# TODO.md

```markdown
# TODO

Implement the following packages as much as possible so that the relationship with the main package is completely consistent

## Packages

- [x] `url-handler-napi` — URL handling NAPI module (signature fix, keep null fallback)
- [x] `modifiers-napi` — Modifier key detection NAPI module (Bun FFI + Carbon)
- [x] `audio-capture-napi` — Audio capture NAPI module (SoX/arecord)
- [x] `color-diff-napi` — Color difference calculation NAPI module (pure TS implementation)
- [x] `image-processor-napi` — image processing NAPI module (sharp + osascript clipboard)

- [x] `@ant/computer-use-swift` — Computer Use Swift native module (macOS JXA/screencapture implementation)
- [x] `@ant/computer-use-mcp` — Computer Use MCP service (type-safe stub + sentinel apps + targetImageSize)
- [x] `@ant/computer-use-input` — Computer Use input module (macOS AppleScript/JXA implementation)
<!-- - [ ] `@ant/claude-for-chrome-mcp` — Chrome MCP extension -->

## Engineering capabilities

- [x] Code formatting and verification
- [x] Redundant code checking
- [x] git hook configuration
- [x] Code health check
- [x] Biome lint rule tuning (adapt decompiled code, turn off formatting to avoid large-scale diff)
- [x] Unit test infrastructure construction (test runner configuration)
- [x] CI/CD Pipeline (GitHub Actions)
```
