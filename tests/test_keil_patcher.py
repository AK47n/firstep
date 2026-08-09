"""Keil5 工程文件：生成时改写 .uvprojx 与母版提炼时确定性现写的行为测试。

通过公开接口驱动：ProjectPatcher.patch（生成）与 build_master_uvprojx /
render_master_uvprojx（母版提炼，工单 09）——断言 .uvprojx 的注册 / 渲染
结果；不碰实现细节。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

import pytest

from contest_generator.keil import (
    UVPROJX_RENDER_LOCATION,
    KeilPatcher,
    KeilProjectError,
    build_master_uvprojx,
    include_search_dirs,
    is_md_startup,
    is_startup_candidate,
    render_master_uvprojx,
    validate_project_structure,
)
from tests.fakes import FAKE_UVPROJX, make_fake_master_project

MODULE_C_FILES = (
    Path("modules/dht11/stm32/src/dht11.c"),
    Path("modules/oled/stm32/src/oled.c"),
)
INCLUDE_DIRS = (
    Path("modules/dht11/stm32/src"),
    Path("modules/dht11/inc"),
    Path("modules/oled/stm32/src"),
    Path("modules/oled/inc"),
)


@pytest.fixture
def keil_project(tmp_path) -> Path:
    """假母版复制到临时目录，模拟生成后的工程。"""
    return make_fake_master_project(tmp_path / "project")


def _parse_uvprojx(project_dir: Path) -> ET.Element:
    return ET.parse(project_dir / "project.uvprojx").getroot()


def test_registers_module_sources_in_modules_group(keil_project):
    KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)

    root = _parse_uvprojx(keil_project)
    groups = root.findall("./Targets/Target/Groups/Group")
    group = next(g for g in groups if g.findtext("GroupName") == "modules")
    files = [
        (f.findtext("FileName"), f.findtext("FileType"), f.findtext("FilePath"))
        for f in group.findall("Files/File")
    ]
    assert files == [
        ("dht11.c", "1", ".\\modules\\dht11\\stm32\\src\\dht11.c"),
        ("oled.c", "1", ".\\modules\\oled\\stm32\\src\\oled.c"),
    ]


def test_appends_module_dirs_to_include_path_preserving_existing(keil_project):
    KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)

    root = _parse_uvprojx(keil_project)
    include_path = root.findtext(
        "Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
    )
    assert include_path == (
        ".\\inc;.\\src"
        ";.\\modules\\dht11\\stm32\\src;.\\modules\\dht11\\inc"
        ";.\\modules\\oled\\stm32\\src;.\\modules\\oled\\inc"
    )


def _strip_patched_parts(root: ET.Element) -> ET.Element:
    """去掉修改器唯一会动的两个节点（Groups、Cads），其余应原样保留。"""
    for target in root.findall("Targets/Target"):
        groups = target.find("Groups")
        if groups is not None:
            target.remove(groups)
        ads = target.find("TargetOption/TargetArmAds")
        if ads is not None:
            cads = ads.find("Cads")
            if cads is not None:
                ads.remove(cads)
    return root


def test_preserves_master_config_except_groups_and_include_path(keil_project):
    original_root = ET.fromstring(
        (keil_project / "project.uvprojx").read_text(encoding="utf-8")
    )

    KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)

    patched_root = _parse_uvprojx(keil_project)
    ET.indent(_strip_patched_parts(original_root), space="  ")
    ET.indent(_strip_patched_parts(patched_root), space="  ")
    assert ET.tostring(patched_root, encoding="unicode") == ET.tostring(
        original_root, encoding="unicode"
    )


def test_patch_without_uvprojx_raises(keil_project, tmp_path):
    empty_project = tmp_path / "empty"
    empty_project.mkdir()

    with pytest.raises(KeilProjectError, match="没有 .uvprojx"):
        KeilPatcher().patch(empty_project, MODULE_C_FILES, INCLUDE_DIRS)


def test_patch_with_multiple_uvprojx_raises(keil_project):
    (keil_project / "other.uvprojx").write_text("<Project/>", encoding="utf-8")

    with pytest.raises(KeilProjectError, match="多个"):
        KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)


def test_patch_finds_uvprojx_in_subdirectory(tmp_path):
    """工程文件在子目录（正点原子风格 USER/）时也能定位并改写。"""
    project = make_fake_master_project(tmp_path / "project")
    user = project / "USER"
    user.mkdir()
    (user / "project.uvprojx").write_text(
        (project / "project.uvprojx").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (project / "project.uvprojx").unlink()

    KeilPatcher().patch(project, MODULE_C_FILES, INCLUDE_DIRS)

    root = _parse_uvprojx(user)
    groups = root.findall("./Targets/Target/Groups/Group")
    assert any(g.findtext("GroupName") == "modules" for g in groups)
    include_path = root.findtext(
        "Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
    )
    assert "modules\\dht11\\stm32\\src" in include_path


def test_patch_registers_module_paths_relative_to_uvprojx_dir(tmp_path):
    r"""母版 .uvprojx 在 user/ 子目录（工单 09 渲染落位）时，模块文件条目与
    include path 相对 user/ 写 .\..\ 回算——否则解析到 user/modules/ 下，
    Keil 编译缺文件（"打开就能编译"不成立）。"""
    project = make_fake_master_project(tmp_path / "project")
    user = project / "user"
    user.mkdir()
    (user / "Project.uvprojx").write_text(FAKE_UVPROJX, encoding="utf-8")
    (project / "project.uvprojx").unlink()

    KeilPatcher().patch(project, MODULE_C_FILES, INCLUDE_DIRS)

    root = ET.parse(user / "Project.uvprojx").getroot()
    group = next(
        g
        for g in root.findall("Targets/Target/Groups/Group")
        if g.findtext("GroupName") == "modules"
    )
    files = [
        (f.findtext("FileName"), f.findtext("FilePath"))
        for f in group.findall("Files/File")
    ]
    assert files == [
        ("dht11.c", r".\..\modules\dht11\stm32\src\dht11.c"),
        ("oled.c", r".\..\modules\oled\stm32\src\oled.c"),
    ]
    include_path = root.findtext(
        "Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
    )
    assert r".\..\modules\dht11\stm32\src" in include_path


def test_patch_ignores_uvprojx_inside_git(tmp_path):
    """.git 里的工程文件不参与定位（旧工程常自带版本库）。"""
    project = make_fake_master_project(tmp_path / "project")
    content = (project / "project.uvprojx").read_text(encoding="utf-8")
    (project / "project.uvprojx").unlink()
    (project / ".git" / "project.uvprojx").write_text(content, encoding="utf-8")

    with pytest.raises(KeilProjectError, match="没有 .uvprojx"):
        KeilPatcher().patch(project, MODULE_C_FILES, INCLUDE_DIRS)


def test_patch_with_invalid_xml_raises(keil_project):
    (keil_project / "project.uvprojx").write_text(
        "<Project><Targets>", encoding="utf-8"
    )

    with pytest.raises(KeilProjectError, match="XML"):
        KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)


def test_xmlns_declarations_preserved(keil_project):
    KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)

    patched = (keil_project / "project.uvprojx").read_text(encoding="utf-8")
    assert 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' in patched
    assert 'xmlns:xsd="http://www.w3.org/2001/XMLSchema"' in patched


def test_missing_include_path_element_raises(keil_project):
    # 母版缺 Cads/VariousControls/IncludePath 时宁可报错，也不产出 include
    # path 不全的工程（真实格式：IncludePath 在 VariousControls 下）
    root = _parse_uvprojx(keil_project)
    controls = root.find("Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls")
    controls.remove(controls.find("IncludePath"))
    (keil_project / "project.uvprojx").write_text(
        ET.tostring(root, encoding="unicode"), encoding="utf-8"
    )

    with pytest.raises(KeilProjectError, match="IncludePath"):
        KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)


def test_repatch_without_sources_removes_stale_modules_group(keil_project):
    KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)
    headers_only = (Path("modules/dht11/inc/dht11.h"),)

    KeilPatcher().patch(keil_project, headers_only, INCLUDE_DIRS)

    root = _parse_uvprojx(keil_project)
    group_names = [
        g.findtext("GroupName") for g in root.findall("Targets/Target/Groups/Group")
    ]
    assert group_names == ["Source Group 1"]


def test_uvprojx_without_targets_raises(keil_project):
    (keil_project / "project.uvprojx").write_text(
        "<Project><SchemaVersion>2.1</SchemaVersion></Project>", encoding="utf-8"
    )

    with pytest.raises(KeilProjectError, match="Target"):
        KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)


def test_patch_twice_is_idempotent(keil_project):
    KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)
    after_first = (keil_project / "project.uvprojx").read_text(encoding="utf-8")

    KeilPatcher().patch(keil_project, MODULE_C_FILES, INCLUDE_DIRS)
    after_second = (keil_project / "project.uvprojx").read_text(encoding="utf-8")

    assert after_second == after_first


def test_patch_twice_with_headers_only_is_idempotent(keil_project):
    headers_only = (Path("modules/dht11/inc/dht11.h"),)
    KeilPatcher().patch(keil_project, headers_only, INCLUDE_DIRS)
    after_first = (keil_project / "project.uvprojx").read_text(encoding="utf-8")

    KeilPatcher().patch(keil_project, headers_only, INCLUDE_DIRS)
    after_second = (keil_project / "project.uvprojx").read_text(encoding="utf-8")

    assert after_second == after_first


# ---------------------------------------------------------------------------
# 母版 .uvprojx 确定性现写（工单 09，判例 09 治本）：渲染器
# ---------------------------------------------------------------------------

# 典型保留集（模拟真实提炼结果：sys/ 官方库 + 启动文件、ml_libs/ 通用封装、
# code/ 业务、inc/ 头文件目录）
_RENDER_KEPT = [
    "sys/system_stm32f10x.c",
    "sys/startup_stm32f10x_md.s",
    "sys/stm32f10x.h",
    "ml_libs/ml_gpio.c",
    "ml_libs/ml_gpio.h",
    "code/drv.c",
]
_RENDER_STARTUP = "sys/startup_stm32f10x_md.s"
_RENDER_INCLUDE_DIRS = ["inc", "ml_libs", "sys"]


def _render(
    kept_paths: Sequence[str] = _RENDER_KEPT,
    startup_path: str | None = _RENDER_STARTUP,
    include_dirs: Sequence[str] = _RENDER_INCLUDE_DIRS,
) -> str:
    return build_master_uvprojx(
        kept_paths=kept_paths, startup_path=startup_path, include_dirs=include_dirs
    )


def _render_files(
    rendered: str,
) -> list[tuple[str | None, str | None, str | None, str | None]]:
    """渲染产物的文件条目：(组名, FileName, FileType, FilePath)。"""
    root = ET.fromstring(rendered)
    files = []
    for group in root.findall("Targets/Target/Groups/Group"):
        for file in group.findall("Files/File"):
            files.append(
                (
                    group.findtext("GroupName"),
                    file.findtext("FileName"),
                    file.findtext("FileType"),
                    file.findtext("FilePath"),
                )
            )
    return files


def test_render_tree_covers_all_kept_sources(tmp_path):
    """文件树引用全部保留 .c/.s（FileType 1/2）+ 模板 main.c 条目。

    main.c 落位工程根、进 user 组、引用 ..\main.c（相对 user/）；启动文件
    作为保留 .s 正常入组（FileType 2，编译链必需件由构造保证在树内）。
    """
    rendered = _render()
    files = _render_files(rendered)

    assert ("user", "main.c", "1", r"..\main.c") in files
    assert ("sys", "system_stm32f10x.c", "1", r"..\sys\system_stm32f10x.c") in files
    assert ("sys", "startup_stm32f10x_md.s", "2", r"..\sys\startup_stm32f10x_md.s") in files
    assert ("ml_libs", "ml_gpio.c", "1", r"..\ml_libs\ml_gpio.c") in files
    assert ("code", "drv.c", "1", r"..\code\drv.c") in files
    # 保留 .h 不进文件树（头文件由 IncludePath 覆盖，决策 1）
    assert not any(name.endswith(".h") for _, name, _, _ in files)


def test_render_groups_by_top_level_dir_sorted(tmp_path):
    """文件树按顶层目录分组（真实母版 sys/ml_libs/user 风格）、组内按路径排序。"""
    files = _render_files(_render())
    groups: dict[str, list[str]] = {}
    for group, name, _, _ in files:
        groups.setdefault(group, []).append(name)

    assert list(groups) == ["code", "ml_libs", "sys", "user"]  # 组名排序
    assert groups["user"] == ["main.c"]
    assert groups["sys"] == ["startup_stm32f10x_md.s", "system_stm32f10x.c"]  # 组内排序


def test_render_device_block_hardcodes_c8t6():
    """设备块硬编码 C8T6（平台线即 STM32F103C8T6/Keil5，决策 4）——参考真实
    母版已知良好格式：Device、IRAM/IROM、ARMCC 0x4、SchemaVersion 2.1。"""
    rendered = _render()
    root = ET.fromstring(rendered)

    assert root.findtext("SchemaVersion") == "2.1"
    assert root.findtext("Header") == "### uVision Project, (C) Keil Software"
    target = root.find("Targets/Target")
    assert target.findtext("ToolsetNumber") == "0x4"
    assert target.findtext("ToolsetName") == "ARM-ADS"
    common = target.find("TargetOption/TargetCommonOption")
    assert common.findtext("Device") == "STM32F103C8"
    assert "IRAM(0x20000000,0x5000)" in common.findtext("Cpu")
    assert "IROM(0x08000000,0x10000)" in common.findtext("Cpu")
    # 与真实母版一致：StartupFile 留空，启动文件经工程树注册（见
    # test_render_tree_covers_all_kept_sources）
    assert common.findtext("StartupFile") == ""


def test_render_include_path_from_kept_header_dirs():
    r"""IncludePath = 保留 .h 所在目录，去重、排序、相对 .uvprojx 所在目录
    （真实惯例 ..\dir;..\dir——决策 3）。"""
    root = ET.fromstring(_render())
    include_path = root.findtext(
        "Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
    )
    assert include_path == r"..\inc;..\ml_libs;..\sys"

    # 去重 + 排序：重复目录只出现一次
    root = ET.fromstring(
        _render(include_dirs=["sys", "ml_libs", "sys", "inc", "code"])
    )
    include_path = root.findtext(
        "Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
    )
    assert include_path == r"..\code;..\inc;..\ml_libs;..\sys"


def test_render_is_deterministic():
    """同一输入必然同一输出（字符串拼接 + 全排序）——确定性现写。"""
    assert _render() == _render()
    assert _render(kept_paths=["a.c", "b/b.c"]) == _render(kept_paths=["a.c", "b/b.c"])
    assert _render(kept_paths=["b/b.c", "a.c"]) == _render(kept_paths=["a.c", "b/b.c"])


def test_render_density_guard_rejects_non_md_startup():
    """密度守卫（决策 4）：保留启动文件必须为 _md（目标板 C8T6 中密度），
    否则大声失败——导入非中密度器件的工程不能静默产出无法编译的母版。"""
    with pytest.raises(KeilProjectError, match="STM32F103C8T6"):
        _render(startup_path="sys/startup_stm32f10x_hd.s")


def test_render_master_writes_fixed_location(tmp_path):
    """render_master_uvprojx 固定落位 user/Project.uvprojx（正点原子风格，
    与真实母版 2026C/21F 一致），内容与 build_master_uvprojx 相同。"""
    project = tmp_path / "master"
    target = render_master_uvprojx(project, _RENDER_KEPT, _RENDER_STARTUP, _RENDER_INCLUDE_DIRS)

    assert target == project / UVPROJX_RENDER_LOCATION
    assert target.read_text(encoding="utf-8") == _render()
    assert "Project" in target.name


def test_render_output_passes_structure_validation(tmp_path):
    """渲染产物入库前过结构校验（ticket 08 安全网）：配置节点齐全 + 工程树
    引用覆盖全部保留 .c/.s——渲染本身保证，构造即一致。"""
    project = tmp_path / "master"
    render_master_uvprojx(project, _RENDER_KEPT, _RENDER_STARTUP, _RENDER_INCLUDE_DIRS)

    expected = sorted(
        p for p in _RENDER_KEPT if Path(p).suffix.lower() in (".c", ".s")
    ) + ["main.c"]
    validate_project_structure(project, expected)


def test_startup_candidate_helpers():
    """启动文件候选识别与 _md 密度判定（决策 2/4）。"""
    assert is_startup_candidate("key/startup_stm32f10x_md.s")
    assert is_startup_candidate("sys/startup_stm32f10x_hd.S")  # 大小写不敏感
    assert not is_startup_candidate("sys/delay.s")  # 自定义汇编不受影响
    assert not is_startup_candidate("sys/startup_stm32f10x.s")  # 无密度变体不算
    assert is_md_startup("key/startup_stm32f10x_md.s")
    assert not is_md_startup("sys/startup_stm32f10x_hd.s")


# ---------------------------------------------------------------------------
# 母版入库前的结构校验（判例 09：AI 整合出的 .uvprojx 结构残缺仍入库）
# ---------------------------------------------------------------------------


def test_validate_structure_accepts_complete_project(keil_project):
    """结构完整的母版工程（假母版 FAKE_UVPROJX：Cads/IncludePath + 工程树引用
    覆盖全部 .c）通过校验。"""
    validate_project_structure(keil_project, ["main.c", "src/system_stm32f10x.c"])


def test_validate_structure_rejects_missing_include_path(keil_project):
    """Cads/IncludePath 节点整个消失（判例 09：AI 合并产物没有该节点）→ 拒绝。"""
    root = ET.parse(keil_project / "project.uvprojx").getroot()
    ads = root.find("Targets/Target/TargetOption/TargetArmAds")
    ads.remove(ads.find("Cads"))
    ET.ElementTree(root).write(keil_project / "project.uvprojx", encoding="utf-8")

    with pytest.raises(KeilProjectError, match="VariousControls/IncludePath"):
        validate_project_structure(keil_project, ["main.c"])


def test_validate_structure_rejects_unreferenced_sources(keil_project):
    """工程树缺了保留源码的引用（判例 09：组被清空）→ 拒绝，中文指出缺谁。"""
    with pytest.raises(KeilProjectError, match="工程树缺少.*dht11.c"):
        validate_project_structure(keil_project, ["main.c", "src/system_stm32f10x.c", "sensors/dht11.c"])


def test_validate_structure_rejects_project_without_target(keil_project):
    """连 Targets/Target 都没有（更残缺的整合产物）→ 拒绝。"""
    (keil_project / "project.uvprojx").write_text(
        "<Project><SchemaVersion>2.1</SchemaVersion></Project>", encoding="utf-8"
    )

    with pytest.raises(KeilProjectError, match="Targets"):
        validate_project_structure(keil_project, [])


def test_include_search_dirs_resolves_master_include_path(keil_project):
    """读侧 include 搜索目录：假母版 IncludePath `.\inc;.\src` 相对 .uvprojx
    所在目录解析为绝对目录（工单 01 共享解析核心，行为逐字）。"""
    assert include_search_dirs(keil_project) == [
        keil_project / "inc",
        keil_project / "src",
    ]
