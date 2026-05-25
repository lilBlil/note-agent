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

## 项目结构

```text
langchain-note-agent/
├─ src/
│  └─ note_agent/
│     ├─ cli.py              # 命令行入口
│     ├─ web.py              # Streamlit 入口
│     ├─ graph.py            # LangGraph 工作流
│     ├─ service.py          # 同步/流式服务层
│     ├─ retrieval.py        # 统一参考信息检索
│     ├─ prompts.py          # LLM 提示词
│     ├─ storage.py          # 运行日志、缓存、中间文件
│     ├─ input_loader.py     # 文件和网页输入加载
│     ├─ schemas.py          # 请求、响应、状态、参考项和资产模型
│     ├─ config.py           # 模型配置
│     └─ utils/
│        ├─ asset_tools.py   # 资产解析、保存、注入
│        ├─ events.py        # 流式事件上下文
│        ├─ llm.py           # LLM 调用封装
│        ├─ markdown.py      # Markdown 清洗和保存
│        └─ text.py          # 通用文本处理
├─ demos/                    # 历史示例
├─ notes/                    # 生成的笔记和资产，默认不提交
├─ runs/                     # 运行日志，默认不提交
├─ .cache/                   # 检索缓存，默认不提交
├─ app.py                    # 兼容入口：streamlit run app.py
├─ main.py                   # 兼容入口：python main.py
├─ pyproject.toml            # 项目元数据和 uv 依赖配置
└─ uv.lock                   # uv 锁文件
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
```

## 运行

命令行：

```bash
uv run note-agent
```

Streamlit 界面：

```bash
uv run streamlit run app.py
```

兼容旧入口：

```bash
python main.py
streamlit run app.py
```

## 输出

- `notes/`：最终 Markdown 笔记
- `notes/intermediate/`：每轮中间版本
- `notes/assets/`：公式、代码、Mermaid、图表等生成资产
- `runs/{run_id}/`：运行摘要、事件日志和最终状态快照
- `.cache/references/`：参考信息检索缓存
