"""
MCP Server
注册3个工具：web_search / generate_image / save_result
通过 stdio 与 Agent 通信
"""
import os
import sys

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.fastmcp import FastMCP
from mcp.tools.web_search import web_search
from mcp.tools.image_gen import generate_image, download_image
from mcp.tools.file_save import save_result

mcp = FastMCP("marketing-tools")


@mcp.tool()
def search_marketing_trends(query: str, max_results: int = 5) -> dict:
    """
    搜索营销趋势、热词和竞品风格。
    适用于了解当前平台热点、用户喜好和内容趋势。

    Args:
        query: 搜索词，如"2024小红书护肤品营销趋势"
        max_results: 返回结果条数（1-10）
    """
    return web_search(query=query, max_results=max_results)


@mcp.tool()
def create_marketing_image(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "standard",
    save_dir: str = "./outputs",
) -> dict:
    """
    调用 DALL-E 3 生成一张营销图片并保存到本地。

    Args:
        prompt: 图片描述（英文），包含风格、色调、构图信息
        size: 尺寸，"1024x1024" / "1792x1024"（横版） / "1024x1792"（竖版）
        quality: "standard" 或 "hd"
        save_dir: 本地保存目录
    """
    import time
    result = generate_image(prompt=prompt, size=size, quality=quality)
    filename = f"image_{int(time.time())}.png"
    local_path = os.path.join(save_dir, filename)
    os.makedirs(save_dir, exist_ok=True)
    download_image(url=result["url"], save_path=local_path)
    return {
        "local_path": local_path,
        "url": result["url"],
        "revised_prompt": result["revised_prompt"],
    }


@mcp.tool()
def save_marketing_result(
    scripts: list,
    image_paths: list,
    product_desc: str,
) -> dict:
    """
    将本次生成的文案和图片保存为结构化文件。

    Args:
        scripts: 文案列表，每项含 platform/title/body/hashtags
        image_paths: 已生成的图片本地路径列表
        product_desc: 产品描述（用于命名输出目录）
    """
    return save_result(
        scripts=scripts,
        image_paths=image_paths,
        product_desc=product_desc,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
