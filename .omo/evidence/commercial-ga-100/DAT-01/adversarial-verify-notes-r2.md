# DAT-01 adversarial verify r2 (dat_01_verify)

Date: 2026-09-06 (Asia/Seoul)
Reviewer: `dat_01_verify`
Tip: `4368d8ead622f8d86a9551c0df3f7e03cfb7da31`
Fix: `5aed1a649ac572fb5789cce8da895576855f7aca`

## Probes
1. Store race 60× cancel vs done (expected status+version): exactly one winner; overwrite_failures=0 (done=45, cancelled=15).
2. F2 TOCTOU stream 20×: cancel wins immediately before done transition → no `*_completed` domain events; display projection cancelled.
3. Vitest F1 view wiring: cancelled store + late `direct_completed` → UI `취소됨`, no `완료`.

## Result
PASS — see `adversarial-verify-r2.txt`.
