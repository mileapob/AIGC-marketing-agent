"""
MCP 工具：save_result
保存文案和图片信息到本地（JSON + 目录结构）
"""
import os
import json
from datetime import datetime


def save_result(scripts: list[dict], image_paths: list[str], product_desc: str) -> dict:
    """
    保存本次生成结果到本地

    Args:
        scripts: 3套文案列表，每套包含 platform/title/body/hashtags
        image_paths: 已下载的图片本地路径列表
        product_desc: 产品描述（用于命名）

    Returns:
        {"save_dir": str, "manifest_path": str}
    """
    output_root = os.getenv("OUTPUT_DIR", "./outputs")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = product_desc[:20].replace(" ", "_").replace("/", "_")
    save_dir = os.path.join(output_root, f"{timestamp}_{safe_name}")
    os.makedirs(save_dir, exist_ok=True)

    manifest = {
        "product_desc": product_desc,
        "created_at": datetime.now().isoformat(),
        "scripts": scripts,
        "images": image_paths,
    }

    manifest_path = os.path.join(save_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return {
        "save_dir": save_dir,
        "manifest_path": manifest_path,
        "scripts_count": len(scripts),
        "images_count": len(image_paths),
    }
