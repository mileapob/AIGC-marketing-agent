# 项目上下文 — AI 营销内容生成助手

## 项目方案文件
F:\05switch2AI\06_Agent\agentic_agent\project_plan.md

## 当前进度
- [x] 项目方案确定
- [ ] 开始写代码

## 项目核心信息

**目标**：用户输入产品描述（可附参考图）→ 自动生成营销文案 + 图片，支持小红书/微博/朋友圈风格

### 4个Agent
1. **Supervisor Agent** — LangGraph StateGraph 编排主流程
2. **Research Agent** — ReAct模式，MCP调用Tavily搜索营销趋势
3. **Script Agent** — CoT模式，生成3套文案（标题+正文+hashtag）
4. **Image Agent** — 分析参考图 + DALL-E 3 生成营销图片

### 技术栈
- 编排：LangGraph
- 推理：DeepSeek-V3
- 图片理解：gpt-4o-mini / Qwen-VL（IMAGE_ANALYZER 配置切换）
- 图片生成：DALL-E 3（OpenAI代理，如智增增）
- 工具协议：MCP（3个工具：web_search / generate_image / save_result）
- 向量记忆：ChromaDB
- 搜索：Tavily API
- 后端：FastAPI
- 前端：Gradio

### API Keys 清单
```
DEEPSEEK_API_KEY=
OPENAI_API_KEY=          # 代理
OPENAI_BASE_URL=         # 如智增增地址
DASHSCOPE_API_KEY=       # Qwen-VL（可选）
TAVILY_API_KEY=
IMAGE_ANALYZER=gpt-4o-mini   # 可切换为 qwen-vl
```

### 项目结构
```
agentic_agent/
├── agents/
│   ├── supervisor.py
│   ├── research_agent.py
│   ├── script_agent.py
│   └── image_agent.py
├── mcp/
│   ├── server.py
│   └── tools/
│       ├── web_search.py
│       ├── image_gen.py
│       └── file_save.py
├── memory/
│   └── store.py
├── api/
│   └── main.py
├── ui/
│   └── app.py
├── .env
└── requirements.txt
```

## 下次继续
告诉Claude：「读一下 F:\05switch2AI\06_Agent\agentic_agent\CONTEXT.md，继续写代码」
