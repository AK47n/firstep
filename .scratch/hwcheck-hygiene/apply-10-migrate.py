#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/10：把 `fx/hwcheck.js`（09 留的过渡态 barrel）的消费者迁到六件，再删 barrel。

用法：

    python .scratch/hwcheck-hygiene/apply-10-migrate.py            # 干跑：只核对与打印
    python .scratch/hwcheck-hygiene/apply-10-migrate.py --write    # 落盘（含删 barrel）

## 为什么是一支脚本

barrel 的消费面上有 **90 来个具名导入**（`ui/hwcheck.js` 一条大 import、`tests/js/hwcheck.test.mjs`
一条大 import、`ui/generate-recommend.js` 一条单词导入），要按**名字的归属**劈成六条。
手抄一遍的失败方式是静默的：抄漏一个名字 = 那个导出变成"零消费者"（判据 D 红），
抄错模块名 = 运行时报"does not provide an export named"。所以：

* 归属表**从六件现算**（`^export (function|const) NAME`），不写死名单；
* 每个消费者改完**自校验**：迁移前后具名集合必须逐名相同（多一个少一个都当场退出）；
* 注释里那些 `fx/hwcheck.js` 引用（文档漂移）用一张**显式替换表**处理，每条都要求命中指定次数。

`fx/hwcheck.js` 本身在 `--write` 时删除（09 的验收标准说它只活一笔提交）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FX = REPO / "src" / "contest_generator" / "static" / "js" / "fx"
BARREL = FX / "hwcheck.js"

# 六件的顺序 = 职责顺序（也是 barrel 里再导出的顺序）
MODULES = [
    "hwcheck-state.js", "hwcheck-project.js", "hwcheck-wiring.js",
    "hwcheck-plan.js", "hwcheck-triage.js", "hwcheck-handoff.js",
]

# 消费者：(文件, 前导注释, 缩进)
CONSUMERS = [
    (REPO / "src/contest_generator/static/js/ui/hwcheck.js",
     "// 纯件按职责分六件（工单 hwcheck-hygiene/09–10 拆的）：状态 / 工程 / 器件与接线 /\n"
     "// 计划 / 排障 / 衔接——每一件的职责与依赖方向见它自己的文件头。",
     ""),
    (REPO / "tests/js/hwcheck.test.mjs",
     "// 六件纯函数（工单 hwcheck-hygiene/09–10 把原 fx/hwcheck.js 按职责拆开）",
     ""),
    (REPO / "src/contest_generator/static/js/ui/generate-recommend.js", None, ""),
]

# 换行与大小：**逐字节读、按原换行写回**。本工作树 LF / CRLF 混装（`ui/hwcheck.js` 是
# CRLF、`tests/js/*.test.mjs` 是 LF），而 `Path.read_text` 会把 CRLF 归一成 LF——
# 第一版就用它做 I/O，于是读数报的是"剥掉 CRLF 后的字符数"，从盘上复现不出来
#（Standards 轴评审实测：盘上 68532 B / 1400 CRLF，脚本报 67132）。现在读进来到处理完
# 一律 LF、落盘按各文件原来的换行还原，报告也改成**字节数**。
EOLS: dict[str, str] = {}
SIZES: dict[str, int] = {}


def load(rel: str) -> str:
    """逐字节读 → LF 文本（原换行与原始字节数记在 EOLS / SIZES 里）。"""
    raw = (REPO / rel).read_bytes()
    EOLS[rel] = "\r\n" if b"\r\n" in raw else "\n"
    SIZES[rel] = len(raw)
    return raw.decode("utf-8").replace("\r\n", "\n")


def save(rel: str, text: str) -> int:
    """按原换行写回（逐字节），→ 写出的字节数。"""
    data = text.replace("\n", EOLS[rel]).encode("utf-8")
    (REPO / rel).write_bytes(data)
    return len(data)

# 注释 / 文档里的旧路径 → 新家（逐条要求命中次数，防止"改了一处漏了一处"）
RENAMES = [
    ("src/contest_generator/static/js/ui/hwcheck.js",
     "// 单向依赖：ui → fx / app（纯件在 fx/hwcheck.js，本文件只读状态、写 DOM、",
     "// 单向依赖：ui → fx / app（纯件在 fx/hwcheck-{state,project,wiring,plan,triage,handoff}.js，\n"
     "// 本文件只读状态、写 DOM、", 1),
    ("src/contest_generator/static/js/ui/hwcheck.js",
     "// 产物区壳由 fx/hwcheck.js 单源给出", "// 产物区壳由 fx/hwcheck-state.js 单源给出", 1),
    ("src/contest_generator/static/js/ui/generate-recommend.js",
     "// 判据在 `fx/hwcheck.js` 的 `hwcheckHandoffMerge`",
     "// 判据在 `fx/hwcheck-handoff.js` 的 `hwcheckHandoffMerge`", 1),
    ("tests/js/hwcheck.test.mjs",
     '"ui 不得手写 data-hwcheck-code 标记（壳的单源在 fx/hwcheck.js）")',
     '"ui 不得手写 data-hwcheck-code 标记（壳的单源在 fx/hwcheck-state.js）")', 1),
    ("tests/js/hwcheck.test.mjs",
     'test("ui 不手拼工程面板 / 清单 / 最近的壳（壳的单源在 fx/hwcheck.js）"',
     'test("ui 不手拼工程面板 / 清单 / 最近的壳（壳的单源在 fx/hwcheck-project.js）"', 1),
    ("tests/js/hwcheck.test.mjs",
     '"ui 不得手拼这些壳的样式标记（单源在 fx/hwcheck.js）")',
     '"ui 不得手拼这些壳的样式标记（单源在 fx/hwcheck-project.js）")', 1),
    ("tests/js/hwcheck.test.mjs",
     '"带值的 data-* 标记只许出现在选择器里（壳的唯一出处是 fx/hwcheck.js）")',
     '"带值的 data-* 标记只许出现在选择器里（壳的唯一出处是 fx/hwcheck-project.js）")', 1),
    ("tests/js/hwcheck.test.mjs",
     '"ui 不得手拼接线表（单源在 fx/hwcheck.js）")',
     '"ui 不得手拼接线表（单源在 fx/hwcheck-wiring.js）")', 1),
    ("tests/js/hwcheck.test.mjs",
     '"板载共享标记的单源在 fx/hwcheck.js")',
     '"板载共享标记的单源在 fx/hwcheck-wiring.js")', 1),
    ("tests/js/hwcheck.test.mjs",
     '"[专精] 标记的单源在 fx/hwcheck.js")',
     '"[专精] 标记的单源在 fx/hwcheck-plan.js")', 1),
    ("tests/js/hwcheck.test.mjs",
     '"文案单源在 fx/hwcheck.js，ui 只渲染")',
     '"文案单源在 fx/hwcheck-project.js，ui 只渲染")', 1),
    ("tests/browser/hwcheck.spec.mjs",
     "// 工单 ci-gate-fixes/08：这条用例的**前提是真工具链**——`fx/hwcheck.js` 的 `ready` 门",
     "// 工单 ci-gate-fixes/08：这条用例的**前提是真工具链**——`fx/hwcheck-project.js` 的 `ready` 门", 1),
    ("src/contest_generator/static/index.html",
     '这句保证"第一眼就知道这批结论的分量"。文案在 fx/hwcheck.js 的',
     '这句保证"第一眼就知道这批结论的分量"。文案在 fx/hwcheck-project.js 的', 1),
    ("src/contest_generator/static/index.html",
     '文案在 fx/hwcheck.js 的 hwcheckDroppedNoteHTML',
     '文案在 fx/hwcheck-state.js 的 hwcheckDroppedNoteHTML', 1),
    ("src/contest_generator/static/index.html",
     "fx/hwcheck.js 的 hwcheckHandoffHTML", "fx/hwcheck-handoff.js 的 hwcheckHandoffHTML", 1),
    ("src/contest_generator/webapp.py",
     "（见 fx/hwcheck.js hwcheckRequestPayload）", "（见 fx/hwcheck-state.js hwcheckRequestPayload）", 1),
    ("src/contest_generator/hwcheck.py",
     "# `fx/hwcheck.js` 的 `HWCHECK_CHANNEL_KEYS` 镜像",
     "# `fx/hwcheck-state.js` 的 `HWCHECK_CHANNEL_KEYS` 镜像", 1),
    ("tests/test_hwcheck_board.py",
     "（`fx/hwcheck.js`），所以首选被别的器件占用", "（`fx/hwcheck-plan.js`），所以首选被别的器件占用", 1),
    ("tests/test_hwcheck_recipe.py",
     "（`fx/hwcheck.js` 的 `hwcheckUnverifiedNoteHTML`）同理",
     "（`fx/hwcheck-project.js` 的 `hwcheckUnverifiedNoteHTML`）同理", 1),
    ("tests/test_js_gate.py",
     '"src/contest_generator/static/js/fx/hwcheck.js",',
     '"src/contest_generator/static/js/fx/hwcheck-state.js",   # 前端资产（09 拆出的六件之一）', 1),
]


def owner_map() -> dict[str, str]:
    """导出名 → 它所在的件（从六件现算）。"""
    owner: dict[str, str] = {}
    for name in MODULES:
        text = (FX / name).read_text(encoding="utf-8")
        for m in re.finditer(r"(?m)^export (?:function|const) ([A-Za-z_$][\w$]*)", text):
            assert m.group(1) not in owner, f"{m.group(1)} 在两件里都导出了"
            owner[m.group(1)] = name
    assert len(owner) >= 70, f"只认出 {len(owner)} 个导出 —— 取数面失效？"
    return owner


BLOCK_RE = re.compile(
    r"import\s*\{([^}]*)\}\s*from\s*\"([^\"]*fx/hwcheck\.js)\"\s*;")


def names_of(block: str) -> list[str]:
    out = []
    for part in block.split(","):
        clean = re.sub(r"//[^\n]*", "", part).strip()
        if clean:
            out.append(clean)
    return out


def render(spec_prefix: str, names: list[str], indent: str) -> str:
    rows = [names[i:i + 3] for i in range(0, len(names), 3)]
    lines = ["import {"]
    lines += [f"{indent}  " + ", ".join(r) + "," for r in rows]
    lines.append(f'{indent}}} from "{spec_prefix}{{FILE}}";')
    return "\n".join(lines)


def migrate(owner: dict[str, str]) -> dict[str, str]:
    """→ {相对路径: 新文本}；每个消费者迁移前后具名集合逐名相同。"""
    out: dict[str, str] = {}
    for path, preamble, indent in CONSUMERS:
        rel = path.relative_to(REPO).as_posix()
        text = load(rel)
        m = BLOCK_RE.search(text)
        if not m:
            continue
        before = names_of(m.group(1))
        spec_prefix = m.group(2)[: -len("hwcheck.js")]
        by_module: dict[str, list[str]] = {name: [] for name in MODULES}
        for name in before:
            assert name in owner, f"{path.name} 导入的 {name} 在六件里都没有 —— 归属表失效？"
            by_module[owner[name]].append(name)
        blocks = []
        if preamble:
            blocks.append(preamble)
        for name in MODULES:
            if by_module[name]:
                blocks.append(render(spec_prefix, by_module[name], indent).replace("{FILE}", name))
        new_text = text[: m.start()] + "\n".join(blocks) + text[m.end():]
        after = []
        for m2 in BLOCK_RE.finditer(new_text):
            after += names_of(m2.group(1))
        assert after == [], "迁移后仍有指向 barrel 的 import"
        after = re.findall(r'from "[^"]*fx/(hwcheck-[a-z]+)\.js"', new_text)
        assert after, f"{path.name} 迁移后没有任何 fx/hwcheck-*.js 的 import"
        moved = sorted(before)
        now = sorted(sum((by_module[n] for n in MODULES), []))
        assert moved == now, f"{path.name} 具名集合变了：{set(moved) ^ set(now)}"
        # 键一律用 **POSIX 分隔**：RENAMES 那张表写的是 `src/...`，而 Windows 上
        # `str(Path.relative_to)` 给的是 `src\...`——两种键指向同一个文件，会让
        # "合成一次写"退化成"写两遍、后一遍覆盖前一遍"（第二版实测踩到）。
        out[rel] = new_text
    return out


def renames(plan: dict[str, str]) -> list[tuple[str, str]]:
    """把注释 / 文档里的旧路径改掉；`plan` = 已算好的 import 迁移结果（同一份文本上继续改）。

    ⚠ 两支变换必须**合成一份文本再一次落盘**：第一版把 import 迁移与注释替换各自算一份、
    按列表顺序写盘，同一个文件被写了两遍——后一遍（基于盘上原文算的）把前一遍覆盖掉，
    于是 `ui/hwcheck.js` 的 import 块根本没迁（干跑读不出来，`--write` 后才现形）。
    """
    out = []
    for rel, old, new, times in RENAMES:
        text = plan.get(rel)
        if text is None:
            text = load(rel)
        got = text.count(old)
        assert got == times, f"{rel}：锚点命中 {got} 次（应 {times}）—— {old[:40]!r}"
        text = text.replace(old, new)
        if old in new:
            raise SystemExit(f"{rel}：替换目标是原文的前缀，会命中自己 —— {old[:40]!r}")
        plan[rel] = text
        out.append((rel, text))
    return out


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="hwcheck-hygiene/10：迁移 barrel 的消费者并删 barrel")
    ap.add_argument("--write", action="store_true", help="落盘（默认只干跑核对）")
    args = ap.parse_args()

    owner = owner_map()
    print(f"归属表（从六件现算）：{len(owner)} 个导出")
    for name in MODULES:
        got = [k for k, v in owner.items() if v == name]
        print(f"  {name:22s} {len(got):2d} 个")

    print("\n消费者：")
    plan = migrate(owner)
    for rel, text in plan.items():
        print(f"  {rel:56s} {SIZES[rel]:6d} → {len(text.replace(chr(10), EOLS[rel]).encode('utf-8')):6d} B"
              f"  （换行 {EOLS[rel]!r}）")

    print("\n注释 / 文档里的旧路径：")
    renames(plan)
    for rel, _old, _new, _n in RENAMES:
        print(f"  {rel}")

    barrel = BARREL.read_text(encoding="utf-8")
    print(f"\nbarrel：{BARREL.relative_to(REPO)}（{len(barrel)} B，{barrel.count('from \"')} 条再导出）"
          f" —— {'待删除' if args.write else '干跑不删'}")

    if args.write:
        for rel, text in plan.items():
            save(rel, text)
        BARREL.unlink()
        print(f"\n[落盘] {len(plan)} 个文件（import 迁移 ＋ 注释替换合成一次写、按原换行逐字节写回）、"
              f"已删除 fx/hwcheck.js")
    else:
        print("\n（干跑：没写盘。加 --write 落盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
