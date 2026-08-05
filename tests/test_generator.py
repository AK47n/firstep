"""生成器核心：唯一的测试接缝。

输入（平台、已选 manifest 集、母版目录、输出目录、main.c 内容）
→ 输出完整工程目录。断言输出目录的结构与文件内容。
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contest_generator.generator import (
    MasterNotFoundError,
    MissingModuleFilesError,
    OutputDirNotEmptyError,
    UndefinedCallsError,
)
from contest_generator.ccs import INCLUDE_OPTION_SUPERCLASS, _SETTINGS_MODULE_ID
from contest_generator.manifest import ModuleManifest
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32, PatcherRegistry
from tests.fakes import (
    DHT11_H,
    DHT11_MSPM0_C,
    DHT11_STM32_C,
    OLED_H,
    OLED_STM32_C,
    RecordingPatcher,
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
        "Targets/Target/TargetOption/TargetArmAds/Cads/IncludePath"
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
