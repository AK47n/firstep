r"""口径探针：**守卫的整文件解析** 与 **scope_lib 的 `<style>` 块解析** 差多少。

为什么要问：本轮的描边腿要住在守卫里（JS），而读数（115）是 Python 按 `<style>` 块算的。
两边若不是一个规则集，"腿绿而读数红"（或反过来）就成了新的假账。
sitewide 轮已经量到过一次差（`generate` 410 vs 409），本探针把它按**描边**这一面算清。
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "ui-density-sitewide"))

from scope_lib import FULL_BORDER_RE, DEAD_BORDER, full_borders, read_page  # noqa: E402

OUT = HERE / "probe-02-caliber-styleblock.txt"
# 守卫 `cssRules()` 的原式：`/([^{}]+)\{([^{}]*)\}/g` + `m[1].replace(/\s+/g," ").trim()`
WHOLE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)


def rules_whole(text: str):
    return [(" ".join(m.group(1).split()), m.group(2)) for m in WHOLE_RE.finditer(text)]


def rules_style(text: str):
    m = re.search(r"<style>(.*?)</style>", text, re.S)
    css = m.group(1) if m else text
    return [(" ".join(x.group(1).split()), x.group(2)) for x in WHOLE_RE.finditer(css)]


def borders(rules):
    out = []
    for sel, body in rules:
        for m in FULL_BORDER_RE.finditer(body):
            value = m.group(1).strip()
            if value.split()[0] in DEAD_BORDER:
                continue
            out.append((sel, value))
    return out


def main() -> int:
    text = read_page()
    whole, style = rules_whole(text), rules_style(text)
    bw, bs = borders(whole), borders(style)
    lines = [
        "# 读数：描边守卫轮 · 解析口径对账（整文件 vs `<style>` 块）",
        "# 命令：python .scratch/border-guard/probe-02-caliber-styleblock.py",
        "# 守卫 cssRules() 的原式 = /([^{}]+)\\{([^{}]*)\\}/g；scope_lib.rules_of 只在 <style> 里跑",
        f"# 时间：{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        f"整文件解析   ：规则 {len(whole):5d}  整圈完整框 {len(bw):5d}",
        f"<style> 块解析：规则 {len(style):5d}  整圈完整框 {len(bs):5d}",
        f"scope_lib.full_borders（口径锚）：{len(full_borders(text))}",
        "",
        "## 整文件多出来的那几条",
    ]
    only_w = [x for x in bw if x not in bs]
    only_s = [x for x in bs if x not in bw]
    for sel, value in only_w:
        lines.append(f"  [整文件独有] {value:34s} {sel}")
    for sel, value in only_s:
        lines.append(f"  [<style> 独有] {value:34s} {sel}")
    if not only_w and not only_s:
        lines.append("  （无——两个口径在描边这一面逐条相同）")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines[5:]))
    print(f"已落盘：{OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
