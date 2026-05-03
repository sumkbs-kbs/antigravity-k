import asyncio
import websockets

async def test():
    async with websockets.connect("ws://localhost:8000/ws/terminal") as websocket:
        await websocket.send("ls\n")
        for i in range(5):
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                print(f"Received: {repr(response)}")
            except asyncio.TimeoutError:
                break

asyncio.run(test())
