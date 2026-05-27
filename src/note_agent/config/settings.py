"""LLM provider configuration."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

load_dotenv()

MODEL_CONFIGS: dict[str, dict[str, str | None]] = {
    "deepseek": {"model": "deepseek-v4-pro", "api_key_env": "DEEPSEEK_API_KEY", "base_url": None},
    "openai": {"model": "gpt-4o", "api_key_env": "OPENAI_API_KEY", "base_url": None},
    "qwen": {
        "model": "qwen-max",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "moonshot": {
        "model": "moonshot-v1-128k",
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


def get_model(provider: str = "deepseek"):
    if provider not in MODEL_CONFIGS:
        raise ValueError(f"Unknown provider: {provider}")
    cfg = MODEL_CONFIGS[provider]
    api_key = os.getenv(str(cfg["api_key_env"]))
    if not api_key:
        raise ValueError(f"Missing {cfg['api_key_env']} — check .env")
    model_kwargs = {"stream_options": {"include_usage": True}}
    if provider == "deepseek":
        return ChatDeepSeek(
            model=str(cfg["model"]),
            api_key=api_key,
            temperature=0.3,
            model_kwargs=model_kwargs,
        )
    return ChatOpenAI(
        model=str(cfg["model"]),
        api_key=api_key,
        base_url=str(cfg["base_url"] or ""),
        temperature=0.3,
        model_kwargs=model_kwargs,
    )
