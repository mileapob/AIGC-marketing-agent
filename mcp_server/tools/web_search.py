"""
MCP 工具：web_search
调用 Tavily API 搜索营销趋势
"""
import os
from tavily import TavilyClient


def web_search(query: str, max_results: int = 5) -> dict:
    """
    搜索营销相关趋势和热词

    Args:
        query: 搜索关键词，如"护肤品小红书营销趋势2024"
        max_results: 返回结果数量，默认5条

    Returns:
        {"results": [...], "query": query}
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY 未配置")

    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        max_results=max_results,
        search_depth="basic",
        include_answer=True,
    )

    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "content": item.get("content", "")[:300],
            "url": item.get("url", ""),
            "score": item.get("score", 0),
        })

    return {
        "query": query,
        "answer": response.get("answer", ""),
        "results": results,
    }
