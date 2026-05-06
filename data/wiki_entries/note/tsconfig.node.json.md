---
id: 137
category: note
tags: []
created: 2026-05-04T09:42:52.418547
---

# tsconfig.node.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "lib": ["ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "baseUrl": ".",
    "paths": {
      "@main/*": ["./src/main/*"],
      "@preload/*": ["./src/preload/*"],
      "@shared/*": ["./src/shared/*"]
    },
    "types": ["node"]
  },
  "include": ["electron.vite.config.ts", "src/main/**/*", "src/preload/**/*"]
}
```
