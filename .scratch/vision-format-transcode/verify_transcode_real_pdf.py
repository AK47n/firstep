"""vision-format-transcode/01 真实验证（离线，零额度）：261 页长 PDF 全部
嵌入图格式分布 + 非 DeepSeek 直发格式（JPEG2000/BMP/未知）转 PNG 验证。

不调用任何视觉 API——只验证「提取 → 转码 → PNG 可解码」链路在真实赛题
PDF 上成立（对应 spec「PDF 内嵌图自动转码」验收）。
"""
import gc
import io
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from contest_generator.extraction import _needs_transcode, _transcode_to_png  # noqa: E402

PDF = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else r"library/topics/2021F/000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"
)


def main() -> None:
    reader = PdfReader(str(PDF))
    counts: dict[str, int] = {}
    targets: list[tuple[int, str, int]] = []  # (页, 名, 字节数)
    ok = 0
    for pno, page in enumerate(reader.pages, start=1):
        try:
            images = list(page.images)
        except Exception:
            continue  # 单页图片解析失败 = 跳过该页（与 pdf_image_notes 同防御）
        for image in images:
            name = image.name or "?"
            suffix = name.rsplit(".", 1)[-1].lower() if "." in name else "?"
            counts[suffix] = counts.get(suffix, 0) + 1
            if _needs_transcode(name):
                try:
                    data = image.data
                except Exception:
                    print(f"  [p{pno}] {name}: 字节提取失败")
                    continue
                png = _transcode_to_png(data)
                if png is None:
                    print(f"  [p{pno}] {name} ({len(data)}B): 转码失败")
                    continue
                from PIL import Image

                with Image.open(io.BytesIO(png)) as im:
                    assert im.format == "PNG"
                ok += 1
                targets.append((pno, name, len(data)))
                print(f"  [p{pno}] {name} ({len(data)}B → {len(png)}B): OK")
        del images  # 释放本页图片字节引用（page.images 为只读 property）
        gc.collect()
    print(f"\n=== {PDF.name} 图片后缀分布 ===")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    print(f"=== 非直发格式转码：成功 {ok}/{len(targets)} ===")


if __name__ == "__main__":
    main()
