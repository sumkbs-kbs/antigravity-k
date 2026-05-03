import urllib.request
import json
import time

url = "http://localhost:8000/v1/chat/completions"
data = {
    "model": "qwen3.6:latest",
    "messages": [{"role": "user", "content": "안녕! 간단히 대답해."}],
    "stream": True,
    "agent_mode": True
}
req = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

start = time.time()
print(f"[{time.strftime('%H:%M:%S')}] Request sent...")
first_chunk = None
full_response = ""

with urllib.request.urlopen(req) as resp:
    for line in resp:
        decoded = line.decode("utf-8").strip()
        if not decoded or decoded == "data: [DONE]":
            continue
        if decoded.startswith("data: "):
            chunk_data = json.loads(decoded[6:])
            content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if content and first_chunk is None:
                first_chunk = time.time()
                ttfc = first_chunk - start
                print(f"[{time.strftime('%H:%M:%S')}] First chunk received in {ttfc:.2f}s")
            full_response += content

total = time.time() - start
print(f"\n[Result] Total time: {total:.2f}s")
print(f"[Result] Time to first chunk: {(first_chunk - start):.2f}s")
print(f"[Result] Response length: {len(full_response)} chars")
print(f"[Result] Response preview: {full_response[:200]}")
