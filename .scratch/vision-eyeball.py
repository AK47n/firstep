r"""通用「视觉通道目视」工具（B 组收口用）：把截图交给仓库自带视觉链路，按每图一问写回原话。

机制与口径（与 `.scratch/module-library-ui/vision-eyeball.py` 同一套路，第十四轮用户拍板）：
- 执行 agent 的模型不声明图像输入（`read_image` 报 does not declare image input），
  故「目视」这一步改走仓库现成链路 `contest_generator.vision.describe_image`
  （DeepSeek 官方端点 + `vision_model`；`vision_api_key` 留空按仓库口径复用主 key，会消耗额度）；
- 每张图配一段**针对性问题**（只问该图要验的那件事），原话落盘 `<图名>.vision.txt`；
- 只看「机器判据已经过了的图」，视觉结论作为**交叉证据**，不单独作为通过依据。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/vision-eyeball.py           # 跑 MANIFEST 全部
    $env:PYTHONIOENCODING='utf-8'; python .scratch\vision-eyeball.py B6 B13   # 只跑指定 key
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.config import load_config  # noqa: E402
from contest_generator.vision import (  # noqa: E402
    describe_image,
    effective_vision_api_key,
    vision_configured,
)

# (key, 图片相对路径, 问题)
MANIFEST: list[tuple[str, str, str]] = [
    ("B6", ".scratch/code-editor-refine/shot-04-rainbow-dark.png",
     "这是代码编辑器的深色主题截图。请只描述你实际看到的：编辑区里有没有若干对括号被**不同颜色**高亮？"
     "如果有，请说出一共看到几种不同颜色、分别在什么位置（哪几行/哪几对括号）。如果所有括号颜色都一样，直接说一样。"),
    ("B6", ".scratch/code-editor-refine/shot-04-rainbow-light.png",
     "这是同一个代码编辑器的浅色主题截图。请只描述你实际看到的：编辑区里括号高亮一共有几种颜色？"
     "浅色背景下这些颜色是否清晰可辨（对比是否足够）？"),
    ("B13", ".scratch/gen-result-panel/shot-01-wide.png",
     "这是网页工具「生成结果」区的宽屏截图。请只描述你实际看到的：这块内容是**左右两列**还是**单列**？"
     "如果是两列，左列和右列分别大致装了哪些内容块？有没有明显错位、重叠或空白异常？"),
    ("B13", ".scratch/gen-result-panel/shot-01-narrow.png",
     "这是同一块「生成结果」区的窄屏截图。请只描述你实际看到的：内容是**左右两列**还是**从上到下单列**？"
     "有没有元素被挤压、切除、重叠或横向溢出？"),
    ("B14", ".scratch/ui-detail/shot-01-step-nav.png",
     "这是生成页左侧的步骤导航截图。请只描述你实际看到的：一共有几个步骤圆点？"
     "圆点里有没有颜色明显不同的（比如绿色/黄色/蓝色的）？最靠上的那个圆点是什么颜色、里面写什么？"),
    ("B14", ".scratch/ui-detail/shot-02-motion.png",
     "这是网页工具的截图（用于核对动效令牌与整体观感）。请只描述你实际看到的：界面整体是否渲染正常"
     "（有无重叠、错位、文字被裁、异常空白块）？看起来是深色还是浅色主题？"),
    ("B14", ".scratch/ui-detail/shot-03-card-group.png",
     "这是生成页的截图，重点看「修复中心」卡片内部。请只描述你实际看到的：卡片内部是否有一到两个"
     "**带浅色底纹和边框的小分组块**（分组块里还有灰色小标题）？分组块的小标题文字分别是什么？"),
    ("B12", ".scratch/master-library-ui-2/shot-06-detail-tree.png",
     "这是「母版详情」弹窗的截图。请只描述你实际看到的：弹窗里有没有一棵可展开的**文件树**"
     "（带目录三角、文件条目、缩进层级）？大致有几个目录节点、多少个文件条目？有没有明显错位或空白异常？"),
    ("B22", ".scratch/wiki-materials/shot-md-list.png",
     "这是「Markdown 资料」页的截图。请只描述你实际看到的：有没有一个表格列表？表格第一列里每行是"
     "**中文标题 + 下面一行更小的英文文件名**这种两行结构吗？页面上还有搜索框/排序/批次标签之类的控件吗？"),
    ("B23", ".scratch/wiki-materials/shot-md-color-preview.png",
     "这是 Markdown 预览弹窗的截图。请只描述你实际看到的：弹窗正文里有没有**图片**（一张彩色屏幕示意图？）？"
     "有没有代码块（深色底、带颜色高亮的代码区）？正文排版是否正常（标题/段落/列表）？"),
    # ---- 第十六轮新增（A11 / A2_A3 / B26 的截图交叉印证）----
    ("A2A3", ".scratch/fix-loop-warnings/shot-16-fix-banner-success.png",
     "这是网页工具「修复中心」区的截图。请只描述你实际看到的：有没有一条横向的**状态横幅**？"
     "横幅里的文字是什么？横幅的底色是偏绿（成功）还是偏红（失败）？横幅下方有没有一个"
     "「编译输出」的多行文本框、里面有没有内容？"),
    ("B26", ".scratch/fix-loop-warnings/shot-16-fix-warning-cleared.png",
     "这是网页工具「修复中心」区的截图（刚跑完一轮自动编译修复）。请只描述你实际看到的："
     "页面上有没有显示轮次或结果的文字（比如「第 N/M 轮」或「编译通过」「0 错 0 警」之类）？"
     "把这些文字照抄出来。有没有红色的删除线/按钮、或者「回滚」字样的按钮？"),
    ("A2A3b", ".scratch/compile-experience-ui/shot-16-compile-banner-success.png",
     "这是网页工具生成结果区的截图。请只描述你实际看到的：最上方有没有一条**横贯的浅绿色"
     "底色状态条**（带边框、里面一行加粗文字）？把这条里的文字照抄出来。它下方还有哪些"
     "区块（例如「下一步」按钮行、工程结构树、右侧栏）？有没有重叠/错位/文字被裁？"),
]


def main() -> int:
    cfg = load_config()
    key = effective_vision_api_key(cfg.vision_api_key, cfg.api_key, cfg.vision_base_url)
    if not vision_configured(key):
        print("视觉通道未配置：vision_api_key 为空且主 key 未复用")
        return 2
    only = set(sys.argv[1:])
    print(f"端点 {cfg.vision_base_url} 模型 {cfg.vision_model}"
          f"（key 来源：{'显式 vision key' if vision_configured(cfg.vision_api_key) else '复用主 key'}）")
    done = 0
    for tag, rel, prompt in MANIFEST:
        if only and tag not in only:
            continue
        png = ROOT / rel
        if not png.is_file():
            print(f"!! 缺图 {rel}")
            continue
        print(f"---- {tag} 目视 {rel} ----")
        try:
            desc = describe_image(png.read_bytes(), "image/png", prompt,
                                  base_url=cfg.vision_base_url, api_key=key,
                                  model=cfg.vision_model, timeout=120.0)
        except Exception as exc:  # 单图失败不拖垮整批
            print(f"   !! 视觉调用失败：{exc}")
            continue
        out = png.with_suffix(".vision.txt")
        out.write_text(desc.strip() + "\n", encoding="utf-8")
        print(desc.strip())
        print(f"--> 已落盘 {out.relative_to(ROOT)}")
        done += 1
    print(f"\n完成 {done} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
