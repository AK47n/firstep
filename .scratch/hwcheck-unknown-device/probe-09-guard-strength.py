# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/09 的**判据强度探针**（反证）：把八条旧坏法注入回去，
看本单的新用例是不是真的变红，再逐字节复原并复核 sha256。

八条注入各打本单一条新守卫（AI 排障带自建件事实）：

* **注入 A** —— 上下文不再印「自建器件」段 →
  `test_context_text_carries_the_custom_device_facts_section` 变红；
* **注入 B** —— 自建件 id 的专用判据拿掉（回到"只靠 slug 词形"）→
  `test_a_custom_id_is_judged_regardless_of_case` 变红（大小写混写的 id 两个方向
  都判不到）；
* **注入 C** —— 件名里的词不再放行 →
  `test_a_custom_name_that_collides_with_a_library_slug_is_not_rejected` 变红；
* **注入 D** —— 排障端点不再把自建件计划送进上下文（`customs=board["custom"]`
  换回空）→ `test_triage_context_carries_the_custom_device_facts` 变红；
* **注入 E** —— 排障的重投影不再吃工程内快照（08 留下的那处记账）→
  `test_triage_context_prefers_the_project_snapshot` 变红；
* **注入 F** —— 地址行不再空段守卫（非 I2C 件印出空地址行）→
  `test_a_custom_device_without_an_address_prints_no_empty_address_line` 变红；
* **注入 G** —— 05 留下的那句旧措辞改回去（"还进不了它的上下文"）→
  `test_the_no_probe_sentence_no_longer_says_the_facts_miss_the_context` 变红；
* **注入 H** —— 提示词拿掉「自建件」那一段 →
  `test_the_triage_prompt_says_custom_conclusions_come_from_user_facts` 变红。

⚠ 纪律（本仓库先例 `module-hwcheck/09`、`probe-05/06/07/08/12-guard-strength.py`）：
**别和测试套件同时跑**——探针会真的改库内文件（改完逐字节复原）。
⚠ 先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。
⚠ 源码读写一律走 **bytes**（文本模式会把 CRLF 归一成 LF，"复原复核"当场假红）。
⚠ 行尾两种形态并存：锚点里一律写 `\\n`，`match_anchor` 先试 LF 再试 CRLF。

用法：`python .scratch/hwcheck-unknown-device/probe-09-guard-strength.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYS = REPO / "src" / "contest_generator"
TRIAGE = SYS / "hwcheck_triage.py"
CUSTOM = SYS / "hwcheck_custom.py"
WEBAPP = SYS / "webapp.py"
LLM = SYS / "llm.py"
TRIAGE_TESTS = "tests/test_hwcheck_triage.py"
CUSTOM_TESTS = "tests/test_hwcheck_custom.py"
ENDPOINT_TESTS = "tests/test_my_devices_endpoint.py"

# 八条注入：文件 / 锚点（必须在原文里唯一）/ 替换文本 / 该让哪条用例变红
INJECTIONS = (
    {
        "name": "A: 上下文不再印「自建器件」段",
        "path": TRIAGE,
        "anchor": "    if context.customs_rows:\n",
        "replacement": "    if False:\n",
        "test": "test_context_text_carries_the_custom_device_facts_section",
        "test_file": TRIAGE_TESTS,
    },
    {
        "name": "B: 自建件 id 的专用判据拿掉（只靠 slug 词形）",
        "path": TRIAGE,
        "anchor": "    for token in dict.fromkeys(_CUSTOM_ID_RE.findall(text)):\n",
        "replacement": "    for token in ():\n",
        "test": "test_a_custom_id_is_judged_regardless_of_case",
        "test_file": TRIAGE_TESTS,
    },
    {
        "name": "C: 件名里的词不再放行",
        "path": TRIAGE,
        "anchor": "        if token in facts.custom_words:\n",
        "replacement": "        if False:\n",
        "test": "test_a_custom_name_that_collides_with_a_library_slug_is_not_rejected",
        "test_file": TRIAGE_TESTS,
    },
    {
        "name": "D: 排障端点不再把自建件计划送进上下文",
        "path": WEBAPP,
        "anchor": '            customs=board["custom"],\n',
        "replacement": "            customs=(),\n",
        "test": "test_triage_context_carries_the_custom_device_facts",
        "test_file": ENDPOINT_TESTS,
    },
    {
        "name": "E: 排障重投影不再吃工程内快照",
        "path": WEBAPP,
        "anchor": "            custom_snapshot_dir=output_dir,\n",
        "replacement": "            custom_snapshot_dir=None,\n",
        "test": "test_triage_context_prefers_the_project_snapshot",
        "test_file": ENDPOINT_TESTS,
    },
    {
        "name": "F: 地址行不再空段守卫（非 I2C 件印空地址行）",
        "path": TRIAGE,
        "anchor": "            if address:\n",
        "replacement": "            if True:\n",
        "test": "test_a_custom_device_without_an_address_prints_no_empty_address_line",
        "test_file": TRIAGE_TESTS,
    },
    {
        "name": "G: 05 那句旧措辞改回去（还进不了它的上下文）",
        "path": CUSTOM,
        "anchor": (
            "    \"③ 现象照常填到下面的「现象回填与排障」里——AI 会带上你填的总线 / 地址 / \"\n"
            "    \"寄存器一起给排查方向\"\n"
        ),
        "replacement": (
            "    \"③ 现象照常填到下面的「现象回填与排障」里——它按平台与检测计划给\"\n"
            "    \"「下一步查什么」的方向（你填的地址 / 寄存器这一版还进不了它的上下文）\"\n"
        ),
        "test": "test_the_no_probe_sentence_no_longer_says_the_facts_miss_the_context",
        "test_file": CUSTOM_TESTS,
    },
    {
        "name": "H: 提示词拿掉「自建件」那一段",
        "path": LLM,
        "anchor": (
            "    \"④ 上下文里【自建器件】那几件（材料里标着 [自建件]）是学生自己登记的\"\n"
            "    \"**库外件**，材料给的是\"\n"
            "    \"**用户确认的事实**（名称 / 地址两种写法 / 身份寄存器 / 期望值 / 备注）：\"\n"
            "    \"关于它们只能说这些事实与接线，**不许把结论说成库内模块有问题**（库内根本\"\n"
            "    \"没有这件），也不许把「没有期望值可比、只回显」当成器件坏了；\"\n"
        ),
        "replacement": "    \"④ 上下文里有几件学生自己登记的库外件；\"\n",
        "test": "test_the_triage_prompt_says_custom_conclusions_come_from_user_facts",
        "test_file": TRIAGE_TESTS,
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def match_anchor(path: Path, text: str) -> tuple[bytes, str] | tuple[None, None]:
    """锚点文本 → **文件里真实的那段字节**，连同它的行尾形态。

    ⚠ 行尾必须按文件实况取（本仓库两种形态并存）。锚点里一律写 `\\n`，
    这里先试 LF 再试 CRLF，恰好命中一处才算数；替换文本跟着用同一种行尾。
    """
    data = path.read_bytes()
    for newline in ("\n", "\r\n"):
        candidate = text.replace("\n", newline).encode("utf-8")
        if data.count(candidate) == 1:
            return candidate, newline
    return None, None


def run_test(name: str, test_file: str) -> tuple[bool, str]:
    """跑一条用例；返回（是否通过, 摘要行）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-q", "-p", "no:cacheprovider",
         "-k", name],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=900,
    )
    tail = [
        line.strip() for line in (proc.stdout or "").splitlines()
        if "passed" in line or "failed" in line or "error" in line
    ]
    return proc.returncode == 0, (tail[-1] if tail else f"exit={proc.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(Path(__file__).with_suffix(".txt")),
        help="证据文件（UTF-8，先落盘再打印；缺省 = 与本探针同名的 .txt）",
    )
    args = parser.parse_args()

    lines: list[str] = []
    ok_all = True
    files = (TRIAGE, CUSTOM, WEBAPP, LLM)
    before = {path: sha256(path) for path in files}

    lines.append("[1] 前置检查（源文件指纹与锚点唯一性）")
    for injection in INJECTIONS:
        path: Path = injection["path"]
        anchor, newline = match_anchor(path, injection["anchor"])
        assert anchor is not None, (
            f"{path.name} 里锚点不唯一或找不到（注入目标必须恰好一处）："
            f"{injection['name']}"
        )
        injection["_anchor_bytes"] = anchor
        injection["_newline"] = newline
    for path in files:
        lines.append(f"    {path.name}: {sha256(path)[:16]}…（锚点各一处 ✓）")

    cases = [(item["test"], item["test_file"]) for item in INJECTIONS]
    base = [run_test(name, test_file) for name, test_file in cases]
    base_ok = all(good for good, _ in base)
    lines.append(
        f"[2] 注入前（守卫在）："
        f"{'PASS（' + str(len(cases)) + ' 条全绿）' if base_ok else 'RED ✗'}"
        f"  ｜ {' / '.join(tail for _g, tail in base)}"
    )
    ok_all = ok_all and base_ok

    for injection in INJECTIONS:
        path: Path = injection["path"]
        original_bytes = path.read_bytes()
        anchor: bytes = injection["_anchor_bytes"]
        replacement = injection["replacement"].replace(
            "\n", injection["_newline"]
        ).encode("utf-8")
        try:
            path.write_bytes(original_bytes.replace(anchor, replacement))
            good, tail = run_test(injection["test"], injection["test_file"])
            lines.append(
                f"[3] 注入 {injection['name']} → "
                f"{'RED（守卫变红）' if not good else '仍绿（守卫没抓住！）'} ｜ {tail}"
            )
            ok_all = ok_all and not good
        finally:
            path.write_bytes(original_bytes)
            restored = sha256(path) == before[path]
            lines.append(
                f"[4] 复原复核：{path.name} sha256 "
                f"{'相等 ✓' if restored else '不相等 ✗'}（{sha256(path)[:16]}…）"
            )
            ok_all = ok_all and restored

    for name, test_file in cases:
        good, tail = run_test(name, test_file)
        lines.append(f"[5] 复原后复跑：{name} {'PASS（回绿）' if good else 'RED ✗'} ｜ {tail}")
        ok_all = ok_all and good

    final = {path: sha256(path) for path in files}
    same = final == before
    lines.append(
        f"[6] 收尾指纹：{f'{len(files)} 个文件逐字节未变 ✓' if same else '有文件被改动 ✗'}"
    )
    ok_all = ok_all and same
    lines.append("")
    lines.append(
        "=== 结论：" + (f"反证成立（{len(INJECTIONS)} 条注入都让对应用例变红，"
                       "且逐字节复原）"
                       if ok_all else "反证不成立（见上面读数）") + " ==="
    )
    report = "\n".join(lines) + "\n"
    Path(args.out).write_text(report, encoding="utf-8")          # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 再打印
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
