# -*- coding: utf-8 -*-
"""判据强度探针：把「连续 N 次内容不符转终态」这条守卫弄坏，看它会不会红。

为什么要它：「守卫全绿」本身不说明任何事——**把被测行为改坏、守卫必须转红**才算数
（照 `.scratch/update-restart-stale-service/probe-guard-strength.py` 的先例）。

三处注入各代表一种退化方式：

- ① **去掉封顶** = 回到改动前（永远重试、永远 downloading）；
- ② **连续改累计** = 过度修正（偶发坏两次就被判死）；
- ③ **把新错误从「不可重试」表里拿掉** = 分类脱节（终态错误却说自己可重试）。

每一个用例：改坏一处 → 跑对应测试 → 记「红/绿」→ **无论结果如何都复原**
（`finally` 里按原字节写回，并复核 sha256）。

判据：**每一条注入都必须转红**。有绿的 = 那条守卫是摆设 → 探针退出码非 0。

用法::

    python .scratch/update-content-mismatch-retry-cap/probe-guard-strength.py
    # 证据落 verify-02-guard-strength.txt / .json
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

DOWNLOAD_RESUME = "src/contest_generator/download_resume.py"
TEST_FILES = ("tests/test_download_resume.py", "tests/test_task_download.py")

#: (名字, 改前（必须唯一命中）, 改后)
CASES: list[tuple[str, str, str]] = [
    (
        "① 去掉封顶（回到改动前：内容不符永远重试）",
        "                if content_mismatch_streak >= max_content_mismatch:",
        "                if False:  # noqa: SIM223 —— 注入：不再封顶",
    ),
    (
        "② 连续改累计（中途别的错误不再清零）",
        "            else:\n                content_mismatch_streak = 0",
        "            else:\n                pass  # 注入：累计口径",
    ),
    (
        "③ 新错误从「不可重试」表里拿掉（终态错误却自称可重试）",
        "    DownloadRangeNotSatisfiableError,\n"
        "    DownloadContentMismatchPersistentError,\n)",
        "    DownloadRangeNotSatisfiableError,\n)",
    ),
]

LINES: list[str] = []
RESULTS: dict = {"cases": []}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def read_text(relative: str) -> str:
    """按**字节**读再解码（不用 `Path.read_text`）：文本模式的换行归一化会让
    「复原复核」在文件有混行时报假红（实测踩到过）。见 `update-orphan-files`
    那支探针的同名函数。"""
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
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *TEST_FILES, "-q", "-p", "no:cacheprovider"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300,
        )
    except subprocess.TimeoutExpired:
        # 卡住 = 没被守卫干净地抓住（多半是「去掉上限之后用例自己停不下来」）。
        # 按**失败**记：判据的可信度要求它是红，不是挂。
        return False, "卡住（300 秒未返回）"
    tail = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    return proc.returncode == 0, (tail[-1] if tail else "(无输出)")


def main() -> int:
    log("# 判据强度探针：「连续 N 次内容不符转终态」（工单 update-content-mismatch-retry-cap/02）")
    log(f"  仓库：{ROOT}")
    log("  判据：**每一条注入都必须转红**（有绿的 = 那条守卫是摆设）")
    log("")

    # 前置：源文件必须是**干净的**（所有锚点都在）。
    # 为什么要有这一步：探针自己被强杀（工具超时 / Ctrl-C）时 `finally` 跑不到，
    # 源文件会停在注入态——那时后面每一条都会报「锚点失效」，看起来像探针写错了，
    # 其实是上一轮没复原。这一步把那种情况变成一句明确的拒绝。
    pristine = read_text(DOWNLOAD_RESUME)
    pristine_newline = newline_of(pristine)
    missing = [name for name, old, _new in CASES
               if pristine.count(adapt(old, pristine_newline)) != 1]
    if missing:
        log("**拒绝开跑**：源文件不是干净状态（可能上一轮探针被强杀、没来得及复原）。")
        for name in missing:
            log(f"  · 锚点不在：{name}")
        log(f"  修法：`git checkout -- {DOWNLOAD_RESUME}` 之后重跑本探针。")
        RESULTS["preflight_missing"] = missing
        RESULTS["verdict"] = "FAIL"
        return 2

    baseline_sha = sha256(DOWNLOAD_RESUME)
    weak: list[str] = []
    for name, old, new in CASES:
        log("-" * 78)
        log(f"[注入] {name}")
        log(f"  文件：{DOWNLOAD_RESUME}")
        original = read_text(DOWNLOAD_RESUME)
        newline = newline_of(original)
        hits = original.count(adapt(old, newline))
        if hits != 1:
            log(f"  **锚点命中 {hits} 次（应为 1）——探针自己失效了，本条按失败记**")
            weak.append(f"{name}（锚点失效）")
            RESULTS["cases"].append({"name": name, "anchor_hits": hits,
                                     "turned_red": False, "weak": True})
            continue
        try:
            write_text(DOWNLOAD_RESUME,
                       original.replace(adapt(old, newline), adapt(new, newline), 1))
            green, summary = run_tests()
        finally:
            write_text(DOWNLOAD_RESUME, original)    # 无论结果如何都复原
        turned_red = not green
        log(f"  测试：{'、'.join(TEST_FILES)}")
        log(f"  结果：{'转红 ✓' if turned_red else '**仍然全绿 ✗**'} —— {summary}")
        RESULTS["cases"].append({"name": name, "anchor_hits": hits,
                                 "turned_red": turned_red, "summary": summary,
                                 "weak": not turned_red})
        if not turned_red:
            weak.append(name)

    log("")
    log("-" * 78)
    log("## 复原复核")
    after = sha256(DOWNLOAD_RESUME)
    log(f"  {DOWNLOAD_RESUME} sha256 "
        f"{'未变 ✓' if after == baseline_sha else f'**变了 ✗（{baseline_sha[:12]} → {after[:12]}）**'}")
    if after != baseline_sha:
        weak.append(f"{DOWNLOAD_RESUME} 未复原")

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
        (HERE / "verify-02-guard-strength.txt").write_text("\n".join(LINES) + "\n",
                                                           encoding="utf-8")
        (HERE / "verify-02-guard-strength.json").write_text(
            json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n证据已写：verify-02-guard-strength.txt / .json")
    raise SystemExit(code)
