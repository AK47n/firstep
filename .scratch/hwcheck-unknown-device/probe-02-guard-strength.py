# -*- coding: utf-8 -*-
"""「我的器件」id 撞库内 slug 守卫的**判据强度探针**（工单 hwcheck-unknown-device/02）。

工单验收项：「反证：把『id 撞库内 slug』的守卫拿掉后，对应用例必须变红」。

做法（照 `.scratch/hwcheck-unknown-device/probe-01-c1-reverse.py` 先例）：

1. **前置干净性检查**：源文件必须与注入目标逐字匹配（否则说明上一轮没复原干净
   ——强杀留下的注入态会让整支探针读数不可信）；
2. 注入：把 `CustomDevice.validated` 里那段撞名判据换成 `pass`（只动这一处）；
3. 跑对应用例（`tests/test_my_devices.py` / `tests/test_my_devices_endpoint.py`
   的撞名三条），断言**必须变红**；
4. 逐字节复原 + sha256 复核 + 再跑一次（必须回绿）。

**别和测试套件同时跑**（仓库既有纪律：探针会真改库内文件）。

用法：`python .scratch/hwcheck-unknown-device/probe-02-guard-strength.py [--out FILE]`
先落盘再打印（本机控制台 GBK，`print` 抛 UnicodeEncodeError 会让证据整份丢）。
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "src" / "contest_generator" / "my_devices.py"

# 注入目标 = 撞名判据那一段（含它上面那行注释，保证锚点唯一）
NEEDLE = '''        if device_id in set(library_slugs):
            raise MyDeviceError(
                f"器件 id {device_id!r} 与库内模块同名（库内 slug 也叫这个）——"
                "请改名：换成你自己的名字（如 mine_" + device_id[len(DEVICE_ID_PREFIX):]
                + "_v2）再存，id 是这件东西在你工具里的唯一名字"
            )
'''
PLANTED = """        # [探针注入] 撞名守卫已被拿掉（反证用，跑完逐字节复原）
        pass
"""

# 三条撞名用例（前两条域层、第三条端点）
TESTS = [
    "tests/test_my_devices.py::test_id_clashing_with_a_library_slug_is_named_out_loud",
    "tests/test_my_devices.py::test_id_that_does_not_clash_is_accepted",
    "tests/test_my_devices_endpoint.py::test_id_clashing_with_a_library_slug_is_400_and_names_the_id",
    "tests/test_my_devices_endpoint.py::test_the_clash_judgement_reads_the_library_at_request_time",
]


def run_tests() -> tuple[bool, str]:
    """跑那几条用例：返回（是否全绿, 尾部读数）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TESTS],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    tail = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, tail.strip().splitlines()[-1] if tail.strip() else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8；先落盘再打印）")
    args = parser.parse_args()

    original = TARGET.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines: list[str] = []
    ok = True

    # ① 前置干净性检查
    if text.count(NEEDLE) != 1:
        lines.append(
            f"[1] 前置检查失败：注入目标出现 {text.count(NEEDLE)} 次（应为 1）"
            "——源文件不是预期形态，读数不可信"
        )
        ok = False
    else:
        lines.append(f"[1] 前置检查：源文件 sha256={digest[:32]}…，注入目标唯一 ✓")

    if ok:
        # ② 注入前基线（必须全绿）
        green, tail = run_tests()
        lines.append(f"[2] 注入前：{'PASS（全绿）' if green else 'FAIL'} ｜ {tail}")
        ok = ok and green

    if ok:
        # ③ 注入 + 复跑（撞名三条必须变红）
        TARGET.write_bytes(text.replace(NEEDLE, PLANTED).encode("utf-8"))
        try:
            green, tail = run_tests()
            lines.append(f"[3] 注入后：{'仍全绿（反证不成立！）' if green else 'RED（撞名用例变红）'} ｜ {tail}")
            ok = ok and not green
        finally:
            # ④ 逐字节复原（无论上面发生什么）
            TARGET.write_bytes(original)

    # ⑤ 复原复核（sha256 相等才算复原）
    restored = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    lines.append(
        f"[4] 复原复核：sha256 {'相等 ✓' if restored == digest else '不等 ✗'}（{restored[:32]}…）"
    )
    ok = ok and restored == digest

    if restored == digest:
        green, tail = run_tests()
        lines.append(f"[5] 复原后复跑：{'PASS（回绿）' if green else 'FAIL'} ｜ {tail}")
        ok = ok and green

    lines.append(f"结论：{'反证成立（守卫是撞名用例变红的唯一判据）' if ok else '反证不成立 / 读数不完整'}")
    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")   # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 再打印
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
