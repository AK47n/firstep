# -*- coding: utf-8 -*-
"""工单 02 的反证探针：判据**真的会因为"母版又撞名"而红**吗？

三条注入（照工单 11 的 `probe-11-guard-strength.py` 先例：真改库内文件 → 跑点名
的用例 → 逐字节复原 → sha256 复核）：

* **注入 A｜把改名撤回一组**（OLED_SPI + JY61P 的 SCL/SDA 还原成裸名）
  → 期望 `test_master_pin_symbols_are_globally_unique` **RED**
  （母版又出现重名），且 `test_mspm0_oled_plus_i2c_sensor_passes_the_gate` **RED**
  （"OLED + 一件 I2C 器件"这一格又关上了）。
* **注入 B｜再塞一个撞名实例**（往母版追加一个 GPIO 实例，引脚符号用既有的
  `SR04_TRIG`）→ 期望守卫 **RED**——这正是票面那句"母版新增一个与既有实例同名的
  引脚符号 → 当场红"（新实例不需要被任何模块选中就会被抓到）。
* **注入 C｜只撤回一边**（只把 OLED_SPI 的 SCL/SDA 还原）→ 期望守卫**仍 GREEN**：
  对面已经叫 `JY61P_SCL`，不撞就是不撞——判据是"母版里有没有同名"，不是"字符串像
  不像"。（这条是**阴性对照**：没有它，A/B 的红分不清是判据抓住了事实，还是判据
  见到熟面孔就红。）

复原纪律（工单 11 的既有约定）：只改**一个**文件（母版 syscfg），跑完逐字节写回并
比对 sha256；任何一步失败都会在 finally 里复原。**别和测试套件同时跑。**

用法：`python .scratch/hwcheck-acceptance/probe-02-reverse.py [--out FILE]`
先落盘再打印（本机控制台 GBK）。
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MASTER = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"

GUARD = "tests/test_syscfg_prune.py::test_master_pin_symbols_are_globally_unique"
COMBOS = "tests/test_generator.py::test_mspm0_oled_plus_i2c_sensor_passes_the_gate"

REVERT_BOTH = (
    ('OLED_SPI.associatedPins[0].$name        = "OLED_SPI_SCL";',
     'OLED_SPI.associatedPins[0].$name        = "SCL";'),
    ('OLED_SPI.associatedPins[1].$name        = "OLED_SPI_SDA";',
     'OLED_SPI.associatedPins[1].$name        = "SDA";'),
    ('JY61P.associatedPins[0].$name        = "JY61P_SCL";',
     'JY61P.associatedPins[0].$name        = "SCL";'),
    ('JY61P.associatedPins[1].$name        = "JY61P_SDA";',
     'JY61P.associatedPins[1].$name        = "SDA";'),
)
REVERT_ONE_SIDE = REVERT_BOTH[:2]

# 追加的撞名实例：引脚符号借既有的 `TRIG`（SR04 用的就是它——02 改名只动了**撞过名**
# 的符号，SR04 的 `TRIG` 本来就没撞、保持原名，所以这才是真撞）。
# 不写 `pin.$assign`：本注入要验的是**名字**那一轴，给了脚反而会顺带撞上同脚轴
# （第一版写了 PA2，恰好是 KEY.START 的脚——探针自己先红在别的轴上）。
EXTRA_INSTANCE = (
    "\n// 反证注入（工单 02 探针）：新实例的引脚符号与既有实例同名\n"
    "const PROBE_DUP = GPIO.addInstance();\n"
    'PROBE_DUP.$name = "PROBE_DUP";\n'
    "PROBE_DUP.associatedPins.create(1);\n"
    'PROBE_DUP.associatedPins[0].$name        = "TRIG";\n'
    'PROBE_DUP.associatedPins[0].direction    = "OUTPUT";\n'
    'PROBE_DUP.associatedPins[0].initialValue = "CLEARED";\n'
)


def run_tests(node: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", node],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=900,
    )
    tail = [line for line in (proc.stdout or "").splitlines() if line.strip()][-1:]
    return proc.returncode, (tail[0] if tail else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    original = MASTER.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines: list[str] = []
    ok_all = True

    lines.append("=== 工单 02 反证探针（母版 syscfg：逐字节复原 + sha256 复核）===")
    lines.append(f"母版：{MASTER.relative_to(REPO).as_posix()}")
    lines.append(f"注入前 sha256：{before}")
    lines.append("")

    injections = [
        ("A｜撤回一组改名（OLED_SPI + JY61P）", "revert_both"),
        ("B｜再塞一个撞名实例（借既有的 TRIG）", "extra"),
        ("C｜只撤回一边（阴性对照）", "revert_one"),
    ]
    base_codes: dict[str, int] = {}
    try:
        for label, mode in injections:
            if mode == "revert_both":
                patched = text
                for old, new in REVERT_BOTH:
                    assert old in patched, old
                    patched = patched.replace(old, new)
            elif mode == "revert_one":
                patched = text
                for old, new in REVERT_ONE_SIDE:
                    assert old in patched, old
                    patched = patched.replace(old, new)
            else:
                patched = text + EXTRA_INSTANCE
            MASTER.write_text(patched, encoding="utf-8")

            guard_code, guard_tail = run_tests(GUARD)
            # 注入 B 只验守卫那一轴（"新加实例撞名当场红"）——组合用例与它无关，
            # 跑它只会引入噪声（第一版跑过：红在别的轴上）。
            combo_code = combo_tail = None
            if mode != "extra":
                combo_code, combo_tail = run_tests(COMBOS)
            lines.append(f"── 注入 {label}")
            lines.append(
                f"     守卫用例：{'RED' if guard_code else 'GREEN'}（{guard_tail}）"
            )
            if combo_code is not None:
                lines.append(
                    f"     组合用例：{'RED' if combo_code else 'GREEN'}（{combo_tail}）"
                )
            if mode in ("revert_both", "extra"):
                expected_guard_red = guard_code != 0
                lines.append(
                    "     期望：守卫 RED"
                    + ("✓" if expected_guard_red else "✗（判据没抓住！）")
                )
                ok_all = ok_all and expected_guard_red
            else:
                lines.append(
                    "     期望：守卫 GREEN"
                    + ("✓" if guard_code == 0 else "✗（假红：不撞也报）")
                )
                ok_all = ok_all and guard_code == 0
            if mode == "revert_both":
                lines.append(
                    "     期望：组合用例 RED"
                    + ("✓" if combo_code else "✗（那一格没关上）")
                )
                ok_all = ok_all and combo_code is not None and combo_code != 0
            if mode == "revert_one":
                lines.append(
                    "     期望：组合用例 GREEN"
                    + ("✓" if combo_code == 0 else "✗（只撤一边不该撞）")
                )
                ok_all = ok_all and combo_code == 0
            lines.append("")
    finally:
        MASTER.write_bytes(original)

    after = hashlib.sha256(MASTER.read_bytes()).hexdigest()
    restored = after == before
    lines.append(f"复原 sha256：{after}（{'相等 ✓' if restored else '不等 ✗'}）")
    ok_all = ok_all and restored

    # 复原后回绿：同两条用例必须重新通过
    guard_code, guard_tail = run_tests(GUARD)
    combo_code, combo_tail = run_tests(COMBOS)
    lines.append(
        f"复原后回绿：守卫 {'PASS' if guard_code == 0 else 'FAIL'}（{guard_tail}）｜"
        f"组合 {'PASS' if combo_code == 0 else 'FAIL'}（{combo_tail}）"
    )
    ok_all = ok_all and guard_code == 0 and combo_code == 0
    lines.append("")
    lines.append("=== 结论：" + ("反证成立" if ok_all else "有 FAIL（见上）") + " ===")

    report = "\n".join(lines) + "\n"
    path = Path(args.out) if args.out else Path(__file__).with_suffix(".txt")
    path.write_text(report, encoding="utf-8")     # 先落盘
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
