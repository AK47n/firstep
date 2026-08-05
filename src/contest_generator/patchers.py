"""平台工程修改器：统一接口 + 注册表。

生成器核心把模块文件复制、main.c 落位等公共逻辑做完后，把工程目录交给
注册表里对应平台的修改器（Keil 改 .uvprojx、CCS 改 .cproject 等）。
核心只认识平台名，不绑定任何平台格式；真实修改器在工单 02/03 落地。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32  # noqa: F401


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


class NullPatcher:
    """桩实现：真实修改器（工单 02/03）前的占位，不做任何修改。"""

    def patch(
        self,
        project_dir: Path,
        module_files: Sequence[Path],
        include_dirs: Sequence[Path],
    ) -> None:
        pass


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
    """两个内置平台都先用桩修改器，保证管线端到端可跑。"""
    registry = PatcherRegistry()
    for platform in KNOWN_PLATFORMS:
        registry.register(platform, NullPatcher())
    return registry
