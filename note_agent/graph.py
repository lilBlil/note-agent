import json

from langgraph.graph import StateGraph, START, END

from note_agent.prompts import (
    finalize_note_prompt,
    generate_initial_note_prompt,
    generate_outline_prompt,
    generate_search_queries_prompt,
    generate_title_prompt,
    infer_note_type_prompt,
    refine_note_prompt,
    verify_note_prompt,
)
from note_agent.search import (
    collect_source_urls,
    format_search_results_for_prompt,
    web_search,
)
from note_agent.state import NoteResearchState
from note_agent.storage import append_event, save_intermediate_note
from note_agent.tools import (
    ask_llm,
    emit_event,
    emit_node_start,
    normalize_query,
    save_markdown,
)


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen = set()
    result = []

    for url in urls:
        url = (url or "").strip()
        if url and url not in seen:
            result.append(url)
            seen.add(url)

    return result


def infer_note_type(state: NoteResearchState):
    emit_node_start("infer_note_type", "正在判断笔记类型")
    note_type = ask_llm(
        infer_note_type_prompt(state["raw_input"]),
        provider=state["llm_provider"],
        stream=True,
    )
    return {"note_type": note_type.strip()}


def generate_dynamic_outline(state: NoteResearchState):
    emit_node_start("generate_dynamic_outline", "正在生成动态笔记结构")
    text = ask_llm(
        generate_outline_prompt(state["raw_input"], state["note_type"]),
        provider=state["llm_provider"],
        stream=True,
    )

    try:
        outline = json.loads(text)
    except Exception:
        outline = [
            {"title": "主题概述", "purpose": "概括主题背景和核心问题"},
            {"title": "核心概念", "purpose": "整理关键概念"},
            {"title": "实践要点", "purpose": "整理可操作内容"},
            {"title": "后续问题", "purpose": "记录需要继续研究的问题"},
        ]

    return {"note_outline": outline}


def generate_initial_note(state: NoteResearchState):
    emit_node_start("generate_initial_note", "正在生成笔记")
    outline_text = json.dumps(state["note_outline"], ensure_ascii=False, indent=2)

    note = ask_llm(
        generate_initial_note_prompt(
            raw_input=state["raw_input"],
            note_type=state["note_type"],
            outline=outline_text,
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    intermediate_path = save_intermediate_note(
        state["run_id"],
        "iteration_0_initial",
        note,
    )

    emit_event("info", text=f"已保存初版中间笔记：{intermediate_path}")

    return {
        "current_note": note,
        "iteration_count": 0,
        "search_queries": [],
        "used_search_queries": [],
        "search_results": [],
        "evidence_items": [],
        "sources": [],
        "intermediate_paths": [intermediate_path],
    }


def route_after_initial_note(state: NoteResearchState) -> str:
    """
    max_iterations = 0 时跳过检索、核验和修正，直接生成最终 Markdown。
    max_iterations > 0 时进入原有迭代流程。
    """
    if state["max_iterations"] <= 0:
        return "finalize"
    return "continue"


def generate_search_queries(state: NoteResearchState):
    emit_node_start("generate_search_queries", "正在分析信息缺口并生成检索问题")

    text = ask_llm(
        generate_search_queries_prompt(
            current_note=state["current_note"],
            used_queries=state.get("used_search_queries", []),
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    raw_queries = [
        line.strip("- ").strip()
        for line in text.splitlines()
        if line.strip()
    ]

    used = set(normalize_query(q) for q in state.get("used_search_queries", []))
    new_queries = []

    for q in raw_queries:
        normalized = normalize_query(q)
        if normalized and normalized not in used:
            new_queries.append(q)
            used.add(normalized)

    selected_queries = new_queries[:3]

    return {
        "search_queries": selected_queries,
        "used_search_queries": state.get("used_search_queries", []) + selected_queries,
    }


def web_search_node(state: NoteResearchState):
    emit_node_start("web_search", f"正在使用 {state['search_api']} 进行网络检索")

    current_round_results = []
    evidence_items = list(state.get("evidence_items", []))
    all_sources = list(state.get("sources", []))

    if not state["search_queries"]:
        emit_event("info", text="本轮没有需要检索的信息缺口。")
        return {
            "search_results": [],
            "evidence_items": evidence_items,
            "sources": _dedupe_urls(all_sources),
        }

    for query in state["search_queries"]:
        emit_event("info", text=f"正在搜索：{query}")

        try:
            results = web_search(
                query,
                search_api=state["search_api"],
            )
        except Exception as e:
            emit_event("info", text=f"搜索失败：{query}；原因：{e}")
            results = []

        current_round_results.extend(results)
        evidence_items.extend(results)
        all_sources.extend(collect_source_urls(results))

    return {
        "search_results": current_round_results,
        "evidence_items": evidence_items,
        "sources": _dedupe_urls(all_sources),
    }


def verify_note(state: NoteResearchState):
    emit_node_start("verify_note", "正在进行事实检验")

    search_text = format_search_results_for_prompt(state["search_results"])

    report = ask_llm(
        verify_note_prompt(
            raw_input=state["raw_input"],
            current_note=state["current_note"],
            search_results=search_text,
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    return {"verification_report": report}


def refine_note(state: NoteResearchState):
    emit_node_start("refine_note", "正在根据检索结果修正并补充笔记")

    search_text = format_search_results_for_prompt(state["search_results"])
    next_iteration = state["iteration_count"] + 1

    new_note = ask_llm(
        refine_note_prompt(
            raw_input=state["raw_input"],
            current_note=state["current_note"],
            search_results=search_text,
            verification_report=state["verification_report"],
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    intermediate_path = save_intermediate_note(
        state["run_id"],
        f"iteration_{next_iteration}_refined",
        new_note,
    )

    emit_event("info", text=f"已保存第 {next_iteration} 轮中间笔记：{intermediate_path}")

    return {
        "current_note": new_note,
        "iteration_count": next_iteration,
        "intermediate_paths": state.get("intermediate_paths", []) + [intermediate_path],
    }


def route_iteration(state: NoteResearchState) -> str:
    if state["iteration_count"] >= state["max_iterations"]:
        return "finalize"
    return "continue"


def finalize_note(state: NoteResearchState):
    emit_node_start("finalize_note", "正在生成最终笔记")

    final_note = ask_llm(
        finalize_note_prompt(
            current_note=state["current_note"],
            sources=state["sources"],
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    intermediate_path = save_intermediate_note(
        state["run_id"],
        "final",
        final_note,
    )

    emit_event("info", text=f"已保存最终中间版本：{intermediate_path}")

    return {
        "final_note": final_note,
        "intermediate_paths": state.get("intermediate_paths", []) + [intermediate_path],
    }


def save_markdown_node(state: NoteResearchState):
    emit_node_start("save_markdown", "正在生成文件名并保存 Markdown")

    title = ask_llm(
        generate_title_prompt(state["final_note"]),
        provider=state["llm_provider"],
        stream=True,
    ).strip()

    saved_path = save_markdown(title, state["final_note"])

    append_event(
        state["run_id"],
        {
            "type": "saved",
            "saved_path": saved_path,
        },
    )

    return {"saved_path": saved_path}


def build_graph():
    builder = StateGraph(NoteResearchState)

    builder.add_node("infer_note_type", infer_note_type)
    builder.add_node("generate_dynamic_outline", generate_dynamic_outline)
    builder.add_node("generate_initial_note", generate_initial_note)
    builder.add_node("generate_search_queries", generate_search_queries)
    builder.add_node("web_search", web_search_node)
    builder.add_node("verify_note", verify_note)
    builder.add_node("refine_note", refine_note)
    builder.add_node("finalize_note", finalize_note)
    builder.add_node("save_markdown", save_markdown_node)

    builder.add_edge(START, "infer_note_type")
    builder.add_edge("infer_note_type", "generate_dynamic_outline")
    builder.add_edge("generate_dynamic_outline", "generate_initial_note")

    builder.add_conditional_edges(
        "generate_initial_note",
        route_after_initial_note,
        {
            "continue": "generate_search_queries",
            "finalize": "finalize_note",
        },
    )

    builder.add_edge("generate_search_queries", "web_search")
    builder.add_edge("web_search", "verify_note")
    builder.add_edge("verify_note", "refine_note")

    builder.add_conditional_edges(
        "refine_note",
        route_iteration,
        {
            "continue": "generate_search_queries",
            "finalize": "finalize_note",
        },
    )

    builder.add_edge("finalize_note", "save_markdown")
    builder.add_edge("save_markdown", END)

    return builder.compile()


graph = build_graph()