"""
MCP 工具：generate_image
调用 gpt-image-2 生成营销图片
"""
import os
import base64
import httpx
from openai import OpenAI

# OpenAI APIKEY生成图片不稳定（智增增代理的原因）
# def generate_image(prompt: str, size: str = "1024x1024", quality: str = "standard") -> dict:
#     client = OpenAI(
#         api_key=os.getenv("OPENAI_API_KEY"),
#         base_url=os.getenv("OPENAI_BASE_URL"),
#     )

#     response = client.images.generate(
#         model="gpt-image-2",
#         prompt=prompt,
#         size=size,
#         n=1,
#     )

#     import sys

#     # 调试增加
#     print("=== RAW RESPONSE ===", response.model_dump(), file=sys.stderr, flush=True)

#     image_data = response.data[0]
#     return {
#         "url": image_data.url,
#         "b64_json": image_data.b64_json,
#         "revised_prompt": prompt,
#     }

# 调用百炼APIKEY生成图片
def generate_image(prompt: str, size: str = "1024x1024", quality: str = "standard") -> dict:
    import httpx
    import time

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未配置")

    # wanx 用 * 分隔尺寸，且只支持固定几种
    size_map = {
        "1024x1024": "1024*1024",
        "1024x1792": "720*1280",
        "1792x1024": "1280*720",
    }
    wanx_size = size_map.get(size, "1024*1024")

    # 1. 提交异步任务
    r = httpx.post(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-DashScope-Async": "enable",
            "Content-Type": "application/json",
        },
        json={
            "model": "wanx2.1-t2i-plus",
            "input": {"prompt": prompt},
            "parameters": {"size": wanx_size, "n": 1},
        },
        timeout=30,
    )
    r.raise_for_status()
    task_id = r.json()["output"]["task_id"]

    # 2. 轮询结果
    for _ in range(20):
        time.sleep(3)
        r = httpx.get(
            f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        data = r.json()
        status = data["output"]["task_status"]
        if status == "SUCCEEDED":
            url = data["output"]["results"][0]["url"]
            return {"url": url, "b64_json": None, "revised_prompt": prompt}
        elif status == "FAILED":
            raise ValueError(f"图片生成失败: {data}")

    raise TimeoutError("图片生成超时（60秒）")



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
