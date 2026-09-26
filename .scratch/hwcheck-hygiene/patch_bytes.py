"""patch_bytes.py — 本目录两份数据面脚本（`apply-07-notes.py` / `apply-07-unmark.py`）
共用的**逐字节锚点替换**小工具（评审整改：两处重复的实现提成一份）。

为什么必须逐字节：`library/hwcheck_recipes.json` 盘上是 **LF**（`core.autocrlf=true`，
checkout 出来仍是 LF）——用 `json.dump` 整档重写会把缩进 / 键序 / 换行全部重排，
diff 与回滚都会变成噪声。所以按**字节**锚点替换，前后字节逐字保留。

`probe-07-red.py` 不共用本文件：它是**注入 → 跑测试 → 复原**的探针，锚点要按"目标文件
实际的换行形态"换算（本工作树 LF / CRLF 混装），比这里的"原样替换"多一层；两边的
换行探测写法已统一成 `b"\\r\\n" in blob`。
"""

from __future__ import annotations

import pathlib

# 本工具服务的文件在盘上的换行形态（实测，2026-09-26：3857 LF / 0 CRLF）
NEWLINE = "LF"


def newline_of(blob: bytes) -> str:
    """这个文件在盘上用的是哪种换行（本工作树 LF / CRLF 混装，锚点必须按实际形态编码）。"""
    return "\r\n" if b"\r\n" in blob else "\n"


def encode_anchor(text: str, blob: bytes) -> bytes:
    """按目标文件**实际**的换行形态编码锚点（本工作树 LF / CRLF 混装）。"""
    return text.replace("\n", newline_of(blob)).encode("utf-8")


def patch(target: pathlib.Path, edits: list[tuple[str, str, int]]) -> None:
    """按字节把 `edits`（旧串, 新串, 期望命中次数）逐条落到 `target` 上。

    任一条命中数对不上就**整体不动**（先全查后全写）：半截写入会让文件停在
    "改了一半"的状态，而下一次跑的幂等检查只会看"新串在不在"——那正是最费时间的坑。
    """
    blob = target.read_bytes()
    text = blob.decode("utf-8")
    for old, _new, want in edits:
        hits = text.count(old)
        if hits != want:
            raise SystemExit(
                f"✗ 锚点命中 {hits} 次（应为 {want}）：{old[:40]!r}——未改动任何字节")
    for old, new, want in edits:
        text = text.replace(old, new, want)
    target.write_bytes(text.encode("utf-8"))
