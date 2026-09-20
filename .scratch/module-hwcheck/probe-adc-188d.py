# -*- coding: utf-8 -*-
"""探针：#188-D 到底是**哪一处**报的——实参（枚举）还是**返回值**（uint16_t → int）？

已知：
* 兄弟件 `flame_stm32.c` 里 `sum += adc_get(ADC_1, FLAME_AO_CH);`（同样是宏，
  同样展开成 `ADC_Channel_5`）**零警告**；
* 配方渲染出的那两行 `hwcheck_report_int(adc_get(adc_i, ch0));` **各报 2 次**。

"2 次"是个线索：一行两个实参、两处枚举混用，恰好=2。但也可能是
`uint16_t` 实参传给 `int` 形参的隐式提升。本探针用宿主机的 ARMCC **真编译**
一份最小 TU 来分辨（不必起整个工程），再回来改配方。
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

MASTER = REPO / "library" / "masters" / "stm32"
CASES = {
    "A 实参是 int 变量（配方现状）": """
static void probe(void)
{
    unsigned int adc_i = 0;
    unsigned int ch0 = 0;
    adc_get(adc_i, ch0);
}
""",
    "B 实参是枚举常量宏（兄弟件同款）": """
static void probe(void)
{
    adc_get(ADC_1, ADC_Channel_5);
}
""",
    "C 实参都对、只把返回值丢给 int": """
static void probe(void)
{
    int v;
    v = (int)adc_get(ADC_1, ADC_Channel_5);
    (void)v;
}
""",
    "D 实参是 int、返回值给 int（变量形）": """
static void probe(void)
{
    unsigned int adc_i = 0;
    unsigned int ch0 = 0;
    int v;
    v = (int)adc_get(adc_i, ch0);
    (void)v;
}
""",
}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    armcc = next(Path(r"C:\Keil5\Core\ARM\ARMCC\Bin").glob("armcc.exe"), None)
    if armcc is None:
        print("armcc.exe 没找到，跳过")
        return 0
    print(f"armcc：{armcc}")
    root = Path(tempfile.mkdtemp(prefix="firstep-probe-188d-"))
    for label, body in CASES.items():
        src = root / "t.c"
        src.write_text(
            '#include "headfile.h"\n' + body, encoding="utf-8"
        )
        cmd = [
            str(armcc), "-c", "--cpu", "Cortex-M3", "-D", "STM32F10X_MD",
            "-I", str(MASTER / "ml_libs"), "-I", str(MASTER / "sys"),
            "-I", str(MASTER), "-o", str(root / "t.o"), str(src),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        text = (proc.stdout or "") + (proc.stderr or "")
        hits = [ln for ln in text.splitlines() if "#188-D" in ln]
        print(f"\n{label}：{len(hits)} 处 #188-D")
        for line in hits:
            print(f"    {line.strip()}")
        for line in text.splitlines():
            if "error" in line.lower():
                print(f"    (err) {line.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
