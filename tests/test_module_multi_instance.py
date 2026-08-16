"""module-multi-instance/01：manifest 多实例能力声明 + 实例数据形状（兼容解析）。

只测 01 的边界：manifest 的 multi_instance 块（解析 / 序列化 / 旧 manifest
兼容）、selection 的 ModuleInstance 模型与 instances 透传。展开 / 默认脚
分配（02）、渲染（03）、前端（04）、推荐 prompt（06）不在此文件。

真实库不变量（led 加 multi_instance 声明后）与旧单实例相关测试
（test_module_led_beep / test_pin_bindings 等）逐字节不破。
"""

from pathlib import Path

import pytest

from contest_generator.library import list_modules
from contest_generator.manifest import (
    ManifestError,
    ModuleManifest,
    MultiInstanceSpec,
)
from contest_generator.selection import (
    ModuleInstance,
    ModuleSelection,
    resolve_selection,
)

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"


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
