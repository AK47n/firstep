"""扫描 PDF 内嵌图片格式分布（vision-deepseek-native 决策用一次性脚本，不入库）。

用 pypdf 逐页枚举图片：统计 pypdf 命名后缀分布 + PIL 真实格式分布，
专门回答「PDF 里有没有 BMP」——DeepSeek 视觉模型只支持 JPEG/PNG/GIF/WebP。
"""

import gc
import sys
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


def scan(path: Path) -> None:
    reader = PdfReader(str(path))
    print(f"== {path}  页数={len(reader.pages)}", flush=True)
    name_ext: Counter[str] = Counter()
    pil_format: Counter[str] = Counter()
    bmp_hits: list[tuple[int, str]] = []
    other_hits: list[tuple[int, str, str]] = []
    decoded = 0
    for pno, page in enumerate(reader.pages, 1):
        try:
            images = list(page.images)
        except Exception as exc:
            print(f"  page {pno}: 图片枚举失败 {exc!r}", flush=True)
            continue
        for image in images:
            try:
                name = image.name or ""
            except Exception:
                name = "?"
            ext = Path(name).suffix.lower() or "(none)"
            name_ext[ext] += 1
            try:
                im = image.image
                fmt = (im.format or "?").upper() if im is not None else "?"
                decoded += 1
            except Exception as exc:
                fmt = f"decode-fail:{type(exc).__name__}"
            pil_format[fmt] += 1
            if fmt == "BMP":
                bmp_hits.append((pno, name))
            elif fmt not in ("JPEG", "PNG", "GIF", "WEBP", "?"):
                other_hits.append((pno, name, fmt))
        del images
        if pno % 10 == 0:
            print(f"  ... page {pno} done, decoded={decoded}", flush=True)
        gc.collect()
    print("  pypdf 命名后缀分布:", dict(name_ext), flush=True)
    print("  PIL 真实格式分布:", dict(pil_format), flush=True)
    print(f"  BMP 命中 {len(bmp_hits)} 处:", bmp_hits[:100], flush=True)
    print(f"  其它非标准格式 {len(other_hits)} 处:", other_hits[:100], flush=True)
    print(flush=True)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        scan(Path(arg))
