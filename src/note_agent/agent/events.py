from contextvars import ContextVar


_event_handler = ContextVar("event_handler", default=None)
_current_node = ContextVar("current_node", default="")
_current_step = ContextVar("current_step", default="")


def set_event_handler(handler):
    return _event_handler.set(handler)


def reset_event_handler(token):
    _event_handler.reset(token)


def has_event_handler() -> bool:
    return _event_handler.get() is not None


def emit_event(event_type: str, **payload):
    handler = _event_handler.get()
    if handler:
        handler(
            {
                "type": event_type,
                **payload,
            }
        )


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
