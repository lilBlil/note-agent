import os

from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI


load_dotenv()


MODEL_CONFIGS = {
    "deepseek": {
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": None,
    },
    "openai": {
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": None,
    },
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
        raise ValueError(f"不支持的模型提供方：{provider}")

    config = MODEL_CONFIGS[provider]
    api_key = os.getenv(config["api_key_env"])

    if not api_key:
        raise ValueError(f"未找到 {config['api_key_env']}，请检查 .env 文件")

    if provider == "deepseek":
        return ChatDeepSeek(
            model=config["model"],
            api_key=api_key,
            temperature=0.3,
        )

    return ChatOpenAI(
        model=config["model"],
        api_key=api_key,
        base_url=config["base_url"],
        temperature=0.3,
    )