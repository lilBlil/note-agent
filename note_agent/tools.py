import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from ddgs import DDGS
from langchain_deepseek import ChatDeepSeek


load_dotenv()

NOTES_DIR = Path("notes")
NOTES_DIR.mkdir(exist_ok=True)


def get_model():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY，请检查 .env 文件")

    return ChatDeepSeek(
        model="deepseek-chat",
        api_key=api_key,
        temperature=0.3,
    )


def ask_llm(prompt: str, stream: bool = True) -> str:
    """调用 LLM。默认逐字流式输出，同时返回完整文本。"""
    llm = get_model()

    if not stream:
        response = llm.invoke(prompt)
        return response.content

    full_text = ""

    for chunk in llm.stream(prompt):
        if chunk.content:
            print(chunk.content, end="", flush=True)
            full_text += chunk.content

    print()
    return full_text


def clean_filename(title: str) -> str:
    title = title.strip()
    title = re.sub(r"[\\/:*?\"<>|]", "", title)
    title = re.sub(r"\s+", "_", title)
    title = re.sub(r"_+", "_", title)
    return title[:40] or "note"


def web_search(query: str, max_results: int = 5) -> tuple[str, list[str]]:
    results = []
    sources = []

    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            title = item.get("title", "")
            body = item.get("body", "")
            href = item.get("href", "")

            results.append(f"标题：{title}\n摘要：{body}\n链接：{href}")
            if href:
                sources.append(href)

    return "\n\n".join(results), sources


def save_markdown(title: str, content: str) -> str:
    safe_title = clean_filename(title)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = NOTES_DIR / f"{safe_title}_{timestamp}.md"
    file_path.write_text(content, encoding="utf-8")
    return str(file_path.resolve())


def strip_markdown_fence(content: str) -> str:
    content = content.strip()

    # 去掉外层代码块
    if content.startswith("```markdown"):
        content = content[len("```markdown"):].strip()
    elif content.startswith("```md"):
        content = content[len("```md"):].strip()
    elif content.startswith("```"):
        content = content[len("```"):].strip()

    if content.endswith("```"):
        content = content[:-3].strip()

    # 如果模型前面有废话，从第一个 Markdown 标题开始截取
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            content = "\n".join(lines[i:]).strip()
            break

    return content