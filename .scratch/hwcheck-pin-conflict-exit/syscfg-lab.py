# -*- coding: utf-8 -*-
"""SysConfig CLI 实验：ADC12_0 的孤儿 MEM 脚怎么处理才不再 Resource conflict。

先按**真实生成口径**裁剪母版 syscfg（parse_syscfg(...).prune(slugs)），再送
SysConfig CLI 验证——不裁剪的母版本身有重名错误，直接跑得不出结论（前一版
实验已踩到）。结论落盘 recon-syscfg-lab.txt。
用法：python .scratch/hwcheck-pin-conflict-exit/syscfg-lab.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.syscfg_model import parse_syscfg  # noqa: E402

LAB = Path(__file__).resolve().parent / "syscfg-lab"
BASE = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"
SDK = Path("C:/ti/ccs2051/mspm0_sdk_2_10_00_04")
CLI = Path("C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat")
OUT = Path(__file__).resolve().parent / "recon-syscfg-lab.txt"

PIN7 = 'ADC12_0.peripheral.adcPin7.$assign = "PA22";'
MEM6 = 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_7";'

SLUGS = ("led", "delay", "debug_uart", "oled", "adc")


def _pruned() -> str:
    return parse_syscfg(BASE.read_text(encoding="utf-8")).prune(SLUGS).to_text()


def _drop_pin7(text: str) -> str:
    return text.replace(PIN7 + "\n", "")


def _share_mem6(text: str) -> str:
    return _drop_pin7(text).replace(
        MEM6, 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_3";'
    )


def _drop_pin7_and_mem6(text: str) -> str:
    return _drop_pin7(text).replace(MEM6 + "\n", "")


def _move_rx_pa24(text: str) -> str:
    return text.replace(
        'DEBUG_UART.peripheral.rxPin.$assign = "PA22";',
        'DEBUG_UART.peripheral.rxPin.$assign = "PA24";',
    )


def run_case(name: str, transform) -> str:
    text = transform(_pruned())
    d = LAB / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "mspm0.syscfg").write_text(text, encoding="utf-8", newline="")
    proc = subprocess.run(
        [str(CLI), "-s", str(SDK / ".metadata" / "product.json"),
         "--script", "mspm0.syscfg", "-o", ".", "--compiler", "ticlang"],
        cwd=str(d), capture_output=True, text=True, timeout=600,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    (d / "syscfg.log").write_text(log, encoding="utf-8")
    errors = [ln for ln in log.splitlines() if ln.startswith("error")]
    return (f"exit={proc.returncode}\n" + "\n".join(errors[:12])
            if errors else f"exit={proc.returncode}（无 error 行）\n{log.strip()[-600:]}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    LAB.mkdir(parents=True, exist_ok=True)
    cases = [
        ("a-pruned-base", lambda t: t),
        ("b-drop-pin7", _drop_pin7),
        ("c-share-mem6", _share_mem6),
        ("d-drop-pin7-and-mem6", _drop_pin7_and_mem6),
        ("e-auto-move-rx-pa24", _move_rx_pa24),
        ("f-move-rx-and-drop-pin7", lambda t: _drop_pin7(_move_rx_pa24(t))),
    ]
    lines = [f"# ADC12_0 孤儿 MEM 脚的 SysConfig 实验（检测页缺陷 B 取证）", "",
             f"选中集：{SLUGS}（先按真实生成口径 prune 再送 CLI）", ""]
    for name, fn in cases:
        try:
            body = run_case(name, fn)
        except subprocess.TimeoutExpired:
            body = "超时（600s）"
        lines.append(f"## {name}\n{body}\n")
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
