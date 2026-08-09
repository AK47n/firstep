"""母版库 CRUD（入库 / 浏览 / 删除）与域错误定义（MasterError）唯一出处。

母版库：磁盘目录即数据库，母版库根下每个平台一个目录（工程文件本体）+ 同名
<platform>.json 元数据（提炼来源、入库时结构分析的警告）。元数据放目录外的
平级文件：母版目录会被生成器整体复制，内部带 json（如 master.json）会污染
生成的工程。

任何从平台名拼路径的操作（浏览 / 删除 / 入库）都先校验平台名合法性，杜绝
借平台名逃出母版库的路径穿越。母版库的物理位置由调用方传入（后续工单接入
本机配置），测试用 tmp_path。

架构深化 v5 三轴拆块（工单 01）：母版库 CRUD 从 master.py 拆出，master 只留
蒸馏编排；本模块不 import categories（防环：categories 的启动验证要用本模块
的 MasterError，依赖方向 master_store → categories 不存在）。工程配置文件
后缀表（PLATFORM_CONFIG_FILE_SUFFIXES）单源在 platforms.py（工单 04 收敛，
词表层谁都能 import 无循环），本模块只消费。
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .autocommit import commit_after_write
from .entry_store import (
    StoreError,
    StoreParseError,
    StoreReadError,
    StoreShapeError,
    delete_entry,
    read_json,
    require_str,
    validate_store_key,
)
# 入库结构校验是母版库域操作（存储域），不走蒸馏编排接缝（工单 04）：其唯一
# 生产消费方就是入库；蒸馏适配器不设 validate 能力，避免死方法
from .keil import KeilProjectError, validate_project_structure
from .platforms import (
    KNOWN_PLATFORMS,
    PLATFORM_CONFIG_FILE_SUFFIXES,
    PLATFORM_MSPM0,
    PLATFORM_STM32,
)
from .treewalk import BUILD_ARTIFACT_DIRS, iter_project_files

_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")


class MasterError(ValueError):
    """母版提炼 / 管理失败，message 说明具体问题。"""


@dataclass(frozen=True)
class StructureAnalysis:
    """入库时的结构分析结果。"""

    platform: str
    warnings: tuple[str, ...]  # 非致命问题（构建产物残留等）


@dataclass(frozen=True)
class MasterMeta:
    """母版元数据（母版库根下的 <platform>.json）。"""

    platform: str
    sources: tuple[str, ...]  # 提炼来源工程名
    warnings: tuple[str, ...]  # 入库时结构分析的警告

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "sources": list(self.sources),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MasterMeta":
        platform = _require_str(data, "platform")
        sources = _require_str_list(data, "sources")
        warnings = _require_str_list(data, "warnings")
        return cls(
            platform=platform, sources=tuple(sources), warnings=tuple(warnings)
        )


# ---------------------------------------------------------------------------
# 母版库：入库（结构分析 + 可更换）、浏览、删除
# ---------------------------------------------------------------------------


def master_project_dir(masters_dir: Path, platform: str) -> Path:
    """母版在库里的目录位置：<masters_dir>/<platform>（库布局的唯一出处）。

    import_master / get_master / delete_master 与生成流程共用这一条布局规则；
    平台名先过合法性校验——借平台名拼路径逃出母版库在入口处就被拦住。
    """
    _validate_store_key(platform)
    return masters_dir / platform


def analyze_structure(master_dir: Path, platform: str) -> StructureAnalysis:
    """入库前的结构分析：平台配置文件缺失 / 编译链结构残缺硬失败，其余进警告。

    平台配置文件缺失说明母版无法被 IDE 打开，拒绝入库；Keil 母版还校验
    .uvprojx 的编译链完整性（配置节点齐全 + 工程树引用覆盖全部保留源码，
    见 _validate_keil_structure）——AI 整合出的 .uvprojx"XML 合法但结构残缺"
    曾照样入库，生成时才被 KeilPatcher 拒绝（判例 09）。构建产物目录等
    非母版内容只给警告（生成器复制时会忽略 .git，构建目录会原样带进新工程，
    建议清理）。
    """
    _validate_known_platform(platform)
    if not master_dir.is_dir():
        raise MasterError(f"母版目录不存在：{master_dir}")
    for suffix in PLATFORM_CONFIG_FILE_SUFFIXES[platform]:
        if not _find_config_files(master_dir, f"*{suffix}"):
            raise MasterError(
                f"母版缺少平台 {platform} 的工程配置文件（{suffix}），拒绝入库"
            )
    if platform == PLATFORM_STM32:
        _validate_keil_structure(master_dir)
    warnings: list[str] = []
    for name in sorted(BUILD_ARTIFACT_DIRS):
        if (master_dir / name).is_dir():
            warnings.append(f"母版含 {name}/ 构建产物目录，建议清理")
    return StructureAnalysis(platform=platform, warnings=tuple(warnings))


def _validate_keil_structure(master_dir: Path) -> None:
    """Keil 母版入库前的编译链结构校验（格式知识归 keil.py）。

    判例 09（用户实测）：AI 把两工程各自的 .uvprojx 判了 merge，整合产物
    XML 合法但组被清空（丢了启动文件 / system_stm32f10x.c 的引用）、连
    Cads/IncludePath 节点都没了——旧校验只查配置文件存在，坏母版照样入库、
    到生成时 KeilPatcher 才拒绝。校验失败在入库前大声拒绝（中文说明缺什么），
    兑现"绝不产出残缺工程"不变量。工程内保留源码清单按扫描同一套忽略规则
    计算（.git / 构建输出目录不进清单）。
    """
    expected: list[str] = []
    for path in iter_project_files(master_dir):
        if path.suffix.lower() in (".c", ".s"):
            expected.append(path.relative_to(master_dir).as_posix())
    try:
        validate_project_structure(master_dir, expected)
    except KeilProjectError as exc:
        raise MasterError(f"母版 .uvprojx 结构不完整，拒绝入库：{exc}") from exc


def import_master(
    masters_dir: Path,
    platform: str,
    source_dir: Path,
    sources: Sequence[str] = (),
) -> MasterMeta:
    """母版入库：结构分析 → 复制到临时目录 → 整体替换同平台旧母版。

    每平台一个母版：目标已存在时整体更换。先分析后动盘，分析失败不落任何
    文件；旧母版先挪到备份目录再换入新母版，中途失败把备份换回来——既有
    母版在任意失败点都完好。旧母版被占用（Keil µVision / 文件资源管理器
    开着）时改名失败：绝不碰旧母版（rmtree 会把只锁住部分的旧母版删残，
    真实事故），抛中文占用说明。
    """
    _validate_store_key(platform)
    analysis = analyze_structure(source_dir, platform)
    masters_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = masters_dir / f".{platform}.importing"
    backup_dir = masters_dir / f".{platform}.backup"
    shutil.rmtree(temp_dir, ignore_errors=True)  # 清掉上次失败残留
    shutil.copytree(source_dir, temp_dir)
    target_dir = masters_dir / platform
    if target_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)
        if backup_dir.exists():
            # 备份目录清理不掉（被占用）：改名只会撞上非空目录，Windows 报
            # WinError 5，这里用中文讲清原因而不是裸抛拒绝访问
            raise MasterError(
                f"旧备份 {backup_dir.name} 目录清理失败（可能被占用），"
                "请先关闭占用程序后重试导入"
            )
    moved_to_backup = False
    try:
        if target_dir.exists():
            os.replace(target_dir, backup_dir)  # 旧母版先挪开
            moved_to_backup = True
        os.replace(temp_dir, target_dir)  # 新母版原子换入
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if moved_to_backup:
            # 旧母版已在备份目录：清掉半换入的新母版，把旧母版换回来
            shutil.rmtree(target_dir, ignore_errors=True)
            if backup_dir.exists():
                os.replace(backup_dir, target_dir)  # 回滚旧母版
            raise
        if target_dir.exists():
            # 旧母版从未挪动（改名失败）：绝不能碰它——rmtree 会把只锁住
            # 部分文件的旧母版删残（判例：真实事故，母版只剩空壳）
            raise MasterError(
                f"母版替换失败：旧母版目录 {target_dir.name} 被占用，无法挪动。"
                "通常是 Keil µVision 或文件资源管理器还打开着该目录，"
                "请先关闭再重试导入（杀毒软件扫描期间偶发，稍后重试亦可）"
            ) from None
        raise
    shutil.rmtree(backup_dir, ignore_errors=True)

    meta = MasterMeta(
        platform=platform,
        sources=tuple(sources),
        warnings=analysis.warnings,
    )
    _write_meta(masters_dir, meta)
    commit_after_write(masters_dir, f"lib: import master {platform}")
    return meta


def list_masters(masters_dir: Path) -> list[MasterMeta]:
    """返回母版库中全部母版（按平台排序）；元数据缺失或损坏抛 MasterError。"""
    if not masters_dir.is_dir():
        return []
    metas: list[MasterMeta] = []
    for entry in sorted(masters_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue  # 散文件与导入中的临时目录不影响浏览
        metas.append(get_master(masters_dir, entry.name))
    return metas


def get_master(masters_dir: Path, platform: str) -> MasterMeta:
    """读取单个母版元数据；不存在或损坏抛 MasterError。

    读盘 / 解析 / 形状校验走 entry_store 原语（read_json），错误类型与文案
    仍归本模块。
    """
    _validate_store_key(platform)
    meta_path = masters_dir / f"{platform}.json"
    try:
        data = read_json(masters_dir, f"{platform}.json")
    except StoreReadError as exc:
        if isinstance(exc.error, FileNotFoundError):
            raise MasterError(f"母版 {platform!r} 不存在") from None
        raise MasterError(f"母版 {platform!r} 的元数据无法读取：{exc.error}") from exc
    except StoreParseError as exc:
        raise MasterError(f"母版 {platform!r} 的元数据不是合法 JSON：{exc.error}") from exc
    except StoreShapeError:
        raise MasterError(f"{meta_path} 必须是 JSON 对象") from None
    try:
        return MasterMeta.from_dict(data)
    except MasterError as exc:
        raise MasterError(f"母版 {platform!r} 的元数据不合法：{exc}") from exc


def delete_master(masters_dir: Path, platform: str) -> None:
    """删除母版：工程目录与元数据文件一并移除（目录存在校验走 entry_store 原语）。"""
    _validate_store_key(platform)
    try:
        delete_entry(masters_dir, platform)
    except StoreError:
        raise MasterError(f"母版 {platform!r} 不存在") from None
    (masters_dir / f"{platform}.json").unlink(missing_ok=True)
    commit_after_write(masters_dir, f"lib: delete master {platform}")


# ---------------------------------------------------------------------------
# 校验与辅助
# ---------------------------------------------------------------------------


def _find_config_files(project_dir: Path, pattern: str) -> list[Path]:
    """递归查找工程配置文件：统一噪音跳过规则（treewalk.iter_project_files）。"""
    return list(iter_project_files(project_dir, pattern=pattern))


def _validate_store_key(platform: str) -> None:
    try:
        validate_store_key(platform, _SLUG_PATTERN, "平台名")
    except StoreError:
        raise MasterError(
            f"非法平台名：{platform!r}（只能含字母数字下划线连字符，且以字母或数字开头）"
        ) from None


def _validate_known_platform(platform: str) -> None:
    if platform not in KNOWN_PLATFORMS:
        raise MasterError(f"未知平台 {platform!r}（已知：{'、'.join(KNOWN_PLATFORMS)}）")


def _write_meta(masters_dir: Path, meta: MasterMeta) -> None:
    """写元数据：先写临时文件再原子换入，写失败不会留下损坏的 json。"""
    target = masters_dir / f"{meta.platform}.json"
    temp = masters_dir / f".{meta.platform}.json.tmp"
    temp.write_text(
        json.dumps(meta.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp, target)


def _require_str(data: dict[str, Any], key: str) -> str:
    try:
        return require_str(data, key)
    except StoreError:
        raise MasterError(f"缺少必填字段：{key}") from None


def _require_str_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise MasterError(f"{key} 必须是非空字符串列表")
    return value
