# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/05 的**判据强度探针**（反证）：把四条回归注入回去，
看新用例是不是真的变红，再逐字节复原并复核 sha256。

四条注入各打本单一条新守卫（都是"页面说得好好的、实际不是那么回事"这类坏法）：

* **注入 A** —— 建议顺序不再把自建件排在最后（拼装处把两段顺序对调）→ 票面第 3
  条（库内 bring-up 件在前、自建件排最后）变红；
* **注入 B** —— 计划只列"出了小节的那几件"（非 I2C / 没勾通道的件直接从计划里
  消失）→ 票面第 5 条（页面要如实说为什么不给它出探测程序）变红；
* **注入 C** —— 上板清单不再接自建件那几条（`custom_checklist` 吃空集）→ 票面
  第 2 条（三类各一条）变红；
* **注入 D** —— "出不出探测小节"的判据不再看总线（非 I2C 件也当 I2C 件渲）→
  票面第 5 条后半（非 I2C 不进 C 产物）变红。

⚠ 纪律（本仓库先例 `module-hwcheck/09`、`probe-03/04-guard-strength.py`）：
**别和测试套件同时跑**——探针会真的改库内文件（改完逐字节复原）。
⚠ 先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。
⚠ 源码读写一律走 **bytes**（文本模式会把 CRLF 归一成 LF，"复原复核"当场假红）。

用法：`python .scratch/hwcheck-unknown-device/probe-05-guard-strength.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYS = REPO / "src" / "contest_generator"
CUSTOM = SYS / "hwcheck_custom.py"
BOARD = SYS / "hwcheck_board.py"
HWCHECK = SYS / "hwcheck.py"
WEBAPP = SYS / "webapp.py"
TEST_FILE = "tests/test_hwcheck_custom.py"

# 四条注入：文件 / 锚点（必须在原文里唯一）/ 替换文本 / 该让哪条用例变红
INJECTIONS = (
    {
        "name": "A: 顺序不再把自建件排在最后",
        "path": BOARD,
        "anchor": '    board_payload["order"] = [*board_payload["order"], *plan_order_rows(custom_plan)]',
        "replacement": '    board_payload["order"] = [*plan_order_rows(custom_plan), *board_payload["order"]]',
        "test": "test_the_order_puts_the_custom_device_after_every_library_module",
    },
    {
        "name": "B: 计划只列出了小节的那几件",
        "path": CUSTOM,
        "anchor": "        probing = _probes(device, has_output_channel=has_output_channel)\n",
        "replacement": (
            "        probing = _probes(device, has_output_channel=has_output_channel)\n"
            "        if not probing:\n"
            "            continue\n"
        ),
        "test": "test_the_page_payload_carries_the_plan_for_every_selected_custom_device",
    },
    {
        "name": "C: 上板清单不再接自建件那几条",
        "path": HWCHECK,
        "anchor": "        for raw in custom_checklist(custom)",
        "replacement": "        for raw in custom_checklist(())",
        "test": "test_the_checklist_grows_by_the_custom_device_classes_in_the_right_place",
    },
    {
        "name": "D: 出不出探测小节不再看总线",
        "path": CUSTOM,
        "anchor": "    return has_output_channel and device.bus == BUS_I2C",
        "replacement": "    return has_output_channel",
        "test": "test_a_non_i2c_custom_device_never_reaches_the_product",
    },
    {
        "name": "E: 回读端点自己拼一份清单（漏喂自建件计划）",
        "path": WEBAPP,
        "anchor": '        payload["checklist"] = _hwcheck_checklist_payload(config, view)',
        "replacement": (
            '        payload["checklist"] = [\n'
            '            item.to_dict() for item in render_checklist(config)\n'
            '        ]'
        ),
        "test": "test_the_checklist_projection_has_a_single_home",
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
    parser.add_argument(
        "--out",
        default=str(Path(__file__).with_suffix(".txt")),
        help="证据文件（UTF-8，先落盘再打印；缺省 = 与本探针同名的 .txt）",
    )
    args = parser.parse_args()

    lines: list[str] = []
    ok_all = True
    files = (CUSTOM, BOARD, HWCHECK, WEBAPP)
    before = {path: sha256(path) for path in files}

    # 前置：源文件此刻是干净的（上一轮被强杀会留在注入态——先自检，别把"已经在
    # 注入态"读成"守卫没抓住"）
    lines.append("[1] 前置检查（源文件指纹与锚点唯一性）")
    for injection in INJECTIONS:
        path: Path = injection["path"]
        count = path.read_bytes().count(injection["anchor"].encode("utf-8"))
        assert count == 1, (
            f"{path.name} 里锚点不唯一（注入目标必须恰好一处）：{count}"
        )
    for path in files:
        lines.append(f"    {path.name}: {sha256(path)[:16]}…（锚点各一处 ✓）")

    names = [injection["test"] for injection in INJECTIONS]
    base = [run_test(name) for name in names]
    lines.append(
        f"[2] 注入前（守卫在）：{'PASS（四条全绿）' if all(g for g, _ in base) else 'RED ✗'}"
        f"  ｜ {' / '.join(tail for _g, tail in base)}"
    )
    ok_all = ok_all and all(good for good, _ in base)

    for injection in INJECTIONS:
        path: Path = injection["path"]
        original_bytes = path.read_bytes()
        anchor = injection["anchor"].encode("utf-8")
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

    for name in names:
        good, tail = run_test(name)
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
