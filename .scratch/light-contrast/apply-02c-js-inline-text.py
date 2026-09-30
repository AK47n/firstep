"""浅色调色板轮 · 施工脚本（02 单 c）：把 **JS 内联**那 14 处文字色也迁到 `-text` 档。

## 为什么必须做（02 单双轴评审 Standards 轴点名）

`02a` 只迁了 `index.html` 样式块里的 223 处；`static/js/**` 里还内联写着 14 处
`style="color:var(--主令牌)"`（状态文字 / 冲突提示 / 汇总数），**门禁只读 index.html，看不见它们**——
于是"六族全部过线"这句话在渲染面上是漏的（`fx/task.js` 那句 `color:var(--ok-bright)`
浅色下仍是 3.29 ❌）。这一趟逐处迁移，**每一处都单列**（不走全局正则：评审点过"逐处过一遍"）。

跑法（仓库根）：
    python .scratch/light-contrast/apply-02c-js-inline-text.py --check   # 复核（只读）
    python .scratch/light-contrast/apply-02c-js-inline-text.py            # 落盘
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

JS = L.ROOT / "src" / "contest_generator" / "static" / "js"

#: `(相对路径, 旧串, 新串)` —— 逐处单列（同一文件里同形的两行各自成一条，便于计数复核）
EDITS = [
    ("fx/flash.js", 'style="color:var(--danger);font-weight:600"', 'style="color:var(--danger-text);font-weight:600"'),
    ("fx/flash.js", 'style="color:var(--warn);font-weight:600"', 'style="color:var(--warn-text);font-weight:600"'),
    ("fx/task.js", 'color:var(--ok-bright)', 'color:var(--ok-text)'),
    ("fx/task.js", 'style="color:var(--warn);font-weight:600"', 'style="color:var(--warn-text);font-weight:600"'),
    ("fx/task.js", 'style="color:var(--danger);font-weight:600"', 'style="color:var(--danger-text);font-weight:600"'),
    ("ui/generate-pins.js", 'style="color:var(--warn)"', 'style="color:var(--warn-text)"'),
    ("ui/generate-pins.js", 'color:var(--accent)"', 'color:var(--accent-text)"'),
    ("ui/generate-pins.js", 'style="color:var(--danger)"', 'style="color:var(--danger-text)"'),
]


def main() -> None:
    check = "--check" in sys.argv
    problems, total = [], 0
    files: dict[Path, str] = {}
    for rel, old, new in EDITS:
        p = JS / rel
        text = files.get(p) or p.read_text(encoding="utf-8")
        n = text.count(old)
        if n == 0:
            # 已经是新版（复核模式）就不再报错
            if check and text.count(new):
                files[p] = text
                continue
            problems.append(f"  {rel}：锚点没命中（0 次）—— {old[:60]}")
            continue
        if check:
            problems.append(f"  {rel}：还有 {n} 处旧写法没迁 —— {old[:60]}")
            continue
        files[p] = text.replace(old, new)
        total += n

    if problems:
        raise SystemExit(("复核发现问题：\n" if check else "锚点没命中，一个字节都没写：\n")
                         + "\n".join(problems))
    if check:
        print("复核 OK：14 处内联文字色已全部迁到 `-text` 档（且盘上不再有旧写法）")
        return
    for p, text in files.items():
        p.write_text(text, encoding="utf-8", newline="")
        print(f"  已写：{p.relative_to(L.ROOT)}")
    print(f"\n逐处迁移完成：**{total}** 处（{len(files)} 个文件）")


if __name__ == "__main__":
    main()
