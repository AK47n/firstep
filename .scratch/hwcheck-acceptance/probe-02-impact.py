# -*- coding: utf-8 -*-
"""工单 02 的第一步：**量影响面**（票面硬要求，不许不量就选改哪一侧）。

量四件事（全部走产品单源，不另抄一份解析 / 一份清单）：

1. **重名组台账**：母版 `mspm0.syscfg` 里 `associatedPins[n].$name` 的同名组
   ——`label → 实例清单`（`parse_syscfg` 是唯一解析实现，与 `syscfg_prune`
   的重名判据同一个源）。
2. **每组各实例的消费模块**（`INSTANCE_CONSUMERS` 反查）——决定"这一组撞上时
   学生看到的是哪两件"。
3. **改名代价（mspm0 侧）**：`<实例>_<符号>_PORT/_PIN/_IOMUX` 在**该模块
   mspm0 文件清单**（manifest `platforms.mspm0.files`，单源）里被引用了几处 /
   几个文件——这就是改这一侧要同批改的源码量。SysConfig 生成宏 =
   `<实例>_<符号>_<后缀>`（本机 `Debug/ti_msp_dl_config.h` 实测确认）。
4. **误改风险（stm32 侧）**：同一个字符串在**该模块 stm32 文件清单**里也出现
   （stm32 的 `pin_config.h` 宏 `AHT10_SCL_PIN` 与 SysConfig 宏**同名不同源**）
   ——这些是"改名时一个字都不许动的"处数。

用法：`python .scratch/hwcheck-acceptance/probe-02-impact.py [--out FILE]`
先落盘再打印（本机控制台 GBK）。**只读**——不改库内任何文件。
"""
import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.manifest import ModuleManifest  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.syscfg_instances import INSTANCE_CONSUMERS  # noqa: E402
from contest_generator.syscfg_model import parse_syscfg  # noqa: E402

MASTER = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"
MODULES = REPO / "library" / "modules"


def duplicate_groups() -> dict[str, list[str]]:
    """同名引脚符号 → 用到它的实例清单（行序）。"""
    model = parse_syscfg(MASTER.read_text(encoding="utf-8"))
    by_name: dict[str, list[str]] = {}
    for instance, names in model.pin_names.items():
        for name in names:
            by_name.setdefault(name, []).append(instance)
    return {name: insts for name, insts in by_name.items() if len(insts) > 1}


def count_in(files: list[Path], pattern: re.Pattern[str]) -> tuple[int, list[str]]:
    hits = 0
    where: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found = len(pattern.findall(text))
        if found:
            hits += found
            where.append(f"{path.relative_to(REPO).as_posix()}({found})")
    return hits, where


def manifest_files(slug: str, platform: str) -> list[Path]:
    """该模块该平台的文件清单（manifest 单源）。"""
    path = MODULES / slug / "manifest.json"
    if not path.is_file():
        return []
    manifest = ModuleManifest.load(MODULES / slug)
    entry = manifest.platforms.get(platform)
    if entry is None:
        return []
    return [MODULES / slug / name for name in entry.files]


def scan_other_trees(groups: dict[str, list[str]]) -> str:
    """模块目录之外（src / tests / masters / tools / docs）的引用面。

    这些引用是"改名要同批改"的第二块：测试里钉死的生成结果、母版其它文件、
    生成器里的常量。**扫描根不含 `library/modules`**，所以这里把 `_PIN` 也一起数
    （stm32 的同名 `_PIN` 宏只出现在 `library/modules/**` 里，不在本轮射程）。
    """
    pairs = [
        (instance, label) for label, insts in groups.items() for instance in insts
    ]
    pattern = re.compile(
        "|".join(
            re.escape(f"{i}_{n}") + r"(?:_PORT|_PIN|_IOMUX)\b" for i, n in pairs
        )
    )
    hits: dict[str, int] = {}
    for root in ("src", "tests", "library/masters", "tools", "docs"):
        for path in sorted((REPO / root).rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in (".py", ".c", ".h", ".json", ".md", ".js", ".mjs", ".syscfg"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            found = pattern.findall(text)
            if found:
                hits[path.relative_to(REPO).as_posix()] = len(found)
    out = ["=== 模块目录之外的引用面（src / tests / masters / tools / docs）==="]
    if not hits:
        out.append("（无——模块目录之外没有引用这些宏）")
    for rel in sorted(hits, key=lambda p: (-hits[p], p)):
        out.append(f"     {hits[rel]:>3} 处 → {rel}")
    out.append(f"合计：{sum(hits.values())} 处 / {len(hits)} 个文件")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8，先落盘再打印）")
    args = parser.parse_args()

    groups = duplicate_groups()
    lines: list[str] = []
    lines.append("=== 母版 mspm0.syscfg 引脚符号重名台账（$name 全局唯一判据）===")
    lines.append(f"文件：{MASTER.relative_to(REPO).as_posix()}")
    lines.append(f"重名组数：{len(groups)}")
    lines.append("")

    mspm0_instances = 0
    mspm0_hits = 0
    mspm0_files: dict[str, int] = {}
    stm32_lookalike = 0
    for label in sorted(groups):
        insts = groups[label]
        lines.append(f"── 符号 {label}：{len(insts)} 个实例")
        for instance in insts:
            pattern = re.compile(
                re.escape(f"{instance}_{label}") + r"(?:_PORT|_PIN|_IOMUX)\b"
            )
            slugs = INSTANCE_CONSUMERS.get(instance, ())
            m_files = [p for slug in slugs for p in manifest_files(slug, PLATFORM_MSPM0)]
            s_files = [p for slug in slugs for p in manifest_files(slug, PLATFORM_STM32)]
            m_hits, m_where = count_in(m_files, pattern)
            s_hits, _ = count_in(s_files, pattern)
            mspm0_instances += 1
            mspm0_hits += m_hits
            for item in m_where:
                rel = item.split("(")[0]
                mspm0_files[rel] = mspm0_files.get(rel, 0) + 1
            stm32_lookalike += s_hits
            lines.append(
                f"     {instance:<14} 模块={'/'.join(slugs) or '（未登记）':<22}"
                f" mspm0 侧引用 {m_hits:>2} 处："
                + ("，".join(m_where) if m_where else "—（不改源码）")
            )
        lines.append("")

    lines.append("=== 影响面汇总（mspm0 侧 = 改名要同批改的）===")
    lines.append(f"撞名实例总数：{mspm0_instances}")
    lines.append(f"mspm0 源码引用合计：{mspm0_hits} 处 / {len(mspm0_files)} 个文件")
    for rel in sorted(mspm0_files, key=lambda p: (-mspm0_files[p], p)):
        lines.append(f"     {mspm0_files[rel]:>2} 个实例的宏 → {rel}")
    lines.append("")
    lines.append(f"=== 误改风险（stm32 侧同名宏，一个字都不许动）：{stm32_lookalike} 处 ===")
    lines.append("（stm32 的 pin_config.h 里 `AHT10_SCL_PIN` 这类宏与 SysConfig 生成宏")
    lines.append("  同名不同源——按文件清单区分平台，才不会顺手改错一片）")
    lines.append("")
    lines.append(scan_other_trees(groups))

    report = "\n".join(lines) + "\n"

    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")     # 先落盘
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
