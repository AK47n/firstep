# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/11 的**判据强度探针**（反证）：把缺陷注入回去，
看新用例是不是真的变红，再逐字节复原并复核 sha256。

四条注入，各自对应一条判据：

* **A 判据整个关掉**（`_duplicate_pin_names` 恒返回空）→ 三重名用例全红；
* **B 判在母版全文上**（拿 `origin` 而不是裁剪后的 `model`）→ 「只选 oled 不该报」
  那条变红（母版里 14 组存量重名会被全报出来）；
* **C 同名也算进 `lines`**（两根轴并成一根）→ 「说重名、别说脚被占」那条变红
  （文案会退回"引脚被占用"，指错出路）；
* **D 检测页那支分支关掉**（`hwcheck_pin_message` 不认纯重名形态）→ 检测页用例变红。

⚠ 纪律：**别和测试套件同时跑**——探针会真的改库内文件（改完逐字节复原）。
⚠ 先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。

用法：`python .scratch/hwcheck-unknown-device/probe-11-guard-strength.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRUNE = REPO / "src" / "contest_generator" / "syscfg_prune.py"
BOARD = REPO / "src" / "contest_generator" / "hwcheck_board.py"

# 注入声明：文件 / 锚点（原文里必须唯一）/ 替换 / 该让哪条用例变红
INJECTIONS = (
    {
        "name": "A: 重名判据整个关掉",
        "path": PRUNE,
        "anchor": "    name_conflicts = _duplicate_pin_names(model)",
        "replacement": "    name_conflicts = {}  # 注入：判据关掉",
        "test": "tests/test_generator.py::test_syscfg_pin_name_collision_is_a_loud_failure",
    },
    {
        "name": "B: 判在母版全文上（没裁剪）",
        "path": PRUNE,
        "anchor": "    name_conflicts = _duplicate_pin_names(model)",
        "replacement": "    name_conflicts = _duplicate_pin_names(origin)  # 注入：未裁剪",
        "test": "tests/test_generator.py::test_syscfg_pin_name_collision_is_solved_by_dropping_one_module",
    },
    {
        "name": "C: 两根轴并成一根（重名塞进 lines）",
        "path": PRUNE,
        "anchor": "    name_lines = [\n        \"  · \" + name + \"：\" + \" × \".join(where)\n        for name, where in sorted(name_conflicts.items())\n    ]",
        "replacement": (
            "    name_lines = []  # 注入：并进 lines（文案会说成脚被占）\n"
            "    lines.extend(\n"
            "        \"  · \" + name + \"：\" + \" × \".join(where)\n"
            "        for name, where in sorted(name_conflicts.items())\n"
            "    )"
        ),
        "test": "tests/test_generator.py::test_syscfg_pin_name_collision_is_a_loud_failure",
    },
    {
        "name": "D: 检测页那支分支关掉",
        "path": BOARD,
        "anchor": "    if not report.lines:\n        return (\n            f\"这套选择在「{board_name}」上装不下：落盘后的 mspm0.syscfg 里 \"",
        "replacement": "    if False:\n        return (\n            f\"这套选择在「{board_name}」上装不下：落盘后的 mspm0.syscfg 里 \"",
        "test": "tests/test_hwcheck_board.py::test_hwcheck_view_surfaces_the_pin_name_collision",
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _anchor_bytes(text: str, data: bytes) -> bytes:
    """锚点 → 字节（**按文件的换行形态**，本机检出是 CRLF）。

    探针里的锚点按读起来舒服的 LF 写，但库内源文件在本机是 CRLF 检出——
    直接 `text.encode()` 去找会一条都匹配不上（本轮第一版就栽在这儿：锚点计数 0，
    断言当场拦下，没造成污染）。
    """
    lf = text.encode("utf-8")
    if data.count(lf):
        return lf
    return text.replace("\n", "\r\n").encode("utf-8")


def run_test(target: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q", "-p", "no:cacheprovider"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600,
    )
    tail = [
        line.strip() for line in (proc.stdout or "").splitlines()
        if "passed" in line or "failed" in line or "error" in line
    ]
    return proc.returncode == 0, (tail[-1] if tail else f"exit={proc.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8，先落盘再打印）")
    args = parser.parse_args()

    lines: list[str] = []
    ok_all = True
    files = (PRUNE, BOARD)
    before = {path: sha256(path) for path in files}
    lines.append("[1] 前置检查（源文件指纹）")
    for path, digest in before.items():
        lines.append(f"    {path.name}: {digest[:16]}…")

    targets = sorted({injection["test"] for injection in INJECTIONS})
    base_ok = True
    for target in targets:
        good, tail = run_test(target)
        lines.append(f"[2] 注入前（守卫在）：{target.split('::')[-1]} "
                     f"{'PASS' if good else 'RED'} ｜ {tail}")
        base_ok = base_ok and good
    ok_all = ok_all and base_ok

    for injection in INJECTIONS:
        path: Path = injection["path"]
        original_bytes = path.read_bytes()          # **逐字节保真**（CRLF 陷阱）
        anchor = _anchor_bytes(injection["anchor"], original_bytes)
        replacement = _anchor_bytes(injection["replacement"], original_bytes)
        assert original_bytes.count(anchor) == 1, (
            f"{path.name} 里锚点不唯一：{original_bytes.count(anchor)}"
        )
        try:
            path.write_bytes(original_bytes.replace(anchor, replacement))
            good, tail = run_test(injection["test"])
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

    for target in targets:
        good, tail = run_test(target)
        lines.append(
            f"[5] 复原后复跑：{target.split('::')[-1]} "
            f"{'PASS（回绿）' if good else 'RED ✗'} ｜ {tail}"
        )
        ok_all = ok_all and good

    same = {path: sha256(path) for path in files} == before
    lines.append(f"[6] 收尾指纹：{'源文件逐字节未变 ✓' if same else '有文件被改动 ✗'}")
    ok_all = ok_all and same
    lines.append("")
    lines.append(
        "=== 结论：" + (f"反证成立（{len(INJECTIONS)} 条注入都让对应用例变红，"
                       "且逐字节复原）" if ok_all else "反证不成立（见上面读数）") + " ==="
    )
    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")     # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
