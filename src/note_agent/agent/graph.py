import json
import re

from langgraph.graph import END, START, StateGraph

from note_agent.assets.tools import (
    build_asset_markdown_items,
    inject_assets_into_markdown,
    parse_asset_plan,
    parse_generated_assets,
    save_generated_assets,
)
from config.llm import ask_llm
from note_agent.io.events import emit_event, emit_node_start
from note_agent.io.text import normalize_query, save_markdown
from note_agent.agent.prompts import (
    finalize_note_prompt,
    generate_assets_prompt,
    generate_initial_note_prompt,
    generate_outline_prompt,
    generate_reference_queries_prompt,
    generate_title_prompt,
    infer_note_type_prompt,
    plan_assets_prompt,
    refine_note_prompt,
    verify_note_prompt,
)
from note_agent.retrieval.retriever import (
    collect_reference_urls,
    format_references_for_prompt,
    retrieve_references,
)
from note_agent.domain.models import NoteResearchState, ReferenceQuery
from note_agent.io.storage import append_event, save_intermediate_note


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen = set()
    result = []

    for url in urls:
        url = (url or "").strip()
        if url and url not in seen:
            result.append(url)
            seen.add(url)

    return result


def _extract_json_object(text: str) -> dict:
    text = (text or "").strip()

    if text.startswith("```json"):
        text = text[len("```json") :].strip()
    elif text.startswith("```"):
        text = text[len("```") :].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0)

    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _model_dump(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


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
        "reference_queries": [],
        "used_reference_queries": [],
        "reference_results": [],
        "evidence_items": [],
        "sources": [],
        "intermediate_paths": [intermediate_path],
        "asset_plan": [],
        "generated_assets": {},
        "asset_paths": [],
    }


def route_after_initial_note(state: NoteResearchState) -> str:
    if state["max_iterations"] <= 0:
        return "finalize"
    return "continue"


def generate_reference_queries(state: NoteResearchState):
    emit_node_start("generate_reference_queries", "正在分析信息缺口并生成统一检索请求")

    text = ask_llm(
        generate_reference_queries_prompt(
            current_note=state["current_note"],
            used_queries=state.get("used_reference_queries", []),
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    data = _extract_json_object(text)
    raw_items = data.get("reference_queries", [])
    if not isinstance(raw_items, list):
        raw_items = []

    used = set(normalize_query(q) for q in state.get("used_reference_queries", []))
    reference_queries = []
    used_query_texts = []

    for item in raw_items:
        if isinstance(item, str):
            item = {"query": item, "source_types": ["web", "academic"], "reason": ""}
        if not isinstance(item, dict):
            continue

        query = str(item.get("query", "")).strip()
        normalized = normalize_query(query)
        if not normalized or normalized in used:
            continue

        source_types = item.get("source_types") or ["web", "academic"]
        if isinstance(source_types, str):
            source_types = [source_types]
        source_types = [s for s in source_types if s in {"web", "paper", "academic"}]
        if not source_types:
            source_types = ["web", "academic"]

        reference_query = ReferenceQuery(
            query=query,
            source_types=source_types,
            reason=str(item.get("reason", "")),
        )
        reference_queries.append(_model_dump(reference_query))
        used_query_texts.append(query)
        used.add(normalized)

    reference_queries = reference_queries[:4]
    used_query_texts = used_query_texts[:4]

    return {
        "reference_queries": reference_queries,
        "used_reference_queries": state.get("used_reference_queries", []) + used_query_texts,
    }


def retrieve_references_node(state: NoteResearchState):
    emit_node_start("retrieve_references", "正在统一检索网页、论文和学术资料")

    current_round_results = []
    evidence_items = list(state.get("evidence_items", []))
    sources = list(state.get("sources", []))

    if not state["reference_queries"]:
        emit_event("info", text="本轮没有需要检索的参考信息。")
        return {
            "reference_results": [],
            "evidence_items": evidence_items,
            "sources": _dedupe_urls(sources),
        }

    for item in state["reference_queries"]:
        try:
            reference_query = ReferenceQuery(**item)
        except Exception:
            continue

        source_types_text = ", ".join(reference_query.source_types)
        emit_event("info", text=f"正在检索：{reference_query.query}；来源类型：{source_types_text}")

        try:
            results = retrieve_references(
                reference_query,
                web_backend=state["search_api"],
                max_results_per_type=5,
            )
        except Exception as e:
            emit_event("info", text=f"检索失败：{reference_query.query}；原因：{e}")
            results = []

        current_round_results.extend(results)
        evidence_items.extend(results)
        sources.extend(collect_reference_urls(results))

    return {
        "reference_results": current_round_results,
        "evidence_items": evidence_items,
        "sources": _dedupe_urls(sources),
    }


def verify_note(state: NoteResearchState):
    emit_node_start("verify_note", "正在进行事实检验")

    references_text = format_references_for_prompt(state["reference_results"])

    report = ask_llm(
        verify_note_prompt(
            raw_input=state["raw_input"],
            current_note=state["current_note"],
            references=references_text,
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    return {"verification_report": report}


def refine_note(state: NoteResearchState):
    emit_node_start("refine_note", "正在根据统一参考信息修正并补充笔记")

    references_text = format_references_for_prompt(state["reference_results"])
    next_iteration = state["iteration_count"] + 1

    new_note = ask_llm(
        refine_note_prompt(
            raw_input=state["raw_input"],
            current_note=state["current_note"],
            references=references_text,
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
    emit_node_start("finalize_note", "正在生成最终文本笔记")

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
        "final_text_only",
        final_note,
    )

    emit_event("info", text=f"已保存文本版最终笔记：{intermediate_path}")

    return {
        "final_note": final_note,
        "intermediate_paths": state.get("intermediate_paths", []) + [intermediate_path],
    }


def route_after_finalize(state: NoteResearchState) -> str:
    if state.get("enable_assets"):
        return "assets"
    return "save"


def plan_note_assets(state: NoteResearchState):
    emit_node_start("plan_note_assets", "正在规划公式、代码、图表和流程图")

    text = ask_llm(
        plan_assets_prompt(
            current_note=state["final_note"],
            note_type=state["note_type"],
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    plan_items = parse_asset_plan(text)
    plan_data = [_model_dump(item) for item in plan_items]

    emit_event("info", text=f"资产规划数量：{len(plan_data)}")

    return {"asset_plan": plan_data}


def generate_note_assets(state: NoteResearchState):
    emit_node_start("generate_note_assets", "正在生成笔记资产")

    if not state.get("asset_plan"):
        emit_event("info", text="没有需要生成的公式、代码、图表或流程图。")
        return {
            "generated_assets": {},
            "asset_paths": [],
        }

    asset_plan_text = json.dumps(state["asset_plan"], ensure_ascii=False, indent=2)

    text = ask_llm(
        generate_assets_prompt(
            current_note=state["final_note"],
            asset_plan=asset_plan_text,
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    generated_assets = parse_generated_assets(text)
    asset_paths = save_generated_assets(state["run_id"], generated_assets)

    emit_event("info", text=f"已生成并保存资产文件：{len(asset_paths)} 个")

    return {
        "generated_assets": _model_dump(generated_assets),
        "asset_paths": asset_paths,
    }


def assemble_assets_into_note(state: NoteResearchState):
    emit_node_start("assemble_assets_into_note", "正在组装多模态 Markdown 笔记")

    generated_assets = parse_generated_assets(
        json.dumps(state.get("generated_assets", {}), ensure_ascii=False)
    )

    asset_items = build_asset_markdown_items(
        generated_assets,
        state.get("asset_paths", []),
    )

    final_note = inject_assets_into_markdown(state["final_note"], asset_items)

    intermediate_path = save_intermediate_note(
        state["run_id"],
        "final_with_assets",
        final_note,
    )

    emit_event("info", text=f"已保存多模态最终版本：{intermediate_path}")

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
            "asset_paths": state.get("asset_paths", []),
            "sources": state.get("sources", []),
        },
    )

    return {"saved_path": saved_path}


def build_graph():
    builder = StateGraph(NoteResearchState)

    builder.add_node("infer_note_type", infer_note_type)
    builder.add_node("generate_dynamic_outline", generate_dynamic_outline)
    builder.add_node("generate_initial_note", generate_initial_note)
    builder.add_node("generate_reference_queries", generate_reference_queries)
    builder.add_node("retrieve_references", retrieve_references_node)
    builder.add_node("verify_note", verify_note)
    builder.add_node("refine_note", refine_note)
    builder.add_node("finalize_note", finalize_note)
    builder.add_node("plan_note_assets", plan_note_assets)
    builder.add_node("generate_note_assets", generate_note_assets)
    builder.add_node("assemble_assets_into_note", assemble_assets_into_note)
    builder.add_node("save_markdown", save_markdown_node)

    builder.add_edge(START, "infer_note_type")
    builder.add_edge("infer_note_type", "generate_dynamic_outline")
    builder.add_edge("generate_dynamic_outline", "generate_initial_note")

    builder.add_conditional_edges(
        "generate_initial_note",
        route_after_initial_note,
        {
            "continue": "generate_reference_queries",
            "finalize": "finalize_note",
        },
    )

    builder.add_edge("generate_reference_queries", "retrieve_references")
    builder.add_edge("retrieve_references", "verify_note")
    builder.add_edge("verify_note", "refine_note")

    builder.add_conditional_edges(
        "refine_note",
        route_iteration,
        {
            "continue": "generate_reference_queries",
            "finalize": "finalize_note",
        },
    )

    builder.add_conditional_edges(
        "finalize_note",
        route_after_finalize,
        {
            "assets": "plan_note_assets",
            "save": "save_markdown",
        },
    )
    builder.add_edge("plan_note_assets", "generate_note_assets")
    builder.add_edge("generate_note_assets", "assemble_assets_into_note")
    builder.add_edge("assemble_assets_into_note", "save_markdown")
    builder.add_edge("save_markdown", END)

    return builder.compile()


graph = build_graph()
