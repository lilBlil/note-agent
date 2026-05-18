import json

from langgraph.graph import StateGraph, START, END

from note_agent.state import NoteResearchState
from note_agent.tools import ask_llm, web_search, save_markdown
from note_agent.prompts import (
    infer_note_type_prompt,
    generate_outline_prompt,
    generate_initial_note_prompt,
    generate_search_queries_prompt,
    verify_note_prompt,
    refine_note_prompt,
    finalize_note_prompt,
    generate_title_prompt,
)


def infer_note_type(state: NoteResearchState):
    print("\n正在判断笔记类型...\n")
    note_type = ask_llm(infer_note_type_prompt(state["raw_input"]))
    return {"note_type": note_type.strip()}


def generate_dynamic_outline(state: NoteResearchState):
    print("\n正在生成动态笔记结构...\n")
    text = ask_llm(generate_outline_prompt(state["raw_input"], state["note_type"]))

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
    print("\n正在生成笔记...\n")
    outline_text = json.dumps(state["note_outline"], ensure_ascii=False, indent=2)

    note = ask_llm(
        generate_initial_note_prompt(
            raw_input=state["raw_input"],
            note_type=state["note_type"],
            outline=outline_text,
        )
    )

    return {
        "current_note": note,
        "iteration_count": 0,
        "search_queries": [],
        "search_results": [],
        "sources": [],
    }


def generate_search_queries(state: NoteResearchState):
    print("\n正在生成检索问题...\n")
    text = ask_llm(generate_search_queries_prompt(state["current_note"]))

    queries = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return {"search_queries": queries[:3]}


def web_search_node(state: NoteResearchState):
    all_results = []
    all_sources = list(state.get("sources", []))

    for query in state["search_queries"]:
        result_text, sources = web_search(query)
        all_results.append(f"## Query: {query}\n\n{result_text}")
        all_sources.extend(sources)

    return {
        "search_results": all_results,
        "sources": all_sources,
    }


def verify_note(state: NoteResearchState):
    print("\n正在进行事实核验...\n")

    search_text = "\n\n".join(state["search_results"])

    report = ask_llm(
        verify_note_prompt(
            raw_input=state["raw_input"],
            current_note=state["current_note"],
            search_results=search_text,
        )
    )

    return {"verification_report": report}


def refine_note(state: NoteResearchState):
    print("\n正在基于核验结果和搜索结果迭代笔记...\n")

    search_text = "\n\n".join(state["search_results"])

    new_note = ask_llm(
        refine_note_prompt(
            raw_input=state["raw_input"],
            current_note=state["current_note"],
            search_results=search_text,
            verification_report=state["verification_report"],
        )
    )

    return {
        "current_note": new_note,
        "iteration_count": state["iteration_count"] + 1,
    }


def route_iteration(state: NoteResearchState) -> str:
    if state["iteration_count"] >= state["max_iterations"]:
        return "finalize"
    return "continue"


def finalize_note(state: NoteResearchState):
    print("\n正在生成最终笔记...\n")
    final_note = ask_llm(
        finalize_note_prompt(
            current_note=state["current_note"],
            sources=state["sources"],
        )
    )

    return {"final_note": final_note}


def save_markdown_node(state: NoteResearchState):
    title = ask_llm(generate_title_prompt(state["final_note"])).strip()
    saved_path = save_markdown(title, state["final_note"])
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
    builder.add_edge("generate_initial_note", "generate_search_queries")
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