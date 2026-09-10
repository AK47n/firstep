r"""用项目自带视觉通道「目视」module-library-ui/01 的截图（第十四轮尾巴收口）。

背景：该项验收写的是「浏览器截图人工目视验收」，而执行 agent 的模型不声明图像输入
（`read_image` 报 does not declare image input）。用户已授权改用仓库现成的视觉链路
（`contest_generator.vision.describe_image` + 配置里的 DeepSeek 视觉模型）看图，会消耗主 key 额度。

只读：不写库、不改产品码；产物两份描述文本落在本目录下。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch\module-library-ui\vision-eyeball.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.config import load_config  # noqa: E402
from contest_generator.vision import (  # noqa: E402
    describe_image,
    effective_vision_api_key,
    vision_configured,
)

HERE = Path(__file__).resolve().parent

PROMPT = """这是一张本地网页工具（电赛工程生成器）界面的截图，深色主题。请只描述你在图里**实际看到**的内容，不要推测、
不要描述你没看到的东西。逐条回答：

1) 页面主标题文字是什么？标题有没有被顶部栏遮挡、切掉一半，或与其它元素重叠？
2) 表格一共有几列？从左到右各列的表头文字分别是什么？
3) 表格的数据行之间有没有斑马纹（相邻行底色明显不同）？
4) 表头那一行的底色与数据行底色是否不同？
5) 表格里出现了哪些彩色小标签／胶囊／徽章？分别是什么颜色、上面写什么字？
   有没有只有形状（圆角块）却没有底色的「裸文字」标签？
6) 最右边操作列有哪些按钮？按钮底色是否一致？有没有红色按钮、写什么字？
7) 第一列的文字看起来是不是等宽字体（像代码那样，每个字符宽度相同）？
8) 描述／简介那一列的文字是否被截断（行尾出现省略号 …）？是否换行溢出？
9) 有没有明显的渲染异常：元素重叠、错位、文字被裁掉、异常空白块、乱码、滚动条压住内容？

最后给一句总评：这张截图看起来是不是一份正常渲染、样式统一的界面？"""


def main() -> int:
    cfg = load_config()
    key = effective_vision_api_key(cfg.vision_api_key, cfg.api_key, cfg.vision_base_url)
    if not vision_configured(key):
        print("视觉通道未配置：vision_api_key 为空且主 key 未复用（检查 ~/.contest_generator/config.json）")
        return 2
    print(f"视觉端点 {cfg.vision_base_url} 模型 {cfg.vision_model}（key 来源：{'显式 vision key' if vision_configured(cfg.vision_api_key) else '复用主 key'}）")

    shots = ["01-table-shot-final.png", "01-table-shot.png"]
    for name in shots:
        png = HERE / name
        if not png.is_file():
            print(f"!! 缺截图 {png}")
            continue
        print(f"---- 目视 {name}（{png.stat().st_size} B） ----")
        desc = describe_image(
            png.read_bytes(),
            "image/png",
            PROMPT,
            base_url=cfg.vision_base_url,
            api_key=key,
            model=cfg.vision_model,
            timeout=120.0,
        )
        out = HERE / (name.replace(".png", ".vision.txt"))
        out.write_text(desc.strip() + "\n", encoding="utf-8")
        print(desc.strip())
        print(f"--> 已落盘 {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
