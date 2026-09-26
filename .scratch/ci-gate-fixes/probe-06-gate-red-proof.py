# -*- coding: utf-8 -*-
"""工单 ci-gate-fixes/06 的判据强度探针：把路由换回两种**旧形态**，验收用例必须
当场变红；每次跑完逐字节复原并复核 sha256。

做法 = **区域手术**：闸门那一段（`project_dirs` 那行与 `llm_run = LLMRun(...) 那行
之间）整段替换成旧形态——按标记行切，不锚注释与排版（注释会随文档改写而漂）。

两种注入形态（都是"修法只做了一半"的真实样子）：

* **A = 无条件要 AI 配置**（本单开工前的形状）：函数一进来就 `_require_config`，
  参考库根无条件推 ⇒ 「无归档 + 空 key」用例应红（答 400 而不是 200）。
* **B = 只有"按需"那一半**（闸门摘掉，AI 配置只剩事务里那一步懒取）⇒ 归档载荷下
  事务先跑起来，报的是事务自己的「工程目录不存在」⇒ 「那声 400 是闸门给的」用例
  应红。磁盘零变化那条分辨不出 B 与修好后（中途 400 也不留痕），故判据单独钉。

判据强度 = 用例能不能抓住旧行为，不是"跑一遍绿"。探针只动 webapp.py，跑完复原；
**别与测试套件并行跑**（探针期间源码在注入态，别的用例会读到中间态——见
local-environment 第 2 节那条纪律）。

用法：python .scratch/ci-gate-fixes/probe-06-gate-red-proof.py
读数落 .scratch/ci-gate-fixes/probe-06-red-proof.txt（UTF-8）。
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "src" / "contest_generator" / "webapp.py"
OUT = REPO / ".scratch" / "ci-gate-fixes" / "probe-06-red-proof.txt"

#: 闸门区域的起止标记行（按 webapp.py 的实际换行 CRLF 写；各应恰好出现一次）
REGION_START = (
    '        project_dirs = [Path(d) for d in _require_str_list(payload, "project_dirs")]\r\n'
)
REGION_END = '        llm_run = LLMRun(context, "masters-confirm")\r\n'

#: 注入配方：(标签, 换进区域里的代码, 期望变红的用例)
INJECTIONS = (
    (
        "A 无条件要 AI 配置（本单开工前的形状）",
        "        config = _require_config(context)\r\n"
        "        reference_dir = reference_library_dir(config.module_library_dir)\r\n",
        "test_confirm_without_archive_needs_no_ai_key_and_really_imports",
    ),
    (
        "B 只做「按需」那一半（闸门摘掉，留给事务里懒取）",
        "        config = _library_config(context)\r\n"
        "        reference_dir = reference_library_dir(config.module_library_dir)\r\n",
        "test_confirm_with_archive_without_key_is_the_gate_talking",
    ),
)

GATE = "tests/test_library_gate.py::"
TESTS = [
    GATE + "test_confirm_without_archive_needs_no_ai_key_and_really_imports",
    GATE + "test_confirm_with_archive_without_key_is_refused_before_any_write",
    GATE + "test_confirm_with_archive_without_key_is_the_gate_talking",
    GATE + "test_confirm_with_archive_without_key_never_enters_the_transaction",
]


def inject(text: str, body: str) -> str:
    """把 `project_dirs` 行与 `llm_run` 行之间的整段换成 `body`。"""
    head, _, rest = text.partition(REGION_START)
    _region, sep, tail = rest.partition(REGION_END)
    assert sep, "区域终点标记不在文件里"
    return head + REGION_START + body + REGION_END + tail


def run_tests(label: str, lines: list[str]) -> None:
    lines.append(f"--- {label} ---")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", *TESTS],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines.append(f"exit={proc.returncode}")
    for line in (proc.stdout or "").strip().splitlines():
        if line.startswith(("FAILED", "PASSED", "ERROR")) or " passed" in line \
                or " failed" in line:
            lines.append(line)
    if proc.stderr.strip():
        lines.append("[stderr] " + proc.stderr.strip()[-500:])


def main() -> int:
    try:  # PowerShell 的控制台是 GBK：探针自己的回显不该因编码炸掉（读数已落盘）
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - 回显尽力而为
        pass
    original = WEBAPP.read_bytes()
    sha_before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    if text.count(REGION_START) != 1 or text.count(REGION_END) != 1:
        print("前置干净性检查失败：闸门区域的起止标记不是各一处（已改过？）")
        return 2
    lines = [f"webapp.py sha256（注入前）={sha_before}"]
    try:
        for tag, body, expected_red in INJECTIONS:
            WEBAPP.write_bytes(inject(text, body).encode("utf-8"))
            run_tests(f"注入态 {tag} —— 期望 {expected_red} 变红", lines)
            WEBAPP.write_bytes(original)
    finally:
        WEBAPP.write_bytes(original)
    sha_after = hashlib.sha256(WEBAPP.read_bytes()).hexdigest()
    lines.append(f"webapp.py sha256（复原后）={sha_after}")
    lines.append(f"逐字节复原={'是' if sha_after == sha_before else '**否**'}")
    run_tests("复原后 —— 三条用例应全绿", lines)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if sha_after == sha_before else 3


if __name__ == "__main__":
    raise SystemExit(main())
