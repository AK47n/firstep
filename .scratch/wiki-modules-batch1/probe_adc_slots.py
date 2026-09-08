# -*- coding: utf-8 -*-
"""穷举探针：LQFP-64(PM) 设备数据实际暴露哪些 ADC 通道槽位（adcPinN）。

对每个候选 (N, A0_M, pin) 生成母版副本 + 一行额外 MEM 配置，跑 SysConfig CLI，
记录通过/失败。产物 .scratch/wiki-modules-batch1/syscfg-probe/probe_results.txt
"""
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[2]
MASTER = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"
OUT = REPO / ".scratch" / "wiki-modules-batch1" / "syscfg-probe" / "variants"
OUT.mkdir(parents=True, exist_ok=True)
CLI = r"C:\ti\ccs2051\sysconfig_1.26.2\sysconfig_cli.bat"
PRODUCT = r"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/.metadata/product.json"

base = MASTER.read_text(encoding="utf-8", newline="")
eol = "\r\n" if "\r\n" in base else "\n"

# 候选：槽位号 N（通道 A0_N 与 adcPinN 同名）→ (通道宏, 引脚)
candidates = {
    0: ("DL_ADC12_INPUT_CHAN_0", "PA27"),
    1: ("DL_ADC12_INPUT_CHAN_1", "PA26"),
    2: ("DL_ADC12_INPUT_CHAN_2", "PA25"),
    5: ("DL_ADC12_INPUT_CHAN_5", "PB24"),
    6: ("DL_ADC12_INPUT_CHAN_6", "PB20"),
    7: ("DL_ADC12_INPUT_CHAN_7", "PA22"),
    12: ("DL_ADC12_INPUT_CHAN_12", "PA14"),
}

lines_o = []
for n, (chan, pin) in candidates.items():
    text = base.replace(
        'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' + eol,
        'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' + eol
        + f'ADC12_0.adcMem1chansel             = "{chan}";' + eol
        + f'ADC12_0.peripheral.adcPin{n}.$assign  = "{pin}";' + eol,
        1,
    )
    variant = OUT / f"adcpin{n}.syscfg"
    variant.write_text(text, encoding="utf-8", newline="")
    r = subprocess.run(
        [CLI, "-s", PRODUCT, "--script", str(variant), "-o", str(OUT / f"out{n}"), "--compiler", "ticlang"],
        capture_output=True, text=True, timeout=240,
    )
    ok = r.returncode == 0 and "unknown property" not in r.stderr and "undefined" not in r.stderr
    lines_o.append(f"adcPin{n} ({chan}, {pin}): {'PASS' if ok else 'FAIL'}  rc={r.returncode}")
    print(lines_o[-1])

result = OUT.parent / "probe_results.txt"
result.write_text("\n".join(lines_o), encoding="utf-8")
print("written:", result)
