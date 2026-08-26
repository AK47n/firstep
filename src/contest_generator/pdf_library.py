"""PDF 资料库：素材库全量 PDF 的检索与文件服务（给人看的资料库）。

素材库（sources/materials）里散落着原理图 / 说明书 / 数据手册等 PDF——
AI 侧有参考文件库作学习素材，人查资料时缺一个直通入口。本模块是
webapp 两端点（/api/pdfs 清单 + /api/pdfs/{rel_path} 预览）的全部逻辑：
全量递归收集（批次 = 素材根下第一级目录）、按名字串过滤、路径安全解析。
"""

from __future__ import annotations

import time
from pathlib import Path

from .entry_store import is_unsafe_path
from .reference_library import ReferenceError


def list_pdfs(root: Path, name: str = "") -> list[dict]:
    """素材根下全量 PDF 清单（递归，扩展名大小写不敏感）。

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
        if not path.is_file() or path.suffix.lower() != ".pdf":
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


def resolve_pdf(root: Path, rel_path: str) -> Path:
    """按 rel_path 定位素材 PDF：路径安全校验 → 存在性校验。

    is_unsafe_path 不通过（绝对路径 / 盘符 / 反斜杠 / .. / 空段）或文件
    不存在 / 非 PDF 抛 ReferenceError（webapp 映射 400，与参考文件库
    同通道，路径缺失不再裸 500）。
    """
    if is_unsafe_path(rel_path):
        raise ReferenceError(f"非法文件路径：{rel_path!r}")
    path = root / rel_path
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ReferenceError(f"素材库中不存在 PDF 文件：{rel_path}")
    return path


def pdf_page_count(root: Path, rel_path: str) -> int:
    """按 rel_path 读取 PDF 页数（PyMuPDF 按需单文件，不预扫全库）。

    resolve_pdf 先校验路径安全与存在性（非法 / 不存在 → ReferenceError）；
    0 字节 / 损坏文件（fitz.FileDataError，含子类 EmptyFileError）→
    ReferenceError（webapp 映射 400，前端详情弹窗对该字段显示「无法读取」）。
    其余异常原样放行 = 真 bug → 500 大声失败（不把库内部缺陷伪装成
    「文件损坏」）。PyMuPDF 是声明依赖（pyproject pymupdf>=1.24），软导入作
    防御：ImportError = 服务器环境缺陷 → RuntimeError（500），与 extraction
    的静默降级语义区分——页数无处可降，缺陷该大声失败（spec 已注明）。
    """
    path = resolve_pdf(root, rel_path)
    try:
        import fitz  # type: ignore[import-untyped]  # PyMuPDF 无类型 stub
    except ImportError as exc:
        raise RuntimeError("服务器缺少 PyMuPDF，无法读取 PDF 页数") from exc
    doc = None
    try:
        doc = fitz.open(str(path))
        return doc.page_count
    except fitz.FileDataError as exc:
        raise ReferenceError(f"无法读取 PDF 页数（文件损坏或为空）：{rel_path}") from exc
    finally:
        if doc is not None:
            doc.close()  # 显式关闭：fitz 句柄留给 GC 会在 Windows 上锁文件（rename 撞 WinError 32）


def trash_pdf(root: Path, rel_path: str, trash_dir: Path) -> str:
    """将素材 PDF 移入回收目录（不真删），返回相对 trash 根的 POSIX 路径。

    目标 = trash_dir/<YYYY-MM-DD>/<rel_path 镜像>——保留批次层级，手动恢复直观
    （整段 mv 回 materials 即可）；同日同路径已回收过 → 文件名加 _1/_2 数字后缀
    （插在扩展名前，不覆盖旧件）；父目录自动创建。resolve_pdf 先校验（非法 /
    缺失 → ReferenceError，webapp 映射 400）；移动失败（回收根被文件占位 /
    不可写等）OSError 原样抛——webapp 映射 400，不伪装成功、不吞错误。
    """
    path = resolve_pdf(root, rel_path)
    date = time.strftime("%Y-%m-%d")
    rel = Path(rel_path)
    target = trash_dir / date / rel
    if target.exists():
        counter = 1
        while True:
            candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
            if not candidate.exists():
                target = candidate
                break
            counter += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    # 短重试：Windows 上文件可能被短锁（PyMuPDF 读页数句柄随 GC 延迟释放 /
    # 杀毒索引）——移动本身瞬时，重试 5×200ms 吞掉瞬态锁后仍失败才抛。
    for attempt in range(5):
        try:
            path.rename(target)
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.2)
    return target.relative_to(trash_dir).as_posix()
