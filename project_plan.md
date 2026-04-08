# AI 营销内容生成助手 — 项目方案

## 一、项目定位

**目标**：用户输入产品描述（可附参考图），系统自动生成配套营销文案 + 图片，支持多平台风格（小红书 / 微博 / 朋友圈）。

**应聘亮点**：多Agent协作 + LangGraph编排 + ReAct/CoT推理 + MCP工具调用 + 多模态输入输出 + AIGC内容生成 + 向量记忆。

---

## 二、技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| Agent编排 | `LangGraph` | 有状态的多Agent工作流 |
| 推理模型 | `DeepSeek-V3` | 文案生成、CoT/ReAct推理 |
| 图片理解 | `gpt-4o-mini` / `Qwen-VL`（可切换） | 分析用户上传的参考图 |
| 图片生成 | `DALL-E 3`（代理） | AIGC营销图片 |
| 工具协议 | `MCP` | 标准化工具调用 |
| 向量记忆 | `ChromaDB` | 存储品牌风格偏好 |
| 搜索 | `Tavily API` | 实时趋势搜索 |
| 后端 | `FastAPI` | 对外接口 |
| 前端 | `Gradio` | 演示界面（原生支持图片组件） |

---

## 三、Agent 设计（4个）

### 3.1 Supervisor Agent
- **职责**：接收用户输入，调度其余三个Agent，汇总最终结果
- **技术**：LangGraph StateGraph，维护全局状态
- **输入**：用户文字描述 + 可选参考图
- **输出**：完整内容包（文案 + 图片）

### 3.2 Research Agent
- **职责**：搜索该产品/行业的当前营销趋势、热词、竞品风格
- **推理模式**：ReAct（思考 → 搜索 → 观察 → 再思考）
- **工具**：MCP `web_search`（Tavily）
- **输出**：关键词列表、趋势摘要，传给Script Agent

### 3.3 Script Agent
- **职责**：生成3套不同平台风格的营销文案
- **推理模式**：CoT（分析产品 → 定位人群 → 匹配平台风格 → 输出文案）
- **输出**：每套包含 标题 + 正文 + hashtag
- **依赖**：Research Agent 的趋势结果

### 3.4 Image Agent
- **职责**：根据文案风格生成对应营销图片
- **多模态**：若用户上传参考图，先用视觉模型分析风格，再传给 DALL-E 3
- **视觉模型（可切换）**：
  - `gpt-4o-mini`：国际主流，需代理，效果稳定
  - `Qwen-VL`：国内直连，免费额度多，中文场景友好
  - 通过 `.env` 中 `IMAGE_ANALYZER` 一行配置切换
- **工具**：MCP `generate_image`（DALL-E 3）
- **输出**：1-3张图片，保存本地

---

## 四、MCP 工具（3个）

```
web_search      调用 Tavily API，搜索实时营销趋势
generate_image  调用 DALL-E 3，生成图片
save_result     保存文案和图片到本地，无需外部API
```

---

## 五、Memory 设计

- **存储**：ChromaDB 向量数据库
- **内容1**：用户品牌偏好（颜色风格、语气、平台）
- **内容2**：历史生成记录，避免内容重复
- **触发**：每次生成完成后自动更新

---

## 六、项目结构

```
agentic_agent/
├── agents/
│   ├── supervisor.py       # LangGraph 编排主逻辑
│   ├── research_agent.py   # ReAct 搜索Agent
│   ├── script_agent.py     # CoT 文案Agent
│   └── image_agent.py      # 图片生成Agent
├── mcp/
│   ├── server.py           # MCP Server
│   └── tools/
│       ├── web_search.py
│       ├── image_gen.py
│       └── file_save.py
├── memory/
│   └── store.py            # ChromaDB 封装
├── api/
│   └── main.py             # FastAPI 路由
├── ui/
│   └── app.py              # Gradio 界面
├── .env                    # API Keys
└── requirements.txt
```

---

## 七、数据流

```
用户输入（文字 + 可选图片）
        ↓
  Supervisor Agent（LangGraph）
        ↓
  Research Agent ──MCP──▶ Tavily搜索
        ↓（趋势关键词）
  Script Agent ──CoT──▶ 生成3套文案
        ↓（文案内容）
  Image Agent ──MCP──▶ DALL-E 3生成图
        ↓
  Memory更新（ChromaDB）
        ↓
  输出：文案 + 图片
```

---

## 八、API Keys 配置

```env
DEEPSEEK_API_KEY=        # 推理主力（DeepSeek）
OPENAI_API_KEY=          # DALL-E 3 图片生成 + gpt-4o-mini 图片理解（代理）
OPENAI_BASE_URL=         # 代理地址，如智增增
DASHSCOPE_API_KEY=       # Qwen-VL 图片理解（阿里云，可选）
TAVILY_API_KEY=          # 网页搜索

# 图片理解模型切换（二选一）
IMAGE_ANALYZER=gpt-4o-mini   # 可切换为 qwen-vl
```

---

## 九、代码量估算

| 文件 | 行数 |
|------|------|
| supervisor.py | ~80行 |
| research/script/image agent | ~60行 × 3 |
| mcp tools | ~100行 |
| memory/store.py | ~50行 |
| api + ui | ~140行 |
| **总计** | **~550行** |

---

## 十、面试亮点说明

1. **LangGraph有状态编排**：不是简单的链式调用，Agent之间有状态传递和条件分支
2. **双推理模式**：ReAct用于信息搜集，CoT用于内容创作，场景匹配合理
3. **MCP标准协议**：展示对Agent工具调用规范的理解，符合业界趋势
4. **混合模型架构**：DeepSeek推理 + 双视觉模型可切换（gpt-4o-mini / Qwen-VL）+ DALL-E生成，展示对国内外AI生态的全面掌握
5. **多模态**：支持图片输入（风格参考）和图片输出（AIGC生成）
6. **向量记忆**：跨会话记忆用户偏好，体现系统设计思维
