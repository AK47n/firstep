"""本机配置文件：读写、默认值、错误处理。

AI API key 存用户主目录下的配置文件（版本库之外，不入库）。
"""

import json

import pytest

from contest_generator.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    ConfigError,
    LLMConfig,
    load_config,
    save_config,
)


def test_save_then_load_roundtrip_preserves_config(tmp_path):
    path = tmp_path / "cfg" / "config.json"  # 父目录不存在，save 应自动创建

    save_config(
        LLMConfig(
            base_url="https://example.com/api",
            api_key="sk-test",
            model="deepseek-reasoner",
        ),
        path,
    )

    assert load_config(path) == LLMConfig(
        base_url="https://example.com/api",
        api_key="sk-test",
        model="deepseek-reasoner",
    )


def test_load_applies_defaults_for_optional_fields(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")

    loaded = load_config(path)

    assert loaded.base_url == DEFAULT_BASE_URL
    assert loaded.model == DEFAULT_MODEL


def test_load_missing_file_raises_with_hint(tmp_path):
    with pytest.raises(ConfigError, match="不存在"):
        load_config(tmp_path / "no-config.json")


def test_load_invalid_json_raises(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ConfigError, match="JSON"):
        load_config(path)


@pytest.mark.parametrize("api_key", [None, "", 123])
def test_load_missing_or_invalid_api_key_raises(tmp_path, api_key):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": api_key}), encoding="utf-8")

    with pytest.raises(ConfigError, match="api_key"):
        load_config(path)


def test_saved_file_is_plain_json(tmp_path):
    path = tmp_path / "config.json"

    save_config(LLMConfig(api_key="sk-test"), path)

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "base_url": DEFAULT_BASE_URL,
        "api_key": "sk-test",
        "model": DEFAULT_MODEL,
    }
