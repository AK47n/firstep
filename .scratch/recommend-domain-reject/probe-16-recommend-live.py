"""第十六轮探针：产品内进程跑一次真实推荐（**不经 webapp**），可选写进 CLI 缓存。

为什么要它（本轮 A8 实测）：2026H / mspm0 走 webapp 时 select_modules 偶发
`error_kind=client`（http 200 / parse_error / attempts=1 / 未重试），而
`errors.llm_error_message` 的 client 分支把所有 client 类错误统一换成
「AI 服务拒绝了本次请求（…）」——**真实理由看不见**。本探针走产品自己的
`selection.run_recommendation`（澄清门 + 收敛循环 + 视觉问答回调一律照旧），
用内存注入的诊断行把真实异常打出来（磁盘 llm.py 零改动，做法同
`.scratch/recommend-domain-reject/probe-16-select-reject.py`）。

第十七轮更新（工单 real-acceptance/03 落地后复跑用）：域拒绝的翻译点已从
`kind=ERROR_KIND_CLIENT` 改为 `kind=ERROR_KIND_DOMAIN`，锚点随源码同步；
此时的现场应出现两种形态之一——① 首轮域拒绝 + 次轮通过（自愈，`[PROBE16]
[域拒绝]` 只出现一次且终态 done）；② 两次都被拒（`[重试耗尽] kind= domain`
且**终态 error 文案带真实理由**，不再说「API key / 余额」）。

顺带产出：成功时把 done 载荷按 `generate_check.cache_recommend` 的同款形状
写进 `.scratch/real-run/cache/recommend_<topic>.json`（`--write-cache`），
让后续 `generate_check --reuse-recommend` 复用这次真实推荐（省额度）。

用法：
    $env:PYTHONPATH='src'; python .scratch/recommend-domain-reject/probe-16-recommend-live.py \
        --topic 2026H --platform mspm0 --attempts 3 --write-cache
"""
from __future__ import annotations

import argparse
import json
import queue
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / ".scratch" / "real-run"))

# --vision-qa 开关（run_once 内读；CLI 解析后写入）
args_vision_qa_flag = False
# --extra-words 词表追加（{类别: [型号…]}；run_once 内读）
args_extra_words: dict[str, list[str]] = {}
# --fake-clarify 注入的补问清单（None = 不注入）
args_fake_clarify: tuple[str, ...] | None = None

import contest_generator.llm as llm_mod  # noqa: E402
from contest_generator import events as ev  # noqa: E402
from contest_generator.config import load_config  # noqa: E402
from contest_generator.generator import resolve_topic_context  # noqa: E402
from contest_generator.selection import run_recommendation  # noqa: E402
from contest_generator.sse import SseEmitter  # noqa: E402

ANCHORS = (
    (
        '                raise LLMError(str(exc), kind=ERROR_KIND_DOMAIN) from exc\n',
        '                print("[PROBE16][域拒绝] SelectionError →", str(exc)[:900],\n'
        '                      flush=True)\n'
        '                raise LLMError(str(exc), kind=ERROR_KIND_DOMAIN) from exc\n',
    ),
    (
        '        _raise_retry_exhausted(label, attempts, last_error)\n',
        '        print("[PROBE16][重试耗尽]", type(last_error).__name__,\n'
        '              "kind=", getattr(last_error, "kind", None), "|",\n'
        '              str(last_error)[:900], flush=True)\n'
        '        _raise_retry_exhausted(label, attempts, last_error)\n',
    ),
    (
        '                    raise LLMError(\n'
        '                        "模块选择输出异常超长（"\n',
        '                    print("[PROBE16][超长守卫]", len(content), flush=True)\n'
        '                    raise LLMError(\n'
        '                        "模块选择输出异常超长（"\n',
    ),
)


def inject(src_path: Path) -> None:
    """内存注入诊断行（锚点必须唯一，否则大声失败）。"""
    src = src_path.read_text(encoding="utf-8")
    for old, new in ANCHORS:
        n = src.count(old)
        if n != 1:
            print(f"⚠ 锚点命中 {n} 处（跳过该注入点）：{old.strip()[:50]!r}")
            continue
        src = src.replace(old, new)
    exec(compile(src, str(src_path), "exec"), llm_mod.__dict__)


def run_once(topic_key: str, platform: str, clarify_answers: dict[str, str]):
    """跑一次推荐；返回 (终态kind, data, 轮次, 问题清单)。

    与 webapp 推荐路由同装配（webapp.py:1721-1739）：清单行先换瘦身形态 →
    预筛（`preselect_module_summaries`）→ 子集化时带 preselect_note，否则
    全量清单行——复刻这一段是为了「探针跑出来的东西 = 网页跑出来的东西」，
    否则两处推荐的 token 预算不同，偶发失败也没法互相印证。
    """
    from dataclasses import replace

    from contest_generator.budget import MODULE_SUMMARY_BYTES
    from contest_generator.llm import DEFAULT_WORDLIST
    from contest_generator.selection import preselect_module_summaries

    cfg = load_config()
    root = REPO / "library"
    topic_md = root / "topics" / topic_key / "topic.md"
    problem_text = topic_md.read_text(encoding="utf-8")
    llm = llm_mod.build_llm(cfg)
    if args_extra_words:
        # 词表外硬件名 → 降级为**词表内类别名**的实测口径：把卡住的那个名字
        # 作为一条候选**型号**加进默认词表（不新建类别——型号经
        # `_solution_group` 反查落在「感知传感器」行），用于回答
        # 「2022C 反复卡死在词表闸，是词表的锅还是推荐的锅」。
        from contest_generator.wordlist import HardwareWordGroup
        groups = list(llm_mod.DEFAULT_WORDLIST)
        for cat, extra in args_extra_words.items():
            for i, g in enumerate(groups):
                if g.category == cat:
                    groups[i] = HardwareWordGroup(
                        category=g.category,
                        models=tuple(g.models) + tuple(extra),
                        solutions=g.solutions,
                    )
                    break
            else:
                groups.append(HardwareWordGroup(
                    category=cat, models=tuple(extra), solutions={}
                ))
        llm = llm_mod.DeepSeekLLM(cfg, hardware_words=tuple(groups))
        print(f"[词表] 追加候选型号：{args_extra_words}", flush=True)
    topic = resolve_topic_context(
        llm=None,
        topic_key=topic_key,
        problem_text=problem_text,
        module_library_dir=root / "modules",
        topic_library_dir=root / "topics",
        reference_library_dir=root / "references",
        platform=platform,
    )
    topic = replace(
        topic,
        manifest_summaries=tuple(s.lean_copy() for s in topic.manifest_summaries),
    )
    presel = preselect_module_summaries(
        topic.manifest_summaries, topic.problem_text,
        DEFAULT_WORDLIST, MODULE_SUMMARY_BYTES,
    )
    preselect_note = ""
    if presel.truncated:
        topic = replace(topic, manifest_summaries=presel.summaries)
        preselect_note = (
            f"（按题面初筛 {len(presel.summaries)}/{presel.total} 条，"
            f"仅展示前 {MODULE_SUMMARY_BYTES} wire 字节）"
        )
    print(f"[装配] 清单行 {len(topic.manifest_summaries)} 条"
          f"（截断={presel.truncated}）note={preselect_note!r}", flush=True)
    events: queue.Queue = queue.Queue()
    emitter = SseEmitter(events, terminal_timeout=5.0)
    rounds: list[int] = []
    terminal: list[tuple[str, dict]] = []
    holder: dict = {"vision": []}

    vision_qa = None
    if args_vision_qa_flag:
        from contest_generator.vision_qa import answer_figure_question
        from contest_generator.vision import effective_vision_api_key
        if topic.figure_pdf is not None:
            vkey = effective_vision_api_key(
                cfg.vision_api_key, cfg.api_key, cfg.vision_base_url
            )
            vmodel = cfg.vision_model or "deepseek-flash"
            vision_log: list[dict] = holder["vision"]

            def vision_qa(question: str):  # noqa: ANN202
                print(f"[视觉] 图内问题消化：{question[:80]}", flush=True)
                ans = answer_figure_question(
                    topic.figure_pdf, topic.problem_text, question,
                    vision_base_url=cfg.vision_base_url,
                    vision_api_key=vkey, vision_model=vmodel,
                )
                vision_log.append({"question": question, "answer": ans})
                print(f"[视觉] 答案：{str(ans)[:400]}", flush=True)
                return ans

    class _Emit:
        def progress(self, event):  # noqa: ANN001
            if getattr(event, "type", "") == ev.EVENT_ROUND:
                rounds.append(getattr(event, "round", 0))

        def done(self, data):  # noqa: ANN001
            terminal.append(("done", data))
            emitter.done(data)

        def question(self, data):  # noqa: ANN001
            questions = list((data or {}).get("questions", []))
            holder.setdefault("questions", []).extend(questions)
            terminal.append(("question", data))
            emitter.question(data)

        def error(self, data):  # noqa: ANN001
            terminal.append(("error", data))
            emitter.error(data)

    clarifications = tuple((q, a) for q, a in clarify_answers.items())
    if args_fake_clarify is not None and not clarifications:
        # 注入式：只替换「模型这一轮澄清门的输出」，其余真代码真服务
        llm.clarify = lambda problem_text, hist=(): tuple(args_fake_clarify)
        print(f"  [注入] llm.clarify → 恒返回 {len(args_fake_clarify)} 条构造补问",
              flush=True)
    try:
        run_recommendation(
            topic, llm, clarifications, emit=_Emit(), platform=platform,
            preselect_note=preselect_note, vision_qa=vision_qa,
        )
    except Exception as exc:  # noqa: BLE001 - 探针就是要看真实异常
        print(f"[PROBE16][编排抛错] {type(exc).__name__}: {str(exc)[:600]}", flush=True)
        return ("exception", {"message": f"{type(exc).__name__}: {exc}"}, rounds, [],
                holder.get("vision", []))

    if not terminal:
        return "nostream", {"message": "无终态事件"}, rounds, [], holder.get("vision", [])
    kind, data = terminal[-1]
    return (kind, data, rounds, list(holder.get("questions", [])),
            list(holder.get("vision", [])))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="2026H")
    parser.add_argument("--platform", default="mspm0")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--write-cache", action="store_true")
    parser.add_argument("--clarify-answers", default="", help="JSON 文件：{问题: 答案}")
    parser.add_argument("--vision-qa", action="store_true",
                        help="注入真视觉问答回调（C1 主链路用）")
    parser.add_argument("--evidence", default="")
    parser.add_argument("--extra-words", default="",
                        help='JSON：{"类别": ["型号", …]} 追加进默认词表')
    parser.add_argument("--extra-words-file", default="",
                        help="同上，从文件读（PowerShell 传 JSON 字面量会被剥引号）")
    parser.add_argument("--fake-clarify", default="",
                        help="JSON 数组：把 llm.clarify 换成恒返回这些问题（注入式探针）")
    parser.add_argument("--fake-clarify-file", default="", help="同上，从文件读")
    parser.add_argument(
        "--out-prefix", default="done-16",
        help="done 载荷落盘前缀（缺省 done-16 覆写第十六轮现场件；"
             "复跑请用 --out-prefix done-17 另存，别污染历史证据）",
    )
    args = parser.parse_args()

    inject(REPO / "src" / "contest_generator" / "llm.py")
    print(f"[探针] 注入诊断行完成（磁盘 llm.py 零改动）；"
          f"topic={args.topic} platform={args.platform} attempts={args.attempts}")
    global args_vision_qa_flag, args_extra_words, args_fake_clarify
    args_vision_qa_flag = args.vision_qa
    if args.fake_clarify or args.fake_clarify_file:
        raw_q = (
            Path(args.fake_clarify_file).read_text(encoding="utf-8")
            if args.fake_clarify_file else args.fake_clarify
        )
        args_fake_clarify = tuple(json.loads(raw_q))
    if args.extra_words or args.extra_words_file:
        raw_words = (
            Path(args.extra_words_file).read_text(encoding="utf-8")
            if args.extra_words_file else args.extra_words
        )
        args_extra_words = {
            str(k): [str(x) for x in v]
            for k, v in json.loads(raw_words).items()
        }

    clarify_answers: dict[str, str] = {}
    if args.clarify_answers:
        clarify_answers = json.loads(
            Path(args.clarify_answers).read_text(encoding="utf-8")
        )

    last = None
    for attempt in range(1, args.attempts + 1):
        print(f"\n===== 第 {attempt}/{args.attempts} 次真实推荐 =====", flush=True)
        kind, data, rounds, questions, vision_log = run_once(
            args.topic, args.platform, clarify_answers
        )
        print(f"[结果] 终态 {kind}；收敛轮次 {rounds}；"
              f"补问 {len(questions)} 条；视觉消化 {len(vision_log)} 次", flush=True)
        for item in vision_log:
            print(f"  [视觉消化] 问题：{item['question'][:90]}", flush=True)
            print(f"           答案：{str(item['answer'])[:200]}", flush=True)
        last = (kind, data, rounds, questions, vision_log)
        if kind == "done":
            break
        if kind == "question" and questions:
            print("  补问清单：", flush=True)
            for q in questions:
                print("   -", q, flush=True)
            if not clarify_answers:
                print("  （无 --clarify-answers，本轮到此为止——用答案文件重跑）",
                      flush=True)
                break

    kind, data, rounds, questions, vision_log = last
    if kind == "done":
        slugs = [m.get("slug") for m in data.get("modules", [])]
        print(f"[done] 模块 {len(slugs)}：{', '.join(slugs)}", flush=True)
        instances = data.get("instances") or {}
        print(f"[done] 多实例猜测：{json.dumps(instances, ensure_ascii=False)}",
              flush=True)
        print(f"[done] 功能需求层 {len(data.get('requirements') or [])} 条；"
              f"互斥组 {len(data.get('exclusive_groups') or [])} 个；"
              f"参考资料 {len(data.get('references') or [])} 条", flush=True)
        out = REPO / ".scratch" / "recommend-domain-reject" / (
            f"{args.out_prefix}-{args.topic}-{args.platform}.json"
        )
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"[落盘] done 载荷 → {out}", flush=True)
        if args.write_cache:
            import generate_check as gc
            cpath = gc.recommend_cache_path(args.topic)
            gc.cache_recommend(
                cpath, data, topic_key=args.topic,
                problem_text=(REPO / "library" / "topics" / args.topic /
                              "topic.md").read_text(encoding="utf-8"),
                platform=args.platform,
                reference_ids=(), clarify_hist=(),
            )
            print(f"[缓存] 已写 {cpath}", flush=True)
            return 0
    print("[未收敛] 见上面 [PROBE16] 行与终态 data", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
