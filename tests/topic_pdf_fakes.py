"""赛题库取题面页图测试假件（工单 topic-pdf-viewer/02）：多页可渲染 PDF。

tests/fakes.py 属既有测试只读件（不追加不修改，仓库惯例），新增假件独立成
文件（同 generate_wiring_fakes.py 先例）。PDF 字符串转义复用 fakes 的
_pdf_escape（同包私有导入，fakes 文件间惯例）。
"""

from __future__ import annotations

import zlib
from pathlib import Path
from typing import Sequence

from tests.fakes import _pdf_escape


def make_multi_page_pdf(path: Path, pages: Sequence[tuple[str, str]]) -> Path:
    """手工构造多页 PDF（ASCII 限定）：每页 (页脚, 正文) 两行文本。

    页脚与正文分两个 Tj 段（不同 y），保证文本层分两行——页脚整行
    「F - 1 / 4」形态可被整行正则匹配（真题汇总 PDF 页脚同款排版）。
    构造参考 fakes.make_sample_pdf（Helvetica + FlateDecode + 手写 xref）。
    """
    streams: list[bytes] = []
    for footer, body in pages:
        lines = []
        if footer:
            lines.append(f"BT /F1 12 Tf 72 760 Td ({_pdf_escape(footer)}) Tj ET\n")
        lines.append(f"BT /F1 24 Tf 72 720 Td ({_pdf_escape(body)}) Tj ET\n")
        streams.append(zlib.compress("".join(lines).encode("ascii")))
    count = len(pages)
    kids = " ".join(f"{4 + i} 0 R" for i in range(count))
    content_refs = [f"{4 + count + i} 0 R" for i in range(count)]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode("ascii"),
        (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        ),
    ]
    for i in range(count):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_refs[i]} >>"
            ).encode("ascii")
        )
    for stream in streams:
        objects.append(
            b"<< /Filter /FlateDecode /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{number} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(b"xref\n0 " + str(len(objects) + 1).encode("ascii") + b"\n")
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(bytes(out))
    return path
