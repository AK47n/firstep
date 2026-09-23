# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/04 的**判据强度探针**（反证）：把两条缺陷注入回去，
看新用例是不是真的变红，再逐字节复原并复核 sha256。

反证的两条都是编译矩阵在票面形态上抓到的真缺陷（都只在"两批小节同趟"时现形）：

* **注入 A** —— 通用降级批次又去印自己那个十六进制助手（`hwcheck_generic.py`
  里加回 `hwcheck_report_hex` 的定义）→ `#247: has already been defined`；
* **注入 B** —— 十进制读数出口的判据退回"选了器件就渲"（`hwcheck.py` 的
  `needs_int=any_section` → `needs_int=any_section or bool(config.devices)`）
  → 非 I2C 自建件那一格留下没人调的 `hwcheck_report_int`（`#177-D`）；
* **注入 C** —— 产物注释不再印平台代价那句（`hwcheck_custom.py` 的
  `PLATFORM_PIN_COST` 那一支关掉）→ 票面验收项 4（产物与页面同一句措辞）变红。

⚠ 纪律（本仓库先例 `module-hwcheck/09`、`probe-03-guard-strength.py`）：
**别和测试套件同时跑**——探针会真的改库内文件（改完逐字节复原）。
⚠ 先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。

用法：`python .scratch/hwcheck-unknown-device/probe-04-guard-strength.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CUSTOM = REPO / "src" / "contest_generator" / "hwcheck_custom.py"
GENERIC = REPO / "src" / "contest_generator" / "hwcheck_generic.py"
HWCHECK = REPO / "src" / "contest_generator" / "hwcheck.py"
TEST_FILE = "tests/test_hwcheck_custom.py"

# 两条注入：文件 / 锚点（必须在原文里唯一）/ 替换文本 / 该让哪条用例变红
INJECTIONS = (
    {
        "name": "A: 通用批次又印一份十六进制助手",
        "path": GENERIC,
        "anchor": '        "/** 扫一遍这一件声明的那条总线（只 ping 地址）。 */",',
        "replacement": (
            '        "/** 把地址打成两位十六进制（注入的副本：两批各印一份）。 */",\n'
            '        "static void hwcheck_report_hex(int value)",\n'
            '        "{",\n'
            '        "    hwcheck_report(\\"0x\\");",\n'
            '        "    (void)value;",\n'
            '        "}",\n'
            '        "",\n'
            '        "/** 扫一遍这一件声明的那条总线（只 ping 地址）。 */",'
        ),
        "test": "test_main_c_never_defines_a_helper_twice",
    },
    {
        "name": "B: 十进制出口退回「选了器件就渲」",
        "path": HWCHECK,
        "anchor": "            needs_int=any_section,",
        "replacement": "            needs_int=any_section or bool(config.devices),",
        "test": "test_main_c_renders_no_readout_helper_nobody_calls",
    },
    {
        "name": "C: 产物不再印平台代价那句（验收项 4）",
        "path": CUSTOM,
        "anchor": '    if cost := PLATFORM_PIN_COST.get(platform, ""):',
        "replacement": '    if False and (cost := PLATFORM_PIN_COST.get(platform, "")):',
        "test": "test_the_platform_cost_sentence_matches_the_board_definition",
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_test(name: str) -> tuple[bool, str]:
    """跑一条用例；返回（是否通过, 摘要行）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_FILE, "-q", "-p", "no:cacheprovider",
         "-k", name],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600,
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
    before = {path: sha256(path) for path in (CUSTOM, GENERIC, HWCHECK)}
    lines.append("[1] 前置检查（源文件指纹）")
    for path, digest in before.items():
        lines.append(f"    {path.name}: {digest[:16]}…")

    base_ok, base_tail = run_test("test_main_c_never_defines_a_helper_twice")
    base_ok2, base_tail2 = run_test("test_main_c_renders_no_readout_helper_nobody_calls")
    base_ok3, base_tail3 = run_test(
        "test_the_platform_cost_sentence_matches_the_board_definition")
    lines.append(
        f"[2] 注入前（守卫在）：{'PASS' if base_ok and base_ok2 and base_ok3 else 'RED'}"
        f"  ｜ {base_tail} / {base_tail2} / {base_tail3}"
    )
    ok_all = ok_all and base_ok and base_ok2 and base_ok3

    for injection in INJECTIONS:
        path: Path = injection["path"]
        # ⚠ **逐字节保真**（本仓库的既有教训：`local-environment.md` §0 工具坑②）：
        # 文本模式读会把 CRLF 归一成 LF，写回去就与原文差行尾——"复原复核"当场
        # 假红（本探针第一版就是这么红的，注入与守卫其实都对）。所以读写都走
        # bytes，只在拼替换时解码。
        original_bytes = path.read_bytes()
        anchor = injection["anchor"].encode("utf-8")
        assert original_bytes.count(anchor) == 1, (
            f"{path.name} 里锚点不唯一（注入目标必须恰好一处）："
            f"{original_bytes.count(anchor)}"
        )
        replacement = injection["replacement"].encode("utf-8")
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

    for name in ("test_main_c_never_defines_a_helper_twice",
                 "test_main_c_renders_no_readout_helper_nobody_calls",
                 "test_the_platform_cost_sentence_matches_the_board_definition"):
        good, tail = run_test(name)
        lines.append(f"[5] 复原后复跑：{name} {'PASS（回绿）' if good else 'RED ✗'} ｜ {tail}")
        ok_all = ok_all and good

    final = {path: sha256(path) for path in (CUSTOM, GENERIC, HWCHECK)}
    same = final == before
    lines.append(
        f"[6] 收尾指纹：{'三个文件逐字节未变 ✓' if same else '有文件被改动 ✗'}"
    )
    ok_all = ok_all and same
    lines.append("")
    lines.append(
        "=== 结论：" + (f"反证成立（{len(INJECTIONS)} 条注入都让对应用例变红，"
                       "且逐字节复原）"
                       if ok_all else "反证不成立（见上面读数）") + " ==="
    )
    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")     # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 再打印
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
