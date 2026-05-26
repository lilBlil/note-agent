"""LLM invocation wrapper with streaming support."""

from __future__ import annotations

from note_agent.config.settings import get_model


def ask_llm(prompt: str, provider: str = "deepseek", stream: bool = False) -> str:
    from note_agent.io.events import emit_token, has_event_handler

    llm = get_model(provider)
    if not stream:
        return str(llm.invoke(prompt).content)

    chunks: list[str] = []
    should_print = not has_event_handler()
    for chunk in llm.stream(prompt):
        if chunk.content:
            emit_token(chunk.content)
            if should_print:
                print(chunk.content, end="", flush=True)
            chunks.append(chunk.content)
    if should_print:
        print()
    return "".join(chunks)
