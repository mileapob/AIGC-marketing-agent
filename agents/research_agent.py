"""
Research Agent — ReAct 模式
职责：搜索产品/行业的当前营销趋势、热词、竞品风格
输出：trend_keywords（列表） + trend_summary（摘要）
"""
import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from tavily import TavilyClient


# ---------- Tool ----------

@tool
def web_search_tool(query: str) -> str:
    """搜索互联网获取营销趋势信息。输入搜索词，返回相关内容摘要。"""
    api_key = os.getenv("TAVILY_API_KEY")
    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        max_results=5,
        search_depth="basic",
        include_answer=True,
    )
    lines = []
    if response.get("answer"):
        lines.append(f"摘要：{response['answer']}")
    for item in response.get("results", [])[:3]:
        lines.append(f"- {item['title']}: {item['content'][:200]}")
    return "\n".join(lines)


# ---------- Agent ----------

SYSTEM_PROMPT = """你是一个营销趋势研究专家，使用 ReAct 模式分析产品的营销趋势。
搜索完成后，以 JSON 格式返回结果，包含：
{
  "trend_keywords": ["关键词1", "关键词2", ...],
  "trend_summary": "趋势摘要，100字以内",
  "competitor_styles": ["风格描述1", "风格描述2"]
}
只返回 JSON，不要其他文字。"""


def run_research_agent(product_desc: str, platform: str) -> dict:
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=0.3,
    )

    agent = create_react_agent(
        model=llm,
        tools=[web_search_tool],
        prompt=SYSTEM_PROMPT,
    )

    user_message = f"产品描述：{product_desc}\n目标平台：{platform}\n请搜索该产品的营销趋势和热词。"

    result = agent.invoke({
        "messages": [{"role": "user", "content": user_message}]
    })

    # 提取最后一条 AI 消息
    output = ""
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and msg.content:
            output = msg.content
            break

    # 提取 JSON
    try:
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(output[start:end])
        else:
            raise ValueError("No JSON found")
    except Exception:
        data = {
            "trend_keywords": [],
            "trend_summary": output[:200],
            "competitor_styles": [],
        }

    return data
