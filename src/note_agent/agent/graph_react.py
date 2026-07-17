"""ReAct-based graph for note agent."""

from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from note_agent.agent.prompts import react_system_prompt
from note_agent.agent.tools import ALL_TOOLS
from note_agent.domain.models import NoteResearchState
from note_agent.io.events import emit_event, emit_node_start


_TOOL_NODE = ToolNode(ALL_TOOLS)


@lru_cache(maxsize=8)
def _bound_tool_model(provider: str):
    from note_agent.config.settings import get_model

    return get_model(provider, for_tools=True).bind_tools(ALL_TOOLS)


def _dedupe_sources(items: list) -> list:
    """Dedupe sources that may be str OR dict (LLM sometimes returns dicts).

    Order-preserving; dicts are keyed by their url/link/href or a stable repr,
    so `set()` never chokes on an unhashable dict again.
    """
    seen: set[str] = set()
    out: list = []
    for it in items:
        if isinstance(it, dict):
            key = str(it.get("url") or it.get("link") or it.get("href") or sorted(it.items()))
        else:
            key = str(it)
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _agent_phase_label(state: NoteResearchState) -> str:
    """Human-readable label for what the agent is about to decide."""
    if not state.get("note_type"):
        return "Agent 分析需求"
    if not state.get("current_note"):
        return "Agent 决策：生成初稿"
    if not state.get("final_note"):
        return "Agent 决策：检索 / 修正 / 最终化"
    if not state.get("saved_path"):
        return "Agent 决策：资产 / 保存"
    return "Agent 收尾"


def create_agent_node(state: NoteResearchState):
    """Agent reasoning node: decides which tool to call next."""

    # Emit a node_start BEFORE the blocking invoke() so the UI shows the agent
    # is reasoning (this call has no token streaming and can be slow).
    emit_node_start("agent", _agent_phase_label(state))

    # Build context message for agent
    context_parts = []

    if not state.get("note_type"):
        context_parts.append("📋 当前状态：尚未开始，需要先推断笔记结构")
    elif not state.get("current_note"):
        context_parts.append(f"📋 笔记类型已确定：{state['note_type']}，需要生成初稿")
    elif state.get("current_note") and not state.get("final_note"):
        iter_count = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 0)
        context_parts.append(f"📋 初稿已生成，当前迭代：{iter_count}/{max_iter}")

        if iter_count < max_iter:
            context_parts.append("💡 可以考虑：搜索参考资料 → 修正笔记")
        else:
            context_parts.append("💡 已达最大迭代次数，应该进入最终化阶段")
    elif state.get("final_note") and not state.get("saved_path"):
        if state.get("enable_assets") and not state.get("asset_plan"):
            context_parts.append("📋 笔记已最终化，需要规划和生成资产")
        elif state.get("asset_plan") and not state.get("generated_assets"):
            context_parts.append("📋 资产规划已完成，需要生成资产文件")
        elif state.get("generated_assets"):
            context_parts.append("📋 资产已生成，需要组装笔记")
        else:
            context_parts.append("📋 笔记已就绪，可以直接保存")
    elif state.get("saved_path"):
        if state.get("enable_notion") and not state.get("notion_url"):
            context_parts.append("📋 笔记已保存，需要发布到 Notion")
        else:
            context_parts.append("✅ 所有任务已完成")

    context_msg = "\n".join(context_parts)

    # Construct messages - ensure valid sequence
    messages = list(state.get("messages", []))

    # Add system prompt if this is the first call
    if not messages or not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=react_system_prompt())] + messages

    # Only add context message if it won't break the message flow
    if context_msg:
        messages = messages + [HumanMessage(content=context_msg)]

    # Call LLM
    response = _bound_tool_model(state["llm_provider"]).invoke(messages)

    # Check if task is complete
    if not response.tool_calls:
        # Agent decided not to call any tool - check if we're done
        if state.get("saved_path"):
            if state.get("enable_notion") and not state.get("notion_url"):
                # Should publish but agent didn't call tool - remind it
                emit_event("warning", text="Agent 未调用发布工具，将自动补充")
                # Force tool call
                from langchain_core.messages import AIMessage
                response = AIMessage(
                    content="需要发布到 Notion",
                    tool_calls=[{
                        "name": "publish_note_to_notion",
                        "args": {
                            "final_note": state["final_note"],
                            "note_title": state.get("note_title", ""),
                            "run_id": state["run_id"],
                        },
                        "id": "auto_publish_call",
                    }]
                )
            else:
                emit_event("info", text="✅ Agent 判断任务已完成")

    return {"messages": [response]}


def create_tool_node(state: NoteResearchState):
    """Execute tools and update state."""

    messages = state["messages"]
    last_message = messages[-1]

    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    # Emit a node_start labeled with the tool(s) about to run so the UI stepper
    # and token meter advance as the agent acts.
    _TOOL_LABELS = {
        "infer_note_structure": "🧭 推断结构",
        "generate_note_draft": "✍️ 生成初稿",
        "search_references": "📚 检索资料",
        "refine_note_with_references": "🔬 核验修正",
        "finalize_note_content": "✨ 最终化",
        "plan_note_assets": "📐 规划资产",
        "generate_note_assets": "🎨 生成资产",
        "assemble_final_note": "🧩 组装笔记",
        "save_final_note": "💾 保存笔记",
        "publish_note_to_notion": "🚀 发布 Notion",
    }
    _names = [c.get("name", "") for c in last_message.tool_calls]
    _label = " · ".join(_TOOL_LABELS.get(n, n) for n in _names) or "执行工具"
    emit_node_start("tools", _label)

    # Inject system parameters into tool calls
    injected_message = AIMessage(
        content=last_message.content,
        tool_calls=[
            {
                **call,
                "args": {
                    **call.get("args", {}),
                    "llm_provider": state.get("llm_provider", "deepseek"),
                    "run_id": state.get("run_id", ""),
                    "search_api": state.get("search_api", "duckduckgo"),
                }
            }
            for call in last_message.tool_calls
        ]
    )

    # Replace last message with injected version
    injected_state = {**state, "messages": messages[:-1] + [injected_message]}

    # Execute tools using the shared ToolNode.
    result = _TOOL_NODE.invoke(injected_state)

    # Extract tool results and update state
    tool_messages = result.get("messages", [])

    state_updates = {}

    for msg in tool_messages:
        if isinstance(msg, ToolMessage):
            try:
                import json
                tool_result = (
                    json.loads(msg.content)
                    if isinstance(msg.content, str)
                    else msg.content
                )

                # Update state based on tool results
                if isinstance(tool_result, dict):
                    # Map tool results to state fields
                    if "note_type" in tool_result:
                        state_updates["note_type"] = tool_result["note_type"]
                    if "note_outline" in tool_result:
                        state_updates["note_outline"] = tool_result["note_outline"]
                    if "current_note" in tool_result:
                        state_updates["current_note"] = tool_result["current_note"]
                    if "refined_note" in tool_result:
                        state_updates["current_note"] = tool_result["refined_note"]
                        state_updates["iteration_count"] = state.get("iteration_count", 0) + 1
                    if "reference_results" in tool_result:
                        current_results = state.get("evidence_items", [])
                        current_results.extend(tool_result["reference_results"])
                        state_updates["evidence_items"] = current_results
                        state_updates["reference_results"] = tool_result["reference_results"]
                    if "new_queries" in tool_result:
                        current_queries = state.get("used_reference_queries", [])
                        current_queries.extend(tool_result["new_queries"])
                        state_updates["used_reference_queries"] = current_queries
                    if "sources" in tool_result:
                        current_sources = list(state.get("sources", []))
                        current_sources.extend(tool_result["sources"] or [])
                        state_updates["sources"] = _dedupe_sources(current_sources)
                    if "final_note" in tool_result:
                        state_updates["final_note"] = tool_result["final_note"]
                    if "final_note_with_assets" in tool_result:
                        state_updates["final_note"] = tool_result["final_note_with_assets"]
                    if "asset_plan" in tool_result:
                        state_updates["asset_plan"] = tool_result["asset_plan"]
                    if "generated_assets" in tool_result:
                        state_updates["generated_assets"] = tool_result["generated_assets"]
                    if "asset_paths" in tool_result:
                        state_updates["asset_paths"] = tool_result["asset_paths"]
                    if "saved_path" in tool_result:
                        state_updates["saved_path"] = tool_result["saved_path"]
                    if "note_title" in tool_result:
                        state_updates["note_title"] = tool_result["note_title"]
                    if "notion_url" in tool_result:
                        state_updates["notion_url"] = tool_result["notion_url"]
                    if "intermediate_path" in tool_result:
                        paths = state.get("intermediate_paths", [])
                        paths.append(tool_result["intermediate_path"])
                        state_updates["intermediate_paths"] = paths

            except Exception as e:
                emit_event("warning", text=f"解析工具结果失败：{e}")

    state_updates["messages"] = tool_messages
    return state_updates


def should_continue(state: NoteResearchState) -> str:
    """Router: decide whether to continue or end."""

    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1]

    # If last message has tool calls, execute tools
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    # If agent decided not to call tools, check if we're done
    if isinstance(last_message, AIMessage) and not last_message.tool_calls:
        # Check if we're truly done
        if state.get("saved_path"):
            if state.get("enable_notion") and not state.get("notion_url"):
                # Need to publish but agent didn't call tool
                emit_event("warning", text="⚠️ 任务未完成但 Agent 未调用工具")
            else:
                # Everything done
                emit_event("info", text="🎉 所有任务已完成")
        else:
            # Not done yet but agent didn't call tools
            emit_event("warning", text="⚠️ 任务未完成但 Agent 未调用工具")
        return END

    # Default: end (shouldn't reach here)
    return END


def build_react_graph():
    """Build the ReAct agent graph."""

    workflow = StateGraph(NoteResearchState)

    # Add nodes
    workflow.add_node("agent", create_agent_node)
    workflow.add_node("tools", create_tool_node)

    # Add edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END,
        }
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()


_react_graph = None


def get_react_graph():
    """Get or create the ReAct graph singleton."""
    global _react_graph
    if _react_graph is None:
        _react_graph = build_react_graph()
    return _react_graph
