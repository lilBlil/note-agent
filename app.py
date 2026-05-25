# app.py
# Note Agent Streamlit UI with unified reference retrieval and multimodal assets.

import html

import streamlit as st

from config.settings import get_settings
from note_agent import __version__
from note_agent.agent.service import stream_note_agent_events
from note_agent.io.input_loader import (
    build_combined_input,
    fetch_webpage_text,
    read_uploaded_text_file,
)
from note_agent.schemas import NoteAgentRequest


st.set_page_config(
    page_title="Note Agent",
    page_icon="📝",
    layout="wide",
)


def render_scroll_box(content: str, height: int = 320) -> str:
    """渲染可滚动文本框，避免 Streamlit text_area 重复 key 问题。"""
    safe_content = html.escape(content or "")
    return f"""
    <div style="
        height: {height}px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-wrap: break-word;
        padding: 14px;
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 10px;
        background-color: rgba(30, 32, 42, 0.95);
        font-family: Consolas, Menlo, Monaco, monospace;
        font-size: 14px;
        line-height: 1.6;
    ">
{safe_content}
    </div>
    """


def render_node_list(node_records: list[dict]) -> str:
    lines = []

    for item in node_records:
        status = item.get("status", "pending")
        label = item.get("label", "")
        node = item.get("node", "")

        if status == "running":
            icon = "🔄"
            tag = "正在运行"
        elif status == "done":
            icon = "✅"
            tag = "已完成"
        else:
            icon = "•"
            tag = "等待中"

        lines.append(f"{icon} {label}\n   节点：{node}\n   状态：{tag}\n")

    return "\n".join(lines)


def parse_urls(raw_urls: str) -> list[str]:
    """支持换行或英文逗号分隔 URL。"""
    raw_urls = raw_urls or ""
    parts = []

    for line in raw_urls.splitlines():
        parts.extend(item.strip() for item in line.split(","))

    return [item for item in parts if item]


def option_index(options: list[str], value: str) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


def main():
    settings = get_settings()

    st.title(f"📝 Note Agent v{__version__}")
    st.caption(
        "LangGraph-based research note agent with unified reference retrieval, verification and multimodal assets."
    )

    with st.sidebar:
        st.header("⚙️ Settings")

        llm_provider_options = [
            "deepseek",
            "openai",
            "qwen",
            "moonshot",
            "zhipu",
            "siliconflow",
        ]
        llm_provider = st.selectbox(
            "LLM Provider",
            options=llm_provider_options,
            index=option_index(llm_provider_options, settings.default_llm_provider),
        )

        search_api_options = [
            "duckduckgo",
            "tavily",
            "perplexity",
            "searxng",
        ]
        search_api = st.selectbox(
            "Web Search Backend",
            options=search_api_options,
            index=option_index(search_api_options, settings.search_api),
            help="统一检索中的网页来源使用该后端；论文、书籍和学术资料由内置来源自动处理。",
        )

        max_iterations = st.number_input(
            "Max Iterations",
            min_value=0,
            value=settings.default_max_iterations,
            step=1,
            help="0 表示不进行检索-核验-修正迭代，直接整理并保存初版笔记。",
        )

        st.divider()

        st.markdown("### 当前功能")
        st.markdown(
            """
            - 手动文本输入
            - `.txt` / `.md` 文件上传
            - 网页 URL 导入
            - 动态笔记结构生成
            - 统一参考信息检索
            - 覆盖网页 / 论文 / 书籍 / 学术资料
            - 搜索缓存
            - 事实检验
            - 多轮迭代
            - 公式 / 代码 / Mermaid / 图表资产生成
            - 中间版本保存
            - 运行日志持久化
            - Markdown 自动保存
            - 运行节点展示
            - 逐字流式输出
            """
        )

    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.subheader("输入来源")

        manual_text = st.text_area(
            label="手动输入文本 / 关键词",
            height=180,
            placeholder=(
                "例如：\n"
                "LangChain Agent\n"
                "LangGraph workflow\n"
                "Memory\n"
                "RAG\n"
            ),
        )

        uploaded_files = st.file_uploader(
            "上传 .txt / .md 文件",
            type=["txt", "md"],
            accept_multiple_files=True,
        )

        raw_urls = st.text_area(
            label="网页 URL",
            height=90,
            placeholder="多个 URL 可换行填写，也可用英文逗号分隔",
        )

        run_button = st.button(
            "🚀 生成研究笔记",
            type="primary",
            use_container_width=True,
        )

        st.subheader("运行节点")
        node_area = st.empty()
        node_area.markdown(
            render_scroll_box("等待运行...", height=300),
            unsafe_allow_html=True,
        )

    with right_col:
        st.subheader("当前步骤输出")

        step_area = st.empty()
        step_area.markdown(
            render_scroll_box("运行后，这里会显示当前节点的逐字输出。", height=300),
            unsafe_allow_html=True,
        )

        st.subheader("检索过程 / 中间版本")
        search_area = st.empty()
        search_area.markdown(
            render_scroll_box("暂无检索信息。", height=180),
            unsafe_allow_html=True,
        )

        st.subheader("Sources")
        source_area = st.empty()
        source_area.markdown(
            render_scroll_box("暂无来源。", height=180),
            unsafe_allow_html=True,
        )

    st.divider()

    st.subheader("最终 Markdown 笔记预览")

    final_area = st.empty()
    final_area.markdown(
        render_scroll_box(
            st.session_state.get(
                "last_note",
                "运行 Agent 后，这里会显示最终 Markdown 笔记。",
            ),
            height=520,
        ),
        unsafe_allow_html=True,
    )

    result_area = st.empty()

    if run_button:
        file_texts = []
        webpage_texts = []

        try:
            for uploaded_file in uploaded_files or []:
                text = read_uploaded_text_file(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                )
                file_texts.append((uploaded_file.name, text))

            for url in parse_urls(raw_urls):
                text = fetch_webpage_text(url)
                webpage_texts.append((url, text))

            raw_input = build_combined_input(
                manual_text=manual_text,
                file_texts=file_texts,
                webpage_texts=webpage_texts,
            )

        except Exception as e:
            st.error(f"输入加载失败：{e}")
            return

        request = NoteAgentRequest(
            raw_input=raw_input,
            max_iterations=int(max_iterations),
            llm_provider=llm_provider,
            search_api=search_api,
        )

        node_records = []
        current_step_output = ""
        search_logs = []
        sources = []

        try:
            for event in stream_note_agent_events(request):
                event_type = event.get("type")

                if event_type == "node_start":
                    if node_records:
                        node_records[-1]["status"] = "done"

                    node_name = event["node_name"]
                    step_label = event["step_label"]

                    node_records.append(
                        {
                            "node": node_name,
                            "label": step_label,
                            "status": "running",
                        }
                    )

                    current_step_output = f"【{step_label}】\n\n"

                elif event_type == "token":
                    current_step_output += event.get("text", "")

                elif event_type == "info":
                    search_logs.append(event.get("text", ""))

                elif event_type == "done":
                    if node_records:
                        node_records[-1]["status"] = "done"

                    latest_state = event["state"]
                    sources = latest_state.get("sources", [])

                    st.session_state.last_note = latest_state.get("final_note", "")

                    result_area.success("笔记生成完成。")
                    result_area.markdown("**保存路径：**")
                    result_area.code(latest_state.get("saved_path", ""))

                    result_area.markdown("**运行 ID：**")
                    result_area.code(event.get("run_id", ""))

                    result_area.markdown("**运行日志目录：**")
                    result_area.code(event.get("run_log_dir", ""))

                    if latest_state.get("intermediate_paths"):
                        result_area.markdown("**中间版本：**")
                        result_area.code("\n".join(latest_state.get("intermediate_paths", [])))

                    if latest_state.get("asset_paths"):
                        result_area.markdown("**生成资产：**")
                        result_area.code("\n".join(latest_state.get("asset_paths", [])))

                elif event_type == "error":
                    result_area.error(f"运行失败：{event.get('message')}")
                    result_area.markdown("**运行 ID：**")
                    result_area.code(event.get("run_id", ""))
                    result_area.markdown("**运行日志目录：**")
                    result_area.code(event.get("run_log_dir", ""))
                    break

                node_area.markdown(
                    render_scroll_box(render_node_list(node_records), height=300),
                    unsafe_allow_html=True,
                )

                step_area.markdown(
                    render_scroll_box(current_step_output, height=300),
                    unsafe_allow_html=True,
                )

                search_area.markdown(
                    render_scroll_box(
                        "\n".join(search_logs) if search_logs else "暂无检索信息。",
                        height=180,
                    ),
                    unsafe_allow_html=True,
                )

                source_area.markdown(
                    render_scroll_box(
                        "\n".join(sorted(set(sources))) if sources else "暂无来源。",
                        height=180,
                    ),
                    unsafe_allow_html=True,
                )

                final_area.markdown(
                    render_scroll_box(
                        st.session_state.get(
                            "last_note",
                            "最终笔记生成后会显示在这里。",
                        ),
                        height=520,
                    ),
                    unsafe_allow_html=True,
                )

        except Exception as e:
            st.error(f"运行失败：{e}")


if __name__ == "__main__":
    main()
