# app.py
# Note Agent v3.3.0 Streamlit UI with node-level and token-level streaming

import html

import streamlit as st

from note_agent import __version__
from note_agent.schemas import NoteAgentRequest
from note_agent.service import stream_note_agent_events


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


def main():
    st.title(f"📝 Note Agent v{__version__}")
    st.caption(
        "LangGraph-based research note agent with search, verification and iterative refinement."
    )

    with st.sidebar:
        st.header("⚙️ Settings")

        llm_provider = st.selectbox(
            "LLM Provider",
            options=[
                "deepseek",
                "openai",
                "qwen",
                "moonshot",
                "zhipu",
                "siliconflow",
            ],
            index=0,
        )

        search_api = st.selectbox(
            "Search API",
            options=[
                "duckduckgo",
                "tavily",
                "perplexity",
                "searxng",
            ],
            index=0,
        )

        max_iterations = st.slider(
            "Max Iterations",
            min_value=1,
            max_value=5,
            value=2,
            step=1,
        )

        st.divider()

        st.markdown("### 当前功能")
        st.markdown(
            """
            - 动态笔记结构生成
            - 网络检索补充
            - 事实检验
            - 多轮迭代
            - Markdown 自动保存
            - 运行节点展示
            - 逐字流式输出
            """
        )

    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.subheader("输入文本 / 关键词")

        raw_input = st.text_area(
            label="请输入研究主题、关键词或原始笔记",
            height=300,
            placeholder=(
                "例如：\n"
                "LangChain Agent\n"
                "LangGraph workflow\n"
                "Memory\n"
                "RAG\n"
            ),
        )

        run_button = st.button(
            "🚀 生成研究笔记",
            type="primary",
            use_container_width=True,
        )

        st.subheader("运行节点")
        node_area = st.empty()
        node_area.markdown(
            render_scroll_box("等待运行...", height=360),
            unsafe_allow_html=True,
        )

    with right_col:
        st.subheader("当前步骤输出")

        step_area = st.empty()
        step_area.markdown(
            render_scroll_box("运行后，这里会显示当前节点的逐字输出。", height=360),
            unsafe_allow_html=True,
        )

        st.subheader("检索 Query / 搜索过程")
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
        if not raw_input.strip():
            st.error("输入内容不能为空。")
            return

        request = NoteAgentRequest(
            raw_input=raw_input.strip(),
            max_iterations=max_iterations,
            llm_provider=llm_provider,
            search_api=search_api,
        )

        node_records = []
        current_step_output = ""
        search_logs = []
        sources = []
        latest_state = None

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

                elif event_type == "error":
                    result_area.error(f"运行失败：{event.get('message')}")
                    break

                node_area.markdown(
                    render_scroll_box(render_node_list(node_records), height=360),
                    unsafe_allow_html=True,
                )

                step_area.markdown(
                    render_scroll_box(current_step_output, height=360),
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