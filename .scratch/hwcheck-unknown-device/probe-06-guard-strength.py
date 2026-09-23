# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/06 的**判据强度探针**（反证）：把五条回归注入回去，
看本单的新用例是不是真的变红，再逐字节复原并复核 sha256。

五条注入各打本单一条新守卫（都是"页面/板上说的与实际不是一回事"这类坏法）：

* **注入 A** —— 命令台复测自建件时改调一份**不存在的** `hwcheck_check_<id>()`
  （= 把那一段 C 抄一份、不再复用上电那一遍的小节函数）→ 票面第 2 条（输出与
  上电同一措辞）变红；
* **注入 B** —— 分配不再避开保留字与已占用的字符（自建件会抢走 `g` 这种既有
  命令 / 配方命令）→ 票面第 1 条（保留字 / 重复判据）变红；
* **注入 C** —— 分不出字符时**静默少一条**（吞掉 `HwCheckError` 的那一件）→
  票面第 1 条后半（冲突仍在构建期大声失败）变红；
* **注入 D** —— 检测页载荷不再告诉前端"这是自建件"（`tag` / `name` 不给）→
  票面第 3 条（页面命令区显示自建件的字符与说明）变红；
* **注入 E** —— 板侧视图不再把自建件喂给命令表（页面一张表、产物另一张表）→
  "页面与板上同源"那条端到端判据变红；
* **注入 F** —— 顺手改掉「这一趟没有配方命令」那两句（统一措辞的诱惑）→
  票面第 5 条（一件自建件都没有时命令台产物逐字与改动前一致）变红——这条是
  **Spec 轴评审当场抓到的破绽**的量具。

⚠ 纪律（本仓库先例 `module-hwcheck/09`、`probe-03/04/05-guard-strength.py`）：
**别和测试套件同时跑**——探针会真的改库内文件（改完逐字节复原）。
⚠ 先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。
⚠ 源码读写一律走 **bytes**（文本模式会把 CRLF 归一成 LF，"复原复核"当场假红）。

用法：`python .scratch/hwcheck-unknown-device/probe-06-guard-strength.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYS = REPO / "src" / "contest_generator"
CONSOLE = SYS / "hwcheck_console.py"
BOARD = SYS / "hwcheck_board.py"
HWCHECK = SYS / "hwcheck.py"
CONSOLE_TESTS = "tests/test_hwcheck_console.py"
ENDPOINT_TESTS = "tests/test_my_devices_endpoint.py"

# 五条注入：文件 / 锚点（必须在原文里唯一）/ 替换文本 / 该让哪条用例变红
INJECTIONS = (
    {
        "name": "A: 复测改调一份不存在的小节函数（不再复用上电那一遍）",
        "path": CONSOLE,
        "anchor": '        out.append(f"        {entry.call_target}();")',
        "replacement": '        out.append(f"        hwcheck_check_{entry.slug}();")',
        "test": "test_the_custom_retest_runs_the_same_section_as_the_power_on_pass",
        "test_file": CONSOLE_TESTS,
    },
    {
        "name": "B: 分配不再避开保留字与已占用的字符",
        "path": CONSOLE,
        "anchor": (
            "        if key in RESERVED_COMMANDS or key in seen:\n"
            "            continue\n"
        ),
        "replacement": "        if False:\n            continue\n",
        "test": "test_a_custom_character_never_takes_a_reserved_or_declared_one",
        "test_file": CONSOLE_TESTS,
    },
    {
        "name": "C: 分不出字符时静默少一条（吞掉大声失败）",
        "path": CONSOLE,
        "anchor": (
            "    for section in custom:\n"
            "        command = _assign_custom_command(section.slug, seen)\n"
        ),
        "replacement": (
            "    for section in custom:\n"
            "        try:\n"
            "            command = _assign_custom_command(section.slug, seen)\n"
            "        except HwCheckError:\n"
            "            continue\n"
        ),
        "test": "test_running_out_of_command_characters_fails_loudly_at_build_time",
        "test_file": CONSOLE_TESTS,
    },
    {
        "name": "D: 载荷不再告诉前端这是自建件",
        "path": CONSOLE,
        "anchor": (
            '                **({"tag": CUSTOM_TAG, "name": entry.name}'
            " if entry.custom else {}),\n"
        ),
        "replacement": "                **({}),\n",
        "test": "test_console_payload_marks_custom_rows_without_touching_library_rows",
        "test_file": CONSOLE_TESTS,
    },
    {
        "name": "E: 板侧视图不再把自建件喂给命令表（页面一张表、产物另一张）",
        "path": BOARD,
        "anchor": "    console = build_console_table(sections, custom_sections)",
        "replacement": "    console = build_console_table(sections)",
        "test": "test_the_page_console_table_carries_the_custom_retest_command",
        "test_file": ENDPOINT_TESTS,
    },
    {
        "name": "F: 顺手改掉「这一趟没有配方命令」那两句（破票面第 5 条的逐字一致）",
        "path": HWCHECK,
        "anchor": '            lines.append(" *   - 这一趟没有配方命令（选的器件都没声明复测字符）：")\n',
        "replacement": (
            '            lines.append(" *   - 这一趟没有复测命令'
            '（配方没声明字符，也没有要复测的自建件）：")\n'
        ),
        "test": "test_a_run_without_custom_devices_keeps_the_old_console_text",
        "test_file": CONSOLE_TESTS,
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def match_anchor(path: Path, text: str) -> tuple[bytes, str] | tuple[None, None]:
    """锚点文本 → **文件里真实的那段字节**，连同它的行尾形态。

    ⚠ 行尾必须按文件实况取（本仓库两种形态并存：`git` 检出的文本是 CRLF
    ——`core.autocrlf=true`，而工具新写的文件是 LF）。锚点里一律写 `\\n`，
    这里先试 LF 再试 CRLF，恰好命中一处才算数；替换文本跟着用同一种行尾，
    免得把注入进去的那几行写成另一种换行。
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
    files = (CONSOLE, BOARD, HWCHECK)
    before = {path: sha256(path) for path in files}

    # 前置：源文件此刻是干净的（上一轮被强杀会留在注入态——先自检，别把"已经在
    # 注入态"读成"守卫没抓住"）
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
