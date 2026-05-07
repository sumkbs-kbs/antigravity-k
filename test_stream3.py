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
    out, rep = processor.process_text(chunk)
    print(
        f"chunk: {repr(chunk)} -> out: {repr(out)}, in_scratch: {processor._state.in_scratch_pad}, buffer: {repr(processor._buffer)}"
    )

out = processor.process_flush_text("")
print(f"flush -> {repr(out)}")
