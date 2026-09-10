"""C1（recommend-vision-qa/03）降级路径真机探针——三条路径的**机器判据**部分。

主链路（真视觉消化图内问题）走
`.scratch/recommend-domain-reject/probe-16-recommend-live.py --vision-qa`（真推荐 +
真视觉），本探针只跑可以离线判定的三条降级路径，判据尽量贴近产品真实代码路径：

- 降级一（无视觉配置）：视觉 key 留空 + **自定义端点** → `effective_vision_api_key`
  返回空串 → `vision_configured` False → 装配层不注入 vision_qa（与改动前逐字节
  一致的那条路）。判据 = 产品函数实况（不是复述文档）。
  （注意：留空 + DeepSeek 官方端点 = 按仓库口径**复用主 key**，那是主链路不是降级。）
- 降级二（粘贴无图题面）：no-topic 形（不带 topic_id）推荐 → 题面无「图N」引用
  → `vision_answerable` 恒 False → 即使注入了视觉回调也不会有一次视觉调用。
  判据 = 真跑一次 no-topic 推荐（真额度一次）+ 视觉回调计数器为 0。
- 降级三（视觉答不上）：构造「图内信息问题但答案不在图里」的问题 → 回调返回
  None（否定词 / 空答案）→ 问题**照旧问用户**、流程不阻塞。判据 =
  `answer_figure_question` 真调 2021F 原 PDF → 返回 None（真视觉调用）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/recommend-vision-qa/probe-16-degrade-paths.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.config import load_config  # noqa: E402
from contest_generator.selection import vision_answerable  # noqa: E402
from contest_generator.vision import (  # noqa: E402
    effective_vision_api_key,
    vision_configured,
)
from contest_generator.vision_qa import answer_figure_question  # noqa: E402

OUT = REPO / ".scratch" / "recommend-vision-qa"
lines: list[str] = []


def note(text: str) -> None:
    print(text, flush=True)
    lines.append(text)


def main() -> int:
    cfg = load_config()
    topic_md = REPO / "library" / "topics" / "2021F" / "topic.md"
    problem = topic_md.read_text(encoding="utf-8")
    pdf = REPO / "library" / "topics" / "2021F" / (
        "000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"
    )

    note("=== C1 降级路径一：无视觉配置（留空 + 自定义端点 → 不注入） ===")
    key_custom = effective_vision_api_key("", cfg.api_key, "https://vision.example.com/v1")
    key_official = effective_vision_api_key("", cfg.api_key, "https://api.deepseek.com")
    key_explicit = effective_vision_api_key("sk-explicit", cfg.api_key, "https://api.deepseek.com")
    note(f"留空 + 自定义端点 → key={key_custom!r} configured={vision_configured(key_custom)}"
         "（期望 '' / False = 不注入，行为与改动前一致）")
    note(f"留空 + DeepSeek 官方端点 → key={'<复用主 key>' if key_official else '空'}"
         f" configured={vision_configured(key_official)}（期望 True = 这是主链路口径）")
    note(f"显式 vision key → {'原样' if key_explicit == 'sk-explicit' else '异常'}"
         f" configured={vision_configured(key_explicit)}")
    ok1 = (key_custom == "" and not vision_configured(key_custom)
           and vision_configured(key_official) and key_explicit == "sk-explicit")
    note(f"降级一路径判据：{'PASS' if ok1 else 'FAIL'}")

    note("")
    note("=== C1 降级路径二：粘贴无图题面（no-topic）→ 视觉回调零调用 ===")
    nofigure = "设计并制作一个自动循迹小车，能沿黑色引导线行驶并在终点停车。"
    note(f"vision_answerable('这个尺寸是多少？', 无图题面) = "
         f"{vision_answerable('这个尺寸是多少？', nofigure)}（期望 False：题面无「图N」引用）")
    note(f"vision_answerable('图1 里的尺寸是多少？', 无图题面) = "
         f"{vision_answerable('图1 里的尺寸是多少？', nofigure)}（期望 False）")
    calls = {"n": 0}

    def vision_stub(question: str) -> str | None:  # noqa: ANN202
        calls["n"] += 1
        return "不该被调到"

    from contest_generator.selection import _answer_vision_questions

    remaining, merged = _answer_vision_questions(
        ("这个尺寸是多少？", "图1 里的尺寸是多少？"), vision_stub, nofigure, ()
    )
    note(f"_answer_vision_questions：剩余待问 {len(remaining)} 条（期望 2 = 全保留）、"
         f"视觉回调调用 {calls['n']} 次（期望 0）")
    ok2 = (vision_answerable("这个尺寸是多少？", nofigure) is False
           and vision_answerable("图1 里的尺寸是多少？", nofigure) is False
           and calls["n"] == 0 and len(remaining) == 2)

    note("")
    note("=== C1 降级路径三：视觉答不上（真调 2021F 原 PDF）===")
    topic_figs = sorted(set(__import__("re").findall(r"图\s*(\d+)", problem)))
    note(f"2021F 题面引用图号：{topic_figs[:8]}{'…' if len(topic_figs) > 8 else ''}")
    hard_q = "图1 中标注的那个部件的采购价格是多少元？"
    note(f"问题：{hard_q}")
    note(f"vision_answerable(问题, 题面) = {vision_answerable(hard_q, problem)}（期望 True：问到图1）")
    vkey = effective_vision_api_key(cfg.vision_api_key, cfg.api_key, cfg.vision_base_url)
    note(f"视觉通道：base_url={cfg.vision_base_url} model={cfg.vision_model} "
         f"key={'复用主 key' if vkey == cfg.api_key else ('显式' if vkey else '空')}")
    ans = answer_figure_question(
        pdf, problem, hard_q,
        vision_base_url=cfg.vision_base_url, vision_api_key=vkey,
        vision_model=cfg.vision_model,
    )
    note(f"answer_figure_question → {ans!r}")
    if ans is None:
        note("判据：返回 None（否定词 / 空答案）→ 问题照旧问用户、流程不阻塞 = PASS")
        remaining3, merged3 = _answer_vision_questions((hard_q,), lambda q: ans, problem, ())
        note(f"编排层复验：剩余待问 {len(remaining3)} 条（期望 1 = 问题保留给用户）"
             f"、澄清历史新增 {len(merged3)} 条（期望 0）")
        ok3 = len(remaining3) == 1 and len(merged3) == 0
    else:
        note("注意：视觉答上来了（非 None）——该问题不算「答不上」样本，"
             "需换一个图内必无答案的问题（如问一个图里根本没有的型号价钱）")
        ok3 = False

    note("")
    note(f"三条降级路径判据：一={'PASS' if ok1 else 'FAIL'} / "
         f"二={'PASS' if ok2 else 'FAIL'} / 三={'PASS' if ok3 else 'FAIL'}")
    OUT.joinpath("verify-16-degrade-paths.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    OUT.joinpath("verify-16-degrade-paths.json").write_text(
        json.dumps(
            {"key_custom": key_custom, "key_official_reused": bool(key_official),
             "vision_stub_calls": calls["n"], "hard_question_answer": ans,
             "ok": {"path1": ok1, "path2": ok2, "path3": ok3}},
            ensure_ascii=False, indent=2,
        ), encoding="utf-8",
    )
    print("--> 落盘 .scratch/recommend-vision-qa/verify-16-degrade-paths.{txt,json}")
    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    raise SystemExit(main())
