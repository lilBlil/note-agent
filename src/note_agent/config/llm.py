"""LLM invocation wrapper with streaming support."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from note_agent.config.runtime import llm_stream_chunk_timeout
from note_agent.config.settings import get_model
from note_agent.net import call_with_retries

_STREAM_END = object()


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


def _invoke_with_retries(model, prompt: str):
    return call_with_retries(
        lambda: model.invoke(prompt),
        attempts=3,
        delay_seconds=1.0,
        label="LLM request",
    )


def _next_stream_chunk(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return _STREAM_END


def _stream_with_timeout(model, prompt: str, timeout_seconds: int):
    iterator = model.stream(prompt)
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        while True:
            future = executor.submit(_next_stream_chunk, iterator)
            try:
                chunk = future.result(timeout=timeout_seconds)
            except FutureTimeoutError as error:
                future.cancel()
                raise TimeoutError(
                    f"no stream chunk received within {timeout_seconds}s"
                ) from error
            if chunk is _STREAM_END:
                break
            yield chunk
    finally:
        close = getattr(iterator, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        executor.shutdown(wait=False, cancel_futures=True)


def ask_llm(prompt: str, provider: str = "deepseek", stream: bool = False) -> str:
    from note_agent.io.events import (
        _current_node,
        _current_step,
        emit_event,
        emit_token,
        has_event_handler,
    )
    from note_agent.agent.tracker import record_usage

    llm = get_model(provider) if stream else get_model(provider, for_tools=True)

    if not stream:
        response = _invoke_with_retries(llm, prompt)
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
    chunk_timeout = llm_stream_chunk_timeout(60 if provider == "moonshot" else 15)
    stream_started_at = time.monotonic()
    empty_chunk_notice_sent = False
    try:
        for chunk in _stream_with_timeout(llm, prompt, chunk_timeout):
            in_tok, out_tok = _extract_usage(chunk)
            input_tokens = input_tokens or in_tok
            output_tokens = output_tokens or out_tok
            if chunk.content:
                emit_token(chunk.content)
                if should_print:
                    # Guard against consoles whose encoding (e.g. Windows GBK) can't
                    # represent some chars; never let display kill a real run.
                    try:
                        print(chunk.content, end="", flush=True)
                    except UnicodeEncodeError:
                        pass
                chunks.append(chunk.content)
            elif (
                provider == "moonshot"
                and not chunks
                and not empty_chunk_notice_sent
                and time.monotonic() - stream_started_at >= 8
            ):
                emit_event("info", text="\u6a21\u578b\u6b63\u5728\u63a8\u7406\uff0c\u7b49\u5f85\u6b63\u6587\u8f93\u51fa...")
                empty_chunk_notice_sent = True
    except Exception as error:
        emit_event(
            "warning",
            text=(
                "LLM streaming failed; retrying once without streaming: "
                f"{type(error).__name__}: {error}"
            ),
        )
        response = _invoke_with_retries(get_model(provider, for_tools=True), prompt)
        input_tokens, output_tokens = _extract_usage(response)
        content = str(response.content)
        chunks = [content]
    if should_print:
        try:
            print()
        except UnicodeEncodeError:
            pass

    record_usage(
        node_name=_current_node.get(),
        step_label=_current_step.get(),
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return "".join(chunks)
