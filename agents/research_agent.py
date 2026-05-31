"""
Research Agent — ReAct 模式（MCP版）
职责：搜索产品/行业的当前营销趋势、热词、竞品风格
输出：trend_keywords（列表） + trend_summary（摘要）
"""
import os
import json
import asyncio
from pathlib import Path

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools


SYSTEM_PROMPT = """你是一个营销趋势研究专家，使用 ReAct 模式分析产品的营销趋势。
搜索完成后，以 JSON 格式返回结果，包含：
{
  "trend_keywords": ["关键词1", "关键词2", ...],
  "trend_summary": "趋势摘要，100字以内",
  "competitor_styles": ["风格描述1", "风格描述2"]
}
只返回 JSON，不要其他文字。"""

MCP_SERVER_PATH = str(Path(__file__).parent.parent / "mcp_server" / "server.py")


async def _run_async(product_desc: str, platform: str) -> dict:
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=0.3,
    )

    server_params = StdioServerParameters(
        command="python",
        args=[MCP_SERVER_PATH],
        env=os.environ.copy(),  # 传递 TAVILY_API_KEY 等环境变量给子进程
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            search_tools = [t for t in tools if "search" in t.name]

            agent = create_react_agent(
                model=llm,
                tools=search_tools,
                prompt=SYSTEM_PROMPT,
            )

            user_message = f"产品描述：{product_desc}\n目标平台：{platform}\n请搜索该产品的营销趋势和热词。"
            result = await agent.ainvoke({
                "messages": [{"role": "user", "content": user_message}]
            })

    output = ""
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and msg.content:
            output = msg.content
            break

    try:
        if "```json" in output:
            start = output.find("```json") + 7
            end = output.find("```", start)
            json_str = output[start:end].strip()
        else:
            start = output.find("{")
            end = output.rfind("}") + 1
            json_str = output[start:end]
        data = json.loads(json_str)
    except Exception:
        data = {
            "trend_keywords": [],
            "trend_summary": output[:200],
            "competitor_styles": [],
        }

    return data


def run_research_agent(product_desc: str, platform: str) -> dict:
    return asyncio.run(_run_async(product_desc, platform))
