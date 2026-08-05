"""本机配置文件：AI API 等用户级设置。

配置文件默认位于用户主目录下的 ~/.contest_generator/config.json——在版本
库之外，API key 等敏感信息不入版本库。配置项随工单扩展（模块库目录、
母版目录等后续工单再加）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIRNAME = ".contest_generator"
CONFIG_FILENAME = "config.json"
DEFAULT_CONFIG_PATH = Path.home() / CONFIG_DIRNAME / CONFIG_FILENAME

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class ConfigError(ValueError):
    """配置文件缺失、损坏或字段非法，message 说明具体问题。"""


@dataclass(frozen=True)
class LLMConfig:
    """AI 配置：服务地址 / API key / 模型名。"""

    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> LLMConfig:
    """读取配置文件；缺失 / 损坏 / 缺 api_key 抛 ConfigError。"""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"配置文件不存在：{path}（请先在设置里配置 AI API）") from None
    except OSError as exc:
        raise ConfigError(f"无法读取配置文件 {path}: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件不是合法 JSON：{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件必须是 JSON 对象：{path}")

    api_key = data.get("api_key")
    if not isinstance(api_key, str) or not api_key:
        raise ConfigError(f"配置缺少 api_key：{path}")

    base_url = _require_nonempty_str(data, "base_url", DEFAULT_BASE_URL, path)
    model = _require_nonempty_str(data, "model", DEFAULT_MODEL, path)

    return LLMConfig(base_url=base_url, api_key=api_key, model=model)


def save_config(config: LLMConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """写入配置文件；父目录不存在时创建。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "base_url": config.base_url,
                "api_key": config.api_key,
                "model": config.model,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)  # POSIX 下仅本人可读写；Windows 无此权限模型
    except OSError:
        pass


def _require_nonempty_str(data: dict, key: str, default: str, path: Path) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{key} 必须是非空字符串：{path}")
    return value
