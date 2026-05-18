# Note Agent

一个基于 **LangGraph + LangChain + DeepSeek API** 构建的自动研究笔记 Agent。

项目目标不是简单整理文本，而是根据用户输入自动生成研究笔记，通过网络检索补充信息，并在每轮迭代中进行事实校验与内容修正，最终生成结构化 Markdown 笔记。

当前主版本为 **v3.1**，采用 **LangGraph 状态机架构**，支持动态笔记结构、网络检索、事实检验、多轮迭代与 Markdown 自动保存。

---

## v3.1 更新内容

v3.1 在 v3.0 的 LangGraph 状态机基础上，新增了事实检验与 Markdown 输出清洗能力。

### 新增功能

- 新增 `verify_note` 事实检验节点
- 在每轮网络检索后、笔记更新前，对当前笔记进行事实一致性检查
- 检查笔记内容是否与用户输入和网络搜索结果相符
- 根据事实检验结果修正错误内容
- 根据搜索结果补充遗漏信息
- 自动生成更贴合笔记主题的文件名
- 文件名格式调整为“主题标题_时间戳.md”
- 保存前自动清理 Markdown 代码块包裹
- 保存前自动去除模型生成的解释性开场白

---

## 功能特点

- 输入文本、关键词或研究主题
- 自动识别笔记类型
- 动态生成笔记结构
- 自动生成初版 Markdown 笔记
- 自动提取知识补充需求
- 自动生成网络检索问题
- 基于搜索结果进行事实检验
- 对笔记内容与用户输入、网络信息进行一致性检查
- 根据核验结果修正错误与补充遗漏
- 支持设置迭代次数
- 自动生成体现主题的文件名
- 自动清理 Markdown 代码块包裹与模型开场白
- 自动保存 Markdown 文件
- 支持长期知识积累与个人知识管理

---

## 技术栈

- Python
- LangChain
- LangGraph
- DeepSeek API
- DDGS Search
- python-dotenv
- Markdown

---

## 项目结构

```text
note-agent/
│
├─ .env
├─ .gitignore
├─ requirements.txt
├─ README.md
├─ main.py
│
├─ notes/
│
├─ note_agent/
│  ├─ __init__.py
│  ├─ state.py
│  ├─ prompts.py
│  ├─ tools.py
│  └─ graph.py
│
└─ demos/
   ├─ v1_main.py
   └─ v1_5_main.py
```

---

## 工作流程

```mermaid
flowchart TD
    A[用户输入文本 / 关键词] --> B[自动识别笔记类型]
    B --> C[动态生成笔记结构]
    C --> D[生成初版笔记]
    D --> E[提取需要补充的知识点]
    E --> F[生成搜索 Query]
    F --> G[网络检索]
    G --> H[事实检验]
    H --> I[根据检验结果与搜索结果更新笔记]
    I --> J{是否达到迭代次数}

    J -- 否 --> E
    J -- 是 --> K[生成最终 Markdown]
    K --> L[生成主题文件名]
    L --> M[保存本地笔记]
```

---

## 输入示例

输入：

```text
LangChain Agent
DeepSeek API
LangGraph workflow
Memory
RAG

END
```

设置迭代次数：

```text
2
```

Agent 自动执行：

```text
生成初版笔记
→ 自动提取知识缺口
→ 自动检索
→ 事实检验
→ 修正并更新笔记
→ 第二轮迭代
→ 生成最终 Markdown
→ 保存本地文件
```

输出：

```text
notes/
└── LangChain_Agent学习笔记_20260518_210012.md
```

---

## 安装

创建虚拟环境：

```bash
python -m venv .venv
```

Windows：

```bash
.\.venv\Scripts\activate
```

Git Bash：

```bash
source .venv/Scripts/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

配置 `.env`：

```env
DEEPSEEK_API_KEY=your_api_key
```

运行：

```bash
python main.py
```

---

## 版本说明

### v3.1

当前主版本。

新增：

- 增加 `verify_note` 事实校验节点
- 在每轮补充前检查笔记内容是否与用户输入和网络信息一致
- 根据核验结果修正错误内容
- 根据搜索结果补充遗漏信息
- 自动生成更符合笔记主题的文件名
- 保存前清理 Markdown 代码块包裹与模型开场白

### v3.0

- 引入 LangGraph 状态机架构
- 自动识别笔记类型
- 动态生成笔记结构
- 自动生成初版笔记
- 自动提取检索问题
- 网络检索补充信息
- 支持多轮迭代
- 自动保存 Markdown

---

## Roadmap

### v3.2

- 增加节点流式输出
- 增加运行日志
- 增加可视化调试

### v4

- 本地 RAG
- 向量数据库
- PDF 输入
- 网页导入
- 长期知识库

### v5

- 多 Agent 协作
- 自动学习规划
- 知识图谱构建

---

## Historical Demo Versions

项目早期版本保留为 Demo，用于展示功能演化过程。

---

### Demo v1

基础笔记整理 Agent。

功能：

- 输入原始文本
- 自动生成标题
- 提取核心知识点
- 输出 Markdown
- 自动保存本地笔记

流程：

```text
输入文本
→ 内容分析
→ Markdown 生成
→ 保存文件
```

---

### Demo v1.5

在 v1 基础上增加：

- 支持 `.txt`
- 支持 `.md`
- 文件导入
- 流式输出
- 自动文件命名
- 输入方式选择
- 输入合法性检查

流程：

```text
手动输入 / 文件导入
→ 内容整理
→ 流式生成
→ 保存 Markdown
```

---

## License

MIT