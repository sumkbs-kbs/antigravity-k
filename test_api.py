import urllib.request
import json

url = "http://localhost:8000/v1/chat/completions"
data = {
    "model": "deepseek-r1:70b",
    "messages": [{"role": "user", "content": "안녕"}],
    "stream": True,
    "agent_mode": True
}
req = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

print("Starting request...")
try:
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            print(line.decode("utf-8").strip())
except Exception as e:
    print(f"Failed: {e}")
