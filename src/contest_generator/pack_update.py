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

from .full_pack import _validate_version

__all__ = ["UPDATE_ZIP_PREFIX", "pack_update", "read_files_manifest", "sha256_of"]

# 更新包 zip 名前缀（与 `update.UPDATE_ZIP_PREFIX` 同口径：用户侧按它识别小发版资产）
UPDATE_ZIP_PREFIX = "firstep-update-"

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


def pack_update(
    tree: Path,
    *,
    version: str,
    out_dir: Path,
    files_manifest: Path,
) -> Path:
    """打小发版更新包：读清单 → `git archive`（确定性）→ zip + `.files.txt`。

    返回 zip 路径。清单不存在 / 为空 / 文件读不到，一律 `ValueError`。
    """
    _validate_version(version)
    tree = Path(tree)
    out_dir = Path(out_dir)
    if not tree.is_dir():
        raise ValueError(f"仓库根目录不存在：{tree}")
    files_manifest = Path(files_manifest)
    if not files_manifest.is_file():
        raise ValueError(f"文件清单不存在：{files_manifest}")

    paths = read_files_manifest(files_manifest)
    if not paths:
        raise ValueError(f"文件清单为空：{files_manifest}")

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
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        zip_path = pack_update(
            Path(args.tree),
            version=args.version,
            out_dir=Path(args.out),
            files_manifest=Path(args.files),
        )
    except Exception as exc:
        print(f"[错误] 更新包打包失败：{exc}", file=sys.stderr)
        return 1

    count = len(read_files_manifest(Path(args.files)))
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"更新包已生成：{zip_path}")
    print(f"  文件数：{count}")
    print(f"  zip 大小：{size_mb:.1f} MB")
    print(f"  SHA256：{sha256_of(zip_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
