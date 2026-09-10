"""D2（wiki-md-repair/02）抽查探针：跨分类抽 5 篇，用仓库自带文本模型判「像真文档」。

口径（挂账单 D2 / 来源工单 wiki-md-repair/02）：跨分类抽查 ≥5 篇产物人工过目
「像真文档」。执行 agent 不能目视，故走与视觉通道同款的**仓库自带模型链路**
（`contest_generator.vision.describe_image` 同款 provider/模型配置，经 `llm` 的
chat 端点调用——文本任务，不传图），逐篇问同一个判据问题，原话落盘
`<篇名>.review.txt`，供人复核。

抽取策略：库内 `lckfb-地猛星移植手册` 批（wiki.md 修复对象）按**二级目录**
（分类）分散取 5 篇——保证跨分类，且文件名自解释。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/wiki-md-repair/probe-16-spotcheck.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.config import load_config  # noqa: E402

OUT = REPO / ".scratch" / "wiki-md-repair"
MATERIALS = REPO / "sources" / "materials"
PROMPT = (
    "下面是从一份硬件模块移植手册（Markdown）里截取的片段（前 1500 字符）。"
    "请只回答两件事：① 这段文字**读起来像一份正常的硬件文档吗**"
    "（标题/段落/列表/代码块结构正常、语句通顺、无「一个词一行」的碎片化、"
    "无行号残留、无乱码）？② 若不像，具体指出哪里坏了（举出原文片段）。"
    "不要复述整段内容，简短回答即可。\n\n----- 片段开始 -----\n"
)


def chat(cfg, text: str) -> str:
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "user", "content": PROMPT + text},
        ],
        "max_tokens": 800,
        "thinking": {"type": "disabled"},
    }
    req = urllib.request.Request(
        cfg.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + cfg.api_key,
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data["choices"][0]["message"].get("content") or "").strip()


def pick_samples() -> list[Path]:
    """跨分类取 5 篇：该批文件名自带分类前缀（`<分类>--<篇名>.md`，批内是平铺
    目录——首版按二级目录分组只抽到 1 篇，属脚本口径错），故按文件名 `--` 前的
    分类分组，每组取首篇，取 5 组。"""
    batch = MATERIALS / "lckfb-地猛星移植手册"
    if not batch.is_dir():
        batch = MATERIALS
    by_cat: dict[str, list[Path]] = {}
    for p in sorted(batch.rglob("*.md")):
        if p.name in ("模块索引.md", "网盘索引.md"):
            continue
        rel = p.relative_to(batch)
        if "--" in p.name:
            cat = p.name.split("--", 1)[0]
        else:
            cat = rel.parts[0] if len(rel.parts) > 1 else "(顶层)"
        by_cat.setdefault(cat, []).append(p)
    picks: list[Path] = []
    for cat in sorted(by_cat):
        picks.append(by_cat[cat][0])
        if len(picks) >= 5:
            break
    return picks


def main() -> int:
    cfg = load_config()
    picks = pick_samples()
    lines: list[str] = []
    results = []

    def note(t: str) -> None:
        print(t, flush=True)
        lines.append(t)

    note(f"[库] {MATERIALS}")
    note(f"[抽篇] {len(picks)} 篇（跨分类取首篇）：")
    for p in picks:
        note(f"   - {p.relative_to(MATERIALS)}（{p.stat().st_size} 字节）")
    note("")
    for p in picks:
        text = p.read_text(encoding="utf-8", errors="replace")[:1500]
        note(f"===== {p.relative_to(MATERIALS)} =====")
        try:
            answer = chat(cfg, text)
        except Exception as exc:  # noqa: BLE001 - 单篇失败不拖垮整批
            answer = f"（调用失败：{type(exc).__name__}: {exc}）"
        note(answer)
        results.append({
            "file": str(p.relative_to(MATERIALS)),
            "size_bytes": p.stat().st_size,
            "head_chars": text[:300],
            "verdict_text": answer,
        })
        out = OUT / (p.stem + ".review.txt")
        out.write_text(answer + "\n", encoding="utf-8")
        note(f"--> 落盘 {out.relative_to(REPO)}")
        note("")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verify-16-spotcheck.txt").write_text("\n".join(lines) + "\n",
                                                 encoding="utf-8")
    (OUT / "verify-16-spotcheck.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("--> 落盘 .scratch/wiki-md-repair/verify-16-spotcheck.{txt,json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
