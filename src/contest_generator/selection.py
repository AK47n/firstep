"""模块选择与依赖解析。

流程：AI 推荐（或用户手选）的 slug 集 → 生成前用户增删 → 按 manifest 递归
展开依赖 → 检查目标平台可用性 → 交给生成器。展开与检查都是纯函数：用户
增删选择后重跑一遍 resolve_dependencies 即可，无需维护中间状态。

平台警告分三类——缺版本（missing，生成必失败）、未验证（unverified，可能
无法编译）、硬件绑定（hardware_bound，换平台需移植）。前两类是风险提示，
缺版本在生成阶段会硬失败，这里提前暴露让用户改选择。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .manifest import ModuleManifest

WARNING_MISSING = "missing"  # 无目标平台版本条目，生成必失败
WARNING_UNVERIFIED = "unverified"  # 有版本但未验证过，可能无法编译
WARNING_HARDWARE_BOUND = "hardware_bound"  # 绑定硬件，换平台需移植


class SelectionError(ValueError):
    """选择 / 依赖解析失败，message 说明具体问题。"""


class UnknownModuleError(SelectionError):
    """选择了库中不存在的模块（或依赖引用了未知 slug）。"""


class DependencyCycleError(SelectionError):
    """依赖成环。"""


@dataclass(frozen=True)
class PlatformWarning:
    """生成前的平台可用性警告。"""

    slug: str
    kind: str  # WARNING_MISSING / WARNING_UNVERIFIED / WARNING_HARDWARE_BOUND
    message: str


def resolve_dependencies(
    slugs: Sequence[str], by_slug: Mapping[str, ModuleManifest]
) -> tuple[ModuleManifest, ...]:
    """按 manifest 递归展开依赖，返回去重后的完整 manifest 集。

    结果顺序：依赖先于使用者（DFS 后序），同层按出现顺序；相互独立的
    选择保持传入顺序。成环（含自依赖）抛 DependencyCycleError，库中
    不存在的 slug（选择或依赖）抛 UnknownModuleError。
    """
    result: list[ModuleManifest] = []
    done: set[str] = set()
    visiting: list[str] = []  # 当前递归路径，用于环检测

    def visit(slug: str) -> None:
        if slug in done:
            return
        if slug in visiting:
            raise DependencyCycleError("依赖成环：" + " -> ".join([*visiting, slug]))
        visiting.append(slug)
        manifest = _get_manifest(by_slug, slug)
        for dep in manifest.dependencies:
            visit(dep)
        visiting.pop()
        done.add(slug)
        result.append(manifest)

    for slug in slugs:
        visit(slug)
    return tuple(result)


def check_platform_warnings(
    slugs: Sequence[str], platform: str, by_slug: Mapping[str, ModuleManifest]
) -> tuple[PlatformWarning, ...]:
    """检查所选模块（应传 resolve_dependencies 的结果）在目标平台的可直接使用性。

    每个模块至多两类风险提示（未验证 / 硬件绑定），缺平台版本单独一条
    missing 警告。警告按输入顺序排列。slug 未知抛 UnknownModuleError。
    """
    warnings: list[PlatformWarning] = []
    for slug in slugs:
        manifest = _get_manifest(by_slug, slug)
        entry = manifest.platforms.get(platform)
        if entry is None:
            warnings.append(
                PlatformWarning(
                    slug,
                    WARNING_MISSING,
                    f"模块 {slug} 缺少平台 {platform} 的版本，生成将失败——请移除或换模块",
                )
            )
            continue
        if not entry.verified:
            warnings.append(
                PlatformWarning(
                    slug,
                    WARNING_UNVERIFIED,
                    f"模块 {slug} 在平台 {platform} 上的版本未验证，可能无法编译",
                )
            )
        if entry.hardware_bound:
            warnings.append(
                PlatformWarning(
                    slug,
                    WARNING_HARDWARE_BOUND,
                    f"模块 {slug} 在平台 {platform} 上的版本硬件绑定，换平台需移植",
                )
            )
    return tuple(warnings)


def _get_manifest(by_slug: Mapping[str, ModuleManifest], slug: str) -> ModuleManifest:
    manifest = by_slug.get(slug)
    if manifest is None:
        raise UnknownModuleError(f"库中不存在模块：{slug}")
    return manifest
