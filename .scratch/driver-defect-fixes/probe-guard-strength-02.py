# -*- coding: utf-8 -*-
"""判据强度反证（工单 `driver-defect-fixes/02`）：把修复撤掉 → 新用例必须变红。

三条注入，逐条独立跑（注入 → 跑两条新用例 → **逐字节复原** → 复核 sha256）：

  A. **判据①（量程）**：母版 `SERVO_PWM.clockPrescale` 从 16 改回 **1**
     ⇒ 20ms = 640000 计数 > 65535，「20ms 放得进 16 位量程」必须红；
  B. **判据②（编译期守量程）**：把 `servo_mspm0.c` 的 `#if … > SERVO_TIMER_MAX_COUNT`
     改成 `> 0u`（等于把守卫关掉）⇒ 必须红；
  C. **判据②尾巴（LOAD 语义）**：把 `servo_period() - 1u` 改回 `servo_period()`
     （EDGE_ALIGN 下多一个计数）⇒ 必须红。

纪律（本仓既有）：探针**会真改库内文件**——**别和测试套件同时跑**；读写走**二进制**
（逐字节保真）；**前置干净性检查**：文件不是「已修」形态就当场退出。

用法：`py -3 .scratch/driver-defect-fixes/probe-guard-strength-02.py`
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPORT = REPO / ".scratch" / "driver-defect-fixes" / "probe-guard-strength-02.txt"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SYSCFG = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"
DRIVER = REPO / "library" / "modules" / "servo" / "code" / "servo_mspm0.c"

CASE_FITS = "tests/test_module_servo.py::test_servo_mspm0_period_fits_the_16bit_counter"
CASE_GUARD = "tests/test_module_servo.py::test_servo_mspm0_runtime_guards_the_counter_range"

INJECTIONS = [
    (
        "A：母版分频改回 1（20ms = 640000 计数，超 16 位量程）",
        "判据①（20ms 的计数 ≤ 65535）",
        SYSCFG,
        b"SERVO_PWM.clockPrescale              = 16;",
        b"SERVO_PWM.clockPrescale              = 1;",
        CASE_FITS,
    ),
    (
        "B：把编译期量程守卫关掉（阈值改成 0）",
        "判据②（#if … > SERVO_TIMER_MAX_COUNT + #error）",
        DRIVER,
        b"#if (SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ) > SERVO_TIMER_MAX_COUNT",
        b"#if (SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ) > 0u",
        CASE_GUARD,
    ),
    (
        "C：LOAD 语义退回（EDGE_ALIGN 下少减 1）",
        "判据②尾巴（LOAD = period - 1，与 stm32 的 ARR = …-1 对偶）",
        DRIVER,
        b"DL_Timer_setLoadValue(SERVO_PWM_INST, servo_period() - 1u);",
        b"DL_Timer_setLoadValue(SERVO_PWM_INST, servo_period());",
        CASE_GUARD,
    ),
    (
        "D：改用「静默钳位」掩盖量程（工单明确否掉的那种修法）",
        "判据②（源码里不许出现对周期值的比较）",
        DRIVER,
        b"DL_Timer_setLoadValue(SERVO_PWM_INST, servo_period() - 1u);",
        b"DL_Timer_setLoadValue(SERVO_PWM_INST,\r\n"
        b"        servo_period() < SERVO_TIMER_MAX_COUNT ? servo_period() - 1u : SERVO_TIMER_MAX_COUNT);",
        CASE_GUARD,
    ),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_case(node: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "--no-header", "-p", "no:cacheprovider", "-rf"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    text = proc.stdout or ""
    reds = [ln.split("::")[-1].split(" ")[0] for ln in text.splitlines() if ln.startswith("FAILED ")]
    tail = text.strip().splitlines()
    summary = tail[-1] if tail else "(无输出)"
    return proc.returncode == 0, f"{summary}（{'红了：' + '、'.join(reds) if reds else '无红'}）"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPORT))
    args = parser.parse_args()
    out_path = Path(args.out)

    originals = {path: path.read_bytes() for path in (SYSCFG, DRIVER)}
    digests = {path: sha256(data) for path, data in originals.items()}
    rows: list[str] = [
        "=== 判据强度反证：driver-defect-fixes/02（servo × mspm0 周期量程）===",
    ]
    for path, digest in digests.items():
        rows.append(f"{path.relative_to(REPO)} sha256 = {digest}")
    rows.append("")

    if b"clockPrescale              = 16;" not in originals[SYSCFG] or \
            b"> SERVO_TIMER_MAX_COUNT" not in originals[DRIVER]:
        rows.append("✗ 前置干净性检查失败：文件不是「已修」形态——上一次探针可能被强杀，"
                    "先 `git checkout -- <文件>` 复原再跑。")
        out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        print(rows[-1])
        return 2

    failures = 0
    try:
        for name, criterion, path, src, dst, node in INJECTIONS:
            original = originals[path]
            assert original.count(src) == 1, f"注入锚点在原文里出现 {original.count(src)} 次：{name}"
            path.write_bytes(original.replace(src, dst))
            try:
                ok, summary = run_case(node)
            finally:
                path.write_bytes(original)
            restored = sha256(path.read_bytes()) == digests[path]
            verdict = "红（符合预期）" if not ok else "**仍然绿——判据没抓住这一条！**"
            if ok or not restored:
                failures += 1
            rows.append(f"[注入] {name}")
            rows.append(f"       目标判据：{criterion}")
            rows.append(f"       结果：{verdict}  —— {summary}")
            rows.append(f"       复原复核：sha256 {'一致' if restored else '**不一致**'}")
            rows.append("")
    finally:
        for path, data in originals.items():
            path.write_bytes(data)

    rows.append("=== 结论：" + (
        "全部符合预期（每条注入都让对应用例变红，且文件逐字节复原）" if not failures
        else f"有 {failures} 处不符"
    ) + " ===")
    out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
