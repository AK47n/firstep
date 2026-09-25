# -*- coding: utf-8 -*-
"""工单 05–08 的形状底稿：**mspm0 侧"动作 + 等待"到底怎么写**（写进工单前先跑真校验器）。

背景（两份 recon 在这里自相矛盾，必须实测定案）：
  * recon-03 §2 给 `servo` 的推荐探针动作是 `servo_set_angle(...)` → `delay_ms(600)` → …
    ——但同一份 recon 的 §0 又写着 "mspm0 侧配方只能引用模块自己 .h 里的名字"，
    而 `delay_ms` 在 mspm0 上属于 **delay 模块**，不是 servo 模块的名字；
  * recon-01 §0 / recon-04 §0.1 说 `prereq` 是**唯一**按"库内任何模块 ∪ 母版"判的段。

本探针（只读，不改库）把四种形状喂进真校验器（`parse_recipes` + `validate_recipes`
+ `render_recipe_section`），把"哪一句在哪一段合法"钉成事实：

  A. mspm0 × servo：`delay_ms` 放进 **probe**（recon-03 的推荐形状）→ 预期构建期红；
  B. mspm0 × servo：整条序列放进 **prereq**（bh1750 先例）→ 预期 PASS 且渲染顺序对；
  C. mspm0 × relay：同上（`relay_init` + `relay_set(1)` + `delay_ms(500)` + `relay_set(0)`）；
  D. mspm0 × hx711：`prereq = ["hx711_init()", "delay_ms(500)"]` + 三元判据探头
     ——比 recon-02 的"不写 init、单读作探头"多一层（gram 可用），标成**可选替代**；
  E. mspm0 × servo：`delay_ms` 放进 **init**（第三种写法）→ 预期同样红（证明"只有 prereq"）。

用法：`py -3 .scratch/hwcheck-specialize/probe-mspm0-delay-shapes.py`
读数先落盘 `probe-mspm0-delay-shapes.txt` 再打印。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.hwcheck_errors import HwCheckError  # noqa: E402
from contest_generator.hwcheck_recipe import (  # noqa: E402
    interface_names, parse_recipes, render_recipe_section, validate_recipes,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
LINES: list[str] = ["=== 工单 05–08 形状底稿：mspm0 侧的 delay_ms 只能进 prereq ===", ""]

manifests = list_modules(MODULES)
master_dir = MASTERS / PLATFORM_MSPM0
master_headers = [
    (path.relative_to(master_dir).as_posix(), path.read_text(encoding="utf-8", errors="replace"))
    for path in sorted(master_dir.rglob("*.h"))
] if master_dir.is_dir() else []
interfaces = {PLATFORM_MSPM0: interface_names(
    manifests, MODULES, PLATFORM_MSPM0, master_headers)}
LINES.append(f"mspm0 母版 .h 个数：{len(master_headers)}（0 = 母版没有头，配方段只认本模块头）")
LINES.append(f"servo × mspm0 可用名字数：{len(interfaces[PLATFORM_MSPM0]['servo'])}、"
             f"relay：{len(interfaces[PLATFORM_MSPM0]['relay'])}、"
             f"hx711：{len(interfaces[PLATFORM_MSPM0]['hx711'])}")
LINES.append(f"servo × mspm0 名单里有 delay_ms 吗："
             f"{'delay_ms' in interfaces[PLATFORM_MSPM0]['servo']}")
LINES.append("")

CASES: list[tuple[str, str, dict, str]] = [
    ("A", "servo", {
        "include": {"headers": ["servo.h"]},
        "init": {"calls": ["servo_init(0, 0)"]},
        "probe": {"calls": ["servo_set_angle(0, 0)", "delay_ms(600)",
                            "servo_set_angle(0, 90)"]},
        "read": {"expressions": ["SERVO_ANGLE_MAX"]},
    }, "delay_ms 放进 probe（recon-03 §2 的推荐形状）→ 预期红"),
    ("B", "servo", {
        "include": {"headers": ["servo.h"]},
        "prereq": {"calls": ["servo_init(0, 0)", "delay_ms(600)",
                             "servo_set_angle(0, 90)", "delay_ms(600)",
                             "servo_set_angle(0, 0)"]},
        "read": {"expressions": ["SERVO_ANGLE_MAX", "SERVO_FREQ_HZ", "SERVO_PULSE_US(90)"]},
    }, "整条序列放进 prereq、不写 init（bh1750 先例）→ 预期 PASS"),
    ("C", "relay", {
        "include": {"headers": ["relay.h"]},
        "prereq": {"calls": ["relay_init()", "relay_set(1)", "delay_ms(500)",
                             "relay_set(0)"]},
        "read": {"expressions": ["RELAY_ON_LEVEL"]},
    }, "relay 同款 prereq 形状 → 预期 PASS"),
    ("D", "hx711", {
        "include": {"headers": ["hx711.h"]},
        "locals": {"declarations": ["uint32_t raw = 0"]},
        "prereq": {"calls": ["hx711_init()", "delay_ms(500)"]},
        "probe": {"calls": ["(raw = hx711_read_raw(), (raw != 0) ? 1 : 0)"],
                  "expect": "1"},
        "read": {"items": [
            {"expression": "raw", "unit": "24bit 偏移值"},
            {"expression": "(int)raw - 8388608", "unit": "有符号计数"},
        ]},
    }, "hx711：prereq 里 init + 等 500ms，探头单读（可选替代，gram 可用）→ 预期 PASS"),
    ("E", "servo", {
        "include": {"headers": ["servo.h"]},
        "init": {"calls": ["servo_init(0, 0)", "delay_ms(600)",
                           "servo_set_angle(0, 90)"]},
        "read": {"expressions": ["SERVO_ANGLE_MAX"]},
    }, "delay_ms 放进 init（第三种写法）→ 预期同样红"),
]

for tag, slug, section, why in CASES:
    document = {slug: {PLATFORM_MSPM0: section}}
    LINES.append(f"{tag}) {slug} × mspm0：{why}")
    try:
        recipes = parse_recipes(document)
        validate_recipes(recipes, manifests, interfaces)
        code = "\n".join(render_recipe_section(recipes[slug][PLATFORM_MSPM0]))
        LINES.append("   ✓ PASS —— 渲染出的 C：")
        for line in code.splitlines():
            if line.strip() and not line.strip().startswith("/*"):
                LINES.append("      " + line.strip()[:120])
    except HwCheckError as exc:
        LINES.append("   ✗ 构建期红：" + str(exc).splitlines()[0][:200])
    LINES.append("")

LINES.append("结论（工单 05–08 照它写）：mspm0 侧 init/probe/read 里出现 delay_ms 一律红；"
             "要「动作 + 等待」就只能整条进 prereq（不写 init 段）。")

text = "\n".join(LINES) + "\n"
(REPO / ".scratch" / "hwcheck-specialize" / "probe-mspm0-delay-shapes.txt").write_text(
    text, encoding="utf-8")
print(text)
