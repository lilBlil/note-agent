def infer_note_type_prompt(raw_input: str) -> str:
    return f"""
请判断下面内容最适合整理成哪类笔记。

可选类型包括但不限于：
- 学习笔记
- 项目学习笔记
- 论文阅读笔记
- GitHub 项目分析笔记
- 面试准备笔记
- 技术方案笔记
- 研究综述笔记

用户输入：
{raw_input}

只输出笔记类型，不要解释。
"""


def generate_outline_prompt(raw_input: str, note_type: str) -> str:
    return f"""
你是一个知识管理 Agent。

请根据用户输入和笔记类型，生成一个灵活的 Markdown 笔记结构。

用户输入：
{raw_input}

笔记类型：
{note_type}

要求：
1. 不要使用固定模板
2. 根据主题自动设计 4-7 个章节
3. 每个章节应服务于该主题本身
4. 输出 JSON 数组
5. 每个元素包含 title 和 purpose
6. 只输出 JSON，不要输出解释

示例格式：
[
  {{"title": "xxx", "purpose": "xxx"}},
  {{"title": "xxx", "purpose": "xxx"}}
]
"""


def generate_initial_note_prompt(raw_input: str, note_type: str, outline: str) -> str:
    return f"""
请基于用户输入生成第一版 Markdown 笔记。

用户输入：
{raw_input}

笔记类型：
{note_type}

笔记结构：
{outline}

要求：
1. 按该结构生成 Markdown
2. 只使用用户输入中已有的信息
3. 不要编造事实
4. 内容具体，不要空泛
5. 不要使用 ```markdown 代码块包裹
6. 第一行必须是一级标题，以 # 开头
"""


def generate_reference_queries_prompt(current_note: str, used_queries: list[str]) -> str:
    used_text = "\n".join(f"- {q}" for q in used_queries) if used_queries else "暂无"

    return f"""
请阅读当前笔记，判断还缺少哪些参考信息，并生成统一检索请求。

当前笔记：
{current_note}

已经使用过的检索请求：
{used_text}

可选 source_types：
- web：官方文档、教程、项目资料、新闻、博客、产品说明、网页资料
- paper：论文、预印本、算法来源、实验方法、benchmark、state-of-the-art
- academic：综合学术资料，包括论文、书籍章节、学位论文、数据集等

选择原则：
1. 查最新研究、算法、实验结果、综述：优先 paper 或 academic
2. 查经典概念、教材体系、理论脉络：优先 academic
3. 查官方用法、开源项目、教程、产品信息：优先 web
4. 不确定时，可以混合 source_types，例如 ["web", "academic"]

要求：
1. 只针对当前笔记的信息缺口生成请求
2. 不要重复已经使用过的 query
3. 如果当前笔记已经足够完整，输出 {{"reference_queries": []}}
4. 最多生成 4 个检索请求
5. query 尽量使用适合检索的中英文关键词；学术类 query 优先英文
6. 输出严格 JSON 对象，不要输出解释

输出格式：
{{
  "reference_queries": [
    {{
      "query": "retrieval augmented generation survey",
      "source_types": ["paper", "academic"],
      "reason": "补充 RAG 方法的论文依据和综述来源"
    }},
    {{
      "query": "LangGraph documentation state graph agent workflow",
      "source_types": ["web"],
      "reason": "补充官方文档和工程实现资料"
    }}
  ]
}}
"""


def verify_note_prompt(raw_input: str, current_note: str, references: str) -> str:
    return f"""
你是一个严格的事实核验 Agent。

请检查当前笔记中的事实性内容，判断其是否能够被“用户原始输入”或“统一参考信息检索结果”支持。

用户原始输入：
{raw_input}

当前笔记：
{current_note}

统一参考信息检索结果：
{references}

要求：
1. 检查笔记中是否存在与用户输入或参考信息不一致的内容
2. 检查是否存在没有来源支撑的具体事实
3. 检查是否遗漏参考信息中与主题高度相关的重要信息
4. 对每个问题尽量指出支持或冲突的来源编号，例如 [R1]、[R2]
5. 理论、方法、实验、benchmark、综述类内容优先参考 paper / academic 来源
6. 经典定义、理论脉络、教材型内容优先参考 academic 来源
7. 工具使用、项目实现、产品文档类内容优先参考 web 来源
8. 不要重写整篇笔记，只输出核验报告
9. 使用 Markdown
"""


def refine_note_prompt(
    raw_input: str,
    current_note: str,
    references: str,
    verification_report: str,
) -> str:
    return f"""
你是一个严谨的研究笔记 Agent。

请基于用户输入、当前笔记、统一参考信息检索结果和事实核验报告，生成迭代后的新版 Markdown 笔记。

用户输入：
{raw_input}

当前笔记：
{current_note}

统一参考信息检索结果：
{references}

事实核验报告：
{verification_report}

要求：
1. 必须修正事实核验报告中指出的不一致内容
2. 必须删除无法由用户输入或参考信息支撑的具体事实
3. 必须补充参考信息中与主题高度相关的重要信息
4. 对新增的外部事实，尽量在句尾标注来源编号，例如 [R1]
5. 理论、方法、实验、综述类内容优先使用 paper / academic 证据
6. 经典概念、教材体系、理论脉络优先使用 academic 证据
7. 工具、项目、软件使用相关内容优先使用 web 证据
8. 可以动态调整笔记结构
9. 不要使用固定模板
10. 不要使用 ```markdown 代码块包裹
11. 第一行必须是一级标题，以 # 开头
12. 输出完整 Markdown 笔记
"""


def finalize_note_prompt(current_note: str, sources: list[str]) -> str:
    source_text = "\n".join(f"- {s}" for s in sorted(set(sources))) if sources else "无外部来源"

    return f"""
请将下面笔记整理为最终 Markdown 版本。

当前笔记：
{current_note}

参考来源链接：
{source_text}

要求：
1. 保持结构灵活
2. 删除重复内容
3. 语言清晰、具体
4. 如果存在参考来源，最后添加 Sources 章节
5. Sources 使用给定链接，不要编造来源
6. 直接输出 Markdown 正文
7. 不要输出解释性开场白
8. 不要使用 ```markdown 代码块包裹
9. 第一行必须是一级标题，以 # 开头
"""


def plan_assets_prompt(current_note: str, note_type: str) -> str:
    return f"""
你是一个研究笔记资产规划 Agent。

请阅读当前 Markdown 笔记，判断是否需要额外生成公式、代码、流程图或数据图表来增强笔记表达。

笔记类型：
{note_type}

当前笔记：
{current_note}

可用资产类型：
- formula：数学公式、理论公式、变量定义
- code：代码示例、伪代码、脚本片段
- mermaid：流程图、状态机图、架构图、因果关系图
- chart：基于结构化数据的折线图或柱状图

要求：
1. 只在确实有必要时规划资产，不要为了凑数量而生成
2. 每类资产最多规划 2 个
3. 总资产数最多 5 个
4. 如果不需要资产，输出空数组 []
5. 输出 JSON 数组，不要输出解释
6. insert_after_heading 必须尽量对应当前笔记中已有的标题文字

输出格式示例：
[
  {{
    "asset_type": "formula",
    "purpose": "解释 Bellman 方程及变量含义",
    "insert_after_heading": "核心原理",
    "priority": "high"
  }},
  {{
    "asset_type": "mermaid",
    "purpose": "展示 Agent 工作流",
    "insert_after_heading": "系统架构",
    "priority": "medium"
  }}
]
"""


def generate_assets_prompt(current_note: str, asset_plan: str) -> str:
    return f"""
你是一个多模态研究笔记资产生成 Agent。

请根据当前笔记和资产规划，生成可以嵌入 Markdown 的公式、代码、Mermaid 图和图表数据。

当前笔记：
{current_note}

资产规划：
{asset_plan}

要求：
1. 只生成资产规划中要求的内容
2. 所有内容必须与当前笔记主题直接相关
3. 不要编造具体实验结果、真实数据或来源事实
4. chart 只能使用示例性、教学性或笔记中已有的数据；不能伪造真实统计数据
5. Mermaid 只输出 Mermaid 语法主体，不要包裹 ```mermaid
6. 代码必须是最小可读示例，不要写大型项目代码
7. 公式必须使用 LaTeX
8. 输出严格 JSON 对象，不要输出解释

JSON 结构如下：
{{
  "formulas": [
    {{
      "formula_id": "formula_001",
      "title": "公式标题",
      "latex": "公式 LaTeX",
      "explanation": "公式说明",
      "variables": {{"x": "变量含义"}},
      "insert_after_heading": "插入到哪个标题之后"
    }}
  ],
  "code_blocks": [
    {{
      "code_id": "code_001",
      "title": "代码标题",
      "language": "python",
      "code": "代码内容",
      "purpose": "代码用途",
      "insert_after_heading": "插入到哪个标题之后"
    }}
  ],
  "diagrams": [
    {{
      "diagram_id": "diagram_001",
      "title": "图标题",
      "mermaid": "flowchart TD\\nA-->B",
      "caption": "图说明",
      "insert_after_heading": "插入到哪个标题之后"
    }}
  ],
  "charts": [
    {{
      "chart_id": "chart_001",
      "title": "图表标题",
      "chart_type": "line",
      "x_label": "横轴名称",
      "y_label": "纵轴名称",
      "series": [
        {{"label": "系列名称", "x": [1, 2, 3], "y": [0.1, 0.2, 0.3]}}
      ],
      "caption": "图表说明",
      "insert_after_heading": "插入到哪个标题之后"
    }}
  ]
}}
"""


def generate_title_prompt(final_note: str) -> str:
    return f"""
请为下面这篇笔记生成一个简洁、准确的文件名标题。

要求：
1. 标题要体现笔记内容主题
2. 不超过 20 个汉字或 8 个英文单词
3. 不要使用标点符号
4. 不要包含日期和时间
5. 只输出标题，不要解释

笔记内容：
{final_note[:2000]}
"""
