---
id: 180
category: note
tags: []
created: 2026-05-04T09:42:52.594303
---

# env.d.ts

```typescript
declare const MACRO: {
  VERSION: string
  BUILD_TIME: string
  PACKAGE_URL?: string
  NATIVE_PACKAGE_URL?: string
  FEEDBACK_CHANNEL?: string
  ISSUES_EXPLAINER?: string
  VERSION_CHANGELOG?: string
}

declare module '*.node' {
  const value: unknown
  export default value
}
```
