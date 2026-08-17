"""Unit tests for VRAMKVThrottler."""

from antigravity_k.engine.vram_kv_throttler import VRAMKVThrottler


def test_vram_throttling_prunes_context():
    throttler = VRAMKVThrottler(warn_threshold=0.80)

    # 10 messages simulated
    messages = [{"role": "system", "content": "sys"}]
    messages.append({"role": "user", "content": "initial goal"})
    for i in range(8):
        messages.append({"role": "assistant", "content": f"turn {i}"})

    # When memory pressure is high (85%)
    pruned, was_pruned = throttler.prune_messages_if_needed(messages, simulated_used_ratio=0.85)

    assert was_pruned is True
    assert len(pruned) < len(messages)
    assert "VRAM Throttler" in pruned[2]["content"]
