# -*- coding: utf-8 -*-
"""硬件检测：通用降级（工单 module-hwcheck/07）——未专精件也能生成检测程序。

**为什么这样测**：通用降级的设计难点全在"不猜"上——它要在**没有任何配方**的
前提下，从库内**已声明的事实**（模块头文件里的函数声明、manifest 的引脚角色）
推出两件事：① 这件能不能被无参初始化；② 它是不是 I2C 类（能不能做总线扫描）。
两条都必须机械可判，猜出来的东西（读函数、初始化参数）一律不做：

* 初始化只在头文件里**声明为无参**时才生成调用（`sht20_init()` 编得过，
  `servo_init(servo_id, channel)` 编不过——不认识就不调，如实说清）；
* 总线扫描只在该件**声明了 i2c_scl / i2c_sda 引脚角色**且给了端口 / 引脚宏时
  才渲染，扫的是**这一件自己那条总线**（不是母版那条），只 ping 地址、
  **不读任何寄存器**（猜出来的垃圾值比不测更坏）。

第三件事是"不假装测过"：通用件在检测页与产物注释里都带同一句
「未专精：只验总线和初始化」（措辞单源），外观与 `[专精]` 件可区分。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.clex import strip_comments as _strip_comments
from contest_generator.hwcheck_generic import (
    GENERIC_LABEL,
    GENERIC_LABEL_IDLE,
    GENERIC_LABEL_SCAN_ONLY,
    BusScan,
    GenericSection,
    declare_functions,
    generic_message,
    plan_generic_section,
    plan_init,
    render_generic_runtime,
    render_generic_section,
    resolve_generic_sections,
    scan_for_pins,
)
from contest_generator.hwcheck_recipe import SECTION_TAG, c_string
from contest_generator.library import list_modules
from contest_generator.manifest import ModuleManifest
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32

REAL_LIBRARY = Path(__file__).resolve().parents[1] / "library" / "modules"


def _headers(*texts: str) -> list[tuple[str, str]]:
    """头文件夹具：`(相对路径, 文本)`——与 `interface_names` 吃的形状一致。"""
    return [(f"code/fake_{index}.h", text) for index, text in enumerate(texts)]


# ---------------------------------------------------------------------------
# ① 初始化发现：只认**无参声明**，三级判据（精确 → 唯一 → 认不出）
# ---------------------------------------------------------------------------


def test_declare_functions_reads_name_and_parameter_forms():
    decls = declare_functions(_headers(
        "void sht20_init(void);\n"
        "uint8_t sht20_read(float *t, float *h);\n"
        "void oled_show(void)\n{\n}\n"       # 定义（带函数体）不算声明
        "#define SHT20_ADDR 0x40\n"          # 宏不是函数
    ))
    assert decls["sht20_init"] == frozenset({"void"})
    assert decls["sht20_read"] == frozenset({"float *t, float *h"})
    assert "oled_show" not in decls
    assert "SHT20_ADDR" not in decls


def test_plan_init_prefers_the_slug_convention():
    decls = declare_functions(_headers(
        "void sht20_init(void);\nvoid sht20_read(float *t);\n"))
    assert plan_init("sht20", decls).name == "sht20_init"


def test_plan_init_accepts_an_empty_parameter_list():
    """`foo_init()`（旧式空参声明）与 `foo_init(void)` 一样能无参调。"""
    decls = declare_functions(_headers("void aht10_init();\n"))
    assert plan_init("aht10", decls).name == "aht10_init"


def test_plan_init_falls_back_to_the_only_init_it_can_call():
    """名字不带 slug 前缀（`ir_tx_init` / `IMU_Init`）也认——**唯一**才认。"""
    decls = declare_functions(_headers(
        "void ir_tx_init(void);\nvoid ir_tx_send(unsigned int code);\n"))
    assert plan_init("ir_remote_tx", decls).name == "ir_tx_init"


def test_plan_init_refuses_to_guess_between_two_candidates():
    """两个都能无参调、又没有精确命中 = 猜不出该调哪个 → 不调（宁可不测，不猜）。

    ⚠ 用 `foo` 而不是 `pid`：真实库里 `pid` 有精确命中的 `pid_init`，那一格走
    第一级（`pid_init` × `gray_init` 也在，但精确命中优先）——拿它当"猜不出"的
    样本会把这条用例测成另一件事。
    """
    decls = declare_functions(_headers(
        "void pid_init(void);\nvoid gray_init(void);\n"))
    plan = plan_init("foo", decls)
    assert plan.name == ""
    assert "多个" in plan.reason and "gray_init" in plan.reason

def test_plan_init_refuses_an_init_that_needs_arguments():
    """`servo_init(servo_id, channel)` 通用降级给不出参数——不调，不编参数。"""
    decls = declare_functions(_headers(
        "void servo_init(uint8_t servo_id, uint8_t channel);\n"))
    plan = plan_init("servo", decls)
    assert plan.name == ""
    # 理由要把真实签名带出来：学生看到"需要参数"才知道该去哪儿补配方
    assert "servo_init(uint8_t servo_id, uint8_t channel)" in plan.reason


def test_plan_init_is_empty_without_any_header():
    """`files: []` 的平台条目（实现内嵌母版）：认不出就是不认，不猜。"""
    plan = plan_init("adc", {})
    assert plan.name == ""
    assert plan.reason


# ---------------------------------------------------------------------------
# ② I2C 类判据：只看**已声明的引脚角色**，扫的是这一件自己那条总线
# ---------------------------------------------------------------------------


def _entry(pins: list[dict], files: tuple[str, ...] = ()) -> ModuleManifest:
    return ModuleManifest.from_dict({
        "slug": "fake",
        "description": "测试件",
        "dependencies": [],
        "platforms": {
            PLATFORM_STM32: {
                "files": list(files), "verified": True, "hardware_bound": False,
                "notes": "", "pins": pins,
            },
        },
    }).platforms[PLATFORM_STM32]


def test_scan_for_pins_reads_the_declared_port_and_pin_macros():
    entry = _entry([
        {"id": "SHT20_SCL", "type": "i2c_scl", "default": "PA6",
         "macros": ["SHT20_SCL_GPIO", "SHT20_SCL_PIN"]},
        {"id": "SHT20_SDA", "type": "i2c_sda", "default": "PA7",
         "macros": ["SHT20_SDA_GPIO", "SHT20_SDA_PIN"]},
    ])
    assert scan_for_pins(entry.pins) == BusScan(
        scl_port="SHT20_SCL_GPIO", scl_pin="SHT20_SCL_PIN",
        sda_port="SHT20_SDA_GPIO", sda_pin="SHT20_SDA_PIN",
    )


def test_scan_for_pins_needs_both_roles():
    """只声明了 SCL（或只 SDA）开不出总线——如实不扫。"""
    assert scan_for_pins(_entry([
        {"id": "X_SCL", "type": "i2c_scl", "default": "PA6",
         "macros": ["X_SCL_GPIO", "X_SCL_PIN"]},
    ]).pins) is None


def test_scan_for_pins_needs_the_macros_to_drive_the_bus():
    """声明了 I2C 角色但没给宏（mspm0 走 SysConfig 实例，无 pin_config 宏）：
    渲染器没有能驱动这条总线的名字——不扫，不猜实例名。"""
    assert scan_for_pins(_entry([
        {"id": "I2C_SCL", "type": "i2c_scl", "default": "PA0"},
        {"id": "I2C_SDA", "type": "i2c_sda", "default": "PA1"},
    ]).pins) is None


def test_scan_for_pins_ignores_non_i2c_modules():
    assert scan_for_pins(_entry([
        {"id": "WS2812_IN", "type": "gpio_out", "default": "PA14"},
    ]).pins) is None


# ---------------------------------------------------------------------------
# 地板断言：真实库的"通用降级面"不许缩水
# ---------------------------------------------------------------------------


def test_real_library_stm32_i2c_class_slots_are_all_driveable():
    """真实库 stm32 侧声明了 I2C 角色的格，宏必须齐（否则扫描静默消失）。

    这条是**地板断言**（照 `WIKI_COVERAGE_FLOOR` 先例）：新录一件软 I2C 件
    却忘了写 `macros`，检测页会悄悄少掉"总线扫描"这一项而没人发现。
    基线 18 格（实测 2026-09-20：库内声明 i2c 角色的格共 20，其中 mspm0 两件
    没有 pin_config 宏，见下一条用例）。
    """
    broken: list[str] = []
    seen = 0
    for manifest in list_modules(REAL_LIBRARY):
        entry = manifest.platforms.get(PLATFORM_STM32)
        if entry is None:
            continue
        roles = {pin.type for pin in entry.pins}
        if not roles & {"i2c_scl", "i2c_sda"}:
            continue
        scan = scan_for_pins(entry.pins)
        if scan is None:
            broken.append(f"{manifest.slug}（roles={sorted(roles)}）")
        else:
            seen += 1
    assert seen >= 18, f"能扫的 stm32 I2C 格少于实测基线（实测 18 格）：{seen}"
    assert broken == [], f"声明了 I2C 角色却扫不了（缺宏 / 缺角色）：{broken}"


def test_real_library_mspm0_i2c_roles_carry_no_pin_macros_so_no_scan():
    """mspm0 侧的平台不对称**如实钉住**：那边的 I2C 走 SysConfig 实例，
    manifest 的 `macros` 为空（mspm0 的引脚由 syscfg 生成，没有 pin_config.h 宏）。

    断言的是**原因**（宏为空 → 渲染器没有能驱动那条总线的名字）而不是结论：
    哪天 mspm0 也给出宏，这条会红，逼着人把渲染器那半（`GPIOn_enum` 是 stm32
    的 ml_gpio 类型）一起想清楚，而不是让扫描"看着有、其实扫不动"。
    """
    checked = 0
    for manifest in list_modules(REAL_LIBRARY):
        entry = manifest.platforms.get(PLATFORM_MSPM0)
        if entry is None:
            continue
        pins = [pin for pin in entry.pins if pin.type in ("i2c_scl", "i2c_sda")]
        if not pins:
            continue
        checked += 1
        assert all(not pin.macros for pin in pins), (
            f"{manifest.slug} × mspm0 的 I2C 角色突然有宏了："
            f"{[(pin.id, pin.macros) for pin in pins]}——通用降级的扫描器只认"
            "stm32 的 ml_gpio 类型，请连同渲染器一起扩展（别只加宏）"
        )
        assert scan_for_pins(entry.pins) is None
    assert checked >= 2, f"mspm0 侧声明 I2C 角色的格应至少有 2（实测 ml_mpu6050 / oled）：{checked}"


def test_real_library_generic_label_is_the_single_source_wording():
    assert GENERIC_LABEL == "未专精：只验总线和初始化"


# ---------------------------------------------------------------------------
# ③ 通用小节的规划与渲染：真库真件，逐字断言
# ---------------------------------------------------------------------------


def _real(slug: str, platform: str) -> tuple[ModuleManifest, list[tuple[str, str]]]:
    """真实库的一格：manifest + 它**自己的**头文件文本（不并母版头——通用
    降级的候选面就是模块自己的头，见 `plan_init` 的三级判据）。"""
    manifest = next(m for m in list_modules(REAL_LIBRARY) if m.slug == slug)
    entry = manifest.platforms[platform]
    headers: list[tuple[str, str]] = []
    for rel in entry.files:
        if rel.lower().endswith(".h"):
            path = REAL_LIBRARY / slug / rel
            if path.is_file():
                headers.append((rel, path.read_text(encoding="utf-8")))
    return manifest, headers


def test_plan_generic_section_for_an_i2c_device_carries_init_and_scan():
    """真库的软 I2C 件（sht20 × stm32）：认得出无参初始化，且扫的是**它自己
    声明的那条总线**（PA6/PA7 的宏），不是母版那条（PA11/PA12）。"""
    manifest, headers = _real("sht20", PLATFORM_STM32)
    section = plan_generic_section(PLATFORM_STM32, manifest, headers)
    assert section.slug == "sht20"
    assert section.init.name == "sht20_init"
    assert section.scan == BusScan(
        scl_port="SHT20_SCL_GPIO", scl_pin="SHT20_SCL_PIN",
        sda_port="SHT20_SDA_GPIO", sda_pin="SHT20_SDA_PIN",
    )
    assert "PA6" in section.scan_label and "PA7" in section.scan_label
    assert section.headers == ("sht20_stm32.h",)
    assert section.label == GENERIC_LABEL
    assert section.scan_note == ""          # 扫得了就不必解释为什么没扫
    assert "sht20_init()" in section.plan_text


def test_plan_generic_section_for_a_non_i2c_device_has_no_scan():
    """非 I2C 件（ws2812 × mspm0）：只有初始化，没有扫描这一项，也不解释。"""
    manifest, headers = _real("ws2812", PLATFORM_MSPM0)
    section = plan_generic_section(PLATFORM_MSPM0, manifest, headers)
    assert section.init.name == "ws2812_init"
    assert section.scan is None
    assert section.scan_note == ""          # 本来就不适用 ≠ 该扫没扫
    assert "扫描" not in section.plan_text


def test_plan_generic_section_without_a_callable_init_still_plans_and_says_why():
    """初始化要参数的件（servo）：照常规划（**不报错、不拒绝**），如实说清
    为什么这一节在板上不做动作，且**不许**再印「只验总线和初始化」。"""
    manifest, headers = _real("servo", PLATFORM_STM32)
    section = plan_generic_section(PLATFORM_STM32, manifest, headers)
    assert section.init.name == ""
    assert "servo_init(uint8_t servo_id, uint8_t channel)" in section.init.reason
    assert "没有可执行的初始化" in section.plan_text
    assert section.label == GENERIC_LABEL_IDLE
    assert GENERIC_LABEL not in section.label


def test_plan_generic_section_says_why_it_did_not_scan_an_i2c_device():
    """**票面只写了"声明了 I2C 角色就扫"，实务上还差"能不能驱动"**：

    mspm0 的 `ml_mpu6050` 声明了 `i2c_scl`/`i2c_sda` 却没有 pin_config 宏
    （引脚由 SysConfig 实例给）——扫不了。判据收窄这件事**必须有说法**
    （`scan_note` 进检测页与产物），不然就是静默少测一项。
    """
    manifest, headers = _real("ml_mpu6050", PLATFORM_MSPM0)
    section = plan_generic_section(PLATFORM_MSPM0, manifest, headers)
    assert section.scan is None
    assert "SysConfig" in section.scan_note and "不扫" in section.scan_note
    assert "不做总线扫描" in section.plan_text
    code = "\n".join(render_generic_section(section))
    assert c_string(f"不做总线扫描：{section.scan_note}") in code
    # 本来就不带 I2C 角色的件（ws2812）：没有"该扫没扫"，一句都不多说
    assert plan_generic_section(
        PLATFORM_MSPM0, *_real("ws2812", PLATFORM_MSPM0)).scan_note == ""


def test_plan_generic_section_marks_a_scan_only_section():
    """只扫了总线、初始化认不出的件（pca9685 的 init 要 freq）——标注不许说
    「只验总线和初始化」（初始化没跑）。"""
    manifest, headers = _real("pca9685", PLATFORM_STM32)
    section = plan_generic_section(PLATFORM_STM32, manifest, headers)
    assert section.init.name == ""
    assert section.scan is not None
    assert section.label == GENERIC_LABEL_SCAN_ONLY


def test_render_generic_section_carries_the_label_and_not_the_specialized_tag():
    """小节体：带「未专精」原话、**不带** `[专精]`、真调初始化、扫这一件那条总线。

    （函数外壳 `static void hwcheck_generic_<slug>(void)` 由 `render_main_c`
    套上——那是 `tests/test_hwcheck.py` 的地盘，见那儿的通用小节用例。）
    """
    manifest, headers = _real("sht20", PLATFORM_STM32)
    code = "\n".join(render_generic_section(
        plan_generic_section(PLATFORM_STM32, manifest, headers)))
    assert c_string(GENERIC_LABEL) in code          # 「未专精」标注进产物
    assert SECTION_TAG not in code                  # 专精标记不许出现在通用小节
    assert "sht20_init();" in code
    assert "hwcheck_i2c_scan(" in code
    assert "SHT20_SCL_GPIO" in code and "SHT20_SDA_GPIO" in code


def test_render_generic_section_never_calls_anything_but_the_init():
    """**票面硬约定**：通用路径不产生任何"猜出来的读调用"。

    判据 = 该模块自己头文件里的名字 ∩ 通用小节里的调用名，必须**只有初始化**
    那一个（`sht20_read` / `sht20_read_temperature` 一个都不许出现）。其余调用
    只能来自框架 / 平台（`hwcheck_*` / `gpio_*`），逐条在白名单里点名。
    """
    module_names = set(declare_functions(_real("sht20", PLATFORM_STM32)[1]))
    manifest, headers = _real("sht20", PLATFORM_STM32)
    code = "\n".join(render_generic_section(
        plan_generic_section(PLATFORM_STM32, manifest, headers)))
    called = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", _strip_comments(code)))
    framework = {
        "hwcheck_section", "hwcheck_detail", "hwcheck_report", "hwcheck_newline",
        "hwcheck_verdict_probe_none", "hwcheck_i2c_scan", "hwcheck_i2c_ping",
        "hwcheck_report_hex", "gpio_init", "gpio_set", "gpio_get",
    }
    assert called <= framework | {"sht20_init"}, called
    assert called & module_names == {"sht20_init"}, called & module_names
    assert not any("read" in name for name in called), called


def test_render_generic_runtime_is_rendered_only_when_a_scan_exists():
    """按需渲染（04/05 的编译矩阵纪律）：没有扫描件时不留 ping 助手——
    声明了没人调的函数，ARMCC 报 `#177-D` / tiarmclang 报 `-Wunused-function`。"""
    manifest, headers = _real("ws2812", PLATFORM_MSPM0)
    no_scan = (plan_generic_section(PLATFORM_MSPM0, manifest, headers),)
    assert render_generic_runtime(no_scan) == []
    i2c_manifest, i2c_headers = _real("sht20", PLATFORM_STM32)
    with_scan = (plan_generic_section(PLATFORM_STM32, i2c_manifest, i2c_headers),)
    code = "\n".join(render_generic_runtime(with_scan))
    assert "hwcheck_i2c_ping" in code and "hwcheck_i2c_scan" in code
    # 地址区间与 Python 侧常量同源（改一处不许漂）
    assert "0x08" in code and "0x77" in code


def test_generic_message_names_the_label_and_the_plan():
    """检测页那句点名：带「未专精」原话 + 这一趟到底做什么。"""
    manifest, headers = _real("sht20", PLATFORM_STM32)
    section = plan_generic_section(PLATFORM_STM32, manifest, headers)
    message = generic_message(section)
    assert message.startswith("sht20：")
    assert GENERIC_LABEL in message
    assert section.plan_text in message


def test_real_library_every_unspecialized_slot_can_be_planned():
    """**地板断言**：真实库每个未专精格都规划得出来（不报错、不拒绝）。

    同时把实测基线钉住：未专精格不许少于 **135**、能拿到无参初始化的格不许少于 **110**
    （2026-09-25 实测：planned 135 / with_init 110）——哪天库内改名把初始化判据
    打瘸了，这里当场红，而不是让学生上板才发现"这一节什么都不做"。

    ⚠ **这两个数随专精面推进而下降**（工单 09 把 v1 清单补到 17 格 → 168/140 变 157/132；
    工单 `hwcheck-specialize/03` 把 `aht10` / `sht20` / `sht30` × 两平台这 6 格转专精
    → 159/134 变 153/128；工单 `hwcheck-specialize/04` 把 `bh1750` / `bmp180` / `ms5611`
    × 两平台这 6 格转专精 → 153/128 变 147/122；工单 `hwcheck-specialize/05` 把
    `hmc5883l` / `qmc5883l` / `tcs34725` × 两平台这 6 格转专精 → 147/122 变 141/116；
    工单 `hwcheck-specialize/06` 把 `mlx90614` / `sgp30` / `at24c02` × 两平台这 6 格转专精
    → 141/116 变 **135/110**——这 6 格原本每格都能拿到无参初始化（`mlx90614_init` /
    `sgp30_init` / `at24c02_init`，见 `probe-batch-cells.txt` 的【06】段），所以两个数各降 6）。
    降的时候要**如实改这里并写清为什么**，别顺手删断言：它挡的是"初始化判据悄悄失灵"，
    不是"配方变多了"；每批该降多少的实测算式见
    `.scratch/hwcheck-specialize/probe-batch-cells.txt`。
    """
    from contest_generator.hwcheck_recipe import load_recipes

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(REAL_LIBRARY, manifests)
    specialized = {
        (slug, platform) for slug, catalog in recipes.items()
        for platform in catalog.sections
    }
    planned = 0
    with_init = 0
    for manifest in manifests:
        for platform in manifest.platforms:
            if (manifest.slug, platform) in specialized:
                continue
            _m, headers = _real(manifest.slug, platform)
            section = plan_generic_section(platform, manifest, headers)
            planned += 1
            # ⚠ 判"拿到没有"必须看 `.init.name`：`InitPlan` 对象恒为真，
            # 写成 `if section.init:` 会让这条地板断言**恒真**（本单评审后自查
            # 抓到过一次——重构把字符串换成对象时最容易出这种静默失效）。
            if section.init.name:
                with_init += 1
            else:
                assert section.init.reason, f"{manifest.slug} × {platform} 没给出理由"
    assert planned >= 135, f"未专精格少于实测基线 135：{planned}"
    assert with_init >= 110, f"能无参初始化的格少于实测基线 110：{with_init}"


# ---------------------------------------------------------------------------
# ④ 规划一趟（resolve_generic_sections）：读盘、过滤、排序
# ---------------------------------------------------------------------------


def test_resolve_generic_sections_skips_specialized_and_foreign_platforms():
    """选中集 → 通用小节：**专精件不走通用**，**没有本平台条目的点名件也不走**
    （它由检测页的 missing 那条路点名，这里再出一条小节就是"两处各说一半"）。"""
    manifests = list_modules(REAL_LIBRARY)
    sections = resolve_generic_sections(
        PLATFORM_STM32,
        ["led", "beep", "sr04", "sht20"],
        ["led"],                     # led 已有专精配方 → 不走通用
        manifests,
        REAL_LIBRARY,
    )
    # sr04 在 stm32 没有条目（实测：只有 mspm0 版）→ 既不通用也不报错
    assert [section.slug for section in sections] == ["beep", "sht20"]
    assert all(section.platform == PLATFORM_STM32 for section in sections)


def test_resolve_generic_sections_is_idempotent_for_a_repeated_device():
    """同一件选两次：只出一条小节（两条 = 两个同名 C 函数，编不过）。"""
    manifests = list_modules(REAL_LIBRARY)
    sections = resolve_generic_sections(
        PLATFORM_STM32, ["beep", "beep"], [], manifests, REAL_LIBRARY)
    assert [section.slug for section in sections] == ["beep"]


def test_resolve_generic_sections_follows_the_shared_verification_order():
    """顺序 = 工程 README「验证顺序清单」同一函数（bring-up 件排前面）。

    判据不手写期望顺序，而是拿**同一个排序函数**的输出当基准——顺序判据只有
    一处（`readme.sort_verification_order`），测试侧再推一遍就是第二个判据源。
    """
    from contest_generator.readme import sort_verification_order

    manifests = {m.slug: m for m in list_modules(REAL_LIBRARY)}
    devices = ["beep", "led_beep", "sht20", "ws2812"]
    expected = [
        m.slug for m in sort_verification_order(
            [manifests[slug] for slug in devices])
    ]
    sections = resolve_generic_sections(
        PLATFORM_STM32, devices, [], list(manifests.values()), REAL_LIBRARY)
    assert [section.slug for section in sections] == expected
    assert expected.index("led_beep") < expected.index("sht20")   # bring-up 前置


def test_every_device_ends_up_in_exactly_one_bucket():
    """**不静默**：选中的每一件要么专精、要么通用、要么被点名缺平台条目。

    这条是"不报错、不拒绝"（票面第一条验收）的机械化形态：三张清单之外
    不许再有第四种下场——器件从三处一起消失，学生看到的就是"选了没反应"。
    """
    from contest_generator.hwcheck_recipe import load_recipes
    from contest_generator.selection import check_platform_warnings, resolve_dependencies

    manifests = list_modules(REAL_LIBRARY)
    by_slug = {m.slug: m for m in manifests}
    recipes = load_recipes(REAL_LIBRARY, manifests)
    devices = ["led", "beep", "sr04", "sht20", "ws2812", "servo"]
    expanded = resolve_dependencies(devices, by_slug)
    specialized = {
        slug for slug in devices
        if (catalog := recipes.get(slug)) is not None
        and catalog.for_platform(PLATFORM_STM32) is not None
    }
    missing = {
        warning.slug
        for warning in check_platform_warnings(devices, PLATFORM_STM32, by_slug)
        if warning.kind == "missing"
    }
    generic = resolve_generic_sections(
        PLATFORM_STM32, devices, specialized, expanded, REAL_LIBRARY)
    buckets = {section.slug for section in generic} | specialized | missing
    assert buckets == set(devices), set(devices) - buckets
    assert not (specialized & {s.slug for s in generic}), "专精件不许再出通用小节"
