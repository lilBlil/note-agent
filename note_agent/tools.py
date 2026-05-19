import re
from datetime import datetime
from pathlib import Path
from note_agent.config import get_model
from contextvars import ContextVar

NOTES_DIR = Path("notes")
NOTES_DIR.mkdir(exist_ok=True)

_event_handler = ContextVar("event_handler", default=None)
_current_node = ContextVar("current_node", default="")
_current_step = ContextVar("current_step", default="")


def set_event_handler(handler):
    return _event_handler.set(handler)


def reset_event_handler(token):
    _event_handler.reset(token)


def emit_event(event_type: str, **payload):
    handler = _event_handler.get()
    if handler:
        handler({
            "type": event_type,
            **payload,
        })


def emit_node_start(node_name: str, step_label: str):
    _current_node.set(node_name)
    _current_step.set(step_label)

    emit_event(
        "node_start",
        node_name=node_name,
        step_label=step_label,
    )


def emit_token(text: str):
    emit_event(
        "token",
        node_name=_current_node.get(),
        step_label=_current_step.get(),
        text=text,
    )


def ask_llm(prompt: str, provider: str = "deepseek", stream: bool = False) -> str:
    llm = get_model(provider)

    if not stream:
        response = llm.invoke(prompt)
        return response.content

    full_text = ""

    for chunk in llm.stream(prompt):
        if chunk.content:
            emit_token(chunk.content)
            print(chunk.content, end="", flush=True)
            full_text += chunk.content

    print()
    return full_text


def normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())


def clean_filename(title: str) -> str:
    title = title.strip()
    title = re.sub(r"^#+\s*", "", title)
    title = re.sub(r"[\\/:*?\"<>|]", "", title)
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