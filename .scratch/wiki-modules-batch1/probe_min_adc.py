# -*- coding: utf-8 -*-
"""最小探针：只有 ADC12 实例 + 单条 adcPin1/adcPin2 赋值，隔离母版干扰。"""
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "syscfg-probe"
CLI = r"C:\ti\ccs2051\sysconfig_1.26.2\sysconfig_cli.bat"
PRODUCT = r"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/.metadata/product.json"

base = """//@cliArgs --device "MSPM0G350X" --package "LQFP-64(PM)" --part "Default"
const ADC12 = scripting.addModule("/ti/driverlib/ADC12", {}, false);
const ADC12_0 = ADC12.addInstance();
ADC12_0.$name = "ADC12_0";
ADC12_0.sampClkSrc = "DL_ADC12_CLOCK_ULPCLK";
ADC12_0.sampClkDiv = "DL_ADC12_CLOCK_DIVIDE_8";
ADC12_0.sampleTime0 = "125 us";
ADC12_0.powerDownMode = "DL_ADC12_POWER_DOWN_MODE_MANUAL";
ADC12_0.adcMem0chansel = "DL_ADC12_INPUT_CHAN_3";
ADC12_0.peripheral.$assign = "ADC0";
ADC12_0.peripheral.adcPin3.$assign = "PA24";
ADC12_0.samplingOperationMode = "sequence";
ADC12_0.startAdd = 0;
"""

variants = {
    "seq-mem0-1": (
        'ADC12_0.endAdd = 1;\n'
        'ADC12_0.adcMem1chansel = "DL_ADC12_INPUT_CHAN_1";\n'
        'ADC12_0.peripheral.adcPin1.$assign = "PA26";\n'
    ),
    "seq-mem0-1-2": (
        'ADC12_0.endAdd = 2;\n'
        'ADC12_0.adcMem1chansel = "DL_ADC12_INPUT_CHAN_1";\n'
        'ADC12_0.adcMem2chansel = "DL_ADC12_INPUT_CHAN_2";\n'
        'ADC12_0.peripheral.adcPin1.$assign = "PA26";\n'
        'ADC12_0.peripheral.adcPin2.$assign = "PA25";\n'
    ),
}

for name, extra in variants.items():
    s = OUT / f"{name}.syscfg"
    s.write_text(base + extra, encoding="utf-8")
    r = subprocess.run(
        [CLI, "-s", PRODUCT, "--script", str(s), "-o", str(OUT / f"{name}_out"), "--compiler", "ticlang"],
        capture_output=True, text=True, timeout=240,
    )
    errs = [l for l in r.stderr.splitlines() if "Error" in l or "error" in l or "undefined" in l or "Cannot" in l]
    print(f"{name}: rc={r.returncode} {errs[:2] if errs else ''}")
