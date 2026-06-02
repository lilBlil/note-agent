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

请根据用户输入和笔记类型，设计一个服务于该主题的 Markdown 笔记结构。

用户输入：
{raw_input}

笔记类型：
{note_type}

设计原则：
1. 每个章节必须有明确的信息目标——读者读完该章节后应获得什么
2. 章节之间有逻辑递进关系（背景→原理→实践→延伸）
3. 根据主题复杂度设计 4-7 个章节
4. 不要使用通用模板章节（如"总结"、"参考"），除非对该主题确实必要

输出 JSON 数组，每个元素包含 title 和 purpose。只输出 JSON：
[
  {{"title": "注意力机制的动机", "purpose": "解释为什么 RNN 序列建模需要注意力"}},
  {{"title": "Scaled Dot-Product Attention", "purpose": "推导核心计算过程和缩放因子的作用"}}
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
1. 按该结构生成 Markdown，第一行必须是 # 开头的一级标题
2. 用户输入中明确提到的信息必须准确保留
3. 可以使用通用领域知识补充上下文和解释，但不要编造具体数据、实验结果或引用来源
4. 每个章节至少有实质性内容（不要只写一句概括），用具体概念、步骤或对比填充
5. 标记信息缺口：对于你不确定或需要检索验证的内容，用 `[待验证]` 标注
6. 不要使用 ```markdown 代码块包裹
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
你是一个事实核验 Agent。请逐条检查笔记中的事实性声明。无论是否有参考信息检索结果，都必须完成以下所有检查。

用户原始输入：
{raw_input}

当前笔记：
{current_note}

参考信息检索结果：
{references}

请输出结构化核验报告，包含以下五部分：

### 事实错误
列出笔记中明显违背常识、公认知识或用户原始输入的事实性错误。格式：
- 笔记原文摘要 → 错误说明
（此为纯知识核验，不依赖参考信息）

### 自相矛盾
检查笔记内部是否有前后不一致或自相矛盾的地方。格式：
- 位置A 的说法 → 位置B 的说法 → 矛盾说明

### 事实冲突
列出笔记中与参考信息检索结果明确矛盾的内容。格式：
- 笔记原文摘要 → 参考信息说法 [来源编号]
（如果没有参考信息，此部分写”无参考信息可供比对”）

### 无源声明
列出笔记中无法被用户原始输入支撑的具体事实断言（通用领域知识和教科书级常识不算）。

### 遗漏信息
列出参考信息中满足以下全部条件的内容：
1. 与笔记核心主题直接相关（不是边缘扩展）
2. 对理解该主题不可或缺
3. 当前笔记完全未涉及
格式：- 遗漏内容摘要 [来源编号]
（如果没有参考信息，此部分写”无参考信息可供比对”）

注意：参考信息中的延伸话题、相关但非核心的内容不算遗漏。宁可少列，不要把所有检索结果都当作遗漏。

如果某部分没有问题，写”无”。不要重写笔记。
"""


def refine_note_prompt(
    raw_input: str,
    current_note: str,
    references: str,
    verification_report: str,
) -> str:
    return f"""
请根据核验报告修正并补充笔记，输出完整的新版 Markdown 笔记。

用户输入：
{raw_input}

当前笔记：
{current_note}

参考信息：
{references}

核验报告：
{verification_report}

修正规则（按优先级严格执行）：
1. 修正"事实错误"中列出的所有常识性和知识性错误
2. 消除"自相矛盾"中列出的所有前后不一致，选择正确的版本保留
3. 修正"事实冲突"中列出的所有矛盾，以参考信息为准
4. 删除或弱化"无源声明"中列出的无法验证的具体事实（改为谨慎措辞如'研究表明''一般认为'等，或直接删除）
5. 将"遗漏信息"中的重要内容整合到已有章节或新增子章节，句尾标注来源 [R1]

保护性约束（不可违反）：
- 禁止删除原有章节或大段已有内容，只能增补和局部修正
- 原笔记中已有的公式、代码、定义、推导必须原样保留，除非被核验报告明确指出有误
- 新增内容应作为补充段落或子章节插入，不要用新内容替换原有内容
- 保持原有章节顺序，新章节只能追加在相关章节之后

格式要求：第一行 # 标题，不要 ```markdown 包裹，输出完整笔记。
"""


def finalize_note_prompt(current_note: str, sources: list[str]) -> str:
    source_text = "\n".join(f"- {s}" for s in sorted(set(sources))) if sources else "无外部来源"

    return f"""
请将笔记整理为最终发布版本。

当前笔记：
{current_note}

参考来源链接：
{source_text}

整理任务：
1. 合并重复或高度相似的段落
2. 确保章节间逻辑连贯（前文引入的概念后文不应重新解释）
3. 删除 [待验证] 标记：已有来源支撑的去掉标记，仍无来源的删除该句
4. 统一术语用法（同一概念全文使用同一名称）
5. 如果有参考来源，末尾添加 ## Sources 章节，使用给定链接，不要编造

不要添加新信息。第一行 # 标题，不要 ```markdown 包裹，直接输出最终笔记。
"""


def plan_assets_prompt(current_note: str, note_type: str) -> str:
    return f"""
请扫描以下笔记，只在文字确实不够用的时候才规划资产（公式/代码/图/图表），不要为了"丰富"而添加装饰性内容。

笔记类型：{note_type}

当前笔记：
{current_note}

## 何时需要用资产（四类，宁缺毋滥）

| 场景 | 类型 | 要求 |
|------|------|------|
| 文字描述数学关系但未给出 LaTeX | formula | 精确表达，避免读者脑补 |
| 描述算法/API 但无代码示例 | code | 最小可运行片段，5-20 行 |
| 多步骤流程/状态转换/组件关系 | mermaid | 3-10 节点，降低认知负担 |
| 引用了可量化对比数据 | chart | 只用笔记中已有的数据，不伪造 |

## 不需要资产的情况
- 笔记中已有对应的代码块、公式或 mermaid 图 → 不要重复
- 纯文字已经足够清晰 → 图表只是锦上添花
- 没有具体数据 → 不创建 chart
- 笔记本身没有触发场景 → 输出空数组

## 要求
- 每个资产有 necessity_reason，说清"为什么纯文字不够"
- insert_after_heading 必须是笔记中已有的标题
- 最多 4 个，不多不少；不需要就输出 []
- 严格 JSON 数组，不要解释

输出格式：
[{{"asset_type": "formula", "purpose": "...", "necessity_reason": "...", "insert_after_heading": "...", "priority": "high"}}]
"""


def generate_assets_prompt(current_note: str, asset_plan: str) -> str:
    return f"""
根据规划生成资产，每个资产必须比文字提供更多信息（精确性/可视化/可运行性），禁止把文字内容换个形式复述。

当前笔记：
{current_note}

资产规划：
{asset_plan}

## 各类型标准

**formula**：笔记中文字关系的精确 LaTeX。variables 只列非显而易见的变量，explanation 一句话说明含义。

**code**：最小可运行示例 5-20 行，直接说明笔记中的算法或用法。不要完整项目、不要 import 之外的样板。

**mermaid**：3-10 节点，简短中文标签。选最合适的图类型（flowchart/sequenceDiagram/stateDiagram/classDiagram）。

**chart**：只用笔记中已有的数据，不伪造。无数据时不生成。

## 输出

严格 JSON，无解释。规划和笔记内容都作为上下文参考，不需要在输出中复述。某类资产在规划中没有则对应字段为 []。

{{"formulas":[{{"formula_id":"f1","title":"...","latex":"...","explanation":"...","variables":{{"x":"含义"}},"insert_after_heading":"..."}}],"code_blocks":[{{"code_id":"c1","title":"...","language":"python","code":"...","purpose":"...","insert_after_heading":"..."}}],"diagrams":[{{"diagram_id":"d1","title":"...","mermaid":"flowchart TD\\nA-->B","caption":"...","insert_after_heading":"..."}}],"charts":[{{"chart_id":"ch1","title":"...","chart_type":"line","x_label":"...","y_label":"...","series":[{{"label":"...","x":[1,2],"y":[3,4]}}],"caption":"...","insert_after_heading":"..."}}]}}
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
