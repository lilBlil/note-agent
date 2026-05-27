"""LLM invocation wrapper with streaming support."""

from __future__ import annotations

from note_agent.config.settings import get_model


def _extract_usage(response) -> tuple[int, int]:
    """Return (input_tokens, output_tokens) from a LangChain AIMessage or AIMessageChunk."""
    try:
        meta = response.usage_metadata or {}
        inp = meta.get("input_tokens", 0) or meta.get("prompt_tokens", 0)
        out = meta.get("output_tokens", 0) or meta.get("completion_tokens", 0)

        if not inp and not out:
            meta = response.response_metadata or {}
            token_usage = meta.get("token_usage", {}) or {}
            inp = token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0)
            out = token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0)

        return inp, out
    except Exception:
        return 0, 0


def ask_llm(prompt: str, provider: str = "deepseek", stream: bool = False) -> str:
    from note_agent.io.events import (
        _current_node,
        _current_step,
        emit_token,
        has_event_handler,
    )
    from note_agent.agent.tracker import record_usage

    llm = get_model(provider)

    if not stream:
        response = llm.invoke(prompt)
        input_tokens, output_tokens = _extract_usage(response)
        record_usage(
            node_name=_current_node.get(),
            step_label=_current_step.get(),
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return str(response.content)

    chunks: list[str] = []
    input_tokens = 0
    output_tokens = 0
    should_print = not has_event_handler()
    for chunk in llm.stream(prompt):
        in_tok, out_tok = _extract_usage(chunk)
        input_tokens = input_tokens or in_tok
        output_tokens = output_tokens or out_tok
        if chunk.content:
            emit_token(chunk.content)
            if should_print:
                print(chunk.content, end="", flush=True)
            chunks.append(chunk.content)
    if should_print:
        print()

    record_usage(
        node_name=_current_node.get(),
        step_label=_current_step.get(),
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return "".join(chunks)
