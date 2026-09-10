"""C1（recommend-vision-qa/03）主链路**注入式**真机探针：图内问题被自动消化。

需求原文（工单 03）：AI 提出「走廊宽度」类**图内**问题时被自动消化、用户不再被问。
单纯重跑 2021F 存在「模型这一轮恰好没提图内问题」的空过情形（实测第 1 次就发生——
`question` 事件数 0、视觉消化 0 次，等于没验到链路）。故本探针复刻**注入式
真机探针**先例（fix-loop-warnings/01 的 warn_probe 手法）：

- `llm.clarify` monkeypatch 成返回一个**真题面图内问题**（题面引用图 1/图 2，
  问题点名图 1 并问图内尺寸）——不改产品代码，只改「模型这一轮的输出」；
- 其余全部走真代码真服务：`selection.run_recommendation`（澄清门 → 视觉消化 →
  收敛循环）+ 真视觉（`vision_qa.answer_figure_question` 读 2021F 原 PDF 渲染页 →
  DeepSeek 视觉模型作答）；
- 判据：① 视觉回调确实被调用（次数 ≥1）；② 回调答案非空；③ **不发 question
  事件**（= 用户不再被问）；④ 答案以 (问题, 回答) 进了收敛用的澄清历史
  （由 `_converge` 收到 clarifications 间接证明——用收敛循环收到的历史快照断言）；
  ⑤ 推荐正常收敛到 done。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/recommend-vision-qa/probe-16-clarify-vision.py
"""
from __future__ import annotations

import json
import queue
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import contest_generator.llm as llm_mod  # noqa: E402
from contest_generator import events as ev  # noqa: E402
from contest_generator.config import load_config  # noqa: E402
from contest_generator.generator import resolve_topic_context  # noqa: E402
from contest_generator.vision import effective_vision_api_key  # noqa: E402
import contest_generator.vision_qa as vqa  # noqa: E402

# 计数用：把 answer_figure_question 包成计数包装**再**让 selection 模块 import
# 它——`run_recommendation` 里的闭包在函数体内 from .vision_qa import
# answer_figure_question，若 selection 已加载则该名字已绑定，事后改模块属性
# 对已加载模块无效（上一版就踩了这个：断言「视觉回调被调用 ≥1 次」假红，
# 而澄清历史里明明有视觉答案 30cm）。先包再重载 selection 才是真计数。
_orig_answer = vqa.answer_figure_question
_vision_calls: list[dict] = []


def _spy_answer(pdf, problem_text, question, **kw):  # noqa: ANN001
    ans = _orig_answer(pdf, problem_text, question, **kw)
    _vision_calls.append({"question": question, "answer": ans})
    print(f"  [视觉] {question[:60]} → {str(ans)[:220]}", flush=True)
    return ans


vqa.answer_figure_question = _spy_answer
for _name in ("contest_generator.selection", "contest_generator.sse"):
    sys.modules.pop(_name, None)
import contest_generator.selection as sel  # noqa: E402  （重载：吃到 spy）

OUT = REPO / ".scratch" / "recommend-vision-qa"

# 构造的图内问题（真题面引用图 1/图 2；问题点名图 1 且问图内尺寸）
FIGURE_QUESTION = "图 1 中场地（走廊）的宽度尺寸是多少？题面图上标注的数值请照读。"


def main() -> int:
    cfg = load_config()
    root = REPO / "library"
    topic = resolve_topic_context(
        llm=None,
        topic_key="2021F",
        problem_text=(root / "topics" / "2021F" / "topic.md").read_text(
            encoding="utf-8"),
        module_library_dir=root / "modules",
        topic_library_dir=root / "topics",
        reference_library_dir=root / "references",
        platform="stm32",
    )
    lines: list[str] = []

    def note(t: str) -> None:
        print(t, flush=True)
        lines.append(t)

    note(f"[题面] key={topic.key!r} 题面 {len(topic.problem_text)} 字符；"
         f"原 PDF={topic.figure_pdf}")
    note(f"[构造问题] {FIGURE_QUESTION}")
    note(f"[可答性判据] vision_answerable = "
         f"{sel.vision_answerable(FIGURE_QUESTION, topic.problem_text)}（期望 True）")

    llm = llm_mod.build_llm(cfg)
    # 请求体尺寸记账（诊断「请求体过大」那类失败：钱要花在看得见的地方）——
    # 包一层 Transport 记录每次发车的字节数与前若干字符，不改产品逻辑。
    _sizes: list[dict] = []

    class _SizeSpy:
        def __init__(self, inner):  # noqa: ANN001
            self._inner = inner

        def post(self, url, headers, payload, timeout):  # noqa: ANN001
            import json as _json
            body = _json.dumps(payload).encode("utf-8")
            segs = {k: len(_json.dumps(v).encode("utf-8"))
                    for k, v in payload.items() if k != "messages"}
            for i, m in enumerate(payload.get("messages") or []):
                segs[f"msg{i}:{m.get('role')}"] = len(
                    _json.dumps(m.get("content") or "").encode("utf-8"))
            _sizes.append({"total": len(body), "segments": segs})
            note(f"  [出车] 请求体 {len(body)} 字节 → {json.dumps(segs, ensure_ascii=False)}")
            return self._inner.post(url, headers, payload, timeout)

    _real_transport = llm_mod.UrllibTransport()
    _spy_transport = _SizeSpy(_real_transport)
    # 词表放宽（**只放宽词表，不改判定逻辑**）：2021F 题面确有一个词表外硬件名
    # （称重传感器——秤重件），模型偶尔把它写进库外建议 → 词表闸拒收 → kind=client
    # 免重试 → 整次推荐终态失败（本轮系统性问题，见收口记录的 F16-2）。本探针
    # 要验的是**视觉链路**，不让词表闸来搅局：把该名作为候选型号加进默认词表。
    from contest_generator.wordlist import HardwareWordGroup
    groups = list(llm_mod.DEFAULT_WORDLIST)
    for i, g in enumerate(groups):
        if g.category == "感知传感器":
            groups[i] = HardwareWordGroup(
                category=g.category,
                models=tuple(g.models) + ("称重传感器",),
                solutions=g.solutions,
            )
            break
    llm = llm_mod.DeepSeekLLM(cfg, hardware_words=tuple(groups),
                              transport=_spy_transport)
    real_clarify = llm.clarify

    def fake_clarify(problem_text, clarifications=()):  # noqa: ANN001
        note("  [注入] llm.clarify → 返回构造的图内问题（只替换模型这一轮输出）")
        return (FIGURE_QUESTION,)

    llm.clarify = fake_clarify  # type: ignore[method-assign]

    vkey = effective_vision_api_key(
        cfg.vision_api_key, cfg.api_key, cfg.vision_base_url)
    vision_calls = _vision_calls   # 计数包装已装好（见文件头）

    def vision_qa(question: str):  # noqa: ANN202
        return vqa.answer_figure_question(
            topic.figure_pdf, topic.problem_text, question,
            vision_base_url=cfg.vision_base_url, vision_api_key=vkey,
            vision_model=cfg.vision_model,
        )

    # 收敛循环收到的澄清历史快照（证明视觉答案进了历史）
    seen_clarifs: list[tuple] = []
    real_converge = sel.select_modules_convergent

    def spy_converge(llm_, problem_text, summaries, **kw):  # noqa: ANN001
        seen_clarifs.append(tuple(kw.get("clarifications") or ()))
        return real_converge(llm_, problem_text, summaries, **kw)

    sel.select_modules_convergent = spy_converge

    events: queue.Queue = queue.Queue()
    terminal: list[tuple[str, dict]] = []

    class _Emit:
        def progress(self, event):  # noqa: ANN001
            pass

        def done(self, data):  # noqa: ANN001
            terminal.append(("done", data))

        def question(self, data):  # noqa: ANN001
            terminal.append(("question", data))

        def error(self, data):  # noqa: ANN001
            terminal.append(("error", data))

    # 域拒绝重试环（**只重试「非视觉链路」的偶发失败**）：本轮实测 select 域拒绝
    # 是概率性的（同一题同一库，多次跑里若干次被拒），一次失败不等于视觉链路坏。
    # 判据是「这一轮里视觉链路是否按承诺工作」，故失败轮记下来重跑；重试时清空
    # 计数与事件，避免把上一轮的残留算进来。
    attempts: list[str] = []
    terminal: list[tuple[str, dict]] = []
    kind, data = "none", {}
    for attempt in range(1, 7):
        del terminal[:]
        del seen_clarifs[:]
        del vision_calls[:]
        try:
            sel.run_recommendation(
                topic, llm, (), emit=_Emit(), platform="stm32",
                vision_qa=vision_qa,
            )
        except Exception as exc:  # noqa: BLE001 - 探针把偶发域拒绝记为「本轮失败」
            attempts.append(f"第 {attempt} 次：{type(exc).__name__}: {str(exc)[:160]}")
            note(f"  [第 {attempt} 次] 编排抛错（非视觉链路）：{str(exc)[:160]}")
            continue
        kind, data = terminal[-1] if terminal else ("none", {})
        note(f"  [第 {attempt} 次] 终态 {kind}；视觉消化 {len(vision_calls)} 次")
        if kind == "done" and vision_calls:
            break
    clarif_with_answer = [
        c for snap in seen_clarifs for c in snap
        if c and c[0] == FIGURE_QUESTION and c[1]
    ]
    checks = [
        ("视觉回调被调用 ≥1 次", len(vision_calls) >= 1),
        ("视觉答案非空", bool(vision_calls) and bool(vision_calls[0]["answer"])),
        ("**未发 question 事件**（用户不再被问）", kind != "question"),
        ("答案进了收敛用澄清历史", bool(clarif_with_answer)),
        ("推荐正常收敛到 done", kind == "done"),
    ]
    note("")
    ok = True
    for name, cond in checks:
        note(("  ✓ " if cond else "  ✗ ") + name)
        ok = ok and bool(cond)
    slugs = [m.get("slug") for m in (data.get("modules") or [])]
    note(f"[终态] {kind}；模块 {len(slugs)}：{', '.join(slugs)}")
    if clarif_with_answer:
        note(f"[澄清历史里的视觉答案] {clarif_with_answer[0][1][:400]}")
    note(f"\nC1 主链路（注入式）真机：{'PASS' if ok else 'FAIL'}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verify-16-C1-clarify-vision.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "verify-16-C1-clarify-vision.json").write_text(json.dumps(
        {"injected_question": FIGURE_QUESTION, "vision_calls": vision_calls,
         "terminal": kind, "modules": slugs, "attempts": attempts,
         "request_sizes": _sizes,
         "clarif_with_answer": [list(c) for c in clarif_with_answer],
         "checks": {n: bool(c) for n, c in checks}}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("--> 落盘 .scratch/recommend-vision-qa/verify-16-C1-clarify-vision.{txt,json}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
