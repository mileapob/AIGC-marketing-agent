"""
Evaluate Agent — 多模态 LLM-as-Judge 评估
职责：使用豆包视觉模型（doubao-vision-pro-32k）对文案+图片进行综合评估
      与生成模型（DeepSeek）刻意隔离，避免自评偏差
被 supervisor.py 的 node_evaluate 节点调用

评估维度：
  1. 文案质量    — 语言表达是否流畅、是否符合平台风格
  2. 图片合规性  — 画面是否包含违规或敏感元素
  3. 图文一致性  — 图片风格是否与文案主题匹配

设计说明：
  评估模型与生成模型使用不同的模型，可捕捉生成模型的系统性盲点。
  这一设计直接对应内容审核场景——初审模型和复审模型分离，提高整体准确率。
"""
import os
import base64
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage


def run_evaluate(scripts: list, image_paths: list) -> dict:
    """
    对文案列表 + 图片列表进行多模态综合评估

    Args:
        scripts:     Script Agent 生成的文案列表，每项含 platform/title/body/hashtags
        image_paths: Image Agent 生成的图片本地路径列表

    Returns:
        {
            "evaluation_result": str,  # 豆包视觉模型的评估报告
        }
    """
    # 把3套文案拼成可读文字
    scripts_text = "\n".join([
        f"【{s.get('platform', '')}】标题：{s.get('title', '')} | 正文：{s.get('body', '')}"
        for s in scripts
    ])

    # 构建消息内容，先放文字提示
    content = [
        {
            "type": "text",
            "text": (
                "请从以下三个维度评估这组营销内容，每项给出1-10分和简短理由：\n"
                "1. 文案质量：语言表达是否流畅、是否符合平台风格\n"
                "2. 图片合规性：画面是否包含违规或敏感元素\n"
                "3. 图文一致性：图片风格是否与文案主题匹配\n\n"
                f"文案内容：\n{scripts_text}"
            ),
        }
    ]

    # 把本地图片转 base64 追加进消息，最多取2张避免超出 token 限制
    for image_path in image_paths[:2]:
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            # 从路径后缀判断图片格式，jpg 统一转成 jpeg（MIME 标准写法）
            ext = os.path.splitext(image_path)[1].lower().replace(".", "")
            if ext == "jpg":
                ext = "jpeg"
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/{ext};base64,{image_data}"},
            })

    # 调用豆包视觉模型，与生成模型（DeepSeek）保持独立，避免自评偏差
    llm_eval = ChatOpenAI(
        model="doubao-vision-pro-32k",
        api_key=os.getenv("DOUBAO_API_KEY"),
        base_url="https://ark.volces.com/api/v3",
        temperature=0.1,  # 评估任务用低温度，保证输出稳定
    )

    try:
        response = llm_eval.invoke([HumanMessage(content=content)])
        evaluation_result = response.content
        print(f"[EvaluateAgent] 评估完成")
    except Exception as e:
        evaluation_result = f"评估失败：{e}"
        print(f"[EvaluateAgent] 评估失败：{e}")

    return {
        "evaluation_result": evaluation_result,
    }
