"""disabled-forms 轮 · 00 号探针：**opacity 形态盘点 + 三处目标的比值复算**。

用途（clarify / spec 期 recon，后续工单复用）：

1. 把样式块里所有 `opacity < 1` 的规则列出来，逐条标三个机械信号：
   `cursor: not-allowed` 同规则 / 类名词法命中嫌疑词表 / 是否在 `@keyframes` 里；
2. 复算三处目标（`.module-card.off` / `.pin-menu-list li.cant` / `.param-stale`）
   **改前（opacity 合成）** 与 **改后（声明色 × 声明底）** 的比值——两种合成模型都给，
   看哪一种能复现 `code-contrast/03` 票尾记的 `浅 3.40 / 2.24`。

跑法（仓库根）：`python .scratch\\disabled-forms\\probe-00-inventory.py`
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE_LIB = ROOT / ".scratch" / "light-contrast" / "probe_lib.py"

spec = importlib.util.spec_from_file_location("_contrast_probe_lib", PROBE_LIB)
plib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plib)

# 反向嫌疑词法 / 关键帧口径 / 登记表**一律读 probe_lib**（那是单源；JS 守卫同名常量由
# `tests/test_contrast_mirror.py` 钉住）。探针里**不许**再抄一份——上一轮就是"口径两份拷贝、
# 只改一侧"踩的坑（`docs/agents/local-environment.md` §0 的 code-contrast 条）。
#
# ⚠ **2026-10-01（工单 `contrast-residue/04`）口径变更**：判据②从"嫌疑面驱动"改成**全量驱动**，
# 原"反向嫌疑词法"（`CONTRAST_DISABLED_HINTS` / `class_hint_hits`）**整条退役**——本探针的
# `HINT_WORDS` 与"词法命中"那一列随之删掉；现在只需要"在册 / 未在册"这一个判定。
KEYFRAME_SEL_RE = plib.KEYFRAME_SEL_RE

OPACITY_RE = re.compile(r"opacity\s*:\s*([\d.]+)")

#: recon 那一刻（`disabled-forms` 单落定之前）量到的形状数——**冻结**，只作对照。
#: 票面引用的 `26 / 5 / 21 / 7` 就是这一行（`7` = 当时命中嫌疑信号的条数；全量口径下这个数
#: 不再有意义，保留只作历史对照）。
RECON_BASELINE = {"rules": 26, "in_keyframes": 5, "live": 21, "suspect": 7}


def declared_bg_token(d) -> str | None:
    """规则自己声明的底（只认 `var(--token)` 这种纯令牌写法；其余返回 None）。"""
    raw = (d.get("background-color") or d.get("background") or "").strip()
    m = re.fullmatch(r"var\((--[a-z0-9-]+)\)", raw)
    return m.group(1) if m else None


def models(tok, theme, fg_tok, own_bg_tok, op, ancestor_tok="--panel"):
    """两种合成模型下的 (fg', bg')；own_bg_tok None = 元素自己没声明底。"""
    fg = tok.value(fg_tok, theme)
    own = tok.value(own_bg_tok, theme) if own_bg_tok else None
    anc = tok.value(ancestor_tok, theme)
    if fg is None or anc is None:
        return None
    behind = anc[0:3]
    # 模型 A：整块（字 + 自己的底）一起压到祖先底上（probe-08 的几何）
    own_bg = own[0:3] if own else behind
    bg_a = [round(op * own_bg[i] + (1 - op) * behind[i]) for i in range(3)]
    fg_a = [round(op * fg[i] + (1 - op) * behind[i]) for i in range(3)]
    # 模型 B：底不动（元素自己那层不透明），只把字往自己底上拉
    bg_b = own[0:3] if own else behind
    fg_b = [round(op * fg[i] + (1 - op) * bg_b[i]) for i in range(3)]
    return {
        "A": (plib.contrast(fg_a, bg_a), plib.hexs(fg_a), plib.hexs(bg_a)),
        "B": (plib.contrast(fg_b, bg_b), plib.hexs(fg_b), plib.hexs(bg_b)),
    }


def plain(tok, theme, fg_tok, bg_tok):
    fg = tok.value(fg_tok, theme)
    bg = tok.value(bg_tok, theme)
    return plib.contrast(fg[0:3], bg[0:3])


def main() -> None:
    text = plib.read_page()
    css = plib.contrast_style_text(text)
    tok = plib.Tokens(text)

    print("=" * 78)
    print("§1 样式块里 `opacity < 1` 的规则（`@keyframes` 帧单列）")
    print("=" * 78)
    rows = []
    for sel, body in plib.css_rules(css):
        m = OPACITY_RE.search(body)
        if not m:
            continue
        op = float(m.group(1))
        if op >= 1:
            continue
        d = plib.decls(body)
        kf = bool(KEYFRAME_SEL_RE.match(sel))
        cursor = d.get("cursor", "")
        rows.append((sel, op, cursor, kf, d))
    in_kf = [r for r in rows if r[3]]
    live = [r for r in rows if not r[3]]
    print(f"总 {len(rows)} 条：动画帧内 {len(in_kf)} 条、活规则 {len(live)} 条\n")
    for sel, op, cursor, _kf, _d in live:
        flags = []
        if cursor == "not-allowed":
            flags.append("cursor:not-allowed")
        kind = plib.disabled_form_kind(sel)
        flags.append(f"在册 {kind}" if kind else "**未在册**")
        print(f"  {op:<5} {sel[:64]:<64} {'  '.join(flags)}")
    print("\n  —— 动画帧内（判据应排除）：")
    for sel, op, _c, _kf, _d in in_kf:
        print(f"  {op:<5} {sel[:64]}")
    # **全量口径**（工单 contrast-residue/04）：活规则**逐条**都必须在册——不再有"嫌疑面"这个中间层。
    missing = [r for r in live if not plib.in_disabled_face(r[0])]
    print(f"\n  ⇒ 活规则 {len(live)} 条，其中**未在册 {len(missing)} 条**"
          + ("（全量口径下这就是红）" if missing else "（全量登记已闭合）"))
    if missing:
        print("     未在册的（守卫的反向判据会逐条点名）：" + "、".join(r[0] for r in missing))
    # recon 那一刻（`disabled-forms` 单之前）的读数——**冻结**，只作历史对照。
    # ⚠ 全量口径（`contrast-residue/04`）之下"嫌疑面"这个中间层已经不存在了，
    # 那一格只按旧定义并列出来，别拿它当判据。
    print(f"  · recon 基线（`disabled-forms` 单记的那份，冻结）：总 {RECON_BASELINE['rules']} / "
          f"动画帧 {RECON_BASELINE['in_keyframes']} / 活规则 {RECON_BASELINE['live']} / 旧嫌疑面 "
          f"{RECON_BASELINE['suspect']}；现算差 = 总 {len(rows) - RECON_BASELINE['rules']:+d} / "
          f"活规则 {len(live) - RECON_BASELINE['live']:+d}")
    # 正向面：**不许弱化**的认人面（`:disabled` / `.disabled` 正则 + 登记表 `disabled` 档）
    # 里**还带着 opacity** 的规则——改完之后这里必须是 0 条（它就是票面"三处改灰底灰字"的机器读数）。
    face_dim = []
    for sel, body in plib.css_rules(css):
        m = OPACITY_RE.search(body)
        if not m or float(m.group(1)) >= 1:
            continue
        if plib.never_dims_form(sel):
            face_dim.append((sel, float(m.group(1))))
    print(f"  ⇒ 正向认人面里还带 `opacity < 1` 的规则 = **{len(face_dim)} 条**"
          + ("（" + "、".join(f"{s} {o:g}" for s, o in face_dim) + "）" if face_dim else "（正向判据应当无话可说）"))

    print()
    print("=" * 78)
    print("§2 三处目标的比值：改前（冻结的 opacity 合成，两模型）× 改后（现算：声明色 × 声明底）")
    print("=" * 78)
    print("  改前那一列的口径：opacity 是**冻结的 recon 值**（改完之后盘上已经没有它，"
          "复算不出来）；\n  改后那一列**每次现算**：读规则现在声明的底（没声明就吃祖先/兜底）。")
    targets = [
        # 名字, 选择器, 改前 opacity（冻结）, 改前自己那层底, 改后兜底底, [(文字令牌, 说明)]
        (".module-card.off", ".module-card.off", 0.55, "--panel-2", "--panel",
         [("--text", "slug（继承正文色）"), ("--muted", "说明 / 徽章文字")]),
        (".pin-menu-list li.cant", ".pin-menu-list li.cant", 0.5, None, "--panel-2",
         [("--text", "角色名（继承正文色）"), ("--muted", "slug / 「不兼容」说明")]),
        (".param-stale", ".param-stale", 0.65, "--panel-2", "--panel-2",
         [("--text", "参数名"), ("--muted", "提示 / 单位")]),
    ]
    for name, sel, op_before, before_bg, after_fallback, fgs in targets:
        rule = next(((s, plib.decls(b)) for s, b in plib.css_rules(css) if s == sel), None)
        if rule is None:
            print(f"\n{name}   **盘上找不到这条规则**——锚点过期了，先看选择器")
            continue
        on_disk = rule[1].get("opacity")
        declared = declared_bg_token(rule[1])
        after_bg = declared or after_fallback
        print(f"\n{name}   （改前 opacity {op_before:g} / 现盘上 "
              f"{'还写着 opacity ' + on_disk if on_disk else '已无 opacity'}；"
              f"底 {('盘上声明 ' + declared) if declared else ('未声明 → 兜底 ' + after_fallback)}）")
        for theme in ("light", "dark"):
            print(f"  [{theme}]")
            for fg_tok, label in fgs:
                res = models(tok, theme, fg_tok, before_bg, op_before)
                a, b = res["A"], res["B"]
                print(f"    {label:<22} {fg_tok:<10} "
                      f"改前 A {a[0]:.2f} ({a[1]} on {a[2]}) | B {b[0]:.2f} ({b[1]} on {b[2]})")
            for fg_tok, label in fgs:
                print(f"    {label:<22} {fg_tok:<10} 改后   {plain(tok, theme, fg_tok, after_bg):.2f} "
                      f"({fg_tok} on {after_bg})")

    print()
    print("=" * 78)
    print("§3 候选落值要用到的基准对（两主题）")
    print("=" * 78)
    for theme in ("light", "dark"):
        for fg_tok in ("--text", "--muted", "--accent-text", "--warn-text"):
            for bg_tok in ("--panel", "--panel-2"):
                print(f"  [{theme}] {fg_tok:<14} on {bg_tok:<10} = {plain(tok, theme, fg_tok, bg_tok):.2f}")


    print()
    print("=" * 78)
    print("§4 两个冻结形状数的现算口（守卫 `CONTRAST_PAIR_COUNT` / `CONTRAST_FAMILY_CELL_COUNT`）")
    print("=" * 78)
    pairs = plib.contrast_pairs(text, tok)
    cells = plib.contrast_family_cells(text, tok)
    print(f"  机械面（同规则 `color:` × `background:`，两主题各一条）= **{len(pairs)}** 对")
    print(f"  族面格数 = **{len(cells)}** 格")
    bad = [p for p in pairs if p.ratio + 1e-9 < p.need]
    print(f"  机械面不达标 = {len(bad)} 条"
          + ("（" + "；".join(f"{p.theme} {p.selector} {p.ratio:.2f}" for p in bad) + "）" if bad else ""))


    print()
    print("=" * 78)
    print("§5 连带调整的比值（off 卡上的「详情」按钮 / 平台徽章坐在两种底上）")
    print("=" * 78)
    print("  · .mc-info 在 off 卡上改 --panel-2 底（可用控件，不许跟着一起弱化）")
    for theme in ("light", "dark"):
        for bg in ("--panel", "--panel-2"):
            tag = "  ← off 卡上用的是这层" if bg == "--panel-2" else ""
            print(f"    [{theme}] --accent-text on {bg:<10} = "
                  f"{plain(tok, theme, '--accent-text', bg):.2f}{tag}")
    print("  · .mc-plat.un 徽章（底是 rgba(139,148,158,.15)，字 --muted）——off 卡的底从 --panel-2 换成")
    print("    --panel，徽章合成底跟着变；两行都摆出来，免得「换底把徽章压暗了」这种担心没人复算")
    badge = (139, 148, 158, 0.15)
    for theme in ("light", "dark"):
        for base in ("--panel-2", "--panel"):
            eff = plib.over(badge, tok.value(base, theme)[0:3])
            print(f"    [{theme}] --muted on rgba(139,148,158,.15) over {base:<10} = "
                  f"{plib.contrast(tok.value('--muted', theme)[0:3], eff):.2f} ({plib.hexs(eff)})")


if __name__ == "__main__":
    main()
