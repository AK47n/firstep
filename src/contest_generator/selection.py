"""模块选择与依赖解析。

流程：AI 推荐（或用户手选）的 slug 集 → 生成前用户增删 → 按 manifest 递归
展开依赖 → 检查目标平台可用性 → 交给生成器。展开与检查都是纯函数：用户
增删选择后重跑一遍 resolve_selection（加载库 + 展开 + 警告的组合操作）即可，
无需维护中间状态。

平台警告分三类——缺版本（missing，生成必失败）、未验证（unverified，可能
无法编译）、硬件绑定（hardware_bound，换平台需移植）。前两类是风险提示，
缺版本在生成阶段会硬失败，这里提前暴露让用户改选择。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .library import list_modules
from .llm import ReferenceSuggestion
from .manifest import ModuleManifest, is_unsafe_path
from .reference_library import ReferenceEntry, ReferenceError, search_references

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


@dataclass(frozen=True)
class ResolvedSelection:
    """选择解析结果：依赖展开后的完整模块集 + 平台可用性警告。"""

    manifests: tuple[ModuleManifest, ...]
    warnings: tuple[PlatformWarning, ...]


def resolve_selection(
    library_dir: Path, platform: str, slugs: Sequence[str]
) -> ResolvedSelection:
    """加载模块库 → 展开依赖 → 平台警告，一步到位。

    webapp 的展开 / 骨架 / 生成三个端点共用这一组合操作——"所选模块最终
    解析成什么"只有一个答案来源，单独跑 expand 与生成前的结果必然一致。
    """
    by_slug = {m.slug: m for m in list_modules(library_dir)}
    manifests = resolve_dependencies(slugs, by_slug)
    warnings = check_platform_warnings([m.slug for m in manifests], platform, by_slug)
    return ResolvedSelection(manifests=manifests, warnings=warnings)


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


# ---------------------------------------------------------------------------
# 工单 03：候选清单带参考文件（两级注入第一级）+ 全文回读（第二级）
# ---------------------------------------------------------------------------


def associated_references(
    reference_root: Path,
    *,
    topic_key: str = "",
    manifests: Sequence[ModuleManifest] = (),
) -> tuple[ReferenceEntry, ...]:
    """该赛题 / 套件关联的参考文件（候选清单的参考段，两级注入第一级的素材）。

    关联判据 = 锚定值匹配赛题编号（topic_key）或套件型号（manifests 各平台
    条目的 kit 词表收集——候选模块的套件身份与模块简介同源，参考文件 ↔ 套件
    链接可靠）。按 id 去重排序：search_references 的锚定过滤是子串匹配，同
    一条目可能被多个锚定值命中（如 kit 名含编号）。参考库目录不存在返回空。
    """
    if not reference_root.is_dir():
        return ()
    kits: list[str] = []
    seen_kits: set[str] = set()
    for manifest in manifests:
        for platform_entry in manifest.platforms.values():
            if platform_entry.kit and platform_entry.kit not in seen_kits:
                seen_kits.add(platform_entry.kit)
                kits.append(platform_entry.kit)
    entries: dict[str, ReferenceEntry] = {}
    for anchor in (topic_key, *kits):
        if anchor:
            for reference in search_references(reference_root, anchor=anchor):
                entries.setdefault(reference.id, reference)
    return tuple(entries.values())


def reference_suggestions(
    entries: Sequence[ReferenceEntry],
) -> tuple[ReferenceSuggestion, ...]:
    """候选清单的参考段形状：参考文件（标题 + 一句话简介），喂给选模块 AI。"""
    return tuple(
        ReferenceSuggestion(id=entry.id, title=entry.title, description=entry.description)
        for entry in entries
    )


def read_reference_fulltext(reference_root: Path, entry: ReferenceEntry) -> str:
    """参考文件条目全文（两级注入第二级的素材）：素材文件拼成带文件名标注的文本。

    二进制素材（说明书 PDF 等）读不了文本——跳过并标注（不让生成流程因个别
    不可读素材整体失败）；条目文件缺失 / 相对路径非法 = 库损坏，大声失败
    （ReferenceError，宁可大声失败也不把坏数据带进上下文）。
    """
    chunks: list[str] = []
    for rel in entry.files:
        if is_unsafe_path(rel):
            raise ReferenceError(
                f"参考文件条目 {entry.id!r} 的文件路径非法：{rel!r}"
            )
        path = reference_root / entry.id / rel
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReferenceError(
                f"参考文件条目 {entry.id!r} 的素材文件无法读取：{rel}: {exc}"
            ) from exc
        except UnicodeDecodeError:
            chunks.append(f"// ---- {rel} ----（二进制素材，未嵌入全文）\n")
            continue
        chunks.append(f"// ---- {rel} ----\n{content}")
    return "\n".join(chunks)
