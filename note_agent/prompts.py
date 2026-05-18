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
"""


def generate_search_queries_prompt(current_note: str) -> str:
    return f"""
请阅读当前笔记，判断哪些地方需要网络检索补充事实信息。

当前笔记：
{current_note}

要求：
1. 生成 3 个搜索 query
2. query 要具体
3. 每行一个 query
4. 不要编号
"""


def refine_note_prompt(raw_input: str, current_note: str, search_results: str) -> str:
    return f"""
你是一个严谨的研究笔记 Agent。

请基于用户输入、当前笔记和网络搜索结果，生成迭代后的新版 Markdown 笔记。

用户输入：
{raw_input}

当前笔记：
{current_note}

网络搜索结果：
{search_results}

要求：
1. 可以动态调整笔记结构
2. 可以新增、合并、重命名章节
3. 只能使用用户输入和搜索结果支持的信息
4. 保留具体事实、概念、流程和关键区别
5. 不要使用固定模板
6. 输出完整 Markdown 笔记
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
"""