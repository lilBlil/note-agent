from config.settings import BaseSharedSettings, PROJECT_ROOT


def test_placeholder_api_keys_are_treated_as_missing():
    settings = BaseSharedSettings(
        llm_api_key="your_provider_api_key",
        deepseek_api_key="your_deepseek_api_key",
        openai_api_key="",
    )

    assert settings.llm_api_key is None
    assert settings.deepseek_api_key is None
    assert settings.openai_api_key is None


def test_unified_api_key_only_applies_to_default_provider():
    settings = BaseSharedSettings(
        default_llm_provider="deepseek",
        llm_api_key="shared-key",
        deepseek_api_key=None,
        openai_api_key=None,
    )

    assert settings.api_key_for("deepseek") == "shared-key"
    assert settings.api_key_for("openai") is None


def test_provider_specific_key_takes_priority_and_qwen_uses_dashscope():
    settings = BaseSharedSettings(
        default_llm_provider="qwen",
        llm_api_key="shared-key",
        dashscope_api_key="dashscope-key",
    )

    assert settings.api_key_for("qwen") == "dashscope-key"


def test_relative_paths_resolve_from_project_root():
    settings = BaseSharedSettings(
        notes_dir="custom_notes",
        runs_dir="custom_runs",
        reference_cache_dir=".cache/custom_references",
        intermediate_dir="custom_intermediate",
        assets_dir="custom_assets",
    )

    assert settings.notes_dir == PROJECT_ROOT / "custom_notes"
    assert settings.runs_dir == PROJECT_ROOT / "custom_runs"
    assert settings.reference_cache_dir == PROJECT_ROOT / ".cache" / "custom_references"
    assert settings.intermediate_dir_path == PROJECT_ROOT / "custom_intermediate"
    assert settings.assets_dir_path == PROJECT_ROOT / "custom_assets"


def test_enabled_asset_types_filters_unknown_values():
    settings = BaseSharedSettings(enabled_asset_types="formula,bad,chart")

    assert settings.enabled_asset_type_list == ["formula", "chart"]
