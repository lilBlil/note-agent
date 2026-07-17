# Command-line interface for Note Agent.

import os

from dotenv import load_dotenv

from note_agent import __version__
from note_agent.io.input_loader import (
    build_combined_input,
    fetch_webpage_text,
    read_text_file,
)
from note_agent.domain.api import NoteAgentRequest
from note_agent.agent.runner_unified import stream_note_agent_events


load_dotenv()


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

    return mapping.get(choice, os.getenv("DEFAULT_LLM_PROVIDER", "deepseek"))


def select_search_api() -> str:
    print("\n请选择网页检索后端。统一检索中的论文和学术资料会自动使用内置来源。")
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


def select_agent_mode() -> str:
    print("\n请选择 Agent 模式：")
    print("1. Fixed Workflow (预定义流程)")
    print("2. ReAct Agent (自主决策工具调用)")

    choice = input("> ").strip()

    mapping = {
        "1": "fixed",
        "2": "react",
    }

    return mapping.get(choice, "fixed")


def select_yes_no(prompt: str, default: bool = False) -> bool:
    default_label = "Y/n" if default else "y/N"
    raw = input(f"\n{prompt}（{default_label}）：\n> ").strip().lower()

    if not raw:
        return default
    if raw in {"y", "yes", "是", "启用", "true", "1"}:
        return True
    if raw in {"n", "no", "否", "不", "false", "0"}:
        return False

    raise ValueError("请输入 y 或 n")


def run_with_progress(request: NoteAgentRequest, mode: str):
    print("\n运行配置：")
    print(f"- 模式：{mode}")
    print(f"- LLM：{request.llm_provider}")
    print(f"- 检索：{request.search_api}")
    print(f"- 迭代次数：{request.max_iterations}")
    print(f"- 多资产生成：{'启用' if request.enable_assets else '关闭'}")
    print(f"- Notion 发布：{'启用' if request.enable_notion else '关闭'}")
    print("\n开始运行，下面会持续显示进度。LLM 请求较慢时，请等待当前步骤完成。\n")

    for event in stream_note_agent_events(request, mode=mode):
        event_type = event.get("type")

        if event_type == "node_start":
            print(f"[步骤] {event.get('step_label', event.get('node_name', ''))}")
        elif event_type in {"info", "warning"}:
            text = event.get("text")
            if text:
                print(f"[{event_type}] {text}")
        elif event_type == "progress":
            iteration = event.get("iteration_count")
            if iteration is not None:
                print(f"[进度] 当前迭代：{iteration}")
        elif event_type == "error":
            message = event.get("message") or event.get("text") or "未知错误"
            print(f"[错误] {message}")
            if event.get("fatal", True):
                raise RuntimeError(message)
        elif event_type == "done":
            return event

    raise RuntimeError("运行结束但没有收到完成事件")


def main():
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

    default_iterations = os.getenv("DEFAULT_MAX_ITERATIONS", "1")
    max_iterations = input(
        f"\n请输入迭代次数，0 表示跳过检索核验，默认 {default_iterations}：\n> "
    ).strip()
    max_iterations = max_iterations or default_iterations

    if not max_iterations.isdigit():
        raise ValueError("迭代次数必须是整数")

    provider = select_provider()
    search_api = select_search_api()
    mode = select_agent_mode()
    enable_assets = select_yes_no("是否启用多资产生成（公式 / 代码 / 图表 / 流程图）")
    enable_notion = select_yes_no("是否发布到 Notion")

    request = NoteAgentRequest(
        raw_input=raw_input,
        max_iterations=int(max_iterations),
        llm_provider=provider,
        search_api=search_api,
        enable_assets=enable_assets,
        enable_notion=enable_notion,
    )

    result = run_with_progress(request, mode=mode)
    state = result.get("state", {})

    print("\n最终笔记已保存：")
    print(state.get("saved_path", ""))

    print("\n运行 ID：")
    print(result.get("run_id", state.get("run_id", "")))

    print("\n运行日志目录：")
    print(result.get("run_log_dir", ""))

    intermediate_paths = state.get("intermediate_paths", [])
    if intermediate_paths:
        print("\n中间版本：")
        for path in intermediate_paths:
            print(path)

    sources = state.get("sources", [])
    if sources:
        print("\n参考来源：")
        for source in sources:
            print(source)

    asset_paths = state.get("asset_paths", [])
    if asset_paths:
        print("\n生成资产：")
        for path in asset_paths:
            print(path)

    notion_url = state.get("notion_url", "")
    if notion_url:
        print("\nNotion 页面：")
        print(notion_url)


if __name__ == "__main__":
    main()
