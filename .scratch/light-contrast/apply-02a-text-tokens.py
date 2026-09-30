"""浅色调色板轮 · 施工脚本（02 单）：插入六族 `-text` 令牌 + 把**当文字用**的色迁过去。

## 契约（写死在这里，02 单票尾要复述）

- `--X`（主令牌）= 描边 / 淡底 / 实心块 / 图标用的色；
- `--X-text`（**新**）= **当文字用**的色。暗色 = 主令牌现值（两族需提亮，见值表）；
  浅色 = 压暗到"三类底 × 真实淡底"上最坏格 ≥ 4.80（AA 4.5 + 余量 0.30）。
- 迁移面 = **所有 `color: var(--X)`**，X ∈ {accent, ok, ok-bright, warn, danger, info, purple-grad}；
  其中 `--ok-bright` 与 `--ok` 共用 `--ok-text`（两者当文字用时取更严的那个值）。
- **不动**：`background` / `border*` / `outline` / `box-shadow` / `stroke` / `fill` / `caret-color`
  （那是主令牌的活）；`--on-accent` / `--on-*-deep`（压在实心块上的字，另有口径）。

值表来自 `probe-04-family-candidates.py`（余量 0.30 口径现算）。

跑法（仓库根）：
    python .scratch/light-contrast/apply-02a-text-tokens.py --dry    # 只打印将改什么
    python .scratch/light-contrast/apply-02a-text-tokens.py          # 落盘
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_lib as L  # noqa: E402

PAGE = L.PAGE

#: `--text` 令牌：`(令牌名, 暗色值, 浅色值, 它替掉哪些主令牌)`
TEXT_TOKENS = [
    ("--accent-text", "#00d4ff", "#006181", ["--accent"]),
    ("--ok-text", "#3fb950", "#15672d", ["--ok", "--ok-bright"]),
    ("--warn-text", "#e3a341", "#7a5100", ["--warn"]),
    ("--danger-text", "#ff685e", "#a81c25", ["--danger"]),
    ("--info-text", "#58a6ff", "#0755b1", ["--info"]),
    ("--purple-text", "#b175ff", "#6840b2", ["--purple-grad"]),
]

DARK_BLOCK = re.compile(r"(\n {2}:root \{(?:[^\n]*\n)*?)( {4}--accent-rgb: )")
LIGHT_BLOCK = re.compile(r'(\n {2}html\[data-theme="light"\] \{(?:[^\n]*\n)*?)( {4}/\* 主题相关裸色令牌)')

DECL_COLOR = re.compile(r"(?<![\w-])color:\s*var\((--[a-z0-9-]+)(\s*,[^)]*)?\)")


def main() -> None:
    dry = "--dry" in sys.argv
    check = "--check" in sys.argv
    raw = PAGE.read_bytes()
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    text = raw.decode("utf-8")

    def enc(s: str) -> bytes:
        return s.replace("\n", nl.decode()).encode("utf-8")

    if check:
        # 复核 = **后置条件**（不问"我改过什么"，问"盘上现在必须是什么样"）——
        # 这样 223 这个数字有一条命令可复算（02 单双评点过：只跑一次的守卫让数不可复算）。
        problems = []
        mains = {m for _n, _d, _l, ms in TEXT_TOKENS for m in ms}
        stale = [m.group(0) for m in re.finditer(r"(?<![\w-])color:\s*var\((--[a-z0-9-]+)\)", text)
                 if m.group(1) in mains]
        if stale:
            problems.append(f"  还有 {len(stale)} 处 `color: var(--主令牌)` 没迁：{stale[:3]}")
        for name, dark, light, _mains in TEXT_TOKENS:
            if f"{name}: {dark};" not in text:
                problems.append(f"  暗色缺 {name}: {dark};")
            if f"{name}: {light};" not in text:
                problems.append(f"  亮色缺 {name}: {light};")
        if problems:
            raise SystemExit("复核发现问题：\n" + "\n".join(problems))
        print(f"复核 OK：{len(TEXT_TOKENS)} 个 `-text` 令牌两主题都在，"
              f"盘上 `color: var(--主令牌)` = 0 处")
        return

    if "--accent-text" in text:
        raise SystemExit("页面里已经有 --accent-text 了——本脚本只跑一次；要重跑先 git checkout")

    # ---- ① 两块主题各插一组 `-text` 令牌 ----------------------------------
    head = (f"{nl.decode()}    /* 文字档（工单 light-contrast/02）：同一个语义色的「当文字用」变体。\n"
            f"       主令牌管描边 / 淡底 / 实心块 / 图标；文字走 `-text`（浅色压暗到 AA 以上，\n"
            f"       暗色 = 主令牌现值；判据 = 守卫腿⑧ 的令牌面与机械面）。 */\n")
    dark_line = head + "    " + " ".join(f"{n}: {d};" for n, d, _l, _p in TEXT_TOKENS) + "\n"
    light_line = ("\n    /* 文字档（亮色配套，工单 02）：见 :root 那段说明 */\n"
                  "    " + " ".join(f"{n}: {l};" for n, _d, l, _p in TEXT_TOKENS) + "\n")

    m = DARK_BLOCK.search(text)
    if not m:
        raise SystemExit("锚点没命中：`--accent-rgb:` 那一行之前（:root 块）")
    text = text[:m.start(2)] + dark_line.lstrip("\n") + text[m.start(2):]
    m = LIGHT_BLOCK.search(text)
    if not m:
        raise SystemExit("锚点没命中：亮色块里 `/* 主题相关裸色令牌` 之前")
    text = text[:m.start(2)] + light_line.lstrip("\n") + text[m.start(2):]

    # ---- ② 迁移 `color: var(--X)` ----------------------------------------
    alias = {main: tok for tok, _d, _l, mains in TEXT_TOKENS for main in mains}
    hits: list[tuple[str, str, str]] = []

    def repl(match: re.Match[str]) -> str:
        main, fallback = match.group(1), match.group(2) or ""
        if main not in alias:
            return match.group(0)
        hits.append((main, alias[main], fallback))
        return f"color: var({alias[main]}{fallback})"

    before = text
    text = DECL_COLOR.sub(repl, text)
    print(f"迁移 `color: var(--X)`：**{len(hits)}** 处")
    for main in sorted({h[0] for h in hits}):
        n = sum(1 for h in hits if h[0] == main)
        print(f"  {main:<16} → {alias[main]:<18} × {n}")

    if dry:
        print("\n（--dry：没写盘）")
        return
    out = text.encode("utf-8")
    PAGE.write_bytes(out)
    print(f"\n已写盘：{PAGE.relative_to(L.ROOT)}（{len(before)} → {len(text)} 字符）")


if __name__ == "__main__":
    main()
