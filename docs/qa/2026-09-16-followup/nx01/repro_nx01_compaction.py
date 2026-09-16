"""NX-01 repro/verification driver: does an early user constraint survive repeated compaction?

Usage (repo root, isolated temp store — never the real vault):

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src AGK_CONVERSATION_SOFT_MAX_MESSAGES=64 \
        .venv/bin/python docs/qa/2026-09-16-followup/nx01/repro_nx01_compaction.py --label before

Prints one JSON object per observed boundary (64/65/122/123 appends) plus a
structured-memory dump, so the same driver can be run against the pre-NX-01 code
(via a temp checkout of the old modules) and against the fixed tree.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from antigravity_k.engine.conversation_store import ConversationStore  # noqa: E402

EARLY = "EARLY_REQUIREMENT_KEEP_OFFLINE: 네트워크 사용 금지, 승인 없이 실행하지 마."


def _probe(store: ConversationStore, appends: int) -> dict[str, object]:
    record = store.get(project_id="p", conversation_id="c")
    assert record is not None
    prompt_text = "\n".join(m["content"] for m in record.prompt_messages())
    # Pre-NX-01 records have no structured memory at all (that is the defect).
    memory = getattr(record, "memory", None)
    return {
        "appends": appends,
        "revision": record.revision,
        "messages": len(record.messages),
        "roles": [m.role for m in record.messages],
        "early_requirement_in_prompt": "EARLY_REQUIREMENT_KEEP_OFFLINE" in prompt_text,
        "active_constraints": len(memory.active_constraints()) if memory is not None else None,
        "superseded_constraints": len(memory.superseded_constraints()) if memory is not None else None,
        "generation": memory.generation if memory is not None else None,
        "constraint_ids": [c.id for c in memory.constraints] if memory is not None else None,
        "summary_chars": len(record.summary or ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run")
    parser.add_argument("--soft-max", type=int, default=64)
    args = parser.parse_args()

    if args.soft_max == 0:
        os.environ["AGK_CONVERSATION_SOFT_MAX_MESSAGES"] = "0"
    else:
        os.environ["AGK_CONVERSATION_SOFT_MAX_MESSAGES"] = str(args.soft_max)

    tmp = tempfile.TemporaryDirectory(prefix="nx01-repro-")
    try:
        store = ConversationStore(storage_dir=Path(tmp.name) / "conversations")
        observed: list[dict[str, object]] = []
        rev = 0
        snap = store.append(
            project_id="p",
            conversation_id="c",
            expected_revision=rev,
            role="user",
            content=EARLY,
        )
        rev = snap.revision
        observed.append(_probe(store, rev))
        boundaries = {64, 65, 122, 123}
        for i in range(1, 123):  # total appends = 1 + 122 = 123
            snap = store.append(
                project_id="p",
                conversation_id="c",
                expected_revision=rev,
                role="user",
                content=f"turn-{i} 작업 진행",
            )
            rev = snap.revision
            if rev in boundaries:
                observed.append(_probe(store, rev))
        # reload from disk (schema round-trip, no in-memory cache)
        reloaded = ConversationStore(storage_dir=Path(tmp.name) / "conversations")
        record = reloaded.get(project_id="p", conversation_id="c")
        assert record is not None
        reload_prompt = "\n".join(m["content"] for m in record.prompt_messages())
        out = {
            "label": args.label,
            "soft_max": args.soft_max,
            "observed": observed,
            "after_reload": {
                "revision": record.revision,
                "messages": len(record.messages),
                "early_requirement_in_prompt": "EARLY_REQUIREMENT_KEEP_OFFLINE" in reload_prompt,
                "active_constraints": (
                    len(record.memory.active_constraints()) if getattr(record, "memory", None) is not None else None
                ),
            },
            "summary_head": (record.summary or "")[:600],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    finally:
        tmp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
