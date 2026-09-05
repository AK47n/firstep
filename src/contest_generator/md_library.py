"""Markdown 资料库：素材库全量 .md 的检索与文件服务（给人看的资料库）。

素材库（sources/materials）里除了 PDF 还有 Markdown 手册（如立创地猛星
wiki 移植手册批次）——AI 侧有参考文件库作学习素材，人查资料时缺一个直通
入口。本模块是 webapp 两端点（/api/materials-md 清单 + /api/materials-md/
{rel_path} 全文）的全部逻辑：全量递归收集（批次 = 素材根下第一级目录）、
按名字串过滤、路径安全解析、大小上限。与 pdf_library 同构但独立属模块
（PDF 专属逻辑——页数 / 回收——不污染本域）。
"""

from __future__ import annotations

from pathlib import Path

from .entry_store import is_unsafe_path
from .reference_library import ReferenceError

# 单文件全文上限（照 codeview 先例）：素材手册单篇均 <300KB，
# 超限 = 拒绝预览（webapp 映射 400 中文），不静默截断。
MD_FILE_MAX_BYTES = 1024 * 1024


def list_markdowns(root: Path, name: str = "") -> list[dict]:
    """素材根下全量 Markdown 清单（递归，扩展名大小写不敏感）。

    每条目 {rel_path, name, batch, size_bytes, mtime}：rel_path 为相对素材根的
    POSIX 路径（服务端 :path 转换器直用，前端逐段编码）；mtime 为 UNIX epoch
    秒（前端格式化显示「修改时间」）；按 (batch, rel_path) 排序（批次分组内
    按路径排）。name 非空时子串过滤（大小写不敏感，命中 文件名 / 批次 /
    完整路径 任意一处）。素材根缺失 = 空清单（不炸——备份未落盘时前端照常
    展示"暂无"）。
    """
    if not root.is_dir():
        return []
    needle = name.strip().lower()
    entries: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        rel = path.relative_to(root).as_posix()
        if needle and needle not in rel.lower():
            continue
        st = path.stat()
        entries.append(
            {
                "rel_path": rel,
                "name": path.name,
                "batch": rel.split("/", 1)[0],
                "size_bytes": st.st_size,
                "mtime": int(st.st_mtime),
            }
        )
    entries.sort(key=lambda e: (e["batch"].lower(), e["rel_path"].lower()))
    return entries


def resolve_markdown(root: Path, rel_path: str) -> Path:
    """按 rel_path 定位素材 Markdown：路径安全校验 → 存在性校验。

    is_unsafe_path 不通过（绝对路径 / 盘符 / 反斜杠 / .. / 空段）或文件
    不存在 / 非 .md 抛 ReferenceError（webapp 映射 400，与参考文件库 /
    pdf_library 同通道，路径缺失不再裸 500）。
    """
    if is_unsafe_path(rel_path):
        raise ReferenceError(f"非法文件路径：{rel_path!r}")
    path = root / rel_path
    if not path.is_file() or path.suffix.lower() != ".md":
        raise ReferenceError(f"素材库中不存在 Markdown 文件：{rel_path}")
    return path


def read_markdown(root: Path, rel_path: str) -> dict:
    """按 rel_path 读取 Markdown 全文，返回 {rel_path, name, size_bytes, content}。

    resolve_markdown 先校验路径安全与存在性（非法 / 缺失 → ReferenceError）；
    超 MD_FILE_MAX_BYTES → ReferenceError（webapp 映射 400 中文，前端提示
    「文件过大」）；读取沿用仓库惯例 utf-8 errors="replace" + 换行归一化
    （\\r\\n → \\n），不静默截断内容。其余异常原样放行 = 真 bug → 500。
    """
    path = resolve_markdown(root, rel_path)
    size = path.stat().st_size
    if size > MD_FILE_MAX_BYTES:
        raise ReferenceError(
            f"文件过大（{size} 字节 > {MD_FILE_MAX_BYTES} 字节上限）：{rel_path}"
        )
    data = path.read_bytes()
    content = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return {
        "rel_path": rel_path,
        "name": path.name,
        "size_bytes": size,
        "content": content,
    }
