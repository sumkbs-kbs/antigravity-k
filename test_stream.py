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

result = ""
for chunk in chunks:
    out, rep = processor.process_text(chunk)
    print(f"chunk: {repr(chunk)} -> out: {repr(out)}")
    result += out

out = processor.process_flush_text("")
print(f"flush -> out: {repr(out)}")
result += out
print(f"RESULT: '{result}'")
