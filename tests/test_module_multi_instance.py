"""module-multi-instance：manifest 能力声明（01）+ 实例展开（02）+ 渲染与骨架
注入（03）的测试文件。

01 边界：manifest 的 multi_instance 块（解析 / 序列化 / 旧 manifest 兼容）、
selection 的 ModuleInstance 模型与 instances 透传。
02 边界：展开纯函数（命名 / 默认脚 / 上限守卫）。
03 边界：led 渲染 hook（led_instances.h 生成 + mspm0 syscfg 落点）与
build_skeleton_interfaces 通道宏注入。前端（04）、推荐 prompt（06）不在此文件。

真实库不变量（led 加 multi_instance 声明后）与旧单实例相关测试
（test_module_led_beep / test_pin_bindings 等）逐字节不破。
"""

import re
from pathlib import Path

import pytest

from contest_generator.boards import BOARDS_DIR, load_boards
from contest_generator.generator import generate
from contest_generator.library import list_modules
from contest_generator.manifest import (
    ManifestError,
    ModuleManifest,
    MultiInstanceSpec,
)
from contest_generator.selection import (
    ExpandedInstance,
    ModuleInstance,
    ModuleSelection,
    SelectionError,
    expand_instances,
    resolve_selection,
)
from contest_generator.instance_render import (
    expand_instance_plans,
    render_led_instances_text,
    rewrite_syscfg_for_led_instances,
)
from contest_generator.skeleton import (
    build_skeleton_interfaces,
    generate_skeleton,
    generate_smoke_main,
)
from tests.fakes import (
    FakeLLM,
    make_fake_ccs_master_project,
    make_fake_master_project,
)

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"
BOARDS = {board.platform: board for board in load_boards(BOARDS_DIR)}
LED = ModuleManifest.load(MODULES / "led")


# ---------------------------------------------------------------------------
# manifest：multi_instance 能力块解析 / 序列化 / 旧 manifest 兼容
# ---------------------------------------------------------------------------


def test_legacy_manifest_without_multi_instance_loads_none():
    """旧 manifest 缺 multi_instance → None（向后兼容，单实例照旧）。"""
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {"stm32": {"files": ["src/dht11.c"], "verified": True}},
    }

    manifest = ModuleManifest.from_dict(data)

    assert manifest.multi_instance is None


def test_legacy_manifest_serializes_without_multi_instance_field():
    """旧 manifest 序列化不引入 multi_instance 键（与基线逐字节一致——写回
    save_manifest 时不会给存量 manifest 平白加一个 null 字段）。"""
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {"stm32": {"files": ["src/dht11.c"], "verified": True}},
    }

    manifest = ModuleManifest.from_dict(data)

    assert "multi_instance" not in manifest.to_dict()


def test_multi_instance_roundtrip_preserves_spec():
    """multi_instance 往返稳定：to_dict → from_dict 无损。"""
    manifest = ModuleManifest(
        slug="led",
        description="LED 指示灯驱动",
        multi_instance=MultiInstanceSpec(max=8, variant="color"),
    )

    parsed = ModuleManifest.from_dict(manifest.to_dict())

    assert parsed == manifest
    assert parsed.multi_instance == MultiInstanceSpec(max=8, variant="color")
    assert manifest.to_dict()["multi_instance"] == {"max": 8, "variant": "color"}


def test_led_manifest_declares_multi_instance():
    """led 模块 manifest 读盘读到 max=8 / variant=color（真实库数据）。"""
    led = ModuleManifest.load(MODULES / "led")

    assert led.multi_instance == MultiInstanceSpec(max=8, variant="color")


def test_all_library_manifests_load_and_only_led_declares_multi_instance():
    """全库 manifest 加载不破；multi_instance 声明只落在 led（首例）。"""
    manifests = list_modules(MODULES)
    by_slug = {m.slug: m for m in manifests}

    assert "led" in by_slug
    assert by_slug["led"].multi_instance == MultiInstanceSpec(max=8, variant="color")
    for slug, manifest in by_slug.items():
        if slug != "led":
            assert manifest.multi_instance is None, slug


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        ({"max": 0, "variant": "color"}, "max"),  # 非正整数
        ({"max": -1, "variant": "color"}, "max"),
        ({"max": "8", "variant": "color"}, "max"),  # 字符串 max（不静默强转）
        ({"max": True, "variant": "color"}, "max"),  # 布尔是 int 子类，宽松强转会放行
        ({"max": 1.5, "variant": "color"}, "max"),  # 浮点
        ({"max": 8, "variant": ""}, "variant"),  # 空 variant
        ({"max": 8, "variant": 123}, "variant"),  # 非字符串 variant
        ({"variant": "color"}, "max"),  # 缺 max
        ({"max": 8}, "variant"),  # 缺 variant
    ],
)
def test_multi_instance_rejects_invalid_values(bad, match):
    """multi_instance 存在则严格校验，错值大声失败（照 _require 系列，不静默
    强转）；match 精确到报错字段（max / variant），不满足于任意 ManifestError。"""
    data = {
        "slug": "led",
        "description": "LED 指示灯驱动",
        "multi_instance": bad,
        "platforms": {"stm32": {"files": [], "verified": True}},
    }

    with pytest.raises(ManifestError, match=match):
        ModuleManifest.from_dict(data)


def test_multi_instance_must_be_object():
    """multi_instance 非对象（如数组 / 字符串 / 数字）大声失败。"""
    data = {
        "slug": "led",
        "description": "LED 指示灯驱动",
        "multi_instance": "8",
        "platforms": {"stm32": {"files": [], "verified": True}},
    }

    with pytest.raises(ManifestError, match="multi_instance"):
        ModuleManifest.from_dict(data)


def test_multi_instance_null_loads_none():
    """multi_instance 显式 null 与缺省同义（None = 不支持多实例）。"""
    data = {
        "slug": "led",
        "description": "LED 指示灯驱动",
        "multi_instance": None,
        "platforms": {"stm32": {"files": [], "verified": True}},
    }

    assert ModuleManifest.from_dict(data).multi_instance is None


# ---------------------------------------------------------------------------
# selection：ModuleInstance 模型 + ModuleSelection.instances + 透传
# ---------------------------------------------------------------------------


def test_module_instance_to_dict_matches_spec_shape():
    """ModuleInstance.to_dict 形状 = spec 的 {name, variant, pin}；缺省 pin /
    variant 归一为空串（空串 = 自动分配 / 非内置色）。"""
    assert ModuleInstance(name="红灯", variant="red").to_dict() == {
        "name": "红灯",
        "variant": "red",
        "pin": "",
    }
    assert ModuleInstance(name="状态灯").to_dict() == {
        "name": "状态灯",
        "variant": "",
        "pin": "",
    }


def test_module_selection_carries_instances_roundtrip():
    """ModuleSelection 能携带 instances，往返不丢（to_dict 形状与 spec 的
    {"led": [{name, variant, pin}]} 一致）。"""
    instances = {
        "led": (
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="状态灯"),
        )
    }
    selection = ModuleSelection(
        modules=("led",), reasons={"led": "指示灯"}, instances=instances
    )

    assert selection.instances == instances
    assert {
        slug: [instance.to_dict() for instance in insts]
        for slug, insts in selection.instances.items()
    } == {
        "led": [
            {"name": "红灯", "variant": "red", "pin": ""},
            {"name": "状态灯", "variant": "", "pin": ""},
        ]
    }


def test_module_selection_instances_default_empty():
    """instances 缺省空 dict（旧选择 / 推荐产物零改动）。"""
    assert ModuleSelection(modules=(), reasons={}).instances == {}


def test_resolve_selection_passes_through_instances(fake_module_library):
    """resolve_selection 透传 instances 不丢（生成 / 骨架 / 展开共用组合操作）。"""
    instances = {
        "led": (ModuleInstance(name="红灯", variant="red"),),
    }

    resolved = resolve_selection(
        fake_module_library, "stm32", ["dht11"], instances=instances
    )

    assert resolved.instances == instances


def test_resolve_selection_without_instances_is_empty(fake_module_library):
    """instances 缺省 = 现行为（空 dict，旧调用方零改动）。"""
    resolved = resolve_selection(fake_module_library, "stm32", ["dht11"])

    assert resolved.instances == {}


# ---------------------------------------------------------------------------
# module-multi-instance/02：实例展开 + 默认脚分配（纯函数）
#
# 契约：给定 led 实例清单 → (slug, 实例号, 宏名, 默认脚) 计划，确定性（同输入
# 同输出）。命名规则：内置色 red/yellow/green → LED_RED/YELLOW/GREEN，重复内
# 置色按出现序 _2/_3 后缀，非内置色按创建顺序 LED_1..n。默认脚：stm32 红/黄/
# 绿优先 PC13/14/15、mspm0 首个实例优先 PA15，其余 board 顺序首个可用 io 脚
# （跳过指定脚 + 同模块已用，不跨模块全局扫描）。实例数 > max 大声失败。
# ---------------------------------------------------------------------------


def _expand(instances, platform):
    return expand_instances(LED, tuple(instances), platform, BOARDS[platform])


def _macros(plan):
    return [entry.macro for entry in plan]


def _pins(plan):
    return [entry.pin for entry in plan]


def test_expand_builtin_colors_stm32_macros_and_pins():
    """红/黄/绿 → LED_RED/YELLOW/GREEN + PC13/PC14/PC15（stm32 三色指定脚）。"""
    plan = _expand(
        [
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="黄灯", variant="yellow"),
            ModuleInstance(name="绿灯", variant="green"),
        ],
        "stm32",
    )

    assert [e.slug for e in plan] == ["led", "led", "led"]
    assert [e.index for e in plan] == [1, 2, 3]
    assert _macros(plan) == ["LED_RED", "LED_YELLOW", "LED_GREEN"]
    assert _pins(plan) == ["PC13", "PC14", "PC15"]


def test_expand_duplicate_builtin_gets_suffix():
    """同一内置色第 2 次起加后缀：两个红灯 → LED_RED + LED_RED_2；两红一黄
    黄仍是 LED_YELLOW（后缀按各色独立出现序）。"""
    plan = _expand(
        [
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="红灯2", variant="red"),
        ],
        "stm32",
    )

    assert _macros(plan) == ["LED_RED", "LED_RED_2"]

    plan = _expand(
        [
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="红灯2", variant="red"),
            ModuleInstance(name="黄灯", variant="yellow"),
        ],
        "stm32",
    )
    assert _macros(plan) == ["LED_RED", "LED_RED_2", "LED_YELLOW"]


def test_expand_non_builtin_numbered_by_creation_order():
    """非内置色（variant 空 / 未知）按创建顺序 LED_1..n，与内置色互不干扰。"""
    plan = _expand(
        [
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="状态灯"),  # variant 空 = 非内置
            ModuleInstance(name="蓝灯", variant="blue"),  # 未知色 = 非内置
            ModuleInstance(name="绿灯", variant="green"),
        ],
        "stm32",
    )

    assert _macros(plan) == ["LED_RED", "LED_1", "LED_2", "LED_GREEN"]


def test_expand_stm32_default_pins_after_builtin_go_board_order():
    """stm32 第 4 个起 board 顺序首个可用 io：三色占 PC13/14/15 后，非内置
    状态灯 → PA0（board 顺序，指定脚跳过）。"""
    plan = _expand(
        [
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="黄灯", variant="yellow"),
            ModuleInstance(name="绿灯", variant="green"),
            ModuleInstance(name="状态灯"),
        ],
        "stm32",
    )

    assert _pins(plan) == ["PC13", "PC14", "PC15", "PA0"]


def test_expand_stm32_duplicate_builtin_does_not_steal_designated_pin():
    """重复内置色 / 非内置色不抢占指定脚：两红一黄 → 红2 走 board 顺序（PA0），
    黄仍留 PC14（红/黄/绿 → PC13/14/15 固定映射保持）。"""
    plan = _expand(
        [
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="红灯2", variant="red"),
            ModuleInstance(name="黄灯", variant="yellow"),
        ],
        "stm32",
    )

    assert _pins(plan) == ["PC13", "PA0", "PC14"]


def test_expand_mspm0_first_instance_pa15_then_board_order():
    """mspm0 首个实例 → PA15（led 单 pin 角色默认），其余 board 顺序（PA15
    指定脚跳过，PA0 起）。"""
    plan = _expand(
        [
            ModuleInstance(name="红灯", variant="red"),
            ModuleInstance(name="黄灯", variant="yellow"),
            ModuleInstance(name="绿灯", variant="green"),
        ],
        "mspm0",
    )

    assert _macros(plan) == ["LED_RED", "LED_YELLOW", "LED_GREEN"]
    assert _pins(plan) == ["PA15", "PA0", "PA1"]


def test_expand_dedup_within_module_all_distinct():
    """同模块内去重：8 个红灯（max 上限）引脚两两互异，宏名 LED_RED..LED_RED_8。"""
    plan = _expand(
        [ModuleInstance(name=f"红灯{i}", variant="red") for i in range(8)],
        "stm32",
    )

    assert _macros(plan) == [f"LED_RED{'' if i == 0 else f'_{i + 1}'}" for i in range(8)]
    assert len(set(_pins(plan))) == 8


def test_expand_explicit_pin_overrides_default():
    """显式 pin 覆盖自动分配：红灯绑 PA6 → PA6；后续自动分配不撞它。"""
    plan = _expand(
        [
            ModuleInstance(name="红灯", variant="red", pin="PA6"),
            ModuleInstance(name="红灯2", variant="red"),
        ],
        "stm32",
    )

    assert _pins(plan) == ["PA6", "PA0"]


def test_expand_upper_bound_rejects_excess_instances():
    """实例数 > max（8）大声失败，中文可读、精确到上限值。"""
    with pytest.raises(SelectionError, match="超过上限 8"):
        _expand(
            [ModuleInstance(name=f"灯{i}") for i in range(9)],
            "stm32",
        )


def test_expand_custom_max_enforced():
    """max 来自 manifest 声明而非写死：max=3 时 4 个实例即拒绝。"""
    manifest = ModuleManifest(
        slug="led",
        description="LED 指示灯驱动",
        multi_instance=MultiInstanceSpec(max=3, variant="color"),
    )
    with pytest.raises(SelectionError, match="超过上限 3"):
        expand_instances(
            manifest,
            tuple(ModuleInstance(name=f"灯{i}") for i in range(4)),
            "stm32",
            BOARDS["stm32"],
        )


def test_expand_non_builtin_first_instance():
    """首个实例即非内置色：stm32 走 board 顺序（PA0）、mspm0 首个仍 PA15——
    不因「首实例非内置」而炸（回归：occurrence 未赋值 NameError）。"""
    plan = _expand([ModuleInstance(name="状态灯")], "stm32")
    assert _macros(plan) == ["LED_1"]
    assert _pins(plan) == ["PA0"]

    plan = _expand([ModuleInstance(name="状态灯")], "mspm0")
    assert _macros(plan) == ["LED_1"]
    assert _pins(plan) == ["PA15"]


def test_expand_empty_instances_returns_empty_plan():
    """空实例清单 = 单默认实例（旧行为）：返回空计划，调用方走单实例路径。"""
    assert _expand([], "stm32") == ()
    assert _expand([], "mspm0") == ()


def test_expand_non_multi_instance_manifest_rejects_instances():
    """不支持多实例的 manifest 带非空实例清单 = 调用方错误（大声失败）；空清单
    仍返回空计划（不误伤旧调用）。"""
    manifest = ModuleManifest(
        slug="dht11", description="DHT11 温湿度传感器驱动"
    )
    with pytest.raises(SelectionError, match="不支持多实例"):
        expand_instances(
            manifest, (ModuleInstance(name="灯"),), "stm32", BOARDS["stm32"]
        )
    assert expand_instances(manifest, (), "stm32", BOARDS["stm32"]) == ()


def test_expand_is_deterministic_and_frozen():
    """同输入同输出（纯函数）；计划条目是冻结数据类（ExpandedInstance 可比较）。"""
    instances = [
        ModuleInstance(name="红灯", variant="red"),
        ModuleInstance(name="状态灯"),
    ]
    first = _expand(instances, "stm32")
    second = _expand(instances, "stm32")

    assert first == second
    assert first[0] == ExpandedInstance(slug="led", index=1, macro="LED_RED", pin="PC13")


# ---------------------------------------------------------------------------
# module-multi-instance/03：渲染（led hook）+ 骨架注入
#
# 渲染契约：led_instances.h 必须定义 LED_CHANNEL_COUNT + 通道索引宏（两平台
# 一致 RED=0/YELLOW=1/GREEN=2/LED_1=3…）+ 每通道 (port, pin) 对 + LED_PIN_TABLE
# （驱动建表用）。stm32 落工程根（与 pin_config.h 同级，母版自带默认 = 单实例
# 三通道 PC13/14/15）；mspm0 落 modules/led/code/（led.c 同目录，库内自带默认
# = 单实例 1 通道 PA15）。mspm0 多实例引脚落 syscfg：通道 0 复用母版 LED_BEEP
# （计划脚 ≠ 现值时改写 $assign）、其余新实例 LED_<实例号>。
# 单实例路径零写侧变化：pin_config.h / syscfg 逐字节不写，led_instances.h
# 用母版/库内默认（不变不写）。
# ---------------------------------------------------------------------------

# 假母版/假模块库素材（集成测试用；真实 led manifest 与真实库目录混用——
# 模块文件读盘与门禁走真实 led 条目）
FAKE_PIN_CONFIG = (
    "/* pin_config.h —— 板级引脚宏（接线单源） */\n"
    "#ifndef _pin_config_h_\n"
    "#define _pin_config_h_\n"
    "#define LED_PORT          GPIO_C\n"
    "#define LED_RED_PIN       Pin_13\n"
    "#define LED_YELLOW_PIN    Pin_14\n"
    "#define LED_GREEN_PIN     Pin_15\n"
    "#endif\n"
)

FAKE_ML_LED_H = (
    "#ifndef _ml_led_h_\n"
    "#define _ml_led_h_\n"
    '#include "ml_gpio.h"\n'
    '#include "pin_config.h"\n'
    '#include "led_instances.h"\n'
    "#include <stdint.h>\n"
    "void led_init(uint8_t channel);\n"
    "void led_on(uint8_t channel);\n"
    "void led_off(uint8_t channel);\n"
    "void led_toggle(uint8_t channel);\n"
    "#endif\n"
)

FAKE_DEFAULT_LED_INSTANCES = (
    "#ifndef _led_instances_h_\n"
    "#define _led_instances_h_\n"
    "#define LED_CHANNEL_COUNT 3\n"
    "#define LED_RED 0\n"
    "#endif\n"
)

FAKE_SYSCFG = (
    "/* fake syscfg */\n"
    'const GPIO = scripting.addModule("/ti/driverlib/GPIO", {}, false);\n'
    "const LED_BEEP = GPIO.addInstance();\n"
    'LED_BEEP.$name = "LED_BEEP";\n'
    "LED_BEEP.associatedPins.create(1);\n"
    'LED_BEEP.associatedPins[0].$name        = "LED";\n'
    'LED_BEEP.associatedPins[0].direction    = "OUTPUT";\n'
    'LED_BEEP.associatedPins[0].initialValue = "CLEARED";\n'
    'LED_BEEP.associatedPins[0].pin.$assign  = "PA15";\n'
    'const Board = scripting.addModule("/ti/driverlib/Board", {}, false);\n'
)

LED_MAIN_C = "int main(void) { led_init(LED_RED); while (1); }\n"

INSTANCES_4 = {
    "led": (
        ModuleInstance(name="红灯", variant="red"),
        ModuleInstance(name="黄灯", variant="yellow"),
        ModuleInstance(name="绿灯", variant="green"),
        ModuleInstance(name="状态灯"),
    )
}


def _fake_stm32_led_master(tmp_path: Path) -> Path:
    """最小 Keil 母版 + led 接线文件（pin_config.h / ml_led.h / led_instances.h
    默认）——ml_led.h 声明 led_init 供 main_calls 门禁解析。"""
    master = make_fake_master_project(tmp_path / "master")
    (master / "pin_config.h").write_text(FAKE_PIN_CONFIG, encoding="utf-8")
    (master / "led_instances.h").write_text(
        FAKE_DEFAULT_LED_INSTANCES, encoding="utf-8"
    )
    (master / "ml_libs").mkdir()
    (master / "ml_libs" / "ml_led.h").write_text(FAKE_ML_LED_H, encoding="utf-8")
    return master


def _fake_mspm0_led_master(tmp_path: Path) -> Path:
    """最小 CCS 母版 + LED_BEEP syscfg（prune / 渲染的落点）。"""
    master = make_fake_ccs_master_project(tmp_path / "ccs_master")
    (master / "mspm0.syscfg").write_text(FAKE_SYSCFG, encoding="utf-8", newline="")
    return master


def _plan(instances: tuple[ModuleInstance, ...], platform: str):
    return expand_instances(LED, instances, platform, BOARDS[platform])


# --------------------------- 纯渲染文本 ---------------------------


def test_render_default_text_matches_checked_in_files():
    """空计划（单实例默认）的渲染文本 = 盘上默认文件（行尾归一后逐字节：
    core.autocrlf 下检出 CRLF，渲染常量恒 LF——归一比较，内容漂移仍红）：
    stm32 母版根 led_instances.h（三通道 PC13/14/15）、mspm0 库内
    code/led_instances.h（单通道 PA15）——渲染层与检查进库的默认文件永不漂移。"""
    stm32_default = (STM32_MASTER / "led_instances.h").read_text(
        encoding="utf-8", errors="replace"
    ).replace("\r\n", "\n")
    mspm0_default = (MODULES / "led" / "code" / "led_instances.h").read_text(
        encoding="utf-8", errors="replace"
    ).replace("\r\n", "\n")

    assert render_led_instances_text((), "stm32") == stm32_default
    assert render_led_instances_text((), "mspm0") == mspm0_default

    assert "#define LED_CHANNEL_COUNT 3" in stm32_default
    assert "#define LED_CHANNEL_COUNT 1" in mspm0_default


def test_render_stm32_multi_plan_channels_and_concrete_pins():
    """stm32 多实例：COUNT=N、通道索引按计划序（LED_1=3）、每通道具体
    (GPIO_x, Pin_y) 对（PA0 → GPIO_A/Pin_0）、便捷宏覆盖每个通道宏。"""
    plan = _plan(INSTANCES_4["led"], "stm32")

    text = render_led_instances_text(plan, "stm32")

    assert "#define LED_CHANNEL_COUNT 4" in text
    for macro, index in (("LED_RED", 0), ("LED_YELLOW", 1), ("LED_GREEN", 2), ("LED_1", 3)):
        assert re.search(rf"#define\s+{macro}\s+{index}\b", text), macro
    assert "#define LED_CHANNEL_0_PORT GPIO_C" in text
    assert "#define LED_CHANNEL_0_PIN  Pin_13" in text
    assert "#define LED_CHANNEL_3_PORT GPIO_A" in text
    assert "#define LED_CHANNEL_3_PIN  Pin_0" in text
    assert "{LED_CHANNEL_3_PORT, LED_CHANNEL_3_PIN}" in text
    for macro in ("LED_RED", "LED_YELLOW", "LED_GREEN", "LED_1"):
        assert f"#define {macro}_ON()" in text
        assert f"#define {macro}_OFF()" in text


def test_render_mspm0_multi_plan_channels_and_instance_macros():
    """mspm0 多实例：通道 0 复用 LED_BEEP 宏、通道 k≥1 引用新 syscfg 实例
    LED_<实例号> 的 <INSTANCE>_PORT / <INSTANCE>_LED<实例号>_PIN 宏（SysConfig
    生成；pin 名全局唯一 → LED2 形态，真机判例）。"""
    plan = _plan(INSTANCES_4["led"], "mspm0")  # PA15/PA0/PA1/PA2

    text = render_led_instances_text(plan, "mspm0")

    assert "#define LED_CHANNEL_COUNT 4" in text
    assert "#define LED_CHANNEL_0_PORT LED_BEEP_PORT" in text
    assert "#define LED_CHANNEL_0_PIN  LED_BEEP_LED_PIN" in text
    assert "#define LED_CHANNEL_1_PORT LED_2_PORT" in text
    assert "#define LED_CHANNEL_1_PIN  LED_2_LED2_PIN" in text
    assert "#define LED_CHANNEL_3_PORT LED_4_PORT" in text
    assert "#define LED_CHANNEL_3_PIN  LED_4_LED4_PIN" in text


# --------------------------- mspm0 syscfg 改写 ---------------------------


def test_rewrite_syscfg_rewrites_channel_zero_and_appends_instances():
    """mspm0 多实例 syscfg：通道 0 计划脚 ≠ 现值 → 改写 LED_BEEP $assign；
    通道 1+ 追加 LED_<实例号> GPIO 实例（LED_2/LED_3，关联 pin $name LED）。
    空计划 → 文本原样（单实例零写侧变化）。"""
    plan = _plan(
        (
            ModuleInstance(name="红灯", variant="red", pin="PB5"),
            ModuleInstance(name="黄灯", variant="yellow"),
            ModuleInstance(name="绿灯", variant="green"),
        ),
        "mspm0",
    )  # PB5 / PA0 / PA1

    rewritten = rewrite_syscfg_for_led_instances(FAKE_SYSCFG, plan)

    assert 'LED_BEEP.associatedPins[0].pin.$assign  = "PB5";' in rewritten
    assert "const LED_2 = GPIO.addInstance();" in rewritten
    assert 'LED_2.associatedPins[0].$name        = "LED2";' in rewritten
    assert 'LED_2.associatedPins[0].direction    = "OUTPUT";' in rewritten
    assert 'LED_2.associatedPins[0].pin.$assign  = "PA0";' in rewritten
    assert "const LED_3 = GPIO.addInstance();" in rewritten
    assert 'LED_3.associatedPins[0].$name        = "LED3";' in rewritten
    assert 'LED_3.associatedPins[0].pin.$assign  = "PA1";' in rewritten
    # 原文行除改写行外逐字保留（首行注释仍在）
    assert rewritten.startswith("/* fake syscfg */\n")

    assert rewrite_syscfg_for_led_instances(FAKE_SYSCFG, ()) == FAKE_SYSCFG


# --------------------------- 展开计划聚合（渲染层入口） ---------------------------


def test_expand_instance_plans_covers_selected_multi_manifests():
    """expand_instance_plans：选中且声明 multi_instance 的模块进计划；无
    instances = 空计划（单默认实例）；非 multi_instance 模块 / 未选中 slug
    的 instances 不进。"""
    plans = expand_instance_plans(
        [LED],
        {"led": (ModuleInstance(name="红灯", variant="red"),)},
        "stm32",
        BOARDS["stm32"],
    )
    assert list(plans) == ["led"]
    assert plans["led"][0].macro == "LED_RED"

    assert expand_instance_plans([LED], None, "stm32", None) == {"led": ()}

    dht = ModuleManifest(slug="dht11", description="DHT11 温湿度传感器驱动")
    assert expand_instance_plans([LED, dht], None, "stm32", None) == {"led": ()}

    plans = expand_instance_plans(
        [LED],
        {"other": (ModuleInstance(name="x"),)},
        "stm32",
        BOARDS["stm32"],
    )
    assert plans == {"led": ()}


# --------------------------- generate() 集成（写侧） ---------------------------


def test_generate_stm32_single_led_no_write_side_changes(tmp_path):
    """stm32 单实例：led_instances.h = 母版默认（逐字节）、pin_config.h 逐字节
    不写——单实例路径零写侧变化。"""
    master = _fake_stm32_led_master(tmp_path)
    output = tmp_path / "out"

    generate(
        platform="stm32",
        manifests=[LED],
        module_library_dir=MODULES,
        master_project_dir=master,
        output_dir=output,
        main_c_content=LED_MAIN_C,
    )

    assert (output / "led_instances.h").read_text(
        encoding="utf-8", errors="replace"
    ) == FAKE_DEFAULT_LED_INSTANCES
    assert (output / "pin_config.h").read_text(
        encoding="utf-8", errors="replace"
    ) == FAKE_PIN_CONFIG
    assert (output / "main.c").read_text(encoding="utf-8", errors="replace") == LED_MAIN_C


def test_generate_stm32_multi_led_writes_channels_and_keeps_pin_config(tmp_path):
    """stm32 多实例：工程根 led_instances.h 含 4 通道宏 + 具体引脚对；
    pin_config.h 仍逐字节不写（实例接线单源在 led_instances.h）。"""
    master = _fake_stm32_led_master(tmp_path)
    output = tmp_path / "out"

    generate(
        platform="stm32",
        manifests=[LED],
        module_library_dir=MODULES,
        master_project_dir=master,
        output_dir=output,
        main_c_content=LED_MAIN_C,
        instances=INSTANCES_4,
    )

    text = (output / "led_instances.h").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "#define LED_CHANNEL_COUNT 4" in text
    assert "#define LED_1" in text
    assert "#define LED_CHANNEL_3_PORT GPIO_A" in text
    assert (output / "pin_config.h").read_text(
        encoding="utf-8", errors="replace"
    ) == FAKE_PIN_CONFIG


def test_generate_mspm0_single_led_default_header_and_no_syscfg_write(tmp_path):
    """mspm0 单实例：modules/led/code/led_instances.h = 库内默认（逐字节，
    复制即就位）；syscfg 逐字节不写（LED_BEEP 不动，绑定机制照旧）。"""
    master = _fake_mspm0_led_master(tmp_path)
    output = tmp_path / "out"

    generate(
        platform="mspm0",
        manifests=[LED],
        module_library_dir=MODULES,
        master_project_dir=master,
        output_dir=output,
        main_c_content=LED_MAIN_C,
    )

    header = output / "modules" / "led" / "code" / "led_instances.h"
    assert header.read_text(encoding="utf-8", errors="replace") == (
        MODULES / "led" / "code" / "led_instances.h"
    ).read_text(encoding="utf-8", errors="replace")
    assert (output / "mspm0.syscfg").read_text(
        encoding="utf-8", newline=""
    ) == FAKE_SYSCFG


def test_generate_mspm0_multi_led_appends_syscfg_instances(tmp_path):
    """mspm0 多实例（红/黄/绿 → PA15/PA0/PA1）：syscfg 追加 LED_2/LED_3 实例
    （通道 0 的 LED_BEEP 现值不变不写）；led_instances.h 引用新实例宏。"""
    master = _fake_mspm0_led_master(tmp_path)
    output = tmp_path / "out"

    generate(
        platform="mspm0",
        manifests=[LED],
        module_library_dir=MODULES,
        master_project_dir=master,
        output_dir=output,
        main_c_content=LED_MAIN_C,
        instances={
            "led": (
                ModuleInstance(name="红灯", variant="red"),
                ModuleInstance(name="黄灯", variant="yellow"),
                ModuleInstance(name="绿灯", variant="green"),
            )
        },
    )

    syscfg = (output / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert 'LED_BEEP.associatedPins[0].pin.$assign  = "PA15";' in syscfg
    assert "const LED_2 = GPIO.addInstance();" in syscfg
    assert 'LED_2.associatedPins[0].pin.$assign  = "PA0";' in syscfg
    assert "const LED_3 = GPIO.addInstance();" in syscfg
    assert 'LED_3.associatedPins[0].pin.$assign  = "PA1";' in syscfg

    header = (output / "modules" / "led" / "code" / "led_instances.h").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "#define LED_CHANNEL_COUNT 3" in header
    assert "#define LED_CHANNEL_1_PORT LED_2_PORT" in header
    assert "#define LED_CHANNEL_1_PIN  LED_2_LED2_PIN" in header


def test_generate_mspm0_without_led_no_header(tmp_path):
    """未选 led：mspm0 产物树里没有任何 led_instances.h（渲染只为选中模块）。"""
    master = _fake_mspm0_led_master(tmp_path)
    output = tmp_path / "out"

    generate(
        platform="mspm0",
        manifests=[],
        module_library_dir=MODULES,
        master_project_dir=master,
        output_dir=output,
        main_c_content="int main(void) { while (1); }\n",
    )

    assert not (output / "modules" / "led").exists()


# --------------------------- 骨架 / 冒烟注入 ---------------------------


def test_build_skeleton_interfaces_injects_led_channel_macros():
    """build_skeleton_interfaces 把 led_instances.h 的通道宏清单喂给 LLM：
    空计划 = 默认三通道（stm32）/ 单通道（mspm0），多实例计划 = 含 LED_1。"""
    interfaces = build_skeleton_interfaces(
        [LED], "stm32", MODULES, instance_plans={"led": ()}
    )
    channel_blocks = [b for b in interfaces if "led_instances.h" in b]
    assert len(channel_blocks) == 1
    block = channel_blocks[0]
    assert "#define LED_CHANNEL_COUNT 3" in block
    assert "#define LED_RED" in block and "#define LED_YELLOW" in block
    assert "led_init(" in block  # 使用提示

    interfaces = build_skeleton_interfaces(
        [LED],
        "mspm0",
        MODULES,
        instance_plans={"led": _plan(INSTANCES_4["led"], "mspm0")},
    )
    block = next(b for b in interfaces if "#define LED_CHANNEL_COUNT" in b)
    assert "#define LED_CHANNEL_COUNT 4" in block
    assert "#define LED_1" in block


def test_generate_skeleton_with_instances_feeds_channel_macros_to_llm():
    """generate_skeleton 带 instances → LLM 收到的接口块含展开后的通道宏
    （LED_1 等），冒烟/骨架两条路径同缝。"""
    llm = FakeLLM()
    generate_skeleton(
        llm, "题面", [LED], "stm32", MODULES, instances=INSTANCES_4
    )
    _problem_text, interfaces = llm.skeleton_calls[0]
    assert any("#define LED_1" in block for block in interfaces)


def test_generate_smoke_main_led_init_calls_not_placeholder_rewritten():
    """冒烟 main.c 逐个 led_init(<通道宏>)（含 LED_1）静态自检不误占位：
    led_init 在 led.h 接口中，intercepted 为空、原文保留。"""
    llm = FakeLLM(
        smoke_skeleton=(
            "int main(void) { led_init(LED_RED); led_init(LED_1); while (1); }\n"
        )
    )
    main_c, intercepted = generate_smoke_main(
        llm, "题面", [LED], "mspm0", MODULES, instances=INSTANCES_4
    )

    assert intercepted == ()
    assert "led_init(LED_RED);" in main_c
    assert "led_init(LED_1);" in main_c
