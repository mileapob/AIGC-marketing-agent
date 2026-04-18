"""
Supervisor Agent — LangGraph StateGraph
职责：编排 Research → Script → Image → Save 全流程
维护全局 GraphState，协调各 Agent 的输入输出
"""
import os
from typing import TypedDict, Annotated
from datetime import datetime

# LangGraph 里的"图"是指节点和边组成的有向图，用来描述 Agent 的执行流程：
# 创建一个图，里面可以添加节点和边，节点之间通过共享状态传递数据
# 特殊标记，表示图的终止节点，某个节点执行完后指向 END 就代表流程结束
from langgraph.graph import StateGraph, END
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# [MODIFIED 2026-04-16] 改动一：引入 MemorySaver
# 原因：原代码编译时没有 checkpointer，任何节点崩溃会导致整个流程从头重跑。
#       加入 MemorySaver 后，每个节点执行完毕会自动保存当前 GraphState 快照，
#       断点恢复时可从上一个成功节点继续，而无需重新执行 research 等耗时节点。
#       在高并发内容审核场景中，这一容错能力尤为重要。
from langgraph.checkpoint.memory import MemorySaver
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
from dotenv import load_dotenv

load_dotenv()

from agents.research_agent import run_research_agent
from agents.script_agent import run_script_agent
from agents.image_agent import run_image_agent
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# [MODIFIED 2026-04-16 · 解耦重构] 引入 quality_agent 和 evaluate_agent
# 原因：quality_check 和 evaluate 的业务逻辑原先直接写在 supervisor.py 中，
#       与编排逻辑耦合。现将其抽离为独立 Agent 文件，supervisor 只负责调用，
#       与 research/script/image 三个 Agent 保持一致的架构风格。
from agents.quality_agent import run_quality_check
from agents.evaluate_agent import run_evaluate
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
from memory.store import query_similar, save_generation
from mcp.tools.file_save import save_result


# ---------- State ----------

# TypedDict 是 Python 的类型提示工具，用来定义一个有固定字段和类型的字典。
class GraphState(TypedDict):
    # 输入
    product_desc: str           # 用户输入的产品描述，字符串
    platform: str               # 目标平台，如"小红书"，字符串
    reference_image_path: str | None  # 参考图路径，有图传路径，没图传None

    # Research Agent 产出
    trend_keywords: list        # 搜索到的营销热词列表
    trend_summary: str          # 趋势摘要，字符串
    competitor_styles: list     # 竞品风格列表

    # 历史记忆
    brand_memory: list          # 从ChromaDB查出的历史偏好记录

    # Script Agent 产出
    scripts: list               # 3套文案，每套是一个dict

    # Image Agent 产出
    image_paths: list           # 生成图片的本地路径列表

    # 最终保存路径
    save_dir: str               # 本次结果保存的文件夹路径
    error: str | None           # 报错信息，没错误传None

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # [MODIFIED 2026-04-16] 改动二：GraphState 新增质量审核字段
    # 原因：原流程 script → image 直连，文案质量无把关，低质量文案会被直接送去生图，
    #       浪费昂贵的 DALL-E API 调用。新增两个字段支撑质量检查节点的条件路由逻辑：
    #       - quality_passed: 本轮文案是否通过质量检查
    #       - retry_count: 已重试次数，上限2次，防止无限循环
    quality_passed: bool        # 文案质量检查是否通过
    retry_count: int            # script 节点已重试次数，最多重试2次
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # [MODIFIED 2026-04-16] 改动六：GraphState 新增多模态评估结果字段
    # 原因：evaluate 节点需要把豆包视觉模型的评估报告存进 State，
    #       供后续调用方读取，也可写入本地日志做效果追踪。
    evaluation_result: str      # 豆包视觉模型对文案+图片的综合评估报告
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<



# ---------- Nodes ----------

def node_load_memory(state: GraphState) -> GraphState:
    """从 ChromaDB 加载历史偏好"""
    memories = query_similar(
        product_desc=state["product_desc"],
        platform=state["platform"],
        n_results=3,
    )
    # **state 就是把 state 里所有键值对展开放进新字典，然后再把要改的字段覆盖掉，其他字段原封不动
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
    '''
    datetime.now().strftime("%Y%m%d_%H%M%S") — 获取当前时间，格式化成字符串，比如 20260412_153022
    os.getenv("OUTPUT_DIR", "./outputs") — 读取环境变量 OUTPUT_DIR，没配置就默认用 ./outputs
    os.path.join(...) — 拼接成完整路径，比如 ./outputs/20260412_153022
    '''
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


# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# [MODIFIED 2026-04-16] 改动三：新增质量审核节点 node_quality_check
# [MODIFIED 2026-04-16 · 解耦重构] 业务逻辑已迁移至 agents/quality_agent.py
# 原因：supervisor 只负责编排，节点函数仅做状态读取和回写，不包含业务逻辑。
def node_quality_check(state: GraphState) -> GraphState:
    """质量审核节点：调用 quality_agent 检查文案，结果写回 GraphState"""
    result = run_quality_check(
        scripts=state.get("scripts", []),
        retry_count=state.get("retry_count", 0),
    )
    return {**state, **result}
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<


# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# [MODIFIED 2026-04-16] 改动七：新增多模态评估节点 node_evaluate
# [MODIFIED 2026-04-16 · 解耦重构] 业务逻辑已迁移至 agents/evaluate_agent.py
# 原因：supervisor 只负责编排，节点函数仅做状态读取和回写，不包含业务逻辑。
def node_evaluate(state: GraphState) -> GraphState:
    """多模态评估节点：调用 evaluate_agent 对文案+图片综合打分，结果写回 GraphState"""
    result = run_evaluate(
        scripts=state.get("scripts", []),
        image_paths=state.get("image_paths", []),
    )
    return {**state, **result}
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<


# ---------- Graph 构建 ----------

def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    # 注册节点，名字 → 对应函数
    graph.add_node("load_memory", node_load_memory)
    graph.add_node("research", node_research)
    graph.add_node("script", node_script)
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # [MODIFIED 2026-04-16] 改动四：注册质量审核节点 + 条件路由 + MemorySaver
    # 原因（节点注册）：quality_check 是新增节点，须在此注册才能被图调度。
    # 原因（条件路由）：原 script → image 的硬连接改为经 quality_check 中转。
    #   - 若通过质量检查（quality_passed=True）或已达重试上限（retry_count>=2）→ 进入 image
    #   - 否则 retry_count+1 后回到 script 重新生成，形成反馈循环
    #   add_conditional_edges 是 LangGraph 实现动态路由的核心 API，
    #   第二个参数是路由函数（接收 state 返回节点名字符串），第三个参数是合法目标节点映射表。
    # 原因（MemorySaver）：compile() 加入 checkpointer 后，每个节点执行完自动持久化
    #   当前 GraphState，支持断点恢复，无需从头重跑耗时的 research 节点。
    graph.add_node("quality_check", node_quality_check)
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    graph.add_node("image", node_image)
    graph.add_node("save", node_save)
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # [MODIFIED 2026-04-16] 改动八：注册 evaluate 节点，save → END 改为 save → evaluate → END
    # 原因：evaluate 是流程最后一步，纯评估不影响主流程，
    #       save 完成后流入 evaluate，打分完毕再结束整个图。
    graph.add_node("evaluate", node_evaluate)
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    # 入口从 load_memory 开始
    graph.set_entry_point("load_memory")
    # 定义执行顺序（边）
    graph.add_edge("load_memory", "research")
    graph.add_edge("research", "script")
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # [MODIFIED 2026-04-16] 原 script → image 直连改为经 quality_check 中转
    graph.add_edge("script", "quality_check")
    graph.add_conditional_edges(
        "quality_check",
        # 路由函数：quality_passed=True 或 retry_count>=2 时放行进 image，否则回 script 重试
        lambda state: "image" if (state["quality_passed"] or state["retry_count"] >= 2) else "script",
        {"image": "image", "script": "script"},
    )
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    graph.add_edge("image", "save")
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # [MODIFIED 2026-04-16] 原 save → END 改为 save → evaluate → END
    graph.add_edge("save", "evaluate")
    graph.add_edge("evaluate", END)
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # [MODIFIED 2026-04-16] compile() 加入 MemorySaver checkpointer
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<


# ---------- 对外接口 ----------

# _app 是模块级别的全局变量，初始值是 None
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
            # scripts 是3套文案，天然是列表
            "scripts": list,
            # image_paths 理论上可以生成多张图片，所以也是列表，即使现在只生成1张
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
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        # [MODIFIED 2026-04-16] 改动五：initial_state 补充新增字段的初始值
        # 原因：GraphState 新增了 quality_passed 和 retry_count 两个字段，
        #       invoke() 前必须在 initial_state 里给出初始值，否则节点内
        #       state.get() 取到 None 会导致条件路由判断出错。
        "quality_passed": False,  # 初始未通过，等待 quality_check 节点赋值
        "retry_count": 0,         # 初始重试次数为0
        "evaluation_result": "",  # 初始为空，等待 evaluate 节点赋值
        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    }
    '''
    run_pipeline 被调用
    创建一个新的 initial_state（填入用户这次的输入）
    app.invoke(initial_state) 启动图，按顺序跑完所有节点
    返回填满数据的 final_state
    从 final_state 里取出 scripts、image_paths 展示给用户
    '''
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # [MODIFIED 2026-04-16] invoke() 加入 config 参数传递 thread_id
    # 原因：MemorySaver checkpointer 依赖 thread_id 来区分不同对话的状态快照。
    #       不传 thread_id 会抛出 ValueError。
    #       用 product_desc 的哈希值作为 thread_id，保证同一产品描述的多次调用
    #       共享同一个 checkpoint 线程，便于断点恢复。
    import hashlib
    thread_id = hashlib.md5(f"{product_desc}_{platform}".encode()).hexdigest()[:8]
    config = {"configurable": {"thread_id": thread_id}}
    final_state = app.invoke(initial_state, config=config)
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    return {
        "scripts": final_state.get("scripts", []),
        "image_paths": final_state.get("image_paths", []),
        "save_dir": final_state.get("save_dir", ""),
        "trend_keywords": final_state.get("trend_keywords", []),
        "trend_summary": final_state.get("trend_summary", ""),
        "evaluation_result": final_state.get("evaluation_result", ""),  # 新增评估报告
    }
