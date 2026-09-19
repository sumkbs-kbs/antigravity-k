# CTX-03 F1 fix adversarial notes (owner)

- Reproduced F1: `'succeeded'.includes('success') === false` → prior `statusFor` returned `unknown`.
- After fix: exact event-type map + `includes('succeed')` → `context.compress.succeeded` → `completed`.
- Degrade/halt unchanged (`degraded` / `failed`).
- Vitest + Node probe green. No APPROVE claimed.
