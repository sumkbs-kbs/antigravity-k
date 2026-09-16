#!/usr/bin/env python
"""NX-02 before/after driver: does the conversation store keep the originals?

Run against two trees:

    PYTHONPATH=/tmp/nx01-before/src .venv/bin/python \
        docs/qa/2026-09-16-followup/nx02/repro_nx02_view_only.py > before.json
    PYTHONPATH=src .venv/bin/python \
        docs/qa/2026-09-16-followup/nx02/repro_nx02_view_only.py > after.json

The driver only uses the public store surface plus the storage files it writes,
so it runs unchanged on the pre-NX-02 (view-only) tree and on the journal tree.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

PROJECT = "p"
CONV = "conv"
TURNS = 40


def main() -> int:
    # 이 드라이버는 PYTHONPATH 로 어느 트리를 검사할지 결정한다(여기서 src 를
    # 주입하면 before 트리를 검사할 수 없다).
    import antigravity_k.engine.conversation_store as store_module
    from antigravity_k.engine.conversation_store import ConversationStore, conversation_storage_relative_path

    tree_module = Path(store_module.__file__).resolve()

    storage = Path(tempfile.mkdtemp(prefix="nx02-driver-")) / "conversations"
    store = ConversationStore(storage_dir=storage)

    appends = []
    for i in range(TURNS):
        store.append(
            project_id=PROJECT,
            conversation_id=CONV,
            expected_revision=i,
            role="user" if i % 2 == 0 else "assistant",
            content=f"turn-{i}",
        )
        appends.append(f"turn-{i}")

    compacted = store.compact(project_id=PROJECT, conversation_id=CONV, expected_revision=TURNS, retain_tail=4)

    # What the client can read back (the prompt view on the pre-NX-02 tree).
    record = store.get(project_id=PROJECT, conversation_id=CONV)
    view = [m.content for m in record.messages] if record is not None else []

    originals_api = hasattr(store, "original_history")
    originals = store.original_history(project_id=PROJECT, conversation_id=CONV) if originals_api else []
    originals_content = [str(m.get("content")) for m in originals]

    files = sorted(str(p.relative_to(storage)) for p in storage.rglob("*") if p.is_file())
    journals = [f for f in files if f.endswith(".jsonl")]
    view_path = storage / conversation_storage_relative_path(PROJECT, CONV)

    report = {
        "tree": os.environ.get("NX02_TREE", "unknown"),
        "store_module": str(tree_module),
        "turns_written": TURNS,
        "compacted": True,
        "view_message_count": len(view),
        "view_has_turn_0": "turn-0" in view,
        "view_is_bounded": len(view) <= 64,
        "originals_api_present": originals_api,
        "originals_message_count": len(originals_content),
        "originals_cover_every_turn": originals_content == appends,
        "original_history_recoverable": originals_content == appends,
        "journal_files": journals,
        "storage_files": files,
        "view_path": str(view_path.relative_to(storage)) if view_path.is_file() else None,
        "compact_summary_present": bool(compacted.summary),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["original_history_recoverable"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
