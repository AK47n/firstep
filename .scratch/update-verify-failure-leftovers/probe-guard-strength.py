# -*- coding: utf-8 -*-
"""判据强度探针：把「不可重试的校验失败要清干净」这条守卫弄坏，看它会不会红。

为什么要它：「守卫全绿」本身不说明任何事——**把被测行为改坏、守卫必须转红**才算数
（照 `.scratch/update-restart-stale-service/probe-guard-strength.py` 的先例）。

两个方向都要注入，因为这条分界有两边，只注入一边等于只证明了一半：

- ①「一律不清」= 改动前的行为（不可重试的校验失败也留半成品 + 边车）；
- ②「一律清」= 过度修正（连网络失败的断点也删掉）。

每一个用例：改坏一处 → 跑对应测试 → 记「红/绿」→ **无论结果如何都复原**
（`finally` 里按原字节写回，并复核 sha256）。

判据：**每一条注入都必须转红**。有绿的 = 那条守卫是摆设 → 探针退出码非 0。

用法::

    python .scratch/update-verify-failure-leftovers/probe-guard-strength.py
    # 证据落 verify-01-guard-strength.txt / .json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

# 控制台是 GBK（Windows 中文默认）：脚本里的 ✓ / ✗ / 中文必须能出去，
# 否则打印时抛 UnicodeEncodeError 把整轮探针打断（照 drill-02 的先例）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

TASK_DOWNLOAD = "src/contest_generator/task_download.py"
TEST_FILE = "tests/test_task_download.py"

#: (名字, 改前（必须唯一命中）, 改后)
CASES: list[tuple[str, str, str]] = [
    (
        "① 一律不清（回到改动前：不可重试的校验失败也留半成品与边车）",
        "                if is_terminal_verify(exc):",
        "                if False:  # noqa: SIM223 —— 注入：一律不清",
    ),
    (
        "② 一律清（过度修正：连网络失败的断点也删掉）",
        "                if is_terminal_verify(exc):",
        "                if True:  # 注入：一律清",
    ),
    (
        "③ 分类判据被换成「只看 error_kind」（把可重试的内容不符也判成终态）",
        '    return (download_resume.error_kind(exc) == "verify"\n'
        "            and not download_resume.is_retryable(exc))",
        '    return download_resume.error_kind(exc) == "verify"',
    ),
]

LINES: list[str] = []
RESULTS: dict = {"cases": []}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def read_text(relative: str) -> str:
    """按**字节**读再解码（不用 `Path.read_text`）。

    文本模式读会把 CRLF 归一成 LF、写回时再换回来——文件里只要有一处混行，一次往返
    就把整份文件的换行统一了，于是「复原复核」报假红。判据要的是**逐字节复原**。
    """
    return (ROOT / relative).read_bytes().decode("utf-8")


def write_text(relative: str, text: str) -> None:
    (ROOT / relative).write_bytes(text.encode("utf-8"))


def newline_of(text: str) -> str:
    """目标文件的换行风格（探针里的锚点一律以 LF 书写，注入前要适配）。"""
    return "\r\n" if "\r\n" in text else "\n"


def adapt(text: str, newline: str) -> str:
    """把 LF 书写的锚点 / 注入文本适配到目标文件的换行风格（读侧逐字节保真，
    所以 CRLF 文件里的多行锚点带 `\\r\\n`）。"""
    return text.replace("\n", newline) if newline != "\n" else text


def sha256(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def run_tests() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_FILE, "-q", "-p", "no:cacheprovider"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=900,
    )
    tail = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    return proc.returncode == 0, (tail[-1] if tail else "(无输出)")


def main() -> int:
    log("# 判据强度探针：「不可重试的校验失败不留半成品」（工单 update-verify-failure-leftovers/01）")
    log(f"  仓库：{ROOT}")
    log("  判据：**每一条注入都必须转红**（有绿的 = 那条守卫是摆设）")
    log("")

    baseline_sha = sha256(TASK_DOWNLOAD)

    # 前置：源文件必须是**干净的**（所有锚点都在）。探针被强杀（工具超时 / Ctrl-C）时
    # `finally` 跑不到，源文件会停在注入态——那时后面每条都报「锚点失效」，
    # 看起来像探针写错了，其实是上一轮没复原。这一步把那种情况变成一句明确的拒绝。
    pristine = read_text(TASK_DOWNLOAD)
    pristine_newline = newline_of(pristine)
    missing = [name for name, old, _new in CASES
               if pristine.count(adapt(old, pristine_newline)) != 1]
    if missing:
        log("**拒绝开跑**：源文件不是干净状态（可能上一轮探针被强杀、没来得及复原）。")
        for name in missing:
            log(f"  · 锚点不在：{name}")
        log(f"  修法：`git checkout -- {TASK_DOWNLOAD}` 之后重跑本探针。")
        RESULTS["preflight_missing"] = missing
        RESULTS["verdict"] = "FAIL"
        return 2
    weak: list[str] = []
    for name, old, new in CASES:
        log("-" * 78)
        log(f"[注入] {name}")
        log(f"  文件：{TASK_DOWNLOAD}")
        original = read_text(TASK_DOWNLOAD)
        newline = newline_of(original)
        hits = original.count(adapt(old, newline))
        if hits != 1:
            log(f"  **锚点命中 {hits} 次（应为 1）——探针自己失效了，本条按失败记**")
            weak.append(f"{name}（锚点失效）")
            RESULTS["cases"].append({"name": name, "anchor_hits": hits,
                                     "turned_red": False, "weak": True})
            continue
        try:
            write_text(TASK_DOWNLOAD,
                       original.replace(adapt(old, newline), adapt(new, newline), 1))
            green, summary = run_tests()
        finally:
            write_text(TASK_DOWNLOAD, original)      # 无论结果如何都复原
        turned_red = not green
        log(f"  测试：{TEST_FILE}")
        log(f"  结果：{'转红 ✓' if turned_red else '**仍然全绿 ✗**'} —— {summary}")
        RESULTS["cases"].append({"name": name, "anchor_hits": hits,
                                 "turned_red": turned_red, "summary": summary,
                                 "weak": not turned_red})
        if not turned_red:
            weak.append(name)

    log("")
    log("-" * 78)
    log("## 复原复核")
    after = sha256(TASK_DOWNLOAD)
    log(f"  {TASK_DOWNLOAD} sha256 "
        f"{'未变 ✓' if after == baseline_sha else f'**变了 ✗（{baseline_sha[:12]} → {after[:12]}）**'}")
    if after != baseline_sha:
        weak.append(f"{TASK_DOWNLOAD} 未复原")

    log("")
    log("## 总判")
    red = sum(1 for case in RESULTS["cases"] if case["turned_red"])
    log(f"  {red}/{len(CASES)} 条注入成功转红")
    for name in weak:
        log(f"  · 守卫薄弱：{name}")
    RESULTS["weak"] = weak
    RESULTS["verdict"] = "PASS" if not weak else "FAIL"
    log(f"  探针：{'PASS' if not weak else 'FAIL'}")
    return 0 if not weak else 1


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        (HERE / "verify-01-guard-strength.txt").write_text("\n".join(LINES) + "\n",
                                                           encoding="utf-8")
        (HERE / "verify-01-guard-strength.json").write_text(
            json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n证据已写：verify-01-guard-strength.txt / .json")
    raise SystemExit(code)
