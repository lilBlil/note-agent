# Note Agent

Note Agent 是一个基于 LangGraph 和 LangChain 的研究笔记生成工具。它接收主题、文本、Markdown/TXT 文件或网页链接，调用大模型生成结构化 Markdown 笔记，并可选执行资料检索、事实核验、多轮修正、资产生成和 Notion 发布。

## 功能概览

- 输入：主题、长文本、`.txt` / `.md` 文件、网页 URL
- 模型：DeepSeek、OpenAI、Anthropic、Qwen、Moonshot、Zhipu、SiliconFlow
- 检索：DuckDuckGo、Tavily、Perplexity、SearXNG
- 模式：固定工作流、ReAct Agent
- 输出：Markdown 笔记、中间版本、运行日志、参考资料缓存
- 可选：公式、代码、Mermaid、图表资产生成；发布为 Notion 子页面

## 环境要求

- Python 3.11+
- `uv`
- 至少一个 LLM API Key
- Docker 可选

安装 `uv`：

```powershell
pip install uv
```

## 快速运行

安装依赖：

```powershell
uv sync
```

如需资产生成和 Notion 发布：

```powershell
uv sync --extra assets --extra notion
```

复制环境变量：

```powershell
Copy-Item .env.example .env
```

macOS/Linux：

```bash
cp .env.example .env
```

编辑 `.env`，至少配置一个模型供应商：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DEFAULT_LLM_PROVIDER=deepseek
SEARCH_API=duckduckgo
DEFAULT_MAX_ITERATIONS=1
```

启动 Web UI：

```powershell
uv run streamlit run app.py
```

打开：

```text
http://localhost:8501
```

## 使用方式

### Web UI

Web UI 是推荐入口。你可以输入主题或正文，上传 `.txt` / `.md` 文件，或粘贴网页 URL。侧边栏提供模型、检索后端、迭代次数、运行模式、资产生成和 Notion 发布等设置。

指定端口：

```powershell
uv run streamlit run app.py --server.port 8501
```

### CLI

启动交互式命令行：

```powershell
uv run note-agent
```

CLI 会依次询问输入内容、文件路径、网页 URL、迭代次数、LLM 供应商、检索后端、运行模式，以及是否启用资产生成和 Notion 发布。

## 配置说明

`.env` 用于配置模型、检索、运行参数和 Notion。不要提交包含真实 API Key 的 `.env`。

### LLM

| provider | 环境变量 | 默认模型 |
|----------|----------|----------|
| `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-v4-pro` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514` |
| `qwen` | `DASHSCOPE_API_KEY` | `qwen-max` |
| `moonshot` | `MOONSHOT_API_KEY` | `moonshot-v1-128k` |
| `zhipu` | `ZHIPU_API_KEY` | `glm-4-plus` |
| `siliconflow` | `SILICONFLOW_API_KEY` | `deepseek-ai/DeepSeek-V3` |

模型可用性还取决于对应账号的模型权限、额度、地区和供应商当前 API 状态；如果供应商下线或改名某个模型，请在 `src/note_agent/config/settings.py` 中更新默认模型。

### 检索

| search_api | 配置 |
|------------|------|
| `duckduckgo` | 无需 Key |
| `tavily` | `TAVILY_API_KEY` |
| `perplexity` | `PERPLEXITY_API_KEY` |
| `searxng` | `SEARXNG_URL` |

### 运行参数

```env
DEFAULT_MAX_ITERATIONS=1
MAX_REFERENCE_QUERIES=3
MAX_RESULTS_PER_SOURCE=3
MAX_RETRIEVAL_WORKERS=3
REFERENCE_REQUEST_TIMEOUT=15
```

`DEFAULT_MAX_ITERATIONS=0` 表示跳过检索核验循环，仅生成笔记。

### Notion

```env
NOTION_API_KEY=your_notion_integration_secret
NOTION_PARENT_PAGE_ID=your_notion_parent_page_id
```

在 Notion 创建 Internal Integration，将父页面授权给该 Integration，然后在 Web UI 或 CLI 中启用 Notion 发布。

## Docker 运行

容器运行 Note Agent Web UI。模型、搜索和 Notion 等外部服务通过 `.env` 配置。

```powershell
docker compose up -d --build
```

访问：

```text
http://localhost:8501
```

查看日志和停止服务：

```powershell
docker compose logs -f
docker compose down
```

持久化目录：

| 宿主机目录 | 容器目录 | 内容 |
|------------|----------|------|
| `./notes` | `/app/notes` | 笔记和生成资产 |
| `./runs` | `/app/runs` | 运行记录 |
| `./.cache` | `/app/.cache` | 检索缓存 |

如果容器需要访问宿主机上的本地服务，例如本地 SearXNG，应使用：

```env
SEARXNG_URL=http://host.docker.internal:8888
```

## 输出目录

| 路径 | 内容 |
|------|------|
| `notes/` | 最终 Markdown 笔记 |
| `notes/intermediate/` | 中间版本 |
| `notes/assets/` | 公式、代码、Mermaid、图表等资产 |
| `runs/{run_id}/` | 运行摘要、事件日志、最终状态 |
| `.cache/references/` | 检索缓存 |

## 检查

```powershell
uv run pytest tests/ -v
uv run python -m compileall -q src
```
