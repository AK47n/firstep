r"""B25（k230-multi-template/04 收口·渲染段）：模板选择 → 生成的 main.py 内容确实不同。

源工单验收最后一条是「真机验收：浏览器手测 k230 模板切换 → 生成工程 main.py 内容随选择变化」。
整条生成链要真实 LLM（推荐/骨架），故这里把**可确定性验证的那一半**钉死：
按 manifest 的 `python_artifact.templates[].template` 取三份模板文件，走产品的模板渲染器
`contest_generator.k230_render.render_python_artifact` 渲染（契约占位符替换），断言：

  ① 三个模板渲染结果**两两不同**（内容随选择变化）；
  ② 每份含自己的特征调用（blob→find_blobs / rect→find_rects / digit→AnchorBaseDet）；
  ③ digit 模板的模板级依赖（digit_uart）与随工程分发的资产（kmodel / deploy_config.json）在盘。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch\k230-multi-template\verify-04-templates.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.k230_render import render_python_artifact  # noqa: E402

MODULE = ROOT / "library" / "modules" / "k230"
MARKERS = {"blob": "find_blobs", "rect": "find_rects", "digit": "AnchorBaseDet"}

failed = 0


def check(name: str, ok: bool, extra: str = "") -> None:
    global failed
    print(("PASS " if ok else "FAIL ") + name + (f" [{extra}]" if extra else ""))
    if not ok:
        failed += 1


def main() -> int:
    manifest = json.loads((MODULE / "manifest.json").read_text(encoding="utf-8"))
    pa = manifest.get("python_artifact") or {}
    templates = pa.get("templates") or []
    check("manifest 声明 ≥2 个模板（下拉出现的前提）", len(templates) >= 2, f"templates={len(templates)}")
    check("manifest 有 default（默认选中项）", bool(pa.get("default")), f"default={pa.get('default')}")

    rendered: dict[str, str] = {}
    for t in templates:
        src = MODULE / str(t["template"])
        check(f"模板文件在盘：{t['id']} → {t['template']}", src.is_file(), str(src.relative_to(ROOT)))
        if not src.is_file():
            continue
        out = render_python_artifact(src.read_text(encoding="utf-8"))
        rendered[t["id"]] = out
        check(f"渲染结果非空且含特征调用（{t['id']} → {MARKERS.get(t['id'], '?')}）",
              len(out) > 200 and MARKERS.get(t["id"], "") in out,
              f"len={len(out)}")

    ids = [t["id"] for t in templates if t["id"] in rendered]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            check(f"渲染内容两两不同：{a} ≠ {b}", rendered[a] != rendered[b],
                  f"len {len(rendered[a])} vs {len(rendered[b])}")

    digit = next((t for t in templates if t["id"] == "digit"), None)
    if digit:
        check("digit 模板声明模板级依赖覆盖（digit_uart）",
              "digit_uart" in (digit.get("dependencies") or []), json.dumps(digit.get("dependencies")))
        for asset in digit.get("assets") or []:
            check(f"digit 随工程分发资产在盘：{asset['src']}", (MODULE / asset["src"]).is_file())

    print(f"\n---- B25(渲染) 总览 ----\n{'FAILED' if failed else 'OK'} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
