import os
from dotenv import load_dotenv
from note_agent import __version__
from note_agent.schemas import NoteAgentRequest
from note_agent.service import run_note_agent

load_dotenv()

def collect_input() -> str:
    print("请输入文本 / 关键词，输入 END 单独一行结束：\n")

    lines = []

    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)

    text = "\n".join(lines).strip()

    if not text:
        raise ValueError("输入内容不能为空")

    return text


def select_provider() -> str:
    print("\n请选择 LLM Provider：")
    print("1. DeepSeek Chat")
    print("2. OpenAI GPT-4o-mini")
    print("3. Qwen / 通义千问")
    print("4. Moonshot / Kimi")
    print("5. Zhipu / 智谱 GLM")
    print("6. SiliconFlow")

    choice = input("> ").strip()

    mapping = {
        "1": "deepseek",
        "2": "openai",
        "3": "qwen",
        "4": "moonshot",
        "5": "zhipu",
        "6": "siliconflow",
    }

    return mapping.get(choice, os.getenv("DEFAULT_LLM_PROVIDER", "deepseek"))


def select_search_api() -> str:
    print("\n请选择 Search API：")
    print("1. DuckDuckGo")
    print("2. Tavily")
    print("3. Perplexity")
    print("4. SearXNG")

    choice = input("> ").strip()

    mapping = {
        "1": "duckduckgo",
        "2": "tavily",
        "3": "perplexity",
        "4": "searxng",
    }

    return mapping.get(choice, os.getenv("SEARCH_API", "duckduckgo"))


def main():
    print(f"Note Agent v{__version__}")
    print("-" * 50)

    raw_input = collect_input()

    max_iterations = input("\n请输入迭代次数：\n> ").strip()

    if not max_iterations.isdigit():
        raise ValueError("迭代次数必须是整数")

    provider = select_provider()
    search_api = select_search_api()

    request = NoteAgentRequest(
        raw_input=raw_input,
        max_iterations=int(max_iterations),
        llm_provider=provider,
        search_api=search_api,
    )

    response = run_note_agent(request)

    print("\n最终笔记已保存：")
    print(response.saved_path)


if __name__ == "__main__":
    main()