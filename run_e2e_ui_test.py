import asyncio

from playwright.async_api import async_playwright


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Navigating to http://localhost:5174/ ...")
        await page.goto("http://localhost:5174/")

        print("Waiting for #chat-input...")
        await page.wait_for_selector("#chat-input", timeout=10000)

        prompt_text = "test_process.md 파일과 test_report.md 파일을 동시에 읽어서 요약해줄래? 병렬 호출(parallel tool call)을 테스트하는 중이야."
        print(f"Typing prompt: {prompt_text}")
        await page.fill("#chat-input", prompt_text)
        await page.click("#send-btn")

        print("Waiting for response to start streaming...")
        await asyncio.sleep(5)  # wait for new bubble

        print("Waiting 25 seconds for stream to finish...")
        await asyncio.sleep(25)

        print("Taking screenshot of parallel execution...")
        await page.screenshot(
            path="/Users/mr.k/.gemini/antigravity/brain/e78058c2-cc06-4c10-b26d-751b68a214aa/artifacts/parallel_exec.png",
            full_page=True,
        )

        # Extract response text and tool-cards
        cards = await page.locator(".tool-card").all_inner_texts()
        print("Tool Cards:")
        for c in cards:
            print("-", c.split("\n")[0])

        content = await page.locator(".message.assistant").last.inner_text()
        print("Response received:")
        print("=" * 40)
        print(content)
        print("=" * 40)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
