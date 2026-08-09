"""上传暂存域：webkitdirectory 整夹上传 → staged/ 暂存目录（工单 02 落域）。

「选择文件夹」上传的语义唯一出处：暂存位置推导（staged_root）、路径穿越
拒绝、目录名清洗、噪音跳过、单次总量上限——此前全部内联在 webapp 路由里
（HTTP 外不可测，且穿越检查与 entry_store.is_unsafe_path 规则集分歧）。
本模块收拢后路由只收参数转调，校验吃既有单源：

- 穿越拒绝 = entry_store.is_unsafe_path（相对路径 / 无 .. / 无空段 / 无
  绝对路径与盘符）——行为变化：空段（a//b）从放行变拒绝，浏览器畸形路径
  大声失败
- 噪音跳过 = 任意深度 ".git"（版本库不进母版素材）+ treewalk.
  skip_project_noise（Debug/Release/Listings/Objects，顶层或 Keil 输出
  任意层级）——与扫描侧 iter_project_files 同一套跳过规则；注意契约：
  skip_project_noise 收项目根相对路径，上传路径首段是选中的文件夹名，
  必须剥除后传

与 master.py 蒸馏预览的 mkdtemp 暂存（函数内自生自灭）区分命名：本模块
是用户上传的落盘点（扫描后即用、不自动清理），staged 目录在母版库同级。

叶子模块：依赖 entry_store + treewalk，零业务库。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .entry_store import is_unsafe_path
from .treewalk import skip_project_noise

# 单次上传总量上限（防误选大目录）：超限报错文案 = "文件夹过大（超过 512MB）…"
STAGE_MAX_TOTAL_BYTES = 512 * 1024 * 1024


class StageError(ValueError):
    """暂存失败（穿越 / 超限 / 空清单），message = 路由原 HTTPException 文案逐字。"""


def staged_root(masters_dir: Path) -> Path:
    """暂存目录位置纯推导：母版库同级（masters_dir.parent / "staged"）。"""
    return masters_dir.parent / "staged"


def stage_project_files(
    masters_dir: Path, files: Iterable[tuple[str, bytes]]
) -> Path:
    """把整夹上传的文件清单落到 staged/<原文件夹名>，返回暂存目录路径。

    files = [(文件名 = 文件夹内相对路径（webkitRelativePath，'/' 分隔），内容)]，
    目录名保留原名（重名覆盖写）、首段按白名单清洗（isalnum + `-_. `，空回退
    "upload"，现状逐字）；穿越（.. / 绝对路径 / 盘符 / 空段）拒绝、噪音
    （.git 任意深度 + 构建产物目录）跳过、总量超 STAGE_MAX_TOTAL_BYTES 拒绝；
    空清单报错。每份内容逐条落盘（跳过噪音不读不计数），任何拒绝都是
    StageError——文案 = 原路由 HTTPException 逐字。
    """
    staged = staged_root(masters_dir)
    name = ""
    total = 0
    for rel, content in files:
        rel = rel.replace("\\", "/")  # 浏览器可能回反斜杠，先归一
        if is_unsafe_path(rel):
            raise StageError(f"非法文件路径：{rel!r}（浏览器应传文件夹内相对路径）")
        parts = rel.split("/")
        if not name:
            name = "".join(
                c if c.isalnum() or c in "-_. " else "_" for c in parts[0]
            ).strip() or "upload"
        # 噪音跳过 = .git 任意深度 + 项目根相对路径规则（首段文件夹名剥除后传）
        if ".git" in parts or skip_project_noise("/".join(parts[1:])):
            continue  # 版本库 / 构建产物不进母版素材（扫描侧同样忽略）
        total += len(content)
        if total > STAGE_MAX_TOTAL_BYTES:
            raise StageError("文件夹过大（超过 512MB），请只选择工程源码目录")
        dest = staged.joinpath(*parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    if not name:
        raise StageError("没有收到任何文件（选择文件夹后浏览器会逐文件上传）")
    return staged / name
