# CTX-01 adversarial notes (owner self-check; not APPROVE)

1. Race: two threads append at same expected_revision → exactly one StaleConversationRevisionError; winner content preserved.
2. Compact with stale expected_revision → 409; history unchanged.
3. Client full message array is not SoT when protocol on — assemble_history uses store + new_turn only.
4. conv_unspecified legacy path skips store assert to avoid false 409 (gated in project_binding).
5. Residual: assistant persist after stream uses CAS; if another tab compact races mid-stream, assistant append may fail soft (logged) — reviewer should probe.
