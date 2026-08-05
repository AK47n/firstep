"""CCS 修改器：改写 .cproject 的行为测试。

通过公开接口 ProjectPatcher.patch 驱动：给定工程目录 + 模块文件 + include
目录，断言 .cproject 的改写结果；不碰实现细节。与 Keil 的关键差异：
.cproject 不逐文件枚举源文件，所以断言的是 include path 与 sourceEntries。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contest_generator.ccs import (
    INCLUDE_OPTION_SUPERCLASS,
    CcsPatcher,
    CcsProjectError,
    _SETTINGS_MODULE_ID,
)
from tests.fakes import make_fake_ccs_master_project

MODULE_FILES = (
    Path("modules/dht11/mspm0/src/dht11.c"),
    Path("modules/dht11/inc/dht11.h"),
    Path("modules/delay/delay.c"),
    Path("modules/delay/delay.h"),
)
INCLUDE_DIRS = (
    Path("modules/dht11/mspm0/src"),
    Path("modules/dht11/inc"),
    Path("modules/delay"),
)
MODULE_INCLUDE_VALUES = (
    "${PROJECT_LOC}/modules/dht11/mspm0/src",
    "${PROJECT_LOC}/modules/dht11/inc",
    "${PROJECT_LOC}/modules/delay",
)


@pytest.fixture
def ccs_project(tmp_path) -> Path:
    """假 CCS 母版复制到临时目录，模拟生成后的工程。"""
    return make_fake_ccs_master_project(tmp_path / "project")


def _parse_cproject(project_dir: Path) -> ET.Element:
    return ET.parse(project_dir / "project.cproject").getroot()


def _build_configurations(root: ET.Element) -> list[ET.Element]:
    result: list[ET.Element] = []
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
                result.extend(build_system.findall("configuration"))
    return result


def _configuration(root: ET.Element, name: str) -> ET.Element:
    return next(
        c for c in _build_configurations(root) if c.get("name") == name
    )


def _include_option(configuration: ET.Element) -> ET.Element:
    return next(
        option
        for option in configuration.findall("folderInfo/toolChain/option")
        if option.get("superClass") == INCLUDE_OPTION_SUPERCLASS
    )


def _include_values(root: ET.Element, config_name: str) -> list[str]:
    option = _include_option(_configuration(root, config_name))
    values = [v.get("value") for v in option.findall("listOptionValue")]
    return [v for v in values if v is not None]


def test_appends_module_include_dirs_to_all_configurations(ccs_project):
    CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)

    root = _parse_cproject(ccs_project)
    assert _include_values(root, "Debug") == [
        "${PROJECT_LOC}/inc",
        "${PROJECT_LOC}/driverlib",
        *MODULE_INCLUDE_VALUES,
    ]
    assert _include_values(root, "Release") == [
        "${PROJECT_LOC}/inc",
        *MODULE_INCLUDE_VALUES,
    ]


def test_skips_include_dir_already_in_master(ccs_project):
    root = _parse_cproject(ccs_project)
    already_present = ET.SubElement(
        _include_option(_configuration(root, "Debug")),
        "listOptionValue",
        {"builtIn": "false", "value": MODULE_INCLUDE_VALUES[1]},
    )
    assert already_present is not None
    (ccs_project / "project.cproject").write_text(
        ET.tostring(root, encoding="unicode"), encoding="utf-8"
    )

    CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)

    values = _include_values(_parse_cproject(ccs_project), "Debug")
    assert values.count(MODULE_INCLUDE_VALUES[1]) == 1


def test_root_source_entry_covers_modules_without_new_entry(ccs_project):
    CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)

    root = _parse_cproject(ccs_project)
    for configuration in _build_configurations(root):
        entry_names = [
            e.get("name") for e in configuration.findall("sourceEntries/entry")
        ]
        assert entry_names == [""]  # 根条目已覆盖 modules/，不加新条目


def test_adds_modules_source_entry_when_root_missing(ccs_project):
    root = _parse_cproject(ccs_project)
    for configuration in _build_configurations(root):
        entries = configuration.find("sourceEntries")
        entries.clear()
    (ccs_project / "project.cproject").write_text(
        ET.tostring(root, encoding="unicode"), encoding="utf-8"
    )

    CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)

    root = _parse_cproject(ccs_project)
    for configuration in _build_configurations(root):
        entries = configuration.findall("sourceEntries/entry")
        assert len(entries) == 1
        assert entries[0].get("name") == "modules"
        assert entries[0].get("kind") == "sourcePath"
        assert entries[0].get("flags") == "VALUE_WORKSPACE_PATH"


def _strip_patched_parts(root: ET.Element) -> ET.Element:
    """去掉修改器唯一会动的节点（buildIncludePath 选项、sourceEntries），其余应原样保留。"""
    for configuration in _build_configurations(root):
        tool_chain = configuration.find("folderInfo/toolChain")
        if tool_chain is None:
            continue
        for option in tool_chain.findall("option"):
            if option.get("superClass") == INCLUDE_OPTION_SUPERCLASS:
                tool_chain.remove(option)
        source_entries = configuration.find("sourceEntries")
        if source_entries is not None:
            configuration.remove(source_entries)
    return root


def test_preserves_master_config_except_include_path_and_source_entries(ccs_project):
    original_root = ET.fromstring(
        (ccs_project / "project.cproject").read_text(encoding="utf-8")
    )

    CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)

    patched_root = _parse_cproject(ccs_project)
    ET.indent(_strip_patched_parts(original_root), space="\t")
    ET.indent(_strip_patched_parts(patched_root), space="\t")
    assert ET.tostring(patched_root, encoding="unicode") == ET.tostring(
        original_root, encoding="unicode"
    )


def test_xml_header_and_fileversion_preserved(ccs_project):
    CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)

    patched = (ccs_project / "project.cproject").read_text(encoding="utf-8")
    assert patched.startswith(
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<?fileVersion 4.0.0?><cproject '
    )


def test_patch_without_cproject_raises(ccs_project, tmp_path):
    empty_project = tmp_path / "empty"
    empty_project.mkdir()

    with pytest.raises(CcsProjectError, match="没有 .cproject"):
        CcsPatcher().patch(empty_project, MODULE_FILES, INCLUDE_DIRS)


def test_patch_with_multiple_cproject_raises(ccs_project):
    (ccs_project / "other.cproject").write_text("<cproject/>", encoding="utf-8")

    with pytest.raises(CcsProjectError, match="多个"):
        CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)


def test_patch_with_invalid_xml_raises(ccs_project):
    (ccs_project / "project.cproject").write_text(
        "<cproject><storageModule>", encoding="utf-8"
    )

    with pytest.raises(CcsProjectError, match="XML"):
        CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)


def test_missing_include_option_raises(ccs_project):
    # 母版缺 buildIncludePath 选项时宁可报错，也不产出 include path 不全的工程
    root = _parse_cproject(ccs_project)
    for configuration in _build_configurations(root):
        tool_chain = configuration.find("folderInfo/toolChain")
        if tool_chain is None:
            continue
        for option in tool_chain.findall("option"):
            if option.get("superClass") == INCLUDE_OPTION_SUPERCLASS:
                tool_chain.remove(option)
    (ccs_project / "project.cproject").write_text(
        ET.tostring(root, encoding="unicode"), encoding="utf-8"
    )

    with pytest.raises(CcsProjectError, match="buildIncludePath"):
        CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)


def test_cproject_without_configurations_raises(ccs_project):
    (ccs_project / "project.cproject").write_text(
        '<cproject><storageModule moduleId="org.eclipse.cdt.core.settings"/></cproject>',
        encoding="utf-8",
    )

    with pytest.raises(CcsProjectError, match="configuration"):
        CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)


def test_patch_twice_is_idempotent(ccs_project):
    CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)
    after_first = (ccs_project / "project.cproject").read_text(encoding="utf-8")

    CcsPatcher().patch(ccs_project, MODULE_FILES, INCLUDE_DIRS)
    after_second = (ccs_project / "project.cproject").read_text(encoding="utf-8")

    assert after_second == after_first
