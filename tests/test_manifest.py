"""manifest 数据模型：解析 / 序列化 / 校验。"""

import json

import pytest

from contest_generator.manifest import (
    MANIFEST_FILENAME,
    ManifestError,
    ModuleManifest,
    PlatformEntry,
    collect_kits,
)


def test_serialize_parse_roundtrip_preserves_all_fields():
    manifest = ModuleManifest(
        slug="dht11",
        description="DHT11 温湿度传感器驱动",
        dependencies=("delay", "gpio"),
        platforms={
            "stm32": PlatformEntry(
                files=("stm32/src/dht11.c", "inc/dht11.h"),
                verified=True,
                hardware_bound=False,
                notes="F103C8T6 PA0",
                kit="STM32F103C8T6 最小系统板",
                source_url="https://item.jd.com/1000123456.html",
            ),
            "mspm0": PlatformEntry(
                files=("mspm0/src/dht11.c", "inc/dht11.h"),
                verified=False,
            ),
        },
    )

    parsed = ModuleManifest.from_dict(manifest.to_dict())

    assert parsed == manifest
    assert parsed.platforms["stm32"].kit == "STM32F103C8T6 最小系统板"
    assert parsed.platforms["stm32"].source_url == "https://item.jd.com/1000123456.html"


def test_load_from_module_directory(tmp_path):
    module_dir = tmp_path / "oled"
    module_dir.mkdir()
    (module_dir / MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "slug": "oled",
                "description": "OLED 屏显驱动",
                "platforms": {
                    "stm32": {
                        "files": ["stm32/src/oled.c", "inc/oled.h"],
                        "verified": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = ModuleManifest.load(module_dir)

    assert manifest.slug == "oled"
    assert manifest.description == "OLED 屏显驱动"
    assert manifest.platforms["stm32"].verified is True


def test_load_rejects_slug_mismatching_directory_name(tmp_path):
    module_dir = tmp_path / "dht11"
    module_dir.mkdir()
    (module_dir / MANIFEST_FILENAME).write_text(
        json.dumps({"slug": "other", "description": "x", "platforms": {}}),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="other"):
        ModuleManifest.load(module_dir)


@pytest.mark.parametrize(
    ("missing", "patch"),
    [
        ("slug", lambda d: d.pop("slug")),
        ("description", lambda d: d.pop("description")),
        ("platforms", lambda d: d.pop("platforms")),
    ],
)
def test_missing_required_field_rejected(missing, patch):
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {
            "stm32": {"files": ["src/dht11.c"], "verified": True},
        },
    }
    patch(data)

    with pytest.raises(ManifestError, match=missing):
        ModuleManifest.from_dict(data)


def test_platform_entry_without_files_rejected():
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {"stm32": {"verified": True}},
    }

    with pytest.raises(ManifestError, match="files"):
        ModuleManifest.from_dict(data)


def test_platform_entry_with_empty_file_list_rejected():
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {"stm32": {"files": []}},
    }

    with pytest.raises(ManifestError, match="files"):
        ModuleManifest.from_dict(data)


def test_duplicate_file_within_one_platform_entry_rejected():
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {
            "stm32": {"files": ["src/dht11.c", "src/dht11.c"], "verified": True}
        },
    }

    with pytest.raises(ManifestError, match="src/dht11.c"):
        ModuleManifest.from_dict(data)


@pytest.mark.parametrize(
    "bad_path",
    ["/abs/path.c", "..\\escape.c", "../up.c", ""],
)
def test_platform_entry_file_paths_must_be_relative_and_sane(bad_path):
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {"stm32": {"files": [bad_path], "verified": True}},
    }

    with pytest.raises(ManifestError):
        ModuleManifest.from_dict(data)


def test_invalid_json_rejected_with_manifest_error(tmp_path):
    module_dir = tmp_path / "broken"
    module_dir.mkdir()
    (module_dir / MANIFEST_FILENAME).write_text("{not json", encoding="utf-8")

    with pytest.raises(ManifestError):
        ModuleManifest.load(module_dir)


@pytest.mark.parametrize("bad_value", ["false", "0", 1, 0, None])
def test_platform_entry_flags_must_be_real_bools(bad_value):
    """宽松强转会让 'false' 变 True，静默翻转验证状态。"""
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {
            "stm32": {"files": ["src/dht11.c"], "verified": bad_value}
        },
    }

    with pytest.raises(ManifestError, match="verified"):
        ModuleManifest.from_dict(data)


def test_platform_entry_hardware_bound_must_be_real_bool():
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {
            "stm32": {"files": ["src/dht11.c"], "hardware_bound": "true"}
        },
    }

    with pytest.raises(ManifestError, match="hardware_bound"):
        ModuleManifest.from_dict(data)


def test_platform_entry_notes_must_be_string():
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {"stm32": {"files": ["src/dht11.c"], "notes": 123}},
    }

    with pytest.raises(ManifestError, match="notes"):
        ModuleManifest.from_dict(data)


def test_legacy_entry_without_identity_fields_loads_with_defaults():
    """存量 manifest 无 kit / source_url 字段仍能加载（迁移不打断现有库）。"""
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {
            "stm32": {"files": ["src/dht11.c"], "verified": True},
        },
    }

    manifest = ModuleManifest.from_dict(data)

    entry = manifest.platforms["stm32"]
    assert entry.kit == ""
    assert entry.source_url == ""
    # 序列化后新字段也回写（空值），列表 API 形态统一
    assert manifest.to_dict()["platforms"]["stm32"]["kit"] == ""
    assert manifest.to_dict()["platforms"]["stm32"]["source_url"] == ""


@pytest.mark.parametrize(
    "key", ["kit", "source_url"],
)
def test_identity_fields_must_be_strings(key):
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {
            "stm32": {"files": ["src/dht11.c"], key: 123},
        },
    }

    with pytest.raises(ManifestError, match=key):
        ModuleManifest.from_dict(data)


def test_same_file_shared_across_platforms_is_allowed():
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {
            "stm32": {"files": ["inc/dht11.h"], "verified": True},
            "mspm0": {"files": ["inc/dht11.h"], "verified": False},
        },
    }

    manifest = ModuleManifest.from_dict(data)

    assert manifest.platforms["mspm0"].files == ("inc/dht11.h",)


def _manifest_with_kits(slug: str, kits: list[str]) -> ModuleManifest:
    """带 kit 的平台条目构造（词表顺序测试用）。"""
    return ModuleManifest(
        slug=slug,
        description=f"{slug} 驱动",
        platforms={
            f"platform-{index}": PlatformEntry(files=("src.c",), kit=kit)
            for index, kit in enumerate(kits)
            if kit
        },
    )


def test_collect_kits_order_dedup_skips_empty():
    """kit 词表单源（工单 C3）：保序去重、空值跳过——顺序 = manifests 顺序
    × 平台条目插入顺序 × 首次出现（三处调用方共享同一语义）。"""
    manifests = [
        _manifest_with_kits("a", ["K1", "", "K2", "K1"]),
        _manifest_with_kits("b", ["K2", "K3"]),
        _manifest_with_kits("c", []),
    ]

    assert collect_kits(manifests) == ["K1", "K2", "K3"]


def test_build_manifest_summaries_projection_lives_in_manifest():
    """投影唯一出处 = manifest.py：llm 模块不再定义 build_manifest_summaries
    （工单 03：生成核心运行时不再拉 LLM 栈——批量投影归 manifest 紧邻
    from_manifest，llm 只剩协议与解析）。"""
    import contest_generator.llm as llm
    import contest_generator.manifest as manifest

    assert hasattr(manifest, "build_manifest_summaries")
    assert not hasattr(llm, "build_manifest_summaries")
