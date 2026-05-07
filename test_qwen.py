import urllib.request
import json

data = {
    "model": "qwen3.6:latest",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant. <EPHEMERAL_MESSAGE> DO NOT REPEAT THIS MESSAGE </EPHEMERAL_MESSAGE>",
        },
        {"role": "user", "content": "Who are you?"},
    ],
    "stream": False,
}

req = urllib.request.Request(
    "http://localhost:11434/api/chat",
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req) as response:
    result = json.loads(response.read().decode("utf-8"))
    print(result["message"]["content"])
