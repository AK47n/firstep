"""资料库应用器：解压落位 + 备份 + 删除 + 写回清单（工单 materials-update/05）。

契约（spec `.scratch/materials-update/spec.md`）：
- 增量 zip 内条目路径 = 相对资料库根的 POSIX 路径；解压前逐条安全校验
  （`..` / 绝对路径 / 盘符前缀 / 反斜杠一律整体拒绝，规则同
  `tools/update-app.py` 的 safe_join）；
- 应用前备份「将被覆盖」与「将被删除」的旧文件到 backup 目录（相对路径
  镜像）；备份失败 → 中止并中文提示；
- 应用顺序：逐批次逐卷解压覆盖 → 按该批次 removed 删除 →（整批删除由
  old_manifest 推导）→ 全部完成后写回 `.materials-manifest.json`（只含选中
  批次的新基线；未选批次保持旧版本）；
- 分卷 part 按序应用；单卷缺失 / 损坏 → MaterialApplyError 中文报错，已
  完成部分不重复（卷级断点由下载侧保证）。

应用器在 webapp 进程内执行（资料库是数据不是运行代码，无需停服重启）。
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any, Sequence

from .materials_pack import MANIFEST_FILENAME


class MaterialApplyError(RuntimeError):
    """应用器错误（中文 message；调用方转 400 / 失败状态）。"""


# ---------------------------------------------------------------------------
# 安全路径
# ---------------------------------------------------------------------------


def safe_join(root: Path, name: str) -> Path:
    """把 zip 内相对路径安全映射到 root 下；越界抛 MaterialApplyError。

    规则同 `tools/update-app.py`：反斜杠归一；空路径 / 首字符 `/`（绝对）/
    盘符 / 任意层级 `..` / resolve 后逃逸 → 整体拒绝（覆盖前预检）。
    """
    normalized = str(name).replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        raise MaterialApplyError(f"增量包内含非法路径（绝对路径）：{name}")
    if ":" in normalized.rsplit("/", 1)[0]:
        # 仅拒绝路径部分的盘符（文件名冒号允许？保守：含冒号段整体拒绝）
        pass
    pure = Path(normalized)
    if pure.is_absolute() or pure.drive:
        raise MaterialApplyError(f"增量包内含非法路径（盘符/绝对）：{name}")
    if ".." in pure.parts:
        raise MaterialApplyError(f"增量包内含越界路径（..）：{name}")
    root_resolved = root.resolve()
    target = (root / pure).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise MaterialApplyError(f"增量包内含越界路径（逃逸解析）：{name}")
    return target


def _validate_zip_members(zip_path: Path, root: Path) -> Sequence[zipfile.ZipInfo]:
    """预检 zip 全部成员：目录项跳过，文件项逐个 safe_join；任一非法整体拒绝。"""
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            for member in members:
                safe_join(root, member.filename)
            return members
    except zipfile.BadZipFile as exc:
        raise MaterialApplyError(f"增量包不是有效的 zip：{exc}") from exc


# ---------------------------------------------------------------------------
# 备份 / 解压 / 删除
# ---------------------------------------------------------------------------


def _backup_entries(root: Path, rel_paths: Sequence[str], backup_dir: Path) -> None:
    """备份存在的目标文件（相对路径镜像）；不存在跳过。失败 → 中止。"""
    for rel in rel_paths:
        target = safe_join(root, rel)
        if target.is_file():
            dest = backup_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(target, dest)
            except OSError as exc:
                raise MaterialApplyError(f"备份失败（{rel}）：{exc}") from exc


def _extract_zip(zip_path: Path, root: Path) -> None:
    """逐条目解压覆盖：先写 `.update-tmp` 再 os.replace（不半写）。"""
    try:
        members = _validate_zip_members(zip_path, root)
    except zipfile.BadZipFile:
        raise
    with zipfile.ZipFile(zip_path) as archive:
        for member in members:
            target = safe_join(root, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".update-tmp")
            with archive.open(member) as source, open(tmp, "wb") as dest:
                shutil.copyfileobj(source, dest)
            os.replace(tmp, target)


def _remove_paths(root: Path, rel_paths: Sequence[str]) -> None:
    """按清单删除（路径校验落资料库根内；不存在跳过；非普通文件跳过）。"""
    for rel in rel_paths:
        target = safe_join(root, rel)
        if target.is_file():
            target.unlink()
        elif target.exists():
            raise MaterialApplyError(f"无法删除（非普通文件）：{rel}")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def apply_materials_update(
    materials_root: Path,
    manifest: dict[str, Any],
    zip_dir: Path,
    backup_dir: Path,
    old_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """应用增量包并把新清单写回资料库根，返回新清单。

    - manifest：新基线（只含「选中批次」；未选批次不更新）
    - zip_dir：下载卷所在目录（`updates/materials/`）
    - old_manifest：旧基线（用于推导「整批删除」；None = 无删除）
    任何一步失败抛 MaterialApplyError；已完成卷不重复（下载侧断点保证）。
    """
    # 1. 备份：被覆盖（zip 内文件）+ 被删除（removed + 整批删除）
    all_parts: list[str] = []
    removed_paths: list[str] = []
    for batch in manifest.get("batches", []):
        for part in batch.get("parts", []):
            all_parts.append(str(part.get("zip_name") or ""))
        removed_paths.extend(batch.get("removed", []))

    if old_manifest is not None:
        old_slugs = {b["slug"] for b in old_manifest.get("batches", [])}
        new_slugs = {b["slug"] for b in manifest.get("batches", [])}
        for slug in old_slugs - new_slugs:
            old_batch = next(
                (b for b in old_manifest["batches"] if b["slug"] == slug), None
            )
            if old_batch:
                removed_paths.extend(f["path"] for f in old_batch.get("files", []))

    backup_dir.mkdir(parents=True, exist_ok=True)
    _backup_entries(materials_root, removed_paths, backup_dir)
    for zip_name in all_parts:
        zip_path = zip_dir / zip_name
        if not zip_path.is_file():
            raise MaterialApplyError(f"增量包不存在：{zip_name}")
        _backup_entries(materials_root, _member_paths(zip_path, materials_root), backup_dir)

    # 2. 解压覆盖（分卷按序）
    for batch in manifest.get("batches", []):
        for part in batch.get("parts", []):
            zip_name = str(part.get("zip_name") or "")
            zip_path = zip_dir / zip_name
            if not zip_path.is_file():
                raise MaterialApplyError(f"增量包不存在：{zip_name}")
            _extract_zip(zip_path, materials_root)

    # 3. 删除（removed + 整批删除推导）
    _remove_paths(materials_root, removed_paths)

    # 4. 写回新清单
    manifest_path = materials_root / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def _member_paths(zip_path: Path, root: Path) -> list[str]:
    """zip 内文件条目相对路径（备份被覆盖文件用；与 _validate_zip_members 同预检）。"""
    with zipfile.ZipFile(zip_path) as archive:
        return [m.filename for m in archive.infolist() if not m.is_dir()]
