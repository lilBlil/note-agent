from config.settings import LLMProvider, get_settings
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

from note_agent.agent.events import emit_token, has_event_handler


MODEL_CONFIGS = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
    },
    "qwen": {
        "api_key_env": "DASHSCOPE_API_KEY",
    },
    "moonshot": {
        "api_key_env": "MOONSHOT_API_KEY",
    },
    "zhipu": {
        "api_key_env": "ZHIPU_API_KEY",
    },
    "siliconflow": {
        "api_key_env": "SILICONFLOW_API_KEY",
    },
}


def get_model(provider: LLMProvider = "deepseek"):
    if provider not in MODEL_CONFIGS:
        raise ValueError(f"不支持的模型提供方：{provider}")

    settings = get_settings()
    api_key = settings.api_key_for(provider)

    if not api_key:
        api_key_env = MODEL_CONFIGS[provider]["api_key_env"]
        fallback = " 或 LLM_API_KEY" if provider == settings.default_llm_provider else ""
        raise ValueError(f"未找到 {api_key_env}{fallback}，请检查 .env 或 env/.env 文件")

    if provider == "deepseek":
        return ChatDeepSeek(
            model=settings.model_for(provider),
            api_key=api_key,
            temperature=0.3,
        )

    return ChatOpenAI(
        model=settings.model_for(provider),
        api_key=api_key,
        base_url=settings.base_url_for(provider),
        temperature=0.3,
    )


def ask_llm(prompt: str, provider: LLMProvider = "deepseek", stream: bool = False) -> str:
    llm = get_model(provider)

    if not stream:
        response = llm.invoke(prompt)
        return response.content

    full_text = ""
    should_print = not has_event_handler()

    for chunk in llm.stream(prompt):
        if chunk.content:
            emit_token(chunk.content)

            # CLI 下保留逐字输出；Streamlit 下不刷终端，避免输出噪声。
            if should_print:
                print(chunk.content, end="", flush=True)

            full_text += chunk.content

    if should_print:
        print()

    return full_text
