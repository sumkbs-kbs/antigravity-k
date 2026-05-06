import urllib.request
import json

url = "http://localhost:8000/v1/chat/completions"
data = {
    "model": "default",
    "messages": [{"role": "user", "content": "단순 인사말 한줄만 부탁해."}],
    "stream": True,
}
req = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)

print("Starting API Test...")
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        for line in resp:
            line = line.decode("utf-8").strip()
            if line:
                print("RECV:", line)
except Exception as e:
    print("Error:", e)
