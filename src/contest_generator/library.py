"""模块库管理核心：库目录即数据库。

每个模块一个目录：manifest.json（机器可读描述）+ 各平台版本文件（路径在
platform entry 的 files 里，相对模块目录）。本模块负责浏览 / 编辑 / 删除模块、
增删各平台版本文件，以及 AI 录入流程——通读代码生成简介草稿 → 用户修改 →
一致性校验 → 校验通过才入库（不一致抛错且不落盘）；编辑简介同样先校验再写回，
保持库的说明可信（spec US 15）。

任何从 slug 拼文件路径的操作（浏览 / 删除 / 写回）都先校验 slug 合法性，
杜绝借 slug 逃出库目录的路径穿越。库目录的物理位置由调用方传入
（后续工单接入本机配置），测试用 tmp_path。
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Mapping, Sequence
from urllib.parse import urlparse

from .entry_store import entry_transaction, iter_entry_dirs, write_json
from .manifest import (
    MANIFEST_FILENAME,
    ManifestError,
    ModuleManifest,
    PlatformEntry,
    is_unsafe_path,
)

if TYPE_CHECKING:
    from .llm import LLM, ValidationResult  # 仅类型注解用（模块库不运行时依赖 LLM 客户端）

ALLOWED_SOURCE_EXTENSIONS = frozenset({".c", ".h"})
_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")


class LibraryError(ValueError):
    """模块库操作失败（模块不存在、slug 冲突、文件非法、校验未通过等）。"""


# ---------------------------------------------------------------------------
# 浏览 / 编辑 / 删除（磁盘目录即数据库，操作即时生效）
# ---------------------------------------------------------------------------


def list_modules(library_root: Path) -> list[ModuleManifest]:
    """返回库中全部模块（按 slug 排序）；manifest 损坏的模块目录抛 LibraryError。

    库根不存在 = 空库、点开头目录不影响浏览（与赛题库 / 参考库浏览同哲学，
    目录迭代走 entry_store 原语）。
    """
    manifests = []
    for entry in iter_entry_dirs(library_root):
        try:
            manifests.append(ModuleManifest.load(entry))
        except ManifestError as exc:
            raise LibraryError(
                f"模块目录 {entry.name} 的 manifest 无法读取：{exc}"
            ) from exc
    return manifests


def get_module(library_root: Path, slug: str) -> ModuleManifest:
    """读取单个模块；不存在或 manifest 损坏抛 LibraryError。"""
    _validate_slug(slug)
    module_dir = library_root / slug
    if not module_dir.is_dir():
        raise LibraryError(f"模块 {slug!r} 不存在")
    try:
        return ModuleManifest.load(module_dir)
    except ManifestError as exc:
        raise LibraryError(
            f"模块 {slug!r} 的 manifest 无法读取：{exc}"
        ) from exc


def delete_module(library_root: Path, slug: str) -> None:
    """删除模块：整个目录移除。"""
    _validate_slug(slug)
    module_dir = library_root / slug
    if not module_dir.is_dir():
        raise LibraryError(f"模块 {slug!r} 不存在")
    shutil.rmtree(module_dir)


def save_manifest(library_root: Path, manifest: ModuleManifest) -> None:
    """把编辑后的 manifest 写回库；结构不合法（如空文件列表）拒绝入库。

    只改结构字段（平台条目、依赖、备注等）；简介字段的编辑应走
    update_module_description——简介与实际代码的一致性必须经 AI 校验。
    """
    _validate_slug(manifest.slug)
    module_dir = library_root / manifest.slug
    if not module_dir.is_dir():
        raise LibraryError(f"模块 {manifest.slug!r} 不存在")
    try:
        ModuleManifest.from_dict(manifest.to_dict())
    except ManifestError as exc:
        raise LibraryError(f"manifest 不合法：{exc}") from exc
    # 存量条目补填走结构编辑路径：身份字段只做格式校验、不强制必填
    # （身份是事实信息，AI 判不了真假——不设 AI 一致性校验）
    for platform, entry in manifest.platforms.items():
        if entry.source_url:
            _validate_source_url_format(entry.source_url, platform)
    _write_manifest(module_dir, manifest)


def update_platform_identity(
    library_root: Path,
    slug: str,
    platform: str,
    *,
    kit: str = "",
    source_url: str = "",
) -> ModuleManifest:
    """存量平台条目的硬件身份补填 / 修改（工单 02）：只改身份字段，不走 AI 校验。

    用户补填身份字段的编辑入口：提供值须合法——kit 非空、source_url 须为
    合法 URL；空值视为未提供、保留原值（补填是逐步的，只填一个字段也能
    保存）。至少填一个字段，拒绝无意义的空保存。只做格式校验，不走 AI
    一致性校验——身份是事实信息、由人确认，AI 判不了真假（spec US 12）。
    只改该条目的 kit / source_url，文件列表、验证状态、硬件绑定等其余
    字段原样保留。任何校验失败都在落盘前。
    """
    manifest = get_module(library_root, slug)
    entry = manifest.platforms.get(platform)
    if entry is None:
        raise LibraryError(f"模块 {slug!r} 没有平台 {platform} 的版本")
    if not kit.strip() and not source_url.strip():
        raise LibraryError("至少填写一个硬件身份字段（kit 或 source_url）")
    if source_url.strip():
        _validate_source_url_format(source_url, platform)
    new_entry = _replace_identity_fields(entry, kit, source_url)
    new_manifest = replace(
        manifest, platforms={**manifest.platforms, platform: new_entry}
    )
    save_manifest(library_root, new_manifest)
    return new_manifest


# ---------------------------------------------------------------------------
# AI 录入流程：草稿 → 用户修改 → 一致性校验 → 入库
# ---------------------------------------------------------------------------


def draft_description(llm: LLM, files: Mapping[str, str]) -> str:
    """AI 通读代码生成简介草稿（与校验用同一份代码拼装，两者视角一致）。"""
    return llm.summarize_module(_assemble_code(files))


def validate_description(
    llm: LLM, description: str, files: Mapping[str, str]
) -> ValidationResult:
    """AI 校验简介与实际代码是否一致。"""
    return llm.validate_module_description(description, _assemble_code(files))


def add_module(
    llm: LLM,
    library_root: Path,
    *,
    slug: str,
    platform: str,
    description: str,
    files: Mapping[str, str],
    dependencies: Sequence[str] = (),
    hardware_bound: bool = False,
    verified: bool = False,
    notes: str = "",
    kit: str = "",
    source_url: str = "",
) -> ModuleManifest:
    """完整录入流程：一致性校验通过才入库；不一致抛 LibraryError 且不落盘。

    校验失败时模块目录根本不会创建，绝无半成品入库。硬件身份字段
    （套件型号 kit / 购买链接 source_url）由人补填、AI 不猜（spec 工单 01）；
    硬件绑定条目必填且链接格式合法，纯逻辑条目（hardware_bound=False）
    不强制但提供值必须合法（工单 06 修订）。
    """
    _validate_slug(slug)
    _validate_platform(platform)
    if (library_root / slug).is_dir():
        raise LibraryError(f"模块 {slug!r} 已存在")
    _validate_source_files(files)
    _validate_identity_fields(kit, source_url, required=hardware_bound)
    result = validate_description(llm, description, files)
    if not result.consistent:
        raise LibraryError(
            f"模块简介与实际代码不一致，请修正后再入库：{result.issues}"
        )

    with entry_transaction(library_root, [slug]) as (module_dir,):
        _write_source_files(module_dir, files)
        manifest = ModuleManifest(
            slug=slug,
            description=description,
            dependencies=tuple(dependencies),
            platforms={
                platform: PlatformEntry(
                    files=tuple(files),
                    verified=verified,
                    hardware_bound=hardware_bound,
                    notes=notes,
                    kit=kit.strip(),
                    source_url=source_url.strip(),
                )
            },
        )
        write_json(module_dir, MANIFEST_FILENAME, manifest.to_dict())
    return manifest


def update_module_description(
    llm: LLM,
    library_root: Path,
    slug: str,
    description: str,
) -> ModuleManifest:
    """编辑简介流程：AI 校验新简介与模块实际代码一致后才写回。

    校验视角是模块全部平台版本引用的文件（与录入流程一致）；未通过时
    抛 LibraryError 且磁盘上的简介保持原样。
    """
    manifest = get_module(library_root, slug)
    module_dir = library_root / slug
    files: dict[str, str] = {}
    for name in _module_source_files(manifest):
        try:
            files[name] = (module_dir / name).read_text(encoding="utf-8")
        except OSError as exc:
            raise LibraryError(f"模块 {slug!r} 的文件读取失败：{name}: {exc}") from exc
    result = validate_description(llm, description, files)
    if not result.consistent:
        raise LibraryError(
            f"模块简介与实际代码不一致，请修正后再保存：{result.issues}"
        )
    new_manifest = replace(manifest, description=description)
    save_manifest(library_root, new_manifest)
    return new_manifest


# ---------------------------------------------------------------------------
# 多平台版本：增删各平台版本文件与 manifest 条目
# ---------------------------------------------------------------------------


def add_platform_files(
    library_root: Path,
    slug: str,
    platform: str,
    files: Mapping[str, str],
    *,
    hardware_bound: bool = False,
    kit: str = "",
    source_url: str = "",
) -> ModuleManifest:
    """给已有模块添加某平台版本文件并更新 manifest 条目。

    路径已存在于模块中的文件视为共享：内容一致则复用（双平台共用同一文件），
    内容不同抛错——不允许同一路径维护两套内容。

    新增平台条目按硬件绑定强制身份字段（hardware_bound=True 时 kit /
    source_url 必填且链接格式合法；纯逻辑条目不强制但提供值必须合法，
    工单 06 修订）；存量条目不受强制，补填只做格式校验、不设 AI 一致性校验
    （身份是事实，AI 判不了真假）。任何校验失败都在落盘前。
    """
    manifest = get_module(library_root, slug)
    _validate_platform(platform)
    _validate_source_files(files)

    entry = manifest.platforms.get(platform)
    identity_provided = bool(kit.strip() or source_url.strip())
    if entry is None:
        _validate_identity_fields(kit, source_url, required=hardware_bound)
    elif identity_provided:
        # 存量条目补填：只做格式校验、不强制必填（补填是逐步的）
        if source_url.strip():
            _validate_source_url_format(source_url)

    module_dir = library_root / slug
    _check_source_files(module_dir, files)  # 写盘前预检：任一路径冲突都不留半成品
    _write_source_files(module_dir, files)

    if entry is None:
        entry = PlatformEntry(
            files=tuple(files),
            hardware_bound=hardware_bound,
            kit=kit.strip(),
            source_url=source_url.strip(),
        )
    else:
        entry = _replace_entry_files(
            entry, tuple(dict.fromkeys(entry.files + tuple(files)))
        )
        if identity_provided:
            entry = _replace_identity_fields(entry, kit, source_url)
    new_manifest = replace(manifest, platforms={**manifest.platforms, platform: entry})
    _write_manifest(module_dir, new_manifest)
    return new_manifest


def remove_platform_files(
    library_root: Path,
    slug: str,
    platform: str,
    filenames: Sequence[str],
) -> ModuleManifest:
    """删除某平台版本的文件与 manifest 条目。

    该平台最后一个文件被删后整个平台条目移除；文件仍被其他平台引用（共享文件）
    时只移出本平台条目，磁盘文件保留。
    """
    manifest = get_module(library_root, slug)
    entry = manifest.platforms.get(platform)
    if entry is None:
        raise LibraryError(f"模块 {slug!r} 没有平台 {platform} 的版本")
    _validate_source_names(filenames)
    if not filenames:
        raise LibraryError("至少指定一个要删除的文件")
    missing = [name for name in filenames if name not in entry.files]
    if missing:
        raise LibraryError(f"{missing[0]!r} 不在平台 {platform} 的版本文件中")

    remaining = tuple(name for name in entry.files if name not in filenames)
    new_platforms = dict(manifest.platforms)
    if remaining:
        new_platforms[platform] = _replace_entry_files(entry, remaining)
    else:
        new_platforms.pop(platform)

    # 只在没有任何平台条目再引用时才删除磁盘文件
    referenced_elsewhere: set[str] = set()
    for other_platform, other_entry in new_platforms.items():
        if other_platform != platform:
            referenced_elsewhere.update(other_entry.files)
    module_dir = library_root / slug
    new_manifest = replace(manifest, platforms=new_platforms)
    _write_manifest(module_dir, new_manifest)  # 先改引用再删实体：写失败不丢文件
    for name in filenames:
        if name not in referenced_elsewhere:
            (module_dir / name).unlink(missing_ok=True)
    return new_manifest


# ---------------------------------------------------------------------------
# 校验与落盘辅助
# ---------------------------------------------------------------------------


def _validate_slug(slug: str) -> None:
    if not _SLUG_PATTERN.fullmatch(slug):
        raise LibraryError(
            f"非法 slug：{slug!r}（只能含字母数字下划线连字符，且以字母或数字开头）"
        )


def _validate_platform(platform: str) -> None:
    if not isinstance(platform, str) or not platform:
        raise LibraryError("平台名必须是非空字符串")


def _validate_source_files(files: Mapping[str, str]) -> None:
    if not files:
        raise LibraryError("至少需要一个 .c/.h 源文件")
    _validate_source_names(tuple(files))


def _validate_source_names(names: Sequence[str]) -> None:
    for name in names:
        if is_unsafe_path(name):
            raise LibraryError(f"文件路径必须是相对且无 .. 的：{name!r}")
        if Path(name).suffix.lower() not in ALLOWED_SOURCE_EXTENSIONS:
            raise LibraryError(f"只支持 .c/.h 源文件：{name!r}")
        if name == MANIFEST_FILENAME:
            raise LibraryError(f"文件名不能与 {MANIFEST_FILENAME} 冲突")


def _replace_entry_files(entry: PlatformEntry, files: tuple[str, ...]) -> PlatformEntry:
    """重建平台条目：仅替换文件列表，其余字段（验证状态、身份字段等）全保留。"""
    return replace(entry, files=files)


def _replace_identity_fields(
    entry: PlatformEntry, kit: str, source_url: str
) -> PlatformEntry:
    """存量条目身份补填：提供了才写回，没提供保留原值。"""
    new_kit = kit.strip() or entry.kit
    new_source_url = source_url.strip() or entry.source_url
    return replace(entry, kit=new_kit, source_url=new_source_url)


def _validate_identity_fields(kit: str, source_url: str, *, required: bool) -> None:
    """硬件身份校验（工单 06 修订）：required 时 kit / source_url 必填且格式合法；
    否则（纯逻辑条目）不强制，但提供值必须合法——给了就要给对。"""
    if required:
        if not kit.strip():
            raise LibraryError("套件型号（kit）必填：硬件绑定条目必须填写套件型号")
        if not source_url.strip():
            raise LibraryError(
                "购买链接（source_url）必填：硬件绑定条目必须填写购买链接"
            )
    if source_url.strip():
        _validate_source_url_format(source_url)


def _validate_source_url_format(
    source_url: str, platform: str | None = None
) -> None:
    """购买链接格式校验：不合法抛 LibraryError，带中文说明与肇事值。"""
    if not _is_valid_source_url(source_url):
        where = f"平台 {platform} 的" if platform else ""
        raise LibraryError(
            f"{where}购买链接（source_url）格式非法：{source_url.strip()!r}"
            "（必须是带协议和主机的完整链接，如 https://item.jd.com/1000123456.html）"
        )


def _is_valid_source_url(source_url: str) -> bool:
    """购买链接的简单格式校验：必须带协议（scheme）与主机（netloc），
    且主机不含空白（urlparse 对空白主机很宽松，会放过 'a b.com'）。"""
    try:
        parsed = urlparse(source_url.strip())
    except ValueError:
        return False
    return bool(parsed.scheme and parsed.netloc) and not any(
        ch.isspace() for ch in parsed.netloc
    )


def _module_source_files(manifest: ModuleManifest) -> tuple[str, ...]:
    """模块全部平台版本引用的文件（去重排序，编辑校验的代码视角）。"""
    names: set[str] = set()
    for entry in manifest.platforms.values():
        names.update(entry.files)
    return tuple(sorted(names))


def _check_source_files(module_dir: Path, files: Mapping[str, str]) -> None:
    """写盘前预检：已存在路径的内容冲突直接拦截，写盘过程不会中途失败。"""
    for name, content in files.items():
        path = module_dir / name
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise LibraryError(f"路径已被其他平台版本占用且内容不一致：{name!r}")


def _write_source_files(module_dir: Path, files: Mapping[str, str]) -> None:
    for name, content in files.items():
        path = module_dir / name
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise LibraryError(
                    f"路径已被其他平台版本占用且内容不一致：{name!r}"
                )
            continue  # 内容一致 → 共享文件，复用
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _write_manifest(module_dir: Path, manifest: ModuleManifest) -> None:
    """写 manifest（JSON 序列化走 entry_store 原语，与赛题库 / 参考库同款）。"""
    write_json(module_dir, MANIFEST_FILENAME, manifest.to_dict())


def _assemble_code(files: Mapping[str, str]) -> str:
    """把模块各源文件拼成一份带文件名标注的代码（草稿与校验共用同一视角）。"""
    return "\n".join(
        f"// ---- {name} ----\n{content}" for name, content in files.items()
    )
