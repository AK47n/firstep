"""代码查看器 / 编辑器域模块（工单 code-viewer/01-03 + code-viewer-editor/01）：
任意本地目录的浏览、搜索与文本保存。

设计立场（与母版树端点同一安全收窄模式，见 read_master_tree_file 先例）：
打开的根目录只来自最近生成记录 output_dir 或服务端原生文件夹对话框
（/api/pick-directory）——本模块不重复校验该来源，但 API 以「显式根 +
相对路径安全判定」收窄，绝不放开任意文件系统访问。读面孔隙（浏览/搜索）
零写侧；唯一写面 = save_code_file（工单 code-viewer-editor/01：编辑器
保存，路径安全同源 + 冲突检测 409，不静默覆盖外部修改）。业务错误统一
CodeViewError → 400 中文、CodeViewConflictError → 409 中文（errors.py
登记；未登记异常 = 真 bug → 500 的仓库不变量不变）。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .clex import quoted_include_lines, top_level_defines, top_level_functions
from .entry_store import is_unsafe_path
from .treewalk import iter_project_files

# 目录打开条目上限：防病态目录（如整盘 / 大仓库）把树渲染与往返压垮
CODE_TREE_MAX_ENTRIES = 5000
# 文件预览 / 搜索上限：与母版树 TREE_FILE_MAX_PREVIEW_BYTES 同量级
CODE_FILE_MAX_BYTES = 1024 * 1024
# 跨文件搜索命中上限：到达即截断（truncated: true），防结果集压垮渲染
CODE_SEARCH_MAX_HITS = 200
# 命中行文本裁剪：空白压缩后以命中点为中心取至多约 120 字符（两侧各约 60）
_CODE_SEARCH_SNIPPET_CHARS = 120
_CODE_SEARCH_SNIPPET_WING = 60
# 图片 raw 端点（工单 code-viewer-md-preview/02）：md 预览本地图片——
# 扩展名白名单 + 8MB 上限 + media_type 手写映射（不依赖 mimetypes 平台差异）
CODE_RAW_MAX_MB = 8
CODE_RAW_MAX_BYTES = CODE_RAW_MAX_MB * 1024 * 1024
CODE_RAW_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
}


class CodeViewError(ValueError):
    """代码查看器业务失败：目录 / 路径 / 文件问题，→ 400 中文。"""


class CodeViewConflictError(CodeViewError):
    """保存冲突（工单 code-viewer-editor/01）：磁盘文件已被外部修改，
    base_mtime_ns 与磁盘不一致 → 409 中文。

    继承 CodeViewError 但登记表项**置于 400 大元组之前**（errors.py）：
    error_entry 按序 isinstance 匹配，若 409 表项排后会被含 CodeViewError
    的 400 元组先吞成 400——顺序即语义，注释说明在登记处。
    """


def list_code_tree(root: Path) -> list[dict[str, Any]]:
    """根目录扁平文件清单（工单 code-viewer/01）：统一噪音跳过后每条
    {path, size_bytes}（path 为相对 root 的正斜杠，与母版树同口径）。

    目录不存在 / 不是目录 → 400 中文；条目超过 CODE_TREE_MAX_ENTRIES →
    400 中文（防病态目录）；排序确定性 = treewalk iter_project_files 的
    全路径排序（sorted rglob）。
    """
    if not root.is_dir():
        raise CodeViewError(f"目录不存在：{root}")
    entries: list[dict[str, Any]] = []
    for path in iter_project_files(root):
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
            }
        )
        if len(entries) > CODE_TREE_MAX_ENTRIES:
            raise CodeViewError(
                f"目录文件过多（超过 {CODE_TREE_MAX_ENTRIES} 个）：{root}"
            )
    return entries


def _resolve_in_root(root: Path, rel_path: str) -> Path:
    r"""安全前置（read_code_file / read_code_file_bytes 共用，工单
    code-viewer-md-preview/02 评审整改：消除 7 行同构）：root 必须是目录、
    rel_path 过 is_unsafe_path 单源（首字符 `/`、`:`、`\`、任意层级 `..` 与
    空段）、resolve 后必须落在 root 内——任一不满足抛 CodeViewError
    （400 中文）。返回已 resolve 的候选路径（调用方再验 is_file / 大小 / 内容）；
    判定全部在盘访问之前，安全策略只此一处。
    """
    if not root.is_dir():
        raise CodeViewError(f"目录不存在：{root}")
    if is_unsafe_path(rel_path):
        raise CodeViewError(f"非法路径：{rel_path}")
    candidate = (root / rel_path).resolve()
    try:
        candidate.relative_to(root.resolve())  # 父解析必须是根目录内
    except ValueError:
        raise CodeViewError(f"非法路径：{rel_path}") from None
    return candidate


def read_code_file(root: Path, rel_path: str) -> dict[str, Any]:
    """根目录内文件全文（只读预览）：三重约束与母版树 read_master_tree_file
    同安全立场（判定在盘访问之前）——路径安全（**调用 entry_store.is_unsafe_path
    单源**：首字符 `/`、`:`（NTFS ADS）、`\\`、任意层级 `..` 与空段 `a//b`，
    另有 resolve 后必须在 root 内的兜底判定）、NUL 字节二进制拒绝、
    超 CODE_FILE_MAX_BYTES 拒绝——三类均 400 中文 CodeViewError；文件缺失
    单独报错。读取沿用仓库惯例 utf-8 errors="replace" + 换行归一化
    （与 read_master_tree_file 同读法；二进制判定这边对预览全量检——预览
    正确性优先，与搜索侧的头 512 字节探测口径见 search_code_files）。

    返回 {path, size_bytes, content, outline, mtime_ns, utf8}；outline 仅
    .c/.h 有值（工单 code-viewer/03：函数 / 顶层宏 / include 清单，非 C 文件
    为 null）；mtime_ns = st_mtime_ns **以字符串返回**（工单
    code-viewer-editor/01：ns 值 ≈1.7e18 超过 JS Number.MAX_SAFE_INTEGER
    ≈9e15，JSON number 往返丢精度——字符串精确传输，前端原样回传）；
    utf8 = 严格解码成功与否（非 UTF-8 文本前端标只读，防止保存损坏——
    二进制已在 NUL 检查前拒绝，此处只判文本编码）。
    """
    candidate = _resolve_in_root(root, rel_path)
    if not candidate.is_file():
        raise CodeViewError(f"文件不存在：{rel_path}")
    size = candidate.stat().st_size
    if size > CODE_FILE_MAX_BYTES:
        _raise_oversize(rel_path)
    data = candidate.read_bytes()
    if b"\x00" in data:
        raise CodeViewError(f"二进制文件不可预览：{rel_path}")
    try:
        content = data.decode("utf-8")
        is_utf8 = True
    except UnicodeDecodeError:
        content = data.decode("utf-8", errors="replace")
        is_utf8 = False
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    return {
        "path": rel_path,
        "size_bytes": size,
        "content": content,
        "outline": _outline_for(content) if _is_c_source(rel_path) else None,
        "mtime_ns": str(candidate.stat().st_mtime_ns),
        "utf8": is_utf8,
    }


def _raise_oversize(rel_path: str) -> None:
    """超限 400 中文单源（read_code_file / save_code_file 共用，工单
    code-viewer-editor/01 评审整改：消除 7 行同构的 limit_mb 计算）。"""
    limit_mb = CODE_FILE_MAX_BYTES // (1024 * 1024)
    raise CodeViewError(f"文件超过预览上限（{limit_mb}MB）：{rel_path}")


def _is_c_source(rel_path: str) -> bool:
    """是否 C 源码 / 头文件（大纲只在 .c/.h 提供；大小写宽容如 .H）。"""
    lower = rel_path.lower()
    return lower.endswith(".c") or lower.endswith(".h")


def code_raw_media_type(rel_path: str) -> str:
    """图片 media_type（md 预览 raw 端点，工单 code-viewer-md-preview/02）——
    扩展名手写映射（小写宽容，不依赖 mimetypes 的平台差异）；白名单外 →
    400 中文（CodeViewError）。"""
    ext = Path(rel_path).suffix.lower()
    media = CODE_RAW_MEDIA_TYPES.get(ext)
    if media is None:
        raise CodeViewError(
            f"不支持的图片类型：{rel_path}（仅支持 png/jpg/jpeg/gif/webp/bmp/ico/svg）"
        )
    return media


def read_code_file_bytes(root: Path, rel_path: str) -> bytes:
    """目录内图片字节（md 预览 raw 端点，工单 code-viewer-md-preview/02）。

    安全判定与 read_code_file 同一组（_resolve_in_root 单源：is_unsafe_path
    + resolve 在 root 内 + is_file）；扩展名白名单在**读盘之前**（非图片不打开
    文件）；超 CODE_RAW_MAX_BYTES → 400 中文。图片本身是二进制，不做 NUL
    拒绝（与 read_code_file 的文本预览口径不同）。返回原始字节，media_type
    由 code_raw_media_type 单源提供。
    """
    candidate = _resolve_in_root(root, rel_path)
    code_raw_media_type(rel_path)              # 白名单先行：非图片不读盘
    if not candidate.is_file():
        raise CodeViewError(f"文件不存在：{rel_path}")
    size = candidate.stat().st_size
    if size > CODE_RAW_MAX_BYTES:
        raise CodeViewError(f"图片超过预览上限（{CODE_RAW_MAX_MB}MB）：{rel_path}")
    return candidate.read_bytes()


def _outline_for(content: str) -> list[dict[str, Any]]:
    """大纲载荷（工单 code-viewer/03）：按行号归并的
    [{kind: function|define|include, name, line}]——函数（top_level_functions）
    + 顶层宏（top_level_defines）+ 引号 include（quoted_include_lines），
    均为 1 基源行号，前端点击按行跳转。clex 单源，此处只做装配。"""
    items: list[tuple[int, str, str]] = []
    for fn in top_level_functions(content):
        items.append((fn["line"], "function", fn["name"]))
    for name, (_value, line) in top_level_defines(content).items():
        items.append((line, "define", name))
    for name, line in quoted_include_lines(content):
        items.append((line, "include", name))
    return [
        {"kind": kind, "name": name, "line": line}
        for line, kind, name in sorted(items)
    ]


def search_code_files(root: Path, query: str) -> dict[str, Any]:
    """跨文件子串搜索（工单 code-viewer/02）：大小写不敏感（中文 / 全角不受
    lower 影响），逐文件逐行匹配；跳过噪音（treewalk 同口径）/ NUL 字节
    二进制（**读文件头 512 字节探测**——spec 决策，多文件扫描不整读二进制
    文件；read_code_file 预览侧对 ≤1MB 单文件仍全量检，两侧口径按需取舍）/
    超 CODE_FILE_MAX_BYTES 文件；命中到 CODE_SEARCH_MAX_HITS 即截断返回
    truncated: true。

    返回 {hits: [{path, line, text}], truncated, files_scanned}——path 为
    相对 root 的正斜杠、line 为 1 基行号、text 为空白压缩后以命中点为中心的
    窗口裁剪；files_scanned = 已扫描文件数（含被跳过的，供前端展示进度）。
    空 q / 目录不存在 → 400 中文；只读搜索，零写侧。
    """
    q = query.strip()
    if not q:
        raise CodeViewError("搜索关键词不能为空")
    if not root.is_dir():
        raise CodeViewError(f"目录不存在：{root}")
    needle = q.lower()
    hits: list[dict[str, Any]] = []
    scanned = 0
    for path in iter_project_files(root):
        scanned += 1
        if path.stat().st_size > CODE_FILE_MAX_BYTES:
            continue
        with path.open("rb") as fh:
            head = fh.read(512)
        if b"\x00" in head:
            continue  # 二进制：头 512 字节 NUL 探测（spec 决策，读头即可）
        text = path.read_bytes().decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if needle in line.lower():
                hits.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "line": lineno,
                        "text": _snippet(line, needle),
                    }
                )
                if len(hits) >= CODE_SEARCH_MAX_HITS:
                    return {"hits": hits, "truncated": True, "files_scanned": scanned}
    return {"hits": hits, "truncated": False, "files_scanned": scanned}


def _snippet(line: str, needle: str) -> str:
    """命中行文本裁剪：空白压缩后以命中点为中心取至多约 120 字符。

    长行 / 长空白不撑爆行内布局；窗口外以「…」标示（长度恒 ≤
    _CODE_SEARCH_SNIPPET_CHARS + 2）。
    """
    flat = re.sub(r"\s+", " ", line.strip())
    if len(flat) <= _CODE_SEARCH_SNIPPET_CHARS:
        return flat
    idx = flat.lower().find(needle)
    if idx < 0:  # 理论不达（命中行必含 needle），保底防退化
        return flat[:_CODE_SEARCH_SNIPPET_CHARS]
    start = max(0, idx - _CODE_SEARCH_SNIPPET_WING)
    end = min(len(flat), idx + len(needle) + _CODE_SEARCH_SNIPPET_WING)
    return (
        ("…" if start > 0 else "")
        + flat[start:end]
        + ("…" if end < len(flat) else "")
    )


def save_code_file(root: Path, rel_path: str, content: str, base_mtime_ns: int | str) -> dict[str, Any]:
    """根目录内文本文件写盘（工单 code-viewer-editor/01——「代码」tab 编辑器
    直接保存的唯一写面）。

    安全判定与 read_code_file 同源（_resolve_in_root 单源：is_unsafe_path +
    resolve 在 root 内；文件必须已存在——不新建文件，树操作不在本轮）。
    写前约束（按序）：content 必须是 str（否则 400）→ **磁盘原文件必须是
    UTF-8**（非 UTF-8 拒绝——errors=replace 已丢码点，覆盖 = 静默损坏）→
    UTF-8 编码后不得超 CODE_FILE_MAX_BYTES（与预览上限同口径；先于冲突判
    定——spec 顺序 超限 → 冲突）→ **冲突检测**：磁盘现行 st_mtime_ns 必须
    等于 base_mtime_ns（打开时的读取值——外部工具 / 任务写盘 / 深化修改
    都会改变它），不一致 → CodeViewConflictError（409 中文，不静默覆盖
    别人的写入）。base_mtime_ns 接受 int 或数字字符串（JSON 传输精度：
    ns 值超 JS 安全整数，前端按字符串回传；非数字 → 400）。写入 = 同目录
    临时文件 + os.replace 原子替换（UTF-8、换行统一 \\n，与读取归一化口径
    一致）；OSError（权限 / 磁盘满 / 占用）由 errors.py 既有 400
    os_error_message 表项接住。

    返回 {path, size_bytes, mtime_ns, outline}——outline 服务端重算
    （.c/.h；前端保存后大纲刷新用，省一次 GET）；mtime_ns = 写盘后新值
    （**字符串**，前端更新基准，下次保存带它）。
    """
    if not isinstance(content, str):
        raise CodeViewError("保存内容必须是文本")
    if isinstance(base_mtime_ns, str):
        try:
            base_mtime_ns = int(base_mtime_ns)
        except ValueError:
            raise CodeViewError("缺少文件修改时间（base_mtime_ns）") from None
    if not isinstance(base_mtime_ns, int):
        raise CodeViewError("缺少文件修改时间（base_mtime_ns）")
    candidate = _resolve_in_root(root, rel_path)
    if not candidate.is_file():
        raise CodeViewError(f"文件不存在：{rel_path}")
    # 非 UTF-8 守卫（工单 code-viewer-editor/01 评审整改）：前端 utf8 标志的
    # 后端兜底——原文严格解码失败的文件若以 UTF-8 覆盖，errors=replace 已丢
    # 码点、字节编码被改写 = 静默损坏；保存统一 UTF-8，非 UTF-8 一律拒绝。
    try:
        candidate.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise CodeViewError(
            f"{rel_path} 不是 UTF-8 编码，为免损坏请用外部编辑器保存"
        ) from None
    content_norm = content.replace("\r\n", "\n").replace("\r", "\n")
    encoded = content_norm.encode("utf-8")
    if len(encoded) > CODE_FILE_MAX_BYTES:
        _raise_oversize(rel_path)
    if candidate.stat().st_mtime_ns != base_mtime_ns:
        raise CodeViewConflictError(
            f"磁盘上的 {rel_path} 已被外部修改（任务 / 深化写盘或外部编辑器），"
            "为免覆盖请选择覆盖写盘或重新加载"
        )
    tmp = candidate.with_name(candidate.name + f".tmp-{os.getpid()}")
    try:
        tmp.write_bytes(encoded)  # 明确字节写入：\n 原样落盘（与读取归一化同口径）
        os.replace(tmp, candidate)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    mtime_ns = candidate.stat().st_mtime_ns
    return {
        "path": rel_path,
        "size_bytes": candidate.stat().st_size,
        "mtime_ns": str(mtime_ns),
        "outline": _outline_for(content_norm) if _is_c_source(rel_path) else None,
    }
