"""
FastAPI 后端
提供 /generate 和 /history 两个端点
"""
import os
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.supervisor import run_pipeline
from memory.store import get_stats

app = FastAPI(title="AI营销内容生成助手", version="1.0.0")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 静态文件服务（供前端预览图片）
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")


# ---------- Models ----------

class GenerateResponse(BaseModel):
    scripts: list
    image_paths: list
    save_dir: str
    trend_keywords: list
    trend_summary: str


# ---------- Routes ----------

@app.get("/")
def health_check():
    return {"status": "ok", "service": "AI营销内容生成助手"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(
    product_desc: str = Form(..., description="产品描述"),
    platform: str = Form(default="小红书", description="目标平台：小红书/微博/朋友圈"),
    reference_image: UploadFile | None = File(default=None, description="参考图片（可选）"),
):
    """
    生成营销文案和图片

    - **product_desc**: 产品描述，例如"一款主打保湿的玻尿酸精华液"
    - **platform**: 目标平台，默认小红书
    - **reference_image**: 参考风格图片（可选，jpg/png）
    """
    # 保存上传的参考图
    ref_image_path = None
    if reference_image and reference_image.filename:
        ext = Path(reference_image.filename).suffix
        tmp_path = os.path.join(OUTPUT_DIR, f"ref_{uuid.uuid4().hex}{ext}")
        with open(tmp_path, "wb") as f:
            content = await reference_image.read()
            f.write(content)
        ref_image_path = tmp_path

    try:
        result = run_pipeline(
            product_desc=product_desc,
            platform=platform,
            reference_image_path=ref_image_path,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败：{str(e)}")
    finally:
        # 清理临时参考图
        if ref_image_path and os.path.exists(ref_image_path):
            try:
                os.remove(ref_image_path)
            except Exception:
                pass

    return GenerateResponse(**result)


@app.get("/history")
def get_history():
    """查询记忆库统计和最近生成记录"""
    stats = get_stats()

    # 扫描输出目录，返回最近5次
    manifests = []
    if os.path.exists(OUTPUT_DIR):
        for manifest_file in sorted(
            Path(OUTPUT_DIR).rglob("manifest.json"), reverse=True
        )[:5]:
            try:
                import json
                with open(manifest_file, encoding="utf-8") as f:
                    manifests.append(json.load(f))
            except Exception:
                pass

    return {
        "memory_stats": stats,
        "recent_generations": manifests,
    }


@app.get("/image/{filename}")
def serve_image(filename: str):
    """提供图片文件访问"""
    for root, dirs, files in os.walk(OUTPUT_DIR):
        if filename in files:
            return FileResponse(os.path.join(root, filename))
    raise HTTPException(status_code=404, detail="图片不存在")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
