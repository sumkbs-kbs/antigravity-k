from antigravity_k.engine.stream_processor import StreamProcessor


def test_stream_processor_suppresses_complete_think_block():
    processor = StreamProcessor()

    output, is_repeat = processor.process_text("앞<think>secret plan</think>뒤")

    assert is_repeat is False
    assert output == "앞뒤"
    assert "secret" not in output
    assert "Thinking Process" not in output


def test_stream_processor_suppresses_split_think_block():
    processor = StreamProcessor()

    first, _ = processor.process_text("앞<think>secret plan")
    second, _ = processor.process_text("</think>뒤")

    combined = first + second
    assert combined == "앞뒤"
    assert "secret" not in combined
    assert "Thinking Process" not in combined


def test_stream_processor_flush_suppresses_unclosed_thought_block():
    processor = StreamProcessor()

    output = processor.process_flush_text("사용자 답변<thought>internal plan")

    assert output == "사용자 답변"
    assert "internal plan" not in output
