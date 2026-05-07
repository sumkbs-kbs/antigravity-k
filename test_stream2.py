import asyncio
from src.antigravity_k.engine.stream_processor import StreamProcessor

processor = StreamProcessor()

chunks = [
    "Hello ",
    "<scrat",
    "ch_pad>",
    "I am thinking",
    "</sc",
    "ratch_pad>",
    " World!",
]

for chunk in chunks:
    print(f"--- chunk: {repr(chunk)}")
    processor._buffer += chunk
    output_parts = []

    while True:
        if processor._state.in_scratch_pad:
            end_idx = processor._buffer.lower().find("</scratch_pad>")
            if end_idx != -1:
                processor._buffer = processor._buffer[end_idx + len("</scratch_pad>") :]
                processor._state.in_scratch_pad = False
            else:
                processor._buffer = ""
                break
        else:
            start_idx = processor._buffer.lower().find("<scratch_pad>")
            if start_idx != -1:
                output_parts.append(processor._buffer[:start_idx])
                processor._buffer = processor._buffer[
                    start_idx + len("<scratch_pad>") :
                ]
                processor._state.in_scratch_pad = True
            else:
                last_lt = processor._buffer.rfind("<")
                if last_lt != -1 and len(processor._buffer) - last_lt < 15:
                    output_parts.append(processor._buffer[:last_lt])
                    processor._buffer = processor._buffer[last_lt:]
                    break
                else:
                    output_parts.append(processor._buffer)
                    processor._buffer = ""
                    break

    output_text = "".join(output_parts)
    print(f"output_text: {repr(output_text)}")
