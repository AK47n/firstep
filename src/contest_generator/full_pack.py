"""完整包（整份 firstep）打包核心（工单 full-download/01）。

发布侧纯函数与薄 I/O 层，供 `tools/pack-full.ps1` 调用（CLI 入口在本模块）：

- 仓库树扫描：**只收会变的内容**——工具本体 / 五个库 / 资料库内容文件 /
  参考工程；排除第三方安装包与 SDK 打包件、虚拟环境与依赖、缓存与工作区、
  本地备份目录、日志。
- 完整包清单（用户侧检查与下载的数据源）：
  `{version, published_at, total_bytes, parts, files, materials_manifest}`
  - `files` = 包内全部文件（下一版完整包的删除清单基线）；
  - `materials_manifest` = 该版本的资料库清单，落位后写入
    `sources/materials/.materials-manifest.json`，使全量用户当场获得增量能力。
- zip 分卷：单卷超 limit 自动拆 `firstep-full-<tag>.part<N>.zip`，每卷独立
  SHA256；zip 内条目路径 = 仓库根相对 POSIX 路径（解压即覆盖）。
- 四件套落盘：zip 分卷 + `.manifest.json` + `.removed.txt` + `.sha256.txt`。

纯函数无网络；扫描与 zip 落盘是薄 I/O 层，测试全部临时目录完成。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Sequence

from .materials_pack import (
    MANIFEST_FILENAME,
    PART_LIMIT_BYTES,
    PartFile,
    derive_slug,
    register_dir_slugs,
    scan_as_manifest,
    slug_for_dir,
)

# 完整包清单内的资料库基线键名（用户侧落位时读它写 .materials-manifest.json）
MATERIALS_MANIFEST_KEY = "materials_manifest"

# 包内顶层白名单（新增顶层目录时在此登记；不在白名单的一律不进包）
TOP_LEVEL_ENTRIES: tuple[str, ...] = (
    "src",
    "library",
    "sources",
    "tests",
    "docs",
    "assets",
    "tools",
    ".githooks",
    ".gitattributes",
    ".gitignore",
    "CLAUDE.md",
    "README.md",
    "CONTEXT.md",
    "CHANGELOG.md",
    "VERSIONS.md",
    "pyproject.toml",
    "install.bat",
    "start-app.bat",
    "start-app.vbs",
    "stop-firstep.bat",
    "stop-firstep.vbs",
)

# 任意层级跳过的目录名（工具链 / 虚拟环境 / 缓存 / 工作区 / 本地备份）
SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".scratch",
        ".claude",
        "logs",
        "updates",
        "fix-backups",
        "revise-backups",
        ".trash-pdf",
    }
)

# 任意层级跳过的文件名
SKIP_FILE_NAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db", MANIFEST_FILENAME})

# 任意层级跳过的后缀（机器可再生的缓存 / 构建产物 / 日志）
SKIP_FILE_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo", ".log")

# 「装机一次、之后几乎不变」的第三方安装包与 SDK 打包件（ASCII 特征模式）。
# 这部分在本机实测约 5.4 GB（CCS 安装包 / 视觉 SDK / VSCode 等），
# 放进每次全量重下等于让「修损坏 / 换机器」多付 4.9 GB，故不进包。
INSTALLER_GLOBS: tuple[str, ...] = (
    "*.exe",
    "*.msi",
    "*.rar",
    "*.7z",
    "*.img",
    "*.img.gz",
    "*.img.xz",
    "*.z01",
    "*.z02",
    "*CCS_20.5*",
    "*tsp-xbhdcc*",
    "*ubuntu-20.04*",
    "*dataset.zip*",
    "*05_SPI*.zip",
)

__all__ = [
    "INSTALLER_GLOBS",
    "MATERIALS_MANIFEST_KEY",
    "SKIP_DIR_NAMES",
    "SKIP_FILE_NAMES",
    "SKIP_FILE_SUFFIXES",
    "TOP_LEVEL_ENTRIES",
    "build_full_manifest",
    "build_zip_volumes",
    "excluded_paths",
    "full_manifest_filename",
    "main",
    "materials_excluded",
    "prepare_full_package",
    "register_materials_dirs",
    "scan_tree",
    "split_volumes",
]


# ---------------------------------------------------------------------------
# 排除规则（单源）
# ---------------------------------------------------------------------------


def _matches_any(name: str, patterns: Sequence[str]) -> bool:
    """大小写不敏感的通配匹配（Windows 语义：`*.EXE` 与 `*.exe` 同判）。"""
    lowered = name.lower()
    return any(Path(lowered).match(pattern.lower()) for pattern in patterns)


def _relative_parts(root: Path, path: Path) -> tuple[str, ...]:
    return path.relative_to(root).parts


def _exclude_reason(root: Path, path: Path) -> str | None:
    """文件不满足进包条件时返回原因（中文可读），否则 None。"""
    parts = _relative_parts(root, path)
    if not parts:
        return "顶层之外"
    # 目录名排除优先判定（.git / .scratch 这类既非白名单也不该进包的）
    for part in parts[:-1]:
        if part in SKIP_DIR_NAMES:
            return "dir-name"
    if parts[-1] in SKIP_DIR_NAMES:
        return "dir-name"
    if parts[0] not in TOP_LEVEL_ENTRIES:
        return "顶层不在白名单"
    if parts[-1] in SKIP_FILE_NAMES:
        return "file-name"
    if _matches_any(parts[-1], INSTALLER_GLOBS):
        return "installer-glob"
    if parts[-1].lower().endswith(SKIP_FILE_SUFFIXES):
        return "file-suffix"
    return None


def scan_tree(root: Path, *, skip_dir_names: frozenset[str] | None = None) -> list[PartFile]:
    """扫描仓库树 → PartFile 列表（相对 POSIX 路径 / size / sha256，按路径排序）。

    只收白名单顶层下的文件，按 `SKIP_DIR_NAMES` / `SKIP_FILE_NAMES` /
    `INSTALLER_GLOBS` / `SKIP_FILE_SUFFIXES` 排除；排序保证清单与分卷确定性。

    **取源口径（工单 full-download/08）**：读**工作树字节**，与小发版包同口径——
    小发版侧 `git archive` 被钉成 `core.autocrlf=false`，两边拿到的就是同一份
    盘上字节（改这里前先看 `tests/test_pack_update.py` 的跨包一致性守卫）。
    """
    root = Path(root)
    dir_skips = SKIP_DIR_NAMES if skip_dir_names is None else skip_dir_names
    entries: list[PartFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        parts = _relative_parts(root, path)
        if not parts or parts[0] not in TOP_LEVEL_ENTRIES:
            continue
        if any(part in dir_skips for part in parts[:-1]):
            continue
        if parts[-1] in SKIP_FILE_NAMES:
            continue
        if _matches_any(parts[-1], INSTALLER_GLOBS):
            continue
        if parts[-1].lower().endswith(SKIP_FILE_SUFFIXES):
            continue
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(256 * 1024), b""):
                digest.update(chunk)
        entries.append(
            PartFile(
                path="/".join(parts),
                size=path.stat().st_size,
                sha256=digest.hexdigest(),
            )
        )
    entries.sort(key=lambda e: e.path)
    return entries


def excluded_paths(root: Path) -> dict[str, str]:
    """全树（不按顶层白名单预筛）扫一遍，返回「被排除的路径 → 原因」。

    用于体检与防回归：排除集合必须是「安装包 / 缓存 / 备份」这类小集合，
    一旦某个模式写宽了（误伤内容文件），条数会立刻异常。
    """
    root = Path(root)
    excluded: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        reason = _exclude_reason(root, path)
        if reason is None:
            continue
        excluded["/".join(_relative_parts(root, path))] = reason
    return excluded


# ---------------------------------------------------------------------------
# 清单构建（纯函数）
# ---------------------------------------------------------------------------


def full_manifest_filename(version: str) -> str:
    return f"firstep-full-{version}.manifest.json"


def full_zip_base(version: str) -> str:
    return f"firstep-full-{version}"


def register_materials_dirs(materials_root: Path) -> dict[str, str]:
    """把资料库里尚未登记 slug 的顶级目录补登记（确定性派生）。

    完整包要顺手把当前资料库状态写成新版基线，新资料目录不该阻断发版：
    显式登记优先，未登记则 `derive_slug` 内容寻址派生（同名恒同 slug）。
    返回本次补登记的映射（可能为空）。
    """
    root = Path(materials_root)
    if not root.is_dir():
        return {}
    extra: dict[str, str] = {}
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in SKIP_DIR_NAMES:
            continue
        try:
            slug_for_dir(child.name)  # 已登记 / 全 ASCII 可规范化 → 无需补登记
        except ValueError:
            extra[child.name] = derive_slug(child.name)
        else:
            continue
    return register_dir_slugs(extra)


def materials_excluded(relative: str) -> bool:
    """资料库内某个相对路径是否被完整包排除（与包本体规则同口径）。

    按路径各段套用 `SKIP_DIR_NAMES` / `SKIP_FILE_NAMES` / `INSTALLER_GLOBS` /
    `SKIP_FILE_SUFFIXES`——**清单与包必须一致**：清单里出现的文件必须在包里。
    """
    parts = tuple(p for p in relative.replace("\\", "/").split("/") if p)
    if not parts:
        return True
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    name = parts[-1]
    if name in SKIP_FILE_NAMES:
        return True
    if _matches_any(name, INSTALLER_GLOBS):
        return True
    if name.lower().endswith(SKIP_FILE_SUFFIXES):
        return True
    return False


def build_full_manifest(
    *,
    version: str,
    published_at: str,
    files: Sequence[PartFile],
    tree: Path,
    parts: Sequence[dict[str, Any]] = (),
    removed: Sequence[str] = (),
) -> dict[str, Any]:
    """构建完整包清单（纯函数，除资料库扫描外无 I/O）。

    `total_bytes` = 包内文件原始大小合计（下载前估算用）；`parts` 由
    `build_zip_volumes` 回填；`removed` = 相对上一版完整包被删除的文件
    （更新器按它清理废弃文件，故必须进清单——`removed.txt` 只是人工副本）。
    """
    materials_root = Path(tree) / "sources" / "materials"
    register_materials_dirs(materials_root)
    materials = scan_as_manifest(materials_root, version, exclude=materials_excluded)
    return {
        "version": version,
        "published_at": published_at,
        "total_bytes": sum(f.size for f in files),
        "parts": [dict(p) for p in parts],
        "removed": [str(p) for p in removed],
        MATERIALS_MANIFEST_KEY: materials,
        "files": [f.to_dict() for f in files],
    }


# ---------------------------------------------------------------------------
# 分卷与 zip（薄 I/O 层）
# ---------------------------------------------------------------------------


def split_volumes(
    files: Sequence[PartFile], limit: int = PART_LIMIT_BYTES
) -> list[list[PartFile]]:
    """按累计原始大小切分卷：超 limit 即开新卷；单文件超限单独成卷。"""
    volumes: list[list[PartFile]] = []
    current: list[PartFile] = []
    current_size = 0
    for file in files:
        if current and current_size + file.size > limit:
            volumes.append(current)
            current = []
            current_size = 0
        current.append(file)
        current_size += file.size
    if current:
        volumes.append(current)
    return volumes


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(256 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_zip_volumes(
    tree: Path,
    version: str,
    files: Sequence[PartFile],
    out_dir: Path,
    limit: int = PART_LIMIT_BYTES,
) -> tuple[list[dict[str, Any]], list[Path]]:
    """把文件按分卷打成 zip（条目路径 = 仓库根相对 POSIX 路径）。

    返回 `([{zip_name, size, sha256}], [zip 路径])`；单卷 = `<base>.zip`，
    多卷 = `<base>.part<N>.zip`（N 从 1 起）。写入的是工作树字节——与
    清单里算 size / sha256 的那份同源，也与小发版包同口径。
    """
    tree = Path(tree)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = full_zip_base(version)
    volumes = split_volumes(files, limit)
    meta: list[dict[str, Any]] = []
    written: list[Path] = []
    for index, volume in enumerate(volumes, start=1):
        zip_name = f"{base}.zip" if len(volumes) == 1 else f"{base}.part{index}.zip"
        zip_path = out_dir / zip_name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in volume:
                source = tree / Path(*file.path.split("/"))
                archive.write(source, arcname=file.path)
        meta.append(
            {
                "zip_name": zip_name,
                "size": zip_path.stat().st_size,
                "sha256": _sha256_file(zip_path),
            }
        )
        written.append(zip_path)
    return meta, written


# ---------------------------------------------------------------------------
# 编排：四件套
# ---------------------------------------------------------------------------


def _validate_version(version: str) -> None:
    if not version or not all(ch.isalnum() or ch in "._-" for ch in version):
        raise ValueError(f"版本号含非法字符：{version!r}")


def _load_baseline_files(baseline_path: Path) -> list[str]:
    """上一版完整包清单 → 基线文件路径列表（容忍 BOM）。"""
    data = json.loads(Path(baseline_path).read_text(encoding="utf-8-sig"))
    return [str(item["path"]) for item in data.get("files", [])]


def prepare_full_package(
    tree: Path,
    *,
    version: str,
    out_dir: Path,
    published_at: str = "",
    baseline_path: Path | None = None,
    limit: int = PART_LIMIT_BYTES,
) -> tuple[dict[str, Any], list[Path]]:
    """完整包打包编排：scan → zip 分卷 → 清单 / 删除清单 / SHA256 落盘。

    返回 `(manifest, written_zips)`；删除清单基线 = `baseline_path` 指向的
    上一版完整包清单（None = 首次发布，空清单）。
    """
    _validate_version(version)
    tree = Path(tree)
    out_dir = Path(out_dir)
    if not tree.is_dir():
        raise ValueError(f"仓库根目录不存在：{tree}")

    files = scan_tree(tree)
    if not files:
        raise ValueError("扫描结果为空——顶层白名单或排除规则可能写错了")

    current_paths = [f.path for f in files]
    current_set = set(current_paths)
    if baseline_path is not None:
        removed = [
            p for p in _load_baseline_files(Path(baseline_path)) if p not in current_set
        ]
    else:
        removed = []

    meta, written = build_zip_volumes(tree, version, files, out_dir, limit)
    manifest = build_full_manifest(
        version=version,
        published_at=published_at,
        files=files,
        tree=tree,
        parts=meta,
        removed=removed,
    )
    # 删除清单必须**同时进清单 JSON**：更新器只读清单（它按 URL 拉清单，
    # 不下载 .removed.txt），漏写会让「废弃文件清理」静默不执行。
    (out_dir / full_manifest_filename(version)).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 同时落一份纯文本（人工核对 / 与既有小发版 removed.txt 形态一致）
    (out_dir / f"{full_zip_base(version)}.removed.txt").write_text(
        "\n".join(removed) + ("\n" if removed else ""), encoding="utf-8"
    )

    (out_dir / f"{full_zip_base(version)}.sha256.txt").write_text(
        "".join(f"{item['sha256']}  {item['zip_name']}\n" for item in meta),
        encoding="utf-8",
    )
    return manifest, written


# ---------------------------------------------------------------------------
# CLI 入口（pack-full.ps1 的调用面；直接调用 main(argv) 可测）
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="full_pack",
        description="firstep 完整包打包：zip 分卷 + 完整包清单 + 删除清单 + 校验和",
    )
    parser.add_argument("--tree", required=True, help="仓库根目录")
    parser.add_argument("--version", required=True, help="版本号（与 GitHub tag 同号，如 v1.1.0）")
    parser.add_argument("--out", required=True, help="输出目录")
    parser.add_argument("--published-at", default="", help="发布时间（UTC ISO8601，可空）")
    parser.add_argument("--baseline", default="", help="上一版完整包清单路径（删除清单基线，可空）")
    parser.add_argument(
        "--limit-mb",
        type=float,
        default=PART_LIMIT_BYTES / 1024 / 1024,
        help="单卷上限 MB（默认与 GitHub 单资产上限留余量后的 1900）",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    tree = Path(args.tree)
    if not tree.is_dir():
        print(f"[错误] 仓库根目录不存在：{tree}", file=sys.stderr)
        return 2

    try:
        manifest, written = prepare_full_package(
            tree,
            version=args.version,
            out_dir=Path(args.out),
            published_at=args.published_at,
            baseline_path=Path(args.baseline) if args.baseline else None,
            limit=int(args.limit_mb * 1024 * 1024),
        )
    except Exception as exc:
        print(f"[错误] 完整包打包失败：{exc}", file=sys.stderr)
        return 1

    total_mb = sum(item["size"] for item in manifest["parts"]) / 1024 / 1024
    source_mb = manifest["total_bytes"] / 1024 / 1024
    materials_files = sum(len(b["files"]) for b in manifest[MATERIALS_MANIFEST_KEY]["batches"])
    print(f"完整包已生成：{args.version}")
    print(f"  包内文件：{len(manifest['files'])} 个（原始 {source_mb:.1f} MB）")
    print(f"  资料库：{len(manifest[MATERIALS_MANIFEST_KEY]['batches'])} 个批次 / {materials_files} 个文件（已写入基线）")
    print(f"  zip 分卷：{len(written)} 卷，共 {total_mb:.1f} MB")
    for path in written:
        print(f"    {path.name}  {path.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"  清单：{Path(args.out) / full_manifest_filename(args.version)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
