"""生成电赛工程生成器桌面图标（assets/电赛生成器.ico）。"""
from PIL import Image, ImageDraw, ImageFont

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角背景（深海军蓝，带一点竖向渐变感）
bg_top, bg_bot = (22, 35, 63, 255), (30, 58, 95, 255)
for y in range(SIZE):
    t = y / SIZE
    c = tuple(round(a + (b - a) * t) for a, b in zip(bg_top[:3], bg_bot[:3]))
    d.line([(0, y), (SIZE, y)], fill=(*c, 255))
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=48, fill=255)
img.putalpha(mask)

# 芯片引脚（四边各 4 根）
pin = (188, 200, 222, 255)
for i in range(4):
    x = 40 + i * 48
    d.rounded_rectangle([x, 22, x + 24, 58], radius=6, fill=pin)
    d.rounded_rectangle([x, SIZE - 58, x + 24, SIZE - 22], radius=6, fill=pin)
    d.rounded_rectangle([22, x, 58, x + 24], radius=6, fill=pin)
    d.rounded_rectangle([SIZE - 58, x, SIZE - 22, x + 24], radius=6, fill=pin)

# 芯片本体（浅色圆角方块 + 左上角缺口标记）
chip = (222, 230, 243, 255)
d.rounded_rectangle([70, 70, 186, 186], radius=18, fill=chip)
d.rectangle([70, 70, 92, 92], fill=bg_top[:3] + (255,))  # 1 脚标记

# "电"字（微软雅黑，白字深色）
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 84)
except OSError:
    font = ImageFont.load_default()
d.text((128, 132), "电", font=font, fill=(30, 58, 95, 255), anchor="mm")

# 右上角绿色电源灯
d.ellipse([198, 24, 232, 58], fill=(34, 197, 94, 255))
d.ellipse([210, 36, 220, 46], fill=(134, 239, 172, 255))

img.save(r"assets\电赛生成器.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
print("icon written")
