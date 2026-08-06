"""Keil5 修改器：改写 .uvprojx 的行为测试。

通过公开接口 ProjectPatcher.patch 驱动：给定工程目录 + 模块文件 + include
目录，断言 .uvprojx 的注册结果；不碰实现细节。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contest_generator.keil import (
    KeilPatcher,
    KeilProjectError,
    rewrite_project_references,
    validate_project_structure,
)
from tests.fakes import make_fake_master_project

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
        "Targets/Target/TargetOption/TargetArmAds/Cads/IncludePath"
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
        "Targets/Target/TargetOption/TargetArmAds/Cads/IncludePath"
    )
    assert "modules\\dht11\\stm32\\src" in include_path


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
    # 母版缺 Cads/IncludePath 时宁可报错，也不产出 include path 不全的工程
    root = _parse_uvprojx(keil_project)
    cads = root.find("Targets/Target/TargetOption/TargetArmAds/Cads")
    cads.remove(cads.find("IncludePath"))
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
# 提炼落盘后的配置引用重写（ticket 06）：剔除不留悬空引用，main.c 指向模板
# ---------------------------------------------------------------------------

# FilePath 用占位符：测试按 .uvprojx 所在位置替换成根级 / 嵌套两种形态
_REWRITE_UVPROJX = (
    '<Project><Targets><Target><Groups>'
    "<Group><GroupName>main</GroupName><Files>"
    "<File><FileName>main.c</FileName><FileType>1</FileType><FilePath>MAIN_PATH</FilePath></File>"
    "</Files></Group>"
    "<Group><GroupName>sys</GroupName><Files>"
    "<File><FileName>delay.c</FileName><FileType>1</FileType><FilePath>DELAY_PATH</FilePath></File>"
    "<File><FileName>startup_stm32f10x_hd.s</FileName><FileType>2</FileType><FilePath>STARTUP_PATH</FilePath></File>"
    "</Files></Group>"
    "<Group><GroupName>code</GroupName><Files>"
    "<File><FileName>app.c</FileName><FileType>1</FileType><FilePath>APP_PATH</FilePath></File>"
    "</Files></Group>"
    "</Groups></Target></Targets></Project>"
)

_KEPT = ["main.c", "sys/delay.c", "sys/startup_stm32f10x_hd.s"]


def _rewrite_uvprojx(project_dir: Path, paths: dict[str, str]) -> None:
    """写一个含占位 FilePath 的 .uvprojx（路径按 .uvprojx 所在目录换填）。"""
    project_dir.mkdir(parents=True, exist_ok=True)
    text = _REWRITE_UVPROJX
    for placeholder, value in paths.items():
        text = text.replace(placeholder, value)
    (project_dir / "project.uvprojx").write_text(text, encoding="utf-8")


def test_rewrite_drops_dangling_refs_and_redirects_main_at_root(tmp_path):
    """根级 .uvprojx：保留集合外的引用删除；main.c 重定向到模板落位（工程根）。"""
    project = tmp_path / "project"
    _rewrite_uvprojx(
        project,
        {
            "MAIN_PATH": r".\main.c",
            "DELAY_PATH": r".\sys\delay.c",
            "STARTUP_PATH": r".\sys\startup_stm32f10x_hd.s",
            "APP_PATH": r".\code\app.c",
        },
    )

    rewrite_project_references(project, _KEPT)

    root = ET.parse(project / "project.uvprojx").getroot()
    files = [
        (f.findtext("FileName"), f.findtext("FilePath")) for f in root.iter("File")
    ]
    assert files == [
        ("main.c", r".\main.c"),
        ("delay.c", r".\sys\delay.c"),
        ("startup_stm32f10x_hd.s", r".\sys\startup_stm32f10x_hd.s"),
    ]  # app.c 悬空引用已删除


def test_rewrite_resolves_nested_uvprojx_paths(tmp_path):
    """.uvprojx 在子目录（USER/）：FilePath 相对 .uvprojx 所在目录（..\ 出目录），
    匹配保留集合前解析回工程根；main.c 重定向目标从子目录回算（.\..\main.c）。"""
    project = tmp_path / "project"
    (project / "user").mkdir(parents=True)
    _rewrite_uvprojx(
        project / "user",
        {
            "MAIN_PATH": r".\main.c",
            "DELAY_PATH": r".\..\sys\delay.c",
            "STARTUP_PATH": r".\..\sys\startup_stm32f10x_hd.s",
            "APP_PATH": r".\..\code\app.c",
        },
    )

    rewrite_project_references(project, _KEPT)

    root = ET.parse(project / "user" / "project.uvprojx").getroot()
    files = [
        (f.findtext("FileName"), f.findtext("FilePath")) for f in root.iter("File")
    ]
    assert files == [
        ("main.c", r".\..\main.c"),
        ("delay.c", r".\..\sys\delay.c"),
        ("startup_stm32f10x_hd.s", r".\..\sys\startup_stm32f10x_hd.s"),
    ]  # ..\ 相对路径按 .uvprojx 所在目录解析，保留集合匹配成功


def test_rewrite_skips_write_when_nothing_changed(tmp_path):
    """无悬空引用且 main.c 已指向模板落位：不改写文件（保持整合产物原样）。"""
    project = tmp_path / "project"
    (project / "user").mkdir(parents=True)
    minimal = (
        '<Project><Targets><Target><Groups><Group><Files>'
        "<File><FileName>main.c</FileName><FileType>1</FileType><FilePath>"
        r".\..\main.c</FilePath></File>"
        "<File><FileName>delay.c</FileName><FileType>1</FileType><FilePath>"
        r".\..\sys\delay.c</FilePath></File>"
        "</Files></Group></Groups></Target></Targets></Project>"
    )
    uvprojx = project / "user" / "project.uvprojx"
    uvprojx.write_text(minimal, encoding="utf-8")

    rewrite_project_references(project, _KEPT)

    assert uvprojx.read_text(encoding="utf-8") == minimal


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

    with pytest.raises(KeilProjectError, match="Cads/IncludePath"):
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
