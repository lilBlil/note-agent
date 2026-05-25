import os
from typing import Any, Literal
from pathlib import Path

from pydantic import Field, field_validator

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - only used before dependencies are synced.
    from pydantic import BaseModel, ConfigDict as SettingsConfigDict

    def _read_env_file(path: str | Path) -> dict[str, str]:
        env_path = Path(path)
        if not env_path.exists():
            return {}

        values: dict[str, str] = {}
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip().lower()] = value.strip().strip('"').strip("'")
        return values

    class BaseSettings(BaseModel):
        def __init__(self, **data: Any) -> None:
            config = getattr(self, "model_config", {})
            env_files = config.get("env_file", ())
            if isinstance(env_files, (str, Path)):
                env_files = (env_files,)

            env_values: dict[str, str] = {}
            for env_file in env_files:
                env_values.update(_read_env_file(env_file))
            env_values.update({key.lower(): value for key, value in os.environ.items()})

            for field_name in self.__class__.model_fields:
                env_name = field_name.upper().lower()
                if field_name not in data and env_name in env_values:
                    data[field_name] = env_values[env_name]

            super().__init__(**data)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_DIRECTORY = PROJECT_ROOT / 'env'


LLMProvider = Literal[
    "deepseek",
    "openai",
    "qwen",
    "moonshot",
    "zhipu",
    "siliconflow",
]

SearchAPI = Literal[
    "duckduckgo",
    "tavily",
    "perplexity",
    "searxng",
]

AssetType = Literal["formula", "code", "mermaid", "chart"]


_PROVIDER_DEFAULTS = {
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": None,
        "api_key_field": "deepseek_api_key",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": None,
        "api_key_field": "openai_api_key",
    },
    "qwen": {
        "model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_field": "dashscope_api_key",
    },
    "moonshot": {
        "model": "moonshot-v1-8k",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_field": "moonshot_api_key",
    },
    "zhipu": {
        "model": "glm-4-flash",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_field": "zhipu_api_key",
    },
    "siliconflow": {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key_field": "siliconflow_api_key",
    },
}


def _resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


class BaseSharedSettings(BaseSettings):

    default_llm_provider: LLMProvider = Field(
        default="deepseek",
        description="default LLM provider",
    )

    default_max_iterations: int = Field(
        default=2,
        ge=0,
        description="default note refinement iterations",
    )

    search_api: SearchAPI = Field(
        default="duckduckgo",
        description="default web search backend",
    )

    llm_api_key: str | None = Field(
        default=None,
        description="single-provider API key for the selected default provider",
    )

    llm_model: str | None = Field(
        default=None,
        description="single-provider model override for the selected default provider",
    )

    llm_base_url: str | None = Field(
        default=None,
        description="single-provider base URL override for OpenAI-compatible providers",
    )

    deepseek_api_key: str | None = Field(
        default=None,
        description="your deepseek api key",
    )

    openai_api_key: str | None = Field(
        default=None,
        description="your openai api key",
    )

    dashscope_api_key: str | None = Field(
        default=None,
        description="your qwen or dashscope api key",
    )

    moonshot_api_key: str | None = Field(
        default=None,
        description="your moonshot api key",
    )

    zhipu_api_key: str | None = Field(
        default=None,
        description="your zhipu api key",
    )

    siliconflow_api_key: str | None = Field(
        default=None,
        description="your siliconflow api key",
    )

    deepseek_model: str = "deepseek-chat"
    openai_model: str = "gpt-4o-mini"
    qwen_model: str = "qwen-plus"
    moonshot_model: str = "moonshot-v1-8k"
    zhipu_model: str = "glm-4-flash"
    siliconflow_model: str = "Qwen/Qwen2.5-7B-Instruct"

    deepseek_base_url: str | None = None
    openai_base_url: str | None = None
    qwen_base_url: str | None = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    moonshot_base_url: str | None = "https://api.moonshot.cn/v1"
    zhipu_base_url: str | None = "https://open.bigmodel.cn/api/paas/v4"
    siliconflow_base_url: str | None = "https://api.siliconflow.cn/v1"

    tavily_api_key: str | None = None
    perplexity_api_key: str | None = None
    searxng_url: str | None = "http://localhost:8888"
    semantic_scholar_api_key: str | None = None

    notes_dir: Path = PROJECT_ROOT / "notes"
    runs_dir: Path = PROJECT_ROOT / "runs"
    reference_cache_dir: Path = PROJECT_ROOT / ".cache" / "references"
    intermediate_dir: Path | None = None
    assets_dir: Path | None = None

    enabled_asset_types: str = Field(
        default="formula,code,mermaid,chart",
        description="comma-separated enabled generated asset types",
    )

    @field_validator(
        "llm_api_key",
        "deepseek_api_key",
        "openai_api_key",
        "dashscope_api_key",
        "moonshot_api_key",
        "zhipu_api_key",
        "siliconflow_api_key",
        "tavily_api_key",
        "perplexity_api_key",
        "semantic_scholar_api_key",
        mode="before",
    )
    @classmethod
    def validate_api_key(cls, value: Any) -> str | None:
        if value is None:
            return None

        value = str(value).strip()
        if not value:
            return None

        lowered = value.lower()
        if lowered.startswith("your_") or lowered in {"none", "null"}:
            return None

        return value

    @field_validator(
        "llm_model",
        "llm_base_url",
        "deepseek_base_url",
        "openai_base_url",
        "qwen_base_url",
        "moonshot_base_url",
        "zhipu_base_url",
        "siliconflow_base_url",
        "searxng_url",
        mode="before",
    )
    @classmethod
    def validate_optional_string(cls, value: Any) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @field_validator("notes_dir", "runs_dir", "reference_cache_dir", mode="before")
    @classmethod
    def validate_required_path(cls, value: Any) -> Path:
        if value is None or str(value).strip() == "":
            raise ValueError("path settings cannot be empty")
        return _resolve_project_path(value)

    @field_validator("intermediate_dir", "assets_dir", mode="before")
    @classmethod
    def validate_optional_path(cls, value: Any) -> Path | None:
        if value is None or str(value).strip() == "":
            return None
        return _resolve_project_path(value)

    @field_validator("enabled_asset_types", mode="before")
    @classmethod
    def validate_enabled_asset_types(cls, value: Any) -> str:
        if value is None:
            return "formula,code,mermaid,chart"
        if isinstance(value, (list, tuple, set)):
            value = ",".join(str(item) for item in value)
        return str(value).strip() or "formula,code,mermaid,chart"

    @property
    def intermediate_dir_path(self) -> Path:
        return self.intermediate_dir or self.notes_dir / "intermediate"

    @property
    def assets_dir_path(self) -> Path:
        return self.assets_dir or self.notes_dir / "assets"

    @property
    def enabled_asset_type_list(self) -> list[AssetType]:
        allowed = {"formula", "code", "mermaid", "chart"}
        values = [
            item.strip().lower()
            for item in self.enabled_asset_types.split(",")
            if item.strip()
        ]
        return [item for item in values if item in allowed]

    def api_key_for(self, provider: LLMProvider) -> str | None:
        api_key_field = _PROVIDER_DEFAULTS[provider]["api_key_field"]
        provider_key = getattr(self, api_key_field)

        if provider_key:
            return provider_key

        if provider == self.default_llm_provider:
            return self.llm_api_key

        return None

    def model_for(self, provider: LLMProvider) -> str:
        if provider == self.default_llm_provider and self.llm_model:
            return self.llm_model
        return getattr(self, f"{provider}_model")

    def base_url_for(self, provider: LLMProvider) -> str | None:
        if provider == self.default_llm_provider and self.llm_base_url:
            return self.llm_base_url
        return getattr(self, f"{provider}_base_url")

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(ENV_DIRECTORY / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )


_settings = None

def get_settings() -> BaseSharedSettings:
    global _settings
    if _settings is None:
        _settings = BaseSharedSettings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
