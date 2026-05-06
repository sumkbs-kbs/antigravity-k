---
id: 233
category: note
tags: []
created: 2026-05-04T09:42:52.780434
---

# tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "esModuleInterop": true,
    "strict": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "declaration": false,
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": false,
    "lib": ["ESNext"],
    "types": ["node"],
    "baseUrl": ".",
    "paths": {
      "bun:bundle": ["./src/types/bun-bundle.d.ts"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.tsx"],
  "exclude": ["node_modules", "dist"]
}

```
