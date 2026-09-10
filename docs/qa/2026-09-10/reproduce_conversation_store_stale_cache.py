from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from antigravity_k.engine.conversation_store import ConversationStore


def main() -> None:
    with TemporaryDirectory(prefix="ssak-conversation-cache-") as temporary_root:
        storage_dir = Path(temporary_root) / "conversations"
        writer = ConversationStore(storage_dir)
        cached_reader = ConversationStore(storage_dir)

        writer.append(
            project_id="project",
            conversation_id="conversation",
            expected_revision=0,
            role="user",
            content="first turn",
        )
        initial_revision = cached_reader.get_revision(
            project_id="project",
            conversation_id="conversation",
        )
        writer.append(
            project_id="project",
            conversation_id="conversation",
            expected_revision=1,
            role="assistant",
            content="second turn",
        )

        stale_revision = cached_reader.get_revision(
            project_id="project",
            conversation_id="conversation",
        )
        stale_record = cached_reader.get(project_id="project", conversation_id="conversation")
        accepted = cached_reader.get_or_create(
            project_id="project",
            conversation_id="conversation",
            expected_revision=1,
        )
        fresh_record = ConversationStore(storage_dir).get(
            project_id="project",
            conversation_id="conversation",
        )

        print(f"initial_reader_revision={initial_revision}")
        print(f"cached_reader_revision_after_remote_append={stale_revision}")
        print(f"cached_reader_message_count_after_remote_append={len(stale_record.messages) if stale_record else None}")
        print(f"stale_get_or_create_accepted_revision={accepted.revision}")
        print(f"fresh_reader_revision={fresh_record.revision if fresh_record else None}")
        print(f"fresh_reader_message_count={len(fresh_record.messages) if fresh_record else None}")


if __name__ == "__main__":
    main()
