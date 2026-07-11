import json

import requests

url = "http://127.0.0.1:8000/v1/chat/completions"
headers = {"Content-Type": "application/json"}
data = {
    "model": "orchestrator-swarm",
    "messages": [
        {
            "role": "user",
            "content": "test_process.md 파일과 test_report.md 파일을 동시에 읽어서 요약해줄래? 꼭 병렬 도구 호출(parallel tool call)을 사용해줘.",
        }
    ],
    "stream": True,
}

print("Sending request to Orchestrator API...")
response = requests.post(url, headers=headers, json=data, stream=True)

for line in response.iter_lines():
    if line:
        try:
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                chunk_data = line_str[6:]
                if chunk_data == "[DONE]":
                    break
                chunk = json.loads(chunk_data)
                # handle event types
                if "event_type" in chunk:
                    print(f"[{chunk['event_type']}]", end=" ")
                    if "tool_calls" in chunk:
                        print("Tool calls triggered:", chunk["tool_calls"])
                else:
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        if "content" in delta:
                            print(delta["content"], end="", flush=True)
                        if "tool_calls" in delta:
                            print(f"[TOOL_CALL: {delta['tool_calls']}]", end="")
        except Exception:
            pass

print("\n\nDone.")
