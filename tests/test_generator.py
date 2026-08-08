"""生成器核心：唯一的测试接缝。

输入（平台、已选 manifest 集、母版目录、输出目录、main.c 内容）
→ 输出完整工程目录。断言输出目录的结构与文件内容。
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contest_generator.generator import (
    GeneratorError,
    MasterNotFoundError,
    MissingModuleFilesError,
    OutputDirNotEmptyError,
    UndefinedCallsError,
    generate_project,
    resolve_topic_context,
)
from contest_generator.ccs import INCLUDE_OPTION_SUPERCLASS, _SETTINGS_MODULE_ID
from contest_generator.llm import LLMError
from contest_generator.manifest import ModuleManifest
from contest_generator.master import MasterError
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32, PatcherRegistry
from contest_generator.topic_library import TopicError
from tests.fakes import (
    DHT11_H,
    DHT11_MSPM0_C,
    DHT11_STM32_C,
    MAIN_SKELETON,
    OLED_H,
    OLED_STM32_C,
    RecordingPatcher,
    make_fake_master_project,
    make_fake_module_library,
)
from tests.generate_wiring_fakes import (
    KIT_REFERENCE_ID,
    TOPIC_PROBLEM_TEXT,
    TOPIC_REFERENCE_ID,
    UWB_REFERENCE_ID,
    make_fake_reference_library,
    make_fake_topic_library,
    make_kit_candidate_module,
    make_topic_specific_module,
)


def test_generate_project_full_flow_returns_summary(fake_module_library, tmp_path):
    """完整流程接缝：选模块 → 定位母版 → 生成 → 摘要，一步返回只读摘要。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    output_dir = tmp_path / "out"

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content=MAIN_SKELETON,
        output_dir=output_dir,
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )

    # 依赖 delay 被自动展开（resolve_selection），落盘与摘要一次给齐
    assert (output_dir / "main.c").is_file()
    assert (output_dir / "modules" / "delay" / "delay.c").is_file()
    assert "modules/dht11/stm32/src" in summary.include_dirs
    assert any(slug == "delay" for slug, _ in summary.modules)


def test_generate_project_master_missing_fails(fake_module_library, tmp_path):
    """母版库里没有该平台母版——流程入口就报错，不产出残缺工程。"""
    with pytest.raises(MasterNotFoundError, match="母版"):
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=tmp_path / "out",
            module_library_dir=fake_module_library,
            masters_dir=tmp_path / "masters",
        )

    assert not (tmp_path / "out").exists()


def test_generate_project_rejects_platform_path_traversal(fake_module_library, tmp_path):
    """借平台名逃出母版库在入口处被拦：平台先过母版库的平台名校验。"""
    with pytest.raises(MasterError, match="非法平台名"):
        generate_project(
            platform="../evil",
            slugs=["dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=tmp_path / "out",
            module_library_dir=fake_module_library,
            masters_dir=tmp_path / "masters",
        )


def test_generate_stm32_outputs_complete_project(make_project, tmp_path):
    result = make_project(output_dir=tmp_path / "out")

    assert result == tmp_path / "out"
    # 母版文件就位
    assert (result / "project.uvprojx").exists()
    assert (result / "inc/stm32f10x_conf.h").exists()
    assert (result / "src/system_stm32f10x.c").exists()
    assert not (result / ".git").exists()
    # .uvprojx：模块源文件注册进工程树，include path 已填好，设备型号保留
    root = ET.parse(result / "project.uvprojx").getroot()
    assert (
        root.findtext("Targets/Target/TargetOption/TargetCommonOption/Device")
        == "STM32F103C8"
    )
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    assert [f.findtext("FilePath") for f in modules.findall("Files/File")] == [
        ".\\modules\\dht11\\stm32\\src\\dht11.c",
        ".\\modules\\oled\\stm32\\src\\oled.c",
    ]
    include_path = root.findtext(
        "Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
    )
    assert include_path == (
        ".\\inc;.\\src"
        ";.\\modules\\dht11\\stm32\\src;.\\modules\\dht11\\inc"
        ";.\\modules\\oled\\stm32\\src;.\\modules\\oled\\inc"
    )
    # main.c 落位，替换母版旧 main
    assert (result / "main.c").read_text(encoding="utf-8") == (
        "int main(void) { float t = dht11_read(); while (1); }\n"
    )
    # 模块文件按平台版本复制，内容原样
    assert (
        result / "modules/dht11/stm32/src/dht11.c"
    ).read_text(encoding="utf-8") == DHT11_STM32_C
    assert (result / "modules/dht11/inc/dht11.h").read_text(encoding="utf-8") == DHT11_H
    assert (
        result / "modules/oled/stm32/src/oled.c"
    ).read_text(encoding="utf-8") == OLED_STM32_C
    assert (result / "modules/oled/inc/oled.h").read_text(encoding="utf-8") == OLED_H


def test_generate_mspm0_outputs_complete_project(make_ccs_project, tmp_path):
    result = make_ccs_project(output_dir=tmp_path / "out")

    assert result == tmp_path / "out"
    # 母版文件就位（.project 是 CCS 打开工程的必需文件）
    assert (result / ".project").exists()
    assert (result / "project.cproject").exists()
    assert (result / "inc/mspm0g3507.h").exists()
    assert (result / "mspm0g3507.cmd").exists()
    assert not (result / ".git").exists()
    # .cproject：include path 已填好，模块目录有 sourceEntry 覆盖
    root = ET.parse(result / "project.cproject").getroot()
    assert _ccs_include_values(root, "Debug") == [
        "${PROJECT_LOC}/inc",
        "${PROJECT_LOC}/driverlib",
        "${PROJECT_LOC}/modules/dht11/mspm0/src",
        "${PROJECT_LOC}/modules/dht11/inc",
        "${PROJECT_LOC}/modules/delay",
    ]
    assert _ccs_include_values(root, "Release") == [
        "${PROJECT_LOC}/inc",
        "${PROJECT_LOC}/modules/dht11/mspm0/src",
        "${PROJECT_LOC}/modules/dht11/inc",
        "${PROJECT_LOC}/modules/delay",
    ]
    assert _ccs_source_entry_names(root, "Debug") == [""]  # 根条目覆盖 modules/
    # main.c 落位，替换母版旧 main
    assert (result / "main.c").read_text(encoding="utf-8") == (
        "int main(void) { float t = dht11_read(); while (1); }\n"
    )
    # 模块文件按平台版本复制，内容原样
    assert (
        result / "modules/dht11/mspm0/src/dht11.c"
    ).read_text(encoding="utf-8") == DHT11_MSPM0_C
    assert (result / "modules/dht11/inc/dht11.h").read_text(encoding="utf-8") == DHT11_H
    assert (result / "modules/delay/delay.c").read_text(encoding="utf-8") == (
        "/* delay */\nvoid delay_ms(int ms);\n"
    )
    assert (result / "modules/delay/delay.h").read_text(encoding="utf-8") == (
        "#pragma once\nvoid delay_ms(int ms);\n"
    )


def _ccs_build_configuration(root: ET.Element, name: str) -> ET.Element:
    for storage in root.findall("storageModule"):
        if storage.get("moduleId") != _SETTINGS_MODULE_ID:
            continue
        for cconfig in storage.findall("cconfiguration"):
            for inner in cconfig.findall("storageModule"):
                if inner.get("moduleId") != _SETTINGS_MODULE_ID:
                    continue
                build_system = inner.find("cdtBuildSystem")
                if build_system is None:
                    continue
                for configuration in build_system.findall("configuration"):
                    if configuration.get("name") == name:
                        return configuration
    raise AssertionError(f"没有名为 {name} 的 build configuration")


def _ccs_include_values(root: ET.Element, config_name: str) -> list[str]:
    configuration = _ccs_build_configuration(root, config_name)
    option = next(
        option
        for option in configuration.findall("folderInfo/toolChain/option")
        if option.get("superClass") == INCLUDE_OPTION_SUPERCLASS
    )
    values = [v.get("value") for v in option.findall("listOptionValue")]
    return [v for v in values if v is not None]


def _ccs_source_entry_names(root: ET.Element, config_name: str) -> list[str]:
    configuration = _ccs_build_configuration(root, config_name)
    names = [e.get("name") for e in configuration.findall("sourceEntries/entry")]
    return [n for n in names if n is not None]


def test_generate_copies_platform_specific_version(
    make_ccs_project, mspm0_selection, tmp_path
):
    dht11 = [m for m in mspm0_selection if m.slug == "dht11"]  # dht11 双平台都有版本
    result = make_ccs_project(manifests=dht11, output_dir=tmp_path / "out")

    assert (
        result / "modules/dht11/mspm0/src/dht11.c"
    ).read_text(encoding="utf-8") == DHT11_MSPM0_C
    # 另一个平台的版本不进来
    assert not (result / "modules/dht11/stm32").exists()


def test_generate_unknown_platform_fails_before_touching_output(make_project, tmp_path):
    from contest_generator.patchers import UnknownPlatformError

    output_dir = tmp_path / "out"

    with pytest.raises(UnknownPlatformError, match="esp32"):
        make_project(platform="esp32", output_dir=output_dir)

    assert not output_dir.exists()


def test_generate_rejects_main_c_calling_undefined_functions(make_project, tmp_path):
    """生成器落盘前的静态自检兜底：不存在调用明确报错，不产出残缺工程。"""
    output_dir = tmp_path / "out"

    with pytest.raises(UndefinedCallsError, match="dht11_init") as excinfo:
        make_project(
            main_c_content="int main(void) { dht11_init(); while (1); }\n",
            output_dir=output_dir,
        )

    assert "头文件" in str(excinfo.value)
    assert not output_dir.exists()


def test_generate_missing_module_file_fails_with_clear_message(
    fake_module_library, make_project, tmp_path
):
    broken = ModuleManifest.load(fake_module_library / "broken")
    output_dir = tmp_path / "out"

    with pytest.raises(MissingModuleFilesError, match="broken") as excinfo:
        make_project(manifests=[broken], output_dir=output_dir)

    assert "stm32/src/broken.c" in str(excinfo.value)
    # 不产出残缺工程：输出目录不被创建
    assert not output_dir.exists()


def test_generate_module_without_platform_version_fails(
    stm32_selection, make_project, tmp_path
):
    oled = [m for m in stm32_selection if m.slug == "oled"]  # oled 没有 mspm0 版本
    output_dir = tmp_path / "out"

    with pytest.raises(MissingModuleFilesError, match=PLATFORM_MSPM0) as excinfo:
        make_project(platform=PLATFORM_MSPM0, manifests=oled, output_dir=output_dir)

    assert "oled" in str(excinfo.value)
    assert not output_dir.exists()


def test_generate_missing_master_dir_fails(make_project, tmp_path):
    output_dir = tmp_path / "out"

    with pytest.raises(MasterNotFoundError, match="master"):
        make_project(
            master_project_dir=tmp_path / "no_such_master", output_dir=output_dir
        )

    assert not output_dir.exists()


def test_generate_rejects_nonempty_output_dir(make_project, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "leftover.txt").write_text("x", encoding="utf-8")

    with pytest.raises(OutputDirNotEmptyError, match="out"):
        make_project(output_dir=output_dir)


def test_generate_accepts_existing_empty_output_dir(make_project, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    result = make_project(output_dir=output_dir)

    assert (result / "main.c").exists()


def test_generate_twice_produces_identical_project_config(make_project, tmp_path):
    first = make_project(output_dir=tmp_path / "out1")
    second = make_project(output_dir=tmp_path / "out2")

    assert (first / "project.uvprojx").read_bytes() == (
        second / "project.uvprojx"
    ).read_bytes()


def test_generate_mspm0_twice_produces_identical_project_config(
    make_ccs_project, tmp_path
):
    first = make_ccs_project(output_dir=tmp_path / "out1")
    second = make_ccs_project(output_dir=tmp_path / "out2")

    assert (first / "project.cproject").read_bytes() == (
        second / "project.cproject"
    ).read_bytes()


def test_patcher_invoked_via_registry_with_files_and_include_dirs(make_project, tmp_path):
    registry = PatcherRegistry()
    spy = RecordingPatcher()
    registry.register(PLATFORM_STM32, spy)
    output_dir = tmp_path / "out"

    make_project(output_dir=output_dir, registry=registry)

    assert len(spy.calls) == 1
    project_dir, module_files, include_dirs = spy.calls[0]
    assert project_dir == output_dir
    assert module_files == (
        Path("modules/dht11/stm32/src/dht11.c"),
        Path("modules/dht11/inc/dht11.h"),
        Path("modules/oled/stm32/src/oled.c"),
        Path("modules/oled/inc/oled.h"),
    )
    assert include_dirs == (
        Path("modules/dht11/stm32/src"),
        Path("modules/dht11/inc"),
        Path("modules/oled/stm32/src"),
        Path("modules/oled/inc"),
    )


# ---------------------------------------------------------------------------
# 工单 03：生成入口支持历史赛题编号（题面全文 + 关联素材 + 该题专用模块）
# ---------------------------------------------------------------------------


def _wired_dirs(tmp_path):
    """生成接线的素材区：赛题库 + 参考文件库 + 该题专用模块与普通候选模块
    （各自独立临时目录，互不污染）。"""
    library = make_fake_module_library(tmp_path / "modules")
    make_topic_specific_module(library)
    make_kit_candidate_module(library)
    topics = make_fake_topic_library(tmp_path / "topics")
    references = make_fake_reference_library(tmp_path / "references")
    return library, topics, references


def test_resolve_topic_context_explicit_key_materializes_entry(tmp_path):
    """显式编号：题面全文（长 PDF 题面全文只在选了该赛题时进上下文）+ 关联素材
    （锚定该题或候选模块套件的参考文件）+ 该题专用模块（XX 题专用标注自动发现）。"""
    library, topics, references = _wired_dirs(tmp_path)

    ctx = resolve_topic_context(
        llm=None,
        topic_key="2026C",
        problem_text="用户粘贴的题面片段",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
    )

    assert ctx is not None
    assert ctx.key == "2026C"
    assert ctx.problem_text == TOPIC_PROBLEM_TEXT
    assert ctx.related_modules == ("lock_control",)
    assert [e.id for e in ctx.references] == [
        TOPIC_REFERENCE_ID,
        KIT_REFERENCE_ID,
        UWB_REFERENCE_ID,
    ]


def test_resolve_topic_context_without_specific_modules_still_carries_kit_refs(
    tmp_path,
):
    """该题没有专用模块（库中无"XX 题专用"标注）时，套件锚定的参考文件仍经
    候选模块的 kit 进清单（评审 c2：关联面不得依赖专用模块是否入库）。"""
    library = make_fake_module_library(tmp_path / "modules")
    make_kit_candidate_module(library)
    topics = make_fake_topic_library(tmp_path / "topics")
    references = make_fake_reference_library(tmp_path / "references")

    ctx = resolve_topic_context(
        llm=None,
        topic_key="2026C",
        problem_text="粘贴",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
    )

    assert ctx is not None
    assert ctx.related_modules == ()
    assert UWB_REFERENCE_ID in [e.id for e in ctx.references]


def test_resolve_topic_context_recognizes_number_in_pasted_text(tmp_path):
    """粘贴题面中出现编号同样可认：AI 提取编号 → 查库得题面全文 + 关联素材。"""
    library, topics, references = _wired_dirs(tmp_path)

    class ExtractingLLM:
        def topic_extract_number(self, text: str) -> str:
            return "2026C"

    ctx = resolve_topic_context(
        llm=ExtractingLLM(),
        topic_key="",
        problem_text="……2026C 数字钥匙题……",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
    )

    assert ctx is not None
    assert ctx.key == "2026C"
    assert ctx.problem_text == TOPIC_PROBLEM_TEXT


def test_resolve_topic_context_auto_recognition_is_best_effort(tmp_path):
    """自动识别尽力而为：提取失败（LLMError）/ 查无此条 / 没提取到 → None，
    不阻断纯粘贴题面流程（与显式编号的查无此条大声报错相对）。"""
    library, topics, references = _wired_dirs(tmp_path)

    class NoNumberLLM:
        def topic_extract_number(self, text: str) -> None:
            return None

    assert (
        resolve_topic_context(
            llm=NoNumberLLM(),
            topic_key="",
            problem_text="普通粘贴题面",
            module_library_dir=library,
            topic_library_dir=topics,
            reference_library_dir=references,
        )
        is None
    )

    class RaisingExtractLLM:
        def topic_extract_number(self, text: str) -> str:
            raise LLMError("服务不可用")

    assert (
        resolve_topic_context(
            llm=RaisingExtractLLM(),
            topic_key="",
            problem_text="粘贴题面",
            module_library_dir=library,
            topic_library_dir=topics,
            reference_library_dir=references,
        )
        is None
    )

    class UnknownKeyLLM:
        def topic_extract_number(self, text: str) -> str:
            return "2021F"  # 库中没有的编号

    assert (
        resolve_topic_context(
            llm=UnknownKeyLLM(),
            topic_key="",
            problem_text="粘贴题面",
            module_library_dir=library,
            topic_library_dir=topics,
            reference_library_dir=references,
        )
        is None
    )


def test_resolve_topic_context_explicit_unknown_key_raises(tmp_path):
    """显式编号查无此条：明确报错（不猜测编造），不是静默降级。"""
    library, topics, references = _wired_dirs(tmp_path)

    with pytest.raises(TopicError, match="没有"):
        resolve_topic_context(
            llm=None,
            topic_key="2021F",
            problem_text="粘贴",
            module_library_dir=library,
            topic_library_dir=topics,
            reference_library_dir=references,
        )


def test_generate_project_with_topic_key_auto_includes_related_modules(
    fake_module_library, tmp_path
):
    """生成入口带历史赛题编号：该题专用模块自动并入最终模块集（生成物与
    用户手选等价），题面 / 关联素材在推荐与骨架阶段已进上下文。"""
    make_topic_specific_module(fake_module_library)
    topics = make_fake_topic_library(tmp_path / "topics")
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
        topic_key="2026C",
        topic_library_dir=topics,
    )

    assert (tmp_path / "out" / "modules" / "lock_control" / "lock_control.c").is_file()
    assert any(slug == "lock_control" for slug, _ in summary.modules)


def test_generate_project_topic_without_library_dir_fails(fake_module_library, tmp_path):
    """入口要求显式编号必须有赛题库目录：缺目录明确报错。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    with pytest.raises(GeneratorError, match="topic_library_dir"):
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=tmp_path / "out",
            module_library_dir=fake_module_library,
            masters_dir=masters_dir,
            topic_key="2026C",
        )


def test_generate_project_unknown_topic_key_raises(fake_module_library, tmp_path):
    """生成入口查无此条：大声报错，不产出残缺工程。"""
    topics = make_fake_topic_library(tmp_path / "topics")
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    with pytest.raises(TopicError, match="没有"):
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=tmp_path / "out",
            module_library_dir=fake_module_library,
            masters_dir=masters_dir,
            topic_key="2021F",
            topic_library_dir=topics,
        )

    assert not (tmp_path / "out").exists()
