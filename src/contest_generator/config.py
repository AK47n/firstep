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

from .tool_root import find_tool_root
from .vision import DEFAULT_VISION_BASE_URL, DEFAULT_VISION_MODEL

CONFIG_DIRNAME = ".contest_generator"
CONFIG_FILENAME = "config.json"
DEFAULT_CONFIG_PATH = Path.home() / CONFIG_DIRNAME / CONFIG_FILENAME

# 配置文件路径覆盖口（工单 ci-gate-fixes/01）：浏览器门禁夹具 / CI / 高级用户
# 指到自己的配置，不必伪造 HOME（伪造 HOME 会连带改掉数据目录、最近工程等一串
# 路径推导——那会把一个显式契约换成全局副作用）。合法值 = 非空字符串。
CONFIG_PATH_ENV = "FIRSTEP_CONFIG_PATH"


def config_path() -> Path:
    """本机配置文件路径：`FIRSTEP_CONFIG_PATH` 覆盖，否则缺省位置。

    **必须调用期解析**：缺省参数若写成 `path: Path = DEFAULT_CONFIG_PATH`，
    取值发生在**导入期**——子进程里设的环境变量对已经导入的模块不生效，
    夹具那条路就会静默地读回用户主目录（正是本单要修的那个假绿）。
    """
    override = os.environ.get(CONFIG_PATH_ENV, "").strip()
    return Path(override) if override else DEFAULT_CONFIG_PATH


def bundled_library_dirs() -> tuple[Path, Path] | None:
    """随软件分发的库目录（模块库 / 母版库）；不在 = None。

    判据复用工具根单源 `tool_root.find_tool_root`：库随软件仓库走（ADR 0008），
    故 `<工具根>/library/{modules,masters}` 就是**同一对**路径——`install.bat`
    首次安装时写给用户的正是它（工单 beginner-guide-enrich/03）。

    站点包安装等场景工具根下没有 `library/` → 返回 None，调用方按「没有随包库」
    处理（不假装有库）。
    """
    root = find_tool_root(__file__)
    modules = root / "library" / "modules"
    masters = root / "library" / "masters"
    if modules.is_dir() and masters.is_dir():
        return (modules, masters)
    return None

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"

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
    # 烧录工具可选覆盖（工单 flash-deploy/01）：空 = 自动探测（STM32 走
    # OpenOCD/st-flash 的 PATH、MSPM0 走 C:/ti/ccs*/ 扫 DSLite）
    openocd_path: str = ""
    stflash_path: str = ""
    dslite_path: str = ""
    # 本地 LLM 端点可选配置（工单 local-llm-routing/01）：空串 = 本地路由关闭
    local_llm_base_url: str = ""
    local_llm_model: str = ""
    # 视觉通道（工单 vision-deepseek-native/01，默认 DeepSeek 官方视觉）：
    # OpenAI 兼容 /chat/completions；api_key 空 = 装配层复用主 key（仅 DeepSeek
    # 官方端点）；base_url / model 缺省填官方默认值
    vision_base_url: str = DEFAULT_VISION_BASE_URL
    vision_api_key: str = ""
    vision_model: str = DEFAULT_VISION_MODEL
    # 问答式精注记开关（工单 vision-detail-qa/01）：默认开——图注一轮描述后
    # 追加二轮视觉追问补细节（型号/尺寸标注/引脚号）；关闭 = 仅一轮描述
    # （每张图省一次视觉调用）
    vision_detail_qa: bool = True
    # LLM 单价覆盖（工单 llm-cost-control/01 + 缓存拆分计价更新）：None = 用内置
    # 默认参考价；dict 形态 {"deepseek": {"input_cache_hit_per_million": x,
    # "input_cache_miss_per_million": y, "output_per_million": z}, "local": {...}}
    # （DeepSeek 输入分缓存命中/未命中两档，官方差价 ~30 倍）；旧形态
    # {"input_per_million": x} 兼容 = 未命中档——条目级脏数据由消费侧静默跳过
    # （展示层旁路）
    llm_prices: dict | None = None
    # 计费时段（工单 01 扩展）：peak 高峰 / off_peak 空闲，决定未覆盖项的
    # 基准价（官方该时段价）；覆盖项（llm_prices）优先。缺省 off_peak（2026-08
    # 起默认低谷——本地工具夜间/业余使用为主，基准价按官方空闲档计）
    llm_price_period: str = "off_peak"
    # 推荐缓存开关（工单 llm-cost-control/02）：默认开——同题重跑推荐命中
    # 缓存直出 done 载荷（省最贵的推荐段 LLM 调用）；关闭 = 每次真实推荐
    recommend_cache_enabled: bool = True
    # 推荐收敛轮数上限（工单 recommend-speedup-v2/01）：2-4，缺省 4。
    # 调低 = 更快但更少自检修订（1 轮无收敛意义，配置层拒绝）；核验轮短标记
    # 提前停生效后实际轮数通常少于上限
    recommend_max_rounds: int = 4


def load_config(path: Path | None = None) -> AppConfig:
    """读取配置文件；缺失 / 损坏 / 缺 api_key 抛 ConfigError。

    **唯一的例外——调用方没指定路径（`path=None`，即"用本机的缺省位置"）且
    随包库在场**（工单 ci-gate-fixes/01）：此时用随包库而不是抛错。理由：库随软件
    分发（ADR 0008），而首次安装本来就要把库指向随包那一份（`write_bootstrap_config`
    / `install.bat`）——没跑过 install.bat 的机器（CI runner、新 clone）此前**起服务
    必然答不出任何库相关的只读端点**，浏览器门禁的端点哨兵就是这么在 CI 上红的。

    契约边界（踩过一次，别再合）：**显式给了 path 就是显式意图**——文件不在就照旧
    抛错，不拿随包库去替。测试用 `AppContext(config_path=…/"never-written.json")`
    表达「这台机器没配置」，若显式路径也回退，那 9 条「未配置」用例会集体静默变绿
    到反方向（实测：`api_configured` 从 False 变 True）。

    回退**只认"文件不在"这一种**（判据 = `path.is_file()`，不是 `except ConfigError`）：
    配置存在但坏 JSON / 缺 api_key 照旧大声抛错——否则用户手上那份写坏的配置会被
    静默换成随包库，"用户写了什么就是什么"就没了（评审 2026-09-25 抓到的过宽判据）。

    `api_key` 仍是空串 → 应用照旧停在「未配置 AI API」引导态（与
    `write_bootstrap_config` 写出来的状态一致，本次不改）。
    """
    if path is None:
        path = config_path()
        if not path.is_file():
            bundled = bundled_library_dirs()
            if bundled is None:
                raise ConfigError(
                    f"配置文件不存在：{path}（请先在设置里配置 AI API）"
                ) from None
            modules, masters = bundled
            return AppConfig(module_library_dir=modules, masters_dir=masters)
    return _read_config(path)


def _read_config(path: Path) -> AppConfig:
    """按给定路径读配置（显式路径的唯一入口，不含任何回退）。"""
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
    # 烧录工具覆盖（工单 flash-deploy/01）：空串 = 自动探测
    openocd_path = data.get("openocd_path", "")
    if not isinstance(openocd_path, str):
        raise ConfigError(f"openocd_path 必须是字符串：{path}")
    stflash_path = data.get("stflash_path", "")
    if not isinstance(stflash_path, str):
        raise ConfigError(f"stflash_path 必须是字符串：{path}")
    dslite_path = data.get("dslite_path", "")
    if not isinstance(dslite_path, str):
        raise ConfigError(f"dslite_path 必须是字符串：{path}")
    # 本地 LLM 端点（工单 local-llm-routing/01）：空串 = 本地路由关闭；类型非法
    # 大声失败（与其余字段同严格度）
    local_llm_base_url = data.get("local_llm_base_url", "")
    if not isinstance(local_llm_base_url, str):
        raise ConfigError(f"local_llm_base_url 必须是字符串：{path}")
    local_llm_model = data.get("local_llm_model", "")
    if not isinstance(local_llm_model, str):
        raise ConfigError(f"local_llm_model 必须是字符串：{path}")
    # 视觉通道（工单 vision-eyes/01 + vision-deepseek-native/01）：api_key 空 =
    # 复用主 key（装配层判定）；旧 config 缺字段或 base/model 为空串时回落
    # DeepSeek 官方默认值（只填 key 即可用）。
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
    vision_detail_qa = data.get("vision_detail_qa", True)
    if not isinstance(vision_detail_qa, bool):
        raise ConfigError(f"vision_detail_qa 必须是布尔值：{path}")
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
    llm_price_period = data.get("llm_price_period", "off_peak")
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
        openocd_path=openocd_path,
        stflash_path=stflash_path,
        dslite_path=dslite_path,
        local_llm_base_url=local_llm_base_url,
        local_llm_model=local_llm_model,
        vision_base_url=vision_base_url,
        vision_api_key=vision_api_key,
        vision_model=vision_model,
        vision_detail_qa=vision_detail_qa,
        llm_prices=llm_prices,
        recommend_cache_enabled=recommend_cache_enabled,
        recommend_max_rounds=recommend_max_rounds,
        llm_price_period=llm_price_period,
    )


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """写入配置文件；父目录不存在时创建。

    缺省路径走 `config_path()`（**调用期**解析 `FIRSTEP_CONFIG_PATH`）：否则设了
    那个环境变量时"读一处、写另一处"——设置页保存会把改动写回用户主目录，
    而应用读的是指过去的那份（评审 2026-09-25 抓到的半截口子）。

    llm_prices 为 None（未覆盖）时不写键——缺省语义与 load 一致，配置文件
    保持最小（既有精确 JSON 断言不受新字段扰动）。
    """
    if path is None:
        path = config_path()
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
        "openocd_path": config.openocd_path,
        "stflash_path": config.stflash_path,
        "dslite_path": config.dslite_path,
        "local_llm_base_url": config.local_llm_base_url,
        "local_llm_model": config.local_llm_model,
        "vision_base_url": config.vision_base_url,
        "vision_api_key": config.vision_api_key,
        "vision_model": config.vision_model,
        "vision_detail_qa": config.vision_detail_qa,
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


def write_bootstrap_config(
    module_library_dir: Path,
    masters_dir: Path,
    path: Path = DEFAULT_CONFIG_PATH,
) -> bool:
    """首次安装引导配置（工单 beginner-guide-enrich/03）：配置文件不存在时
    写入最小配置——api_key 空串（应用保持「未配置 AI API」引导态，AI 功能不可用），
    模块库 / 母版库指向随包 library。已存在一律不动（幂等、尊重用户已有配置）。
    返回 True=已写入；False=已存在跳过。写入失败抛 OSError，由调用方决定处理。

    这里**刻意写死 `DEFAULT_CONFIG_PATH`**（不走 `config_path()`）：它是 install.bat
    给**这台机器的用户**装配置的那一步，不是"当前进程该读哪份配置"——被
    `FIRSTEP_CONFIG_PATH`（夹具 / CI 用的口子）带走就会把引导配置写进临时目录。
    """
    if path.exists():
        return False
    data = {
        "api_key": "",
        "module_library_dir": str(module_library_dir),
        "masters_dir": str(masters_dir),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def raw_library_dirs(path: Path | None = None) -> tuple[Path | None, Path | None]:
    """从配置文件原始字段取模块库 / 母版目录（工单 beginner-guide-enrich/03）。

    缺省路径走 `config_path()`（**调用期**解析），与 `load_config` / `save_config`
    同一口径——设了 `FIRSTEP_CONFIG_PATH` 时读 / 写 / 取原始字段指向同一份文件。

    只解析原始 JSON（无 key 的引导配置也可读）；两字段都必须是 JSON 对象里
    的非空字符串，缺一 / 非法 = 该项 None（调用方回退默认）。供设置读取接口
    使用：配置存在但未配 key（load_config 抛 ConfigError）时仍返回磁盘目录，
    避免首次保存设置把 install.bat 自动指向的库目录覆盖成默认值。
    """
    if path is None:
        path = config_path()
    if not path.is_file():
        return (None, None)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (None, None)
    if not isinstance(data, dict):
        return (None, None)

    def _dir(key: str) -> Path | None:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value)
        return None

    return (_dir("module_library_dir"), _dir("masters_dir"))


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


def pdf_trash_dir(materials: Path) -> Path:
    """PDF 回收目录：素材根平级兄弟 .trash-pdf/（工单 06）。

    与 materials_dir 同源推导（config.py 冻结，不新增配置项）——素材根随模块
    库位置走，回收目录跟随。回收 = 移动不真删（git 忽略 + 手可恢复 + git 历史
    双保险），前端的确认弹窗把去向暴露给用户。
    """
    return materials.parent / ".trash-pdf"


def _require_nonempty_str(data: dict, key: str, default: str, path: Path) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{key} 必须是非空字符串：{path}")
    return value
