"""manifest 数据模型：解析 / 序列化 / 校验。"""

import json

import pytest

from contest_generator.manifest import (
    MANIFEST_FILENAME,
    ManifestError,
    ManifestSummary,
    ModuleManifest,
    PlatformEntry,
    PythonArtifactSpec,
    PythonArtifactTemplate,
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
