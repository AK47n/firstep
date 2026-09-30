"""浅色调色板轮 · 施工脚本（02 单 b）：**压在实心语义块上的字**也令牌化。

## 为什么还要这一趟

`apply-02a` 之后剩下的 12 处不达标全是同一类：**白字（或 `--panel`）压在实心语义块上**。
暗色的实心块是亮的（`--ok #3fb950` / `--accent #00d4ff`），白字只有 1.77–2.54；
浅色的实心块是暗的（`--ok #1a7f37`），深字又不够。**同一个 `#fff` 救不了两套主题**——
所以"实心块上的字"必须**按主题给值**（这正是 `--on-accent` 存在的理由，只是当年只做了 accent 一件）。

值（两主题各一组，判据 = 守卫腿⑧ 的机械面）：

| 令牌 | 暗色 | 浅色 | 压在什么上 |
|---|---|---|---|
| `--on-ok-deep`（**改**） | `#04170c`（不变） | `#ffffff`（原 `#04170c`，浅色下 3.65 ❌） | `--ok` 实心（步骤点 / 概览点） |
| `--on-danger`（**新**） | `#04170c` | `#ffffff` | `--danger` 实心（危险钮的悬停态） |
| `--on-accent-dark`（**新**） | `#04222b` | `#ffffff` | 浅色把 `--accent-dark` 压到 `#00607f` 之后的悬停底（**按底令牌命名**，不按状态命名） |

跑法（仓库根）：
    python .scratch/light-contrast/apply-02b-solid-on-tokens.py --dry
    python .scratch/light-contrast/apply-02b-solid-on-tokens.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

#: `(旧串, 新串, 期望命中次数)` —— 每一处都在票尾点名（改动面必须可审计）
EDITS = [
    # ① 浅色：亮色悬停底压深（原来 #007ea8 与深字只有 3.59）
    ("--accent: #0096c7; --accent-dark: #007ea8;",
     "--accent: #0096c7; --accent-dark: #00607f;", 1),
    # ② 浅色：实心块上的字改白（三个令牌）。
    #    ⚠ 这一行在两块里**逐字相同**，必须带上各自的主题上下文才认得出是哪一个。
    ("--accent-rgb: 0, 150, 199;\n    --accent-hi: #33dcff; --accent-lo: #00b8de;   "
     "/* 渐变亮/暗端沿用（深底对比换 accent 主色） */\n"
     "    --on-accent-deep: #001018; --on-ok-deep: #04170c;",
     "--accent-rgb: 0, 150, 199;\n    --accent-hi: #33dcff; --accent-lo: #00b8de;   "
     "/* 渐变亮/暗端沿用（深底对比换 accent 主色） */\n"
     "    --on-accent-deep: #001018; --on-ok-deep: #ffffff;   /* 浅色实心块是暗的 → 块上改白字 */\n"
     "    --on-danger: #ffffff; --on-accent-dark: #ffffff;", 1),
    # ③ 暗色：同样三个令牌（深字压亮块）
    ("    --accent-rgb: 0, 212, 255;\n    --accent-hi: #33dcff; --accent-lo: #00b8de;\n"
     "    --on-accent-deep: #001018; --on-ok-deep: #04170c;",
     "    --accent-rgb: 0, 212, 255;\n    --accent-hi: #33dcff; --accent-lo: #00b8de;\n"
     "    --on-accent-deep: #001018; --on-ok-deep: #04170c;\n"
     "    --on-danger: #04170c; --on-accent-dark: #04222b;", 1),
    # ④ 白字压 accent 实心：四处改走 --on-accent
    ("background: var(--accent); color: #fff; cursor: pointer; flex: none; }",
     "background: var(--accent); color: var(--on-accent); cursor: pointer; flex: none; }", 1),
    ("background: var(--accent); color: #fff; border: 0;",
     "background: var(--accent); color: var(--on-accent); border: 0;", 1),
    (".sugg-discuss-toggle:hover { background: var(--accent); color: var(--panel); }",
     ".sugg-discuss-toggle:hover { background: var(--accent); color: var(--on-accent); }", 1),
    (".btn-param-ref:hover { background: var(--accent); color: var(--panel); }",
     ".btn-param-ref:hover { background: var(--accent); color: var(--on-accent); }", 1),
    # ⑤ 悬停实心：--on-accent → --on-accent-dark（浅色那一档才需要白字）
    ("button.primary:hover { background: var(--accent-dark); color: var(--on-accent); }",
     "button.primary:hover { background: var(--accent-dark); color: var(--on-accent-dark); }", 1),
    # ⑥ 步骤点的对勾：白字压 --ok 实心 → --on-ok-deep
    (".stepper .step.done .dot { border-color: var(--ok); background: var(--ok); color: #fff; }",
     ".stepper .step.done .dot { border-color: var(--ok); background: var(--ok);"
     " color: var(--on-ok-deep); }", 1),
    # ⑦ 危险钮悬停：白字压 --danger 实心 → --on-danger
    ("button.danger:hover { background: var(--danger); color: #fff; }",
     "button.danger:hover { background: var(--danger); color: var(--on-danger); }", 1),
]

#: 悬停实心那两处（折行的合并选择器规则）——与 `EDITS` 同一套机制，只是锚点里带换行
HOVER_EDITS = [
    (".btn-task-dialog-send:hover, .btn-global-chat-send:hover, .btn-params-chat-send:hover,\n"
     "  .sugg-discuss-send:hover { background: var(--accent-dark); color: var(--on-accent); }",
     ".btn-task-dialog-send:hover, .btn-global-chat-send:hover, .btn-params-chat-send:hover,\n"
     "  .sugg-discuss-send:hover { background: var(--accent-dark); color: var(--on-accent-dark); }", 1),
    (".task-card .btn-task-run:not(:disabled):hover { background: var(--accent-dark);"
     " color: var(--on-accent); }",
     ".task-card .btn-task-run:not(:disabled):hover { background: var(--accent-dark);"
     " color: var(--on-accent-dark); }", 1),
]


def main() -> None:
    dry = "--dry" in sys.argv
    check = "--check" in sys.argv
    raw = L.PAGE.read_bytes()
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    text = raw.decode("utf-8")

    if check:
        # 复核 = **后置条件**（同 02a：让 12 这个数字有一条命令可复算）
        problems = []
        for name, dark, light in (("--on-danger", "#04170c", "#ffffff"),
                                  ("--on-accent-dark", "#04222b", "#ffffff")):
            if f"{name}: {dark};" not in text:
                problems.append(f"  暗色缺 {name}: {dark};")
            if f"{name}: {light};" not in text:
                problems.append(f"  亮色缺 {name}: {light};")
        if "--accent-dark: #00607f;" not in text:
            problems.append("  浅色 `--accent-dark` 没改成 #00607f（悬停底那一档）")
        for frag in ("background: var(--accent); color: #fff", "background: var(--ok); color: #fff",
                     "background: var(--danger); color: #fff", "color: var(--panel); cursor: pointer"):
            if frag in text:
                problems.append(f"  还有没令牌化的实心块字色：{frag}")
        if problems:
            raise SystemExit("复核发现问题：\n" + "\n".join(problems))
        print("复核 OK：实心块上的字全部走 `--on-*` 令牌（4 处）＋两个新令牌两主题都在")
        return

    if "--on-danger" in text:
        raise SystemExit("页面里已经有 --on-danger 了——本脚本只跑一次；要重跑先 git checkout")

    problems = []
    nls = nl.decode()
    for old, new, want in EDITS:
        old, new = old.replace("\n", nls), new.replace("\n", nls)   # 锚点按盘上真实换行换算
        n = text.count(old)
        if n != want:
            problems.append(f"  命中 {n} 次（期望 {want}）：{old[:70]}")
            continue
        text = text.replace(old, new)
    if problems:
        raise SystemExit("锚点没命中，一个字节都没写：\n" + "\n".join(problems))

    # 悬停实心的另两处（`--on-accent` → `--on-accent-dark`）走 EDITS 的同一套机制：
    # 合并选择器那条规则折了行，锚点里带上换行与缩进（按盘上真实换行换算）。
    for old, new, want in HOVER_EDITS:
        old, new = old.replace("\n", nls), new.replace("\n", nls)
        n = text.count(old)
        if n != want:
            raise SystemExit(f"悬停规则锚点命中 {n} 次（期望 {want}）：{old[:70]}")
        text = text.replace(old, new)

    if dry:
        print(f"（--dry）{len(EDITS) + len(HOVER_EDITS)} 处锚点全部命中，没写盘")
        return
    L.PAGE.write_bytes(text.encode("utf-8"))
    print(f"已写盘：{L.PAGE.relative_to(L.ROOT)}；改了 {len(EDITS) + len(HOVER_EDITS)} 处")


if __name__ == "__main__":
    main()
