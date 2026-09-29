r"""描边守卫轮 · 施工脚本（01 单）：把 115 条整圈完整框**按类别**生成守卫里的登记簿。

**这是一次性脚本**（照 sitewide 轮 `apply-*` 的先例）：它产出的登记簿一旦落进
`tests/js/css-tokens.test.mjs`，**守卫源码就是唯一真源**——本脚本与 `register-block.js.txt`
都是**已被消费的一次性产物，别拿它们当判据**（双轴评审点过名：那是同一份数据的第二、三份副本）。

为了不让那两份副本悄悄烂掉，本脚本带一个 **`--check`**：按盘上现算 + 本文件的 `KIND` 表
重新生成一遍，与守卫里那张表**逐条比**；不一致就非零退出。
（复算的正确姿势仍是 `.scratch/border-guard/probe-03-register.py`——它从守卫源码读，
不读本文件。`--check` 回答的是另一个问题："当年这张表是不是这么生成的、有没有人偷偷改过"。）

口径 = `scope_lib.full_borders`（判据一字不动）；选择器在写表前**剥掉前导块注释 + 空白归一**
（与守卫 `scopeOf` / 探针 `scope_of` 同一口径）。

判据（硬断言，不等就停手——sitewide 08 账第 4 条：数量对账别留逃生门）：
  ① 盘上现算 115 条，与申报一致；
  ② 每条都在 `KIND` 表里有类别（`KIND` 里多出来的选择器也算错——防"表比盘多"）；
  ③ 类别值必须在 `KINDS` 里；
  ④ 每条选择器在本作用域内唯一（认人键成立的前提）。
"""

from __future__ import annotations

import collections
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "ui-density-sitewide"))

from scope_lib import (  # noqa: E402
    full_borders, load_border_register, load_scopes, read_page, scope_of, strip_lead_comments,
)

OUT = HERE / "register-block.js.txt"
CHECK = "--check" in sys.argv

HEADER = [
    "  // ⚠ 本表由 `.scratch/border-guard/generate-01-register.py` 生成过一次"
    "（`--check` 可复核生成关系）；",
    "  //   **真源就是这张表本身**——那个脚本与 `register-block.js.txt` 是已消费的一次性产物，"
    "别拿它们当判据。",
]

EXPECT_TOTAL = 115

# 类别表（单源在守卫里；这里是为了生成时的取值校验与分布对账）
KINDS: dict[str, str] = {
    "block": "顶层块：一屏里自成一块的容器",
    "control": "可点控件",
    "tag": "徽章与标签（不可点）",
    "alert": "语义告示块",
    "modal": "弹层外壳",
    "float": "浮在内容之上的自己的面",
    "doc": "文档与表格语法",
    "editor": "编辑器形状",
    "nonbox": "不是框（圆点 / 字形 / 环 / 滚动条）",
    "placeholder": "透明占位",
}

# 逐条类别（人判；选择器已剥注释、空白归一）
KIND: dict[str, str] = {
    # ---- shell ----
    "header nav button": "control",
    ".card": "block",
    "textarea, input[type=text], input[type=password], select": "control",
    "input[type=search]": "control",
    "button": "control",
    ".banner": "alert",
    ".welcome-card": "alert",
    ".platform-card": "control",
    "#compile-banner.running": "alert",
    "#compile-banner.success": "alert",
    "#compile-banner.fail": "alert",
    "#compile-banner.notool": "alert",
    ".mod-info-btn": "control",
    "#btn-score-export": "control",
    "input[type=checkbox], input[type=radio]": "control",
    "input[type=checkbox]:checked::after": "nonbox",
    "input[type=file]": "control",
    "input[type=file]::file-selector-button": "control",
    "::-webkit-scrollbar-thumb": "nonbox",
    "#btn-code-ai-send": "control",
    "#btn-recent-refresh": "control",
    ".card-step-status": "placeholder",
    # ---- components ----
    ".btn": "control",
    ".chip": "control",
    ".btn-param-ref": "control",
    ".btn-params-reset": "control",
    ".badge.needs-choice-badge": "alert",
    ".spinner": "nonbox",
    ".service-stopped-box": "alert",
    ".toast": "modal",
    ".toast-copy, .toast-action, .wait-cancel": "control",
    # ---- settings ----
    ".env-jump": "control",
    ".settings-stickybar": "float",
    "#tab-settings .error:not(.ok):not(:empty)": "alert",
    # ---- library ----
    ".module-card": "control",
    ".module-card .mc-offtag": "alert",
    ".module-card .mc-info": "control",
    ".module-info-modal": "modal",
    ".module-info-off": "alert",
    ".mi-pins th, .mi-pins td": "doc",
    ".lib-edit-modal": "modal",
    ".lib-chip": "control",
    # ---- generate ----
    ".fix-row": "placeholder",
    ".task-more-menu": "modal",
    ".param-card-head .param-unit-chip": "tag",
    ".group-card.needs-choice": "alert",
    ".topic-preread": "alert",
    ".preread-slot": "alert",
    ".sp-item": "placeholder",
    ".pin-role": "placeholder",
    ".pin-fixed-list .fx": "tag",
    ".pin-warn-list .wx": "alert",
    ".pin-legend .lg": "tag",
    ".pin-menu": "modal",
    ".step-nav .step-dot": "placeholder",
    ".step-nav .step-dot .dot": "nonbox",
    ".gen-overview": "block",
    ".ov-chip": "control",
    ".ov-chip .ov-dot": "nonbox",
    ".ov-actions .ov-fill": "control",
    ".gen-recent": "block",
    ".recent-chip": "placeholder",
    ".recent-platform": "tag",
    ".revise-tab": "control",
    ".revise-tab-badge": "tag",
    ".task-phase": "alert",
    ".task-phase .task-spinner": "nonbox",
    ".tasks-done-line .btn-task-goto-delivery": "control",
    ".res-chip": "tag",
    ".res-view-btn": "control",
    ".res-board-legend .dot": "nonbox",
    ".res-board-legend .res-legend-conflict": "nonbox",
    ".score-chip": "tag",
    ".task-next-hint": "alert",
    ".rc-summary": "block",
    # ---- hwcheck ----
    ".hwcheck-warn": "alert",
    ".hwcheck-check": "placeholder",
    ".hwcheck-recent-row": "placeholder",
    ".hwcheck-order-index": "tag",
    ".hwcheck-section-tag": "tag",
    ".hwcheck-symptom": "control",
    "#tab-hwcheck .hwcheck-band-num": "tag",
    "#tab-hwcheck .hwcheck-jump": "control",
    # ---- master ----
    ".stepper .step .dot": "nonbox",
    ".prog-badge": "alert",
    ".master-file-btn": "control",
    ".master-health-pill": "placeholder",
    # ---- reference ----
    ".ref-files-modal": "modal",
    ".ref-files-filter": "control",
    # ---- changelog ----
    ".rel-tag.tag-other": "tag",
    # ---- topic ----
    ".topic-card": "control",
    ".topic-year": "tag",
    ".topic-page img": "doc",
    # ---- code ----
    ".code-pane-action, .code-compile-head button, .code-statusbar button": "control",
    ".code-kbd": "tag",
    ".code-bottom-tab": "placeholder",
    ".code-ai-preview-btn": "control",
    ".code-ai-chat-input": "control",
    ".code-change-badge.b-removed": "tag",
    ".code-tab": "placeholder",
    ".code-tab-ro": "tag",
    ".code-back-preview, .code-md-edit": "control",
    ".code-view::-webkit-scrollbar-thumb": "placeholder",
    ".code-ro-note": "float",
    ".code-zoom-badge": "float",
    ".code-ctx-menu": "modal",
    ".quick-open-box": "modal",
    ".code-tree-name-input": "control",
    ".code-md-preview th, .code-md-preview td": "doc",
    ".code-md-preview img": "doc",
    ".code-wrap": "editor",
    ".code-zoom": "editor",
    # ---- guide ----
    ".guide-tab": "control",
    ".guide-table th": "doc",
    ".guide-table td": "doc",
}


def main() -> int:
    text = read_page()
    scopes = load_scopes()
    rows = full_borders(text)
    if len(rows) != EXPECT_TOTAL:
        raise SystemExit(f"盘上现算 {len(rows)} 条，与申报的 {EXPECT_TOTAL} 不等——停手")

    entries: list[tuple[str, str, str, str]] = []  # (scope, stripped, kind, value)
    seen: collections.Counter[tuple[str, str]] = collections.Counter()
    for line, sel, value in rows:
        clean = " ".join(strip_lead_comments(sel).split())
        scope = scope_of(sel, scopes)
        seen[(scope, clean)] += 1
        if clean not in KIND:
            raise SystemExit(f"盘上这条没有类别：[{scope}] {clean}")
        entries.append((scope, clean, KIND[clean], value))

    dupes = {k: v for k, v in seen.items() if v > 1}
    if dupes:
        raise SystemExit(f"同一作用域里选择器重复（认人键不成立）：{dupes}")
    used = {clean for _, clean, _, _ in entries}
    extra = set(KIND) - used
    if extra:
        raise SystemExit(f"KIND 表里多出盘上没有的选择器（表比盘多）：{sorted(extra)}")
    bad = {k for k in KIND.values() if k not in KINDS}
    if bad:
        raise SystemExit(f"未知类别：{sorted(bad)}")

    dist = collections.Counter(k for _, _, k, _ in entries)
    empt = set(KINDS) - set(dist)
    if empt:
        raise SystemExit(f"空类别（判据退化成摆设）：{sorted(empt)}")

    # ---- 生成守卫里那段表 ----
    # **按作用域分组**（组序 = 该作用域在盘上首次出现的顺序，组内保持盘上顺序）：
    # 表读起来就是"哪一页留了哪些框"。⚠ 别按行号顺序直接铺——盘上行号是交错的
    # （shell / components / settings / shell / library …），那不叫分组（第一版就这么错了）。
    order = list(dict.fromkeys(scope for scope, _, _, _ in entries))
    lines = ["const BORDER_REGISTER = [", *HEADER]
    written: list[tuple[str, str, str]] = []  # 写出去的那份（**分组后**的顺序）
    for scope in order:
        lines.append(f"  // ---- {scope}（{sum(1 for s, _, _, _ in entries if s == scope)} 条）----")
        for s, clean, kind, _value in entries:
            if s == scope:
                lines.append(f'  ["{s}", "{clean}", "{kind}"],')
                written.append((s, clean, kind))
    lines.append("];")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    dist = collections.Counter(k for _, _, k, _ in entries)
    vis = sum(n for k, n in dist.items() if k not in ("placeholder", "nonbox"))
    nonbox = dist["placeholder"] + dist["nonbox"]

    if CHECK:
        # `--check`：守卫里那张表必须与本脚本**写出去的**那份逐条相同
        # ⚠ 比的是 `written`（分组后），不是 `entries`（盘上顺序）——第一版拿 `entries` 比，
        #   集合相等、顺序不同，于是报了 DIFF 却一行差异也打印不出来（诊断自己是瞎的）。
        in_guard = load_border_register()
        if in_guard == written:
            print(f"[OK] 守卫里的登记簿与本脚本生成结果逐条相同（{len(written)} 条，含顺序）")
            return 0
        print(f"[DIFF] 守卫 {len(in_guard)} 条 vs 生成 {len(written)} 条")
        for i, (a, b) in enumerate(zip(in_guard, written)):
            if a != b:
                print(f"  首个不同在第 {i + 1} 条：守卫 {a} / 生成 {b}")
                break
        for row in [r for r in written if r not in in_guard][:10]:
            print(f"  只在生成里：{row}")
        for row in [r for r in in_guard if r not in written][:10]:
            print(f"  只在守卫里：{row}")
        return 1

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    print("115 条全部有类别 ✅  类别分布：" + " / ".join(f"{k} {dist[k]}" for k in KINDS))
    print(f"口径分列：可见框 {vis} / 非框 {nonbox}（placeholder {dist['placeholder']} + nonbox {dist['nonbox']}）")
    print(f"守卫表已生成：{OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
