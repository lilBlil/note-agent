"""LLM provider configuration."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

from note_agent.config.runtime import llm_request_timeout, llm_stream_chunk_timeout

load_dotenv()

MODEL_CONFIGS: dict[str, dict[str, str | None]] = {
    "deepseek": {"model": "deepseek-v4-flash", "api_key_env": "DEEPSEEK_API_KEY", "base_url": None},
    "openai": {"model": "gpt-4o", "api_key_env": "OPENAI_API_KEY", "base_url": None},
    "anthropic": {
        "model": "claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": None,
    },
    "qwen": {
        "model": "qwen-max",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "moonshot": {
        "model": "kimi-k3",
        "api_key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
    },
    "zhipu": {
        "model": "glm-4-plus",
        "api_key_env": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "siliconflow": {
        "model": "deepseek-ai/DeepSeek-V3",
        "api_key_env": "SILICONFLOW_API_KEY",
        "base_url": "https://api.siliconflow.cn/v1",
    },
}


@lru_cache(maxsize=16)
def get_model(provider: str = "deepseek", for_tools: bool = False):
    """
    Get LLM model instance.

    Args:
        provider: LLM provider name
        for_tools: If True, returns model suitable for tool calling (no stream_options)
    """
    if provider not in MODEL_CONFIGS:
        raise ValueError(f"Unknown provider: {provider}")
    cfg = MODEL_CONFIGS[provider]
    api_key = os.getenv(str(cfg["api_key_env"]))
    if not api_key:
        raise ValueError(f"Missing {cfg['api_key_env']} — check .env")

    # Kimi's OpenAI-compatible endpoint works best with a plain streaming request.
    model_kwargs = (
        {}
        if for_tools or provider == "moonshot"
        else {"stream_options": {"include_usage": True}}
    )
    if provider == "moonshot":
        timeout = llm_request_timeout(180)
        chunk_timeout = llm_stream_chunk_timeout(60)
    else:
        timeout = llm_request_timeout()
        chunk_timeout = llm_stream_chunk_timeout()

    if provider == "deepseek":
        return ChatDeepSeek(
            model=str(cfg["model"]),
            api_key=api_key,
            temperature=0,
            model_kwargs=model_kwargs,
            timeout=timeout,
            max_retries=0,
            stream_chunk_timeout=chunk_timeout,
        )
    if provider == "anthropic":
        return ChatAnthropic(
            model=str(cfg["model"]),
            api_key=api_key,
            temperature=0,
            timeout=timeout,
            max_retries=0,
        )
    temperature = None if provider == "moonshot" else 0
    openai_kwargs = {}
    if provider == "moonshot" and str(cfg["model"]).startswith("kimi-k3"):
        openai_kwargs["reasoning_effort"] = os.getenv("MOONSHOT_REASONING_EFFORT", "low")

    return ChatOpenAI(
        model=str(cfg["model"]),
        api_key=api_key,
        base_url=str(cfg["base_url"] or ""),
        temperature=temperature,
        model_kwargs=model_kwargs,
        timeout=timeout,
        max_retries=0,
        stream_chunk_timeout=chunk_timeout,
        **openai_kwargs,
    )


def clear_model_cache() -> None:
    """Clear cached LangChain clients after changing environment variables."""
    get_model.cache_clear()
