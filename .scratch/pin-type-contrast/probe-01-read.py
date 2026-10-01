# -*- coding: utf-8 -*-
"""引脚类型配色族 · 真像素读数（`probe-01-pin-family-pixels.mjs` 的第二半）。

## 它做什么

  1. 读 `probe-01-shots-<tag>.json`（真元素 + 逐元素 PNG + 静态预测的原料）；
  2. **族认人**：先用同趟的角色类型标建立「主色 → 族」表（标上的文字就是类型，类型前缀就是族），
     再用它给状态文字 / 图例色点 / 板图焊盘与引脚名 / 菜单色点认族——**不是按文本猜**；
  3. **两侧各算一次比值**：
     · **静态** = 浏览器怎么合成（自己的 `color` / SVG `fill`·`stroke` 压在自己的底上；
       板图那几个面的底是 PCB 底色叠在祖先底上）；
     · **实测** = 读 PNG：全量直方图 → 主色（底）→ 字形/图形核心（`pixel_lib`）；
  4. 逐格给**阈值判定**：文字面 4.5、非文字面（色点 / 焊盘描边）3.0。

## 口径（不另起一套）

  · 颜色数学 / 令牌 → `.scratch/light-contrast/probe_lib.py`（与守卫腿⑧ 同源、镜像守卫钉住）；
  · 读像素（直方图 / 主色 / 核心） → `.scratch/code-contrast/pixel_lib.py`；
  · **"没量到"逐条记账**：库内零实例的族（今天 `spi` / `exti`）、非家族色元素、截图失败——
    都不许静默变成"通过"。

跑法（仓库根；先跑 mjs）：

    python .scratch\\pin-type-contrast\\probe-01-read.py --tag before
    python .scratch\\pin-type-contrast\\probe-01-read.py --tag before --out .scratch\\pin-type-contrast
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code-contrast"))      # pixel_lib（读像素的公共半）
sys.path.insert(0, str(HERE.parent / "light-contrast"))     # probe_lib（颜色数学 / 令牌）

import pixel_lib as PX  # noqa: E402
import probe_lib as L  # noqa: E402

NUM_RE = re.compile(r"[\d.]+")
FAMILIES = ["gpio", "pwm", "enc", "uart", "i2c", "spi", "adc", "exti"]
# 文字面要 4.5；非文字面（色点 / 焊盘描边）3.0
TEXT_FACES = {"badge", "status", "board-label", "menu-badge"}
NONTEXT_FACES = {"legend-dot", "menu-dot", "board-pad"}


def rgba(css: str):
    if not css:
        return None
    parts = NUM_RE.findall(css)
    if len(parts) < 3:
        return None
    r, g, b = (int(float(p)) for p in parts[:3])
    a = float(parts[3]) if len(parts) > 3 else 1.0
    return (r, g, b, a)


def flat(fg, bg):
    """前景（可能带 alpha）压在底上 → 不透明三元组。"""
    return tuple(round(v) for v in L.over(fg, bg)[:3])


def family_of_row(row, color2fam: dict):
    """认族：先看探针记的 `familyHint`（类型前缀），否则拿颜色去同趟的标色表里查。"""
    hint = row.get("familyHint") or ""
    fam = next((f for f in FAMILIES if hint.startswith(f)), "")
    if fam:
        return fam
    for key in ("color", "fill", "stroke", "background"):
        c = row.get(key) or ""
        if c in color2fam:
            return color2fam[c]
    return ""


def measure(path: Path):
    """真像素：主色（底）+ 核心（字/图形）→ `(fg, bg, ratio)`；读不动 = None。"""
    if not path.is_file():
        return None
    cnt = PX.histogram(path)
    if not cnt:
        return None
    bg, _n = PX.dominant(cnt)
    fg = PX.glyph_core(cnt)
    return fg, bg, L.contrast(fg, bg)


def main() -> int:
    args = sys.argv[1:]

    def opt(name, dflt=None):
        if name not in args:
            return dflt
        i = args.index(name) + 1
        if i >= len(args) or args[i].startswith("--"):
            raise SystemExit(f"{name} 后面要给一个值")
        return args[i]

    tag = opt("--tag", "before")
    where = Path(opt("--out") or HERE)
    src = where / f"probe-01-shots-{tag}.json"
    if not src.is_file():
        raise SystemExit(f"找不到 {src}——先跑 probe-01-pin-family-pixels.mjs --tag {tag}")

    data = json.loads(src.read_text(encoding="utf-8"))
    rows = data["rows"]
    out: list[str] = []
    out.append("=" * 108)
    out.append("引脚类型配色族 · 真像素读数（probe-01：真 Chromium + 真后端 + 逐元素截图）")
    out.append(f"读数文件 = {src.name}；tag = {tag}；模块集 = {'、'.join(data.get('modules', []))}；"
               f"格数 = {len(rows)}")
    out.append("=" * 108)
    for p in data.get("prepares", []):
        out.append(f"  准备[{p['theme']}]：{p['note']}")
    for n in data.get("notes", []):
        if n.get("missing"):
            out.append(f"  没量到[{n['theme']}/{n['scope']}]：页签或面板不存在")
            continue
        sk = " / ".join(f"{k} {v}" for k, v in (n.get("skipped") or {}).items() if v)
        if sk:
            out.append(f"  没量到[{n['theme']}/{n['scope']}]：{sk}")
        for d in n.get("skippedDetail") or []:
            out.append(f"      · {d}")
        for x in n.get("failedShots") or []:
            out.append(f"      ⚠ 截图失败：{x['face']} {x['sel']} 「{x['text']}」 {x['box']}")

    # ---- 逐主题：先建「主色 → 族」表，再逐格判 ----
    summary = defaultdict(list)          # (theme, face, fam) → [ratio...]
    mismatches: list[str] = []
    machine: list[dict] = []             # 机器可读那半（`probe-01-readings-<tag>.json`）
    for theme in ("light", "dark"):
        sub = [r for r in rows if r["theme"] == theme]
        color2fam: dict[str, str] = {}
        for r in sub:
            if r["face"] in ("badge", "menu-badge"):
                fam = next((f for f in FAMILIES if (r.get("familyHint") or "").startswith(f)), "")
                if fam:
                    color2fam[r["color"]] = fam
        out.append("")
        out.append("-" * 108)
        out.append(f"【{theme}】族认人表（同趟角色类型标的主色 → 族）："
                   + "、".join(f"{k}→{v}" for k, v in sorted(color2fam.items(), key=lambda x: x[1])))
        out.append("-" * 108)
        out.append(f"  {'面':<12}{'族':<7}{'元素':<26}{'静态':>7}{'实测':>7}{'判定':>7}  备注")
        seen: dict[tuple[str, str], list] = defaultdict(list)
        for r in sub:
            face = r["face"]
            fam = family_of_row(r, color2fam)
            if not fam:
                continue
            fg = None
            if face in ("badge", "status", "menu-badge"):
                fg = rgba(r.get("color"))                      # 文字色
            elif face in ("legend-dot", "menu-dot"):
                fg = rgba(r.get("background"))                 # 色点：它自己的填充就是"字"
            elif face == "board-label":
                fg = rgba(r.get("fill"))                       # 板上引脚名：SVG 的 fill
            elif face == "board-pad":
                fg = rgba(r.get("stroke"))                     # 焊盘：描边环（填充是淡化色，只作底）
            bg_chain = [tuple(r["behind"])]
            pcb = rgba(r.get("pcbFill")) if face in ("board-pad", "board-label") else None
            if pcb:
                bg_chain.append(flat(pcb, bg_chain[-1]))
            own = rgba(r.get("background")) if face in ("badge", "menu-badge") else None
            bg = bg_chain[-1]
            if own:
                bg = flat(own, bg)
            if fg is None:
                out.append(f"  {face:<12}{fam:<7}{str(r['text'])[:24]:<26}{'解不出':>7}")
                continue
            fg_f = flat(fg, bg)
            static = L.contrast(fg_f, bg)
            m = measure(where / r["file"])
            if m is None:
                out.append(f"  {face:<12}{fam:<7}{str(r['text'])[:24]:<26}{static:>7.2f}{'没量到':>7}")
                continue
            pfg, pbg, measured = m
            need = 4.5 if face in TEXT_FACES else 3.0
            verdict = "过" if measured >= need else "**低**"
            note = ""
            if face == "board-pad":
                # 焊盘的取样盒（13×13）**几乎就是焊盘本身**：像素上量到的那对色是
                # "描边环 vs 盘内填充"，与静态那一对（环 vs PCB 底）**口径不同**——
                # 如实记，但不拿它当判据（判据看静态那一列）。
                note = f"（实测那对 = 环 vs 盘内填充，口径不同）"
            elif abs(measured - static) > 0.35:
                note = f"⚠ 静态 {static:.2f} vs 实测 {measured:.2f} 差 {abs(measured - static):.2f}"
                mismatches.append(f"{theme}/{face}/{fam} {r['text'][:12]}：静态 {static:.2f} / 实测 {measured:.2f}")
            out.append(f"  {face:<12}{fam:<7}{str(r['text'])[:24]:<26}{static:>7.2f}{measured:>7.2f}"
                       f"{verdict:>7}  {PX.hx(pfg)} on {PX.hx(pbg)} {note}")
            seen[(face, fam)].append((r, static, measured, need))
            summary[(theme, face, fam)].append(measured)
            machine.append({"theme": theme, "scope": r["scope"], "face": face, "family": fam,
                            "text": r.get("note") or r.get("text") or "", "static": round(static, 3),
                            "measured": round(measured, 3), "need": need, "file": r["file"]})
        # 每主题的小结：每族每面取最坏格
        out.append("")
        out.append(f"  【{theme}】按面 × 族的最坏格（文字 ≥4.5 / 非文字 ≥3.0）：")
        faces = ["badge", "status", "board-label", "legend-dot", "menu-badge", "menu-dot", "board-pad"]
        out.append("    " + "面".ljust(12) + "".join(f"{f:>9}" for f in FAMILIES))
        for face in faces:
            cells = []
            for fam in FAMILIES:
                vals = summary.get((theme, face, fam)) or []
                cells.append(f"{min(vals):>9.2f}" if vals else f"{'—':>9}")
            out.append("    " + face.ljust(12) + "".join(cells))
    out.append("")
    out.append("=" * 108)
    out.append("§ 静态 vs 实测 偏差 > 0.35 的格（先查量具与口径，别先改账）")
    out.append("=" * 108)
    out.extend(f"  {m}" for m in mismatches) if mismatches else out.append("  （无）")
    out.append("")
    out.append("§ 库内零实例的族（今天造不出角色 → 这一族**没有**渲染面读数）")
    out.append("=" * 108)
    for fam in ("spi", "exti"):
        out.append(f"  {fam}：两支 recon（recon-03-mspm0.txt / recon-03-stm32.txt）实测 0 个模块声明该类型；"
                   "令牌仍在（`--pin-%s*`），只是没有角色能造出来" % fam)

    body = "\n".join(out)
    dest = where / f"probe-01-readings-{tag}.txt"
    dest.write_text(body + "\n", encoding="utf-8")
    # **机器可读那半**（工单 pin-type-contrast/03 补）：两发对照脚本不许去解析中文表格
    # ——列宽/文本里的空格会把键解析错（实测：`已绑 PA1` 这类文本一进列，格数就"对不上"）。
    (where / f"probe-01-readings-{tag}.json").write_text(
        json.dumps({"tag": tag, "rows": machine}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(body.encode("utf-8", "replace").decode("utf-8", "replace"))
    print(f"\n[落盘] {dest} + {dest.with_suffix('.json').name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
