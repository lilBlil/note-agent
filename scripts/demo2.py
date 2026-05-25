# main.py
# Note Organizer Agent v1.5：支持手动输入 / 文件读取 / 流式输出 / 自动保存

import os
import re
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


def clean_filename(title: str) -> str:
    """生成更干净的文件名。"""
    title = title.strip()
    title = re.sub(r"[\\/:*?\"<>|]", "", title)
    title = re.sub(r"\s+", "_", title)
    title = re.sub(r"_+", "_", title)
    return title[:40] or "note"


def read_text_file(file_path: str) -> str:
    """读取 .txt / .md 文件。"""
    path = Path(file_path.strip().strip('"').strip("'"))

    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")

    if path.suffix.lower() not in [".txt", ".md"]:
        raise ValueError("当前仅支持 .txt 和 .md 文件")

    content = path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError("文件内容为空")

    return content


@tool
def save_markdown(title: str, content: str) -> str:
    """将整理后的笔记保存为 Markdown 文件。"""

    safe_title = clean_filename(title)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 文件名格式：
    # LangChain_Agent_学习笔记_20260516_153012.md
    filename = f"{safe_title}_{timestamp}.md"
    file_path = NOTES_DIR / filename
    file_path.write_text(content, encoding="utf-8")

    return f"笔记已保存到：{file_path.resolve()}"


def get_model():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY，请检查 .env 文件")

    return ChatDeepSeek(
        model="deepseek-chat",
        api_key=api_key,
        temperature=0.3,
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
        7. 先输出整理后的 Markdown 笔记内容
        8. 最终必须调用 save_markdown 工具保存笔记
        """,
    )


def input_manual_text() -> str:
    """手动输入多行文本。"""
    print("\n请输入原始笔记内容，输入 END 单独一行结束：\n")

    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)

    return "\n".join(lines).strip()


def input_from_file() -> str:
    """从本地 .txt / .md 文件读取文本。"""
    file_path = input("\n请输入 .txt 或 .md 文件路径：\n> ").strip()

    if not file_path:
        raise ValueError("文件路径不能为空")

    return read_text_file(file_path)


def get_raw_text() -> str:
    """选择输入方式并获取原始文本。"""
    print("请选择输入方式：")
    print("1. 手动输入文本")
    print("2. 读取本地 .txt / .md 文件")

    choice = input("> ").strip()

    if choice == "1":
        raw_text = input_manual_text()
    elif choice == "2":
        raw_text = input_from_file()
    else:
        raise ValueError("无效选项，请输入 1 或 2")

    if not raw_text:
        raise ValueError("输入内容为空，程序结束")

    return raw_text


def run_agent(raw_text: str):
    print("\n正在创建 Agent...")
    agent = build_agent()

    user_prompt = f"""
    请整理以下原始笔记，并保存为 Markdown 文件：
    {raw_text}
    """

    print("\nAgent 流式输出：\n")

    for msg_chunk, metadata in agent.stream(
        {"messages": [HumanMessage(content=user_prompt)]},
        stream_mode="messages",
    ):
        if msg_chunk.content:
            print(msg_chunk.content, end="", flush=True)

    print("\n\n处理完成。")


def main():
    print("Note Organizer Agent v2")
    print("-" * 40)

    try:
        raw_text = get_raw_text()
        run_agent(raw_text)
    except Exception as e:
        print(f"\n错误：{e}")


if __name__ == "__main__":
    main()