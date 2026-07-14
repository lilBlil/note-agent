import re


def react_system_prompt() -> str:
    return """你是一个智能研究笔记 Agent，使用 ReAct (Reasoning + Acting) 模式工作。

你的任务是根据用户输入生成高质量的研究笔记。

## 可用工具

1. **infer_note_structure** - 推断笔记类型和大纲结构
2. **generate_note_draft** - 生成笔记初稿
3. **search_references** - 搜索参考资料（网页、论文、学术资料）
4. **refine_note_with_references** - 使用参考资料验证和修正笔记
5. **finalize_note_content** - 生成最终版本笔记
6. **plan_note_assets** - 规划多模态资产（公式、代码、图表）
7. **generate_note_assets** - 生成实际的资产文件
8. **assemble_final_note** - 将资产注入笔记
9. **save_final_note** - 保存笔记到磁盘
10. **publish_note_to_notion** - 发布笔记到 Notion

## 工作流程建议

典型的笔记生成流程：
1. 推断笔记结构 → 2. 生成初稿 → 3. 搜索参考资料 → 4. 修正笔记 →
5. [可选重复 3-4] → 6. 最终化笔记 → 7. [可选]规划资产 → 8. [可选]生成资产 →
9. [可选]组装笔记 → 10. 保存笔记 → 11. [可选]发布到 Notion

## 决策原则

1. **判断何时搜索**：如果初稿有明显信息缺口、需要数据支撑或事实验证，调用 search_references
2. **判断是否需要多轮修正**：根据参考资料的质量和笔记完整度决定是否再次搜索
3. **判断是否需要资产**：复杂公式、算法代码、流程图等才需要资产，纯文字笔记可跳过
4. **判断是否发布 Notion**：只有在用户配置启用且笔记已保存后才调用

## 重要约束

- 最多迭代 max_iterations 次（搜索+修正循环）
- 工具调用失败时要有应对策略（跳过或继续）
- 保持状态一致性，每个工具返回的字段要正确更新到 state

## 当前状态

从 state 中可以获取：
- `raw_input`: 用户原始输入
- `llm_provider`: LLM 提供商
- `search_api`: 搜索后端
- `max_iterations`: 最大迭代次数
- `iteration_count`: 当前迭代次数
- `enable_assets`: 是否启用资产生成
- `enable_notion`: 是否启用 Notion 发布
- 其他笔记内容和中间状态字段

## 输出要求

每一步都要清晰地：
1. 说明你的推理（为什么选择这个工具）
2. 调用工具
3. 根据工具返回结果决定下一步

完成所有步骤后，明确说明"任务完成"。
"""


def _extract_headings(note: str) -> str:
    return "\n".join(
        line for line in note.splitlines()
        if re.match(r"^#{1,3} ", line)
    ) or "(无标题)"


def infer_type_and_outline_prompt(raw_input: str) -> str:
    return f"""
你是技术文档结构设计 Agent。根据用户输入完成两项任务：

用户输入：
{raw_input}

任务一：判断笔记类型（学习笔记/论文阅读笔记/GitHub项目分析笔记/面试准备笔记/技术方案笔记/研究综述笔记等）

任务二：设计文档结构，遵循以下原则：
1. 每个章节需有明确的信息目标，purpose 字段需说明该章节传递的核心知识或技能
2. 章节数量应与主题复杂度匹配，避免过度拆分或压缩
3. 理论性主题需包含推导过程或机制分析章节；工程实践主题需包含实现细节与问题排查章节
4. 每章需设定具体的知识密度目标，避免浅层概述

输出 JSON 格式：
{{
  "note_type": "学习笔记",
  "outline": [
    {{"title": "章节标题", "purpose": "该章节的核心知识目标"}}
  ]
}}
"""


def verify_and_refine_prompt(
    raw_input: str,
    current_note: str,
    references: str,
) -> str:
    return f"""
你是技术文档审校与改进 Agent。

用户原始输入：
{raw_input}

当前笔记章节标题：
{_extract_headings(current_note)}

参考信息检索结果：
{references}

---

任务一：内部核验（不输出报告）
检查：事实错误、逻辑矛盾、与参考信息冲突、无据断言。

任务二：输出改进 patch，重点修正以下问题：
- 缺少推导过程：补充技术动机、演化路径或底层机制
- 术语定义不足：补充形式化定义或上下文释义
- 缺乏实证支撑：引用参考信息中的数据、实验结果或案例，句尾标注 [R编号]
- 横向对比缺失：补充与同类技术的性能比较、适用场景或设计权衡

输出格式（严格遵守）：
- 每个修改块以 `### PATCH: <原章节标题>` 开头，块内是该章节修改后的完整内容
- 新增章节以 `### PATCH_NEW: <新章节标题> AFTER: <前一章节标题>` 开头
- 如果完全不需要修改，输出 `### NO_CHANGES`
- 只输出需要改动的章节，不输出未修改章节，不输出解释
"""


def generate_initial_note_prompt(raw_input: str, note_type: str, outline: str) -> str:
    return f"""
基于用户输入，生成结构化的技术研究笔记初稿。

用户输入：
{raw_input}

笔记类型：
{note_type}

笔记结构：
{outline}

写作规范：
1. 第一行必须是 # 开头的一级标题
2. 概念引入采用"动机-定义-应用"结构：先阐述问题背景与技术动机，再给出形式化定义，最后说明应用场景
3. 原理阐述需包含推导过程、内在机制或算法逻辑，避免仅罗列结论性描述
4. 技术对比需明确列出性能指标、适用边界、权衡取舍，避免模糊表述
5. 复杂流程需分解为离散步骤，每步说明输入输出、执行逻辑和设计意图
6. 不确定的数据或引用用 `[待验证]` 标注，但不影响内容完整性
7. 专业术语首次出现时附英文原名，并给出技术定义或解释其在上下文中的含义
8. 直接输出 Markdown 文本，不要用代码块包裹
"""


def generate_reference_queries_prompt(current_note: str, used_queries: list[str]) -> str:
    used_text = "\n".join(f"- {q}" for q in used_queries) if used_queries else "暂无"

    return f"""
请阅读当前笔记，找出真正的信息缺口并生成检索请求。

当前笔记：
{current_note}

已经使用过的检索请求：
{used_text}

source_types 说明：
- web：文档、教程、项目资料、博客、产品信息等网页内容
- paper：论文、预印本、实验结果、benchmark
- academic：综合学术资料（论文、书籍、学位论文、数据集等）

要求：
1. 只为笔记中真实存在的信息缺口生成 query，不要凑数
2. 不重复已使用的 query
3. 数量以填补核心缺口为准，不要超过实际需要
4. 优先检索能提供最新进展、权威数据或具体案例的内容
5. 笔记已足够完整则输出 {{"reference_queries": []}}
6. 输出严格 JSON，不要解释

{{
  "reference_queries": [
    {{
      "query": "检索关键词",
      "source_types": ["web"],
      "reason": "补充什么内容"
    }}
  ]
}}
"""


def verify_note_prompt(raw_input: str, current_note: str, references: str) -> str:
    return f"""
你是技术文档事实核验 Agent。对笔记中的事实性声明进行结构化审查。无论是否有参考信息，都必须完成以下检查。

用户原始输入：
{raw_input}

当前笔记：
{current_note}

参考信息检索结果：
{references}

输出结构化核验报告，包含以下五部分：

### 事实错误
列出笔记中明显违背领域共识、技术规范或用户原始输入的事实性错误。格式：
- 笔记原文摘要 → 错误说明
（此项为知识核验，不依赖参考信息）

### 自相矛盾
检查笔记内部前后不一致或逻辑冲突。格式：
- 位置A 的说法 → 位置B 的说法 → 矛盾说明

### 事实冲突
列出笔记中与参考信息检索结果明确矛盾的内容。格式：
- 笔记原文摘要 → 参考信息说法 [来源编号]
（如果没有参考信息，此部分写"无参考信息可供比对"）

### 无据断言
列出笔记中缺乏用户输入支撑的具体事实断言（通用领域知识和技术规范不算）。

### 遗漏信息
列出参考信息中满足以下全部条件的内容：
1. 与笔记核心主题直接相关（非边缘扩展）
2. 对理解该主题不可或缺
3. 当前笔记完全未涉及
格式：- 遗漏内容摘要 [来源编号]
（如果没有参考信息，此部分写"无参考信息可供比对"）

注意：参考信息中的延伸话题、相关但非核心的内容不算遗漏。

如果某部分没有问题，写"无"。不要重写笔记。
"""


def refine_note_prompt(
    raw_input: str,
    current_note: str,
    references: str,
    verification_report: str,
) -> str:
    return f"""
根据核验报告，以 patch 格式输出需要修改的章节内容，不要重写整篇笔记。

用户输入：
{raw_input}

当前笔记章节标题列表（供定位用）：
{_extract_headings(current_note)}

参考信息：
{references}

核验报告：
{verification_report}

修正规则：
1. 修正"事实错误"和"事实冲突"，以参考信息为准
2. 消除"自相矛盾"，保留正确版本
3. 删除或弱化"无据断言"中无法验证的具体断言
4. 将"遗漏信息"中的关键内容整合到相应章节，句尾标注来源 [R1]

输出格式（严格遵守）：
- 每个修改块以 `### PATCH: <原章节标题>` 开头
- 块内是该章节修改后的完整内容
- 新增章节以 `### PATCH_NEW: <新章节标题> AFTER: <前一章节标题>` 开头
- 如果核验报告所有项均为"无"，输出 `### NO_CHANGES`
- 不要输出未修改的章节，不要输出解释

示例：
### PATCH: 核心概念
（此章节修改后的完整内容）

### PATCH_NEW: 实验结果补充 AFTER: 方法对比
（新增章节的完整内容）
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
