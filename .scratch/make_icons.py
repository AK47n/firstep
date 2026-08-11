"""图标生成脚本：python .scratch/make_icons.py          → 4 款候选预览 PNG
                      python .scratch/make_icons.py 1   → 把风格 N 固化为 assets/电赛生成器.ico"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SIZE = 256
OUT = Path("assets/icon-candidates")
OUT.mkdir(parents=True, exist_ok=True)
ICO = Path("assets/电赛生成器.ico")


def base(radius=48, bg_top=(22, 35, 63), bg_bot=(30, 58, 95)):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(SIZE):
        t = y / SIZE
        c = tuple(round(a + (b - a) * t) for a, b in zip(bg_top, bg_bot))
        d.line([(0, y), (SIZE, y)], fill=(*c, 255))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def style1():
    """金线电路板：深底 + 金色走线汇向中央芯片。"""
    img = base(bg_top=(10, 20, 33), bg_bot=(20, 40, 62))
    d = ImageDraw.Draw(img)
    gold = (201, 162, 39, 255)
    traces = [
        (10, 50, 92, 96), (10, 140, 92, 122), (10, 210, 92, 158),
        (246, 50, 164, 96), (246, 140, 164, 122), (246, 210, 164, 158),
        (50, 10, 96, 92), (140, 10, 122, 92), (210, 10, 158, 92),
        (50, 246, 96, 164), (140, 246, 122, 164), (210, 246, 158, 164),
    ]
    for x1, y1, x2, y2 in traces:
        d.line([(x1, y1), (x2, y2)], fill=gold, width=3)
    for x, y in [(38, 30), (218, 30), (38, 226), (218, 226)]:
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=gold)
    d.rounded_rectangle([96, 96, 160, 160], radius=10, fill=(38, 46, 60, 255),
                        outline=gold, width=3)
    d.rectangle([96, 96, 110, 110], fill=gold)
    return img


def style2():
    img = base(bg_top=(20, 120, 74), bg_bot=(10, 80, 50), radius=52)
    d = ImageDraw.Draw(img)
    bolt = [(148, 26), (84, 146), (122, 146), (104, 230), (176, 108), (134, 108)]
    d.polygon(bolt, fill=(255, 255, 255, 255))
    shade = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shade).polygon(bolt, fill=(0, 60, 40, 90))
    shade = shade.filter(ImageFilter.GaussianBlur(2))
    img.alpha_composite(shade.rotate(0, translate=(0, 4)))
    return img


def style3():
    img = base(bg_top=(13, 18, 30), bg_bot=(24, 32, 50))
    d = ImageDraw.Draw(img)
    pin_gray = (150, 163, 184, 255)
    chip_body = (203, 212, 228, 255)
    chip_shadow = (176, 186, 204, 255)
    d.rounded_rectangle([52, 52, 204, 204], radius=16, fill=chip_body)
    d.rounded_rectangle([52, 52, 204, 204], radius=16, outline=(255, 255, 255, 200), width=2)
    d.rounded_rectangle([66, 66, 190, 190], radius=10, fill=chip_shadow)
    for i in range(5):
        y = 76 + i * 26
        d.rounded_rectangle([30, y, 52, y + 14], radius=3, fill=pin_gray)
        d.rounded_rectangle([204, y, 226, y + 14], radius=3, fill=pin_gray)
        x = 76 + i * 26
        d.rounded_rectangle([x, 30, x + 14, 52], radius=3, fill=pin_gray)
        d.rounded_rectangle([x, 204, x + 14, 226], radius=3, fill=pin_gray)
    d.rounded_rectangle([88, 88, 168, 168], radius=8, fill=(168, 178, 196, 255))
    d.rectangle([52, 52, 70, 70], fill=chip_body)
    return img


def style4():
    img = base(bg_top=(13, 17, 23), bg_bot=(22, 28, 38))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([36, 66, 220, 196], radius=12, fill=(24, 30, 40, 255),
                        outline=(70, 82, 100, 255), width=2)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([52 + i * 26, 82, 62 + i * 26, 92], fill=c)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 72)
    except OSError:
        font = ImageFont.load_default()
    d.text((52, 118), ">", font=font, fill=(57, 211, 83, 255))
    d.rounded_rectangle([120, 118, 128, 182], radius=4, fill=(57, 211, 83, 255))
    return img


STYLES = {"1": style1, "2": style2, "3": style3, "4": style4}

if __name__ == "__main__":
    if len(sys.argv) > 1:  # 固化：python make_icons.py N
        img = STYLES[sys.argv[1]]()
        img.save(ICO, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
        print(f"finalized style{sys.argv[1]} -> {ICO}")
    else:  # 预览：生成 4 款 PNG
        for n, fn in STYLES.items():
            fn().save(OUT / f"style{n}_preview.png")
            print("wrote style", n)
