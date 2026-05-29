"""Streamlit UI for Note Agent."""

from __future__ import annotations

import re

import streamlit as st

from note_agent import __version__
from note_agent.io.input_loader import (
    build_combined_input,
    fetch_webpage_text,
    read_uploaded_text_file,
)
from note_agent.domain.api import NoteAgentRequest
from note_agent.agent.runner import stream_note_agent_events

st.set_page_config(page_title="Note Agent", page_icon="📝", layout="wide")

_MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _status_icon(status: str) -> str:
    return {"running": "🔵", "done": "🟢", "pending": "⚪"}.get(status, "⚪")


def _parse_urls(raw: str) -> list[str]:
    parts: list[str] = []
    for line in (raw or "").splitlines():
        parts.extend(s.strip() for s in line.split(","))
    return [s for s in parts if s]


def _render_mermaid(code: str, height: int = 420) -> None:
    import streamlit.components.v1 as components

    safe = code.replace("`", r"\`")
    html = f"""
    <div class="mermaid">{safe}</div>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
      mermaid.initialize({{ startOnLoad: true, theme: "default", securityLevel: "loose" }});
    </script>
    """
    components.html(html, height=height, scrolling=True)


def _render_note_with_mermaid(container, note: str) -> None:
    """Render a markdown note, replacing fenced ```mermaid blocks with live diagrams."""
    if not note:
        container.markdown("*Generating…*")
        return

    parts = _MERMAID_RE.split(note)
    with container.container():
        for idx, part in enumerate(parts):
            if idx % 2 == 0:
                if part.strip():
                    st.markdown(part)
            else:
                _render_mermaid(part.strip())


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _build_sidebar() -> tuple:
    with st.sidebar:
        st.title("Note Agent")
        st.caption(f"v{__version__}")
        st.divider()

        llm = st.selectbox(
            "LLM",
            ["deepseek", "openai", "qwen", "moonshot", "zhipu", "siliconflow"],
            index=0,
        )
        search = st.selectbox(
            "Search",
            ["duckduckgo", "tavily", "perplexity", "searxng"],
            index=0,
        )
        iters = st.number_input(
            "Max iterations",
            min_value=0,
            value=1,
            step=1,
            help="0 = single-pass, no verify loop.",
        )
        assets = st.checkbox("Generate assets", value=False)
        notion = st.checkbox("Publish to Notion", value=False)

        st.divider()
        with st.expander("About", expanded=False):
            st.markdown(
                "LangGraph research agent with search, verification, and "
                "multimodal asset generation. Inputs: text, `.txt`/`.md` "
                "files, or webpage URLs."
            )
    return llm, search, int(iters), assets, notion


# ---------------------------------------------------------------------------
# Input section
# ---------------------------------------------------------------------------


def _build_input_section() -> tuple:
    st.header("New Research Note", divider="rainbow")
    tabs = st.tabs(["Write", "Upload", "URLs"])

    with tabs[0]:
        text = st.text_area(
            "Topic or keywords",
            height=200,
            placeholder="LangChain Agent\nLangGraph workflow\nMemory\nRAG",
            label_visibility="collapsed",
        )

    with tabs[1]:
        files = st.file_uploader(
            "Upload `.txt` or `.md`",
            type=["txt", "md"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

    with tabs[2]:
        urls = st.text_area(
            "One URL per line",
            height=120,
            placeholder="https://example.com/article",
            label_visibility="collapsed",
        )

    col, _ = st.columns([1, 3])
    with col:
        run = st.button("Generate", type="primary", use_container_width=True)

    return text, files, urls, run


# ---------------------------------------------------------------------------
# Run logic
# ---------------------------------------------------------------------------


def _run_agent(
    manual_text: str,
    uploaded_files: list,
    raw_urls: str,
    llm: str,
    search: str,
    max_iters: int,
    enable_assets: bool,
    enable_notion: bool,
) -> None:
    file_texts: list[tuple[str, str]] = []
    webpage_texts: list[tuple[str, str]] = []

    try:
        for f in uploaded_files or []:
            content = read_uploaded_text_file(f.name, f.getvalue())
            file_texts.append((f.name, content))
        for url in _parse_urls(raw_urls):
            webpage_texts.append((url, fetch_webpage_text(url)))
        combined = build_combined_input(
            manual_text=manual_text,
            file_texts=file_texts,
            webpage_texts=webpage_texts,
        )
    except Exception as exc:
        st.error(f"Input error: {exc}")
        st.stop()

    request = NoteAgentRequest(
        raw_input=combined,
        max_iterations=max_iters,
        llm_provider=llm,
        search_api=search,
        enable_assets=enable_assets,
        enable_notion=enable_notion,
    )

    # Placeholders
    result_tabs = st.tabs(["Progress", "Final Note", "Sources", "Run Info"])
    with result_tabs[0]:
        progress_ph = st.empty()
        step_ph = st.empty()
    with result_tabs[1]:
        note_ph = st.empty()
    with result_tabs[2]:
        source_ph = st.empty()
    with result_tabs[3]:
        info_ph = st.empty()

    nodes: list[dict] = []
    step_output = ""
    sources: list[str] = []

    try:
        for event in stream_note_agent_events(request):
            etype = event.get("type")

            if etype == "node_start":
                if nodes:
                    nodes[-1]["status"] = "done"
                nodes.append({
                    "node": event["node_name"],
                    "label": event["step_label"],
                    "status": "running",
                })
                step_output = f"### {event['step_label']}\n\n"

            elif etype == "token":
                step_output += event.get("text", "")

            elif etype == "done":
                if nodes:
                    nodes[-1]["status"] = "done"
                st.session_state.last_note = event["state"].get("final_note", "")
                sources = event["state"].get("sources", [])

            elif etype == "error":
                st.error(f"Run failed: {event.get('message')}")
                break

            # Render
            with result_tabs[0]:
                badges = "  ".join(
                    f"{_status_icon(n['status'])} `{n['label']}`" for n in nodes
                )
                progress_ph.markdown(badges or "Waiting…")
                step_ph.markdown(step_output)

            with result_tabs[1]:
                last_note = st.session_state.get("last_note", "")
                if last_note and _MERMAID_RE.search(last_note):
                    _render_note_with_mermaid(note_ph, last_note)
                else:
                    note_ph.markdown(last_note or "*Generating…*")

            with result_tabs[2]:
                if sources:
                    source_ph.markdown(
                        "\n".join(f"- {s}" for s in sorted(set(sources)))
                    )
                else:
                    source_ph.caption("Sources will appear here.")

            with result_tabs[3]:
                lines = [
                    f"**Run ID:** `{event.get('run_id', '—')}`",
                    f"**Log:** `{event.get('run_log_dir', '—')}`",
                ]
                if etype == "done":
                    state = event["state"]
                    lines.append(f"**Saved:** `{state.get('saved_path', '—')}`")
                    nurl = state.get("notion_url") or ""
                    if nurl:
                        lines.append(f"**Notion:** {nurl}")
                    ipaths = state.get("intermediate_paths") or []
                    apaths = state.get("asset_paths") or []
                    if ipaths:
                        lines.append(f"**Versions:** {len(ipaths)} saved")
                    if apaths:
                        lines.append(f"**Assets:** {len(apaths)} generated")

                    usage = event.get("usage") or {}
                    total = usage.get("total_tokens") or 0
                    if total > 0:
                        ti = usage["total_input_tokens"]
                        to = usage["total_output_tokens"]
                        tt = usage["total_tokens"]
                        lines.append(
                            f"**Tokens:** {tt:,} total "
                            f"(in: {ti:,}, out: {to:,})"
                        )
                        by_node = usage.get("by_node") or {}
                        if by_node:
                            rows = [
                                f"| `{k}` | {v['calls']} | {v['input_tokens']:,} "
                                f"| {v['output_tokens']:,} | {v['input_tokens'] + v['output_tokens']:,} |"
                                for k, v in by_node.items()
                            ]
                            lines.append(
                                "| Node | Calls | In | Out | Total |\n"
                                "|------|-------|----|-----|-------|\n"
                                + "\n".join(rows)
                            )
                info_ph.markdown("\n\n".join(filter(None, lines)))

    except Exception as exc:
        st.error(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    llm, search, max_iters, enable_assets, enable_notion = _build_sidebar()
    manual_text, uploaded_files, raw_urls, run = _build_input_section()

    if run:
        st.session_state["_active_run"] = True
        st.session_state["_run_params"] = (
            manual_text, uploaded_files, raw_urls,
            llm, search, max_iters, enable_assets, enable_notion,
        )

    if st.session_state.get("_active_run"):
        try:
            _run_agent(*st.session_state["_run_params"])
        finally:
            st.session_state["_active_run"] = False


if __name__ == "__main__":
    main()
