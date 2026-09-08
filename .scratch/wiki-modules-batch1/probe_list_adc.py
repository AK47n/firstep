# -*- coding: utf-8 -*-
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "syscfg-probe"
script = OUT / "list_adc.syscfg"
script.write_text(
    "//@cliArgs --device \"MSPM0G350X\" --package \"LQFP-64(PM)\" --part \"Default\"\n"
    "//@v2CliArgs --device \"MSPM0G3507\" --package \"LQFP-64(PM)\"\n"
    "// 探针：列出运行时设备数据的 ADC 资源\n"
    "console.log('ADC资源: ' + JSON.stringify(Object.keys(system.deviceData.peripheralPins).filter(e => e.includes('ADC')).sort()))\n",
    encoding="utf-8",
)
r = subprocess.run(
    [r"C:\ti\ccs2051\sysconfig_1.26.2\sysconfig_cli.bat", "-s",
     r"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/.metadata/product.json",
     "--script", str(script), "-o", str(OUT / "listadc_out"), "--compiler", "ticlang"],
    capture_output=True, text=True, timeout=240,
)
print("rc:", r.returncode)
print(r.stdout[-3000:])
print("ERR:", r.stderr[-3000:])
