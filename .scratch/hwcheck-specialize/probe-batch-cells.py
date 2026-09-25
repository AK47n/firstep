# -*- coding: utf-8 -*-
"""首批 20 件的**逐格能力清点**（写工单 03–08 的"基线该降多少"要用到的实测数）。

只读，不改库。对首批 20 件的每一格（slug × 平台）算一遍**未专精时通用降级能给什么**：
  * `init` = `plan_generic_section(...).init.name`（非空 = 这一格现在能拿到无参初始化，
    专精化之后就从"未专精基线"里减 1）；
  * `scan` = 能不能出总线地址扫描（I2C 类件才有；stm32 侧才有，mspm0 侧走 SysConfig
    实例、manifest 里没有 pin_config 宏 → 不扫）。

为什么要有这份读数：`tests/test_hwcheck_generic.py` 的 `planned >= 157` / `with_init >= 132`
是**随批次下降**的基线，spec 要求"每批按实数如实下调并写原因"。每批各降多少不能靠感觉
——"这一格现在有没有 init"是库内事实，扫一遍就有。

用法：`py -3 .scratch/hwcheck-specialize/probe-batch-cells.py`；读数先落盘再打印。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.hwcheck_generic import plan_generic_section  # noqa: E402
from contest_generator.hwcheck_recipe import load_recipes  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402

LIB = REPO / "library" / "modules"
BATCHES: list[tuple[str, tuple[str, ...]]] = [
    ("03 温湿度", ("aht10", "sht20", "sht30")),
    ("04 光照气压", ("bh1750", "bmp180", "ms5611")),
    ("05 姿态光色", ("hmc5883l", "qmc5883l", "tcs34725")),
    ("06 红外气体存储", ("mlx90614", "sgp30", "at24c02")),
    ("07 数字外设单总线", ("ads1115", "pca9685", "dht11", "ds18b20")),
    ("08 称重人机执行", ("hx711", "joystick", "servo", "relay")),
]
LINES: list[str] = ["=== 首批 20 件逐格清点：通用降级能给什么（基线该降多少） ===", ""]

manifests = {m.slug: m for m in list_modules(LIB)}
recipes = load_recipes(LIB, manifests)
specialized = {(slug, platform) for slug, one in recipes.items()
               for platform in one.sections}
LINES.append(f"现状：配方文件里 {len(recipes)} 件 / {len(specialized)} 格已专精")
LINES.append("")

total_cells = total_init = 0
for title, slugs in BATCHES:
    cells = init_cells = 0
    LINES.append(f"【{title}】")
    for slug in slugs:
        manifest = manifests[slug]
        for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
            if platform not in manifest.platforms:
                LINES.append(f"   {slug:10s} {platform:6s} —— 本平台没有这一格")
                continue
            entry = manifest.platforms[platform]
            headers = [
                (rel, (LIB / slug / rel).read_text(encoding="utf-8", errors="replace"))
                for rel in entry.files if rel.lower().endswith(".h")
            ]
            section = plan_generic_section(platform, manifest, headers)
            has_init = bool(section.init.name)
            cells += 1
            init_cells += 1 if has_init else 0
            LINES.append(
                f"   {slug:10s} {platform:6s} init={section.init.name or '（拿不到）':<24s}"
                f" scan={'yes' if section.scan else 'no ':3s}"
                f" {'已专精' if (slug, platform) in specialized else ''}"
            )
    total_cells += cells
    total_init += init_cells
    LINES.append(f"   → 本批 {cells} 格；转专精后基线各降 {cells} / {init_cells}"
                 f"（拿不到 init 的 {cells - init_cells} 格只降 planned）")
    LINES.append("")

LINES.append(f"合计：{total_cells} 格；其中能拿无参初始化的 {total_init} 格、"
             f"拿不到的 {total_cells - total_init} 格（pca9685 / servo 两平台各 2 格）")
LINES.append("落到测试那条基线上（`tests/test_hwcheck_generic.py:423-424` 一带）："
             "从本 spec 立项时的 159/134 起算，减去上表每一批的实降数——"
             "03~06 各 6/6、07 与 08 各 8/6。**已落地的实况**（工单落地时以当场实测为准）："
             "03 → 153/128、04 → 147/122、05 → 141/116、06 → 135/110、07 → **127/104**；"
             "08 落地后应为 119/98。")
LINES.append("（本文件是「每批该降多少」的算式，不替代实测；带 `已专精` 的格就是已落地的批次。）")

text = "\n".join(LINES) + "\n"
(REPO / ".scratch" / "hwcheck-specialize" / "probe-batch-cells.txt").write_text(
    text, encoding="utf-8")
print(text)
