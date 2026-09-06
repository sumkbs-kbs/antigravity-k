# DAT-01 adversarial notes (owner probe)

1. Stale expected_version → conflict; status remains running; output untouched.
2. Terminal freeze: done→done with new output raises InvalidTaskTransitionError.
3. Two threads / two processes cancel vs done → one win one lose; winner fields sticky.
4. Four-process stress (done/cancelled/failed/done) → single terminal; no mixed reason/output.
5. Contradictory late `direct_completed` event after cancelled store → display stays cancelled.
6. UI: projectTaskExecution(..., 'cancelled') clamps agent/checklist away from completed.
