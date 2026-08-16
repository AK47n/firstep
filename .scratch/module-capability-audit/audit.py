"""模块能力盘点（只读）：扫描 library/modules + stm32 母版内嵌头 → report.md。

用法：python audit.py
不改任何 library/src/tests 文件；输出 .scratch/module-capability-audit/report.md。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.skeleton import extract_header_functions  # noqa: E402

MODULES = REPO / "library" / "modules"
STM32_MASTER = REPO / "library" / "masters" / "stm32"
OUT = Path(__file__).resolve().parent / "report.md"

# 空 files = 实现内嵌母版：盘点 API 时用母版头补齐（manifest notes 单源）
EMBEDDED_STM32_HEADERS = {
    "delay": ("ml_libs/ml_delay.h",),
    "led": ("ml_libs/ml_led.h",),
    "oled": ("ml_libs/ml_oled.h",),
}


def load_manifests() -> list[dict]:
    out = []
    for d in sorted(MODULES.iterdir()):
        if d.is_dir():
            data = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            data["_dir"] = d
            out.append(data)
    return out


def header_text(slug: str, rel: str) -> str:
    return (MODULES / slug / rel).read_text(encoding="utf-8", errors="replace")


def api_names_from_texts(texts: list[str]) -> set[str]:
    names: set[str] = set()
    for text in texts:
        names |= extract_header_functions([f"### audit\n{text}"])
    return names


def platform_api(m: dict, platform: str) -> set[str]:
    entry = m["platforms"].get(platform)
    if entry is None:
        return set()
    headers = [rel for rel in entry.get("files", []) if rel.lower().endswith(".h")]
    if not headers and platform == "stm32" and m["slug"] in EMBEDDED_STM32_HEADERS:
        headers = list(EMBEDDED_STM32_HEADERS[m["slug"]])
        texts = [(STM32_MASTER / h).read_text(encoding="utf-8", errors="replace") for h in headers]
        return api_names_from_texts(texts)
    return api_names_from_texts([header_text(m["slug"], h) for h in headers])


def pin_count(entry: dict | None) -> int:
    if not entry:
        return 0
    return len(entry.get("pins", []))


def main() -> None:
    manifests = load_manifests()
    lines: list[str] = []
    lines.append("# 模块能力盘点报告\n")
    lines.append("> 只读盘点，数据源：library/modules/*/manifest.json + 模块 .h + stm32 内嵌母版头。\n")

    # 平台条目统计
    by_platform: dict[str, list[dict]] = {}
    for m in manifests:
        for platform, entry in m["platforms"].items():
            by_platform.setdefault(platform, []).append((m, entry))
    lines.append("## 1. 平台覆盖与验证状态\n")
    lines.append("| 平台 | 条目数 | verified | unverified | 空 files（内嵌母版） | hardware_bound |")
    lines.append("|---|---|---|---|---|---|")
    for platform in sorted(by_platform):
        rows = by_platform[platform]
        verified = sum(1 for _, e in rows if e.get("verified"))
        empty = sum(1 for _, e in rows if not e.get("files"))
        hb = sum(1 for _, e in rows if e.get("hardware_bound"))
        lines.append(f"| {platform} | {len(rows)} | {verified} | {len(rows)-verified} | {empty} | {hb} |")
    lines.append("")

    single = {}
    for platform in ("stm32", "mspm0"):
        missing = [m["slug"] for m in manifests if platform not in m["platforms"]]
        single[platform] = missing
    lines.append("单平台模块（缺对方平台版本）：")
    lines.append(f"- 缺 mspm0（仅 stm32）：{', '.join(single['mspm0']) or '无'}")
    lines.append(f"- 缺 stm32（仅 mspm0）：{', '.join(single['stm32']) or '无'}")
    lines.append("")

    # 全库总表
    lines.append("## 2. 模块 × 平台总表\n")
    lines.append("| slug | deps | stm32 files | stm32 verified | stm32 pins | mspm0 files | mspm0 verified | mspm0 pins |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for m in manifests:
        slug = m["slug"]
        deps = ", ".join(m.get("dependencies", [])) or "-"
        st = m["platforms"].get("stm32")
        ms = m["platforms"].get("mspm0")
        def fmt(entry):
            if entry is None:
                return "-"
            n = len(entry.get("files", []))
            return "内嵌" if n == 0 else str(n)
        lines.append(
            f"| {slug} | {deps} | {fmt(st)} | {'✓' if st and st.get('verified') else '-'} | {pin_count(st)} | "
            f"{fmt(ms)} | {'✓' if ms and ms.get('verified') else '-'} | {pin_count(ms)} |"
        )
    lines.append("")

    # 双平台 API 集合差
    lines.append("## 3. 双平台 API 集合差\n")
    lines.append("> stm32 空 files 模块用内嵌母版头补齐（delay→ml_delay.h、led→ml_led.h、oled→ml_oled.h）。")
    lines.append("> 名字集合来自函数声明 + 函数式宏（与骨架自检同提取器）。\n")
    lines.append("| slug | stm32 独有 | mspm0 独有 | 共同 |")
    lines.append("|---|---|---|---|")
    for m in manifests:
        slug = m["slug"]
        if "stm32" not in m["platforms"] or "mspm0" not in m["platforms"]:
            continue
        st = platform_api(m, "stm32")
        ms = platform_api(m, "mspm0")
        if not st and not ms:
            continue
        def names(xs):
            return "<br>".join(sorted(xs)) or "—"
        lines.append(f"| {slug} | {names(st - ms)} | {names(ms - st)} | {len(st & ms)} |")
    lines.append("")

    # 每个双平台模块 API 清单
    lines.append("## 4. 双平台 API 清单\n")
    for m in manifests:
        slug = m["slug"]
        if "stm32" not in m["platforms"] or "mspm0" not in m["platforms"]:
            continue
        st = platform_api(m, "stm32")
        ms = platform_api(m, "mspm0")
        if not st and not ms:
            continue
        lines.append(f"### {slug}\n")
        lines.append(f"- stm32：{', '.join(sorted(st)) or '—'}")
        lines.append(f"- mspm0：{', '.join(sorted(ms)) or '—'}")
        lines.append("")
    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
