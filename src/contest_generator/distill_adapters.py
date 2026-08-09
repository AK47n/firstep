"""蒸馏侧平台适配接缝（架构深化 v5 工单 04）：摘要读 / 渲染（含守卫翻译）/
启动候选谓词 per platform 经适配器分派，master / categories 只消费。

生成侧有 patchers registry 接缝，蒸馏侧没有：master.py 内联 stm32 if/else
四处分派 + 直连 keil（4 名）/ ccs（2 名）；mspm0 = "keil 减一切"（无渲染 /
无密度守卫 / 预览恒空串）；密度守卫从蒸馏缝逃逸成 KeilProjectError
（distill_master 的 docstring 承诺 MasterError）。本轮收口：守卫错误翻译在
缝内归 MasterError（message 原样，HTTP 层 MasterError 同映射 400）；mspm0
显式无操作（renders_config=False / render_config 恒 "" / 谓词恒 False）。

薄壳——格式知识仍归 keil.py / ccs.py：这里只做平台分派 + 错误翻译 + mspm0
显式无操作。识别知识（工程配置文件后缀表）单源 = platforms.py。不 import
patchers（生成侧 registry 零改动）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .ccs import CcsProjectError, extract_config_summary as extract_ccs_config_summary
from .keil import (
    KeilProjectError,
    build_master_uvprojx,
    extract_config_summary as extract_keil_config_summary,
    is_md_startup as keil_is_md_startup,
    is_startup_candidate as keil_is_startup_candidate,
    render_master_uvprojx,
)
from .master_store import MasterError
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32


class DistillAdapter(Protocol):
    """蒸馏侧平台行为接缝：摘要读 / 渲染 / 启动候选谓词。

    实现约定：config_summary 内部失败（多配置文件 / 非法 XML 等）转成一行
    摘要，扫描不因单个工程带病中断（软失败语义）；渲染守卫（stm32 密度
    守卫）翻译成 MasterError——HTTP 层只认这一种母版错误。
    """

    renders_config: bool  # 是否现写工程配置文件（False = 保留首份原样，判例 09）

    def config_summary(self, project_dir: Path) -> tuple[str, ...]:
        """平台配置摘要行（配置对比的 AI 素材），失败转一行软失败行。"""

    def render_config(
        self,
        kept_paths: Sequence[str],
        startup_path: str | None,
        include_dirs: Sequence[str],
    ) -> str:
        """工程配置文件全文（报告预览用）；非渲染平台恒空串。"""

    def write_config(
        self,
        output_dir: Path,
        kept_paths: Sequence[str],
        startup_path: str | None,
        include_dirs: Sequence[str],
    ) -> Path | None:
        """把工程配置文件现写落盘，返回落盘路径；非渲染平台无操作（None）。"""

    def is_startup_candidate(self, rel_path: str) -> bool:
        """启动文件候选谓词（决策 2 去重入口）；非 stm32 恒 False。"""

    def is_md_startup(self, rel_path: str) -> bool:
        """密度匹配谓词（_md = 中容量，目标板 C8T6）；非 stm32 恒 False。"""


class KeilDistillAdapter:
    """stm32 / Keil 蒸馏适配器：渲染现写 .uvprojx（格式知识在 keil.py）。

    密度守卫翻译：build_master_uvprojx / render_master_uvprojx 抛
    KeilProjectError（保留启动文件非 _md，目标板 STM32F103C8T6 中密度）——
    message 原样翻成 MasterError，契约兑现 distill_master 的 docstring（HTTP
    层 MasterError 同映射 400）。
    """

    renders_config = True

    def config_summary(self, project_dir: Path) -> tuple[str, ...]:
        try:
            return extract_keil_config_summary(project_dir)
        except KeilProjectError as exc:
            return (f"{PLATFORM_STM32} 工程配置读取失败：{exc}",)

    def render_config(
        self,
        kept_paths: Sequence[str],
        startup_path: str | None,
        include_dirs: Sequence[str],
    ) -> str:
        try:
            return build_master_uvprojx(kept_paths, startup_path, include_dirs)
        except KeilProjectError as exc:
            raise MasterError(str(exc)) from exc

    def write_config(
        self,
        output_dir: Path,
        kept_paths: Sequence[str],
        startup_path: str | None,
        include_dirs: Sequence[str],
    ) -> Path:
        try:
            return render_master_uvprojx(
                output_dir, kept_paths, startup_path, include_dirs
            )
        except KeilProjectError as exc:
            raise MasterError(str(exc)) from exc

    def is_startup_candidate(self, rel_path: str) -> bool:
        return keil_is_startup_candidate(rel_path)

    def is_md_startup(self, rel_path: str) -> bool:
        return keil_is_md_startup(rel_path)


class CcsDistillAdapter:
    """mspm0 / CCS 蒸馏适配器（显式无操作）：无现写（判例 09 保留首份）。

    renders_config=False → apply_distillation 永不调用 write_config（返回
    None 是显式无操作的落盘形态）；render_config 恒空串（报告 .uvprojx
    预览为空）；启动候选谓词恒 False——mspm0 母版无 .s 启动文件（TI/CCS
    启动为 .c，不在基础设施词表），启动去重规则对 mspm0 不生效。
    """

    renders_config = False

    def config_summary(self, project_dir: Path) -> tuple[str, ...]:
        try:
            return extract_ccs_config_summary(project_dir)
        except CcsProjectError as exc:
            return (f"{PLATFORM_MSPM0} 工程配置读取失败：{exc}",)

    def render_config(
        self,
        kept_paths: Sequence[str],
        startup_path: str | None,
        include_dirs: Sequence[str],
    ) -> str:
        return ""

    def write_config(
        self,
        output_dir: Path,
        kept_paths: Sequence[str],
        startup_path: str | None,
        include_dirs: Sequence[str],
    ) -> None:
        return None

    def is_startup_candidate(self, rel_path: str) -> bool:
        return False

    def is_md_startup(self, rel_path: str) -> bool:
        return False


_DISTILL_ADAPTERS: dict[str, DistillAdapter] = {
    PLATFORM_STM32: KeilDistillAdapter(),
    PLATFORM_MSPM0: CcsDistillAdapter(),
}


def get_distill_adapter(platform: str) -> DistillAdapter:
    """按平台取蒸馏适配器（模块级 dict 分派）；未知平台抛 MasterError。"""
    try:
        return _DISTILL_ADAPTERS[platform]
    except KeyError:
        raise MasterError(
            f"未知平台 {platform!r}（已知：{'、'.join(KNOWN_PLATFORMS)}）"
        ) from None
