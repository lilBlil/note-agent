"""Infrastructure utilities: events, LLM, config, text, and markdown helpers."""

from __future__ import annotations

import os
import re
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

EventHandler = Callable[[dict[str, Any]], None]

_event_handler: ContextVar[EventHandler | None] = ContextVar("event_handler", default=None)
_current_node: ContextVar[str] = ContextVar("current_node", default="")
_current_step: ContextVar[str] = ContextVar("current_step", default="")


def set_event_handler(handler: EventHandler):
    return _event_handler.set(handler)


def reset_event_handler(token) -> None:
    _event_handler.reset(token)


def has_event_handler() -> bool:
    return _event_handler.get() is not None


def emit_event(event_type: str, **payload: Any) -> None:
    handler = _event_handler.get()
    if handler:
        handler({"type": event_type, **payload})


def emit_node_start(node_name: str, step_label: str) -> None:
    _current_node.set(node_name)
    _current_step.set(step_label)
    emit_event("node_start", node_name=node_name, step_label=step_label)


def emit_token(text: str) -> None:
    emit_event("token", node_name=_current_node.get(), step_label=_current_step.get(), text=text)


# ---------------------------------------------------------------------------
# LLM config & invocation
# ---------------------------------------------------------------------------

MODEL_CONFIGS: dict[str, dict[str, str | None]] = {
    "deepseek": {"model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY", "base_url": None},
    "openai": {"model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY", "base_url": None},
    "qwen": {
        "model": "qwen-plus",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "moonshot": {
        "model": "moonshot-v1-8k",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
    },
    "zhipu": {
        "model": "glm-4-flash",
        "api_key_env": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "siliconflow": {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "api_key_env": "SILICONFLOW_API_KEY",
        "base_url": "https://api.siliconflow.cn/v1",
    },
}


def get_model(provider: str = "deepseek"):
    if provider not in MODEL_CONFIGS:
        raise ValueError(f"Unknown provider: {provider}")
    cfg = MODEL_CONFIGS[provider]
    api_key = os.getenv(str(cfg["api_key_env"]))
    if not api_key:
        raise ValueError(f"Missing {cfg['api_key_env']} — check .env")
    if provider == "deepseek":
        return ChatDeepSeek(model=str(cfg["model"]), api_key=api_key, temperature=0.3)
    return ChatOpenAI(model=str(cfg["model"]), api_key=api_key, base_url=str(cfg["base_url"] or ""), temperature=0.3)


def ask_llm(prompt: str, provider: str = "deepseek", stream: bool = False) -> str:
    llm = get_model(provider)
    if not stream:
        return str(llm.invoke(prompt).content)

    full_text = ""
    should_print = not has_event_handler()
    for chunk in llm.stream(prompt):
        if chunk.content:
            emit_token(chunk.content)
            if should_print:
                print(chunk.content, end="", flush=True)
            full_text += chunk.content
    if should_print:
        print()
    return full_text


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

NOTES_DIR = Path("notes")
NOTES_DIR.mkdir(exist_ok=True)


def normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())


def clean_filename(title: str) -> str:
    title = title.strip()
    title = re.sub(r"^#+\s*", "", title)
    title = re.sub(r'[\\/:*?"<>|]', "", title)
    title = re.sub(r"\s+", "_", title)
    title = re.sub(r"_+", "_", title)
    title = title.strip("_")
    return title[:40] or "note"


def strip_markdown_fence(content: str) -> str:
    content = content.strip()
    if content.startswith("```markdown"):
        content = content[len("```markdown"):].strip()
    elif content.startswith("```md"):
        content = content[len("```md"):].strip()
    elif content.startswith("```"):
        content = content[len("```"):].strip()
    if content.endswith("```"):
        content = content[:-3].strip()
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            content = "\n".join(lines[i:]).strip()
            break
    return content


def save_markdown(title: str, content: str) -> str:
    safe_title = clean_filename(title)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    content = strip_markdown_fence(content)
    file_path = NOTES_DIR / f"{safe_title}_{timestamp}.md"
    file_path.write_text(content, encoding="utf-8")
    return str(file_path.resolve())
