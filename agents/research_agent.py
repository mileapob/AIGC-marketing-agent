"""
Research Agent — ReAct 模式
职责：搜索产品/行业的当前营销趋势、热词、竞品风格
输出：trend_keywords（列表） + trend_summary（摘要）
"""
import os
import json
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
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


# ---------- Prompt ----------

REACT_PROMPT = PromptTemplate.from_template("""你是一个营销趋势研究专家，使用 ReAct 模式分析产品的营销趋势。

产品描述：{product_desc}
目标平台：{platform}

你可以使用以下工具：
{tools}

工具名称：{tool_names}

按照以下格式推理：
Thought: 我需要了解什么信息？
Action: 工具名称
Action Input: 工具输入
Observation: 工具返回结果
... (可重复 Thought/Action/Observation 最多3次)
Thought: 我已经收集到足够信息
Final Answer: 以 JSON 格式返回，包含：
{{
  "trend_keywords": ["关键词1", "关键词2", ...],  // 5-8个热门营销关键词
  "trend_summary": "趋势摘要，100字以内",
  "competitor_styles": ["风格描述1", "风格描述2"]  // 竞品内容风格
}}

开始！

{agent_scratchpad}""")


# ---------- Agent ----------

def run_research_agent(product_desc: str, platform: str) -> dict:
    """
    运行 Research Agent，返回趋势关键词和摘要

    Returns:
        {
            "trend_keywords": list,
            "trend_summary": str,
            "competitor_styles": list,
        }
    """
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=0.3,
    )

    tools = [web_search_tool]
    agent = create_react_agent(llm=llm, tools=tools, prompt=REACT_PROMPT)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=4,
        verbose=True,
        handle_parsing_errors=True,
    )

    result = executor.invoke({
        "product_desc": product_desc,
        "platform": platform,
    })

    output = result.get("output", "{}")
    # 尝试从输出中提取 JSON
    try:
        # 找到第一个 { 和最后一个 }
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(output[start:end])
        else:
            raise ValueError("No JSON found")
    except Exception:
        # 降级：返回空结构
        data = {
            "trend_keywords": [],
            "trend_summary": output[:200],
            "competitor_styles": [],
        }

    return data
