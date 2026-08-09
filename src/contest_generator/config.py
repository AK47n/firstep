"""本机配置文件：AI API 与工作目录等用户级设置。

配置文件默认位于用户主目录下的 ~/.contest_generator/config.json——在版本
库之外，API key 等敏感信息不入版本库。配置项：AI API（base_url / key /
模型）与工作目录（模块库目录、母版目录——spec：默认在工具工作目录下，
可配置）。
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
DEFAULT_MODEL = "deepseek-v4-flash"

# 工作目录默认值：工具工作目录（配置目录）下的 modules/ 与 masters/
DEFAULT_MODULE_LIBRARY_DIR = Path.home() / CONFIG_DIRNAME / "modules"
DEFAULT_MASTERS_DIR = Path.home() / CONFIG_DIRNAME / "masters"


class ConfigError(ValueError):
    """配置文件缺失、损坏或字段非法，message 说明具体问题。"""


@dataclass(frozen=True)
class AppConfig:
    """应用配置：AI API 与服务的工作目录。"""

    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL
    module_library_dir: Path = DEFAULT_MODULE_LIBRARY_DIR
    masters_dir: Path = DEFAULT_MASTERS_DIR


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
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
    module_library_dir = Path(
        _require_nonempty_str(
            data, "module_library_dir", str(DEFAULT_MODULE_LIBRARY_DIR), path
        )
    )
    masters_dir = Path(
        _require_nonempty_str(data, "masters_dir", str(DEFAULT_MASTERS_DIR), path)
    )

    return AppConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        module_library_dir=module_library_dir,
        masters_dir=masters_dir,
    )


def save_config(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """写入配置文件；父目录不存在时创建。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "base_url": config.base_url,
                "api_key": config.api_key,
                "model": config.model,
                "module_library_dir": str(config.module_library_dir),
                "masters_dir": str(config.masters_dir),
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


def topic_library_dir(module_library_dir: Path) -> Path:
    """赛题库目录：模块库同级目录下的 topics/（工单 01 约定）。

    配置没有独立字段（config.py 不在工单边界内），取模块库同级目录——与
    默认布局（~/.contest_generator/{modules,masters}）同一工作目录；将来
    加配置项时只改这一处。
    """
    return module_library_dir.parent / "topics"


def reference_library_dir(module_library_dir: Path) -> Path:
    """参考文件库目录：模块库平级兄弟 references/（素材库 colocate，工单 02）。

    本批不新增配置项（config.py 冻结），按模块库目录的平级兄弟推导——默认
    布局下 = ~/.contest_generator/references；用户配置模块库位置时参考库跟随。
    """
    return module_library_dir.parent / "references"


def _require_nonempty_str(data: dict, key: str, default: str, path: Path) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{key} 必须是非空字符串：{path}")
    return value
