# -*- coding: utf-8 -*-
"""量具（工单 `driver-defect-fixes/02`）：**实测** SysConfig 折出来的计数时钟与周期。

为什么不能只靠推断：修法取的是「用母版侧配好的分频」，也就是说
`(a)` SysConfig 会按 `clockPrescale = 16` 把 `SERVO_PWM_INST_CLK_FREQ` 折成 2MHz、
`(b)` 并把 `timerCount = 40000` 写进 `.period`——这两件事都得从**生成产物**上读回来，
不然驱动里那句 `SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ` 就是在猜。

做法：走产品端点（`/api/hwcheck/generate`，servo 单选、两通道默认开）生成一份 mspm0
检测工程 → 真编译（gmake 会先跑 sysconfig_cli 生成 `Debug/ti_msp_dl_config.*`）→
从**生成的文件**里读四个数（计数时钟 / prescale / period / C0 比较值）。

用法：`py -3 .scratch/driver-defect-fixes/probe-02-inst-clk-freq.py`
"""
import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.compile_runner import collect_build_log, find_make  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"
REPORT = REPO / ".scratch" / "driver-defect-fixes" / "probe-02-inst-clk-freq.txt"

# 判据面（独立于实现）：母版 SYSCTL.forceDefaultClkConfig ⇒ BUSCLK = 32MHz；
# 母版 clockPrescale = 16 ⇒ 计数时钟 2MHz；20ms ⇒ 40000 计数。
EXPECT_BUSCLK = 32_000_000
EXPECT_PRESCALE = 16
EXPECT_COUNT_CLOCK = EXPECT_BUSCLK // EXPECT_PRESCALE
EXPECT_PERIOD_COUNTS = EXPECT_COUNT_CLOCK // 50


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPORT))
    args = parser.parse_args()
    out_path = Path(args.out)

    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app

    make = find_make(GMAKE)
    work = Path(tempfile.mkdtemp(prefix="firstep-servo-clk-"))
    ctx = AppContext(
        config_path=work / "cfg" / "config.json",
        config=AppConfig(api_key="sk-test", module_library_dir=MODULES, masters_dir=MASTERS),
        desktop_dir=lambda: work,
    )
    client = TestClient(create_app(ctx))
    rows: list[str] = ["=== servo × mspm0：SysConfig 折出来的计数时钟（driver-defect-fixes/02）==="]
    failures = 0
    try:
        payload = {"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": True,
                   "devices": ["servo"], "parent_dir": str(work)}
        response = client.post("/api/hwcheck/generate", json=payload)
        rows.append(f"生成 HTTP {response.status_code}")
        if response.status_code != 200:
            rows.append("✗ 生成失败：" + str(response.text)[:300])
            failures += 1
        else:
            project = Path(response.json()["output_dir"])
            log = collect_build_log(PLATFORM_MSPM0, project, make=make, timeout=900)
            rows.append(f"gmake exit={log.run.exit_code}（这一步会先跑 sysconfig_cli）")
            header = (project / "Debug" / "ti_msp_dl_config.h").read_text(
                encoding="utf-8", errors="replace")
            source = (project / "Debug" / "ti_msp_dl_config.c").read_text(
                encoding="utf-8", errors="replace")
            count_clock = int(re.search(r"#define\s+SERVO_PWM_INST_CLK_FREQ\s+(\d+)",
                                        header).group(1))
            prescale = int(re.search(r"\.prescale = (\d+)U", source).group(1))
            period = int(re.search(r"\.period = (\d+),", source).group(1))
            cc_match = re.search(r"\.ccValue\s*=\s*(\d+)", source)
            cc0 = int(cc_match.group(1)) if cc_match else None
            rows += [
                f"SERVO_PWM_INST_CLK_FREQ = {count_clock}（期望 {EXPECT_COUNT_CLOCK}）",
                f".prescale = {prescale}（期望 {EXPECT_PRESCALE - 1}，即 clockPrescale = {EXPECT_PRESCALE}）",
                f".period   = {period}（期望 {EXPECT_PERIOD_COUNTS} = 20ms）",
                f".ccValue  = {cc0 if cc0 is not None else '（生成的私有头部里，非本量具判据）'}"
                f"（初值占空比，运行时由 servo_init 覆盖）",
            ]
            for label, got, want in (
                ("计数时钟", count_clock, EXPECT_COUNT_CLOCK),
                ("预分频寄存器", prescale, EXPECT_PRESCALE - 1),
                ("周期计数", period, EXPECT_PERIOD_COUNTS),
            ):
                if got != want:
                    failures += 1
                    rows.append(f"✗ {label} 与期望不符：{got} ≠ {want}")
            if period > 65535:
                failures += 1
                rows.append(f"✗ 周期计数 {period} 超过 16 位量程")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    rows.append("=== 结论：" + (
        "SysConfig 折出的计数时钟与周期与驱动假设一致，且周期在 16 位量程内"
        if not failures else f"有 {failures} 处不符"
    ) + " ===")
    out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
