r"""描边守卫轮 · 施工脚本（01 单）：把 `BORDER_KINDS` + `BORDER_REGISTER` 两张表插进守卫。

**一次性脚本**（照 sitewide 轮 `apply-*` 的先例）：锚点命中恰好一次、插完自报行数，
跑完就不再需要它（守卫源码从此是唯一真源）。

⚠ **本脚本已经跑过，锚点已消费，别再跑它**。而且它插进去的那两段文本**在守卫里被双轴评审
整改过**（`placeholder` 的判据措辞补了"滚动条 thumb 的透明声明"那一半；登记簿说明块补了
"两条容易贴错的"）——本文件里那两份是**改前的快照**，与守卫**不再逐字相同**。
要复核"守卫里那张表对不对"，用 `probe-03-register.py`（从守卫读）或
`generate-01-register.py --check`（复核生成关系），**别拿本文件当判据**。

锚点取 `FROZEN_FONT_SIZES` 定义块的**结尾那一行**（`]);` 收尾 + 紧随的注释块开头），
按 `\n` 写——`tests/js/css-tokens.test.mjs` 实测是纯 LF（577 行，CRLF 0），
与 sitewide 轮的"按文件实际换行换算"纪律一致（那条纪律是给 CRLF 文件写的）。
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"
BLOCK = HERE / "register-block.js.txt"

ANCHOR = """const FROZEN_FONT_SIZES = new Set([
  // index.html 样式块 0 处裸 px 字号（07 单达成）；此处**故意留空**——
  // 加回任何一个取值 = 加回一处裸字号。
]);

"""

KINDS_DOC = '''/**
 * **描边类别表**（工单 border-guard/01，单源）：回答「这条框为什么可以留」。
 *
 * **它不重推类别**——机器判不了"这是语义告示还是内层框"（那正是 08 账第 1 条说的判据问题）。
 * 类别是**人判过一次、写进 BORDER_REGISTER 的数据**；守卫只保证：
 *   · 每条登记项的类别值在**本表**里（新造一个类别把框塞进来这条路走不通）；
 *   · **每个类别至少有一条**（类别表不长出空档——空类别 = 判据退化成摆设）。
 *
 * 类别出处 = `.scratch/ui-density-sitewide/spec.md` 的例外 ①–⑥ 与那张轮的逐层清单；
 * 本表把它们机械化。**判据边界**：不判"该不该留"、不判好不好看。
 * 格式固定（`["id", "判据"],` 一行一条，判据里**不写 ASCII 双引号**）——
 * `.scratch/border-guard/probe-03-register.py` 与 `scope_lib.load_border_kinds()` 按同一格式解析。
 */
const BORDER_KINDS = [
  ["block", "顶层块：一屏里自成一块的容器（页面主体卡 / 页级汇总条）——「一屏一层」要留的就是它"],
  ["control", "可点控件：按钮 / 输入 / 下拉 / 勾选框 / 可点卡片 / 可点 chip / 标签页——那是控件的形状"],
  ["tag", "徽章与标签（不可点）：身份 / 计数 / 图例胶囊，用一条边把自己从正文里拎出来"],
  ["alert", "语义告示块：带警示或状态语义的告示（编译条 / 未选功能组 / 未上板 / 服务已停止 / 保存失败）"],
  ["modal", "弹层外壳：弹层 / 菜单 / toast——它自己是一屏，那一条要留"],
  ["float", "浮在内容之上的自己的面：悬浮保存条 / 只读标注 / 缩放浮标（不然与背后的字糊在一起）"],
  ["doc", "文档与表格语法：表格网格线 / md 预览的表格与图片框 / 指南表——去掉文档就散了"],
  ["editor", "编辑器形状：代码编辑器本体与它的悬浮工具条"],
  ["nonbox", "不是框：用 border 画的圆点 / 对勾字形 / 转圈环 / 滚动条 thumb——画得出像素，但不是盒子"],
  ["placeholder", "透明占位（★ 唯一带机器不变量）：取值含 transparent，默认态画不出框，给悬停 / 选中态留位置"],
];

/**
 * **描边登记簿**（工单 border-guard/01）：`index.html` 样式块里**允许留框**的整圈完整框，逐条登记。
 *
 * **认人键 = `(作用域, 选择器)`**（选择器是**剥掉前导块注释、空白归一**后的形态，与 `scopeOf` 同口径
 * ——原始选择器前面挂着大段块注释，拿它当键等于把注释一起冻进表里）。
 * 取值**不进键**：换个描边色 / 换令牌不该动这张表（那轮"守卫不判好不好看"的边界）。
 *
 * **腿⑥ 四条判据**（判据本体在 `borderRegisterProblems`，红证在文件末尾那条合成用例里）：
 *   ① 盘上 ⊆ 本表（新增一条框必须**显式登记**，否则当场判红）；
 *   ② 本表 ⊆ 盘上（改名 / 删规则会让登记项**过期**——反向对账，这份数据因此不会烂）；
 *   ③ `placeholder` ⟺ 取值含 `transparent`（**抓"透明占位偷偷变成真框"**）；
 *   ④ 类别表形状（类别值必须在 `BORDER_KINDS` 里、每类至少一条）。
 *
 * **口径分列（别混着读）**：本表 115 条 = **94 条可见框** + **21 条非框**
 * （12 `placeholder` + 9 `nonbox`）。"整圈完整框 115"是**声明数**口径（`scope_lib.full_borders`），
 * 与"渲染出来的框元素数"不是同一把尺——那一条 `local-environment` 记过。
 *
 * **不在射程内（明写的边界）**：`border-color` 这类**单声明**不是"完整框"，
 * 所以悬停 / 选中态才出现的框**本来就不在这个口径里**（`.code-tab` 那族占位的意义正是这个）；
 * `border-top` / `border-bottom` 的单边分隔线同理不在射程。
 *
 * 格式固定（`["作用域", "选择器", "类别"],` 一行一条，`// ---- <作用域> ----` 是分组注释）——
 * 探针与 `scope_lib.load_border_register()` 按同一格式解析，格式变了会**大声失败**。
 */
const BORDER_REGISTER = [
'''


def main() -> int:
    text = GUARD.read_text(encoding="utf-8", newline="")
    if text.count(ANCHOR) != 1:
        raise SystemExit(f"锚点命中 {text.count(ANCHOR)} 次（应为 1）——守卫变了，停手")
    if "BORDER_REGISTER" in text:
        raise SystemExit("守卫里已经有 BORDER_REGISTER 了——本脚本是一次性的，别跑第二遍")
    rows = BLOCK.read_text(encoding="utf-8").strip().splitlines()
    body = "\n".join(rows[1:])  # 去掉生成块首行的 `const BORDER_REGISTER = [`
    assert body.rstrip().endswith("];"), "生成块结尾不对"
    entries = sum(1 for line in rows[1:] if line.strip().startswith('["'))
    inserted = KINDS_DOC + body.rstrip() + "\n"
    new = text.replace(ANCHOR, ANCHOR + inserted)
    if len(new) - len(text) != len(inserted):
        raise SystemExit("插入后长度对不上——停手")
    GUARD.write_text(new, encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    added = len(inserted.splitlines())
    print(f"已插入：{added} 行（守卫 {len(text.splitlines())} → {len(new.splitlines())} 行）")
    print(f"其中登记项 {entries} 行 + 类别表 {KINDS_DOC.count(chr(10) + '  [')} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
