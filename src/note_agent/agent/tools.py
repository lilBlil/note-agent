"""ReAct tools for note agent."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Annotated

from langchain_core.tools import tool, InjectedToolArg

from note_agent.agent.common import apply_patches, dedupe_urls, parse_note_structure
from note_agent.config.llm import ask_llm
from note_agent.config.runtime import (
    max_reference_queries,
    max_results_per_source,
    max_retrieval_workers,
)
from note_agent.io.events import emit_event
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
from note_agent.domain.models import ReferenceQuery
from note_agent.io.storage import append_event, save_intermediate_note
from note_agent.notion import publish_note
from note_agent.utils import extract_json_object, to_plain_data
from note_agent.assets.tools import (
    build_asset_markdown_items,
    filter_asset_plan,
    inject_assets_into_markdown,
    parse_asset_plan,
    parse_generated_assets,
    save_generated_assets,
    validate_generated_assets,
)

@tool
def infer_note_structure(
    raw_input: str,
    llm_provider: Annotated[str, InjectedToolArg] = "deepseek"
) -> dict:
    """
    推断笔记类型并生成大纲结构。

    Args:
        raw_input: 用户原始输入

    Returns:
        包含 note_type 和 note_outline 的字典
    """
    emit_event("info", text="🔍 正在推断笔记类型和大纲结构")
    text = ask_llm(
        infer_type_and_outline_prompt(raw_input),
        provider=llm_provider,
        stream=False,
    )
    note_type, outline = parse_note_structure(text)

    emit_event("info", text=f"✅ 笔记类型：{note_type}，大纲章节数：{len(outline)}")
    return {"note_type": note_type, "note_outline": outline}


@tool
def generate_note_draft(
    raw_input: str,
    note_type: str,
    note_outline: list,
    llm_provider: Annotated[str, InjectedToolArg] = "deepseek",
    run_id: Annotated[str, InjectedToolArg] = ""
) -> dict:
    """
    生成笔记初稿。

    Args:
        raw_input: 用户原始输入
        note_type: 笔记类型
        note_outline: 笔记大纲

    Returns:
        包含 current_note 和 intermediate_path 的字典
    """
    emit_event("info", text="✍️ 正在生成笔记初稿")
    outline_text = json.dumps(note_outline, ensure_ascii=False, indent=2)

    note = ask_llm(
        generate_initial_note_prompt(
            raw_input=raw_input,
            note_type=note_type,
            outline=outline_text,
        ),
        provider=llm_provider,
        stream=True,
    )

    intermediate_path = save_intermediate_note(run_id, "initial_draft", note)
    emit_event("info", text=f"✅ 初稿已保存：{intermediate_path}")

    return {"current_note": note, "intermediate_path": intermediate_path}


@tool
def search_references(
    current_note: str,
    used_queries: list,
    llm_provider: Annotated[str, InjectedToolArg] = "deepseek",
    search_api: Annotated[str, InjectedToolArg] = "duckduckgo"
) -> dict:
    """
    分析笔记信息缺口，生成检索查询并执行搜索。

    Args:
        current_note: 当前笔记内容
        used_queries: 已使用的查询列表

    Returns:
        包含 reference_results 和 new_queries 的字典
    """
    emit_event("info", text="🔎 正在分析信息缺口并生成检索请求")

    # 生成检索查询
    text = ask_llm(
        generate_reference_queries_prompt(
            current_note=current_note,
            used_queries=used_queries,
        ),
        provider=llm_provider,
        stream=False,
    )

    data = extract_json_object(text)
    raw_items = data.get("reference_queries", [])
    if not isinstance(raw_items, list):
        raw_items = []

    used = set(normalize_query(q) for q in used_queries)
    reference_queries = []
    new_query_texts = []

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
        reference_queries.append(reference_query)
        new_query_texts.append(query)
        used.add(normalized)

    query_limit = max_reference_queries()
    reference_queries = reference_queries[:query_limit]
    new_query_texts = new_query_texts[:query_limit]

    if not reference_queries:
        emit_event("info", text="✅ 未发现新的信息缺口")
        return {"reference_results": [], "new_queries": [], "sources": [], "failed_sources": []}

    # 执行检索
    emit_event("info", text=f"🌐 开始检索 {len(reference_queries)} 个查询")

    lock = Lock()
    all_results = []
    all_sources = []
    failed_sources = []

    def fetch(rq: ReferenceQuery):
        failures = []
        emit_event("info", text=f"  📡 检索：{rq.query} ({', '.join(rq.source_types)})")
        try:
            results = retrieve_references(
                rq,
                web_backend=search_api,
                max_results_per_type=max_results_per_source(),
                on_failure=failures.append,
            )
            return results, failures
        except Exception as e:
            failure = {
                "query": rq.query,
                "source_type": ",".join(rq.source_types),
                "source_name": search_api,
                "error_type": type(e).__name__,
                "error": str(e),
            }
            emit_event("warning", text=f"Reference retrieval failed: {rq.query}: {e}", failed_source=failure)
            emit_event("info", text=f"  ⚠️ 检索失败：{rq.query} - {e}")
            return [], [failure]

    with ThreadPoolExecutor(
        max_workers=min(len(reference_queries), max_retrieval_workers())
    ) as pool:
        futures = {pool.submit(fetch, rq): rq for rq in reference_queries}
        for fut in as_completed(futures):
            results, failures = fut.result()
            with lock:
                all_results.extend(results)
                all_sources.extend(collect_reference_urls(results))
                failed_sources.extend(failures)

    emit_event("info", text=f"✅ 检索完成，共获取 {len(all_results)} 条参考信息")

    return {
        "reference_results": [to_plain_data(r) for r in all_results],
        "new_queries": new_query_texts,
        "sources": dedupe_urls(all_sources),
        "failed_sources": failed_sources,
    }


@tool
def refine_note_with_references(
    raw_input: str,
    current_note: str,
    reference_results: list,
    iteration: int,
    llm_provider: Annotated[str, InjectedToolArg] = "deepseek",
    run_id: Annotated[str, InjectedToolArg] = ""
) -> dict:
    """
    使用检索到的参考信息验证和修正笔记。

    Args:
        raw_input: 用户原始输入
        current_note: 当前笔记内容
        reference_results: 参考信息列表
        iteration: 当前迭代次数

    Returns:
        包含 refined_note 和 intermediate_path 的字典
    """
    emit_event("info", text=f"🔍 正在验证和修正笔记（第 {iteration} 轮）")

    # Convert dict results back to ReferenceItem objects
    from note_agent.domain.models import ReferenceItem
    reference_items = []
    for item in reference_results:
        if isinstance(item, dict):
            reference_items.append(ReferenceItem(**item))
        else:
            reference_items.append(item)

    references_text = format_references_for_prompt(reference_items)

    patch_text = ask_llm(
        verify_and_refine_prompt(
            raw_input=raw_input,
            current_note=current_note,
            references=references_text,
        ),
        provider=llm_provider,
        stream=True,
    )

    new_note = apply_patches(current_note, patch_text)

    intermediate_path = save_intermediate_note(
        run_id,
        f"refined_iter_{iteration}",
        new_note,
    )

    emit_event("info", text=f"✅ 第 {iteration} 轮修正完成：{intermediate_path}")

    return {"refined_note": new_note, "intermediate_path": intermediate_path}


@tool
def finalize_note_content(
    current_note: str,
    sources: list,
    llm_provider: Annotated[str, InjectedToolArg] = "deepseek",
    run_id: Annotated[str, InjectedToolArg] = ""
) -> dict:
    """
    生成最终版本的笔记（纯文本）。

    Args:
        current_note: 当前笔记内容
        sources: 参考来源列表

    Returns:
        包含 final_note 和 intermediate_path 的字典
    """
    emit_event("info", text="📝 正在生成最终版本笔记")

    final_note = ask_llm(
        finalize_note_prompt(
            current_note=current_note,
            sources=sources,
        ),
        provider=llm_provider,
        stream=True,
    )

    intermediate_path = save_intermediate_note(run_id, "final_text_only", final_note)
    emit_event("info", text=f"✅ 最终版本已保存：{intermediate_path}")

    return {"final_note": final_note, "intermediate_path": intermediate_path}


@tool
def plan_note_assets(
    final_note: str,
    note_type: str,
    llm_provider: Annotated[str, InjectedToolArg] = "deepseek"
) -> dict:
    """
    规划笔记需要的多模态资产（公式、代码、图表、流程图）。

    Args:
        final_note: 最终笔记内容
        note_type: 笔记类型

    Returns:
        包含 asset_plan 的字典
    """
    emit_event("info", text="🎨 正在规划笔记资产")

    text = ask_llm(
        plan_assets_prompt(
            current_note=final_note,
            note_type=note_type,
        ),
        provider=llm_provider,
        stream=False,
    )

    asset_errors = []
    plan_items = parse_asset_plan(text, errors=asset_errors)
    plan_items = filter_asset_plan(plan_items, final_note)
    plan_data = [to_plain_data(item) for item in plan_items]

    emit_event("info", text=f"✅ 资产规划完成：{len(plan_data)} 项")

    return {"asset_plan": plan_data, "asset_errors": asset_errors}


@tool
def generate_note_assets(
    final_note: str,
    asset_plan: list,
    llm_provider: Annotated[str, InjectedToolArg] = "deepseek",
    run_id: Annotated[str, InjectedToolArg] = ""
) -> dict:
    """
    根据规划生成实际的资产文件。

    Args:
        final_note: 最终笔记内容
        asset_plan: 资产规划列表

    Returns:
        包含 generated_assets 和 asset_paths 的字典
    """
    if not asset_plan:
        emit_event("info", text="ℹ️ 无需生成资产")
        return {"generated_assets": {}, "asset_paths": [], "asset_errors": []}

    emit_event("info", text=f"🎨 正在生成 {len(asset_plan)} 项资产")

    asset_plan_text = json.dumps(asset_plan, ensure_ascii=False, indent=2)

    text = ask_llm(
        generate_assets_prompt(
            current_note=final_note,
            asset_plan=asset_plan_text,
        ),
        provider=llm_provider,
        stream=False,
    )

    asset_errors = []
    generated_assets = parse_generated_assets(text, errors=asset_errors)
    generated_assets = validate_generated_assets(generated_assets)
    asset_paths = save_generated_assets(run_id, generated_assets, errors=asset_errors)

    emit_event("info", text=f"✅ 资产生成完成：{len(asset_paths)} 个文件")

    return {
        "generated_assets": to_plain_data(generated_assets),
        "asset_paths": asset_paths,
        "asset_errors": asset_errors,
    }


@tool
def assemble_final_note(
    final_note: str,
    generated_assets: dict,
    asset_paths: list,
    run_id: Annotated[str, InjectedToolArg] = ""
) -> dict:
    """
    将资产注入到笔记中，生成多模态 Markdown。

    Args:
        final_note: 最终笔记文本
        generated_assets: 生成的资产数据
        asset_paths: 资产文件路径列表

    Returns:
        包含 final_note_with_assets 和 intermediate_path 的字典
    """
    emit_event("info", text="🔧 正在组装多模态笔记")

    assets = parse_generated_assets(json.dumps(generated_assets, ensure_ascii=False))
    asset_items = build_asset_markdown_items(assets, asset_paths)
    assembled_note = inject_assets_into_markdown(final_note, asset_items)

    intermediate_path = save_intermediate_note(run_id, "final_with_assets", assembled_note)
    emit_event("info", text=f"✅ 多模态笔记已组装：{intermediate_path}")

    return {"final_note_with_assets": assembled_note, "intermediate_path": intermediate_path}


@tool
def save_final_note(
    final_note: str,
    asset_paths: list,
    sources: list,
    llm_provider: Annotated[str, InjectedToolArg] = "deepseek",
    run_id: Annotated[str, InjectedToolArg] = ""
) -> dict:
    """
    生成标题并保存最终笔记到磁盘。

    Args:
        final_note: 最终笔记内容
        asset_paths: 资产文件路径列表
        sources: 参考来源列表

    Returns:
        包含 saved_path 和 note_title 的字典
    """
    emit_event("info", text="💾 正在保存笔记")

    title = derive_title(final_note)

    saved_path = save_markdown(title, final_note)

    append_event(
        run_id,
        {
            "type": "saved",
            "saved_path": saved_path,
            "asset_paths": asset_paths,
            "sources": sources,
        },
    )

    emit_event("info", text=f"✅ 笔记已保存：{saved_path}")

    return {"saved_path": saved_path, "note_title": title}


@tool
def publish_note_to_notion(
    final_note: str,
    note_title: str,
    run_id: Annotated[str, InjectedToolArg] = ""
) -> dict:
    """
    发布笔记到 Notion。

    Args:
        final_note: 最终笔记内容
        note_title: 笔记标题

    Returns:
        包含 notion_url 的字典
    """
    emit_event("info", text="🚀 正在发布到 Notion")

    title = note_title.strip() if note_title else "Untitled Note"
    if not title:
        for line in final_note.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

    try:
        notion_url = publish_note(markdown=final_note, title=title)
        emit_event("info", text=f"✅ 已发布到 Notion：{notion_url}")

        append_event(run_id, {"type": "notion_published", "notion_url": notion_url})

        return {"notion_url": notion_url}
    except Exception as e:
        emit_event("error", message=f"Notion 发布失败：{e}", fatal=False)
        return {"notion_url": "", "error": str(e)}


# 导出所有工具
ALL_TOOLS = [
    infer_note_structure,
    generate_note_draft,
    search_references,
    refine_note_with_references,
    finalize_note_content,
    plan_note_assets,
    generate_note_assets,
    assemble_final_note,
    save_final_note,
    publish_note_to_notion,
]
