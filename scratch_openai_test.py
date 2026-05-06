from openai import OpenAI
import os

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-antigravity")

print("Starting Test using OpenAI SDK...")
try:
    response = client.chat.completions.create(
        model="default",
        messages=[
            {"role": "user", "content": "파이썬의 주요 장단점을 하나씩만 설명해줘"}
        ],
        stream=True,
    )
    for chunk in response:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n\n--- OpenAI SDK Test Complete ---")
except Exception as e:
    print(f"Error: {e}")
