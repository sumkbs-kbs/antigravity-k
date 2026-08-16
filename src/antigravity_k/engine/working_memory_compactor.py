"""Long-Horizon Working Memory Compactor — Infinite-turn state condensation.

Eliminates attention dilution during 50+ turn sessions by distilling raw message history
into a dense, immutable 3-part Working State:
1. Pinned Architectural Decisions (ADRs)
2. Current Modified Symbol Map
3. Pending Subgoal DAG Tasks
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkingMemoryState:
    """Structured, token-efficient working state."""

    architectural_decisions: list[str] = field(default_factory=list)
    active_files: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    compressed_summary: str = ""

    def format_pinned_working_memory(self) -> str:
        """Format as high-priority pinned context block."""
        lines = [
            "<!-- PINNED_WORKING_MEMORY_STATE: HIGHEST ATTENTION -->",
            "🧠 **[ACTIVE WORKING MEMORY & ADR STATE]**",
        ]
        if self.architectural_decisions:
            lines.append("📌 Architectural Decisions:")
            for adr in self.architectural_decisions:
                lines.append(f"  • {adr}")

        if self.active_files:
            lines.append("📂 Modified Files in Context:")
            for f in self.active_files:
                lines.append(f"  • {f}")

        if self.pending_tasks:
            lines.append("⏳ Remaining Pending Subgoals:")
            for t in self.pending_tasks:
                lines.append(f"  • {t}")

        if self.compressed_summary:
            lines.append(f"📝 Trajectory Summary: {self.compressed_summary}")

        lines.append("<!-- END_PINNED_WORKING_MEMORY -->")
        return "\n".join(lines)


class WorkingMemoryCompactor:
    """Condenses verbose multi-turn history into compact WorkingMemoryState."""

    @staticmethod
    def compact(
        messages: list[dict[str, Any]],
        adrs: list[str] | None = None,
        pending_subgoals: list[str] | None = None,
    ) -> WorkingMemoryState:
        """Distill raw message stream into pure state."""
        modified_files: set[str] = set()

        for msg in messages:
            content = str(msg.get("content", ""))
            # Extract mentioned file paths
            for line in content.splitlines():
                if any(ext in line for ext in (".py", ".json", ".yaml", ".md", ".ts", ".js")):
                    for word in line.split():
                        clean_word = word.strip("`'\",:()")
                        if "." in clean_word and "/" in clean_word or clean_word.endswith((".py", ".json", ".yaml")):
                            modified_files.add(clean_word)

        summary = f"Total turns: {len(messages)}. Tracking {len(modified_files)} active files."

        return WorkingMemoryState(
            architectural_decisions=adrs or [],
            active_files=sorted(modified_files)[:10],
            pending_tasks=pending_subgoals or [],
            compressed_summary=summary,
        )
