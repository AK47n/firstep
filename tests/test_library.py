"""模块库管理核心：浏览 / 编辑 / 删除、AI 录入流程（草稿 + 一致性校验）、多平台版本。

用 conftest 的假模块库与假 LLM 驱动，断言磁盘库目录结构与 manifest 内容（外部行为）。
"""

import dataclasses
import json

import pytest

from contest_generator.library import (
    LibraryError,
    add_module,
    add_platform_files,
    delete_module,
    draft_description,
    get_module,
    list_modules,
    remove_platform_files,
    save_manifest,
    update_module_description,
    update_platform_identity,
    validate_description,
)
from contest_generator.llm import ValidationResult
from contest_generator.manifest import MANIFEST_FILENAME, ModuleManifest, PlatformEntry
from tests.fakes import FakeLLM

DHT11_FILES = {
    "inc/dht11.h": "#pragma once\nfloat dht11_read(void);\n",
    "stm32/src/dht11.c": "float dht11_read(void) { return 25.0; }\n",
}

# 硬件身份字段（工单 01）：新录入的平台条目必填
KIT_STM32 = "STM32F103C8T6 最小系统板"
SOURCE_URL_STM32 = "https://item.jd.com/1000123456.html"
SOURCE_URL_MSPM0 = "https://item.jd.com/6543210001.html"


def _add_bmp180(library, files: dict[str, str] | None = None) -> None:
    """在库中入库一个 bmp180 模块（stm32 版本，带硬件身份字段）。"""
    add_module(
        FakeLLM(),
        library,
        slug="bmp180",
        platform="stm32",
        description="BMP180 气压计驱动",
        files=files or {"bmp180.c": "int bmp180_read(void);\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )


# ---------------------------------------------------------------------------
# 浏览
# ---------------------------------------------------------------------------


def test_list_modules_returns_all_modules_sorted_by_slug(fake_module_library):
    manifests = list_modules(fake_module_library)

    assert [m.slug for m in manifests] == ["broken", "delay", "dht11", "oled"]


def test_list_modules_loads_manifest_fields(fake_module_library):
    dht11 = next(m for m in list_modules(fake_module_library) if m.slug == "dht11")

    assert dht11.description == "DHT11 温湿度传感器驱动"
    assert dht11.dependencies == ("delay",)
    assert dht11.platforms["stm32"].files == ("stm32/src/dht11.c", "inc/dht11.h")
    assert dht11.platforms["stm32"].verified is True


def test_list_modules_ignores_stray_files_at_library_root(fake_module_library):
    (fake_module_library / "README.md").write_text("说明", encoding="utf-8")

    assert {m.slug for m in list_modules(fake_module_library)} == {
        "broken",
        "delay",
        "dht11",
        "oled",
    }


def test_list_modules_rejects_corrupt_manifest(fake_module_library):
    (fake_module_library / "broken" / MANIFEST_FILENAME).write_text(
        "{not json", encoding="utf-8"
    )

    with pytest.raises(LibraryError, match="manifest"):
        list_modules(fake_module_library)


def test_get_module_returns_manifest(fake_module_library):
    assert get_module(fake_module_library, "dht11").slug == "dht11"


def test_get_module_missing_raises(fake_module_library):
    with pytest.raises(LibraryError, match="不存在"):
        get_module(fake_module_library, "wifi")


def test_get_module_rejects_path_traversal_slug(fake_module_library):
    with pytest.raises(LibraryError, match="slug"):
        get_module(fake_module_library, "../evil")


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------


def test_delete_module_removes_directory(fake_module_library):
    delete_module(fake_module_library, "oled")

    assert not (fake_module_library / "oled").exists()
    assert "oled" not in [m.slug for m in list_modules(fake_module_library)]


def test_delete_module_missing_raises(fake_module_library):
    with pytest.raises(LibraryError, match="不存在"):
        delete_module(fake_module_library, "wifi")


def test_delete_module_rejects_path_traversal_slug(tmp_path, fake_module_library):
    outside = tmp_path / "evil"
    outside.mkdir()

    with pytest.raises(LibraryError, match="slug"):
        delete_module(fake_module_library, "../evil")

    assert outside.exists()  # 库外目录未被删除


# ---------------------------------------------------------------------------
# 编辑（save_manifest 写回结构字段；简介编辑走 update_module_description）
# ---------------------------------------------------------------------------


def test_save_manifest_persists_edits(fake_module_library):
    edited = dataclasses.replace(
        get_module(fake_module_library, "dht11"), dependencies=("delay", "uart")
    )

    save_manifest(fake_module_library, edited)

    assert get_module(fake_module_library, "dht11").dependencies == ("delay", "uart")
    assert '"uart"' in (fake_module_library / "dht11" / MANIFEST_FILENAME).read_text(
        encoding="utf-8"
    )


def test_save_manifest_missing_module_raises(fake_module_library):
    ghost = ModuleManifest(slug="ghost", description="x")

    with pytest.raises(LibraryError, match="不存在"):
        save_manifest(fake_module_library, ghost)


def test_save_manifest_rejects_path_traversal_slug(fake_module_library):
    ghost = ModuleManifest(slug="../evil", description="x")

    with pytest.raises(LibraryError, match="slug"):
        save_manifest(fake_module_library, ghost)


def test_save_manifest_rejects_structural_errors(fake_module_library):
    bad = ModuleManifest(
        slug="dht11",
        description="x",
        platforms={"stm32": PlatformEntry(files=())},
    )

    with pytest.raises(LibraryError, match="不能为空"):
        save_manifest(fake_module_library, bad)


def test_update_module_description_persists_when_consistent(fake_module_library):
    llm = FakeLLM()

    manifest = update_module_description(llm, fake_module_library, "dht11", "新的简介")

    assert manifest.description == "新的简介"
    assert get_module(fake_module_library, "dht11").description == "新的简介"
    description, code = llm.validation_calls[0]
    assert description == "新的简介"
    # 校验视角 = 模块全部平台版本引用的文件
    assert "stm32/src/dht11.c" in code
    assert "mspm0/src/dht11.c" in code


def test_update_module_description_revalidates_edited_description(fake_module_library):
    llm = FakeLLM(
        validation=ValidationResult(consistent=False, issues="简介与代码不符")
    )

    with pytest.raises(LibraryError, match="不一致"):
        update_module_description(llm, fake_module_library, "dht11", "错误的新简介")

    # 校验未通过：磁盘上的简介保持原样
    assert (
        get_module(fake_module_library, "dht11").description
        == "DHT11 温湿度传感器驱动"
    )


def test_update_module_description_missing_module_raises(fake_module_library):
    with pytest.raises(LibraryError, match="不存在"):
        update_module_description(FakeLLM(), fake_module_library, "wifi", "x")


# ---------------------------------------------------------------------------
# AI 录入流程：草稿 + 一致性校验
# ---------------------------------------------------------------------------


def test_draft_description_asks_llm_with_assembled_code():
    llm = FakeLLM(summary="DHT11 温湿度传感器驱动，单总线")

    draft = draft_description(llm, DHT11_FILES)

    assert draft == "DHT11 温湿度传感器驱动，单总线"
    (code,) = llm.summary_calls[0]
    assert "inc/dht11.h" in code
    assert "stm32/src/dht11.c" in code
    assert "float dht11_read(void);" in code


def test_validate_description_returns_llm_verdict():
    llm = FakeLLM(
        validation=ValidationResult(consistent=False, issues="简介写 I2C，实际是单总线")
    )

    result = validate_description(llm, "支持 I2C", DHT11_FILES)

    assert result.consistent is False
    assert "单总线" in result.issues
    description, code = llm.validation_calls[0]
    assert description == "支持 I2C"
    assert "float dht11_read(void);" in code


def test_add_flow_validates_user_edited_description_after_draft(fake_module_library):
    """完整录入流程：AI 草稿 → 用户修改 → 入库前校验的是修改后的描述。"""
    llm = FakeLLM(summary="AI 草稿：DHT11 温湿度传感器驱动")
    draft = draft_description(llm, DHT11_FILES)
    edited = draft.replace("AI 草稿：", "")  # 用户修改草稿

    add_module(
        llm,
        fake_module_library,
        slug="bmp180",
        platform="stm32",
        description=edited,
        files=DHT11_FILES,
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    validated_description, _ = llm.validation_calls[0]
    assert validated_description == "DHT11 温湿度传感器驱动"


# ---------------------------------------------------------------------------
# 添加模块：校验通过才入库
# ---------------------------------------------------------------------------


def test_add_module_stores_module_with_consistent_description(fake_module_library):
    manifest = add_module(
        FakeLLM(),
        fake_module_library,
        slug="bmp180",
        platform="stm32",
        description="BMP180 气压计驱动",
        files=DHT11_FILES,
        verified=True,
        notes="PA0",
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    assert manifest.slug == "bmp180"
    entry = manifest.platforms["stm32"]
    assert entry.files == ("inc/dht11.h", "stm32/src/dht11.c")
    assert entry.verified is True
    assert entry.notes == "PA0"
    assert entry.kit == KIT_STM32
    assert entry.source_url == SOURCE_URL_STM32
    module_dir = fake_module_library / "bmp180"
    assert (module_dir / "inc" / "dht11.h").read_text(encoding="utf-8").startswith(
        "#pragma once"
    )
    assert (module_dir / "stm32" / "src" / "dht11.c").exists()
    on_disk = json.loads((module_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert on_disk["description"] == "BMP180 气压计驱动"
    assert on_disk["dependencies"] == []
    # 身份字段落盘包含新字段
    assert on_disk["platforms"]["stm32"]["kit"] == KIT_STM32
    assert on_disk["platforms"]["stm32"]["source_url"] == SOURCE_URL_STM32


def test_add_module_records_dependencies(fake_module_library):
    manifest = add_module(
        FakeLLM(),
        fake_module_library,
        slug="bmp180",
        platform="stm32",
        description="BMP180 气压计驱动",
        dependencies=("delay",),
        files={"bmp180.c": "int bmp180_read(void);\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    assert manifest.dependencies == ("delay",)
    assert get_module(fake_module_library, "bmp180").dependencies == ("delay",)


def test_add_module_inconsistent_validation_raises_and_leaves_no_trace(
    fake_module_library,
):
    llm = FakeLLM(
        validation=ValidationResult(consistent=False, issues="简介说支持 I2C，代码实际是单总线")
    )

    with pytest.raises(LibraryError, match="不一致"):
        add_module(
            llm,
            fake_module_library,
            slug="wifi",
            platform="stm32",
            description="WIFI 驱动",
            files={"wifi.c": "int wifi_init(void);\n"},
            kit=KIT_STM32,
            source_url=SOURCE_URL_STM32,
        )

    assert not (fake_module_library / "wifi").exists()
    assert llm.validation_calls  # 校验确实被调用后才拒绝


def test_add_module_rejects_specificity_claim_unsupported_by_code(
    fake_module_library,
):
    """专用性路径 1：简介声称"XX 题专用"但代码是通用驱动 → 校验拒绝，差异说明
    透传给出（AI 指出的具体差异进 LibraryError，用户据此修正）。"""
    llm = FakeLLM(
        validation=ValidationResult(
            consistent=False,
            issues="简介声称 2026C 题专用，但代码是通用 GPIO 驱动，无任何赛题逻辑",
        )
    )

    with pytest.raises(LibraryError, match="2026C 题专用.*通用 GPIO 驱动"):
        add_module(
            llm,
            fake_module_library,
            slug="lock",
            platform="stm32",
            description="2026C 数字钥匙题专用锁逻辑",
            files={"lock.c": "void lock_init(void);\n"},
            kit=KIT_STM32,
            source_url=SOURCE_URL_STM32,
        )

    assert not (fake_module_library / "lock").exists()
    description, code = llm.validation_calls[0]
    assert "2026C 数字钥匙题专用锁逻辑" in description  # 校验读的是用户提交的简介
    assert "void lock_init(void);" in code  # 与校验用同一份代码拼装


def test_add_module_rejects_specific_code_missing_annotation(fake_module_library):
    """专用性路径 2：代码明显是赛题专用逻辑但简介未标注 → 校验拒绝，issues 提示
    补充专用性标注（简介不完整同样是"与代码不一致"，拒绝入库直到补上标注）。"""
    llm = FakeLLM(
        validation=ValidationResult(
            consistent=False,
            issues="代码是 2026C 数字钥匙题的锁逻辑，简介未标注专用性，"
            "请在简介中补充'2026C 题专用'标注",
        )
    )

    with pytest.raises(LibraryError, match="补充.*2026C 题专用.*标注"):
        add_module(
            llm,
            fake_module_library,
            slug="lock",
            platform="stm32",
            description="通用锁逻辑",
            files={"lock.c": "/* 2026C 数字钥匙题判定 */\nvoid lock_init(void);\n"},
            kit=KIT_STM32,
            source_url=SOURCE_URL_STM32,
        )

    assert not (fake_module_library / "lock").exists()
    description, code = llm.validation_calls[0]
    assert description == "通用锁逻辑"
    assert "2026C 数字钥匙题判定" in code


def test_add_module_duplicate_slug_raises(fake_module_library):
    with pytest.raises(LibraryError, match="已存在"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="dht11",
            platform="stm32",
            description="x",
            files={"a.c": "int a(void);\n"},
        )


@pytest.mark.parametrize("bad_slug", ["", "a b", "a/b", "..", ".", "-abc", "a..b"])
def test_add_module_rejects_bad_slug(fake_module_library, bad_slug):
    with pytest.raises(LibraryError, match="slug"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug=bad_slug,
            platform="stm32",
            description="x",
            files={"a.c": "int a(void);\n"},
        )


@pytest.mark.parametrize("bad_file", ["../escape.c", "/abs.c", "a\\b.c", "sub/../up.c"])
def test_add_module_rejects_unsafe_file_path(fake_module_library, bad_file):
    with pytest.raises(LibraryError, match="相对"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="new",
            platform="stm32",
            description="x",
            files={bad_file: "int a(void);\n"},
        )


def test_add_module_rejects_non_source_extension(fake_module_library):
    with pytest.raises(LibraryError, match=".c/.h"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="new",
            platform="stm32",
            description="x",
            files={"notes.txt": "hi"},
        )


def test_add_module_rejects_manifest_filename(fake_module_library):
    with pytest.raises(LibraryError, match="manifest"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="new",
            platform="stm32",
            description="x",
            files={MANIFEST_FILENAME: "{}"},
        )


def test_add_module_rejects_empty_files(fake_module_library):
    with pytest.raises(LibraryError, match="至少"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="new",
            platform="stm32",
            description="x",
            files={},
        )


# ---------------------------------------------------------------------------
# 多平台版本：增删各平台版本文件与 manifest 条目
# ---------------------------------------------------------------------------


def test_add_platform_files_creates_new_platform_entry(fake_module_library):
    _add_bmp180(fake_module_library)

    manifest = add_platform_files(
        fake_module_library,
        "bmp180",
        "mspm0",
        {"mspm0/bmp180.c": "int bmp180_read(void);\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_MSPM0,
    )

    assert set(manifest.platforms) == {"stm32", "mspm0"}
    assert (fake_module_library / "bmp180" / "mspm0" / "bmp180.c").read_text(
        encoding="utf-8"
    ).startswith("int bmp180_read")
    # 新增平台条目带身份字段落盘
    assert manifest.platforms["mspm0"].kit == KIT_STM32
    assert manifest.platforms["mspm0"].source_url == SOURCE_URL_MSPM0
    # 既有平台条目原样保留
    assert manifest.platforms["stm32"].files == ("bmp180.c",)


def test_add_platform_files_appends_to_existing_entry(fake_module_library):
    _add_bmp180(fake_module_library)

    manifest = add_platform_files(
        fake_module_library, "bmp180", "stm32", {"bmp180.h": "#pragma once\n"}
    )

    assert manifest.platforms["stm32"].files == ("bmp180.c", "bmp180.h")


def test_add_platform_files_reuses_identical_shared_file(fake_module_library):
    header = "#pragma once\nint bmp180_read(void);\n"
    add_module(
        FakeLLM(),
        fake_module_library,
        slug="bmp180",
        platform="stm32",
        description="BMP180 气压计驱动",
        files={"inc/bmp180.h": header, "stm32/bmp180.c": "int bmp180_read(void) { return 0; }\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    manifest = add_platform_files(
        fake_module_library,
        "bmp180",
        "mspm0",
        {"inc/bmp180.h": header, "mspm0/bmp180.c": "int bmp180_read(void) { return 1; }\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_MSPM0,
    )

    # 双平台共用同一头文件：只写一份，两个条目都引用
    assert manifest.platforms["mspm0"].files == ("inc/bmp180.h", "mspm0/bmp180.c")
    assert (fake_module_library / "bmp180" / "inc" / "bmp180.h").read_text(
        encoding="utf-8"
    ) == header


def test_add_platform_files_rejects_conflicting_content_at_existing_path(
    fake_module_library,
):
    add_module(
        FakeLLM(),
        fake_module_library,
        slug="bmp180",
        platform="stm32",
        description="BMP180 气压计驱动",
        files={"inc/bmp180.h": "#pragma once\nint bmp180_read(void);\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    with pytest.raises(LibraryError, match="内容不一致"):
        add_platform_files(
            fake_module_library,
            "bmp180",
            "mspm0",
            {"inc/bmp180.h": "#pragma once\nfloat bmp180_read(void);\n"},
            kit=KIT_STM32,
            source_url=SOURCE_URL_MSPM0,
        )


def test_add_platform_files_conflict_leaves_no_orphan_files(fake_module_library):
    """写盘前预检：后一个文件冲突时，前一个文件不残留。"""
    add_module(
        FakeLLM(),
        fake_module_library,
        slug="bmp180",
        platform="stm32",
        description="BMP180 气压计驱动",
        files={"inc/bmp180.h": "#pragma once\nint bmp180_read(void);\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    with pytest.raises(LibraryError, match="内容不一致"):
        add_platform_files(
            fake_module_library,
            "bmp180",
            "mspm0",
            {
                "mspm0/bmp180.c": "int bmp180_read(void);\n",
                "inc/bmp180.h": "DIFFERENT CONTENT\n",
            },
            kit=KIT_STM32,
            source_url=SOURCE_URL_MSPM0,
        )

    assert not (fake_module_library / "bmp180" / "mspm0" / "bmp180.c").exists()


def test_add_platform_files_missing_module_raises(fake_module_library):
    with pytest.raises(LibraryError, match="不存在"):
        add_platform_files(
            fake_module_library, "ghost", "stm32", {"a.c": "int a(void);\n"}
        )


def test_remove_platform_files_removes_files_then_drops_empty_entry(
    fake_module_library,
):
    add_module(
        FakeLLM(),
        fake_module_library,
        slug="bmp180",
        platform="stm32",
        description="BMP180 气压计驱动",
        files={"bmp180.c": "int bmp180_read(void);\n", "bmp180.h": "#pragma once\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    manifest = remove_platform_files(fake_module_library, "bmp180", "stm32", ["bmp180.c"])

    assert manifest.platforms["stm32"].files == ("bmp180.h",)
    assert not (fake_module_library / "bmp180" / "bmp180.c").exists()
    assert (fake_module_library / "bmp180" / "bmp180.h").exists()

    manifest = remove_platform_files(fake_module_library, "bmp180", "stm32", ["bmp180.h"])

    assert "stm32" not in manifest.platforms
    assert not (fake_module_library / "bmp180" / "bmp180.h").exists()


def test_remove_platform_files_keeps_file_shared_by_other_platform(
    fake_module_library,
):
    header = "#pragma once\n"
    add_module(
        FakeLLM(),
        fake_module_library,
        slug="bmp180",
        platform="stm32",
        description="BMP180 气压计驱动",
        files={"inc/bmp180.h": header, "stm32/bmp180.c": "int bmp180_read(void);\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )
    add_platform_files(
        fake_module_library,
        "bmp180",
        "mspm0",
        {"inc/bmp180.h": header, "mspm0/bmp180.c": "int bmp180_read(void);\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_MSPM0,
    )

    manifest = remove_platform_files(
        fake_module_library, "bmp180", "stm32", ["inc/bmp180.h", "stm32/bmp180.c"]
    )

    # stm32 条目删空后移除；共享的 inc/bmp180.h 仍被 mspm0 引用，磁盘文件保留
    assert "stm32" not in manifest.platforms
    assert (fake_module_library / "bmp180" / "inc" / "bmp180.h").exists()
    assert not (fake_module_library / "bmp180" / "stm32" / "bmp180.c").exists()


def test_remove_platform_files_rejects_unknown_filename(fake_module_library):
    _add_bmp180(fake_module_library)

    with pytest.raises(LibraryError, match="不在"):
        remove_platform_files(fake_module_library, "bmp180", "stm32", ["nope.c"])


def test_remove_platform_files_rejects_missing_platform_entry(fake_module_library):
    _add_bmp180(fake_module_library)

    with pytest.raises(LibraryError, match="没有"):
        remove_platform_files(fake_module_library, "bmp180", "mspm0", ["bmp180.c"])


def test_remove_platform_files_rejects_empty_filenames(fake_module_library):
    _add_bmp180(fake_module_library)

    with pytest.raises(LibraryError, match="至少"):
        remove_platform_files(fake_module_library, "bmp180", "stm32", [])


# ---------------------------------------------------------------------------
# 硬件身份字段（工单 01）：新录入强制，校验失败在落盘前
# ---------------------------------------------------------------------------


def test_add_module_requires_kit(fake_module_library):
    with pytest.raises(LibraryError, match="kit"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="bmp180",
            platform="stm32",
            description="BMP180 气压计驱动",
            files={"bmp180.c": "int bmp180_read(void);\n"},
            hardware_bound=True,
            kit="",
            source_url=SOURCE_URL_STM32,
        )

    assert not (fake_module_library / "bmp180").exists()  # 拒绝不落盘


def test_add_module_requires_source_url(fake_module_library):
    with pytest.raises(LibraryError, match="source_url"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="bmp180",
            platform="stm32",
            description="BMP180 气压计驱动",
            files={"bmp180.c": "int bmp180_read(void);\n"},
            hardware_bound=True,
            kit=KIT_STM32,
            source_url="",
        )

    assert not (fake_module_library / "bmp180").exists()  # 拒绝不落盘


def test_add_module_pure_logic_without_identity_ok(fake_module_library):
    """纯逻辑模块（hardware_bound=False）可不带身份字段入库（工单 06 修订）。"""
    manifest = add_module(
        FakeLLM(),
        fake_module_library,
        slug="zone",
        platform="stm32",
        description="区域判定逻辑（纯软件）",
        files={"zone.c": "int zone_determine(void);\n"},
    )

    entry = manifest.platforms["stm32"]
    assert entry.hardware_bound is False
    assert entry.kit == ""
    assert entry.source_url == ""


def test_add_module_hardware_bound_requires_identity(fake_module_library):
    """硬件绑定条目仍强制身份字段——修订只放行纯逻辑条目。"""
    with pytest.raises(LibraryError, match="kit"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="bmp180",
            platform="stm32",
            description="BMP180 气压计驱动",
            files={"bmp180.c": "int bmp180_read(void);\n"},
            hardware_bound=True,
            kit="",
            source_url=SOURCE_URL_STM32,
        )

    assert not (fake_module_library / "bmp180").exists()  # 拒绝不落盘


def test_add_module_pure_logic_rejects_provided_bad_url(fake_module_library):
    """纯逻辑条目给了身份就校验格式——给了就要给对。"""
    with pytest.raises(LibraryError, match="格式非法"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="bmp180",
            platform="stm32",
            description="BMP180 气压计驱动",
            files={"bmp180.c": "int bmp180_read(void);\n"},
            kit=KIT_STM32,
            source_url="item.jd.com/1000.html",  # 无协议
        )

    assert not (fake_module_library / "bmp180").exists()  # 拒绝不落盘


@pytest.mark.parametrize(
    "bad_url",
    [
        "item.jd.com/1000.html",  # 无协议
        "https://",  # 无主机
        "ftp://",  # 无主机
        "不是链接",  # 无协议无主机
        "https://a b.com",  # 主机含空白
    ],
)
def test_add_module_rejects_invalid_source_url(fake_module_library, bad_url):
    with pytest.raises(LibraryError, match="格式非法"):
        add_module(
            FakeLLM(),
            fake_module_library,
            slug="bmp180",
            platform="stm32",
            description="BMP180 气压计驱动",
            files={"bmp180.c": "int bmp180_read(void);\n"},
            kit=KIT_STM32,
            source_url=bad_url,
        )

    assert not (fake_module_library / "bmp180").exists()  # 拒绝不落盘


def test_add_module_strips_identity_whitespace(fake_module_library):
    manifest = add_module(
        FakeLLM(),
        fake_module_library,
        slug="bmp180",
        platform="stm32",
        description="BMP180 气压计驱动",
        files={"bmp180.c": "int bmp180_read(void);\n"},
        kit=f"  {KIT_STM32}  ",
        source_url=f"  {SOURCE_URL_STM32}  ",
    )

    assert manifest.platforms["stm32"].kit == KIT_STM32
    assert manifest.platforms["stm32"].source_url == SOURCE_URL_STM32


def test_add_platform_files_requires_identity_for_new_platform(fake_module_library):
    _add_bmp180(fake_module_library)

    # 硬件绑定新平台条目：缺 kit 拒绝并说明
    with pytest.raises(LibraryError, match="kit"):
        add_platform_files(
            fake_module_library,
            "bmp180",
            "mspm0",
            {"mspm0/bmp180.c": "int bmp180_read(void);\n"},
            hardware_bound=True,
            source_url=SOURCE_URL_MSPM0,
        )
    # 硬件绑定新平台条目：缺 source_url 拒绝并说明
    with pytest.raises(LibraryError, match="source_url"):
        add_platform_files(
            fake_module_library,
            "bmp180",
            "mspm0",
            {"mspm0/bmp180.c": "int bmp180_read(void);\n"},
            hardware_bound=True,
            kit=KIT_STM32,
        )

    # 拒绝后无残留：文件不落盘、manifest 条目不新增
    assert not (fake_module_library / "bmp180" / "mspm0" / "bmp180.c").exists()
    assert set(get_module(fake_module_library, "bmp180").platforms) == {"stm32"}


def test_add_platform_files_pure_logic_new_platform_without_identity(fake_module_library):
    """纯逻辑新平台条目可不带身份字段（工单 06 修订）。"""
    _add_bmp180(fake_module_library)

    manifest = add_platform_files(
        fake_module_library,
        "bmp180",
        "mspm0",
        {"mspm0/bmp180.c": "int bmp180_read(void);\n"},
    )

    entry = manifest.platforms["mspm0"]
    assert entry.hardware_bound is False
    assert entry.kit == ""
    assert entry.source_url == ""
    assert (fake_module_library / "bmp180" / "mspm0" / "bmp180.c").exists()


def test_add_platform_files_appending_keeps_existing_identity(fake_module_library):
    """给已有平台版本追加文件不是新增条目：身份字段不强制、原值保留。"""
    _add_bmp180(fake_module_library)

    manifest = add_platform_files(
        fake_module_library,
        "bmp180",
        "stm32",
        {"bmp180.h": "#pragma once\n"},
    )

    assert manifest.platforms["stm32"].files == ("bmp180.c", "bmp180.h")
    assert manifest.platforms["stm32"].kit == KIT_STM32
    assert manifest.platforms["stm32"].source_url == SOURCE_URL_STM32


def test_add_platform_files_backfills_identity_on_existing_entry(fake_module_library):
    _add_bmp180(fake_module_library)

    manifest = add_platform_files(
        fake_module_library,
        "bmp180",
        "stm32",
        {"bmp180.h": "#pragma once\n"},
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    assert manifest.platforms["stm32"].kit == KIT_STM32
    assert manifest.platforms["stm32"].source_url == SOURCE_URL_STM32


def test_add_platform_files_rejects_invalid_backfill_identity(fake_module_library):
    _add_bmp180(fake_module_library)

    with pytest.raises(LibraryError, match="格式非法"):
        add_platform_files(
            fake_module_library,
            "bmp180",
            "stm32",
            {"bmp180.h": "#pragma once\n"},
            source_url="not-a-url",
        )

    # 校验失败在落盘前：文件没写、既有身份字段保持原样
    assert not (fake_module_library / "bmp180" / "bmp180.h").exists()
    assert (
        get_module(fake_module_library, "bmp180").platforms["stm32"].source_url
        == SOURCE_URL_STM32
    )


# ---------------------------------------------------------------------------
# 存量迁移（工单 01）：无身份字段的 manifest 照常加载 / 浏览 / 编辑
# ---------------------------------------------------------------------------


def test_legacy_manifest_without_identity_loads_with_empty_fields(
    fake_module_library,
):
    """假库的存量 manifest 全部没有身份字段：浏览正常，字段为空值。"""
    dht11 = get_module(fake_module_library, "dht11")

    assert dht11.platforms["stm32"].kit == ""
    assert dht11.platforms["stm32"].source_url == ""
    assert dht11.platforms["mspm0"].kit == ""
    assert dht11.platforms["mspm0"].source_url == ""


def test_save_manifest_backfills_identity_fields(fake_module_library):
    """存量条目经结构编辑路径补填身份字段：成功写回。"""
    dht11 = get_module(fake_module_library, "dht11")
    entry = dht11.platforms["stm32"]
    backfilled = dataclasses.replace(
        dht11,
        platforms={
            **dht11.platforms,
            "stm32": dataclasses.replace(
                entry, kit=KIT_STM32, source_url=SOURCE_URL_STM32
            ),
        },
    )

    save_manifest(fake_module_library, backfilled)

    stored = get_module(fake_module_library, "dht11")
    assert stored.platforms["stm32"].kit == KIT_STM32
    assert stored.platforms["stm32"].source_url == SOURCE_URL_STM32


def test_save_manifest_rejects_invalid_backfilled_source_url(fake_module_library):
    dht11 = get_module(fake_module_library, "dht11")
    entry = dht11.platforms["stm32"]
    bad = dataclasses.replace(
        dht11,
        platforms={
            **dht11.platforms,
            "stm32": dataclasses.replace(entry, source_url="not-a-url"),
        },
    )

    with pytest.raises(LibraryError, match="格式非法"):
        save_manifest(fake_module_library, bad)

    # 落盘前拒绝：磁盘上仍是原样
    assert get_module(fake_module_library, "dht11").platforms["stm32"].source_url == ""


def test_save_manifest_allows_identity_still_empty(fake_module_library):
    """存量条目补填是逐步的：身份字段仍为空也能保存（只做格式校验、不强制）。"""
    dht11 = get_module(fake_module_library, "dht11")

    save_manifest(fake_module_library, dataclasses.replace(dht11, dependencies=("delay",)))

    assert get_module(fake_module_library, "dht11").platforms["stm32"].kit == ""
    assert get_module(fake_module_library, "dht11").platforms["stm32"].source_url == ""


# ---------------------------------------------------------------------------
# 存量身份补填编辑路径（工单 02）：update_platform_identity
# ---------------------------------------------------------------------------


def test_update_platform_identity_backfills_legacy_entry(fake_module_library):
    """给存量（无身份字段）平台条目补填 kit / source_url：保存成功并落盘。"""
    manifest = update_platform_identity(
        fake_module_library,
        "dht11",
        "stm32",
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    entry = manifest.platforms["stm32"]
    assert entry.kit == KIT_STM32
    assert entry.source_url == SOURCE_URL_STM32
    stored = get_module(fake_module_library, "dht11").platforms["stm32"]
    assert stored.kit == KIT_STM32
    assert stored.source_url == SOURCE_URL_STM32
    assert stored.files == ("stm32/src/dht11.c", "inc/dht11.h")  # 文件列表不变


def test_update_platform_identity_preserves_other_entry_fields(fake_module_library):
    """只改身份字段：文件列表、验证状态、硬件绑定、备注全部原样保留。"""
    before = get_module(fake_module_library, "dht11").platforms["stm32"]
    assert before.verified is True
    assert before.hardware_bound is False
    assert before.notes == "PA0"

    manifest = update_platform_identity(
        fake_module_library,
        "dht11",
        "stm32",
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    entry = manifest.platforms["stm32"]
    assert entry.verified is True
    assert entry.hardware_bound is False
    assert entry.notes == "PA0"
    assert entry.files == before.files


def test_update_platform_identity_backfills_each_field_independently(
    fake_module_library,
):
    """补填是逐步的：只填 kit、不填 source_url 也能保存（反之亦然），
    未提供的字段保留原值。"""
    manifest = update_platform_identity(
        fake_module_library, "dht11", "stm32", kit=KIT_STM32
    )

    assert manifest.platforms["stm32"].kit == KIT_STM32
    assert manifest.platforms["stm32"].source_url == ""

    manifest = update_platform_identity(
        fake_module_library, "dht11", "stm32", source_url=SOURCE_URL_STM32
    )

    assert manifest.platforms["stm32"].kit == KIT_STM32  # 原值保留
    assert manifest.platforms["stm32"].source_url == SOURCE_URL_STM32


def test_update_platform_identity_modifies_existing_fields(fake_module_library):
    """已填过身份字段的条目可修改为新值（补填 / 修改同一条路径）。"""
    update_platform_identity(
        fake_module_library,
        "dht11",
        "stm32",
        kit=KIT_STM32,
        source_url=SOURCE_URL_STM32,
    )

    manifest = update_platform_identity(
        fake_module_library,
        "dht11",
        "stm32",
        kit="地猛星 MSPM0G3507 开发板",
        source_url=SOURCE_URL_MSPM0,
    )

    entry = manifest.platforms["stm32"]
    assert entry.kit == "地猛星 MSPM0G3507 开发板"
    assert entry.source_url == SOURCE_URL_MSPM0


def test_update_platform_identity_strips_whitespace(fake_module_library):
    manifest = update_platform_identity(
        fake_module_library,
        "dht11",
        "stm32",
        kit=f"  {KIT_STM32}  ",
        source_url=f"  {SOURCE_URL_STM32}  ",
    )

    assert manifest.platforms["stm32"].kit == KIT_STM32
    assert manifest.platforms["stm32"].source_url == SOURCE_URL_STM32


def test_update_platform_identity_rejects_invalid_source_url(fake_module_library):
    with pytest.raises(LibraryError, match="格式非法"):
        update_platform_identity(
            fake_module_library,
            "dht11",
            "stm32",
            kit=KIT_STM32,
            source_url="not-a-url",
        )

    # 校验失败在落盘前：磁盘上身份字段仍是原样（空）
    stored = get_module(fake_module_library, "dht11").platforms["stm32"]
    assert stored.kit == ""
    assert stored.source_url == ""


def test_update_platform_identity_rejects_empty_payload(fake_module_library):
    """编辑至少填一个身份字段：全空（含只给空白）拒绝，避免无意义保存。"""
    with pytest.raises(LibraryError, match="至少填写一个硬件身份字段"):
        update_platform_identity(fake_module_library, "dht11", "stm32")
    with pytest.raises(LibraryError, match="至少填写一个硬件身份字段"):
        update_platform_identity(fake_module_library, "dht11", "stm32", kit="   ")


def test_update_platform_identity_blank_kit_means_not_provided(
    fake_module_library,
):
    """kit 只给空白 = 未提供：不报错、保留原值——补填是逐步的，只填
    source_url（表单带空 kit）也必须能保存。"""
    manifest = update_platform_identity(
        fake_module_library,
        "dht11",
        "stm32",
        kit="   ",
        source_url=SOURCE_URL_STM32,
    )

    assert manifest.platforms["stm32"].kit == ""
    assert manifest.platforms["stm32"].source_url == SOURCE_URL_STM32


def test_update_platform_identity_missing_platform_entry_raises(fake_module_library):
    with pytest.raises(LibraryError, match="没有平台"):
        update_platform_identity(fake_module_library, "oled", "mspm0", kit=KIT_STM32)


def test_update_platform_identity_missing_module_raises(fake_module_library):
    with pytest.raises(LibraryError, match="不存在"):
        update_platform_identity(fake_module_library, "wifi", "stm32", kit=KIT_STM32)
