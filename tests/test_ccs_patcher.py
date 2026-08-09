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
    DEFINE_OPTION_SUPERCLASSES,
    INCLUDE_OPTION_SUPERCLASSES,
    CcsPatcher,
    CcsProjectError,
    extract_config_summary,
    include_search_dirs,
    _BUILD_SYSTEM_MODULE_ID,
    _SETTINGS_MODULE_ID,
)
from tests.fakes import (
    FAKE_CPROJECT_THEIA,
    make_fake_ccs_master_project,
    make_fake_ccs_theia_master_project,
)

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
    """与生产同款的双格式走查：classic（settings 内 cdtBuildSystem 元素）与
    Theia（独立 cdtBuildSystem storageModule）同一条路径取 configuration。"""
    result: list[ET.Element] = []
    for storage in root.findall("storageModule"):
        if storage.get("moduleId") != _SETTINGS_MODULE_ID:
            continue
        for cconfig in storage.findall("cconfiguration"):
            for inner in cconfig.findall("storageModule"):
                build_system = inner.find("cdtBuildSystem")
                if build_system is None:
                    if inner.get("moduleId") != _BUILD_SYSTEM_MODULE_ID:
                        continue
                    build_system = inner
                result.extend(build_system.findall("configuration"))
    return result


def _configuration(root: ET.Element, name: str) -> ET.Element:
    return next(
        c for c in _build_configurations(root) if c.get("name") == name
    )


def _include_option(configuration: ET.Element) -> ET.Element:
    """与生产同款双位置：classic 直接子元素 / Theia 在 <tool> 元素内。"""
    for option in configuration.findall("folderInfo/toolChain/option"):
        if option.get("superClass") in INCLUDE_OPTION_SUPERCLASSES:
            return option
    for tool in configuration.findall("folderInfo/toolChain/tool"):
        for option in tool.findall("option"):
            if option.get("superClass") in INCLUDE_OPTION_SUPERCLASSES:
                return option
    raise AssertionError("没有 include 选项")


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
            if option.get("superClass") in INCLUDE_OPTION_SUPERCLASSES:
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
            if option.get("superClass") in INCLUDE_OPTION_SUPERCLASSES:
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


# ---------------------------------------------------------------------------
# 读侧 include_search_dirs（keil.py:207 的 CCS 对偶，工单 07）：四态合成 fixture
# ---------------------------------------------------------------------------


def _write_include_search_fixture(project_dir: Path, values: list[str]) -> Path:
    """合成最小 .cproject：单个 Debug 配置 + 给定 buildIncludePath 值（读侧 fixture）。"""
    project_dir.mkdir()
    (project_dir / "project.cproject").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<cproject>\n'
        '  <storageModule moduleId="org.eclipse.cdt.core.settings">\n'
        '    <cconfiguration id="c1">\n'
        '      <storageModule moduleId="org.eclipse.cdt.core.settings">\n'
        '        <cdtBuildSystem>\n'
        '          <configuration name="Debug">\n'
        '            <folderInfo name="/">\n'
        '              <toolChain name="TI Code Generation Tools">\n'
        '                <option name="Include Options" '
        'superClass="ti.ccs.misc.options.buildIncludePath" valueType="includePath">\n'
        + "".join(
            f'                  <listOptionValue builtIn="false" value="{v}"/>\n'
            for v in values
        )
        + '                </option>\n'
        '              </toolChain>\n'
        '            </folderInfo>\n'
        '          </configuration>\n'
        '        </cdtBuildSystem>\n'
        '      </storageModule>\n'
        '    </cconfiguration>\n'
        '  </storageModule>\n'
        '</cproject>\n',
        encoding="utf-8",
    )
    return project_dir


def test_include_search_dirs_expands_project_loc(tmp_path):
    project = _write_include_search_fixture(
        tmp_path / "proj", ["${PROJECT_LOC}/inc", "${PROJECT_LOC}"]
    )

    dirs = include_search_dirs(project)

    assert dirs == [project / "inc", project]


def test_include_search_dirs_keeps_absolute_paths(tmp_path):
    abs_inc = tmp_path / "sdk" / "include"
    project = _write_include_search_fixture(tmp_path / "proj", [str(abs_inc)])

    dirs = include_search_dirs(project)

    assert dirs == [abs_inc]


def test_include_search_dirs_resolves_relative_paths(tmp_path):
    project = _write_include_search_fixture(tmp_path / "proj", ["sdk/headers", "./inc"])

    dirs = include_search_dirs(project)

    assert dirs == [project / "sdk" / "headers", project / "inc"]


def test_include_search_dirs_without_cproject_returns_empty(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    assert include_search_dirs(empty) == []


def test_include_search_dirs_dedupes_in_first_appearance_order(tmp_path):
    project = make_fake_ccs_master_project(tmp_path / "proj")  # Debug: inc+driverlib，Release: inc

    dirs = include_search_dirs(project)

    assert dirs == [project / "inc", project / "driverlib"]


# ---------------------------------------------------------------------------
# Theia 20.5 双格式（工单 08）：以真实 TI empty 工程 .cproject 为底
# ---------------------------------------------------------------------------


@pytest.fixture
def theia_project(tmp_path) -> Path:
    """Theia 母版复制到临时目录，模拟生成后的工程。"""
    return make_fake_ccs_theia_master_project(tmp_path / "project")


def test_patch_theia_locates_configuration_and_appends_includes(theia_project):
    """D1 配置定位：Theia 的 cdtBuildSystem 在独立 storageModule（configuration
    是直接子元素），_build_configurations 单路径找到 → patch 正常追加。"""
    CcsPatcher().patch(theia_project, MODULE_FILES, INCLUDE_DIRS)

    root = _parse_cproject(theia_project)
    values = _include_values(root, "Debug")
    assert values[-3:] == list(MODULE_INCLUDE_VALUES)  # 追加到原有 6 条之后
    assert "${PROJECT_ROOT}" in values  # 母版自带值原样保留


def test_patch_theia_adds_root_source_entry_when_source_entries_missing(theia_project):
    """Theia 母版没有 sourceEntries 元素（CDT 缺省 = 全树为源）——patch 补
    classic 同款根条目把覆盖说死：只加 modules 条目会让 main.c 等母版源码
    不再被编译（sourceEntries 一旦存在 = 完整源集）。"""
    root = _parse_cproject(theia_project)
    assert root.findall("*/cconfiguration/storageModule/sourceEntries") == []
    assert root.findall("*/cconfiguration/storageModule/configuration/sourceEntries") == []

    CcsPatcher().patch(theia_project, MODULE_FILES, INCLUDE_DIRS)

    root = _parse_cproject(theia_project)
    for configuration in _build_configurations(root):
        entries = configuration.findall("sourceEntries/entry")
        assert len(entries) == 1
        assert entries[0].get("name") == ""  # 根条目（excluding Debug），覆盖 modules/
        assert entries[0].get("kind") == "sourcePath"
        assert entries[0].get("excluding") == "Debug"


def test_patch_theia_is_idempotent(theia_project):
    CcsPatcher().patch(theia_project, MODULE_FILES, INCLUDE_DIRS)
    after_first = (theia_project / "project.cproject").read_text(encoding="utf-8")

    CcsPatcher().patch(theia_project, MODULE_FILES, INCLUDE_DIRS)
    after_second = (theia_project / "project.cproject").read_text(encoding="utf-8")

    assert after_second == after_first


def test_patch_theia_missing_include_option_raises(theia_project):
    """Theia 选项（TMS470_TICLANG_4.0 命名空间，编译器 <tool> 内）找不到时同样拒产。"""
    root = _parse_cproject(theia_project)
    for configuration in _build_configurations(root):
        for option in configuration.findall("folderInfo/toolChain/option"):
            if option.get("superClass") in INCLUDE_OPTION_SUPERCLASSES:
                configuration.find("folderInfo/toolChain").remove(option)
        for tool in configuration.findall("folderInfo/toolChain/tool"):
            for option in tool.findall("option"):
                if option.get("superClass") in INCLUDE_OPTION_SUPERCLASSES:
                    tool.remove(option)
    (theia_project / "project.cproject").write_text(
        ET.tostring(root, encoding="unicode"), encoding="utf-8"
    )

    with pytest.raises(CcsProjectError, match="buildIncludePath"):
        CcsPatcher().patch(theia_project, MODULE_FILES, INCLUDE_DIRS)


def _write_theia_include_search_fixture(project_dir: Path, values: list[str]) -> Path:
    """合成最小 Theia .cproject：cdtBuildSystem storageModule 直接持有 configuration
    + 给定 INCLUDE_PATH 值（读侧四态 fixture，Theia 形态）。"""
    project_dir.mkdir()
    (project_dir / "project.cproject").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<cproject>\n'
        '  <storageModule moduleId="org.eclipse.cdt.core.settings">\n'
        '    <cconfiguration id="c1">\n'
        '      <storageModule moduleId="cdtBuildSystem" version="4.0.0">\n'
        '        <configuration name="Debug">\n'
        '          <folderInfo name="/">\n'
        '            <toolChain name="TI Build Tools">\n'
        '              <option name="Include Options" '
        'superClass="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH" '
        'valueType="includePath">\n'
        + "".join(
            f'                  <listOptionValue value="{v}"/>\n' for v in values
        )
        + '                </option>\n'
        '              </toolChain>\n'
        '            </folderInfo>\n'
        '          </configuration>\n'
        '        </storageModule>\n'
        '      </cconfiguration>\n'
        '    </storageModule>\n'
        '</cproject>\n',
        encoding="utf-8",
    )
    return project_dir


def test_include_search_dirs_theia_expands_root_and_skips_macros(tmp_path):
    """D3 值规范化四态 + 去重保序：${PROJECT_ROOT} 前缀 / 等值展开、SDK 宏跳过、
    展开后仍含宏跳过（${PROJECT_ROOT}/${ConfigName}）、绝对保留、相对解析、
    ${PROJECT_LOC} 与 ${PROJECT_ROOT} 同语义（去重）。"""
    abs_inc = tmp_path / "sdk" / "include"
    project = _write_theia_include_search_fixture(
        tmp_path / "proj",
        [
            "${PROJECT_ROOT}/inc",
            "${PROJECT_LOC}/inc",  # 与上行同目录 → 去重（保首个位置）
            "${PROJECT_ROOT}",
            "${COM_TI_MSPM0_SDK_INCLUDE_PATH}",  # SDK 环境宏 → 跳过
            "${COM_TI_MSPM0_SDK_INSTALL_DIR}/source",  # SDK 宏前缀 → 跳过
            "${PROJECT_ROOT}/${ConfigName}",  # 展开后仍含宏 → 跳过
            str(abs_inc),  # 绝对路径保留
            "sdk/headers",  # 相对路径按 .cproject 基准解析
        ],
    )

    dirs = include_search_dirs(project)

    assert dirs == [project / "inc", project, abs_inc, project / "sdk" / "headers"]


def test_include_search_dirs_theia_real_master_values(tmp_path):
    """真实 TI empty 工程值集：只有 ${PROJECT_ROOT} 可展开成工程根，其余全跳过。"""
    project = make_fake_ccs_theia_master_project(tmp_path / "proj")

    dirs = include_search_dirs(project)

    assert dirs == [project]


def test_extract_config_summary_reads_both_formats(tmp_path):
    """配置摘要双格式通吃：classic 与 Theia 的 include path / defines 都读到
    （Theia 走 TMS470_TICLANG_4.0 superClass，defines 同款）。"""
    classic = make_fake_ccs_master_project(tmp_path / "classic")
    lines = extract_config_summary(classic)
    assert any("include path:" in line and "${PROJECT_LOC}/inc" in line for line in lines)
    assert any("defines:" in line and "MSPM0G3507" in line for line in lines)

    theia = make_fake_ccs_theia_master_project(tmp_path / "theia")
    lines = extract_config_summary(theia)
    assert any("include path:" in line and "${PROJECT_ROOT}" in line for line in lines)
    assert any("defines:" in line and "${COM_TI_MSPM0_SDK_SYMBOLS}" in line for line in lines)


def test_ccs_dual_superclass_pins():
    """双格式认知防回退：classic + Theia 两套 superClass 字符串都活在 ccs.py
    （单实现路径；改成一元匹配 Theia 母版即找不到选项）。"""
    import contest_generator.ccs as ccs
    from pathlib import Path

    source = Path(ccs.__file__).read_text(encoding="utf-8")
    for pin in (
        "ti.ccs.misc.options.buildIncludePath",
        "com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH",
        "ti.ccs.misc.options.buildDefine",
        "com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.DEFINE",
    ):
        assert pin in source, f"ccs.py 缺双格式 superClass 认知：{pin}"


def test_fake_theia_cproject_stays_theia_shaped():
    """fixture 自查：Theia 形态三差异仍在（防止 fixture 被悄悄改成 classic 形态
    让双格式测试空转——cdtBuildSystem 独立 storageModule + TMS470 superClass）。"""
    root = ET.fromstring(FAKE_CPROJECT_THEIA)
    configs = _build_configurations(root)
    assert len(configs) == 1
    assert configs[0].get("name") == "Debug"
    assert "${PROJECT_ROOT}" in FAKE_CPROJECT_THEIA
    assert "TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH" in FAKE_CPROJECT_THEIA
    assert DEFINE_OPTION_SUPERCLASSES[1] in FAKE_CPROJECT_THEIA
