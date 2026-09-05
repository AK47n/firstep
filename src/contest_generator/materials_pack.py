"""资料库增量打包核心（工单 materials-update/01）。

发布侧纯函数与薄 I/O 层：资料库扫描（排除自身清单 / .git / __pycache__）、
目录名 → ASCII slug 映射（中文目录登记表，未登记报错）、前后清单 diff
（新增 / 修改 / 删除三态，未变更批次不出现）、分卷切分（单批次 zip 超
limit 自动拆 `.part<N>`）、批次 zip 生成（条目相对资料库根，路径安全由
消费方校验）、清单 JSON 构建。

数据契约（manifest JSON，用户侧与发布侧同一格式）：
    {version, published_at, batches: [{slug, name,
      files: [{path, size, sha256}],   // 该批次全量文件集（下一版 diff 基线）
      removed: [path],                 // 自上一基线起删除的文件（部分删除）
      parts: [{zip_name, size, sha256}]}]}
整批目录删除 = 该批次从 batches 消失（用户侧以「旧清单有、新清单无」推导
删除清单），本模块不另行表示。

纯函数无网络；扫描与 zip 落盘是薄 I/O 层，测试全部临时目录完成。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

MANIFEST_FILENAME = ".materials-manifest.json"
PART_LIMIT_BYTES = int(1.9 * 1024**3)  # GitHub 单资产 2 GB 上限留余量

# 中文顶级目录名 → ASCII slug（新增目录须在此登记；未登记 = 大声失败）
DIR_SLUGS: dict[str, str] = {
    "2026_04_地猛星电赛控制题配套资料": "2026-04-dimx-kit",
    "2026_06_电赛视觉资料": "2026-06-vision",
    "2026_07_电赛带练真题资料": "2026-07-drill-topics",
    "2026_08_MSPM0G3507与常用芯片手册": "2026-08-mspm0-manuals",
    "2026_08_STM32F103手册": "2026-08-stm32-manuals",
    "C7-3-4L ESP32-CAM开发板资料": "c7-3-4l-esp32cam",
    "k230资料": "k230",
    "MSPM0_MOTOR参考例程": "mspm0-motor-examples",
    "塔克R3两驱小车底盘资料": "tark-r3-chassis",
    "无线串口模块资料": "wireless-uart",
}

# 扫描时跳过的条目名（任意层级）
SKIP_NAMES = {".git", "__pycache__", MANIFEST_FILENAME}


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PartFile:
    """清单中的一个文件（相对资料库根的 POSIX 路径）。"""

    path: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}


def file_from_dict(data: dict[str, Any]) -> PartFile:
    return PartFile(
        path=str(data["path"]),
        size=int(data["size"]),
        sha256=str(data["sha256"]),
    )


@dataclass(frozen=True)
class BatchChange:
    """一次发版的版本间，某一个批次的变更（发布侧 diff 与用户侧 check 共用）。"""

    slug: str
    name: str
    added: tuple[PartFile, ...] = ()  # 本次新增的文件
    modified: tuple[PartFile, ...] = ()  # 本次修改的文件
    removed: tuple[str, ...] = ()  # 本次删除的文件（相对资料库根）
    parts: tuple[dict[str, Any], ...] = ()  # 本次增量 zip 分卷元数据（发布后填充）

    @property
    def parts_files(self) -> tuple[PartFile, ...]:
        """本次打包进增量 zip 的文件（新增 + 修改）。"""
        return self.added + self.modified

    @property
    def add_count(self) -> int:
        return len(self.added)

    @property
    def modify_count(self) -> int:
        return len(self.modified)

    @property
    def del_count(self) -> int:
        return len(self.removed)

    @staticmethod
    def split_parts(
        files: Sequence[PartFile], limit: int = PART_LIMIT_BYTES
    ) -> list[list[PartFile]]:
        """按累计原始大小切分卷：超过 limit 即开新卷；单文件超限单独成卷。"""
        parts: list[list[PartFile]] = []
        current: list[PartFile] = []
        current_size = 0
        for file in files:
            if current and current_size + file.size > limit:
                parts.append(current)
                current = []
                current_size = 0
            current.append(file)
            current_size += file.size
        if current:
            parts.append(current)
        return parts


# ---------------------------------------------------------------------------
# slug
# ---------------------------------------------------------------------------


def slug_for_dir(dirname: str) -> str:
    """目录名 → ASCII slug：登记表命中直接用；全 ASCII 则规范化；否则报错。

    规范化：小写；非 `[A-Za-z0-9._-]` 字符替换为 `_`（空格等）。
    """
    if dirname in DIR_SLUGS:
        return DIR_SLUGS[dirname]
    if all(ord(ch) < 128 for ch in dirname) and dirname not in (".", ".."):
        return "".join(ch.lower() if ch.isalnum() or ch in "._-" else "_" for ch in dirname)
    raise ValueError(f"目录「{dirname}」未登记 slug，请在 DIR_SLUGS 中登记后再打包")


# ---------------------------------------------------------------------------
# 扫描（薄 I/O 层）
# ---------------------------------------------------------------------------


def _relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def scan_materials(root: Path) -> list[PartFile]:
    """扫描资料库根：全部文件 → PartFile（相对 POSIX 路径 / size / sha256）。

    跳过 SKIP_NAMES（任意层级）与零字节以下的目录噪音；结果按 path 排序
    （确定性，diff 稳定）。
    """
    entries: list[PartFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_NAMES for part in path.relative_to(root).parts):
            continue
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(256 * 1024), b""):
                digest.update(chunk)
        entries.append(
            PartFile(
                path=_relative_posix(root, path),
                size=path.stat().st_size,
                sha256=digest.hexdigest(),
            )
        )
    entries.sort(key=lambda e: e.path)
    return entries


def scan_as_manifest(root: Path, version: str) -> dict[str, Any]:
    """扫描结果直接构造成「当前全量清单」（批次 = 顶级目录，slug 映射登记）。"""
    entries = scan_materials(root)
    groups: dict[str, list[PartFile]] = {}
    for entry in entries:
        top = entry.path.split("/", 1)[0]
        groups.setdefault(top, []).append(entry)
    batches = []
    for dirname in sorted(groups):
        files = [f.to_dict() for f in groups[dirname]]
        batches.append(
            {
                "slug": slug_for_dir(dirname),
                "name": dirname,
                "files": files,
                "removed": [],
                "parts": [],
            }
        )
    return {"version": version, "published_at": "", "batches": batches}


# ---------------------------------------------------------------------------
# diff（纯函数）
# ---------------------------------------------------------------------------


def diff_manifest(
    prev: dict[str, Any] | None, curr: dict[str, Any]
) -> list[BatchChange]:
    """前后清单 diff → 批次变更列表（未变更批次不出现）。

    prev=None（首次 / Init / Full）→ 全部视为新增；整批目录被删 → 返回
    仅含 removed 的变更（slug / parts_files 空）。
    """
    prev_batches = {
        b["slug"]: b for b in (prev or {}).get("batches", [])
    }
    curr_batches = {b["slug"]: b for b in curr.get("batches", [])}
    changes: list[BatchChange] = []

    for slug, cur in curr_batches.items():
        prev_files = {f["path"]: f for f in prev_batches[slug]["files"]} if slug in prev_batches else {}
        cur_files = {f["path"]: f for f in cur["files"]}
        added = [cur_files[p] for p in sorted(cur_files) if p not in prev_files]
        modified = [
            cur_files[p]
            for p in sorted(cur_files)
            if p in prev_files and prev_files[p]["sha256"] != cur_files[p]["sha256"]
        ]
        removed = [p for p in sorted(prev_files) if p not in cur_files]
        if not added and not modified and not removed:
            continue
        changes.append(
            BatchChange(
                slug=slug,
                name=str(cur.get("name") or slug),
                added=tuple(PartFile(**f) for f in added),
                modified=tuple(PartFile(**f) for f in modified),
                removed=tuple(removed),
            )
        )

    # 整批目录删除：旧清单有、新清单无
    for slug, old in prev_batches.items():
        if slug in curr_batches:
            continue
        removed = [f["path"] for f in old["files"]]
        if removed:
            changes.append(
                BatchChange(slug=slug, name=str(old.get("name") or slug),
                            removed=tuple(removed))
            )
    return changes


# ---------------------------------------------------------------------------
# zip 生成（薄 I/O 层）
# ---------------------------------------------------------------------------


def build_zip_parts(
    materials_root: Path,
    zip_base: str,
    files: Sequence[PartFile],
    out_dir: Path,
    limit: int = PART_LIMIT_BYTES,
) -> tuple[list[dict[str, Any]], list[Path]]:
    """把变更文件按分卷打成 zip（条目路径 = 相对资料库根）。

    返回 `([{zip_name, size, sha256}], [zip 路径])`；zip_name 默认
    `<zip_base>.zip`，多卷为 `<zip_base>.part<N>.zip`（N 从 1 起）。
    单文件超限 = 单独成卷（由发布者注意是否需整批切割）。
    """
    parts = BatchChange.split_parts(files, limit)
    meta: list[dict[str, Any]] = []
    written: list[Path] = []
    for index, part in enumerate(parts, start=1):
        zip_name = f"{zip_base}.zip" if len(parts) == 1 else f"{zip_base}.part{index}.zip"
        zip_path = out_dir / zip_name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in part:
                source = materials_root / Path(*file.path.split("/"))
                archive.write(source, arcname=file.path)
        digest = hashlib.sha256()
        with open(zip_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(256 * 1024), b""):
                digest.update(chunk)
        meta.append(
            {
                "zip_name": zip_name,
                "size": zip_path.stat().st_size,
                "sha256": digest.hexdigest(),
            }
        )
        written.append(zip_path)
    return meta, written


# ---------------------------------------------------------------------------
# 清单构建（纯函数）
# ---------------------------------------------------------------------------


def build_manifest(
    version: str,
    published_at: str,
    full_batches: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """构建新版全量清单。`full_batches` 为「当前全量」批次列表（files 全量、
    removed / parts 已按 diff 结果填充），未变更批次 parts 为空。"""
    return {
        "version": version,
        "published_at": published_at,
        "batches": [
            {
                "slug": b["slug"],
                "name": b["name"],
                "files": b["files"],
                "removed": b.get("removed", []),
                "parts": b.get("parts", []),
            }
            for b in full_batches
        ],
    }


# ---------------------------------------------------------------------------
# 编排（prepare_package：Init / Full / Diff 三种模式）
# ---------------------------------------------------------------------------


def prepare_package(
    tree: Path,
    prev: dict[str, Any] | None,
    version: str,
    out_dir: Path,
    write_zips: bool = True,
    limit: int = PART_LIMIT_BYTES,
    published_at: str = "",
) -> tuple[dict[str, Any], list[Path]]:
    """资料库打包编排：scan → diff → (zip) → manifest。

    - prev=None, write_zips=False：Init（只出当前快照清单，不打包）
    - prev=None, write_zips=True：Full（全量打批次分卷包）
    - prev=清单, write_zips=True：Diff（只打新增 / 修改文件）
    返回 `(manifest, written_zips)`；manifest 落盘由调用方决定。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    curr = scan_as_manifest(tree, version)
    changes = diff_manifest(prev, curr)

    # 全量批次表：以 scan 全量为准；removed / parts 按 diff 合并
    full_batches: list[dict[str, Any]] = []
    change_by_slug = {c.slug: c for c in changes}
    written: list[Path] = []
    for batch in curr["batches"]:
        slug = batch["slug"]
        change = change_by_slug.get(slug)
        removed = list(change.removed) if change else []
        parts: list[dict[str, Any]] = []
        written_for_batch: list[Path] = []
        if change and change.parts_files and write_zips:
            zip_base = f"firstep-materials-{version}-{slug}"
            parts, written_for_batch = build_zip_parts(tree, zip_base, change.parts_files, out_dir, limit)
        full_batches.append(
            {
                "slug": slug,
                "name": batch["name"],
                "files": batch["files"],
                "removed": removed,
                "parts": parts,
            }
        )
        written.extend(written_for_batch)

    manifest = build_manifest(version, published_at, full_batches)
    return manifest, written


# ---------------------------------------------------------------------------
# CLI 入口（pack-materials.ps1 的调用面；直接调用 main(argv) 可测）
# ---------------------------------------------------------------------------


def _load_prev_manifest(location: str) -> dict[str, Any]:
    """从本地路径或 URL 读取上一版清单（diff 模式的基线）。"""
    target: Path
    if location.startswith(("http://", "https://")):
        request = urllib.request.Request(
            location, headers={"User-Agent": "firstep-materials-pack"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    target = Path(location)
    if not target.is_file():
        raise FileNotFoundError(f"上一版清单不存在：{target}")
    # utf-8-sig 容忍 BOM：Windows 上 PS 5.1 / 部分编辑器写的 UTF-8 清单常带 BOM
    return json.loads(target.read_text(encoding="utf-8-sig"))


def _write_manifest(manifest: dict[str, Any], out_dir: Path, version: str) -> Path:
    manifest_path = out_dir / f"firstep-materials-{version}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest_path


def main(argv: Sequence[str] | None = None) -> int:
    """资料库打包 CLI：`python -m contest_generator.materials_pack --help`。

    模式：
      init   只生成当前快照清单（不发 zip）
      full   无基线全量打包（每批次起点 = 全部文件）
      diff   相对上一版清单只打新增 / 修改文件（-Baseline 本地路径或 URL）
    """
    parser = argparse.ArgumentParser(
        prog="materials_pack",
        description="firstep 资料库增量打包：清单 + 批次分卷 zip",
    )
    parser.add_argument("--tree", required=True, help="资料库根目录（sources/materials）")
    parser.add_argument("--version", required=True, help="资料库版本号（如 v1.1.0）")
    parser.add_argument("--out", required=True, help="输出目录")
    parser.add_argument("--mode", choices=("init", "full", "diff"), default="init")
    parser.add_argument("--baseline", default="", help="diff 模式：上一版清单路径或 URL")
    args = parser.parse_args(list(argv) if argv is not None else None)

    version = args.version
    if not version or not all(ch.isalnum() or ch in "._-" for ch in version):
        print(f"[错误] 版本号含非法字符：{version!r}", file=sys.stderr)
        return 2

    tree = Path(args.tree)
    if not tree.is_dir():
        print(f"[错误] 资料库目录不存在：{tree}", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    try:
        if args.mode == "diff":
            if not args.baseline:
                print("[错误] diff 模式需要 --baseline（上一版清单路径或 URL）", file=sys.stderr)
                return 2
            prev = _load_prev_manifest(args.baseline)
            manifest, written = prepare_package(
                tree, prev=prev, version=version, out_dir=out_dir, write_zips=True
            )
        elif args.mode == "full":
            manifest, written = prepare_package(
                tree, prev=None, version=version, out_dir=out_dir, write_zips=True
            )
        else:  # init
            manifest, written = prepare_package(
                tree, prev=None, version=version, out_dir=out_dir, write_zips=False
            )
    except Exception as exc:
        print(f"[错误] 打包失败：{exc}", file=sys.stderr)
        return 1

    manifest_path = _write_manifest(manifest, out_dir, version)
    changed = [b for b in manifest["batches"] if b["parts"]]
    total_mb = sum(p["size"] for b in changed for p in b["parts"]) / 1024 / 1024
    print(f"清单：{manifest_path}")
    print(f"版本：{version}，批次 {len(manifest['batches'])} 个（有变更 {len(changed)} 个）")
    if written:
        print(f"增量 zip：{len(written)} 卷，共 {total_mb:.1f} MB")
        for path in written:
            print(f"  {path.name}")
    else:
        print("无增量 zip（init 模式或零变更）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
