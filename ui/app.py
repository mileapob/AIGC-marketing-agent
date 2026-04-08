"""
Gradio 前端界面
布局：左侧输入区 | 右侧文案Tab + 图片展示
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gradio as gr
from dotenv import load_dotenv

load_dotenv()

from agents.supervisor import run_pipeline


# ---------- 核心回调 ----------

def generate_content(product_desc: str, platform: str, reference_image):
    """
    Gradio 回调：触发完整生成流程

    Returns:
        (小红书文案, 微博文案, 朋友圈文案, 图片列表, 趋势关键词, 状态信息)
    """
    if not product_desc.strip():
        return "请输入产品描述", "", "", [], "❌ 产品描述不能为空", ""

    # 保存上传图片到临时文件
    ref_path = None
    if reference_image is not None:
        ref_path = reference_image  # Gradio Image 组件返回临时文件路径

    try:
        result = run_pipeline(
            product_desc=product_desc.strip(),
            platform=platform,
            reference_image_path=ref_path,
        )
    except Exception as e:
        return f"生成失败：{e}", "", "", [], f"❌ {str(e)}", ""

    scripts = result.get("scripts", [])
    image_paths = result.get("image_paths", [])
    keywords = result.get("trend_keywords", [])
    save_dir = result.get("save_dir", "")

    # 按平台提取文案
    def format_script(s: dict) -> str:
        title = s.get("title", "")
        body = s.get("body", "")
        tags = " ".join([f"#{t}" for t in s.get("hashtags", [])])
        parts = []
        if title:
            parts.append(f"**{title}**\n")
        parts.append(body)
        if tags:
            parts.append(f"\n\n{tags}")
        return "".join(parts)

    xhs = next((format_script(s) for s in scripts if s.get("platform") == "小红书"), "暂无")
    weibo = next((format_script(s) for s in scripts if s.get("platform") == "微博"), "暂无")
    pyq = next((format_script(s) for s in scripts if s.get("platform") == "朋友圈"), "暂无")

    keywords_str = "、".join(keywords) if keywords else "无"
    status = f"✅ 生成完成！已保存至：{save_dir}"

    return xhs, weibo, pyq, image_paths, status, keywords_str


# ---------- UI 布局 ----------

with gr.Blocks(title="AI营销内容生成助手", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 🎯 AI 营销内容生成助手
        输入产品描述，自动生成小红书 / 微博 / 朋友圈三套营销文案 + 配套图片
        """
    )

    with gr.Row():
        # 左侧输入区
        with gr.Column(scale=1):
            product_desc = gr.Textbox(
                label="产品描述",
                placeholder="例如：一款主打保湿补水的玻尿酸精华液，适合干性敏感肌，成分温和...",
                lines=5,
            )
            platform = gr.Radio(
                choices=["小红书", "微博", "朋友圈"],
                value="小红书",
                label="主要目标平台（文案风格参考）",
            )
            reference_image = gr.Image(
                label="参考风格图片（可选）",
                type="filepath",
                height=200,
            )
            generate_btn = gr.Button("🚀 开始生成", variant="primary", size="lg")
            status_box = gr.Textbox(label="状态", interactive=False)
            trend_keywords = gr.Textbox(label="📈 本次搜索到的趋势关键词", interactive=False)

        # 右侧输出区
        with gr.Column(scale=1):
            with gr.Tabs():
                with gr.Tab("📕 小红书"):
                    xhs_output = gr.Markdown(label="小红书文案")
                with gr.Tab("🐦 微博"):
                    weibo_output = gr.Markdown(label="微博文案")
                with gr.Tab("💬 朋友圈"):
                    pyq_output = gr.Markdown(label="朋友圈文案")

            image_gallery = gr.Gallery(
                label="🖼️ 生成的营销图片",
                columns=2,
                height=300,
                object_fit="contain",
            )

    generate_btn.click(
        fn=generate_content,
        inputs=[product_desc, platform, reference_image],
        outputs=[xhs_output, weibo_output, pyq_output, image_gallery, status_box, trend_keywords],
    )

    gr.Markdown(
        """
        ---
        **技术栈**：LangGraph · DeepSeek-V3 · DALL-E 3 · MCP · ChromaDB · Tavily
        """
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
