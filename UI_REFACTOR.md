# UI 重构总结

**日期：** 2026-07-15  
**分支：** feature/main  
**目标：** 打造 ChatGPT / Notion / Deep Research 风格的专业 AI Research Agent 工作空间

---

## 架构变更

### 旧结构（单文件 344 行）
```
src/note_agent/web.py  # 全部 UI 逻辑
```

### 新结构（模块化包）
```
src/note_agent/ui/
  __init__.py          # 包声明
  theme.py             # 深色主题 + CSS（变量、容器、输入框、状态卡片）
  state.py             # RunView 状态管理 + 固定流程 stage 映射 + 事件 reducer
  history.py           # 历史记录加载（runs/ 读取 + 快照重建）
  render.py            # 纯渲染函数（任务卡、状态面板、输出画布、详情折叠）
  sidebar.py           # 侧边栏（历史列表 + 全部设置）
  runner_ui.py         # 事件流消费 + RunView 更新 + 重绘循环
  app.py               # 主编排器（布局脚手架 + 输入处理 + 运行循环）
src/note_agent/web.py  # 瘦入口（from ui.app import main）
```

**原则：** UI 层只读事件流，从不修改 LangGraph 工作流（agent/、runner*、graph*）。

---

## 核心交互流程

### 用户提交 → 执行 → 完成（2 次 rerun）

1. **提交：** 用户在 `st.chat_input` 输入/上传 → `_handle_submission()` 提取文本、读取文件字节、解析 URL → 构建 `pending` RunView → 存入 `session_state` → **`st.rerun()`**

2. **执行：** 下次运行渲染脚手架（任务头、状态/输出占位符、输入框全部先就位） → 检测到 `status=="pending"` → 切换为 `running` → `execute_stream()` **阻塞**消费事件流、折叠到 view、实时重绘占位符 → 完成后标记 `done` 或 `error`（无 rerun，占位符已显示最终态）

3. **后续 rerun：** 从 `session_state` 读取 view，直接重绘完成状态（任务头 + 状态面板 + 输出画布 + 详情折叠）

### 历史记录

- 左侧 Sidebar 列出 `runs/` 下全部任务（状态点 + 预览文本）
- 点击 → `history.load_view()` 从 `run.json` + `final_state.json` + `saved_path` 重建 `done` view（`readonly=True`）→ `st.rerun()` → 渲染只读快照

---

## 布局（单屏适配）

```
┌─────────────────┬────────────────────────────────────────────┐
│   Sidebar       │          主工作区                          │
│  （可收起）     │                                            │
│                 │  ┌────────────────────────────────────┐   │
│  历史记录       │  │ 用户任务卡片（文本/文件/URL）      │   │
│   🟢 最近1      │  └────────────────────────────────────┘   │
│   🔴 任务2      │                                            │
│   ...           │  ┌─────────────┬──────────────────────┐   │
│                 │  │ Agent Status│   生成内容 Output   │   │
│  ─────────      │  │  (500px h)  │     (500px h)        │   │
│                 │  │  独立滚动   │     独立滚动         │   │
│  设置           │  │             │                      │   │
│   LLM 模型      │  │  固定流程： │  Markdown + 图表     │   │
│   Search        │  │  ✓ 任务分析 │  实时流式显示       │   │
│   Iteration     │  │  ● 生成初稿 │                      │   │
│   Notion 发布   │  │  ○ 查询生成 │  ReAct 完成后才呈现 │   │
│   高级参数      │  │  ...        │                      │   │
│                 │  │             │                      │   │
│                 │  │  ReAct 自主：│                      │   │
│                 │  │  Iteration 2│                      │   │
│                 │  │  Think: xxx │                      │   │
│                 │  │  Act: 检索  │                      │   │
│                 │  │  Observe: …│                      │   │
│                 │  └─────────────┴──────────────────────┘   │
│                 │                                            │
│                 │  ▼ 详细信息（折叠）                        │
│                 │    Sources | Token Usage | Execution Trace │
│                 │                                            │
│                 │  ───────────────────────────────────────   │
│                 │  [ 研究模式：固定流程 ◉  ReAct 自主 ○ ]   │
│                 │  ┌────────────────────────────────────┐   │
│                 │  │ ＋  输入主题、粘贴文本…         ↑ │   │  ← st.chat_input
│                 │  └────────────────────────────────────┘   │    (固定底部)
└─────────────────┴────────────────────────────────────────────┘
```

### 关键技术

- **固定高度容器 + 独立滚动：** `st.container(height=500)` 包裹状态和输出 → 页面不会无限向下延伸
- **ChatGPT 风格输入：** `st.chat_input(accept_file="multiple", file_type=["txt","md"])` 原生附件 + 发送按钮，深色圆角 CSS 定制
- **研究模式切换：** `st.segmented_control` 放在输入框上方，视觉关联
- **响应式列布局：** `st.columns([1, 3])` → 状态 25% | 输出 75%

---

## 视觉主题

**配色（低饱和 + 中性灰）：**
- 背景：`#111214` | 面板：`#191a1d` `#1e2024`
- 边框：`#2a2c31` | 文本：`#e6e7ea` | 弱化：`#8b8e96`
- 强调：`#6b8afd`（仅研究模式 active）
- 状态色：成功 `#3fb779` | 运行 `#e0a44b` | 错误 `#e0605e`

**样式约束：**
- 不用高饱和色、大面积渐变、彩色 Dashboard 风
- 圆角 12px（容器）/ 22px（输入框）
- 留白充足，层级清晰
- 状态颜色仅用于指示，不作装饰

---

## RunView 状态机

```python
{
  "status": "pending" | "running" | "done" | "error",
  "mode": "fixed" | "react",
  "task": {"text": str, "files": [name], "urls": [url]},  # 用户可见
  "params": {"manual_text": str, "file_texts": [(n,bytes)], "urls": []},  # 执行用
  "settings": {"llm", "search", "iters", "assets", "notion"},
  
  # 固定流程
  "nodes": [{"node": str, "label": str, "status": "pending|running|done"}],
  "iteration": int,  # verify_and_refine 计数
  
  # ReAct 自主
  "react": [{"think": str, "act": str, "observe": [str]}],
  "iteration": int,  # agent 节点计数
  
  "live_text": str,  # 流式 token 累积（固定模式）
  "final_note": str, "sources": [str], "usage": {},
  "trace": [str],  # 执行日志
  "run_id": str, "run_log_dir": str, "error": str,
  "readonly": bool,  # 历史记录标志
}
```

### 事件折叠规则

| 事件类型 | 固定流程 | ReAct 自主 |
|---------|---------|-----------|
| `node_start` | 标记 stage 为 running，前一个 done；`verify_and_refine` → iter+1 | `agent` → 新 step（think），`tools` → 设置 act |
| `token` | 累积到 `live_text`（实时显示） | _（agent 节点不流式，忽略）_ |
| `info` / `warning` | 追加到 trace | 追加到当前 step 的 observe + trace |
| `done` | 提取 `final_note` / `sources` / `usage`，标记所有 nodes 为 done | 同左 |
| `error` | 记录错误，标记 `status="error"` | 同左 |

---

## 固定流程 Pipeline 映射

```python
PIPELINE = [
    ("infer_type_and_outline", "任务分析"),
    ("generate_initial_note", "生成初稿"),
    ("generate_reference_queries", "查询生成"),
    ("retrieve_references", "信息检索"),
    ("verify_and_refine", "内容验证"),  # ← 每次 node_start 增加 iteration
    ("finalize_note", "生成笔记"),
]
# + 可选 asset 阶段（规划/生成/组装/保存/发布）
```

**渲染：** 按顺序显示 ✓完成 / ●运行中 / ○待处理，动态追加未知节点。

---

## 测试覆盖

- ✅ **编译：** 全模块 `py_compile` 通过
- ✅ **导入链：** `web.py` → `ui.app.main` 无断链
- ✅ **URL 分离：** 从文本提取 URL，剩余作为 topic
- ✅ **历史加载：** 读取 `run.json` + `final_state.json` + `saved_path` 重建 view
- ✅ **事件 reducer：** 固定/ReAct 模式 `_fold_event()` 正确更新 iteration / nodes / react steps
- ✅ **Streamlit AppTest：** 空状态渲染、模式切换、已完成任务渲染（15 markdown、3 tabs、2 expanders）
- ✅ **提交流程：** `_handle_submission()` 构建 pending view，触发 rerun，URLs/文件/文本正确拆分

---

## 向后兼容

- **入口点保持不变：** `note-agent-ui` 命令、`streamlit run app.py`、`from note_agent.web import main` 全部仍可用
- **后端零改动：** `agent/`、`runner*`、`graph*` 完全未触及，只消费事件流
- **配置保留：** `.streamlit/config.toml` 继续生效（追加主题变量）

---

## 已知限制 & 后续

- **历史记录：** 当前只读快照，不支持重新运行或编辑；可扩展"基于此任务继续研究"
- **ReAct 可视化：** Agent 节点不流式，最终笔记等 `done` 后才显示；可考虑显示工具调用的中间结果
- **响应式布局：** 窄屏（<1024px）列比例可能不理想，可增加断点判断
- **Assets 预览：** 生成的资产路径列在详情中，未内嵌预览（Mermaid 除外）

---

## 使用方式

```bash
# 开发模式
uv run streamlit run app.py

# 生产模式
uv run note-agent-ui
```

打开浏览器 → `http://localhost:8501`

**首次使用：**
1. 左侧设置 LLM / Search / Iteration
2. 底部输入框粘贴主题或 URL，或点击 ＋ 上传 `.txt` / `.md`
3. 选择**固定流程**（预定义管道）或 **ReAct 自主**（Agent 决策）
4. 点击发送 ↑ 或回车
5. 左侧 25% 面板显示 Agent 执行状态，右侧 75% 实时呈现生成笔记
6. 完成后展开**详细信息**查看来源、Token 用量、执行日志
7. 历史任务自动保存在左侧边栏，点击可重新查看

---

**设计目标达成：** ✅ 单屏无滚动、ChatGPT 级输入体验、清晰状态展示、专业深色主题、模块化可维护架构。
