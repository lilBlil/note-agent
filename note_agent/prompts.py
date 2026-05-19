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


def generate_search_queries_prompt(current_note: str, used_queries: list[str]) -> str:
    used_text = "\n".join(f"- {q}" for q in used_queries) if used_queries else "暂无"

    return f"""
请阅读当前笔记，判断还缺少哪些必要信息，并据此生成搜索 query。

当前笔记：
{current_note}

已经使用过的检索问题：
{used_text}

要求：
1. 只针对当前笔记的信息缺口生成 query
2. 不要重复已经使用过的 query
3. 如果当前笔记已经足够完整，可以不输出任何 query
4. 每行一个 query
5. 不要编号，不要解释
"""


def verify_note_prompt(raw_input: str, current_note: str, search_results: str) -> str:
    return f"""
你是一个严格的事实核验 Agent。

请检查当前笔记中的事实性内容，判断其是否能够被“用户原始输入”或“网络搜索结果”支持。

用户原始输入：
{raw_input}

当前笔记：
{current_note}

网络搜索结果：
{search_results}

要求：
1. 检查笔记中是否存在与用户输入或搜索结果不一致的内容
2. 检查是否存在没有来源支撑的具体事实
3. 检查是否遗漏搜索结果中与主题高度相关的重要信息
4. 输出需要修改、删除或补充的内容
5. 不要重写整篇笔记，只输出核验报告
6. 使用 Markdown
"""


def refine_note_prompt(
    raw_input: str,
    current_note: str,
    search_results: str,
    verification_report: str,
) -> str:
    return f"""
你是一个严谨的研究笔记 Agent。

请基于用户输入、当前笔记、网络搜索结果和事实核验报告，生成迭代后的新版 Markdown 笔记。

用户输入：
{raw_input}

当前笔记：
{current_note}

网络搜索结果：
{search_results}

事实核验报告：
{verification_report}

要求：
1. 必须修正事实核验报告中指出的不一致内容
2. 必须删除无法由用户输入或搜索结果支撑的具体事实
3. 必须补充搜索结果中与主题高度相关的重要信息
4. 可以动态调整笔记结构
5. 可以新增、合并、重命名章节
6. 不要使用固定模板
7. 不要使用 ```markdown 代码块包裹
8. 第一行必须是一级标题，以 # 开头
9. 输出完整 Markdown 笔记
"""


def finalize_note_prompt(current_note: str, sources: list[str]) -> str:
    source_text = "\n".join(f"- {s}" for s in sorted(set(sources)))

    return f"""
请将下面笔记整理为最终 Markdown 版本。

当前笔记：
{current_note}

来源链接：
{source_text}

要求：
1. 保持结构灵活
2. 删除重复内容
3. 语言清晰、具体
4. 最后添加 Sources 章节
5. Sources 使用给定链接
6. 直接输出 Markdown 正文
7. 不要输出解释性开场白
8. 不要使用 ```markdown 代码块包裹
9. 第一行必须是一级标题，以 # 开头
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