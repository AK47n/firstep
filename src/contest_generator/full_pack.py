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
    # 面向新用户：解压后第一个该看到的东西（工单 newuser-download/02）。
    # 文件名前的 `00-` 是刻意的：资源管理器按名称排序时它排**第一位**，新人打开文件夹
    # 第一眼就撞上它（裸叫 `START-HERE.txt` 会掉到 README 之下，实测名称序 #11/14、
    # 隐藏扩展名时 #17/22——等于没有）。
    # 它必须在白名单里，否则按下面的规则根本不进包——新用户解压完就又是「没有任何说明」。
    "00-START-HERE.txt",
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
        ".trash-dedup",
    }
)

# 任意层级跳过的文件名
SKIP_FILE_NAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db", MANIFEST_FILENAME})

# 任意层级跳过的后缀（机器可再生的缓存 / 构建产物 / 日志）
SKIP_FILE_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo", ".log")

# 包内相对路径长度上限（工单 path-budget/01）。
# 为什么必须有这条护栏：Windows 资源管理器「全部解压缩」走老 API、硬卡 259 字符
# （含解压根目录），超了报 `0x80010135: 路径太长`，点「跳过」还会**静默丢文件**；
# 解压根目录取决于用户名与放哪（实测 `C:\Users\Administrator\Desktop\firstep` 这种
# 常见姿势就吃掉 38 字符）。工具自身的解压（Python zipfile）与 `tar.exe` 走长路径
# API 不受影响——所以病灶只有一个：**包内路径太长**，必须在打包这一关挡住。
# 上限取 200（≈59 字符余量）：库里最长路径实测 194（减肥前 223，已按
# `.scratch/path-budget/` 的操作脚本压下来），再长就该动资料库而不是放宽这里。
MAX_ENTRY_PATH_CHARS = 200

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
    "MAX_ENTRY_PATH_CHARS",
    "SKIP_DIR_NAMES",
    "SKIP_FILE_NAMES",
    "SKIP_FILE_SUFFIXES",
    "TOP_LEVEL_ENTRIES",
    "build_full_manifest",
    "build_zip_volumes",
    "cumulative_removed",
    "ensure_paths_fit",
    "excluded_paths",
    "find_baseline_parts",
    "find_update_files_for",
    "full_manifest_filename",
    "is_product_file",
    "main",
    "materials_excluded",
    "overlong_entries",
    "prepare_full_package",
    "previous_shipped_files",
    "product_file_reason",
    "product_paths",
    "read_release_file_list",
    "register_materials_dirs",
    "release_tag_of",
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


def product_file_reason(
    relative: str, *, skip_dir_names: frozenset[str] | None = None
) -> str | None:
    """仓库根相对路径 → **不进包的原因**（中文可读）；`None` = 它是产品文件。

    **这是「哪些文件算产品文件」的唯一判据**（工单 `update-orphan-files/01`）。
    为什么必须单源：完整包按这套规则扫工作树，小发版包原先只按一份**手抄的顶层白名单**
    过滤 `git ls-files`——于是同一次发布的两条更新路径给出两套盘面，实测已经漂移三处
    （白名单漏了 `00-START-HERE.txt`、排除规则整套没抄、两者对「本机库备份目录」的判定相反）。
    小发版包因此把 `library/revise-backups/**` 1481 个文件发到了每个用户盘上，
    而完整包刻意不收它们。

    判据本体住在 `full_pack`（完整包扫描先有它），`scan_tree` / `excluded_paths` /
    小发版打包核心都问它，谁都不许再写一份。

    `skip_dir_names` 只给测试用（造一个「只排除某类目录」的扫描面）；
    产品路径一律用缺省的 `SKIP_DIR_NAMES`。
    """
    parts = [part for part in str(relative).replace("\\", "/").split("/") if part]
    if not parts:
        return "顶层之外"
    dir_skips = SKIP_DIR_NAMES if skip_dir_names is None else skip_dir_names
    # 目录名排除优先判定（.git / .scratch 这类既非白名单也不该进包的）
    if any(part in dir_skips for part in parts[:-1]):
        return "dir-name"
    if parts[-1] in dir_skips:
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


def is_product_file(relative: str) -> bool:
    """这个仓库根相对路径算不算产品文件（`product_file_reason` 的二值投影）。

    两个打包器共用它：完整包扫工作树时筛盘上文件，小发版包筛 `git ls-files` 的候选清单。
    于是「小发版包发的东西 ⊆ 完整包发的东西」这条不再靠人手同步两处。
    """
    return product_file_reason(relative) is None


def _exclude_reason(root: Path, path: Path) -> str | None:
    """文件不满足进包条件时返回原因（中文可读），否则 None。

    只是把 `product_file_reason`（判据单源）套到「根 + 绝对路径」这对入参上——
    规则一个字都不在这儿。
    """
    return product_file_reason("/".join(_relative_parts(root, path)))


def scan_tree(root: Path, *, skip_dir_names: frozenset[str] | None = None) -> list[PartFile]:
    """扫描仓库树 → PartFile 列表（相对 POSIX 路径 / size / sha256，按路径排序）。

    只收白名单顶层下的文件，按 `SKIP_DIR_NAMES` / `SKIP_FILE_NAMES` /
    `INSTALLER_GLOBS` / `SKIP_FILE_SUFFIXES` 排除；排序保证清单与分卷确定性。
    排除判据**不在这里**——它只住 `product_file_reason`（本函数与 `excluded_paths`、
    小发版打包核心共用同一份，工单 `update-orphan-files/01`）。

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
        relative = "/".join(parts)
        if product_file_reason(relative, skip_dir_names=dir_skips) is not None:
            continue
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(256 * 1024), b""):
                digest.update(chunk)
        entries.append(
            PartFile(
                path=relative,
                size=path.stat().st_size,
                sha256=digest.hexdigest(),
            )
        )
    entries.sort(key=lambda e: e.path)
    return entries


def product_paths(root: Path, *, skip_dir_names: frozenset[str] | None = None) -> set[str]:
    """扫工作树 → 产品文件**路径集合**（不算哈希，比 `scan_tree` 便宜得多）。

    用途 = 发布侧删除清单的「本版发行集合」。小发版打包器**必须**拿它当基准（而不能只有
    `git ls-files` 那份）：完整包会发一批**未被 git 跟踪**的产品文件（例如
    `library/masters/**/Project.uvguix.*`、`sources/contest/**` 下的构建产物、`*.pdf`），
    它们不在小发版清单里，却不是「本版不再发」的东西。拿小发版清单当基准，它们就会被写进
    删除清单、升级时**真被删掉**——本机离线演练实测踩到：`not_in_official == 0` 成立、
    而盘上少了 `Project.uvguix.luoji` 与几个 `sources/contest/**` 文件。
    """
    root = Path(root)
    dir_skips = SKIP_DIR_NAMES if skip_dir_names is None else skip_dir_names
    found: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = "/".join(_relative_parts(root, path))
        if product_file_reason(relative, skip_dir_names=dir_skips) is None:
            found.add(relative)
    return found


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


def cumulative_removed(shipped_before: Iterable[str], current: Iterable[str]) -> list[str]:
    """**发布侧删除清单的唯一算法**：历史发过、本版不发的一律删（排序输出）。

    为什么不能只跟「上一版」做差（工单 `update-orphan-files/02`）：删除清单是给**所有**用户
    用的——任何版本的用户升级到本版都执行同一份。只看上一版，**跳版升级**的用户就会永久
    留下被跳过那个版本删掉的文件（一个版本区间的洞）。所以输入取「上一版**发行集合**」，
    而那一份本身已经含更早的历史（见 `previous_shipped_files`）。

    **安全边界**：只删「发布过的名字」。用户自己补录的模块 / 归档的参考文件从不出现在任何
    发布清单里，因此不可能被这条规则删掉——这正是本方案与「按本版文件集合扫盘清理」那条
    危险修法的分界（那条会连用户内容一起删）。

    空行与 `#` 注释跳过；输出排序，保证同一输入给出逐字节相同的清单。
    """
    now = {name for name in (str(item).strip() for item in current) if name}
    names = {
        name for name in (str(item).strip() for item in shipped_before)
        if name and not name.startswith("#")
    }
    return sorted(names - now)


def read_release_file_list(path: Path) -> list[str]:
    """读发布清单（每行一个相对路径；空行与 `#` 注释跳过，容忍 BOM 与 CRLF）。

    `tools/pack-update.ps1` 写出的 `.files.txt` / `.removed.txt` 就是这个形态；
    更新器的 `remove_named_files` 读的也是同一形态。
    """
    text = Path(path).read_bytes().decode("utf-8-sig")
    return [
        line.strip() for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _removed_sibling(update_files: Path) -> Path:
    """`firstep-update-<tag>.files.txt` → 同目录的 `.removed.txt`。"""
    name = Path(update_files).name
    suffix = ".files.txt"
    if not name.endswith(suffix):
        return Path(update_files).with_name(name + ".removed.txt")
    return Path(update_files).with_name(name[: -len(suffix)] + ".removed.txt")


def release_tag_of(name: str) -> str:
    """发布产物文件名 → tag。

    `firstep-update-v1.1.1.files.txt` / `firstep-full-v1.1.1.manifest.json` / … → `v1.1.1`。

    **为什么要有这个函数**（而不是让打包脚本自己切字符串）：tag 里带点（`v1.1.1`），
    而后缀里也有点——PowerShell 的 `GetFileNameWithoutExtension` 只削**一层**扩展名，
    于是 `firstep-update-v1.1.1.files.txt` 会被切成 `v1.1.1.files`，算出
    `firstep-update-v1.1.1.files.removed.txt` 这个**不存在**的兄弟名
    （`.scratch/update-orphan-files/drill-offline.py` 第一次跑就是这么红的）。
    规则放在 Python 侧，才有单测钉得住。
    """
    stem = Path(str(name)).name
    for suffix in (".files.txt", ".removed.txt", ".manifest.json", ".sha256.txt",
                   ".txt", ".json"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    for prefix in ("firstep-update-", "firstep-full-", "firstep-materials-"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    return stem


def find_baseline_parts(
    update_files: Path, *, search_dir: Path | None = None
) -> tuple[Path, Path | None]:
    """→（上一版小发版删除清单, 上一版完整包清单或 `None`）。

    - 删除清单：与 `update_files` 同目录、同 tag 的 `.removed.txt`
      （找不到时由 `previous_shipped_files` 决定是拒绝发版还是放行）；
    - 完整包清单：`search_dir`（缺省 = `update_files` 所在目录）里的
      `firstep-full-<tag>.manifest.json`——有才算，没有就只是少一份输入。
    """
    update_files = Path(update_files)
    tag = release_tag_of(update_files.name)
    where = Path(search_dir) if search_dir is not None else update_files.parent
    manifest = where / f"firstep-full-{tag}.manifest.json"
    return _removed_sibling(update_files), (manifest if manifest.is_file() else None)


def find_update_files_for(
    manifest: Path, *, search_dir: Path | None = None
) -> Path | None:
    """给定上一版**完整包清单** → 同 tag 的小发版清单（`firstep-update-<tag>.files.txt`）。

    反向的那个方向在 `find_baseline_parts`（给小发版清单 → 完整包清单）里。
    两处都不在 PowerShell 里手写字符串切分——tag 里的点与后缀里的点会咬人。
    """
    manifest = Path(manifest)
    tag = release_tag_of(manifest.name)
    where = Path(search_dir) if search_dir is not None else manifest.parent
    candidate = where / f"firstep-update-{tag}.files.txt"
    return candidate if candidate.is_file() else None


def previous_shipped_files(
    *,
    update_files: Path | None = None,
    full_manifest: Path | None = None,
    allow_missing_parts: bool = False,
) -> set[str]:
    """上一版**发行集合** = 小发版清单 ∪ 小发版删除清单 ∪ 完整包清单的 files ∪ removed。

    为什么要三项一起（工单 `update-orphan-files/02`）：两条打包路径发的东西**不一样**——
    完整包收不到的（`library/revise-backups/**` 这类被排除的目录、`*.exe`）小发版包原先照发；
    完整包发过的（未被 git 跟踪的 `sources/contest/**` 构建产物）小发版清单里根本没有。
    只取其中一份，另一份发过的文件就永远清不掉。

    `allow_missing_parts=False`（缺省）时，给了 `update_files` 却找不到它旁边的
    `.removed.txt` → **大声失败**：宁可不发版，也不写出一份比用户盘面短的删除清单
    （少删 = 用户盘上永久残留，且没有任何东西会报警）。
    """
    shipped: set[str] = set()
    if update_files is not None:
        shipped.update(read_release_file_list(Path(update_files)))
        sibling = _removed_sibling(Path(update_files))
        if sibling.is_file():
            shipped.update(read_release_file_list(sibling))
        elif not allow_missing_parts:
            raise ValueError(
                f"上一版的小发版删除清单不见了：{sibling}"
                f"（与 {Path(update_files).name} 同目录同 tag）。"
                "没有它就写不出完整的累计删除清单（跳版升级的用户会留下残留）。"
                "确认过确实要这么发（例如首次发布）再传 allow_missing_parts=True。"
            )
    if full_manifest is not None:
        data = json.loads(Path(full_manifest).read_bytes().decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError(f"完整包清单格式非法（顶层不是对象）：{full_manifest}")
        shipped.update(
            str(item.get("path") or "")
            for item in data.get("files") or [] if isinstance(item, dict)
        )
        shipped.update(str(name) for name in data.get("removed") or [])
    return {
        name for name in (str(item).strip() for item in shipped)
        if name and not name.startswith("#")
    }


def overlong_entries(
    files: Sequence[PartFile], limit: int = MAX_ENTRY_PATH_CHARS
) -> list[PartFile]:
    """包内相对路径超过上限的文件（空 = 可发版），按长度降序。"""
    return sorted(
        (f for f in files if len(f.path) > limit), key=lambda f: len(f.path), reverse=True
    )


def ensure_paths_fit(
    files: Sequence[PartFile], limit: int = MAX_ENTRY_PATH_CHARS
) -> None:
    """过长的包内路径直接拒绝发版（否则用户解压时静默丢文件）。

    判据只有一条：`len(相对路径) <= limit`。失败信息必须给出「长度 + 路径 +
    怎么办」，因为这条错误只会在发版时撞到，而发版的人就是唯一能修的人。
    """
    bad = overlong_entries(files, limit)
    if not bad:
        return
    head = "\n".join(f"  {len(f.path):4d}  {f.path}" for f in bad[:5])
    more = f"\n  ……另有 {len(bad) - 5} 个" if len(bad) > 5 else ""
    raise ValueError(
        f"包内路径超过 {limit} 字符上限，共 {len(bad)} 个文件——"
        "Windows 资源管理器解压会报「路径太长」并**跳过文件**（用户拿到残缺包）。\n"
        f"{head}{more}\n"
        "修法：给资料库对应目录做「路径减肥」（改目录名，不删内容）——"
        "见 `.scratch/path-budget/slim_materials_paths.py`（dry-run 默认，--write 才落盘）。"
    )


def prepare_full_package(
    tree: Path,
    *,
    version: str,
    out_dir: Path,
    published_at: str = "",
    baseline_path: Path | None = None,
    baseline_update_files: Path | None = None,
    baseline_search_dir: Path | None = None,
    allow_missing_baseline_parts: bool = False,
    limit: int = PART_LIMIT_BYTES,
) -> tuple[dict[str, Any], list[Path]]:
    """完整包打包编排：scan → zip 分卷 → 清单 / 删除清单 / SHA256 落盘。

    返回 `(manifest, written_zips)`；删除清单基线 = `baseline_path` 指向的
    上一版完整包清单（None = 首次发布，空清单）。

    删除清单按**累计口径**算（`cumulative_removed`，工单 `update-orphan-files/02`）：
    输入是上一版的**发行集合**——完整包清单的 `files` ∪ `removed`，外加（如果给了）
    上一版小发版清单 `baseline_update_files` 及其 `.removed.txt`。只看上一版清单的话，
    跳版升级的用户会永久留下被跳过版本的删除项。
    """
    _validate_version(version)
    tree = Path(tree)
    out_dir = Path(out_dir)
    if not tree.is_dir():
        raise ValueError(f"仓库根目录不存在：{tree}")

    files = scan_tree(tree)
    if not files:
        raise ValueError("扫描结果为空——顶层白名单或排除规则可能写错了")
    ensure_paths_fit(files)

    current_paths = [f.path for f in files]
    if baseline_update_files is None and baseline_path is not None and baseline_search_dir:
        # 同 tag 的上一版小发版清单：有就并进「发行集合」（两条打包路径发的东西不一样）
        baseline_update_files = find_update_files_for(
            Path(baseline_path), search_dir=Path(baseline_search_dir))
    if baseline_path is not None or baseline_update_files is not None:
        shipped_before = previous_shipped_files(
            update_files=baseline_update_files,
            full_manifest=Path(baseline_path) if baseline_path is not None else None,
            allow_missing_parts=allow_missing_baseline_parts,
        )
        removed = cumulative_removed(shipped_before, current_paths)
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
        "--baseline-update-files",
        default="",
        help="上一版小发版清单（`firstep-update-<tag>.files.txt`，累计删除清单的第二个输入，可空）",
    )
    parser.add_argument(
        "--baseline-search-dir",
        default="",
        help="按基线 tag 找上一版小发版清单的目录（缺省 = 不自动找）",
    )
    parser.add_argument(
        "--allow-missing-baseline-parts",
        action="store_true",
        help="允许基线旁边的 .removed.txt 缺失（首次发布等；缺省 = 缺了就拒绝发版）",
    )
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
            baseline_update_files=(
                Path(args.baseline_update_files) if args.baseline_update_files else None
            ),
            baseline_search_dir=(
                Path(args.baseline_search_dir) if args.baseline_search_dir else None
            ),
            allow_missing_baseline_parts=bool(args.allow_missing_baseline_parts),
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
