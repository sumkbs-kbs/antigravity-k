import sys
import json
import httpx
import asyncio

API_URL = "http://localhost:8000/v1/chat/completions"
TARGET_MODEL = "gemini-3.1-pro"  # or whatever is available, let's just pass "gemini" or let the API route it. I'll use default.


async def stream_chat(messages, plan_mode=True):
    payload = {
        "model": "default",
        "messages": messages,
        "stream": True,
        "agent_mode": True,
        "plan_mode": plan_mode,
    }

    assistant_response = ""
    waiting_for_approval = False

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            async with client.stream("POST", API_URL, json=payload) as response:
                if response.status_code != 200:
                    print(f"Error: {response.status_code}")
                    content = await response.aread()
                    print(content.decode())
                    return None, False

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            chunk = (
                                data.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            assistant_response += chunk
                            sys.stdout.write(chunk)
                            sys.stdout.flush()

                            if (
                                "[PLANNING_MODE: WAITING_FOR_USER_APPROVAL]" in chunk
                                or "승인" in chunk
                                or "동의" in chunk
                            ):
                                waiting_for_approval = True
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"\nRequest Failed: {e}")
            return None, False

    print("\n")
    return assistant_response, waiting_for_approval


async def main():
    print("=== Starting E2E Test for Ssak AI Lab ===\n")

    prompt = (
        "Ssak AI Lab 프로젝트를 /Users/mr.k/program/coding/ssak_comp/antigravity-k/ssak-ai-lab 에 구축해줘. "
        "지식 공유를 위한 웹사이트이며, 이번에는 순수 HTML, CSS, JS만 사용하여 다크모드 기반의 모던 UI로 만들어줘. "
        "자율 기획(Planning Mode)을 통해 기획부터 코딩까지 완수해라."
    )

    messages = [{"role": "user", "content": prompt}]

    print(">>> Phase 1: Sending Initial Request (Planning Mode)...\n")
    resp, needs_approval = await stream_chat(messages, plan_mode=True)

    if not resp:
        print("Test failed at Phase 1.")
        return

    messages.append({"role": "assistant", "content": resp})

    if needs_approval or "승인" in resp or "plan" in resp.lower() or "계획" in resp:
        print("\n>>> Agent is waiting for approval. Sending Auto-Approval...\n")
        approval_msg = "승인합니다. 계획대로 진행해주세요."
        messages.append({"role": "user", "content": approval_msg})

        print(">>> Phase 2: Executing Implementation...\n")
        # Turn off plan_mode in the second request, since we already planned.
        resp2, _ = await stream_chat(messages, plan_mode=False)

        if resp2:
            print("\n=== E2E Test Completed ===")
    else:
        print("\n=== E2E Test Completed (No explicit approval detected) ===")


if __name__ == "__main__":
    asyncio.run(main())
