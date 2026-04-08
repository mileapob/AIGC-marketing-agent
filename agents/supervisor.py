"""
Supervisor Agent — LangGraph StateGraph
职责：编排 Research → Script → Image → Save 全流程
维护全局 GraphState，协调各 Agent 的输入输出
"""
import os
from typing import TypedDict, Annotated
from datetime import datetime

from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

from agents.research_agent import run_research_agent
from agents.script_agent import run_script_agent
from agents.image_agent import run_image_agent
from memory.store import query_similar, save_generation
from mcp.tools.file_save import save_result


# ---------- State ----------

class GraphState(TypedDict):
    # 输入
    product_desc: str
    platform: str
    reference_image_path: str | None

    # Research Agent 产出
    trend_keywords: list
    trend_summary: str
    competitor_styles: list

    # 历史记忆
    brand_memory: list

    # Script Agent 产出
    scripts: list

    # Image Agent 产出
    image_paths: list

    # 最终保存路径
    save_dir: str
    error: str | None


# ---------- Nodes ----------

def node_load_memory(state: GraphState) -> GraphState:
    """从 ChromaDB 加载历史偏好"""
    memories = query_similar(
        product_desc=state["product_desc"],
        platform=state["platform"],
        n_results=3,
    )
    return {**state, "brand_memory": memories}


def node_research(state: GraphState) -> GraphState:
    """Research Agent：搜索营销趋势"""
    try:
        result = run_research_agent(
            product_desc=state["product_desc"],
            platform=state["platform"],
        )
        return {
            **state,
            "trend_keywords": result.get("trend_keywords", []),
            "trend_summary": result.get("trend_summary", ""),
            "competitor_styles": result.get("competitor_styles", []),
        }
    except Exception as e:
        print(f"[Research] 失败，使用空趋势继续：{e}")
        return {**state, "trend_keywords": [], "trend_summary": "", "competitor_styles": []}


def node_script(state: GraphState) -> GraphState:
    """Script Agent：生成3套文案"""
    scripts = run_script_agent(
        product_desc=state["product_desc"],
        platform=state["platform"],
        trend_keywords=state.get("trend_keywords", []),
        trend_summary=state.get("trend_summary", ""),
        brand_memory=state.get("brand_memory", []),
    )
    return {**state, "scripts": scripts}


def node_image(state: GraphState) -> GraphState:
    """Image Agent：生成营销图片"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.getenv("OUTPUT_DIR", "./outputs"), timestamp)

    image_paths = run_image_agent(
        product_desc=state["product_desc"],
        scripts=state.get("scripts", []),
        reference_image_path=state.get("reference_image_path"),
        output_dir=output_dir,
    )
    return {**state, "image_paths": image_paths}


def node_save(state: GraphState) -> GraphState:
    """保存结果到本地文件 + 更新 ChromaDB"""
    result = save_result(
        scripts=state.get("scripts", []),
        image_paths=state.get("image_paths", []),
        product_desc=state["product_desc"],
    )

    # 更新向量记忆
    scripts = state.get("scripts", [])
    if scripts:
        style_notes = "、".join([s.get("platform", "") for s in scripts])
        save_generation(
            platform=state["platform"],
            product_desc=state["product_desc"],
            style_notes=style_notes,
            scripts=scripts,
        )

    return {**state, "save_dir": result["save_dir"]}


# ---------- Graph 构建 ----------

def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("load_memory", node_load_memory)
    graph.add_node("research", node_research)
    graph.add_node("script", node_script)
    graph.add_node("image", node_image)
    graph.add_node("save", node_save)

    graph.set_entry_point("load_memory")
    graph.add_edge("load_memory", "research")
    graph.add_edge("research", "script")
    graph.add_edge("script", "image")
    graph.add_edge("image", "save")
    graph.add_edge("save", END)

    return graph.compile()


# ---------- 对外接口 ----------

_app = None


def get_app():
    global _app
    if _app is None:
        _app = build_graph()
    return _app


def run_pipeline(
    product_desc: str,
    platform: str = "小红书",
    reference_image_path: str | None = None,
) -> dict:
    """
    运行完整生成流程

    Returns:
        {
            "scripts": list,
            "image_paths": list,
            "save_dir": str,
            "trend_keywords": list,
        }
    """
    app = get_app()
    initial_state: GraphState = {
        "product_desc": product_desc,
        "platform": platform,
        "reference_image_path": reference_image_path,
        "trend_keywords": [],
        "trend_summary": "",
        "competitor_styles": [],
        "brand_memory": [],
        "scripts": [],
        "image_paths": [],
        "save_dir": "",
        "error": None,
    }

    final_state = app.invoke(initial_state)
    return {
        "scripts": final_state.get("scripts", []),
        "image_paths": final_state.get("image_paths", []),
        "save_dir": final_state.get("save_dir", ""),
        "trend_keywords": final_state.get("trend_keywords", []),
        "trend_summary": final_state.get("trend_summary", ""),
    }
