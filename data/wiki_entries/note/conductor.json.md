---
id: 204
category: note
tags: []
created: 2026-05-04T09:42:52.698376
---

# conductor.json

```json
{
    "scripts": {
        "run": "cd $CONDUCTOR_ROOT_PATH && git checkout $(git rev-parse --abbrev-ref HEAD) -- . && npm run build; git reset --hard HEAD"
    }
}
```
