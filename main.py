from note_agent.graph import graph
from note_agent import __version__

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


def main():
    print(f"Note Research Agent v{__version__}")
    print("-" * 50)

    raw_input = collect_input()

    max_iterations = input("\n请输入迭代次数，建议 1-3：\n> ").strip()

    if not max_iterations.isdigit():
        raise ValueError("迭代次数必须是整数")

    initial_state = {
        "raw_input": raw_input,
        "max_iterations": int(max_iterations),
        "iteration_count": 0,
        "note_type": "",
        "note_outline": [],
        "current_note": "",
        "search_queries": [],
        "search_results": [],
        "sources": [],
        "final_note": "",
        "saved_path": "",
    }

    print("\n开始运行状态机...\n")

    for event in graph.stream(initial_state, stream_mode="updates"):
        for node_name, update in event.items():
            print(f"\n=== 节点完成：{node_name} ===")

            if "note_type" in update:
                print(f"笔记类型：{update['note_type']}")

            if "note_outline" in update:
                print("已生成动态笔记结构。")

            if "current_note" in update:
                print("\n当前笔记预览：")
                print(update["current_note"][:800] + "...")

            if "search_queries" in update:
                print("\n本轮检索问题：")
                for q in update["search_queries"]:
                    print(f"- {q}")

            if "sources" in update:
                print(f"累计来源数量：{len(update['sources'])}")

            if "final_note" in update:
                print("\n最终笔记已生成。")

            if "saved_path" in update:
                print(f"\n最终笔记已保存：{update['saved_path']}")

    print("\n运行结束。")


if __name__ == "__main__":
    main()