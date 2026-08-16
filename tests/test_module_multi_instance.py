"""module-multi-instance/01：manifest 多实例能力声明 + 实例数据形状（兼容解析）。

只测 01 的边界：manifest 的 multi_instance 块（解析 / 序列化 / 旧 manifest
兼容）、selection 的 ModuleInstance 模型与 instances 透传。展开 / 默认脚
分配（02）、渲染（03）、前端（04）、推荐 prompt（06）不在此文件。

真实库不变量（led 加 multi_instance 声明后）与旧单实例相关测试
（test_module_led_beep / test_pin_bindings 等）逐字节不破。
"""

from pathlib import Path

import pytest

from contest_generator.boards import BOARDS_DIR, load_boards
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

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
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
