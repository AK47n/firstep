# -*- coding: utf-8 -*-
"""工单 01 的量具之一：**`ti_msp_dl_config.h` 到底提供哪些函数**（构建期生成的头，
母版里没有这个文件——门禁按"头文件里有没有这个名字"判，于是判不到它）。

为什么必须量：修法候选①是"把该符号纳入 mspm0 的已知接口面"，而接口面要**精确**
（不是 `SYSCFG_DL_*` 前缀白名单——那等于放行错名）。所以要问清楚：

* 哪些 `SYSCFG_DL_*` 是**恒有**的（与选中集无关）；
* 哪些是**按实例**生成的（`SYSCFG_DL_OLED_init` 这种——名字随选中集变）。

口径：扫描本机真产物头（`.scratch/**/matrix*/**/Debug/ti_msp_dl_config.h`），
按"出现它的工程数 / 工程总数"分恒有与按实例两类；再与同目录 syscfg 里的实例名对表。

用法：`python .scratch/hwcheck-acceptance/probe-01-symbol-surface.py [--out FILE]`
只读，不改任何文件。
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DECL = re.compile(r"^\s*(?:void|bool|int)\s+(SYSCFG_DL_\w+)\s*\(", re.MULTILINE)
INSTANCE_DECL = re.compile(r"^\s*const\s+(\w+)\s*=", re.MULTILINE)


def find_headers() -> list[Path]:
    roots = [REPO / ".scratch", REPO / "library"]
    out: list[Path] = []
    for root in roots:
        if root.is_dir():
            out.extend(sorted(root.rglob("ti_msp_dl_config.h")))
    return out


def instances_near(header: Path) -> set[str]:
    """同工程里活着的实例名（取同目录/工程根的 syscfg；找不到就算空）。"""
    project = header.parent.parent
    for candidate in (project / "mspm0.syscfg", project / "empty.syscfg"):
        if candidate.is_file():
            return set(INSTANCE_DECL.findall(candidate.read_text(encoding="utf-8")))
    return set()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    headers = find_headers()
    seen: Counter[str] = Counter()
    per_project: list[tuple[Path, list[str]]] = []
    for header in headers:
        try:
            text = header.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names = sorted(set(DECL.findall(text)))
        if not names:
            continue
        per_project.append((header, names))
        for name in names:
            seen[name] += 1

    total = len(per_project)
    lines = [
        "=== 工单 01 量具：`ti_msp_dl_config.h` 的函数面（本机真产物扫描）===",
        f"扫到 {total} 份构建期生成的头（.scratch/** 与 library/** 下的真产物）",
        "",
        "出现次数 / 总数——**恒有**的（= 与选中集无关）：",
    ]
    always: list[str] = []
    sometimes: dict[str, list[str]] = defaultdict(list)
    for header, names in per_project:
        for name in names:
            if seen[name] == total:
                always.append(name)
            else:
                sometimes[name].append(
                    str(header.parent.parent.relative_to(REPO).as_posix())
                )
    for name in sorted(set(always)):
        lines.append(f"  {seen[name]:>3}/{total}  {name}")

    lines.append("")
    lines.append("**按实例**生成的（名字随选中集变）——逐条给出一个出现它的工程：")
    for name in sorted(sometimes):
        where = sometimes[name][0]
        lines.append(f"  {seen[name]:>3}/{total}  {name:<34} 例：{where}")

    lines.append("")
    lines.append("=== 与实例名的关系（抽一份看）===")
    if per_project:
        header, names = per_project[0]
        insts = instances_near(header)
        lines.append(f"工程：{header.parent.parent.relative_to(REPO).as_posix()}")
        lines.append(f"  活着的实例：{'、'.join(sorted(insts)) or '（读不到 syscfg）'}")
        lines.append(
            "  该工程里按实例的 init："
            + "、".join(
                n for n in names
                if n not in set(always) and n.startswith("SYSCFG_DL_")
            )
        )
        lines.append(
            "  判据：`SYSCFG_DL_<实例>_init` 的 <实例> 必须在该工程的实例集里"
            "（不选中的实例那个 init 不会生成 → 调它就是真错，门禁该红）"
        )

    report = "\n".join(lines) + "\n"
    path = Path(args.out) if args.out else Path(__file__).with_suffix(".txt")
    path.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
