"""
Image Agent — 多模态
职责：
  1. 若用户上传了参考图，用视觉模型分析风格
  2. 将风格 + 文案摘要拼成 DALL-E 3 prompt
  3. 调用 generate_image 生成图片并下载本地
"""
import os
import base64
import time
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from mcp.tools.image_gen import generate_image, download_image


# ---------- 图片理解 ----------

def _analyze_image_gpt(image_path: str) -> str:
    """用 gpt-4o-mini 分析参考图风格"""
    client = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        temperature=0.2,
    )

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    ext = Path(image_path).suffix.lower().lstrip(".")
    media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"

    message = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{image_data}"},
        },
        {
            "type": "text",
            "text": (
                "请分析这张图片的视觉风格，用英文描述以下要素（供 DALL-E 3 使用）：\n"
                "1. Color palette (主色调)\n"
                "2. Composition style (构图风格)\n"
                "3. Lighting (光线)\n"
                "4. Overall aesthetic (整体美感)\n"
                "输出一段简洁的英文描述，50词以内。"
            ),
        },
    ])

    response = client.invoke([message])
    return response.content.strip()


def _analyze_image_qwen(image_path: str) -> str:
    """用 Qwen-VL 分析参考图风格（国内直连）"""
    import httpx
    import json

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未配置")

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    ext = Path(image_path).suffix.lower().lstrip(".")
    media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"

    payload = {
        "model": "qwen-vl-plus",
        "input": {
            "messages": [{
                "role": "user",
                "content": [
                    {"image": f"data:{media_type};base64,{image_data}"},
                    {"text": (
                        "请分析这张图片的视觉风格，用英文描述：色调、构图、光线、整体美感，"
                        "50词以内，供 DALL-E 3 生成图片使用。"
                    )},
                ],
            }],
        },
        "parameters": {"result_format": "message"},
    }

    with httpx.Client(timeout=30) as client:
        response = client.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    return data["output"]["choices"][0]["message"]["content"][0]["text"]


def analyze_reference_image(image_path: str) -> str:
    """根据环境变量选择视觉模型分析参考图"""
    analyzer = os.getenv("IMAGE_ANALYZER", "gpt-4o-mini").lower()
    if analyzer == "qwen-vl":
        return _analyze_image_qwen(image_path)
    return _analyze_image_gpt(image_path)


# ---------- Prompt 构建 ----------

def _build_dalle_prompt(scripts: list[dict], style_desc: str, product_desc: str) -> str:
    """将文案摘要 + 风格描述合并成 DALL-E 3 prompt"""
    # 取小红书文案的核心卖点
    main_script = next((s for s in scripts if s.get("platform") == "小红书"), scripts[0] if scripts else {})
    title = main_script.get("title", "")
    hashtags = " ".join(main_script.get("hashtags", [])[:3])

    style_part = f"Visual style: {style_desc}. " if style_desc else ""
    prompt = (
        f"A high-quality marketing product photo for Chinese social media. "
        f"Product: {product_desc}. "
        f"{style_part}"
        f"Clean background, professional lighting, visually appealing, "
        f"suitable for Xiaohongshu/WeChat marketing. "
        f"No text overlay. Photorealistic."
    )
    return prompt[:1000]  # DALL-E 3 prompt 限制


# ---------- Image Agent 主函数 ----------

def run_image_agent(
    product_desc: str,
    scripts: list[dict],
    reference_image_path: str | None,
    output_dir: str = "./outputs",
) -> list[str]:
    """
    运行 Image Agent，生成并保存营销图片

    Args:
        product_desc: 产品描述
        scripts: Script Agent 生成的文案列表
        reference_image_path: 用户上传的参考图路径（可选）
        output_dir: 图片保存目录

    Returns:
        已保存的图片本地路径列表
    """
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: 分析参考图（若有）
    style_desc = ""
    if reference_image_path and os.path.exists(reference_image_path):
        try:
            style_desc = analyze_reference_image(reference_image_path)
            print(f"[ImageAgent] 参考图风格分析：{style_desc}")
        except Exception as e:
            print(f"[ImageAgent] 参考图分析失败，跳过：{e}")

    # Step 2: 构建 prompt
    dalle_prompt = _build_dalle_prompt(scripts, style_desc, product_desc)
    print(f"[ImageAgent] DALL-E 3 Prompt: {dalle_prompt[:100]}...")

    # Step 3: 生成图片
    saved_paths = []
    try:
        result = generate_image(prompt=dalle_prompt, size="1024x1024", quality="standard")
        filename = f"image_{int(time.time())}.png"
        local_path = os.path.join(output_dir, filename)
        download_image(url=result["url"], save_path=local_path)
        saved_paths.append(local_path)
        print(f"[ImageAgent] 图片已保存：{local_path}")
    except Exception as e:
        print(f"[ImageAgent] 图片生成失败：{e}")

    return saved_paths
