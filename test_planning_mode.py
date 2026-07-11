import json
import urllib.request

data = {
    "model": "orchestrator-swarm",
    "messages": [
        {
            "role": "user",
            "content": "Antigravity-K 아키텍처를 전면 리팩토링하고 플러그인 시스템을 추가해줘. 규모가 큰 작업이야.",
        }
    ],
    "stream": True,
    "agent_mode": True,
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/v1/chat/completions",
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

print("Testing Planning Mode...")
try:
    with urllib.request.urlopen(req) as response:
        for line in response:
            line = line.decode("utf-8").strip()
            if line:
                print(line)
except Exception as e:
    print(f"Error: {e}")
