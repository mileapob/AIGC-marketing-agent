"""
MCP 工具：generate_image
调用 gpt-image-1 生成营销图片
"""
import os
import base64
import httpx
from openai import OpenAI


def generate_image(prompt: str, size: str = "1024x1024", quality: str = "standard") -> dict:
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size,
        n=1,
    )

    image_data = response.data[0]
    return {
        "url": image_data.url,
        "b64_json": image_data.b64_json,
        "revised_prompt": prompt,
    }


def download_image(url: str, save_path: str, b64_json: str = None) -> str:
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    # gpt-image-1 → 返回 b64_json，数据直接在响应体里
    if b64_json:
        with open(save_path, "wb") as f:
            f.write(base64.b64decode(b64_json))
    # DALL-E 3 → 返回临时 url，需要下载
    else:
        with httpx.Client(timeout=60) as client:
            response = client.get(url)
            response.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(response.content)
    return save_path
