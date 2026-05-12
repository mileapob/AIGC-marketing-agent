"""
MCP 工具：generate_image
调用 DALL-E 3 生成营销图片
"""
import os
import httpx
from openai import OpenAI


def generate_image(prompt: str, size: str = "1024x1024", quality: str = "standard") -> dict:
    """
    调用 DALL-E 3 生成图片

    Args:
        prompt: 图片描述 prompt（英文效果更好）
        size: 图片尺寸，可选 "1024x1024" / "1792x1024" / "1024x1792"
        quality: "standard" 或 "hd"

    Returns:
        {"url": str, "revised_prompt": str}
    """
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality=quality,
        n=1,
    )

    image_data = response.data[0]
    return {
        "url": image_data.url,
        "revised_prompt": image_data.revised_prompt or prompt,
    }


def download_image(url: str, save_path: str) -> str:
    """下载图片到本地"""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with httpx.Client(timeout=60) as client:
        response = client.get(url)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(response.content)
    return save_path
