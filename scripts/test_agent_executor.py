import asyncio
from api_forwarder import AgentExecutor

class MockSearchEngine:
    async def search(self, query):
        class MockResponse:
            pass
        res = MockResponse()
        res.results = [
            type("Result", (), {"title": "Mock Title", "snippet": "Mock Snippet", "url": "http://mock.com", "source": "mock"})()
        ]
        return res
    
    def format_for_llm(self, results):
        return "Formatted mock search results"

class MockWiki:
    def search_for_llm(self, query, limit=3):
        return "Mock wiki hits for " + query

async def test_agent_executor():
    search_engine = MockSearchEngine()
    wiki = MockWiki()
    executor = AgentExecutor(search_engine, wiki)
    
    print("Testing web_search tool...")
    web_res = await executor.execute_tool("web_search", {"query": "test query"})
    print("Web Search Result:", web_res)
    assert web_res == "Formatted mock search results"
    
    print("Testing wiki_search tool...")
    wiki_res = await executor.execute_tool("wiki_search", {"query": "test query"})
    print("Wiki Search Result:", wiki_res)
    assert wiki_res == "Mock wiki hits for test query"
    
    print("Testing unknown tool...")
    unknown_res = await executor.execute_tool("unknown_tool", {})
    print("Unknown Tool Result:", unknown_res)
    assert "Error: 알 수 없는 도구" in unknown_res
    
    print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_agent_executor())
