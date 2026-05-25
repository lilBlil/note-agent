# main.py
# Note Agent：基于 LangChain + DeepSeek 的笔记整理 Agent

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain_deepseek import ChatDeepSeek


load_dotenv()


NOTES_DIR = Path("notes")
NOTES_DIR.mkdir(exist_ok=True)


@tool
def save_markdown(title: str, content: str) -> str:
    """将整理后的笔记保存为 Markdown 文件。

    Args:
        title: 笔记标题
        content: Markdown 格式的笔记内容
    """
    safe_title = "".join(c for c in title if c.isalnum() or c in ("-", "_", " ")).strip()
    safe_title = safe_title.replace(" ", "_") or "note"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = NOTES_DIR / f"{timestamp}_{safe_title}.md"

    file_path.write_text(content, encoding="utf-8")
    return f"笔记已保存到：{file_path}"


def get_model():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY，请检查 .env 文件")

    return ChatDeepSeek(
        model="deepseek-chat",
        api_key=api_key,
    )


def build_agent():
    model = get_model()

    return create_agent(
        model=model,
        tools=[save_markdown],
        system_prompt="""
        你是一个个人笔记整理 Agent。

        你的任务是把用户输入的零散文本整理成结构化 Markdown 笔记，并调用 save_markdown 工具保存。

        输出要求：
        1. 自动生成清晰标题
        2. 生成摘要
        3. 提取核心知识点
        4. 按层级整理详细笔记
        5. 给出后续行动建议
        6. 不要编造原文没有的信息
        7. 最终必须调用 save_markdown 工具保存笔记
        """,
    )


def main():
    print("Note Organizer Agent")
    print("请输入原始笔记内容，输入 END 结束：\n")

    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)

    raw_text = "\n".join(lines).strip()

    if not raw_text:
        print("未输入内容，程序结束。")
        return
    
    agent = build_agent()

    user_prompt = f"""
请整理以下原始笔记，并保存为 Markdown 文件：

{raw_text}
"""

    result = agent.invoke({
        "messages": [HumanMessage(content=user_prompt)]
    })

    print("\nAgent 回复：")
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main()