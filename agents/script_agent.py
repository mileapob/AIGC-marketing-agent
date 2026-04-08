"""
Script Agent — CoT 模式
职责：根据产品描述 + 趋势关键词，生成3套不同平台风格的营销文案
输出：scripts（list of dict，每套含 platform/title/body/hashtags）
"""
import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


SYSTEM_PROMPT = """你是一位资深营销文案专家，专注于中国社交媒体内容创作。
你将使用链式思考（CoT）逐步分析，生成高质量营销文案。
输出必须是合法的 JSON，不要包含任何 JSON 以外的文字。"""

COT_TEMPLATE = """请按照以下步骤思考，然后生成3套营销文案：

**产品信息**
- 产品描述：{product_desc}
- 目标平台：{platform}
- 营销趋势关键词：{trend_keywords}
- 趋势摘要：{trend_summary}
- 历史偏好参考：{brand_memory}

**思考步骤（CoT）**
Step 1: 分析产品核心卖点和差异化优势
Step 2: 识别目标受众（年龄/性别/兴趣/消费能力）
Step 3: 结合趋势关键词，确定内容方向
Step 4: 按平台特性生成3套文案

**平台风格要求**
- 小红书：emoji丰富、种草感强、口语化、标题要有吸引力（加✨💕等）、结尾引导互动
- 微博：简短有力、话题感、140字内正文、热搜词风格标题
- 朋友圈：生活化、情感共鸣、不超过150字、真实感强、不过度营销

**输出格式（严格遵守）**
{{
  "scripts": [
    {{
      "platform": "小红书",
      "title": "标题（25字内）",
      "body": "正文内容",
      "hashtags": ["话题1", "话题2", "话题3"]
    }},
    {{
      "platform": "微博",
      "title": "标题",
      "body": "正文内容",
      "hashtags": ["话题1", "话题2"]
    }},
    {{
      "platform": "朋友圈",
      "title": "",
      "body": "朋友圈文案（无标题）",
      "hashtags": []
    }}
  ]
}}"""


def run_script_agent(
    product_desc: str,
    platform: str,
    trend_keywords: list,
    trend_summary: str,
    brand_memory: list,
) -> list[dict]:
    """
    运行 Script Agent，生成3套文案

    Returns:
        list of {"platform": str, "title": str, "body": str, "hashtags": list}
    """
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
        temperature=0.7,
    )

    memory_str = ""
    if brand_memory:
        memory_str = "；".join([
            f"{m.get('platform', '')}风格：{m.get('style_notes', '')}"
            for m in brand_memory[:2]
        ])
    else:
        memory_str = "无历史记录"

    user_prompt = COT_TEMPLATE.format(
        product_desc=product_desc,
        platform=platform,
        trend_keywords="、".join(trend_keywords) if trend_keywords else "无",
        trend_summary=trend_summary or "无",
        brand_memory=memory_str,
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    response = llm.invoke(messages)
    output = response.content.strip()

    # 提取 JSON
    try:
        start = output.find("{")
        end = output.rfind("}") + 1
        data = json.loads(output[start:end])
        return data.get("scripts", [])
    except Exception:
        # 降级返回空文案占位
        return [
            {"platform": "小红书", "title": "文案生成失败", "body": output[:200], "hashtags": []},
            {"platform": "微博", "title": "文案生成失败", "body": "", "hashtags": []},
            {"platform": "朋友圈", "title": "", "body": "", "hashtags": []},
        ]
