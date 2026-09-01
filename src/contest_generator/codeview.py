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
from typing import Any, Iterator

from .clex import quoted_include_lines, top_level_defines, top_level_functions
from .entry_store import is_unsafe_path
from .treewalk import iter_project_files, skip_project_noise

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


def _iter_project_dirs(root: Path) -> Iterator[Path]:
    """遍历工程目录下的**目录**（绝对路径、按路径排序，确定性），跳过统一噪音。

    与 iter_project_files 同规则（skip_project_noise 单源，原地剪枝不下钻
    噪音目录）；含**空目录**——树操作（工单 code-tree-ops/01）需要展示与
    删除空目录，而纯文件清单（iter_project_files）看不到它们。
    """
    for dirpath, dirnames, _ in os.walk(root):
        top = Path(dirpath)
        dirnames[:] = [
            d for d in sorted(dirnames)
            if not skip_project_noise((top / d).relative_to(root).as_posix())
        ]
        if top != root:
            yield top


def list_code_tree(root: Path) -> list[dict[str, Any]]:
    """根目录文件 + 目录清单（工单 code-viewer/01 + code-tree-ops/01 +
    code-ide-flow/02）：统一噪音跳过后每条文件 {path, size_bytes, mtime_ns}、
    每条目录 {path, is_dir: True}（path 为相对 root 的正斜杠，与母版树同口径）。

    目录条目 = 非噪音目录（含空目录——树 UI 需展示/删除空目录，
    code-tree-ops/01）；与文件条目合并后按 path 排序。目录不存在 / 不是
    目录 → 400 中文；条目（文件+目录）超过 CODE_TREE_MAX_ENTRIES → 400
    中文（防病态目录）。mtime_ns = st_mtime_ns **以字符串返回**（JSON 传输
    精度，与 /api/code/file、/api/code/save 同口径——供 code-ide-flow/02
    磁盘基线对比判定外部/AI 写盘）。
    """
    if not root.is_dir():
        raise CodeViewError(f"目录不存在：{root}")
    entries: list[dict[str, Any]] = [
        {"path": d.relative_to(root).as_posix(), "is_dir": True}
        for d in _iter_project_dirs(root)
    ]
    for path in iter_project_files(root):
        st = path.stat()  # 一次 stat 同时喂 size 与 mtime（避免两次系统调用）
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": st.st_size,
                "mtime_ns": str(st.st_mtime_ns),
            }
        )
    entries.sort(key=lambda e: e["path"])
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


# ---------------------------------------------------------------------------
# AI diff 应用（工单 code-ide-ai/02）：/api/code/apply-diff——预览（只算不写）
# 与写模式（409 冲突语义与 save 同口径）。hunk 契约见 fx/ai-diff.js（AI 输出
# 结构化 diff，与 main_diff 同构：{line, title, lines:[{kind:"ctx"|"del"|"add",
# text}]}）。
# ---------------------------------------------------------------------------

_AI_DIFF_KINDS = ("ctx", "del", "add")


def _validate_ai_hunks(hunks: object) -> list[dict[str, Any]]:
    """AI diff hunk 结构校验（对齐前端 parseAiDiff 契约；后端二次校验——
    LLM 输出不可信，结构/枚举/锚点任一不符 → CodeViewError 400 中文）。
    返回归一化 hunks（line 展示语义保留；应用匹配以 old 段为准）。"""
    if not isinstance(hunks, list) or not hunks:
        raise CodeViewError("缺少结构化的 hunk 列表（AI 输出不含改动或无缝隙）")
    norm: list[dict[str, Any]] = []
    for i, h in enumerate(hunks):
        if not isinstance(h, dict):
            raise CodeViewError(f"第 {i + 1} 个 hunk 不是对象")
        line = h.get("line")
        if not isinstance(line, int) or line < 1:
            raise CodeViewError(f"第 {i + 1} 个 hunk 行号非法")
        title = h.get("title") or ""
        if not isinstance(title, str):
            raise CodeViewError(f"第 {i + 1} 个 hunk 标题非法")
        lines = h.get("lines")
        if not isinstance(lines, list) or not lines:
            raise CodeViewError(f"第 {i + 1} 个 hunk 缺少行清单")
        norm_lines: list[dict[str, str]] = []
        has_anchor = False
        for ln in lines:
            if not isinstance(ln, dict):
                raise CodeViewError(f"第 {i + 1} 个 hunk 的行不是对象")
            kind = ln.get("kind")
            text = ln.get("text")
            if kind not in _AI_DIFF_KINDS or not isinstance(text, str):
                raise CodeViewError(f"第 {i + 1} 个 hunk 的行结构非法")
            if kind != "add":
                has_anchor = True
            norm_lines.append({"kind": kind, "text": text})
        if not has_anchor:
            raise CodeViewError(
                f"第 {i + 1} 个 hunk 缺少匹配锚点行（需要 ctx/del 行）"
            )
        norm.append({"line": line, "title": title, "lines": norm_lines})
    return norm


def _find_hunk_line(lines: list[str], old: list[str], from_idx: int) -> int | None:
    """在 lines[from_idx:] 顺序精确匹配 old 段（hunk 的 ctx+del 行序列）；
    命中返回起始下标，未命中 None。匹配原语 = 整行相等（不做归一化——用户
    确认路径应显式失败提示重预览，不静默魔改）。"""
    n = len(old)
    if n == 0:
        return None
    limit = len(lines) - n + 1
    for i in range(from_idx, limit):
        if lines[i : i + n] == old:
            return i
    return None


def _apply_hunks_to_lines(lines: list[str], hunks: list[dict[str, Any]]) -> list[str]:
    """hunks（升序）顺序应用：每 hunk 先在 from_idx 后精确匹配 old 段
    （ctx+del），命中 → 保留 hunk 前磁盘行 + 输出非 del 行（ctx 原样 + add
    插入）；未命中 → CodeViewError 400（磁盘已变或与基线不一致）。"""
    out: list[str] = []
    from_idx = 0
    for i, h in enumerate(hunks):
        old = [ln["text"] for ln in h["lines"] if ln["kind"] != "add"]
        pos = _find_hunk_line(lines, old, from_idx)
        if pos is None:
            raise CodeViewError(
                f"第 {i + 1} 个 hunk 在磁盘文件中未匹配（文件已被修改或 AI 输出"
                "与基线不一致）——请重新预览后再应用"
            )
        out.extend(lines[from_idx:pos])
        out.extend(ln["text"] for ln in h["lines"] if ln["kind"] != "del")
        from_idx = pos + len(old)
    out.extend(lines[from_idx:])
    return out


def apply_code_diff(
    root: Path,
    rel_path: str,
    hunks: object,
    base_mtime_ns: int | str | None = None,
    preview: bool = False,
) -> dict[str, Any]:
    """AI diff 应用（工单 code-ide-ai/02）：{hunks} 应用 → 预览只算不写 /
    写盘（409 与 save_code_file 同口径）。

    安全判定与读面同源（_resolve_in_root 单源）；写前约束对齐 save_code_file：
    文件须存在、UTF-8 守卫、超限拒绝、base_mtime_ns 冲突 409（仅供写模式——
    preview 无需 mtime，只算不写）。应用以 old 段（ctx+del）整行精确匹配为
    锚点（AI 行号 line 仅展示语义，不参与匹配——LLM 行号经常不准，old 段
    匹配免疫该失败面）。写入 = 同目录临时文件 + os.replace 原子替换。

    preview=True 返回 {new_content, stats:{additions, deletions, hunks}}；
    写模式返回 {saved: true, path, size_bytes, mtime_ns, stats}。
    """
    norm_hunks = _validate_ai_hunks(hunks)
    candidate = _resolve_in_root(root, rel_path)
    if not candidate.is_file():
        raise CodeViewError(f"文件不存在：{rel_path}")
    try:
        raw = candidate.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise CodeViewError(
            f"{rel_path} 不是 UTF-8 编码，为免损坏请用外部编辑器保存"
        ) from None
    # 读取归一化与 save 写口径一致（CRLF/CR → LF），确保 old 段匹配不受
    # 行尾差异干扰。
    content = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = content.split("\n")
    new_lines = _apply_hunks_to_lines(lines, norm_hunks)
    new_content = "\n".join(new_lines)
    stats = {
        "additions": sum(
            1 for h in norm_hunks for ln in h["lines"] if ln["kind"] == "add"
        ),
        "deletions": sum(
            1 for h in norm_hunks for ln in h["lines"] if ln["kind"] == "del"
        ),
        "hunks": len(norm_hunks),
    }
    if preview:
        return {"new_content": new_content, "stats": stats}
    encoded = new_content.encode("utf-8")
    if len(encoded) > CODE_FILE_MAX_BYTES:
        _raise_oversize(rel_path)
    base = base_mtime_ns
    if isinstance(base, str):
        try:
            base = int(base)
        except ValueError:
            base = None
    if not isinstance(base, int):
        raise CodeViewError("缺少文件修改时间（base_mtime_ns）")
    if candidate.stat().st_mtime_ns != base:
        raise CodeViewConflictError(
            f"磁盘上的 {rel_path} 已被外部修改（任务 / 深化写盘或外部编辑器），"
            "为免覆盖请重新加载后再应用"
        )
    tmp = candidate.with_name(candidate.name + f".tmp-{os.getpid()}")
    try:
        tmp.write_bytes(encoded)
        os.replace(tmp, candidate)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    mtime_ns = candidate.stat().st_mtime_ns
    return {
        "saved": True,
        "path": rel_path,
        "size_bytes": candidate.stat().st_size,
        "mtime_ns": str(mtime_ns),
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# 树操作（工单 code-tree-ops/01）：新建文件/目录、重命名、删除——最小增删改
# 闭环。全部复用 _resolve_in_root 单源（is_unsafe_path + resolve 在 root 内，
# 判定在盘操作之前）；业务失败统一 CodeViewError → 400 中文（errors.py 既有
# 表项），OSError（权限 / 占用 / 磁盘满）由 errors.py os_error_message 接住。
# ---------------------------------------------------------------------------

# 单段名称非法字符（Windows 保留集；路径分隔符靠 is_unsafe_path 拦，这里
# 防「多段名」绕过 rename 语义——new_name 只允许单段，不做跨目录移动）。
_CODE_NAME_ILLEGAL = set('/\\:*?"<>|')


def _validate_entry_name(name: str) -> None:
    """单段条目名称校验（tree 操作共用单源）：非空、非纯空白、首尾无空白、
    ≤120 字符、不为 `.` / `..`、不含 Windows 保留字符 → 违规 400 中文。"""
    if (
        not isinstance(name, str)
        or not name
        or name.strip() != name
        or len(name) > 120
        or name in (".", "..")
        or (_CODE_NAME_ILLEGAL & set(name))
    ):
        raise CodeViewError(
            "名称不合法（非空、首尾无空格、≤120 字符、不能是 . 或 ..、不含 / \\ : * ? \" < > |）"
        )


def create_code_entry(root: Path, kind: str, rel_path: str) -> dict[str, Any]:
    """根目录内新建空文件 / 目录（工单 code-tree-ops/01）。

    安全判定与 read_code_file 同源（_resolve_in_root：is_unsafe_path +
    resolve 在 root 内，前置在盘操作之前）。kind ∈ {"file", "dir"}——其余
    400 中文；目标已存在 → 400 中文「已存在」（**不覆盖**，杜绝误操作）；
    父级目录随 mkdirs 一次建出（前端「当前目录 + 名称」拼相对路径，可含
    子目录，如 src/drivers/）。file = O_EXCL 原子创建空文件（open
    O_CREAT|O_EXCL，不存在才成功——无「判后覆盖隙间同名」TOCTOU 窗，
    隙间同名 → 400「已存在」；空文件即终态，无半成品）；成功返回 {path,
    size_bytes: 0, mtime_ns: 字符串}——mtime 即打开 tab 的保存基准（创建后
    立即编辑、Ctrl+S 保存，基准一致无 409）；dir = os.mkdir（父级已
    mkdirs），成功返回 {path}。
    """
    if kind not in ("file", "dir"):
        raise CodeViewError("新建类型必须是 file 或 dir")
    candidate = _resolve_in_root(root, rel_path)
    if candidate.exists():
        raise CodeViewError(f"已存在：{rel_path}")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if kind == "file":
        # O_EXCL 原子创建（评审整改）：不存在才创建成功，杜绝「exists() 判后
        # os.replace(tmp, candidate) 可覆盖隙间新建同名文件」的 TOCTOU 窗；
        # 空文件落盘即终态，无需 tmp 中转。隙间同名 → FileExistsError → 400。
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            raise CodeViewError(f"已存在：{rel_path}") from None
        return {
            "path": rel_path,
            "size_bytes": candidate.stat().st_size,
            "mtime_ns": str(candidate.stat().st_mtime_ns),
        }
    try:
        candidate.mkdir()
    except FileExistsError:  # 理论不达（上面已判 exists），并发兜底
        raise CodeViewError(f"已存在：{rel_path}") from None
    return {"path": rel_path}


def rename_code_entry(root: Path, rel_path: str, new_name: str) -> dict[str, Any]:
    """根目录内文件 / 目录改名（工单 code-tree-ops/01）。

    new_name 必须**单段**（_validate_entry_name 单源：非空 / 非纯空白 /
    首尾无空白 / ≤120 / 非 `.` `..` / 无 Windows 保留字符）——不支持跨目录
    移动（移动 = 删除 + 新建，用户自行）。安全判定与读面同源
    （_resolve_in_root × 2：源与目标都在 root 内，目标天然 = 源父目录 +
    new_name）；源不存在 / 目标已存在 → 400 中文；改名回自身名 = 幂等
    成功（返回现状，不报「已存在」）。os.rename 原子（目录可改，子树随之
    移动；rename 不改 mtime）。文件返回 {path: 新相对路径, mtime_ns: 字符串
    （= 改名后现值，作为打开 tab 的保存基准）}；目录返回 {path}。
    """
    _validate_entry_name(new_name)
    src = _resolve_in_root(root, rel_path)
    if not src.exists():
        raise CodeViewError(f"不存在：{rel_path}")
    dst = _resolve_in_root(
        root, (src.relative_to(root).parent / new_name).as_posix()
    )
    if src == dst:
        is_file = src.is_file()
        return {
            "path": rel_path,
            **({"mtime_ns": str(src.stat().st_mtime_ns)} if is_file else {}),
        }
    if dst.exists():
        raise CodeViewError(f"已存在：{dst.relative_to(root).as_posix()}")
    was_file = src.is_file()  # rename 后原路径即不存在，文件/目录判定必须前置
    os.rename(src, dst)
    new_rel = dst.relative_to(root).as_posix()
    if was_file:
        return {"path": new_rel, "mtime_ns": str(dst.stat().st_mtime_ns)}
    return {"path": new_rel}


def delete_code_entry(root: Path, rel_path: str) -> dict[str, Any]:
    """根目录内文件 / 空目录删除（工单 code-tree-ops/01）。

    安全判定与读面同源（_resolve_in_root）；不存在 → 400 中文；文件 →
    os.unlink；目录 → 仅空目录可删（os.rmdir），非空 → 400 中文
    「目录非空，请先清空（或删除其中文件）」——显式 any(iterdir) 判定，
    避免把权限类 OSError 误翻成「非空」。成功返回 {removed: True}。
    """
    target = _resolve_in_root(root, rel_path)
    if not target.exists():
        raise CodeViewError(f"不存在：{rel_path}")
    if target.is_dir():
        if any(target.iterdir()):
            raise CodeViewError(
                f"目录非空，请先清空（或删除其中文件）：{rel_path}"
            )
        target.rmdir()
    else:
        target.unlink()
    return {"removed": True}
