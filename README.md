# Note Agent

基于 **LangGraph + LangChain** 的研究笔记 Agent。它可以从手动输入、文本文件和网页内容中整理研究主题，自动生成 Markdown 笔记，并通过参考信息检索、事实核验、多轮修正和多模态资产生成提升笔记质量。

## 功能

- 多输入源：手动文本、`.txt` / `.md` 文件、网页 URL
- 多模型后端：DeepSeek、OpenAI、Qwen、Moonshot、Zhipu、SiliconFlow
- 统一参考检索：Web、论文、综合学术资料
- 事实核验与多轮修正
- 自动保存最终笔记、中间版本、运行日志和生成资产
- Streamlit 可视化界面
- 可选公式、代码、Mermaid 图和图表资产生成
- 一键发布笔记到 Notion（子页面模式）

## 项目结构

```text
note-agent/
├─ scripts/
│  └─ main.py                   # CLI 兼容 wrapper
├─ src/note_agent/
│  ├─ __init__.py               # 版本号
│  ├─ cli.py                    # 命令行交互入口
│  ├─ web.py                    # Streamlit 界面入口
│  ├─ utils.py                  # 通用工具函数
│  ├─ config/
│  │  ├─ settings.py            # LLM 模型配置
│  │  └─ llm.py                 # LLM 调用封装
│  ├─ domain/
│  │  ├─ models.py              # 领域模型（ReferenceItem, NoteResearchState 等）
│  │  └─ api.py                 # I/O schema（NoteAgentRequest/Response）
│  ├─ agent/
│  │  ├─ graph.py               # LangGraph 工作流
│  │  ├─ runner.py              # 同步/流式服务层
│  │  └─ prompts.py             # LLM 提示词模板
│  ├─ retrieval/
│  │  ├─ retriever.py           # 检索编排与格式化
│  │  ├─ sources.py             # 8 种搜索后端（Web/论文/书籍/学术）
│  │  └─ cache.py               # 检索结果缓存
│  ├─ io/
│  │  ├─ events.py              # 流式事件系统
│  │  ├─ input_loader.py        # 文本/文件/网页输入加载
│  │  ├─ storage.py             # 运行日志、状态快照、中间文件
│  │  └─ text.py                # 文本/Markdown 工具
│  ├─ assets/
│  │  ├─ types.py               # 资产 Pydantic 模型
│  │  └─ tools.py               # 资产生成与 Markdown 注入
│  └─ notion/
│     ├─ client.py              # Notion SDK 封装
│     ├─ converter.py           # Markdown → Notion blocks
│     └─ publish.py             # 发布编排
├─ tests/
│  ├─ conftest.py
│  ├─ unit/                     # 单元测试
│  └─ integration/              # 集成测试（占位）
├─ demos/                       # 历史示例
├─ notes/                       # 生成的笔记和资产
├─ runs/                        # 运行日志
├─ .cache/                      # 检索缓存
├─ app.py                       # 入口：streamlit run app.py
├─ pyproject.toml
└─ uv.lock
```

## 安装

推荐使用 `uv`：

```bash
uv sync
```

如果需要生成图表图片等多模态资产：

```bash
uv sync --extra assets
```

如果需要发布笔记到 Notion：

```bash
uv sync --extra notion
```

## 配置

复制环境变量模板：

```powershell
copy .env.example .env
```

至少配置一个模型供应商的 API Key：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
OPENAI_API_KEY=your_openai_api_key
DASHSCOPE_API_KEY=your_qwen_api_key
MOONSHOT_API_KEY=your_moonshot_api_key
ZHIPU_API_KEY=your_zhipu_api_key
SILICONFLOW_API_KEY=your_siliconflow_api_key

DEFAULT_LLM_PROVIDER=deepseek
SEARCH_API=duckduckgo
DEFAULT_MAX_ITERATIONS=1

# Notion（可选）
NOTION_API_KEY=your_notion_integration_secret
NOTION_PARENT_PAGE_ID=your_notion_parent_page_id
```

### Notion 集成步骤

1. 访问 [Notion Integrations](https://www.notion.so/my-integrations) 创建集成，复制 **Internal Integration Secret** 填入 `NOTION_API_KEY`
2. 在 Notion 中创建一个页面作为笔记的父页面，从 URL 中复制 32 位页面 ID 填入 `NOTION_PARENT_PAGE_ID`
3. 在集成页面点击 **Add connections**，授权该父页面
4. 在 Streamlit 界面侧边栏勾选 **"Publish to Notion"** 即可

## 运行

命令行：

```bash
uv run note-agent          # 通过 pyproject.toml 入口
python scripts/main.py     # 或直接脚本
```

Streamlit 界面：

```bash
uv run streamlit run app.py
```

## 测试

```bash
uv run pytest tests/ -v
```

## 输出

- `notes/`：最终 Markdown 笔记
- `notes/intermediate/`：每轮中间版本
- `notes/assets/`：公式、代码、Mermaid、图表等生成资产
- `runs/{run_id}/`：运行摘要、事件日志和最终状态快照
- `.cache/references/`：参考信息检索缓存
