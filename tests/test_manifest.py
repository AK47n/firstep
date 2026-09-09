"""manifest 数据模型：解析 / 序列化 / 校验。"""

import json
from pathlib import Path

import pytest

from contest_generator.budget import MODULE_SUMMARY_BYTES, wire_size
from contest_generator.library import list_modules
from contest_generator.selection import filter_manifests_by_platform
from contest_generator.manifest import (
    LEAN_SUMMARY_SENTENCE_CHARS,
    MANIFEST_FILENAME,
    ManifestError,
    ManifestSummary,
    ModuleManifest,
    PlatformEntry,
    PythonArtifactSpec,
    PythonArtifactTemplate,
    build_manifest_summaries,
    collect_exclusive_groups,
    collect_kits,
)

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"


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


def test_platform_entry_with_empty_file_list_is_embedded_in_master():
    """空 files 平台条目 = 实现内嵌母版（随母版进工程，不复制不注册）；
    无 files 数组的平台条目仍报错（平台条目本身必填）。"""
    data = {
        "slug": "oled",
        "description": "OLED 屏显驱动",
        "platforms": {"stm32": {"files": [], "verified": True}},
    }

    manifest = ModuleManifest.from_dict(data)

    assert manifest.platforms["stm32"].files == ()
    assert manifest.platforms["stm32"].verified is True


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


# ---------------------------------------------------------------------------
# k230-vision-copilot/01：python_artifact 能力块解析 / 序列化 / 旧 manifest 兼容
# ---------------------------------------------------------------------------


def test_legacy_manifest_without_python_artifact_loads_none():
    """旧 manifest 缺 python_artifact → None（向后兼容，无副产物照旧）。"""
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {"stm32": {"files": ["src/dht11.c"], "verified": True}},
    }

    manifest = ModuleManifest.from_dict(data)

    assert manifest.python_artifact is None


def test_legacy_manifest_serializes_without_python_artifact_field():
    """旧 manifest 序列化不引入 python_artifact 键（与基线逐字节一致——写回
    save_manifest 时不会给存量 manifest 平白加一个 null 字段）。"""
    data = {
        "slug": "dht11",
        "description": "DHT11 温湿度传感器驱动",
        "platforms": {"stm32": {"files": ["src/dht11.c"], "verified": True}},
    }

    manifest = ModuleManifest.from_dict(data)

    assert "python_artifact" not in manifest.to_dict()


def test_python_artifact_roundtrip_preserves_spec():
    """python_artifact 往返稳定：to_dict → from_dict 无损（旧单模板形状）。"""
    manifest = ModuleManifest(
        slug="k230",
        description="K230 视觉副控",
        python_artifact=PythonArtifactSpec(
            templates=(
                PythonArtifactTemplate(
                    id="default", name="", description="",
                    template="code/k230_main.py", output="main.py",
                ),
            ),
            default_id="default",
        ),
    )

    parsed = ModuleManifest.from_dict(manifest.to_dict())

    assert parsed == manifest
    assert parsed.python_artifact == PythonArtifactSpec(
        templates=(
            PythonArtifactTemplate(
                id="default", name="", description="",
                template="code/k230_main.py", output="main.py",
            ),
        ),
        default_id="default",
    )
    # 单模板序列化回旧形状（存量 manifest 逐字节兼容）
    assert manifest.to_dict()["python_artifact"] == {
        "template": "code/k230_main.py",
        "output": "main.py",
    }


def test_python_artifact_null_loads_none():
    """python_artifact 显式 null 与缺省同义（None = 无副产物），且序列化不落键。"""
    data = {
        "slug": "k230",
        "description": "K230 视觉副控",
        "python_artifact": None,
        "platforms": {"stm32": {"files": [], "verified": True}},
    }

    manifest = ModuleManifest.from_dict(data)
    assert manifest.python_artifact is None
    assert "python_artifact" not in manifest.to_dict()


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        ({"template": "code/k230_main.py"}, "output"),  # 缺 output
        ({"output": "main.py"}, "template"),  # 缺 template
        ({"template": "", "output": "main.py"}, "template"),  # 空 template
        ({"template": "code/k230_main.py", "output": ""}, "output"),  # 空 output
        ({"template": 123, "output": "main.py"}, "template"),  # 非字符串 template
        ({"template": "code/k230_main.py", "output": 123}, "output"),  # 非字符串 output
        ({"template": "/abs/k230_main.py", "output": "main.py"}, "template"),  # 绝对路径
        ({"template": "../up.py", "output": "main.py"}, "template"),  # .. 逃逸
        ({"template": "..\\escape.py", "output": "main.py"}, "template"),  # 反斜杠逃逸
        ({"template": "a//b.py", "output": "main.py"}, "template"),  # 空段
        ({"template": ".", "output": "main.py"}, "template"),  # 目录自身（非文件）
        ({"template": "code/k230_main.py", "output": "../main.py"}, "output"),  # output 逃逸
        ({"template": "code/k230_main.py", "output": "sub/main.py"}, "output"),  # output 含目录
        ({"template": "code/k230_main.py", "output": "."}, "output"),  # output 目录自身
    ],
)
def test_python_artifact_rejects_invalid_values(bad, match):
    """python_artifact 存在则严格校验，错值大声失败（照 multi_instance 先例，
    不静默强转）；match 精确到报错字段（template / output），不满足于任意
    ManifestError。"""
    data = {
        "slug": "k230",
        "description": "K230 视觉副控",
        "python_artifact": bad,
        "platforms": {"stm32": {"files": [], "verified": True}},
    }

    with pytest.raises(ManifestError, match=match):
        ModuleManifest.from_dict(data)


def test_python_artifact_must_be_object():
    """python_artifact 非对象（如字符串）大声失败。"""
    data = {
        "slug": "k230",
        "description": "K230 视觉副控",
        "python_artifact": "main.py",
        "platforms": {"stm32": {"files": [], "verified": True}},
    }

    with pytest.raises(ManifestError, match="python_artifact"):
        ModuleManifest.from_dict(data)


# ---------------------------------------------------------------------------
# k230-multi-template/01：python_artifact 多模板形状（旧形状兼容 + 新形状校验）
# ---------------------------------------------------------------------------

_MULTI_TEMPLATE_BLOCK = {
    "default": "blob",
    "templates": [
        {
            "id": "blob",
            "name": "色块追踪",
            "description": "find_blobs 色块追踪，输出 B 帧",
            "template": "code/main.py",
            "output": "main.py",
        },
        {
            "id": "rect",
            "name": "矩形识别",
            "description": "find_rects 矩形定位，输出 B 帧",
            "template": "code/main_rect.py",
            "output": "main.py",
        },
    ],
}


def _multi_manifest() -> ModuleManifest:
    return ModuleManifest.from_dict(
        {
            "slug": "k230",
            "description": "K230 视觉副控",
            "python_artifact": _MULTI_TEMPLATE_BLOCK,
            "platforms": {"stm32": {"files": [], "verified": True}},
        }
    )


def test_python_artifact_multi_template_parses():
    manifest = _multi_manifest()
    assert manifest.python_artifact is not None
    assert [t.id for t in manifest.python_artifact.templates] == ["blob", "rect"]
    assert manifest.python_artifact.default_id == "blob"
    assert manifest.python_artifact.default_template.id == "blob"
    # 旧消费方 property = default 模板
    assert manifest.python_artifact.template == "code/main.py"
    assert manifest.python_artifact.output == "main.py"


def test_python_artifact_multi_template_roundtrip():
    manifest = _multi_manifest()
    parsed = ModuleManifest.from_dict(manifest.to_dict())
    assert parsed == manifest
    # 多模板序列化 = 新形状（含 default）
    assert manifest.to_dict()["python_artifact"] == _MULTI_TEMPLATE_BLOCK


def test_python_artifact_multi_template_rejects_duplicate_ids():
    block = {
        "default": "a",
        "templates": [
            {"id": "a", "template": "code/a.py", "output": "a.py"},
            {"id": "a", "template": "code/b.py", "output": "b.py"},
        ],
    }
    with pytest.raises(ManifestError, match="id 重复"):
        ModuleManifest.from_dict(
            {
                "slug": "k230",
                "description": "K230 视觉副控",
                "python_artifact": block,
                "platforms": {"stm32": {"files": [], "verified": True}},
            }
        )


def test_python_artifact_multi_template_rejects_missing_default():
    block = {
        "templates": [
            {"id": "a", "template": "code/a.py", "output": "a.py"},
        ],
    }
    with pytest.raises(ManifestError, match="default"):
        ModuleManifest.from_dict(
            {
                "slug": "k230",
                "description": "K230 视觉副控",
                "python_artifact": block,
                "platforms": {"stm32": {"files": [], "verified": True}},
            }
        )


def test_python_artifact_multi_template_rejects_default_not_in_list():
    block = {
        "default": "nope",
        "templates": [
            {"id": "a", "template": "code/a.py", "output": "a.py"},
        ],
    }
    with pytest.raises(ManifestError, match="不在模板 id 列表"):
        ModuleManifest.from_dict(
            {
                "slug": "k230",
                "description": "K230 视觉副控",
                "python_artifact": block,
                "platforms": {"stm32": {"files": [], "verified": True}},
            }
        )


def test_python_artifact_rejects_legacy_and_new_shape_mixed():
    """旧形状（template/output）与新形状（templates/default）并存 = 大声失败。

    在途盘点补口（2026-09-09）：并存时旧键被静默忽略，录入者以为的单模板
    会被多模板覆盖——宁可拒收，不静默丢字段。
    """
    for legacy_key in ("template", "output"):
        block = {
            "default": "a",
            "templates": [{"id": "a", "template": "code/a.py", "output": "a.py"}],
            legacy_key: "code/legacy.py" if legacy_key == "template" else "legacy.py",
        }
        with pytest.raises(ManifestError, match="不能同时使用旧形状"):
            ModuleManifest.from_dict(
                {
                    "slug": "k230",
                    "description": "K230 视觉副控",
                    "python_artifact": block,
                    "platforms": {"stm32": {"files": [], "verified": True}},
                }
            )


def test_python_artifact_multi_template_rejects_empty_list():
    block = {"default": "a", "templates": []}
    with pytest.raises(ManifestError, match="非空数组"):
        ModuleManifest.from_dict(
            {
                "slug": "k230",
                "description": "K230 视觉副控",
                "python_artifact": block,
                "platforms": {"stm32": {"files": [], "verified": True}},
            }
        )


def test_python_artifact_multi_template_item_path_validation():
    """模板条目内的 template/output 沿用旧口径（相对路径 / 纯文件名）。"""
    block = {
        "default": "a",
        "templates": [
            {"id": "a", "template": "../up.py", "output": "main.py"},
        ],
    }
    with pytest.raises(ManifestError, match="相对且无"):
        ModuleManifest.from_dict(
            {
                "slug": "k230",
                "description": "K230 视觉副控",
                "python_artifact": block,
                "platforms": {"stm32": {"files": [], "verified": True}},
            }
        )


def test_manifest_summary_annotates_multi_template():
    """ManifestSummary.to_line 有多个模板时展示模板清单（能力证据，AI 可选）。"""
    summary = ManifestSummary.from_manifest(_multi_manifest())
    line = summary.to_line()
    assert "副产物模板可选" in line
    assert "色块追踪" in line and "矩形识别" in line
    assert "默认 = blob" in line
    # 单模板模块（存量 k230 形状）无标注（旧行格式逐字不变）
    legacy = ModuleManifest.from_dict(
        {
            "slug": "k230",
            "description": "K230 视觉副控",
            "python_artifact": {"template": "code/main.py", "output": "main.py"},
            "platforms": {"stm32": {"files": [], "verified": True}},
        }
    )
    assert "副产物模板可选" not in ManifestSummary.from_manifest(legacy).to_line()


# ---------------------------------------------------------------------------
# 功能组互斥声明（工单 recommend-exclusive-groups/01）
# ---------------------------------------------------------------------------


def _group_manifest(
    slug: str, group_block: dict | None, platforms: dict | None = None
) -> ModuleManifest:
    """构造带（或不带）exclusive_group 声明的 manifest。"""
    data: dict = {
        "slug": slug,
        "description": f"{slug} 描述",
        "platforms": platforms
        or {"mspm0": {"files": [f"code/{slug}.c"], "verified": True}},
    }
    if group_block is not None:
        data["exclusive_group"] = group_block
    return ModuleManifest.from_dict(data)


_GROUP_BLOCK = {
    "id": "gray-track",
    "label": "8 路灰度传感器驱动",
    "role": "灰度读取 + 加权质心巡线（开环，真机控制代码移植）",
}


def test_exclusive_group_parse_and_roundtrip():
    manifest = _group_manifest("xunji", _GROUP_BLOCK)
    assert manifest.exclusive_group is not None
    assert manifest.exclusive_group.id == "gray-track"
    assert manifest.exclusive_group.label == "8 路灰度传感器驱动"
    assert manifest.exclusive_group.role == _GROUP_BLOCK["role"]
    parsed = ModuleManifest.from_dict(manifest.to_dict())
    assert parsed == manifest


def test_exclusive_group_missing_absent_omitted_in_to_dict():
    """缺省 = 不属任何组；to_dict 不落键（旧 manifest 序列化逐字节一致）。"""
    manifest = _group_manifest("huidu", None)
    assert manifest.exclusive_group is None
    assert "exclusive_group" not in manifest.to_dict()


def test_exclusive_group_rejects_wrong_type():
    with pytest.raises(ManifestError, match="exclusive_group"):
        ModuleManifest.from_dict(
            {
                "slug": "pid",
                "description": "pid 描述",
                "exclusive_group": "gray-track",
                "platforms": {"mspm0": {"files": ["code/pid.c"], "verified": True}},
            }
        )


def test_exclusive_group_rejects_missing_or_empty_fields():
    for bad, match in [
        ({"label": "x", "role": "y"}, "id"),
        ({"id": "g", "role": "y"}, "label"),
        ({"id": "g", "label": "x"}, "role"),
        ({"id": "", "label": "x", "role": "y"}, "id"),
        ({"id": "g", "label": "", "role": "y"}, "label"),
        ({"id": "g", "label": "x", "role": ""}, "role"),
        ({"id": "g", "label": "x", "role": 1}, "role"),
    ]:
        with pytest.raises(ManifestError, match=match):
            _group_manifest("pid", dict(bad))


def test_summary_to_line_annotates_exclusive_group():
    """摘要行带「同组互斥」标注（进推荐提示词与缓存指纹）。"""
    summary = ManifestSummary.from_manifest(_group_manifest("xunji", _GROUP_BLOCK))
    line = summary.to_line()
    assert "同组互斥" in line
    assert "8 路灰度传感器驱动" in line
    assert "组内仅选其一" in line
    # 无组声明 = 旧行格式逐字不变（无标注）
    plain = ManifestSummary.from_manifest(_group_manifest("huidu", None))
    assert "同组互斥" not in plain.to_line()


# ---------------------------------------------------------------------------
# 摘要行瘦身形态（工单 preselect-visibility/01）：喂模型的清单行只留
# 「slug + 有界首句 + 依赖 + 多实例 + 副产物/互斥标记」，套件段与采购链接不进
# 一级行——全库可装进预筛预算，截断消失。
# ---------------------------------------------------------------------------


def test_lean_summary_line_keeps_first_sentence_and_drops_kit():
    """瘦身行 = slug + 首句 + 依赖段；套件段（含采购链接）不进一级行。

    首句只在「。」「；」切——`motor` 的「：」后才是能力句，切了就等于没写。
    """
    manifest = ModuleManifest.from_dict(
        {
            "slug": "motor",
            "description": (
                "TB6612 双路直流电机驱动（双平台统一 API）：motor_set_duty 调速"
                " + motor_set_direction 方向。适用于小车类赛题。"
            ),
            "dependencies": ["config"],
            "platforms": {
                "stm32": {
                    "files": ["code/motor.c"],
                    "verified": True,
                    "kit": "TB6612FNG 电机驱动模块（页面采购链接：淘宝 id=616285586821）",
                }
            },
        }
    )
    line = ManifestSummary.from_manifest(manifest).lean_copy().to_line()

    assert "motor_set_duty 调速" in line, f"「：」后的能力句被切掉了：{line}"
    assert "适用于小车类赛题" not in line, f"第二句应被切掉：{line}"
    assert "TB6612FNG" not in line and "采购链接" not in line, f"套件段不应出现：{line}"
    assert "（依赖: config）" in line, f"依赖段必须保留：{line}"
    assert line.startswith("- motor: "), f"行首形态错：{line}"


def test_lean_summary_line_caps_long_first_sentence():
    """首句超上限时硬截断到 100 字符（行长度可断言上界，库再长也不失控）。"""
    manifest = ModuleManifest.from_dict(
        {
            "slug": "long_mod",
            "description": "能" * 300,
            "platforms": {"stm32": {"files": ["code/long.c"], "verified": True}},
        }
    )
    line = ManifestSummary.from_manifest(manifest).lean_copy().to_line()

    assert line == "- long_mod: " + "能" * LEAN_SUMMARY_SENTENCE_CHARS, (
        f"未按 {LEAN_SUMMARY_SENTENCE_CHARS} 字符截断：{len(line)}"
    )


def test_lean_summary_line_keeps_decision_markers():
    """依赖 / 多实例 / 副产物模板 / 互斥组四段决策信息必须保留（选模块后配
    实例与模板选择靠它们）。"""
    manifest = ModuleManifest.from_dict(
        {
            "slug": "led",
            "description": "LED 指示灯驱动（双平台）。细节已封装在模块内。",
            "dependencies": ["config", "delay"],
            "multi_instance": {"max": 8, "variant": "color"},
            "python_artifact": {
                "default": "blob",
                "templates": [
                    {"id": "blob", "name": "色块追踪", "template": "a.py", "output": "main.py"},
                    {"id": "rect", "name": "矩形识别", "template": "b.py", "output": "main.py"},
                ],
            },
            "exclusive_group": {
                "id": "gray-track",
                "label": "8 路灰度传感器驱动",
                "role": "仅读取",
            },
            "platforms": {"stm32": {"files": ["code/led.c"], "verified": True}},
        }
    )
    line = ManifestSummary.from_manifest(manifest).lean_copy().to_line()

    assert "（依赖: config, delay）" in line
    assert "（多实例：上限 8，变体 = color）" in line
    assert "副产物模板可选：色块追踪、矩形识别，默认 = blob" in line
    assert "同组互斥：8 路灰度传感器驱动，组内仅选其一" in line
    assert "细节已封装在模块内" not in line, f"第二句应被切掉：{line}"


def test_lean_summary_line_breaks_at_earliest_sentence_mark():
    """「。」「；」谁先出现就在谁处切——不能按固定顺序只认「。」。

    真实库 84/93 条简介「；」先于「。」（如 adc：「…四通道；MEM0 与…」），
    按固定顺序切会得到 100 字符长串而非真正的首句。
    """
    manifest = ModuleManifest.from_dict(
        {
            "slug": "adc",
            "description": "ADC12 采集：四通道；MEM0 与 us016 共读同槽。第二句在此。",
            "platforms": {"stm32": {"files": ["code/adc.c"], "verified": True}},
        }
    )
    line = ManifestSummary.from_manifest(manifest).lean_copy().to_line()

    assert line == "- adc: ADC12 采集：四通道", f"未在最早的「；」处切分：{line}"


def test_lean_summary_lines_fit_preselect_budget_for_real_library():
    """真实库全库瘦身行装得进预筛预算（工单 01 的核心不变量）。

    实测依据：现状完整行 stm32 86598B / mspm0 78668B 远超预算，故预筛截断到
    33–41 条、关键模块不可见；瘦身行 28071B / 28062B 全库可装 → 截断消失
    （复测 .scratch/library-audit/probe_lean_variants.py，走生产实现）。
    余量断言 ≥5KB：库继续长大到临界（或首句上限被调大）时这里红，提醒重新
    记账而不是静默回退到截断。

    与 tests/test_llm.py::test_recommend_real_library_budget 同轴但不同层：
    那条守「完整 payload ≤ 网关预算」，这条守「摘要段本身装得下全库」——
    后者是前者的前提，也是本批验收口径。
    """
    modules = list_modules(LIBRARY_MODULES)
    assert modules, "真实模块库为空——测试语料路径错了"

    for platform in ("stm32", "mspm0"):
        summaries = build_manifest_summaries(
            filter_manifests_by_platform(modules, platform)
        )
        # join 分隔符 +1 与 selection._fit_summaries_by_wire 同口径（预筛实际
        # 计的就是这个数，不另立账法）
        total = sum(wire_size(s.lean_copy().to_line()) + 1 for s in summaries)
        assert total <= MODULE_SUMMARY_BYTES - 5 * 1024, (
            f"{platform} 全库瘦身行 {total}B 超出预筛预算 {MODULE_SUMMARY_BYTES}B "
            f"（余量须 ≥5KB，共 {len(summaries)} 条）"
        )


def test_collect_exclusive_groups_aggregates_members_in_order():
    manifests = [
        _group_manifest("huidu", {**_GROUP_BLOCK, "role": "仅读取"}),
        _group_manifest("pid", {**_GROUP_BLOCK, "role": "PID 巡线"}),
        _group_manifest("xunji", {**_GROUP_BLOCK, "role": "质心巡线"}),
    ]
    groups = collect_exclusive_groups(manifests)
    assert len(groups) == 1
    group = groups[0]
    assert group.id == "gray-track"
    assert group.label == "8 路灰度传感器驱动"
    assert [m.slug for m in group.members] == ["huidu", "pid", "xunji"]
    assert [m.role for m in group.members] == ["仅读取", "PID 巡线", "质心巡线"]


def test_collect_exclusive_groups_platform_filter_and_single_member_dropped():
    """平台过滤：成员 = 该平台有条目的模块；过滤后仅 1 成员的组 = 无意义组。"""
    mspm0_only = _group_manifest("xunji", _GROUP_BLOCK)
    both = _group_manifest(
        "pid",
        _GROUP_BLOCK,
        platforms={
            "mspm0": {"files": ["code/pid_mspm0.c"], "verified": True},
            "stm32": {"files": ["code/pid.c"], "verified": True},
        },
    )
    manifests = [mspm0_only, both]
    assert len(collect_exclusive_groups(manifests)) == 1
    mspm0_groups = collect_exclusive_groups(manifests, platform="mspm0")
    assert [m.slug for m in mspm0_groups[0].members] == ["xunji", "pid"]
    # stm32 只有 pid（xunji 无条目）→ 单成员组不出卡
    assert collect_exclusive_groups(manifests, platform="stm32") == []
    # 平台过滤不影响成员顺序（库登记顺序）
    assert [m.slug for m in collect_exclusive_groups(manifests)[0].members] == [
        "xunji",
        "pid",
    ]


def test_collect_exclusive_groups_rejects_label_mismatch():
    """同 id 的 label 逐字一致（不一致 = 库错误，大声失败）。"""
    a = _group_manifest("huidu", {**_GROUP_BLOCK, "label": "灰度驱动"})
    b = _group_manifest("pid", {**_GROUP_BLOCK, "label": "灰度巡线驱动"})
    with pytest.raises(ManifestError, match="label"):
        collect_exclusive_groups([a, b])


def test_collect_exclusive_groups_keeps_distinct_groups():
    manifests = [
        _group_manifest("xunji", _GROUP_BLOCK),
        _group_manifest(
            "imu_uart",
            {
                "id": "attitude-hold",
                "label": "航向保持 / 姿态传感器",
                "role": "UART 串口陀螺仪",
            },
        ),
        _group_manifest(
            "ml_mpu6050",
            {
                "id": "attitude-hold",
                "label": "航向保持 / 姿态传感器",
                "role": "I2C + DMP 解算",
            },
        ),
    ]
    groups = collect_exclusive_groups(manifests)
    assert [g.id for g in groups] == ["gray-track", "attitude-hold"]
    assert [g.label for g in groups] == ["8 路灰度传感器驱动", "航向保持 / 姿态传感器"]

