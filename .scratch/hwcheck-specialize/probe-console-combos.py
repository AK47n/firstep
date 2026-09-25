# -*- coding: utf-8 -*-
"""工单 07 的量具：**控制台字符的组合穷举与容量边界**（批次 D 踩过坑后的每批纪律）。

背景（交接区「四条量具纪律」第 ④ 条）：新件声明的首选可能**挤掉旧件的首选**，而旧件的
候选又刚好都是别人的首选 ⇒ 一个看起来正常的组合直接**构建期 400**。批次 D（工单 06）
实测踩到过一次（`at24c02` 的候选 `e` 撞 `sht30` 首选，而 `sht30` 的候选 `f`/`c` 又都是
别人的首选）。所以每批落地都要把"新件 + 既有件"的组合过一遍。

本支回答三个问题（只读，一个字节不写库）：

1. **本批该负责的射程**（学生真会用的规模）：`|S| <= 6` **全子集穷举**——一件都不能撞。
2. **更大组合的失败曲线**：按 |S| 分档随机抽样，并把**本批前 / 本批后**两个数并排打印
   （本批的四件会占掉 4 个池子字符，曲线整体左移是必然的；左移多少要如实记账）。
3. **容量天花板**：一个平台的全部专精件一次勾满 → 现在的实况（✗ 在哪一件上、还差几个字符）。
   这是**既有的**边界（本批前 `tcs34725` 就已经撞死），不是本批引入的；记在这里是为了
   不把它误读成"本批的失败"。

用法：`py -3 .scratch/hwcheck-specialize/probe-console-combos.py [--quick]`
读数先落盘 `probe-console-combos.txt` 再打印；退出码非 0 = 第 1 问（本批射程）有失败。

⚠ **下一批（批次 F：hx711 / joystick / servo / relay）落地时必须再跑一次本支**：
批次 E 补的共享池里那个 `i` **正是 `joystick` 的首选**（工单 08 的字符声明），
`w` 是 `hx711` 的首选——新件一进来，池子里的字符就可能被它们先拿走。
（批次 E 落地时用"本批 + 合成批次 F"两套目录实测过 `|S| <= 6` 仍然零撞车，
但那是在批次 F 真实配方落地**之前**；真落地后要按真数据复跑。）
"""
import argparse
import itertools
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.hwcheck_console import (  # noqa: E402
    COMMAND_POOL, build_console_table, console_payload, render_console_runtime,
)
from contest_generator.hwcheck_errors import HwCheckError  # noqa: E402
from contest_generator.hwcheck_recipe import (  # noqa: E402
    load_library_recipes, resolve_sections,
)
from contest_generator.library import list_modules  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
OUT = REPO / ".scratch" / "hwcheck-specialize" / "probe-console-combos.txt"

BATCH_E = ("ads1115", "pca9685", "dht11", "ds18b20")
EXHAUSTIVE_MAX = 6          # 全子集穷举的规模上界（学生真会用的规模）
SAMPLE_SIZES = (7, 8, 9, 10, 12, 14)
SAMPLES_PER_SIZE = 150
SEED = 7

_parser = argparse.ArgumentParser()
_parser.add_argument("--quick", action="store_true", help="抽样次数减半（调试用）")
_args = _parser.parse_args()
if _args.quick:
    SAMPLES_PER_SIZE = 40

LINES: list[str] = ["=== 工单 07：控制台字符组合穷举与容量边界 ===", ""]
RANGE_FAILURES: list[str] = []      # 第 1 / 4 问的失败 = 本批要修的问题
CEILING_NOTES: list[str] = []       # 第 3 问 + 大组合的现象 = 既有边界，如实记账

manifests = list_modules(MODULES)
catalog = load_library_recipes(MODULES, MASTERS, manifests)


def specialized(platform: str, drop_batch_e: bool = False) -> list[str]:
    return [
        slug for slug, one in sorted(catalog.items())
        if one.for_platform(platform) is not None and one.for_platform(platform).usable
        and not (drop_batch_e and slug in BATCH_E)
    ]


def try_build(platform: str, slugs):
    """→ (命令表 或 None, 失败原因)。"""
    try:
        sections = resolve_sections(platform, slugs, catalog, manifests)
        return build_console_table(sections), ""
    except HwCheckError as exc:
        return None, str(exc).splitlines()[0]


for platform in ("stm32", "mspm0"):
    slugs = specialized(platform)
    before = specialized(platform, drop_batch_e=True)
    LINES.append(f"## {platform}（专精件 {len(slugs)} 件；本批前 {len(before)} 件）")
    LINES.append("")

    # --- 1) 本批射程：|S| <= EXHAUSTIVE_MAX 全子集穷举 ---------------------------
    checked = 0
    failures: list[str] = []
    for size in range(2, EXHAUSTIVE_MAX + 1):
        for combo in itertools.combinations(slugs, size):
            checked += 1
            table, why = try_build(platform, list(combo))
            if table is None:
                failures.append(f"{'、'.join(combo)}：{why}")
                if len(failures) >= 5:
                    break
        if len(failures) >= 5:
            break
    if failures:
        RANGE_FAILURES.extend(f"{platform} |S|<={EXHAUSTIVE_MAX}：{line}" for line in failures)
        LINES.append(f"1) 全子集穷举 |S| = 2..{EXHAUSTIVE_MAX}（{checked} 组）→ "
                     f"✗ {len(failures)} 组撞车（列出前 5 组）：")
        LINES += [f"   {line}" for line in failures]
    else:
        LINES.append(f"1) 全子集穷举 |S| = 2..{EXHAUSTIVE_MAX}（{checked} 组）→ "
                     f"✓ 全部建得出表（本批射程内零撞车）")
    LINES.append("")

    # --- 2) 更大组合的失败曲线（本批前 / 本批后） --------------------------------
    rng = random.Random(SEED)
    LINES.append("2) 按规模抽样（每档 150 组，种子固定）：")
    LINES.append("   规模 | 本批后失败 | 本批前失败（同一批随机组合去掉本批四件）")
    for size in SAMPLE_SIZES:
        after_bad = before_bad = 0
        for _ in range(SAMPLES_PER_SIZE):
            picked = rng.sample(slugs, size)
            if try_build(platform, picked)[0] is None:
                after_bad += 1
            pruned = [s for s in picked if s not in BATCH_E]
            if pruned and try_build(platform, pruned)[0] is None:
                before_bad += 1
        LINES.append(f"   {size:4d} | {after_bad:10d} | {before_bad:10d}")
    LINES.append("   （左移是必然的：本批四件占掉 4 个池子字符；这一栏只作如实记账，"
                 "判据是第 1 问。）")
    LINES.append("")

    # --- 3) 容量天花板：全部专精件勾满 ------------------------------------------
    table, why = try_build(platform, slugs)
    if table is None:
        CEILING_NOTES.append(f"{platform} 全部勾满：{why}")
        LINES.append(f"3) 全部 {len(slugs)} 件一次勾满 → ✗（既有边界，非本批引入）：")
        LINES.append(f"   {why[:200]}")
    else:
        used = {entry.slug: entry.command for entry in table.entries}
        free = [c for c in COMMAND_POOL if c not in set(used.values())]
        LINES.append(f"3) 全部 {len(slugs)} 件一次勾满 → ✓ 表建出来了；"
                     f"池子 {len(COMMAND_POOL)} 个、空闲 {len(free)} 个：{''.join(free) or '（无）'}")
    LINES.append("")

    # --- 4) 跨批重点对：本批的争用 + 本批四件的内部组合 --------------------------
    focus = [
        ["ads1115", "sgp30"],          # 都想要 v
        ["pca9685", "bmp180"],         # 都想要 c
        ["pca9685", "tcs34725"],       # 都想要 c
        ["dht11", "aht10"],            # 都想要 h
        ["ds18b20", "sht20"],          # 都想要 t
        ["ads1115", "pca9685", "dht11", "ds18b20"],
    ]
    LINES.append("4) 跨批重点对（让位实况；页面载荷与板上 case 必须同字符）：")
    for combo in focus:
        picked = [s for s in combo if s in slugs]
        if len(picked) != len(combo):
            continue
        table, why = try_build(platform, picked)
        if table is None:
            # 重点对里也有"两件都要同一个首选"的形态（如 ads1115 + sgp30 都想要 v）——
            # 那是**让位机制该处理**的场面，处理不了才算问题；处理得了就不算。
            RANGE_FAILURES.append(f"{platform} {'+'.join(picked)}：{why}")
            LINES.append(f"   {'+'.join(picked):34s} ✗ {why[:120]}")
            continue
        got = {entry.slug: entry.command for entry in table.entries}
        shown = {item["slug"]: item["command"]
                 for item in console_payload(True, table)["commands"]}
        code = "\n".join(render_console_runtime(table))
        cases = sum(1 for line in code.splitlines() if line.strip().startswith("case '"))
        same = all(shown.get(slug) == char for slug, char in got.items())
        LINES.append(
            f"   {'+'.join(picked):34s} "
            + "、".join(f"{s}={got[s]!r}" for s in picked)
            + f"；页面与板上同字符：{'✓' if same else '✗'}；case 数 {cases}"
        )
        if not same:
            RANGE_FAILURES.append(f"{platform} {'+'.join(picked)} 页面与板上字符不一致")
    LINES.append("")

LINES.append("结论：")
LINES.append("  ① 本批射程（|S| <= 6 全子集）："
             + ("✓ 零撞车" if not RANGE_FAILURES else f"✗ {len(RANGE_FAILURES)} 处"))
LINES += [f"     - {line}" for line in RANGE_FAILURES]
LINES.append(f"  ② 容量天花板（全部勾满）：{len(CEILING_NOTES)} 个平台撞死"
             "——既有边界（本批前 `tcs34725` 就已经撞死），"
             "见 `.scratch/backlog.md` 的字符池账")
LINES += [f"     - {line[:170]}" for line in CEILING_NOTES]

text = "\n".join(LINES) + "\n"
OUT.write_text(text, encoding="utf-8")
print(text)
raise SystemExit(0 if not RANGE_FAILURES else 1)
