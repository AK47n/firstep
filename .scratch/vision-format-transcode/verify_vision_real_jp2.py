"""vision-format-transcode/01 真实视觉验证：长 PDF 的 12 张 JPEG2000 图转码后
真实调用 DeepSeek 视觉（deepseek-v4-flash-vision-exp）识别。

key 来源：~/.contest_generator/config.json 的主 key（api_key）——只读不打印；
不修改任何配置。消耗：12 张 × ≤384 token/张 ≈ 5K token（几分钱量级）。
"""
import gc
import json
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from contest_generator.extraction import _transcode_to_png  # noqa: E402
from contest_generator.vision import describe_image_cached  # noqa: E402

PDF = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else r"library/topics/2021F/000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"
)


def main() -> None:
    cfg_path = Path.home() / ".contest_generator" / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    main_key = (cfg.get("api_key") or "").strip()
    if not main_key:
        print("主 key 未配置——无法真实调用，退出")
        sys.exit(1)
    print(f"主 key 已配置（{len(main_key)} 字符，不展示内容）")

    reader = PdfReader(str(PDF))
    ok = 0
    fail = 0
    for pno, page in enumerate(reader.pages, start=1):
        try:
            images = list(page.images)
        except Exception:
            continue
        for image in images:
            name = image.name or "?"
            if not name.lower().endswith(".jp2"):
                continue
            try:
                data = image.data
            except Exception:
                print(f"  [p{pno}] {name}: 提取失败")
                fail += 1
                continue
            png = _transcode_to_png(data)
            if png is None:
                print(f"  [p{pno}] {name}: 转码失败")
                fail += 1
                continue
            try:
                desc = describe_image_cached(
                    png,
                    "image/png",
                    base_url="https://api.deepseek.com",
                    api_key=main_key,
                    model="deepseek-v4-flash-vision-exp",
                )
            except Exception as exc:
                print(f"  [p{pno}] {name}: 视觉调用失败 {type(exc).__name__}: {exc}")
                fail += 1
                continue
            ok += 1
            print(f"  [p{pno}] {name} → {desc[:120]}")
        del images
        gc.collect()
    print(f"\n=== JPEG2000 真实识别：成功 {ok}，失败 {fail} ===")


if __name__ == "__main__":
    main()
