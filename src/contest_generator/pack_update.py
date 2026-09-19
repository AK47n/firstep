"""小发版更新包打包核心（工单 full-download/08）。

**为什么要重做**：原先 `tools/pack-update.ps1` 直接用 `git archive` 打 zip，而
`git archive` 按调用方机器的 `core.autocrlf` 做 checkout 侧转换——本机 `=true`
时它把 blob 的 LF 转成 CRLF，而完整包读工作树字节，两边对同一 commit 的同一文件
就可能给出不同字节（v1.1.0 现场：3474 个共有文件里 926 个字节不同、真实内容差异 0 个）。
后果不是洁癖：增量发布按字节 SHA256 判「改了哪些文件」，这些文件会被一律判为
「已修改」，把「只下变化部分」变成「几乎全量重下」。

**做法**：把 `git archive` 的属性转换钉成**确定性**——显式 `-c core.autocrlf=false`：

- `core.autocrlf=false` 时不做文本转换（`core.eol` 也不参与）；
- `.gitattributes` 里显式写了 `eol` 的仍按其物化（`*.bat text eol=crlf` → CRLF，
  `.githooks/* text eol=lf` → LF）——这正是仓库要的口径，也与工作树检出结果一致。

于是更新包字节 = 工作树字节 = 完整包字节，**在设过 autocrlf 的机器上同样成立**；
`.bat` 的 CRLF 与钩子的 LF 都保持不变。`tests/test_pack_update.py` 的跨包守卫钉住这条。

非 git 目录（手工打包 / 测试夹具）回退为按清单读盘打 zip；清单很长时自动分块
（Windows 命令行有长度上限），两条路径产出同样的 zip 内容。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Sequence

from .full_pack import (
    _validate_version,
    cumulative_removed,
    is_product_file,
    previous_shipped_files,
)

__all__ = [
    "EMPTY_REMOVED_PLACEHOLDER",
    "UPDATE_ZIP_PREFIX",
    "pack_update",
    "read_files_manifest",
    "select_product_files",
    "sha256_of",
    "write_removed_list",
]

# 更新包 zip 名前缀（与 `update.UPDATE_ZIP_PREFIX` 同口径：用户侧按它识别小发版资产）
UPDATE_ZIP_PREFIX = "firstep-update-"

# 空删除清单要写一行注释：0 字节文件会被 `gh release upload` 以
# `HTTP 400: Bad Content-Length` 拒收（工单 full-download/08 现场踩到；
# 更新器跳过 `#` 行，语义不变）。
EMPTY_REMOVED_PLACEHOLDER = "# 无删除项（空清单占位：0 字节会被 gh 拒收）"

# 单次 `git archive` 命令行里 pathspec 的总长度上限（保守值，远低于 Windows
# CreateProcess 的 32767 限制；本机 tracked 快照约 3500 个文件、~150KB → 分 2 块）。
_PATHSPEC_CHUNK_CHARS = 60_000


# ---------------------------------------------------------------------------
# 清单、分块与哈希
# ---------------------------------------------------------------------------


def read_files_manifest(path: Path) -> list[str]:
    """读文件清单（每行一个仓库根相对路径；空行与 `#` 注释跳过）。

    容忍 BOM 与 CRLF：清单由 PowerShell 写出过，也可能被人工编辑。
    """
    text = Path(path).read_text(encoding="utf-8-sig")
    paths: list[str] = []
    for line in text.splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        paths.append(name)
    return paths


def _pathspec_chunks(paths: Sequence[str]) -> Iterator[list[str]]:
    """把路径清单切成若干块，使每块拼起来不超过命令行长度上限。"""
    chunk: list[str] = []
    size = 0
    for name in paths:
        if chunk and size + len(name) + 1 > _PATHSPEC_CHUNK_CHARS:
            yield chunk
            chunk, size = [], 0
        chunk.append(name)
        size += len(name) + 1
    if chunk:
        yield chunk


def sha256_of(path: Path) -> str:
    """文件 SHA256（供打包脚本写 `.sha256.txt` 与自检复用）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# 打包
# ---------------------------------------------------------------------------


def _zip_entries(path: Path) -> list[str]:
    """zip 内条目路径（跳过目录项）。"""
    with zipfile.ZipFile(path) as archive:
        return [name for name in archive.namelist() if not name.endswith("/")]


def _archive_via_git(tree: Path, paths: Sequence[str], target: Path) -> bool:
    """用 `git archive` 打（确定性配置）；失败或非 git 仓库返回 False。

    清单很长 → 分块各打一份，再合并成一个 zip（条目内容逐字节搬运、不重压，
    故与单次调用等价）。`--ignore-missing`：manifest 里出现未 tracked 路径时
    （手工清单 / 夹具）让 git 照常出包，不缺 tracked 文件。
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="firstep-pack-"))
    try:
        chunks: list[Path] = []
        for index, chunk in enumerate(_pathspec_chunks(paths)):
            chunk_zip = temp_dir / f"chunk-{index}.zip"
            completed = subprocess.run(
                (
                    "git",
                    "-c",
                    "core.autocrlf=false",
                    "-c",
                    "core.quotepath=false",
                    "archive",
                    "--format=zip",
                    "--ignore-missing",
                    f"--output={chunk_zip}",
                    "HEAD",
                    "--",
                    *chunk,
                ),
                cwd=str(tree),
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0 or not chunk_zip.is_file():
                return False
            chunks.append(chunk_zip)

        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as merged:
            for chunk_zip in chunks:
                with zipfile.ZipFile(chunk_zip) as source:
                    for name in _zip_entries(chunk_zip):
                        merged.writestr(name, source.read(name))
        return True
    except OSError:
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _pack_from_disk(tree: Path, paths: Sequence[str], target: Path) -> None:
    """按清单读盘打 zip（非 git 目录的回退路径）。

    读不到的文件不静默跳过——发版产物宁可失败，也不能少文件。
    """
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in paths:
            source = tree / Path(*name.split("/"))
            if not source.is_file():
                raise ValueError(f"清单里的文件不存在：{name}")
            archive.writestr(name, source.read_bytes())


def select_product_files(candidates: Sequence[str]) -> list[str]:
    """候选清单（`git ls-files` 全量）→ **只留产品文件**（判据单源 = `full_pack.is_product_file`）。

    为什么要这一步（工单 `update-orphan-files/01`）：小发版包原先靠 `tools/pack-update.ps1`
    里一份**手抄的**顶层白名单过滤，与完整包的排除规则是两套——实测把
    `library/revise-backups/**` 1481 个本机库备份与一个 `*.exe` 发到了用户盘上
    （完整包刻意不收），同时**漏了** `00-START-HERE.txt`（白名单漂移），于是 v1.1.1 的用户
    走小发版升级永远拿不到它。现在两边问同一个谓词，漂移不可能再发生。

    保留顺序、去重；空段跳过（清单文件是人工也能编辑的文本）。
    """
    picked: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        name = str(candidate).strip()
        if not name or name in seen or not is_product_file(name):
            continue
        seen.add(name)
        picked.append(name)
    return picked


def write_removed_list(
    out_dir: Path,
    version: str,
    *,
    current: Sequence[str],
    baseline_update_files: Path | None = None,
    baseline_full_manifest: Path | None = None,
    allow_missing_baseline_parts: bool = False,
) -> list[str]:
    """写 `firstep-update-<tag>.removed.txt`（**累计口径**，工单 `update-orphan-files/02`）。

    删除清单 = 上一版**发行集合**（`previous_shipped_files`）− 本版产品文件，
    规则单源在 `full_pack.cumulative_removed`。**为什么是累计**：这份清单是给所有用户用的
    ——跳版升级的用户只会执行本版这一份，只跟上一版做差就会永久留下被跳过版本的删除项。

    清单为空时写一行 `#` 注释占位（0 字节资产会被 `gh release upload` 拒收）。
    返回写出的名字列表（空清单时为空）。
    """
    shipped_before: set[str] = set()
    if baseline_update_files is not None or baseline_full_manifest is not None:
        shipped_before = previous_shipped_files(
            update_files=baseline_update_files,
            full_manifest=baseline_full_manifest,
            allow_missing_parts=allow_missing_baseline_parts,
        )
    removed = cumulative_removed(shipped_before, current)
    target = Path(out_dir) / f"{UPDATE_ZIP_PREFIX}{version}.removed.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(removed) + "\n" if removed else EMPTY_REMOVED_PLACEHOLDER + "\n"
    target.write_bytes(body.encode("utf-8"))
    return removed


def pack_update(
    tree: Path,
    *,
    version: str,
    out_dir: Path,
    files_manifest: Path,
) -> Path:
    """打小发版更新包：读清单 → 按产品判据筛 → `git archive`（确定性）→ zip + `.files.txt`。

    返回 zip 路径。清单不存在 / 为空 / 一个产品文件都不剩，一律 `ValueError`。

    `files_manifest` 收的是**候选**（`tools/pack-update.ps1` 直接喂 `git ls-files` 全量），
    筛选在核心这一层做——这样 zip 与 `.files.txt` 天然一一对应，且判据只有一处。
    """
    _validate_version(version)
    tree = Path(tree)
    out_dir = Path(out_dir)
    if not tree.is_dir():
        raise ValueError(f"仓库根目录不存在：{tree}")
    files_manifest = Path(files_manifest)
    if not files_manifest.is_file():
        raise ValueError(f"文件清单不存在：{files_manifest}")

    candidates = read_files_manifest(files_manifest)
    if not candidates:
        raise ValueError(f"文件清单为空：{files_manifest}")
    paths = select_product_files(candidates)
    if not paths:
        raise ValueError(
            "候选清单里一个产品文件都没有——顶层白名单或排除规则可能写错了"
            f"（候选 {len(candidates)} 条，全被筛掉）"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{UPDATE_ZIP_PREFIX}{version}.zip"

    if not _archive_via_git(tree, paths, zip_path):
        _pack_from_disk(tree, paths, zip_path)

    # 清单与 zip 条目一一对应（发布侧自检会拿两者对拍）
    (out_dir / f"{UPDATE_ZIP_PREFIX}{version}.files.txt").write_text(
        "".join(f"{name}\n" for name in paths), encoding="utf-8"
    )
    return zip_path


# ---------------------------------------------------------------------------
# CLI 入口（tools/pack-update.ps1 的调用面；直接调用 main(argv) 可测）
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pack_update",
        description="firstep 小发版更新包打包：zip + files.txt（字节与完整包同源）",
    )
    parser.add_argument("--tree", required=True, help="仓库根目录")
    parser.add_argument("--version", required=True, help="版本号（与 GitHub tag 同号，如 v1.1.2）")
    parser.add_argument("--out", required=True, help="输出目录")
    parser.add_argument("--files", required=True, help="文件清单（每行一个相对路径）")
    parser.add_argument(
        "--baseline-update-files",
        default="",
        help="上一版小发版清单（`firstep-update-<tag>.files.txt`；与它旁边的 `.removed.txt` "
             "一起构成累计删除清单的输入，可空）",
    )
    parser.add_argument(
        "--baseline-full-manifest",
        default="",
        help="上一版完整包清单（`firstep-full-<tag>.manifest.json`；可空）",
    )
    parser.add_argument(
        "--allow-missing-baseline-parts",
        action="store_true",
        help="允许基线旁边的 .removed.txt 缺失（首次发布等；缺省 = 缺了就拒绝发版）",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        zip_path = pack_update(
            Path(args.tree),
            version=args.version,
            out_dir=Path(args.out),
            files_manifest=Path(args.files),
        )
        candidates = read_files_manifest(Path(args.files))
        selected = select_product_files(candidates)
        removed = write_removed_list(
            Path(args.out),
            args.version,
            current=selected,
            baseline_update_files=(
                Path(args.baseline_update_files) if args.baseline_update_files else None
            ),
            baseline_full_manifest=(
                Path(args.baseline_full_manifest) if args.baseline_full_manifest else None
            ),
            allow_missing_baseline_parts=bool(args.allow_missing_baseline_parts),
        )
    except Exception as exc:
        print(f"[错误] 更新包打包失败：{exc}", file=sys.stderr)
        return 1

    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"更新包已生成：{zip_path}")
    print(f"  候选 {len(candidates)} 条 → 产品文件 {len(selected)} 条（筛掉 "
          f"{len(candidates) - len(selected)} 条：本地备份目录 / 安装包 / 缓存 / 白名单外）")
    print(f"  删除清单：{len(removed)} 条（累计口径：历史发过、本版不发）")
    print(f"  zip 大小：{size_mb:.1f} MB")
    print(f"  SHA256：{sha256_of(zip_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
