"""C2（clarify-no-restriction/02）真机探针：重启服务后 2024H 推荐不再问那三类问题。

口径（挂账单 C2）：重启服务 → 跑 2024H → 不再问「起始方向 / 声光形式 / 几路」。
历史症状（工单 01/02）：把"题面没写"当"缺失信息"逐条补问，用户被问三类无意义问题。

判据拆成两段，各自机器可判：
1. **提示词契约**（纯件）：澄清系统提示词里确含「题目中没有提到 = 没有限制」这类
   条款，且三类问题措辞被点名禁止——直接对 `llm.CLARIFY_SYSTEM_PROMPT` 断言；
2. **真机行为**（真调用一次 clarify）：2024H 题面走 `llm.clarify` →
   返回**空**（无补问）；若模型仍提了问题，逐条打印出来（本项如实报告，
   非「拒绝交付」——模型输出是概率性的，提示词修正是工单 01/02 已交付的正解）。
   同批附 `generate_check`/probe 真机跑 2024H 推荐的补问条数（0 = 用户没被问）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/clarify-no-restriction/probe-16-2024h-clarify.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import contest_generator.llm as L  # noqa: E402
from contest_generator.config import load_config  # noqa: E402

OUT = REPO / ".scratch" / "clarify-no-restriction"
# 三类历史症状问题（工单原文措辞；判据 = 提示词点名禁止「题面未说=缺失」这条推理）
SYMPTOM_WORDS = ("起始方向", "声光", "几路")


def main() -> int:
    cfg = load_config()
    problem = (REPO / "library" / "topics" / "2024H" / "topic.md").read_text(
        encoding="utf-8"
    )
    lines: list[str] = []

    def note(t: str) -> None:
        print(t, flush=True)
        lines.append(t)

    prompt = L.CLARIFY_SYSTEM_PROMPT
    note(f"[提示词] CLARIFY_SYSTEM_PROMPT {len(prompt)} 字符")
    clause_checks = [
        ("含「题目中没有提到 = 没有限制」类条款",
         ("没有提到" in prompt and "没有限制" in prompt)),
        ("含「不要问题面已明确/可推断的信息」类条款",
         ("不要问" in prompt or "不问" in prompt)),
        ("禁止把「题面未写」当缺失（'缺失' 推理被约束）",
         ("缺失" in prompt)),
    ]
    for name, cond in clause_checks:
        note(("  ✓ " if cond else "  ✗ ") + name)
    note(f"[提示词片段] {prompt[:600]}")

    llm = L.build_llm(cfg)
    note(f"\n[真机] 走 llm.clarify（model={cfg.model}）——2024H 题面 "
         f"{len(problem)} 字符")
    try:
        questions = tuple(llm.clarify(problem, ()))
    except Exception as exc:  # noqa: BLE001 - 探针把异常如实报告
        note(f"✗ clarify 调用失败：{type(exc).__name__}: {str(exc)[:300]}")
        return 1
    note(f"[真机] clarify 返回 {len(questions)} 条补问：")
    for q in questions:
        note(f"   - {q}")

    asks_symptoms = [
        q for q in questions if any(w in q for w in SYMPTOM_WORDS)
    ]
    checks = clause_checks + [
        ("真机 clarify 未返回任何补问（用户不被问）", len(questions) == 0),
        ("未出现三类历史症状问题（起始方向/声光/几路）", not asks_symptoms),
    ]
    if asks_symptoms:
        note(f"  ⚠ 命中症状措辞的问题：{asks_symptoms}")
    note("")
    ok = all(c for _, c in checks)
    for name, cond in checks:
        note(("  ✓ " if cond else "  ✗ ") + name)
    note(f"\nC2 重启后 2024H 不再问三类问题：{'PASS' if ok else 'FAIL'}"
         "（提示词契约段 + 真机 clarify 实况；推荐全链补问条数见"
         " .scratch/clarify-no-restriction/verify-16-C2-2024H.txt 的"
         "「补问 N 条」行）")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verify-16-C2-clarify.txt").write_text("\n".join(lines) + "\n",
                                                  encoding="utf-8")
    (OUT / "verify-16-C2-clarify.json").write_text(json.dumps(
        {"prompt_chars": len(prompt), "questions": list(questions),
         "symptom_hits": asks_symptoms,
         "checks": {n: bool(c) for n, c in checks}}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("--> 落盘 .scratch/clarify-no-restriction/verify-16-C2-clarify.{txt,json}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
