"""平台工程修改器：统一接口 + 注册表。

生成器核心把模块文件复制、main.c 落位等公共逻辑做完后，把工程目录交给
注册表里对应平台的修改器（Keil 改 .uvprojx、CCS 改 .cproject 等）。
核心只认识平台名，不绑定任何平台格式。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .ccs import CcsPatcher, include_search_dirs as _ccs_include_search_dirs
from .keil import KeilPatcher, include_search_dirs as _keil_include_search_dirs
from .platforms import PLATFORM_MSPM0, PLATFORM_STM32


class UnknownPlatformError(ValueError):
    """注册表里没有该平台的修改器。"""


class ProjectPatcher(Protocol):
    """把已就位的模块文件注册进平台工程（.uvprojx / .cproject 等）。

    patch 被调用时，project_dir 内已完成：母版文件复制、模块文件
    复制到 modules/<slug>/ 下、main.c 落位。路径均为相对 project_dir。

    参数:
        project_dir: 生成完毕的工程目录
        module_files: 已复制的模块文件路径（相对 project_dir）
        include_dirs: 需要加入 include path 的目录（相对 project_dir，
            已去重，按首次出现顺序）
    """

    def patch(
        self,
        project_dir: Path,
        module_files: Sequence[Path],
        include_dirs: Sequence[Path],
    ) -> None: ...


class PatcherRegistry:
    """平台名 -> 修改器的映射。"""

    def __init__(self) -> None:
        self._patchers: dict[str, ProjectPatcher] = {}

    def register(self, platform: str, patcher: ProjectPatcher) -> None:
        """注册修改器；同平台重复注册以后者为准。"""
        self._patchers[platform] = patcher

    def get(self, platform: str) -> ProjectPatcher:
        try:
            return self._patchers[platform]
        except KeyError:
            known = ", ".join(sorted(self._patchers)) or "（无）"
            raise UnknownPlatformError(
                f"未知平台 {platform!r}，已注册的平台：{known}"
            ) from None


def default_registry() -> PatcherRegistry:
    """两个平台都用真实修改器：stm32 → Keil，mspm0 → CCS。"""
    registry = PatcherRegistry()
    registry.register(PLATFORM_STM32, KeilPatcher())
    registry.register(PLATFORM_MSPM0, CcsPatcher())
    return registry


def include_search_dirs(platform: str, project_dir: Path) -> list[Path]:
    """平台工程 include 搜索目录（引号头文件解析范围，读侧与写侧同规则）。

    生成核心只认识平台名，不绑定任何平台格式：stm32 走 keil 版（.uvprojx
    IncludePath）、mspm0 走 ccs 版（.cproject buildIncludePath）。
    """
    if platform == PLATFORM_STM32:
        return _keil_include_search_dirs(project_dir)
    if platform == PLATFORM_MSPM0:
        return _ccs_include_search_dirs(project_dir)
    known = ", ".join(sorted((PLATFORM_STM32, PLATFORM_MSPM0)))
    raise UnknownPlatformError(f"未知平台 {platform!r}，已注册的平台：{known}")
