"""浅色调色板轮 · 施工脚本（05 单 b）：给"文件名/打开"链接补上令牌色（人眼复核逮到的漏改）。

## 来源（05 单的人眼复核）

复核在 **topic / md / pdf 三个页签**都看到：文件名链接是**浏览器默认蓝 `#0000EE`**，
而**同一个功能**在参考文件库走的是 `var(--accent-text)`（`.ref-files-list a`）——
同屏两种链接蓝，像漏改。根因：那几处的链接挂在 `.desc-cell` 里，
而 `.desc-cell` 只有截断规则（`max-width/overflow/text-overflow`），**没有颜色规则**。

## 修法

把 `.desc-cell` 的截断规则那条**拆开**：保留截断，另加一条 `.desc-cell a { color: var(--accent-text); }`
（与 `.ref-files-list a` 同款）。用 `--accent-text` 而不是 `--accent`：链接是文字，走文字档（浅色 #006181 过 AA）。

跑法（仓库根）：
    python .scratch/light-contrast/apply-05b-desc-cell-links.py --check
    python .scratch/light-contrast/apply-05b-desc-cell-links.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

ANCHOR = ".ref-files-list a { color: var(--accent-text); text-decoration: none; cursor: pointer; }"
ADDITION = ("\n  /* 表格里的「文件名 / 打开」链接（工单 05：人眼复核逮到 topic / md / pdf 三页仍是\n"
            "     浏览器默认蓝 #0000EE，而同一功能在参考文件库走 --accent-text——同屏两种链接色）。 */\n"
            "  .desc-cell a { color: var(--accent-text); text-decoration: none; }")


def main() -> None:
    check = "--check" in sys.argv
    text = L.read_page()
    if check:
        if ".desc-cell a { color: var(--accent-text)" not in text:
            raise SystemExit("复核不过：`.desc-cell a` 还没有颜色规则（那三页的链接仍是默认蓝）")
        print("复核 OK：`.desc-cell a` 已走 `--accent-text`")
        return
    if ".desc-cell a {" in text:
        raise SystemExit("页面里已经有 `.desc-cell a` 规则了——本脚本只跑一次")
    n = text.count(ANCHOR)
    if n != 1:
        raise SystemExit(f"锚点命中 {n} 次（期望 1）——一个字节都没写")
    L.PAGE.write_text(text.replace(ANCHOR, ANCHOR + ADDITION), encoding="utf-8", newline="")
    print(f"已写盘：{L.PAGE.relative_to(L.ROOT)}（新增 `.desc-cell a` 一条规则）")


if __name__ == "__main__":
    main()
