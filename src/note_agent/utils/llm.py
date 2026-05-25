from note_agent.config import get_model
from note_agent.utils.events import emit_token, has_event_handler


def ask_llm(prompt: str, provider: str = "deepseek", stream: bool = False) -> str:
    llm = get_model(provider)

    if not stream:
        response = llm.invoke(prompt)
        return response.content

    full_text = ""
    should_print = not has_event_handler()

    for chunk in llm.stream(prompt):
        if chunk.content:
            emit_token(chunk.content)

            # Keep token streaming in CLI, while Streamlit consumes tokens through events.
            if should_print:
                print(chunk.content, end="", flush=True)

            full_text += chunk.content

    if should_print:
        print()

    return full_text
