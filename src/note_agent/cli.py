from config.settings import get_settings
from note_agent import __version__
from note_agent.agent.service import run_note_agent
from note_agent.io.input_loader import (
    build_combined_input,
    fetch_webpage_text,
    read_text_file,
)
from note_agent.schemas import NoteAgentRequest


def collect_manual_input() -> str:
    print("请输入文本 / 关键词，输入 END 单独一行结束；如果不需要手动输入，直接输入 END：\n")

    lines = []

    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)

    return "\n".join(lines).strip()


def collect_file_inputs() -> list[tuple[str, str]]:
    print("\n请输入要导入的 .txt / .md 文件路径。")
    print("多个文件用英文逗号分隔；如果不导入文件，直接回车。")

    raw = input("> ").strip()

    if not raw:
        return []

    file_paths = [item.strip() for item in raw.split(",") if item.strip()]

    results = []

    for path in file_paths:
        try:
            text = read_text_file(path)
            results.append((path, text))
            print(f"已读取文件：{path}")
        except Exception as e:
            print(f"读取文件失败：{path}，原因：{e}")

    return results


def collect_url_inputs() -> list[tuple[str, str]]:
    print("\n请输入要导入的网页 URL。")
    print("多个 URL 用英文逗号分隔；如果不导入网页，直接回车。")

    raw = input("> ").strip()

    if not raw:
        return []

    urls = [item.strip() for item in raw.split(",") if item.strip()]

    results = []

    for url in urls:
        try:
            text = fetch_webpage_text(url)
            results.append((url, text))
            print(f"已读取网页：{url}")
        except Exception as e:
            print(f"读取网页失败：{url}，原因：{e}")

    return results


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

    return mapping.get(choice, get_settings().default_llm_provider)


def select_search_api() -> str:
    print("\n请选择网页检索后端。统一检索中的论文、书籍和学术资料会自动使用内置来源。")
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

    return mapping.get(choice, get_settings().search_api)


def main() -> None:
    print(f"Note Agent v{__version__}")
    print("-" * 50)

    manual_text = collect_manual_input()
    file_texts = collect_file_inputs()
    webpage_texts = collect_url_inputs()

    raw_input = build_combined_input(
        manual_text=manual_text,
        file_texts=file_texts,
        webpage_texts=webpage_texts,
    )

    default_iterations = get_settings().default_max_iterations
    max_iterations = input(
        f"\n请输入迭代次数，0 表示跳过检索核验，建议 1-3，默认 {default_iterations}：\n> "
    ).strip()

    if not max_iterations:
        max_iterations_value = default_iterations
    elif max_iterations.isdigit():
        max_iterations_value = int(max_iterations)
    else:
        raise ValueError("迭代次数必须是整数")

    provider = select_provider()
    search_api = select_search_api()

    request = NoteAgentRequest(
        raw_input=raw_input,
        max_iterations=max_iterations_value,
        llm_provider=provider,
        search_api=search_api,
    )

    response = run_note_agent(request)

    print("\n最终笔记已保存：")
    print(response.saved_path)

    print("\n运行 ID：")
    print(response.run_id)

    print("\n运行日志目录：")
    print(response.run_log_dir)

    if response.intermediate_paths:
        print("\n中间版本：")
        for path in response.intermediate_paths:
            print(path)

    if response.sources:
        print("\n参考来源：")
        for source in response.sources:
            print(source)

    if response.asset_paths:
        print("\n生成资产：")
        for path in response.asset_paths:
            print(path)
