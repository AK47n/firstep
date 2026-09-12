"""全库「同类功能件没有同组」机械筛（只读，零额度）。

三道筛：
  A) 关键词筛：manifest description + platforms[*].notes 里提到**别的模块名**
     （slug 字面 或 该模块的 kit 名）且带「互替/替代/可替代/等效/同款/承接/
     二选一/同功能」一类词的片段 —— 噪声高，逐条判。
  B) 默认脚重叠筛：两模块在**同一平台**的 pins[].default 落到同一块板的同一脚
     —— 母版刻意的设计（同选概率最低者重叠），只作候选池。
  C) 同功能多实现形态：同一器件不同接口（UART/I2C/SPI）、同型号不同屏。
  D) kit 交叉提及：notes 提到他件的 kit 型号。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch/exclusive-group-gap-audit/scan.py
产物：.scratch/exclusive-group-gap-audit/scan-output.txt（本脚本 stdout 全量）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"
OUT = Path(__file__).resolve().parent / "scan-output.txt"

SUBSTITUTE_WORDS = (
    "互替",
    "替代",
    "可替代",
    "等效",
    "同款",
    "承接",
    "二选一",
    "同功能",
    "换成",
    "换件",
)

# 引脚歧义：同一块板上同一个脚（stm32 = P<port><num>，mspm0 = 同名 PAxx）
PIN_RE = re.compile(r"\bP[A-D]\d{1,2}\b")


def load_modules() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(MODULES.iterdir()):
        if not path.is_dir():
            continue
        mf = path / "manifest.json"
        if not mf.exists():
            continue
        out[path.name] = json.loads(mf.read_text(encoding="utf-8"))
    return out


def platform_notes(mod: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for plat, entry in (mod.get("platforms") or {}).items():
        if isinstance(entry, dict):
            out[plat] = str(entry.get("notes") or "")
    return out


def default_pins(mod: dict) -> dict[str, dict[str, str]]:
    """{platform: {pin: role_id}}（同名脚多角色只留第一个）。"""
    out: dict[str, dict[str, str]] = {}
    for plat, entry in (mod.get("platforms") or {}).items():
        if not isinstance(entry, dict):
            continue
        pins: dict[str, str] = {}
        for role in entry.get("pins") or []:
            if not isinstance(role, dict):
                continue
            default = role.get("default")
            if isinstance(default, str) and default:
                pins.setdefault(default, str(role.get("id") or ""))
        out[plat] = pins
    return out


def kits(mod: dict) -> set[str]:
    out: set[str] = set()
    for entry in (mod.get("platforms") or {}).values():
        if isinstance(entry, dict) and entry.get("kit"):
            out.add(str(entry["kit"]))
    return out


def main() -> int:
    mods = load_modules()
    slugs = sorted(mods)
    lines: list[str] = []
    say = lines.append

    say(f"# 机械筛输出（{len(slugs)} 个模块）")
    say("")

    # ---- 已有组 ----
    say("## 0. 现状：已声明 exclusive_group 的模块")
    groups: dict[str, list[str]] = {}
    for slug in slugs:
        eg = mods[slug].get("exclusive_group")
        if isinstance(eg, dict):
            groups.setdefault(str(eg["id"]), []).append(slug)
    for gid, members in sorted(groups.items()):
        say(f"- {gid}: {members}")
    say("")

    # ---- 筛 A：关键词 ----
    say("## A. 关键词筛（提到别的模块 + 互替类词）")
    hits = 0
    for slug in slugs:
        for plat, note in platform_notes(mods[slug]).items():
            for word in SUBSTITUTE_WORDS:
                for m in re.finditer(re.escape(word), note):
                    start = max(0, m.start() - 120)
                    end = min(len(note), m.end() + 120)
                    ctx = note[start:end].replace("\n", " ")
                    # 上下文里必须出现**别的 slug 字面**，否则不是「件×件」关系
                    others = [
                        s
                        for s in slugs
                        if s != slug
                        and re.search(rf"(?<![a-z0-9_]){re.escape(s)}(?![a-z0-9_])", ctx)
                    ]
                    if not others:
                        continue
                    hits += 1
                    say(f"- [{slug}/{plat}] 词={word!r} 他件={others}")
                    say(f"    …{ctx}…")
    say(f"（命中 {hits} 条）")
    say("")

    # ---- 筛 B：默认脚重叠 ----
    say("## B. 默认脚重叠（同平台同脚的两模块）")
    pinmap = {slug: default_pins(mods[slug]) for slug in slugs}
    for plat in ("stm32", "mspm0"):
        inverted: dict[str, list[str]] = {}
        for slug in slugs:
            for pin, role in pinmap[slug].get(plat, {}).items():
                inverted.setdefault(pin, []).append(f"{slug}:{role}")
        say(f"### {plat}")
        for pin in sorted(inverted, key=lambda p: (p[:2], int(p[2:]))):
            owners = inverted[pin]
            if len(owners) < 2:
                continue
            say(f"- {pin}: {', '.join(owners)}")
        say("")

    # ---- 筛 C：同功能多实现（器件族）----
    say("## C. 器件族 / 同功能多实现（人工归族，供逐条判）")
    families = {
        "距离/测距": ["us016", "ir_distance", "vl53l0x", "sr04"],
        "姿态": ["imu_uart", "jy61p", "ml_mpu6050"],
        "灰度循迹": ["huidu", "pid", "xunji"],
        "显示": ["lcd", "oled", "max7219", "ili9341", "ili9488", "st7789_para"],
        "无线链路": [
            "zigbee_link",
            "zigbee_uart",
            "zigbee_uart_key",
            "as32",
            "nrf24l01",
            "hc05",
            "esp01s",
            "ec01g",
            "uwb_uart",
            "neo_6m",
        ],
        "环境温湿度": ["dht11", "sht20", "sht30", "aht10"],
        "气压": ["bmp180", "ms5611"],
        "气体": [
            "mq2",
            "mq3",
            "mq4",
            "mq5",
            "mq6",
            "mq7",
            "mq8",
            "mq9",
            "mq135",
            "ms1100",
            "ags10",
            "sgp30",
        ],
        "颜色/光": ["tcs34725", "bh1750", "photoresistance", "s12sd"],
        "声音提示": ["beep", "led", "led_beep", "jq8900", "syn6288"],
        "人机输入": ["key", "key_matrix", "ttp224", "ec11", "ir_remote", "joystick"],
        "身份识别": ["fingerprint", "rc522", "k230", "coord_detect", "open_mv4"],
        "测温": ["ds18b20", "mlx90614"],
        "电机驱动": ["motor", "l298n", "step_motor", "servo", "pca9685"],
        "红外测距/对射": ["ir_beam", "ir_remote_tx"],
    }
    for fam, members in families.items():
        present = [s for s in members if s in mods]
        declared = {gid for s in present for gid, ms in groups.items() if s in ms}
        say(f"- {fam}: {present}  已声明组={sorted(declared)}")
    say("")

    # ---- 筛 D：kit 交叉提及（notes 里出现他件的 kit 名）----
    say("## D. kit 交叉提及（notes 提到他件 kit 型号）")
    kit_owner: dict[str, str] = {}
    for slug in slugs:
        for kit in kits(mods[slug]):
            kit_owner.setdefault(kit, slug)
    d_hits = 0
    for slug in slugs:
        for plat, note in platform_notes(mods[slug]).items():
            for kit, owner in kit_owner.items():
                if owner == slug:
                    continue
                if kit and kit in note:
                    d_hits += 1
                    say(f"- [{slug}/{plat}] 提到 {owner} 的 kit：{kit}")
    say(f"（命中 {d_hits} 条）")

    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)
    print(f"落盘：{OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
