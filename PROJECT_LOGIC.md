# Note Agent 项目逻辑详解（面试版）

> 一份用于面试复盘的完整文档：整体逻辑、全部函数清单、涉及的 Agent 技术。
> 技术栈：**LangGraph（编排）+ LangChain（模型/工具抽象）+ Pydantic（数据校验）+ Streamlit（界面）**。

---

## 一、项目一句话概括

输入一段主题文字 / 一个 URL / 一个文本文件，Agent 自动完成：
**判类型定大纲 → 生成初稿 → 检索参考资料 → 事实核验并增量修正（可多轮）→ 定稿 → 生成多模态资产（公式/代码/图表/流程图）→ 落盘 → 可选发布到 Notion**，
最终产出一篇经过检索核验的高质量 Markdown 研究笔记。

核心亮点（面试可主动讲）：
1. **两套 Agent 架构并存**：固定工作流图（workflow）+ ReAct 自主决策图（agent），一个 `mode` 参数切换。
2. **PATCH 增量修改**：核验修正时让 LLM 输出结构化补丁而非重写全文，省 token、降风险。
3. **统一检索层**：8 个搜索后端归一化为统一模型，线程池并发 + SHA1 缓存。
4. **全链路可观测**：基于 ContextVar 的事件流 + token 用量追踪，支持流式和优雅中断。

---

## 二、目录结构与模块职责

```text
src/note_agent/
├─ cli.py                  # 命令行交互入口
├─ web.py                  # Streamlit 界面入口
├─ utils.py                # JSON 提取、模型序列化等通用工具
├─ config/
│  ├─ settings.py          # 6 家模型 Provider 配置 + get_model()
│  └─ llm.py               # ask_llm() 统一调用封装（流式/非流式 + token 记账）
├─ domain/
│  ├─ models.py            # 领域模型：ReferenceItem / ReferenceQuery / NoteResearchState 等
│  └─ api.py               # I/O schema：NoteAgentRequest / NoteAgentResponse
├─ agent/
│  ├─ graph.py             # 【架构A】固定工作流图（已提交主版本）
│  ├─ graph_react.py       # 【架构B】ReAct 自主决策图（新版）
│  ├─ tools.py             # ReAct 用的 10 个 @tool
│  ├─ runner.py            # 架构A 的服务层（同步/流式/事件流）
│  ├─ runner_react.py      # 架构B 的服务层
│  ├─ runner_unified.py    # 用 mode 参数统一切换两套架构
│  ├─ prompts.py           # 全部提示词模板
│  └─ tracker.py           # 基于 ContextVar 的 token 用量追踪
├─ retrieval/
│  ├─ sources.py           # 8 个搜索后端 + 按类型路由
│  ├─ retriever.py         # 检索编排、去重、格式化
│  └─ cache.py             # SHA1-keyed 检索缓存
├─ io/
│  ├─ events.py            # 基于 ContextVar 的流式事件系统
│  ├─ input_loader.py      # 文本/文件/网页输入加载与合并
│  ├─ storage.py           # 运行记录、状态快照、中间笔记落盘
│  └─ text.py              # 文件名清洗、Markdown 围栏剥离、落盘
├─ assets/
│  ├─ types.py             # 资产 Pydantic 模型
│  └─ tools.py             # 资产解析/校验/保存/注入 Markdown
└─ notion/
   ├─ client.py            # Notion SDK 封装
   ├─ converter.py         # Markdown → Notion blocks
   └─ publish.py           # 发布编排（分批处理 100 block 限制）
```

分层思想：**入口层(cli/web) → 服务层(runner) → 编排层(graph) → 能力层(retrieval/assets/notion) → 基础层(io/config/domain/utils)**，依赖单向向下。

---

## 三、核心数据模型

### `NoteResearchState`（TypedDict，贯穿整张图的状态）
LangGraph 的状态容器。为什么用 TypedDict 而非 Pydantic：LangGraph 的状态更新语义是"节点返回 dict → 局部合并"，TypedDict 轻量且天然契合 partial update。

关键字段分组：
- **消息**：`messages: Annotated[Sequence[BaseMessage], add_messages]` —— ReAct 需要，`add_messages` 是 LangGraph 的 reducer，自动追加合并消息而非覆盖。
- **运行元数据**：`run_id / raw_input / max_iterations / iteration_count`
- **配置**：`llm_provider / search_api / enable_assets / enable_notion`
- **笔记结构**：`note_type / note_outline / current_note`
- **检索状态**：`reference_queries / used_reference_queries / reference_results / evidence_items / sources`
- **核验**：`verification_report`
- **最终产出**：`final_note / note_title / saved_path / notion_url / intermediate_paths`
- **资产**：`asset_plan / generated_assets / asset_paths`

### 其他模型
| 模型 | 位置 | 作用 |
|------|------|------|
| `ReferenceQuery` | domain/models | 一条统一检索请求：`query / source_types / reason` |
| `ReferenceItem` | domain/models | 统一检索结果，兼容网页/论文/书籍/学术（title/abstract/authors/doi/citation_count…）|
| `RunRecord` | domain/models | 单次运行的摘要记录（status/provider/saved_path…）|
| `NoteAgentRequest` | domain/api | 入参 schema（Pydantic，带校验 `max_iterations>=0`）|
| `NoteAgentResponse` | domain/api | 出参 schema |
| `AssetPlanItem / FormulaBlock / CodeBlock / MermaidBlock / ChartBlock / GeneratedAssets` | assets/types | 资产的 Pydantic 模型 |

类型字面量：`ReferenceType`(web/paper/book/academic/other)、`LLMProvider`(6家)、`SearchAPI`(4家)、`AssetType`(formula/code/mermaid/chart)。

---

## 四、两套 Agent 架构（面试核心）

### 架构 A：固定工作流图 `graph.py`（Workflow，主版本）

人工编排的状态机，节点和边写死，**决策权在代码里，LLM 只负责节点内的生成**。

```
START
 → infer_type_and_outline        判笔记类型 + 生成大纲
 → generate_initial_note         生成初稿
 → [route_after_initial_note]    max_iterations<=0 ? finalize : continue
 → generate_reference_queries    分析信息缺口 → 生成检索词（去重、限4条）
 → retrieve_references           线程池并发检索
 → verify_and_refine             核验 + 输出 PATCH → 应用补丁，iteration+1
 → [route_iteration]             iteration>=max ? finalize : 回到 generate_reference_queries（循环）
 → finalize_note                 合并去重、统一术语、加 Sources 章节
 → [route_after_finalize]        enable_assets ? assets : save
 → plan_note_assets → generate_note_assets → assemble_assets_into_note   （资产分支）
 → save_markdown                 生成标题 + 落盘
 → [route_after_save]            enable_notion ? publish_notion : END
 → publish_notion → END
```

流程控制靠 `add_conditional_edges` + 路由函数（`route_after_initial_note` / `route_iteration` / `route_after_finalize` / `route_after_save`）。

**特点**：确定性强、可预测、省 token、易调试；缺点是不灵活，本质是 **LLM 工作流** 而非严格意义的 agent。

### 架构 B：ReAct 图 `graph_react.py` + `tools.py`（Agent，新版）

把 A 的每个节点改造成 LangChain `@tool`（共 10 个），用经典两节点 ReAct 循环，**决策权交给 LLM**。

```
START → agent ⇄ tools
        │
        ├─ agent 节点：llm.bind_tools(ALL_TOOLS)，模型自己决定下一步调哪个工具
        └─ should_continue 路由：有 tool_calls → tools；无 → END
```

关键工程细节：
1. **`InjectedToolArg`**：`llm_provider / run_id / search_api` 这类系统参数不该让 LLM 填，标记为注入参数，在 `create_tool_node` 里手动塞进每个 tool call 再执行。
2. **状态回写**：`ToolNode` 执行后返回 `ToolMessage`，代码手动解析 JSON，把工具返回值映射回 state（如 `refined_note → current_note` 且 `iteration_count+1`）。
3. **上下文提示**：`create_agent_node` 每轮根据当前 state 拼一段"当前进度"提示（如"初稿已生成，当前迭代 1/2"），引导模型决策。
4. **兜底纠偏**：若模型该发 Notion 却没调工具，代码强行构造 tool_call 补上——处理 ReAct 不可控性的典型补丁。

**特点**：灵活、模型自主规划；缺点是要处理"模型漏步骤/多余调用/不按格式"的鲁棒性问题，多花推理 token。

### 两者取舍（面试话术）
> 笔记生成流程本身相对固定，所以**主版本用固定图**（稳定、可控、成本低）；ReAct 是探索版，适合开放式、步骤不定的任务。生产上常见做法是"固定骨架 + 局部让 LLM 决策"的混合。`runner_unified.py` 用 `mode` 参数在两者间切换。

---

## 五、全部函数清单（按模块）

### `agent/graph.py`（固定工作流图）
| 函数 | 作用 |
|------|------|
| `_dedupe_urls(urls)` | URL 去重（保序）|
| `infer_type_and_outline(state)` | 节点：LLM 判笔记类型 + 生成大纲，JSON 多层容错解析，失败给默认大纲 |
| `generate_initial_note(state)` | 节点：按大纲生成初稿，存中间版本，初始化各状态字段 |
| `route_after_initial_note(state)` | 路由：`max_iterations<=0` → finalize，否则 continue |
| `generate_reference_queries(state)` | 节点：分析信息缺口生成检索词，`normalize_query` 去重、过滤 source_types、限 4 条 |
| `retrieve_references_node(state)` | 节点：`ThreadPoolExecutor` 并发检索多个 query，`Lock` 保护共享列表，累积证据与来源 |
| `verify_and_refine(state)` | 节点：LLM 核验并输出 PATCH，调 `_apply_patches` 应用，iteration+1，存中间版本 |
| `_apply_patches(current_note, patch_text)` | 解析 `### PATCH/PATCH_NEW/NO_CHANGES` 补丁块，按标题层级替换/插入章节 |
| `route_iteration(state)` | 路由：`iteration>=max` → finalize，否则 continue（构成检索-修正循环）|
| `finalize_note(state)` | 节点：合并去重、删 `[待验证]`、统一术语、加 Sources 章节 |
| `route_after_finalize(state)` | 路由：`enable_assets` → assets，否则 save |
| `plan_note_assets(state)` | 节点：规划资产，`parse_asset_plan` + `filter_asset_plan` 过滤冗余 |
| `generate_note_assets(state)` | 节点：LLM 生成资产内容，解析/校验/保存文件 |
| `assemble_assets_into_note(state)` | 节点：把资产按 `insert_after_heading` 注入 Markdown |
| `save_markdown_node(state)` | 节点：LLM 生成标题 + 落盘，写 saved 事件 |
| `publish_notion_node(state)` | 节点：发布 Notion，失败 `fatal=False` 不中断 |
| `route_after_save(state)` | 路由：`enable_notion` → publish_notion，否则 END |
| `build_graph()` | 构建并 compile 整张 StateGraph |
| `get_graph()` | 单例获取图 |

### `agent/graph_react.py`（ReAct 图）
| 函数 | 作用 |
|------|------|
| `create_agent_node(state)` | agent 推理节点：绑定工具、拼当前进度提示、调 LLM 决策、无 tool_call 时兜底 |
| `create_tool_node(state)` | 注入系统参数 → `ToolNode` 执行 → 解析 `ToolMessage` 回写 state |
| `should_continue(state)` | 路由：有 tool_calls → tools，否则判断是否真完成 → END |
| `build_react_graph()` | 构建 agent⇄tools 两节点循环图 |
| `get_react_graph()` | 获取图（每次 rebuild 以拾取改动）|

### `agent/tools.py`（10 个 ReAct 工具 + 辅助）
| 工具（`@tool`）| 对应固定图节点 |
|------|------|
| `infer_note_structure` | infer_type_and_outline |
| `generate_note_draft` | generate_initial_note |
| `search_references` | generate_reference_queries + retrieve_references（合并）|
| `refine_note_with_references` | verify_and_refine |
| `finalize_note_content` | finalize_note |
| `plan_note_assets` | plan_note_assets |
| `generate_note_assets` | generate_note_assets |
| `assemble_final_note` | assemble_assets_into_note |
| `save_final_note` | save_markdown |
| `publish_note_to_notion` | publish_notion |

辅助：`_dedupe_urls`、`_apply_patches`（与 graph.py 同逻辑）、`ALL_TOOLS`（工具列表导出）。

### `agent/runner.py`（固定图服务层）
| 函数 | 作用 |
|------|------|
| `build_initial_state(request, run_id)` | 从请求构建初始 state dict |
| `build_response(result)` | 从终态构建 `NoteAgentResponse` |
| `run_note_agent(request)` | 同步阻塞运行：`graph.invoke`，注册事件 handler，存快照，收尾 |
| `stream_note_agent(request)` | 流式：`graph.stream(stream_mode="updates")`，逐节点 yield |
| `stream_note_agent_events(request)` | 事件流：图跑在 daemon 线程，主线程用 `Queue` 拉事件 + `stop` Event 优雅中断 |

### `agent/runner_react.py`（ReAct 服务层）
`build_initial_state_react`（多一条初始 `HumanMessage`）、`build_response`、`run_note_agent_react`、`stream_note_agent_react`、`stream_note_agent_events_react` —— 与 runner.py 结构一致，只是换成 `get_react_graph()`。

### `agent/runner_unified.py`（统一入口）
`run_note_agent(request, mode)` / `stream_note_agent(request, mode)` / `stream_note_agent_events(request, mode)` —— 按 `mode="fixed"|"react"` 分派到对应 runner。

### `agent/tracker.py`（token 追踪，ContextVar）
| 函数 | 作用 |
|------|------|
| `reset_usage()` | 清空当前上下文的用量记录 |
| `record_usage(node_name, step_label, provider, input_tokens, output_tokens)` | 记一次调用用量 |
| `summarize_usage()` | 汇总总量 + 按节点聚合 |

### `agent/prompts.py`（提示词模板）
`react_system_prompt`（ReAct 系统提示，含工具列表/流程建议/决策原则）、`_extract_headings`（抽标题供定位）、`infer_type_and_outline_prompt`、`generate_initial_note_prompt`、`generate_reference_queries_prompt`、`verify_and_refine_prompt`（输出 PATCH）、`verify_note_prompt` + `refine_note_prompt`（旧版两段式核验，现由 verify_and_refine 合并）、`finalize_note_prompt`、`plan_assets_prompt`、`generate_assets_prompt`、`generate_title_prompt`。

### `config/settings.py` & `config/llm.py`
| 函数 | 作用 |
|------|------|
| `get_model(provider, for_tools)` | 按 `MODEL_CONFIGS` 建 LLM 实例（DeepSeek 用 `ChatDeepSeek`，其余走 `ChatOpenAI` + base_url）；`for_tools=True` 时去掉 `stream_options`（工具调用不能带）|
| `get_llm_for_provider(provider)` | 供工具绑定用的模型 |
| `_extract_usage(response)` | 从 AIMessage/chunk 抽 (input, output) token，多字段兜底 |
| `ask_llm(prompt, provider, stream)` | **统一 LLM 调用封装**：流式时逐 chunk `emit_token` + 累积；非流式直接 invoke；两种都 `record_usage` 记账 |

### `retrieval/sources.py`（8 个后端 + 路由）
- 工具：`_clean_text`、`dedupe_references`（DOI>URL>标题+年份 为 key 去重）、`_cached`（缓存包装）
- Web 后端：`retrieve_duckduckgo` / `retrieve_tavily` / `retrieve_perplexity` / `retrieve_searxng`
- 论文/学术/书籍后端：`retrieve_semantic_scholar` / `retrieve_arxiv`（解析 XML）/ `retrieve_google_books` / `retrieve_open_library` / `retrieve_openalex`
- 路由：`retrieve_by_source_type(query, source_type, web_backend, max_results)` —— 按 web/paper/book/academic 分派，多后端合并去重

### `retrieval/retriever.py`（编排）
`retrieve_references(reference_query, web_backend, max_results_per_type)`（按 source_types 逐个检索合并去重）、`format_references_for_prompt(results)`（格式化成 `[R1]...[R2]` 文本块喂 LLM）、`collect_reference_urls(results)`（抽 url+pdf_url 去重）。

### `retrieval/cache.py`（SHA1 缓存）
`_cache_key(*parts)`（SHA1 哈希）、`load_reference_cache(...)`、`save_reference_cache(...)` —— 按 (source_name, query, max_results) 缓存到 `.cache/references/*.json`。

### `io/events.py`（流式事件系统，ContextVar）
`set_event_handler` / `reset_event_handler` / `has_event_handler` / `emit_event(type, **payload)` / `emit_node_start(node, label)`（设当前节点+发事件）/ `emit_token(text)`（发流式 token）。用 ContextVar 是为了**线程隔离**（图跑在后台线程）。

### `io/input_loader.py`（输入加载）
`read_text_file(path)`、`read_uploaded_text_file(filename, content)`（Streamlit 上传）、`is_valid_url(url)`、`fetch_webpage_text(url)`（requests+BeautifulSoup 抽正文，去 script/style/nav）、`build_combined_input(manual, files, webpages)`（合并三类输入为 Agent 输入）。

### `io/storage.py`（持久化）
`write_json` / `read_json` / `get_run_dir` / `get_assets_dir` / `start_run`（写 run.json 状态 running）/ `finish_run`（更新 success/error）/ `append_event`（追加 events.jsonl）/ `summarize_state`（长文本截断到 1000 字做快照）/ `save_state_snapshot` / `save_intermediate_note`（存每轮中间版本）。

### `io/text.py`（文本工具）
`normalize_query`（小写去空白，用于去重）、`clean_filename`（清非法字符，限 40 字）、`strip_markdown_fence`（剥 ```markdown 围栏 + 从 `# ` 标题开始截）、`save_markdown(title, content)`（生成带时间戳文件名落盘 notes/）。

### `assets/tools.py`（资产处理）
- 解析/校验：`parse_asset_plan`、`filter_asset_plan`（去冗余：笔记已有代码/公式/图则跳过）、`parse_generated_assets`、`validate_generated_assets`（删空/低质：公式要有 latex、图要有连线、chart 要 x/y 等长）
- 保存：`_safe_name`、`_relative_to_project`、`save_formula_assets`（写 index.json）、`save_code_assets`（按语言选扩展名）、`save_mermaid_assets`（.mmd）、`save_chart_specs`（.json）、`render_chart_images`（matplotlib 出 png，无 matplotlib 则跳过）、`save_generated_assets`（统一调度）
- Markdown 生成：`formula_to_markdown` / `code_to_markdown` / `mermaid_to_markdown` / `chart_to_markdown`（有图用图，否则列数据）、`build_asset_markdown_items`（生成 (标题, md) 列表）、`inject_assets_into_markdown`（按标题模糊匹配插入，剩余的追加到"自动生成资产"章节）

### `notion/`（发布）
- `client.py`：`NotionClient`（`create_page` / `append_blocks` / `search_pages`，懒加载 notion-client SDK）
- `converter.py`：`markdown_to_notion_blocks` + 一系列内联解析（`_parse_inline_rich_text` 处理 **粗体**/*斜体*/`代码`/~~删除~~/[链接]/$公式$，支持 4 种 LaTeX 分隔符）、标题/代码块/列表/表格/分割线解析
- `publish.py`：`publish_note(markdown, title, ...)` —— 转 blocks 后按 Notion **100 block/请求** 限制分批 create+append

### `utils.py`（通用）
`strip_code_fence`、`extract_json_object`（正则抓 `{...}` 容错解析）、`extract_json_array_or_object`（先试数组再试对象）、`to_plain_data`（递归把 Pydantic/嵌套结构转纯 dict/list，用于 JSON 序列化）。

### `cli.py` / `web.py`（入口）
- `cli.py`：`collect_manual_input` / `collect_file_inputs` / `collect_url_inputs` / `select_provider` / `select_search_api` / `select_agent_mode`（选 fixed/react）/ `main`
- `web.py`：Streamlit 界面，消费事件流实时展示生成过程

---

## 六、涉及的 Agent 技术（面试重点）

### 1. LangGraph 状态图编排（StateGraph）
- **节点(node)**：一个函数，接收 state 返回局部更新 dict。
- **边(edge)**：普通边 `add_edge` + 条件边 `add_conditional_edges`（配路由函数实现分支/循环）。
- **状态与 reducer**：`Annotated[..., add_messages]` 是 reducer，控制字段合并策略（消息追加而非覆盖）。
- **编译与执行**：`compile()` 得可执行图，支持 `invoke`（同步）和 `stream(stream_mode="updates")`（逐节点流式，天然是检查点，可中断）。

### 2. ReAct 范式（Reasoning + Acting）
- 经典 `agent ⇄ tools` 循环：模型**推理**下一步 → **行动**（调工具）→ 观察结果 → 再推理，直到判定完成。
- LangGraph 组件：`llm.bind_tools()` 绑定工具、`ToolNode` 执行工具调用、`should_continue` 做循环终止判断。

### 3. Tool / Function Calling
- `@tool` 装饰器把普通函数变成 LLM 可调用工具，docstring + 类型注解自动生成 schema。
- **`InjectedToolArg`**：区分"模型该填的业务参数"和"运行时注入的系统参数"（run_id/provider），是工具设计的关键实践。

### 4. Workflow vs Agent 的取舍（业界热点）
- 固定图 = **workflow**（编排写死，可控省钱）；ReAct = **agent**（模型自主决策，灵活但不可控）。
- 本项目两套都实现，能讲清取舍是加分项（对应 Anthropic "Building Effective Agents" 里 workflow vs agent 的区分）。

### 5. 迭代式自我修正（Reflection / Self-Refine）
- `verify_and_refine` 循环：核验当前笔记 → 找问题 → 生成修正补丁 → 应用，最多 `max_iterations` 轮。是 Reflection 模式的落地。

### 6. RAG / 检索增强
- 生成初稿后**主动分析信息缺口**生成检索词（agentic RAG，而非一次性检索），检索结果作为证据喂给核验修正环节，要求句尾标 `[R编号]` 溯源。

### 7. 结构化输出与容错解析
- 提示词要求严格 JSON / PATCH 格式，代码侧多层兜底解析（`extract_json_object` 去围栏→正则抓→默认值）。
- **PATCH 增量修改**：让 LLM 只输出改动章节的补丁而非重写全文（省 token、降"改坏"风险、可追溯），代价是正则解析脆弱。

### 8. 多模型抽象与并发
- 6 家 Provider 统一到 `get_model`，LangChain 的 `ChatOpenAI`/`ChatDeepSeek` 统一接口。
- 检索用 `ThreadPoolExecutor` 并发（I/O 密集，GIL 不影响）+ Lock 保护共享状态。

### 9. 可观测性与流式（Observability & Streaming）
- 基于 **ContextVar** 的事件系统 + token 追踪，实现线程隔离；`emit_token` 支持 UI 实时流式；
- 图跑在 daemon 线程，主线程 `Queue` 拉事件 + `stop` Event 做**优雅中断**。
- 全程留痕：run.json（运行摘要）、events.jsonl（事件日志）、中间版本、状态快照、检索缓存。

---

## 七、面试高频追问 & 参考答法

**Q：为什么用 LangGraph 而不是纯 LangChain 或自己写循环？**
A：这个流程有循环（多轮检索修正）、有分支（是否检索/是否生成资产/是否发 Notion）、有共享状态。LangGraph 提供状态管理(reducer)、显式条件控制流、节点级流式与检查点，比 chain 或裸循环更清晰、更好调试和中断。

**Q：固定图和 ReAct 上生产选哪个？**
A：看场景。要稳定可控成本低选固定图；开放式步骤不定选 ReAct。本项目笔记流程相对固定，主版本是固定图，ReAct 是探索。生产常用"固定骨架 + 局部 LLM 决策"的混合。

**Q：怎么保证 LLM 输出可解析？**
A：多层兜底——去代码围栏 → 正则抓 JSON → 默认值；PATCH 用正则 + 模糊标题匹配 + NO_CHANGES 短路。诚实讲仍不够健壮，更好的是用 structured output / function calling 强约束 schema。

**Q：PATCH 机制的价值和缺点？**
A：价值是省 token、降低重写改坏内容的风险、修改可追溯；缺点是正则解析脆弱、标题模糊匹配可能误伤，LLM 不按格式就丢改动。

**Q：并发与线程安全怎么处理？**
A：检索用线程池 + Lock 保护共享列表；事件与 token 追踪用 ContextVar 做线程隔离，避免后台图线程与主线程串数据。

**Q：这个项目的"agent 性"体现在哪？**
A：固定图更像 LLM workflow（决策硬编码）；ReAct 版才是让模型自主规划工具调用的 agent。主动点出这个区分（workflow vs agent）本身是加分项。

**Q：成本怎么控制？**
A：`max_iterations` 限制核验轮数、检索缓存避免重复请求、PATCH 减少输出 token、`filter_asset_plan` 宁缺毋滥、token 追踪按节点定位成本大头。
