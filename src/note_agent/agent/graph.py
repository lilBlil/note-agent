import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from langgraph.graph import END, START, StateGraph

from note_agent.agent.common import apply_patches, dedupe_urls, parse_note_structure
from note_agent.assets.tools import (
    build_asset_markdown_items,
    filter_asset_plan,
    inject_assets_into_markdown,
    parse_asset_plan,
    parse_generated_assets,
    save_generated_assets,
    validate_generated_assets,
)
from note_agent.config.llm import ask_llm
from note_agent.config.runtime import (
    max_reference_queries,
    max_results_per_source,
    max_retrieval_workers,
)
from note_agent.io.events import emit_event, emit_node_start
from note_agent.io.text import derive_title, normalize_query, save_markdown
from note_agent.agent.prompts import (
    finalize_note_prompt,
    generate_assets_prompt,
    generate_initial_note_prompt,
    generate_reference_queries_prompt,
    infer_type_and_outline_prompt,
    plan_assets_prompt,
    verify_and_refine_prompt,
)
from note_agent.retrieval.retriever import (
    collect_reference_urls,
    format_references_for_prompt,
    retrieve_references,
)
from note_agent.domain.models import NoteResearchState, ReferenceQuery
from note_agent.io.storage import append_event, save_intermediate_note
from note_agent.notion import publish_note

from note_agent.utils import extract_json_object, to_plain_data


_apply_patches = apply_patches


def infer_type_and_outline(state: NoteResearchState):
    emit_node_start("infer_type_and_outline", "正在判断笔记类型并生成结构")
    text = ask_llm(
        infer_type_and_outline_prompt(state["raw_input"]),
        provider=state["llm_provider"],
        stream=False,
    )
    note_type, outline = parse_note_structure(text)
    emit_event(
        "info",
        text=f"Note structure ready: type={note_type}; sections={len(outline)}",
        note_type=note_type,
        note_outline=outline,
    )
    return {"note_type": note_type, "note_outline": outline}


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
        stream=False,
    )

    data = extract_json_object(text)
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
        reference_queries.append(to_plain_data(reference_query))
        used_query_texts.append(query)
        used.add(normalized)

    query_limit = max_reference_queries()
    reference_queries = reference_queries[:query_limit]
    used_query_texts = used_query_texts[:query_limit]

    if reference_queries:
        lines = []
        for item in reference_queries:
            source_types = ", ".join(item.get("source_types", []))
            reason = item.get("reason", "")
            suffix = f" [{source_types}]" if source_types else ""
            if reason:
                suffix += f" - {reason}"
            lines.append(f"- {item.get('query', '')}{suffix}")
        emit_event(
            "info",
            text="Generated reference queries:\n" + "\n".join(lines),
            reference_queries=reference_queries,
        )
    else:
        emit_event(
            "info",
            text="No new reference queries generated.",
            reference_queries=[],
        )

    return {
        "reference_queries": reference_queries,
        "used_reference_queries": state.get("used_reference_queries", []) + used_query_texts,
    }


def retrieve_references_node(state: NoteResearchState):
    emit_node_start("retrieve_references", "正在统一检索网页、论文和学术资料")

    evidence_items = list(state.get("evidence_items", []))
    sources = list(state.get("sources", []))
    failed_sources = list(state.get("failed_sources", []))

    if not state["reference_queries"]:
        emit_event("info", text="本轮没有需要检索的参考信息。")
        return {
            "reference_results": [],
            "evidence_items": evidence_items,
            "sources": dedupe_urls(sources),
            "failed_sources": failed_sources,
        }

    queries = []
    for item in state["reference_queries"]:
        try:
            queries.append(ReferenceQuery(**item))
        except Exception:
            continue

    lock = Lock()
    current_round_results = []

    def fetch(rq: ReferenceQuery):
        failures = []
        emit_event("info", text=f"正在检索：{rq.query}；来源类型：{', '.join(rq.source_types)}")
        try:
            results = retrieve_references(
                rq,
                web_backend=state["search_api"],
                max_results_per_type=max_results_per_source(),
                on_failure=failures.append,
            )
            return results, failures
        except Exception as e:
            failure = {
                "query": rq.query,
                "source_type": ",".join(rq.source_types),
                "source_name": state["search_api"],
                "error_type": type(e).__name__,
                "error": str(e),
            }
            emit_event("warning", text=f"Reference retrieval failed: {rq.query}: {e}", failed_source=failure)
            emit_event("info", text=f"检索失败：{rq.query}；原因：{e}")
            return [], [failure]

    with ThreadPoolExecutor(max_workers=min(len(queries), max_retrieval_workers())) as pool:
        futures = {pool.submit(fetch, rq): rq for rq in queries}
        for fut in as_completed(futures):
            results, failures = fut.result()
            with lock:
                current_round_results.extend(results)
                evidence_items.extend(results)
                sources.extend(collect_reference_urls(results))
                failed_sources.extend(failures)

    source_counts = Counter(
        item.source_name or item.source_type or "unknown"
        for item in current_round_results
    )
    source_summary = ", ".join(
        f"{name}:{count}" for name, count in sorted(source_counts.items())
    ) or "none"
    emit_event(
        "info",
        text=(
            f"Retrieval summary: total={len(current_round_results)}; "
            f"sources={source_summary}"
        ),
    )
    if failed_sources:
        emit_event(
            "warning",
            text=f"Retrieval failures recorded: {len(failed_sources)}",
            failed_sources=failed_sources,
        )

    web_requested = any("web" in rq.source_types for rq in queries)
    web_result_count = source_counts.get(state["search_api"], 0)
    if not web_requested:
        emit_event(
            "info",
            text=(
                f"Web backend '{state['search_api']}' was not called because "
                "no generated query requested source_type='web'."
            ),
        )
    elif web_result_count == 0:
        emit_event(
            "warning",
            text=(
                f"Web backend '{state['search_api']}' was requested but returned "
                "no recorded results; check failed_sources."
            ),
        )

    return {
        "reference_results": current_round_results,
        "evidence_items": evidence_items,
        "sources": dedupe_urls(sources),
        "failed_sources": failed_sources,
    }


def verify_and_refine(state: NoteResearchState):
    emit_node_start("verify_and_refine", "正在核验并修正笔记")

    references_text = format_references_for_prompt(state["reference_results"])
    next_iteration = state["iteration_count"] + 1

    patch_text = ask_llm(
        verify_and_refine_prompt(
            raw_input=state["raw_input"],
            current_note=state["current_note"],
            references=references_text,
        ),
        provider=state["llm_provider"],
        stream=True,
    )

    new_note = apply_patches(state["current_note"], patch_text)

    intermediate_path = save_intermediate_note(
        state["run_id"],
        f"iteration_{next_iteration}_refined",
        new_note,
    )

    emit_event("info", text=f"已保存第 {next_iteration} 轮中间笔记：{intermediate_path}")

    return {
        "current_note": new_note,
        "iteration_count": next_iteration,
        "verification_report": "",
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
        stream=False,
    )

    asset_errors = list(state.get("asset_errors", []))
    plan_items = parse_asset_plan(text, errors=asset_errors)
    plan_items = filter_asset_plan(plan_items, state["final_note"])
    plan_data = [to_plain_data(item) for item in plan_items]

    emit_event("info", text=f"资产规划数量（过滤后）：{len(plan_data)}")

    return {"asset_plan": plan_data, "asset_errors": asset_errors}


def generate_note_assets(state: NoteResearchState):
    emit_node_start("generate_note_assets", "正在生成笔记资产")

    if not state.get("asset_plan"):
        emit_event("info", text="没有需要生成的公式、代码、图表或流程图。")
        return {
            "generated_assets": {},
            "asset_paths": [],
            "asset_errors": list(state.get("asset_errors", [])),
        }

    asset_plan_text = json.dumps(state["asset_plan"], ensure_ascii=False, indent=2)

    text = ask_llm(
        generate_assets_prompt(
            current_note=state["final_note"],
            asset_plan=asset_plan_text,
        ),
        provider=state["llm_provider"],
        stream=False,
    )

    asset_errors = list(state.get("asset_errors", []))
    generated_assets = parse_generated_assets(text, errors=asset_errors)
    generated_assets = validate_generated_assets(generated_assets)
    asset_paths = save_generated_assets(state["run_id"], generated_assets, errors=asset_errors)

    emit_event("info", text=f"已生成并保存资产文件：{len(asset_paths)} 个")

    return {
        "generated_assets": to_plain_data(generated_assets),
        "asset_paths": asset_paths,
        "asset_errors": asset_errors,
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
    emit_node_start("save_markdown", "正在保存 Markdown")

    title = derive_title(state["final_note"])

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
    emit_event(
        "info",
        text=f"Markdown saved: {saved_path}",
        saved_path=saved_path,
    )

    return {"saved_path": saved_path, "note_title": title}


def publish_notion_node(state: NoteResearchState):
    emit_node_start("publish_notion", "正在发布到 Notion")

    title = state.get("note_title", "").strip()
    if not title:
        for line in state["final_note"].splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
    if not title:
        title = "Untitled Note"

    try:
        notion_url = publish_note(
            markdown=state["final_note"],
            title=title,
        )
        emit_event("info", text=f"已发布到 Notion：{notion_url}")

        append_event(
            state["run_id"],
            {
                "type": "notion_published",
                "notion_url": notion_url,
            },
        )

        return {"notion_url": notion_url}
    except Exception as e:
        emit_event("error", message=f"Notion 发布失败：{e}", fatal=False)
        return {"notion_url": ""}



def route_after_save(state: NoteResearchState) -> str:
    if state.get("enable_notion"):
        return "publish_notion"
    return "end"


def build_graph():
    builder = StateGraph(NoteResearchState)

    builder.add_node("infer_type_and_outline", infer_type_and_outline)
    builder.add_node("generate_initial_note", generate_initial_note)
    builder.add_node("generate_reference_queries", generate_reference_queries)
    builder.add_node("retrieve_references", retrieve_references_node)
    builder.add_node("verify_and_refine", verify_and_refine)
    builder.add_node("finalize_note", finalize_note)
    builder.add_node("plan_note_assets", plan_note_assets)
    builder.add_node("generate_note_assets", generate_note_assets)
    builder.add_node("assemble_assets_into_note", assemble_assets_into_note)
    builder.add_node("save_markdown", save_markdown_node)
    builder.add_node("publish_notion", publish_notion_node)

    builder.add_edge(START, "infer_type_and_outline")
    builder.add_edge("infer_type_and_outline", "generate_initial_note")
    builder.add_conditional_edges(
        "generate_initial_note",
        route_after_initial_note,
        {"continue": "generate_reference_queries", "finalize": "finalize_note"},
    )
    builder.add_edge("generate_reference_queries", "retrieve_references")
    builder.add_edge("retrieve_references", "verify_and_refine")
    builder.add_conditional_edges(
        "verify_and_refine",
        route_iteration,
        {"continue": "generate_reference_queries", "finalize": "finalize_note"},
    )
    builder.add_conditional_edges(
        "finalize_note",
        route_after_finalize,
        {"assets": "plan_note_assets", "save": "save_markdown"},
    )
    builder.add_edge("plan_note_assets", "generate_note_assets")
    builder.add_edge("generate_note_assets", "assemble_assets_into_note")
    builder.add_edge("assemble_assets_into_note", "save_markdown")
    builder.add_conditional_edges(
        "save_markdown",
        route_after_save,
        {"publish_notion": "publish_notion", "end": END},
    )
    builder.add_edge("publish_notion", END)

    return builder.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
