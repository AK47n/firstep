# -*- coding: utf-8 -*-
"""工单 module-hwcheck/08 的**判据强度探针**（仓库纪律：每条新守卫都要有一次
"停用后用例必须变红"的实测）。

做法：对每个判据做一处**最小停用**（源码逐字节替换）→ 跑点名的那几条用例 →
要求它们变红 → **逐字节复原**并复核（`file_bytes == original`）。任何一步不符
就当场报 FAIL，末尾打印 PASS/FAIL 清单。

用法：`python .scratch/module-hwcheck/probe-08-guard-strength.py`
（约 1 分钟；全程只改这 5 处，跑完源码与开工前逐字节相同。）
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Mutation:
    """一处停用：文件 + 原文 + 替换文 + 期望变红的用例 + 怎么跑。"""

    name: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    runner: str = "pytest"  # pytest | node


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        name="事实约束查表被停用（引脚 / 模块白名单）",
        path="src/contest_generator/hwcheck_triage.py",
        old="    violations = check_advice_facts(advice, context.facts)\n",
        new="    violations = ()\n",
        tests=(
            "tests/test_hwcheck_triage.py::test_parse_advice_rejects_invented_pin",
            "tests/test_hwcheck_triage.py::test_parse_advice_rejects_module_that_is_not_in_this_detection",
            "tests/test_hwcheck.py::test_triage_endpoint_rejects_facts_outside_the_context",
        ),
    ),
    Mutation(
        name="LLM 失败不再兜底（把降级路径改成直接抛）",
        path="src/contest_generator/webapp.py",
        old=(
            "            message = str(exc)\n"
            "            advice = fallback_advice(triage_context)\n"
            "            degraded = True\n"
        ),
        new="            raise\n",
        tests=(
            "tests/test_hwcheck.py::test_triage_endpoint_degrades_without_blocking_when_llm_fails",
        ),
    ),
    Mutation(
        name="排障记录不落盘（triage 端点）",
        path="src/contest_generator/webapp.py",
        old=(
            "        record = record_with_advice(record, advice)\n"
            "        write_hwcheck_record(output_dir, record)\n"
        ),
        new="        record = record_with_advice(record, advice)\n",
        tests=(
            "tests/test_hwcheck.py::test_triage_endpoint_returns_advice_and_persists_the_record",
            "tests/test_hwcheck.py::test_triage_endpoint_degrades_without_blocking_when_llm_fails",
        ),
    ),
    Mutation(
        name="清单勾选不落盘（checklist 端点）",
        path="src/contest_generator/webapp.py",
        old=(
            "        record = record_with_checked(record, tuple(_require_str_list(payload, \"checked_ids\")))\n"
            "        write_hwcheck_record(output_dir, record)\n"
        ),
        new=(
            "        record = record_with_checked(record, tuple(_require_str_list(payload, \"checked_ids\")))\n"
        ),
        tests=(
            "tests/test_hwcheck.py::test_checklist_endpoint_persists_ticks_and_project_reads_them_back",
        ),
    ),
    Mutation(
        name="勾选响应整份采纳（会把没提交的现象吃掉）",
        path="src/contest_generator/static/js/ui/hwcheck.js",
        old="    Object.assign(hwcheckUI, hwcheckChecklistState(hwcheckUI, payload));\n",
        new="    Object.assign(hwcheckUI, hwcheckRecordState(hwcheckUI, payload));\n",
        tests=("tests/js/hwcheck.test.mjs",),
        runner="node",
    ),
    Mutation(
        name="材料里出现过的脚不算事实（评审 ① 那条两张皮回到旧样）",
        path="src/contest_generator/hwcheck_triage.py",
        old=(
            "    for text in material_texts:\n"
            "        if isinstance(text, str) and text:\n"
            "            pins.update(_PIN_TOKEN_RE.findall(text))\n"
        ),
        new="",
        tests=(
            "tests/test_hwcheck_triage.py::test_pins_quoted_from_the_material_are_allowed",
            "tests/test_hwcheck_triage.py::test_pin_mentioned_in_the_symptom_is_allowed",
        ),
    ),
    Mutation(
        name="勾选端点不判 kind（能往赛题工程里写检测记录）",
        path="src/contest_generator/webapp.py",
        old="    read_hwcheck_project(output_dir)\n    return output_dir\n",
        new="    return output_dir\n",
        tests=(
            "tests/test_hwcheck.py::test_triage_endpoint_400s_on_empty_symptom_and_unknown_dir",
        ),
    ),
    Mutation(
        name="事实错退回 parse 快重试（丢掉 domain 分道）",
        path="src/contest_generator/llm.py",
        old=(
            "            except TriageFactError as exc:\n"
            "                raise LLMError(str(exc), kind=ERROR_KIND_DOMAIN) from exc\n"
        ),
        new="",
        tests=(
            "tests/test_llm.py::test_triage_fact_rejection_is_domain_kind_and_retries_with_the_reason",
        ),
    ),
    Mutation(
        name="反馈出口缺省失效（模型不给就没有出口）",
        path="src/contest_generator/hwcheck_triage.py",
        old="        issue_hint=issue_hint or DEFAULT_ISSUE_HINT,\n",
        new="        issue_hint=issue_hint,\n",
        tests=(
            "tests/test_hwcheck_triage.py::test_parse_advice_issue_hint_defaults_to_the_repair_ticket_exit",
        ),
    ),
)


def run_tests(mutation: Mutation) -> tuple[bool, str]:
    """跑点名用例；返回（有没有红，输出尾巴）。"""
    if mutation.runner == "node":
        cmd = ["node", "--test", *mutation.tests]
    else:
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *mutation.tests]
    proc = subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    tail = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode != 0, tail.strip().splitlines()[-1] if tail.strip() else ""


def main() -> int:
    verdicts: list[str] = []
    for mutation in MUTATIONS:
        path = REPO / mutation.path
        original = path.read_bytes()
        text = original.decode("utf-8")
        # 行尾按文件自身的约定（本仓库 Windows 工作树里 webapp.py / ui/*.js 是 CRLF，
        # 新建的 .py 是 LF）——探针写的是 "\n"，这里逐文件归一，否则多行片段匹配 0 次
        newline = "\r\n" if "\r\n" in text else "\n"
        old = mutation.old.replace("\n", newline)
        new = mutation.new.replace("\n", newline)
        if text.count(old) != 1:
            verdicts.append(
                f"FAIL  {mutation.name}：原文匹配 {text.count(old)} 次（要求恰好 1 次）"
            )
            continue
        try:
            path.write_bytes(text.replace(old, new).encode("utf-8"))
            red, tail = run_tests(mutation)
        finally:
            path.write_bytes(original)
        restored = path.read_bytes() == original
        verdicts.append(
            f"{'PASS' if (red and restored) else 'FAIL'}  {mutation.name}"
            f"（变红={red} / 逐字节复原={restored}）  {tail}"
        )
    print("\n".join(verdicts))
    return 0 if all(v.startswith("PASS") for v in verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
