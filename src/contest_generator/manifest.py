"""模块 manifest 数据模型。

模块库：磁盘目录即数据库，每个模块一个目录——机器可读的 manifest.json
（本模块负责解析/序列化/校验）+ 各平台版本文件（路径在 platform entry 的
files 里，相对模块目录）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_FILENAME = "manifest.json"


class ManifestError(ValueError):
    """manifest 解析或校验失败，message 中说明具体问题。"""


@dataclass(frozen=True)
class PlatformEntry:
    """单个平台下的模块版本条目。"""

    files: tuple[str, ...]  # 相对模块目录的文件路径列表
    verified: bool = False  # 该平台版本是否验证过
    hardware_bound: bool = False  # 是否绑定硬件（换平台需移植）
    notes: str = ""  # 备注


@dataclass(frozen=True)
class ModuleManifest:
    """一个模块的机器可读描述。"""

    slug: str  # 模块唯一 id，即模块目录名
    description: str  # 功能简介
    dependencies: tuple[str, ...] = ()  # 依赖模块 slug 列表
    platforms: dict[str, PlatformEntry] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容 dict。"""
        return {
            "slug": self.slug,
            "description": self.description,
            "dependencies": list(self.dependencies),
            "platforms": {
                platform: {
                    "files": list(entry.files),
                    "verified": entry.verified,
                    "hardware_bound": entry.hardware_bound,
                    "notes": entry.notes,
                }
                for platform, entry in self.platforms.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModuleManifest":
        """从 dict 解析并校验，任何缺失/非法字段抛 ManifestError。"""
        slug = _require(data, "slug", str)
        description = _require(data, "description", str)
        raw_platforms = _require(data, "platforms", dict)

        platforms: dict[str, PlatformEntry] = {}
        for platform, raw_entry in raw_platforms.items():
            if not isinstance(platform, str) or not platform:
                raise ManifestError(f"平台名必须是非空字符串：{platform!r}")
            if not isinstance(raw_entry, dict):
                raise ManifestError(f"平台 {platform} 的条目必须是对象")
            files_raw = _require(raw_entry, "files", list, platform)
            files = _parse_file_list(files_raw, platform)
            platforms[platform] = PlatformEntry(
                files=files,
                verified=_require_flag(raw_entry, "verified", platform),
                hardware_bound=_require_flag(raw_entry, "hardware_bound", platform),
                notes=_require_notes(raw_entry, platform),
            )

        return cls(
            slug=slug,
            description=description,
            dependencies=tuple(_parse_dependencies(data.get("dependencies"))),
            platforms=platforms,
        )

    @classmethod
    def load(cls, module_dir: Path) -> "ModuleManifest":
        """读取模块目录下的 manifest.json。"""
        manifest_path = module_dir / MANIFEST_FILENAME
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError(f"无法读取 {manifest_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ManifestError(f"{manifest_path} 必须是 JSON 对象")
        manifest = cls.from_dict(data)
        if manifest.slug != module_dir.name:
            raise ManifestError(
                f"manifest slug {manifest.slug!r} 与目录名 {module_dir.name!r} 不一致"
            )
        return manifest


def _require(data: dict[str, Any], key: str, expected_type: type, platform: str | None = None) -> Any:
    where = f"平台 {platform} 的" if platform else ""
    if key not in data:
        raise ManifestError(f"缺少必填字段：{where}{key}")
    value = data[key]
    if not isinstance(value, expected_type):
        raise ManifestError(f"字段 {where}{key} 必须是 {expected_type.__name__}")
    return value


def _require_flag(entry: dict[str, Any], key: str, platform: str) -> bool:
    """布尔标记严格校验——宽松强转会让错值静默翻转验证状态。"""
    value = entry.get(key, False)
    if not isinstance(value, bool):
        raise ManifestError(f"平台 {platform} 的 {key} 必须是布尔值")
    return value


def _require_notes(entry: dict[str, Any], platform: str) -> str:
    value = entry.get("notes", "")
    if not isinstance(value, str):
        raise ManifestError(f"平台 {platform} 的 notes 必须是字符串")
    return value


def _parse_file_list(files: list[Any], platform: str) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, str) or not item:
            raise ManifestError(f"平台 {platform} 的文件路径必须是非空字符串：{item!r}")
        if _is_unsafe_path(item):
            raise ManifestError(f"平台 {platform} 的文件路径必须是相对且无 .. 的：{item!r}")
        if item in seen:
            raise ManifestError(f"平台 {platform} 的文件列表重复：{item!r}")
        seen.add(item)
        result.append(item)
    if not result:
        raise ManifestError(f"平台 {platform} 的 files 不能为空")
    return tuple(result)


def _parse_dependencies(dependencies: Any) -> list[str]:
    if dependencies is None:
        return []
    if not isinstance(dependencies, list) or not all(
        isinstance(dep, str) and dep for dep in dependencies
    ):
        raise ManifestError("dependencies 必须是字符串列表")
    return dependencies


def _is_unsafe_path(path: str) -> bool:
    """路径必须是相对路径，不含 .. 、空段、绝对路径（跨目录逃逸风险）。"""
    return (
        path.startswith("/")
        or ":" in path
        or "\\" in path
        or any(part in ("", "..") for part in path.split("/"))
    )
