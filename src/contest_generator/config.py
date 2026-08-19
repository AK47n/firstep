"""本机配置文件：AI API 与工作目录等用户级设置。

配置文件默认位于用户主目录下的 ~/.contest_generator/config.json——在版本
库之外，API key 等敏感信息不入版本库。配置项：AI API（base_url / key /
模型）、工作目录（模块库目录、母版目录——spec：默认在工具工作目录下，
可配置）与写库自动提交开关（autocommit_enabled，工单 01）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .vision import DEFAULT_VISION_BASE_URL, DEFAULT_VISION_MODEL

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
    autocommit_enabled: bool = True  # 写库动作自动 git 提交开关（工单 01，默认开）
    uv4_path: str = ""  # Keil UV4 可选覆盖（工单 autocompile-loop/01）：空 = 自动探测
    gmake_path: str = ""  # gmake 可选覆盖：空 = 走 PATH 探测
    # CCS 工具链三件套可选覆盖（工单 mspm0-build-makefiles/01）：空 = 自动探测
    # （C:/ti/ccs*/ 扫描）；三件逐件独立（真机 SDK / 编译器分居两个版本目录）
    ccs_sdk_dir: str = ""
    ccs_compiler_dir: str = ""
    ccs_sysconfig_cli: str = ""
    # 本地 LLM 端点可选配置（工单 local-llm-routing/01）：空串 = 本地路由关闭
    local_llm_base_url: str = ""
    local_llm_model: str = ""
    # 视觉通道（工单 vision-eyes/01）：免费云端 GLM-4V-Flash（OpenAI 兼容）。
    # api_key 空 = 视觉功能关闭；base_url / model 缺省填官方免费通道
    vision_base_url: str = DEFAULT_VISION_BASE_URL
    vision_api_key: str = ""
    vision_model: str = DEFAULT_VISION_MODEL
    # LLM 单价覆盖（工单 llm-cost-control/01 + 缓存拆分计价更新）：None = 用内置
    # 默认参考价；dict 形态 {"deepseek": {"input_cache_hit_per_million": x,
    # "input_cache_miss_per_million": y, "output_per_million": z}, "local": {...}}
    # （DeepSeek 输入分缓存命中/未命中两档，官方差价 ~30 倍）；旧形态
    # {"input_per_million": x} 兼容 = 未命中档——条目级脏数据由消费侧静默跳过
    # （展示层旁路）
    llm_prices: dict | None = None
    # 计费时段（工单 01 扩展）：peak 高峰 / off_peak 空闲，决定未覆盖项的
    # 基准价（官方该时段价）；覆盖项（llm_prices）优先。缺省 peak
    llm_price_period: str = "peak"
    # 推荐缓存开关（工单 llm-cost-control/02）：默认开——同题重跑推荐命中
    # 缓存直出 done 载荷（省最贵的推荐段 LLM 调用）；关闭 = 每次真实推荐
    recommend_cache_enabled: bool = True
    # 推荐收敛轮数上限（工单 recommend-speedup-v2/01）：2-4，缺省 4。
    # 调低 = 更快但更少自检修订（1 轮无收敛意义，配置层拒绝）；核验轮短标记
    # 提前停生效后实际轮数通常少于上限
    recommend_max_rounds: int = 4


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
    autocommit_enabled = data.get("autocommit_enabled", True)
    if not isinstance(autocommit_enabled, bool):
        raise ConfigError(f"autocommit_enabled 必须是布尔值：{path}")

    # 工具链可选覆盖（工单 autocompile-loop/01）：空串 = 自动探测；类型非法
    # 大声失败（与其余字段同严格度）
    uv4_path = data.get("uv4_path", "")
    if not isinstance(uv4_path, str):
        raise ConfigError(f"uv4_path 必须是字符串：{path}")
    gmake_path = data.get("gmake_path", "")
    if not isinstance(gmake_path, str):
        raise ConfigError(f"gmake_path 必须是字符串：{path}")
    # CCS 三件套覆盖（工单 mspm0-build-makefiles/01）：空串 = 自动探测
    ccs_sdk_dir = data.get("ccs_sdk_dir", "")
    if not isinstance(ccs_sdk_dir, str):
        raise ConfigError(f"ccs_sdk_dir 必须是字符串：{path}")
    ccs_compiler_dir = data.get("ccs_compiler_dir", "")
    if not isinstance(ccs_compiler_dir, str):
        raise ConfigError(f"ccs_compiler_dir 必须是字符串：{path}")
    ccs_sysconfig_cli = data.get("ccs_sysconfig_cli", "")
    if not isinstance(ccs_sysconfig_cli, str):
        raise ConfigError(f"ccs_sysconfig_cli 必须是字符串：{path}")
    # 本地 LLM 端点（工单 local-llm-routing/01）：空串 = 本地路由关闭；类型非法
    # 大声失败（与其余字段同严格度）
    local_llm_base_url = data.get("local_llm_base_url", "")
    if not isinstance(local_llm_base_url, str):
        raise ConfigError(f"local_llm_base_url 必须是字符串：{path}")
    local_llm_model = data.get("local_llm_model", "")
    if not isinstance(local_llm_model, str):
        raise ConfigError(f"local_llm_model 必须是字符串：{path}")
    # 视觉通道（工单 vision-eyes/01）：api_key 空 = 关闭；旧 config 缺字段或
    # base/model 为空串时回落官方免费默认值（只填 key 即可用）。
    vision_base_url = data.get("vision_base_url", DEFAULT_VISION_BASE_URL)
    if not isinstance(vision_base_url, str):
        raise ConfigError(f"vision_base_url 必须是字符串：{path}")
    if not vision_base_url.strip():
        vision_base_url = DEFAULT_VISION_BASE_URL
    vision_api_key = data.get("vision_api_key", "")
    if not isinstance(vision_api_key, str):
        raise ConfigError(f"vision_api_key 必须是字符串：{path}")
    vision_model = data.get("vision_model", DEFAULT_VISION_MODEL)
    if not isinstance(vision_model, str):
        raise ConfigError(f"vision_model 必须是字符串：{path}")
    if not vision_model.strip():
        vision_model = DEFAULT_VISION_MODEL
    # LLM 单价覆盖（工单 llm-cost-control/01）：缺省 None = 内置默认价
    llm_prices = data.get("llm_prices")
    if llm_prices is not None and not isinstance(llm_prices, dict):
        raise ConfigError(f"llm_prices 必须是 JSON 对象或省略：{path}")
    # 推荐缓存开关（工单 llm-cost-control/02）：缺省开
    recommend_cache_enabled = data.get("recommend_cache_enabled", True)
    if not isinstance(recommend_cache_enabled, bool):
        raise ConfigError(f"recommend_cache_enabled 必须是布尔值：{path}")
    # 推荐收敛轮数上限（工单 recommend-speedup-v2/01）：2-4，缺省 4
    recommend_max_rounds = data.get("recommend_max_rounds", 4)
    if (
        not isinstance(recommend_max_rounds, int)
        or isinstance(recommend_max_rounds, bool)
        or not 2 <= recommend_max_rounds <= 4
    ):
        raise ConfigError(f"recommend_max_rounds 必须是 2-4 的整数：{path}")
    # 计费时段（工单 01 扩展）：peak 高峰 / off_peak 空闲，缺省 peak
    llm_price_period = data.get("llm_price_period", "peak")
    if llm_price_period not in ("peak", "off_peak"):
        raise ConfigError(f"llm_price_period 必须是 peak 或 off_peak：{path}")

    return AppConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        module_library_dir=module_library_dir,
        masters_dir=masters_dir,
        autocommit_enabled=autocommit_enabled,
        uv4_path=uv4_path,
        gmake_path=gmake_path,
        ccs_sdk_dir=ccs_sdk_dir,
        ccs_compiler_dir=ccs_compiler_dir,
        ccs_sysconfig_cli=ccs_sysconfig_cli,
        local_llm_base_url=local_llm_base_url,
        local_llm_model=local_llm_model,
        vision_base_url=vision_base_url,
        vision_api_key=vision_api_key,
        vision_model=vision_model,
        llm_prices=llm_prices,
        recommend_cache_enabled=recommend_cache_enabled,
        recommend_max_rounds=recommend_max_rounds,
        llm_price_period=llm_price_period,
    )


def save_config(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """写入配置文件；父目录不存在时创建。

    llm_prices 为 None（未覆盖）时不写键——缺省语义与 load 一致，配置文件
    保持最小（既有精确 JSON 断言不受新字段扰动）。
    """
    data: dict = {
        "base_url": config.base_url,
        "api_key": config.api_key,
        "model": config.model,
        "module_library_dir": str(config.module_library_dir),
        "masters_dir": str(config.masters_dir),
        "autocommit_enabled": config.autocommit_enabled,
        "uv4_path": config.uv4_path,
        "gmake_path": config.gmake_path,
        "ccs_sdk_dir": config.ccs_sdk_dir,
        "ccs_compiler_dir": config.ccs_compiler_dir,
        "ccs_sysconfig_cli": config.ccs_sysconfig_cli,
        "local_llm_base_url": config.local_llm_base_url,
        "local_llm_model": config.local_llm_model,
        "vision_base_url": config.vision_base_url,
        "vision_api_key": config.vision_api_key,
        "vision_model": config.vision_model,
        "recommend_cache_enabled": config.recommend_cache_enabled,
        "recommend_max_rounds": config.recommend_max_rounds,
        "llm_price_period": config.llm_price_period,
    }
    if config.llm_prices is not None:
        data["llm_prices"] = config.llm_prices
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
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


def materials_dir(module_library_dir: Path) -> Path:
    """素材备份根：参考条目二进制素材（PDF / zip 等）的镜像目录。

    与 reference_library_dir 同源推导（config.py 冻结，不新增配置项）——素材
    工具脚本以工作区根为根写 sources/materials，工作区根可能直接装模块库
    （默认布局 ~/.contest_generator/modules → 同级 sources/），也可能模块库
    在 library/ 子目录下（仓库布局 firstep/library/modules → 备份在仓库根
    firstep/sources/）。两级候选都取目录实况判定，避免把推导钉死在 404 上；
    两处都没有 = 返回优先候选（resolve_entry_file 对缺失文件抛 ReferenceError
    → 400，不因推导空根而炸）。
    """
    sibling = module_library_dir.parent / "sources" / "materials"
    if sibling.is_dir():
        return sibling
    repo_root = module_library_dir.parent.parent / "sources" / "materials"
    return repo_root if repo_root.is_dir() else sibling


def _require_nonempty_str(data: dict, key: str, default: str, path: Path) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{key} 必须是非空字符串：{path}")
    return value
