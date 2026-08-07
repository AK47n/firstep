"""母版提炼核心：扫描 / 对比 / AI 提炼报告 / 确认落盘 / 结构分析 / 母版库。

用 conftest 的假旧工程（proj-a / proj-b 同平台对）与假 LLM 驱动，断言报告
结构与确认流程落盘的磁盘结果（外部行为）。
"""

import dataclasses
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

from contest_generator.keil import KeilProjectError
from contest_generator.master import (
    BINARY_FILE_REASON,
    MAIN_C_TEMPLATE_REASON,
    RULE_CATEGORIES,
    STARTUP_REPLACEMENT_REASON,
    MasterError,
    ProjectComparison,
    ProjectStructure,
    analyze_structure,
    apply_distillation,
    build_comparison_summary,
    build_judgment_files,
    compare_projects,
    confirm_distillation,
    delete_master,
    distill_master,
    get_master,
    import_master,
    list_masters,
    main_c_template,
    residue_reason,
    scan_project,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    DistillationReport,
    FileDecision,
    ReportError,
)
from tests.fakes import (
    FAKE_CCS_PROJECT,
    FAKE_DISTILL_UVPROJX_A,
    FAKE_DISTILL_UVPROJX_B,
    FakeLLM,
    make_fake_ccs_master_project,
    make_fake_master_project,
)

# 假工程对的判定范围（公共 + 冲突 + 独有，全部文件）与一份典型 AI 判定
# 公共文件（所有工程内容一致）同样由 AI 判定：基础建设必需 → keep（判例 06）
# merge 携带整合产物全文（content）+ 整合说明（explanation）；选一份只是特例
# 注意：.uvprojx 是工程配置文件（工单 09），由确定性规则处理、不在判定范围
MERGED_OLED = "/* 通用 OLED 驱动（整合版） */\nvoid oled_init(void);\n"
DEFAULT_DECISIONS = (
    FileDecision("inc/stm32f10x_conf.h", ACTION_KEEP, reason="官方库配置头，基础必需"),
    FileDecision("src/system_stm32f10x.c", ACTION_KEEP, reason="系统初始化，基础必需"),
    FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用传感器驱动，应进母版"),
    FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="上一场比赛的字体表残留"),
    FileDecision(
        "src/oled.c",
        ACTION_MERGE,
        content=MERGED_OLED,
        explanation="两版接口一致，整合去重",
        source="proj-b",
        reason="B 版本较新",
    ),
)


def _projects(fake_stm32_projects):
    """扫好的工程结构快照列表。"""
    return [scan_project(p) for p in fake_stm32_projects]


def _write_startup(project: Path, directory: str, name: str, content: str) -> None:
    """在工程子目录写一份启动文件候选（目录不存在时先创建）。"""
    path = project / directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _comparison(fake_stm32_projects):
    return compare_projects(_projects(fake_stm32_projects))


def _distill(fake_stm32_projects, llm):
    return distill_master(llm, PLATFORM_STM32, _projects(fake_stm32_projects))


# ---------------------------------------------------------------------------
# 扫描
# ---------------------------------------------------------------------------


def test_rule_categories_keys_match_structure_fields():
    """类别表与结构 / 对比字段一一对应：新增类别必须补字段，防漂移。

    四大类别（残留 / 旧 main.c / 基础设施 / 二进制）的生命周期由
    RULE_CATEGORIES 表驱动，扫描分类按表序进行；类别 key 必须是
    ProjectStructure / ProjectComparison 的既有字段，否则生命周期里
    getattr 静默拿不到分组，带病入库。
    """
    structure_fields = {f.name for f in dataclasses.fields(ProjectStructure)}
    comparison_fields = {f.name for f in dataclasses.fields(ProjectComparison)}
    for category in RULE_CATEGORIES:
        assert category.key in structure_fields
        assert category.key in comparison_fields


def test_scan_detects_platform_and_lists_files(fake_stm32_projects):
    structure_a = scan_project(fake_stm32_projects[0])

    assert structure_a.name == "proj-a"
    assert structure_a.platform == PLATFORM_STM32
    assert structure_a.files == (
        "inc/stm32f10x_conf.h",
        "sensors/dht11.c",
        "src/oled.c",
        "src/system_stm32f10x.c",
    )
    # 工程配置文件（.uvprojx，工单 09）单独记录：确定性规则处理（渲染现写）、
    # 不进扫描清单也不读内容
    assert structure_a.config_files == ("project.uvprojx",)
    assert "project.uvprojx" not in structure_a.files
    assert "project.uvprojx" not in structure_a.file_hashes
    # 旧工程 main.c 单独记录（模板替代，ADR 0002），不进扫描清单也不读内容
    assert structure_a.main_c_files == ("main.c",)
    assert "main.c" not in structure_a.files
    assert "main.c" not in structure_a.file_hashes
    # .git 与构建产物目录不进清单
    assert ".git/HEAD" not in structure_a.files
    assert "Debug/out.axf" not in structure_a.files
    # 源码树内的残留单独记录（含 IDE 用户选项 .uvoptx，工单 09）、不进扫描清单也不读内容
    assert structure_a.residues == ("main.c.bak", "project.uvoptx", "src/oled.o")
    assert "src/oled.o" not in structure_a.files
    assert "src/oled.o" not in structure_a.file_hashes


def test_scan_ignores_build_artifacts_in_other_project(fake_stm32_projects):
    structure_b = scan_project(fake_stm32_projects[1])

    assert ".git/HEAD" not in structure_b.files
    assert "Release/oled.o" not in structure_b.files


def test_scan_classifies_residues_by_rule(tmp_path):
    """构建产物 / 备份 / 临时文件按扩展名与模式识别；名单外的相近命名不误伤。"""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.uvprojx").write_text(FAKE_DISTILL_UVPROJX_B, encoding="utf-8")
    for name, content in {
        "src/driver.o": "ELF",  # 构建产物
        "build/out.axf": "ELF",
        "flash/fw.hex": "hex",
        "build/out.map": "map",
        "main.c.bak": "backup",  # 备份文件
        "src/driver.c~": "backup",
        "list.tmp": "temp",  # 临时文件
        "scratch.temp": "temp",
        "src/real.c": "/* real */",  # 源码不受影响
        "src/real.c.orig": "/* orig */",  # 不在名单内 → 普通文件
    }.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    structure = scan_project(project)

    assert structure.residues == (
        "build/out.axf",
        "build/out.map",
        "flash/fw.hex",
        "list.tmp",
        "main.c.bak",
        "scratch.temp",
        "src/driver.c~",
        "src/driver.o",
    )
    # .uvprojx 是工程配置文件（工单 09），不进扫描清单
    assert structure.config_files == ("project.uvprojx",)
    assert structure.files == ("src/real.c", "src/real.c.orig")


def test_scan_classifies_binary_files_by_content(tmp_path):
    """二进制文件（内容判据：文件头含 NUL）单独记录、不进扫描清单也不读全文；
    纯文本文件不受影响（判例 08：真实旧工程混着 PDF/模型/图片/压缩包，扩展名
    名单永远有尾，内容判据全覆盖）。"""
    project = tmp_path / "proj"
    (project / "USER").mkdir(parents=True)
    (project / "USER" / "project.uvprojx").write_text(
        FAKE_DISTILL_UVPROJX_B, encoding="utf-8"
    )
    (project / "assets").mkdir(parents=True, exist_ok=True)
    (project / "docs").mkdir(parents=True, exist_ok=True)
    (project / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00binary junk")
    (project / "docs" / "note.txt").write_text("plain text\n", encoding="utf-8")

    structure = scan_project(project)

    assert structure.binaries == ("assets/logo.png",)
    assert "assets/logo.png" not in structure.files
    assert "assets/logo.png" not in structure.file_hashes
    assert "docs/note.txt" in structure.files


def test_scan_classifies_bak_variants_as_residues(tmp_path):
    """备份变体（.bak2 / .bak_consolidate——判例 08 真实旧工程备份习惯）按规则
    剔除，不因后缀不在精确名单里漏进 AI 判定。"""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.uvprojx").write_text(FAKE_DISTILL_UVPROJX_B, encoding="utf-8")
    for name in ("code/pid.c.bak2", "code/pid.c.bak3", "code/pid.c.bak_consolidate"):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("/* backup */", encoding="utf-8")
    (project / "code" / "pid.c").write_text("/* real pid */", encoding="utf-8")

    structure = scan_project(project)

    assert structure.residues == (
        "code/pid.c.bak2",
        "code/pid.c.bak3",
        "code/pid.c.bak_consolidate",
    )
    assert "code/pid.c" in structure.files


def test_scan_detects_ccs_platform(tmp_path):
    structure = scan_project(make_fake_ccs_master_project(tmp_path / "ccs_proj"))

    assert structure.platform == PLATFORM_MSPM0
    # .cproject/.project 是工程配置文件（工单 09 决策 6）：确定性保留首份、
    # 不进扫描清单
    assert structure.config_files == (".project", "project.cproject")
    assert "project.cproject" not in structure.files
    assert ".project" not in structure.files


def test_scan_rejects_project_without_config_file(tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "main.c").write_text("int main(void) {}\n", encoding="utf-8")

    with pytest.raises(MasterError, match="无法判定平台"):
        scan_project(bare)


def test_scan_detects_keil_platform_with_nested_uvprojx(tmp_path):
    """工程文件在子目录（正点原子风格 USER/）时也能判定平台。"""
    project = tmp_path / "proj"
    user = project / "USER"
    user.mkdir(parents=True)
    (user / "project.uvprojx").write_text(FAKE_DISTILL_UVPROJX_B, encoding="utf-8")

    structure = scan_project(project)

    assert structure.platform == PLATFORM_STM32
    assert structure.config_files == ("USER/project.uvprojx",)
    assert "USER/project.uvprojx" not in structure.files
    assert structure.config_summary[0] == "project.uvprojx 设备：STM32F103C8"


def test_scan_records_nested_main_c(tmp_path):
    """任意层级的 main.c（正点原子风格 USER/ 子目录）都由模板替代；大小写不
    敏感（Windows 下 MAIN.C 也是 main 文件）。"""
    project = tmp_path / "proj"
    (project / "USER").mkdir(parents=True)
    (project / "USER" / "project.uvprojx").write_text(
        FAKE_DISTILL_UVPROJX_B, encoding="utf-8"
    )
    # USER/MAIN.C 与根 main.c 不同目录：Windows 文件系统大小写不敏感，同目录
    # 写两个会互相覆盖
    (project / "USER" / "MAIN.C").write_text("int main(void) {}\n", encoding="utf-8")
    (project / "main.c").write_text("int main(void) {}\n", encoding="utf-8")

    structure = scan_project(project)

    # 顺序按平台路径排序规则而定，只断言集合
    assert set(structure.main_c_files) == {"USER/MAIN.C", "main.c"}
    assert "main.c" not in structure.files
    assert "MAIN.C" not in structure.files


def test_scan_ignores_uvprojx_inside_git(tmp_path):
    project = tmp_path / "proj"
    (project / ".git").mkdir(parents=True)
    (project / ".git" / "project.uvprojx").write_text("<Project/>", encoding="utf-8")

    with pytest.raises(MasterError, match="无法判定平台"):
        scan_project(project)


def test_scan_rejects_project_with_both_config_files(tmp_path):
    both = tmp_path / "both"
    both.mkdir()
    (both / "project.uvprojx").write_text(FAKE_DISTILL_UVPROJX_B, encoding="utf-8")
    (both / "project.cproject").write_text("<cproject/>", encoding="utf-8")

    with pytest.raises(MasterError, match="无法判定平台"):
        scan_project(both)


def test_scan_rejects_missing_dir(tmp_path):
    with pytest.raises(MasterError, match="不存在"):
        scan_project(tmp_path / "nope")


def test_scan_extracts_keil_config_summary(fake_stm32_projects):
    structure = scan_project(fake_stm32_projects[0])

    assert structure.config_summary == (
        "project.uvprojx 设备：STM32F103C8",
        "project.uvprojx include path：.\\inc;.\\src",
    )


def test_scan_extracts_ccs_config_summary(tmp_path):
    structure = scan_project(make_fake_ccs_master_project(tmp_path / "ccs_proj"))

    assert any("include path" in line for line in structure.config_summary)
    assert any("Debug" in line for line in structure.config_summary)


def test_scan_tolerates_broken_config_xml(fake_stm32_projects):
    (fake_stm32_projects[0] / "project.uvprojx").write_text("<not-xml", encoding="utf-8")

    structure = scan_project(fake_stm32_projects[0])

    assert "无法解析为 XML" in structure.config_summary[0]


def test_scan_classifies_keil_build_logs_as_residues(fake_stm32_projects):
    """Keil 构建产物盲区（判例 06 扩展）：.lst/.htm/.crf/.dep/.lnp 与 .o/.axf
    同模式识别为残留；.ld 链接脚本 / .cmd 命令文件是基础设施不受误伤。名单刻意
    不含裸 .d——依赖文件由输出目录级忽略覆盖（见 RESIDUE_RULES 注释）。"""
    proj = fake_stm32_projects[0]
    for rel, content in {
        "Listings/proj.lst": "listing junk",  # 目录级忽略（.d 等无规则后缀的产物）
        "Listings/proj.d": "dep junk",
        "Objects/proj.crf": "crf junk",
        "Objects/proj.dep": "dep junk",
        "Objects/proj.htm": "<html>link log</html>",
        "proj.lst": "stray listing",  # 目录外的散件按后缀规则识别
        "proj.out": "ccs link junk",
        "proj.elf": "elf junk",
        "startup.ld": "MEMORY { FLASH (rx) : ORIGIN = 0x0 }",  # 链接脚本：基础设施
        "link.cmd": "--stack_size=512",  # TI 链接命令文件：基础设施
    }.items():
        path = proj / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    structure = scan_project(proj)

    residues = set(structure.residues)
    # 目录外的散件按后缀规则识别为残留（.lst/.out/.elf，带规则化原因）
    assert {"proj.elf", "proj.lst", "proj.out"} <= residues
    # Listings/Objects 是构建产物目录，整目录忽略（与 Debug/Release 同模式）：
    # .d/.crf/.dep/.htm 等不再出现在任何清单，也不读内容、不进 AI 判定
    assert not {"Objects/proj.crf", "Objects/proj.dep", "Objects/proj.htm"} <= residues
    assert "Listings/proj.d" not in residues
    assert "Listings/proj.lst" not in residues
    # .ld/.cmd 是基础设施，确定保留、不进判定（后缀匹配是整段 endswith，不会被 .d 误伤）
    assert structure.infrastructure == ("link.cmd", "startup.ld")


def test_scan_ignores_keil_output_dirs_below_uvprojx_dir(fake_stm32_projects):
    """Keil 把 Listings/Objects 建在 .uvprojx 所在目录：工程在 USER/ 下时产物
    在 USER/Listings、USER/Objects（判例 07 交叉缺口——顶层忽略挡不住）。裸 .d
    依赖文件没有后缀规则，全靠目录级忽略兜底，任意层级匹配漏了就会进 AI 判定
    素材。"""
    proj = fake_stm32_projects[0]
    for rel, content in {
        "USER/Listings/proj.d": "dep junk",
        "USER/Listings/proj.htm": "<html>link log</html>",
        "USER/Objects/proj.crf": "crf junk",
        "USER/Objects/proj.o": "obj junk",
    }.items():
        path = proj / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    structure = scan_project(proj)

    ignored = {
        "USER/Listings/proj.d",
        "USER/Listings/proj.htm",
        "USER/Objects/proj.crf",
        "USER/Objects/proj.o",
    }
    assert not set(structure.files) & ignored
    assert not set(structure.residues) & ignored


# ---------------------------------------------------------------------------
# 对比
# ---------------------------------------------------------------------------


def test_compare_classifies_common_conflict_unique(fake_stm32_projects):
    comparison = _comparison(fake_stm32_projects)

    assert comparison.common == (
        "inc/stm32f10x_conf.h",
        "src/system_stm32f10x.c",
    )
    assert comparison.conflicts == ("src/oled.c",)
    assert comparison.unique == ("sensors/dht11.c", "ui/oled_fonts.c")
    # 旧工程 main.c 由模板替代：不进公共 / 冲突 / 独有分类，也就进不了 AI 判定
    assert comparison.main_c_files == ("main.c",)
    # 工程配置文件（.uvprojx）与启动文件候选同样不在判定范围（工单 09）
    assert comparison.config_files == ("project.uvprojx",)
    assert "project.uvprojx" not in comparison.judgment


def test_compare_records_which_projects_hold_each_path(fake_stm32_projects):
    comparison = _comparison(fake_stm32_projects)

    assert "main.c" not in comparison.by_path
    assert comparison.by_path["sensors/dht11.c"] == ("proj-a",)
    assert comparison.by_path["ui/oled_fonts.c"] == ("proj-b",)


def test_compare_unions_residues_across_projects(fake_stm32_projects):
    comparison = _comparison(fake_stm32_projects)

    assert comparison.residues == (
        "main.c.bak",
        "project.uvoptx",  # IDE 用户选项（工单 09）：两工程都有，并集去重
        "src/oled.hex",
        "src/oled.o",
        "ui/oled_fonts.c~",
    )
    # 残留不进对比分类，也不进 AI 判定范围
    assert "src/oled.o" not in comparison.judgment
    assert "src/oled.o" not in comparison.common
    assert "src/oled.o" not in comparison.conflicts
    assert "src/oled.o" not in comparison.unique


def test_compare_rejects_platform_mismatch(fake_stm32_projects, tmp_path):
    ccs = scan_project(make_fake_ccs_master_project(tmp_path / "ccs_proj"))

    with pytest.raises(MasterError, match="同一平台"):
        compare_projects([scan_project(fake_stm32_projects[0]), ccs])


def test_compare_rejects_duplicate_project_names(fake_stm32_projects, tmp_path):
    # 两个同名工程（不同父目录）：by_path 会按名字合并，静默取错来源，必须拒绝
    copy = tmp_path / "copy" / "proj-a"
    copy.parent.mkdir(parents=True)
    shutil.copytree(fake_stm32_projects[0], copy)

    with pytest.raises(MasterError, match="工程名重复"):
        compare_projects([scan_project(fake_stm32_projects[0]), scan_project(copy)])


def test_compare_rejects_empty_projects():
    with pytest.raises(MasterError, match="至少导入一个工程"):
        compare_projects([])


def test_comparison_summary_lists_every_path_and_config(fake_stm32_projects):
    summary = build_comparison_summary(_comparison(fake_stm32_projects))

    for path in ("src/oled.c", "sensors/dht11.c", "ui/oled_fonts.c"):
        assert path in summary
    assert "工程 proj-a" in summary
    assert "include path" in summary


# ---------------------------------------------------------------------------
# 提炼报告
# ---------------------------------------------------------------------------


def test_distill_report_groups_keep_merge_exclude(fake_stm32_projects):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))

    assert report.platform == PLATFORM_STM32
    assert report.projects == ("proj-a", "proj-b")
    # 全部文件（公共 + 冲突 + 独有）都由 AI 判定：公共文件判 keep 进保留；
    # .uvprojx 是工程配置文件（工单 09），确定性现写、自动进 keep 带规则原因
    # （规则条目排最前，AI 判定在后）
    assert [d.path for d in report.keep] == [
        "project.uvprojx",
        "inc/stm32f10x_conf.h",
        "src/system_stm32f10x.c",
        "sensors/dht11.c",
    ]
    assert report.keep[1].reason == "官方库配置头，基础必需"
    config_entry = next(d for d in report.keep if d.path == "project.uvprojx")
    assert config_entry.reason == "工程配置文件：由确定性模板现写，保留文件全量入树"
    assert [d.path for d in report.merge] == ["src/oled.c"]
    assert report.merge[0].source == "proj-b"
    # exclude = AI 判定（ui/oled_fonts.c）+ 规则识别的残留（确定性、排序，
    # 含 IDE 用户选项 .uvoptx）+ 旧工程 main.c（模板替代，规则化原因）
    assert [d.path for d in report.exclude] == [
        "ui/oled_fonts.c",
        "main.c.bak",
        "project.uvoptx",
        "src/oled.hex",
        "src/oled.o",
        "ui/oled_fonts.c~",
        "main.c",
    ]
    assert "残留" in report.exclude[0].reason
    uvoptx_entry = next(d for d in report.exclude if d.path == "project.uvoptx")
    assert uvoptx_entry.reason == "IDE 用户选项：编译时自动重建"
    assert report.exclude[-1].reason == MAIN_C_TEMPLATE_REASON


def test_distill_passes_platform_names_and_summary_to_llm(fake_stm32_projects):
    llm = FakeLLM(distillation=DEFAULT_DECISIONS)

    _distill(fake_stm32_projects, llm)

    platform, names, judgment_files, summary = llm.distill_calls[0]
    assert platform == PLATFORM_STM32
    assert names == ("proj-a", "proj-b")
    assert "src/oled.c" in summary
    # 判定素材覆盖公共 + 冲突 + 独有（全部文件），含全文与持有工程（判例 06：
    # 公共文件也进 AI 判定，内容一致不等于基础建设必需）；.uvprojx 是工程配置
    # 文件（工单 09），确定性规则处理、不进判定素材
    by_path = {f.path: f for f in judgment_files}
    assert set(by_path) == {
        "inc/stm32f10x_conf.h",
        "src/system_stm32f10x.c",
        "src/oled.c",
        "sensors/dht11.c",
        "ui/oled_fonts.c",
    }
    assert "project.uvprojx" not in by_path
    # 摘要里的配置行仍含 "project.uvprojx 设备：..."（配置对比素材），但不作为
    # 待判路径出现——上面 by_path 已断言不进判定素材
    # 公共文件：单版本、持有两工程
    assert by_path["inc/stm32f10x_conf.h"].versions[0].projects == (
        "proj-a",
        "proj-b",
    )
    assert by_path["src/system_stm32f10x.c"].versions[0].projects == (
        "proj-a",
        "proj-b",
    )
    oled_versions = by_path["src/oled.c"].versions
    assert len(oled_versions) == 2  # 冲突文件两个版本都传
    assert {v.projects for v in oled_versions} == {("proj-a",), ("proj-b",)}
    assert any("A 版本" in v.content for v in oled_versions)
    assert any("B 版本" in v.content for v in oled_versions)
    assert by_path["sensors/dht11.c"].versions[0].projects == ("proj-a",)
    assert "DHT11" in by_path["sensors/dht11.c"].versions[0].content
    assert by_path["ui/oled_fonts.c"].versions[0].projects == ("proj-b",)


def test_residues_never_reach_ai_material(fake_stm32_projects):
    """残留不进 AI 判定范围、不进两阶段摘要——AI 只看到公共 + 冲突 + 独有文件。"""
    llm = FakeLLM(distillation=DEFAULT_DECISIONS)

    _distill(fake_stm32_projects, llm)

    _, _, judgment_files, summary = llm.distill_calls[0]
    residue_paths = {"main.c.bak", "src/oled.hex", "src/oled.o", "ui/oled_fonts.c~"}
    assert not {f.path for f in judgment_files} & residue_paths
    for path in residue_paths:
        assert path not in summary


def test_distill_lists_residues_with_rule_reasons(fake_stm32_projects):
    """报告 exclude 清单含残留条目，reason 为规则化原因（不做黑盒消失）。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))

    by_path = {d.path: d for d in report.exclude}
    assert by_path["src/oled.o"].action == ACTION_EXCLUDE
    assert by_path["src/oled.o"].reason == "构建产物：.o 文件"
    assert by_path["src/oled.hex"].reason == "构建产物：.hex 文件"
    assert by_path["main.c.bak"].reason == "备份文件：.bak"
    assert by_path["ui/oled_fonts.c~"].reason == "备份文件：~ 结尾"


def test_binary_files_never_reach_ai_material(fake_stm32_projects):
    """二进制文件（内容判据）不进 AI 判定范围：素材里没有、报告 exclude 带规则化
    原因（判例 08：真实旧工程混着 PDF/模型/图片，全文嵌入会撑爆 LLM 上下文）。"""
    (fake_stm32_projects[0] / "assets").mkdir(parents=True, exist_ok=True)
    (fake_stm32_projects[0] / "assets" / "logo.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00binary junk"
    )

    llm = FakeLLM(distillation=DEFAULT_DECISIONS)
    report = _distill(fake_stm32_projects, llm)

    _, _, judgment_files, summary = llm.distill_calls[0]
    assert "assets/logo.png" not in {f.path for f in judgment_files}
    assert "assets/logo.png" not in summary
    by_path = {d.path: d for d in report.exclude}
    assert by_path["assets/logo.png"].action == ACTION_EXCLUDE
    assert by_path["assets/logo.png"].reason == BINARY_FILE_REASON


def test_distill_rejects_ai_decision_on_binary(fake_stm32_projects):
    """二进制文件由内容规则确定性剔除，AI 判定二进制路径是越界——宁可大声失败。"""
    (fake_stm32_projects[0] / "assets").mkdir(parents=True, exist_ok=True)
    (fake_stm32_projects[0] / "assets" / "logo.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00binary junk"
    )
    bad = (
        *DEFAULT_DECISIONS,
        FileDecision("assets/logo.png", ACTION_EXCLUDE, reason="AI 也判剔除"),
    )

    with pytest.raises(MasterError, match="无需 AI 判定"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))


def test_distill_rejects_ai_decision_on_residue(fake_stm32_projects):
    """残留由规则确定性剔除，AI 判定残留路径是越界——宁可大声失败。"""
    bad = (*DEFAULT_DECISIONS, FileDecision("src/oled.o", ACTION_EXCLUDE, reason="AI 也判残留"))

    with pytest.raises(MasterError, match="无需 AI 判定"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))


def test_distill_excludes_old_main_c_with_rule_reason(fake_stm32_projects):
    """旧工程 main.c 一律不进母版：报告 exclude 带规则化原因，keep 无 main.c。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))

    by_path = {d.path: d for d in report.exclude}
    assert by_path["main.c"].action == ACTION_EXCLUDE
    assert by_path["main.c"].reason == MAIN_C_TEMPLATE_REASON
    assert "main.c" not in {d.path for d in report.keep}


def test_old_main_c_never_reaches_ai_material(fake_stm32_projects):
    """旧工程 main.c 由模板确定性替代：不进判定范围、不进两阶段摘要。"""
    llm = FakeLLM(distillation=DEFAULT_DECISIONS)

    _distill(fake_stm32_projects, llm)

    _, _, judgment_files, summary = llm.distill_calls[0]
    assert "main.c" not in {f.path for f in judgment_files}
    assert "main.c" not in summary


def test_distill_rejects_ai_decision_on_main_c(fake_stm32_projects):
    """旧工程 main.c 由模板确定性替代，AI 判定 main.c 是越界——宁可大声失败。"""
    bad = (*DEFAULT_DECISIONS, FileDecision("main.c", ACTION_KEEP, reason="AI 也判保留"))

    with pytest.raises(MasterError, match="无需 AI 判定"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))


def test_judgment_files_group_identical_contents_across_projects(
    fake_stm32_projects, tmp_path
):
    """内容一致的工程合并为一个版本：oled.c 在 proj-a / proj-c 相同 → 只传一份。"""
    third = tmp_path / "old_projects2" / "proj-c"
    third.parent.mkdir(parents=True)
    shutil.copytree(fake_stm32_projects[0], third)  # proj-c 与 proj-a 内容一致
    projects = [scan_project(p) for p in (*fake_stm32_projects, third)]

    judgment = build_judgment_files(compare_projects(projects))

    oled = next(f for f in judgment if f.path == "src/oled.c")
    assert len(oled.versions) == 2  # A 版本一份（proj-a / proj-c 共享），B 版本一份
    by_projects = {v.projects: v.content for v in oled.versions}
    assert "A 版本" in by_projects[("proj-a", "proj-c")]
    assert "B 版本" in by_projects[("proj-b",)]


def test_distill_accepts_ai_exclude_on_common_path(fake_stm32_projects):
    """公共文件 AI 判 exclude 合法：内容一致 ≠ 基础建设必需（判例 06）。

    所有工程共享的业务 .c/.h（如都拷贝了同一份驱动）由 AI 按内容判除，
    不再"内容一致 → 自动保留"。"""
    # 把 DEFAULT_DECISIONS 里对公共文件的 keep 判定改成 exclude（同路径只判一次）
    decisions = tuple(
        FileDecision("inc/stm32f10x_conf.h", ACTION_EXCLUDE, reason="非基础必需")
        if d.path == "inc/stm32f10x_conf.h"
        else d
        for d in DEFAULT_DECISIONS
    )

    report = _distill(fake_stm32_projects, FakeLLM(distillation=decisions))

    excluded = {d.path for d in report.exclude}
    assert "inc/stm32f10x_conf.h" in excluded
    assert "inc/stm32f10x_conf.h" not in {d.path for d in report.keep}


def test_distill_rejects_merge_on_common_path(fake_stm32_projects):
    """公共文件判定 merge 是错误——内容一致、没有可整合的多份版本。"""
    decisions = DEFAULT_DECISIONS + (
        FileDecision(
            "inc/stm32f10x_conf.h", ACTION_MERGE, source="proj-a", reason="取 proj-a 版本"
        ),
    )

    with pytest.raises(MasterError, match="只用于"):
        _distill(fake_stm32_projects, FakeLLM(distillation=decisions))


def test_distill_rejects_platform_mismatch_with_projects(fake_stm32_projects):
    """调用方给的平台必须与工程的平台一致——不一致时报告会带错误平台的
    模板 main.c 预览与错误落位路径，确认前拦住（平台交叉校验）。"""
    with pytest.raises(MasterError, match="平台不一致"):
        distill_master(
            FakeLLM(distillation=DEFAULT_DECISIONS),
            PLATFORM_MSPM0,
            _projects(fake_stm32_projects),
        )


def test_apply_rejects_report_platform_mismatch(fake_stm32_projects, tmp_path):
    """确认回传的报告平台与工程不一致——与 AI 路径同一道校验，落盘前拦住。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(report, platform=PLATFORM_MSPM0)

    with pytest.raises(MasterError, match="平台不一致"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_distill_requires_full_judgment_coverage(fake_stm32_projects):
    # AI 漏判了冲突文件 src/oled.c（只剩 keep 与 exclude）
    partial = tuple(d for d in DEFAULT_DECISIONS if d.action != ACTION_MERGE)
    llm = FakeLLM(distillation=partial)

    with pytest.raises(MasterError, match="缺少判定.*src/oled.c"):
        _distill(fake_stm32_projects, llm)


def test_distill_rejects_unknown_path(fake_stm32_projects):
    # 判定范围只有 4 条，AI 多给了第 5 条（库外路径）
    bad = (*DEFAULT_DECISIONS, FileDecision("src/extra.c", ACTION_EXCLUDE))
    llm = FakeLLM(distillation=bad)

    with pytest.raises(MasterError, match="对比范围外"):
        _distill(fake_stm32_projects, llm)


# ---------------------------------------------------------------------------
# 确认流程：apply_distillation 按报告落盘
# ---------------------------------------------------------------------------


def test_apply_copies_keep_and_merge_skips_exclude(fake_stm32_projects, tmp_path):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    output = tmp_path / "preview"

    apply_distillation(report, _comparison(fake_stm32_projects), output)

    # 公共文件与 AI 保留的文件就位
    assert (output / "main.c").is_file()
    assert (output / "sensors/dht11.c").is_file()
    # merge：落盘的是 AI 整合产物全文（不是任何一份源工程的复制）
    assert (output / "src/oled.c").read_text(encoding="utf-8") == MERGED_OLED
    assert "B 版本" not in (output / "src/oled.c").read_text(encoding="utf-8")
    # .uvprojx：不再复制源工程（也不写 AI 整合产物）——确定性渲染现写到
    # user/Project.uvprojx（工单 09，判例 09 治本），内容 = 报告预览
    rendered = output / "user" / "Project.uvprojx"
    assert rendered.is_file()
    assert rendered.read_text(encoding="utf-8") == report.uvprojx_preview
    assert "STM32F103C8" in rendered.read_text(encoding="utf-8")
    # exclude：不复制
    assert not (output / "ui/oled_fonts.c").exists()


def test_apply_skips_residues(fake_stm32_projects, tmp_path):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    output = tmp_path / "preview"

    apply_distillation(report, _comparison(fake_stm32_projects), output)

    for residue in ("main.c.bak", "src/oled.hex", "src/oled.o", "ui/oled_fonts.c~"):
        assert not (output / residue).exists()


def test_apply_writes_template_main_c(fake_stm32_projects, tmp_path):
    """落盘后母版 main.c = 平台模板全文，旧工程 main.c 内容不在其中。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    output = tmp_path / "preview"

    apply_distillation(report, _comparison(fake_stm32_projects), output)

    content = (output / "main.c").read_text(encoding="utf-8")
    assert content == main_c_template(PLATFORM_STM32)
    assert "proj-a 的赛题 main" not in content
    assert "proj-b 的赛题 main" not in content


def test_apply_rejects_main_c_missing_from_report(fake_stm32_projects, tmp_path):
    """确认时删掉 main.c 剔除条目——模板替代不能黑盒消失（ADR 0001）。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        exclude=tuple(d for d in report.exclude if d.path != "main.c"),
    )

    with pytest.raises(MasterError, match="旧工程 main.c 必须剔除"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_rejects_main_c_moved_to_keep(fake_stm32_projects, tmp_path):
    """确认时把 main.c 改成保留——确定性替代不因用户编辑而失效。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        exclude=tuple(d for d in report.exclude if d.path != "main.c"),
        keep=(*report.keep, FileDecision("main.c", ACTION_KEEP, reason="用户改的")),
    )

    with pytest.raises(MasterError, match="旧工程 main.c 必须剔除"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_rejects_residue_missing_from_report(fake_stm32_projects, tmp_path):
    """确认时删掉残留条目——残留确定性剔除，不能静默消失。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        exclude=tuple(d for d in report.exclude if d.path != "src/oled.o"),
    )

    with pytest.raises(MasterError, match="残留文件必须剔除"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_rejects_residue_moved_to_keep(fake_stm32_projects, tmp_path):
    """确认时把残留改成保留——规则识别的确定性剔除不因用户编辑而失效。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        exclude=tuple(d for d in report.exclude if d.path != "src/oled.o"),
        keep=(*report.keep, FileDecision("src/oled.o", ACTION_KEEP, reason="用户改的")),
    )

    with pytest.raises(MasterError, match="残留文件必须剔除"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_rejects_binary_missing_from_report(fake_stm32_projects, tmp_path):
    """确认时删掉二进制条目——二进制确定性剔除，不能静默消失（ADR 0001）。"""
    (fake_stm32_projects[0] / "assets").mkdir(parents=True, exist_ok=True)
    (fake_stm32_projects[0] / "assets" / "logo.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00binary junk"
    )
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        exclude=tuple(d for d in report.exclude if d.path != "assets/logo.png"),
    )

    with pytest.raises(MasterError, match="二进制文件必须剔除"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_rejects_binary_moved_to_keep(fake_stm32_projects, tmp_path):
    """确认时把二进制改成保留——内容规则识别的确定性剔除不因用户编辑而失效。"""
    (fake_stm32_projects[0] / "assets").mkdir(parents=True, exist_ok=True)
    (fake_stm32_projects[0] / "assets" / "logo.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00binary junk"
    )
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        exclude=tuple(d for d in report.exclude if d.path != "assets/logo.png"),
        keep=(
            *report.keep,
            FileDecision("assets/logo.png", ACTION_KEEP, reason="用户改的"),
        ),
    )

    with pytest.raises(MasterError, match="二进制文件必须剔除"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_user_edited_merge_content_wins(fake_stm32_projects, tmp_path):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    # 用户确认时把 oled.c 的整合产物改成选 A 版本全文（改回选某份）
    report = replace(
        report,
        merge=tuple(
            replace(d, content="/* A 版本全文 */\n", explanation="用户改回选 A 版本")
            if d.path == "src/oled.c"
            else d
            for d in report.merge
        ),
    )
    output = tmp_path / "preview"

    apply_distillation(report, _comparison(fake_stm32_projects), output)

    assert "A 版本全文" in (output / "src/oled.c").read_text(encoding="utf-8")


def test_apply_rejects_report_without_full_coverage(fake_stm32_projects, tmp_path):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    # 用户确认时把剔除项整个删了 → 覆盖不全，拒绝落盘
    report = replace(report, exclude=())

    with pytest.raises(MasterError, match="缺少判定"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_rejects_unknown_path_in_report(fake_stm32_projects, tmp_path):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        exclude=(
            *report.exclude,
            FileDecision("src/extra.c", ACTION_EXCLUDE, reason="用户加的"),
        ),
    )

    with pytest.raises(MasterError, match="对比范围外"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_distill_rejects_merge_on_unique_path(fake_stm32_projects):
    # 独有文件只有一份内容，没有可整合的对象——merge 只用于冲突文件
    bad = tuple(
        FileDecision(
            d.path,
            ACTION_MERGE,
            content="/* 整合 */",
            explanation="无意义",
            source="proj-a",
            reason="不应出现",
        )
        if d.path == "sensors/dht11.c"
        else d
        for d in DEFAULT_DECISIONS
    )

    with pytest.raises(MasterError, match="只用于"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))


def test_distill_rejects_conflict_classified_as_keep(fake_stm32_projects):
    # 冲突文件（同路径不同内容）只能 merge 或 exclude；keep 没有"取哪份"的信息
    bad = tuple(
        FileDecision(d.path, ACTION_KEEP, reason="两版都可")
        if d.path == "src/oled.c"
        else d
        for d in DEFAULT_DECISIONS
    )

    with pytest.raises(MasterError, match="必须 merge 或 exclude"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))


def test_distill_allows_conflict_exclude(fake_stm32_projects):
    """冲突文件可以剔除——分类不决定动作（内容判据才是唯一判据）。"""
    decisions = tuple(
        FileDecision(d.path, ACTION_EXCLUDE, reason="两版都是赛题残留")
        if d.path == "src/oled.c"
        else d
        for d in DEFAULT_DECISIONS
    )

    report = _distill(fake_stm32_projects, FakeLLM(distillation=decisions))

    assert "src/oled.c" in [d.path for d in report.exclude]
    assert "src/oled.c" not in [d.path for d in report.merge]


def test_distill_rejects_merge_without_content(fake_stm32_projects):
    """merge 必须带整合产物全文——空或纯空白 content 在确认前就拦住。"""
    bad = tuple(
        FileDecision(d.path, ACTION_MERGE, explanation="忘了写产物")
        if d.path == "src/oled.c"
        else d
        for d in DEFAULT_DECISIONS
    )

    with pytest.raises(MasterError, match="整合产物全文"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))

    whitespace = tuple(
        FileDecision(d.path, ACTION_MERGE, content="   ", explanation="空白产物")
        if d.path == "src/oled.c"
        else d
        for d in DEFAULT_DECISIONS
    )
    with pytest.raises(MasterError, match="整合产物全文"):
        _distill(fake_stm32_projects, FakeLLM(distillation=whitespace))


def test_distill_rejects_merge_with_unknown_source(fake_stm32_projects):
    """merge 选一份特例时来源工程必须是导入工程。"""
    bad = tuple(
        FileDecision(
            d.path,
            ACTION_MERGE,
            content=d.content,
            explanation=d.explanation,
            source="proj-c",
            reason=d.reason,
        )
        if d.path == "src/oled.c"
        else d
        for d in DEFAULT_DECISIONS
    )

    with pytest.raises(MasterError, match="来源工程未知"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))


def test_report_round_trips_through_json(fake_stm32_projects):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))

    rebuilt = DistillationReport.from_dict(
        report.to_dict(),
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
    )

    assert rebuilt == report
    # wire format 形状：确认请求按 to_dict 输出原样回传
    data = report.to_dict()
    assert set(data) == {
        "platform",
        "projects",
        "keep",
        "merge",
        "exclude",
        "main_c_preview",
        "uvprojx_preview",
    }
    assert next(d for d in data["keep"] if d["path"] == "inc/stm32f10x_conf.h") == {
        "path": "inc/stm32f10x_conf.h",
        "action": ACTION_KEEP,
        "content": "",
        "explanation": "",
        "source": "",
        "reason": "官方库配置头，基础必需",
    }
    assert data["merge"][0]["source"] == "proj-b"
    assert data["merge"][0]["content"] == MERGED_OLED
    assert data["merge"][0]["explanation"]


def test_distill_report_carries_template_main_c_preview(fake_stm32_projects):
    """报告携带模板 main.c 全文预览：用户一次确认前能看到将要写入母版的 main.c。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))

    assert report.main_c_preview == main_c_template(PLATFORM_STM32)
    assert report.main_c_preview  # 非空全文


def test_distill_report_carries_uvprojx_preview(fake_stm32_projects):
    """报告携带 .uvprojx 全文预览（工单 09 决策 7，与 main_c_preview 同款）：
    确定性渲染产物，非 AI 生成；用户一次确认前能看到将要写入母版的工程文件。
    （预览 = 落盘渲染产物由 test_apply_copies_keep_and_merge_skips_exclude 断言。）"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))

    assert report.uvprojx_preview
    assert "STM32F103C8" in report.uvprojx_preview
    assert "Project" in report.uvprojx_preview
    assert "<Targets>" in report.uvprojx_preview


def test_report_from_dict_ignores_client_preview(fake_stm32_projects):
    """确认请求回传的预览不可信：from_dict 忽略回传值，预览由调用方按平台重推导。

    预览是确定性展示素材（落盘永远写 main_c_template(platform) 与确定性渲染
    产物），客户端改它不会影响落盘内容；调用方传入权威预览保证报告自洽。
    """
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    data = report.to_dict()
    data["main_c_preview"] = "/* 伪造的预览 */"
    data["uvprojx_preview"] = "<Project/>"

    rebuilt = DistillationReport.from_dict(
        data,
        main_c_preview=main_c_template(PLATFORM_STM32),
        uvprojx_preview=report.uvprojx_preview,
    )

    assert rebuilt.main_c_preview == main_c_template(PLATFORM_STM32)
    assert rebuilt.main_c_preview != "/* 伪造的预览 */"
    assert rebuilt.uvprojx_preview == report.uvprojx_preview
    assert rebuilt.uvprojx_preview != "<Project/>"


def test_report_from_dict_rejects_malformed(fake_stm32_projects):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    data = report.to_dict()
    preview = main_c_template(PLATFORM_STM32)

    bad_cases = [
        "not a dict",
        {**data, "platform": ""},  # 缺平台
        {**data, "projects": []},  # 缺来源工程
        {**data, "keep": "not a list"},
        {**data, "merge": [{"path": "a.c", "action": "archive"}]},  # 条目形状非法
    ]
    for bad in bad_cases:
        with pytest.raises(ReportError):
            DistillationReport.from_dict(bad, main_c_preview=preview)


def test_confirm_wraps_report_shape_errors_as_master_error(
    fake_stm32_projects, tmp_path
):
    """容器形状校验（ReportError）在确认入口转成 MasterError：HTTP 层只认这一种。"""
    project_dirs = list(fake_stm32_projects)

    with pytest.raises(MasterError, match="提炼报告必须是 JSON 对象"):
        confirm_distillation(tmp_path, project_dirs, "not a dict")


def test_apply_rejects_user_edited_merge_on_unique(fake_stm32_projects, tmp_path):
    # 报告本身没问题，但用户确认时把独有文件改成 merge（没有可整合的多份内容）
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        keep=tuple(d for d in report.keep if d.path != "sensors/dht11.c"),
        merge=(
            *report.merge,
            FileDecision(
                "sensors/dht11.c",
                ACTION_MERGE,
                content="/* 整合 */",
                explanation="用户改的",
                source="proj-b",
                reason="用户改的",
            ),
        ),
    )

    with pytest.raises(MasterError, match="只用于"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_user_moves_common_to_exclude(fake_stm32_projects, tmp_path):
    """确认时用户把公共文件改为剔除——公共文件默认保留，但可改剔除。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        keep=tuple(d for d in report.keep if d.path != "inc/stm32f10x_conf.h"),
        exclude=(
            *report.exclude,
            FileDecision("inc/stm32f10x_conf.h", ACTION_EXCLUDE, reason="用户确认剔除"),
        ),
    )

    output = tmp_path / "preview"
    apply_distillation(report, _comparison(fake_stm32_projects), output)

    assert not (output / "inc/stm32f10x_conf.h").exists()


def test_apply_rejects_common_left_undecided(fake_stm32_projects, tmp_path):
    """公共文件既不在 keep 也不在 exclude——报告不完整，拒绝落盘。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        keep=tuple(d for d in report.keep if d.path != "inc/stm32f10x_conf.h"),
    )

    with pytest.raises(MasterError, match="必须保留或剔除"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_rejects_user_merge_on_common(fake_stm32_projects, tmp_path):
    """公共文件内容一致、没有整合对象——确认时改成 merge 被拦截。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        keep=tuple(d for d in report.keep if d.path != "inc/stm32f10x_conf.h"),
        merge=(
            *report.merge,
            FileDecision(
                "inc/stm32f10x_conf.h",
                ACTION_MERGE,
                content="x",
                explanation="y",
                reason="用户改的",
            ),
        ),
    )

    with pytest.raises(MasterError, match="公共文件必须保留"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_rejects_comparison_mismatch(fake_stm32_projects, tmp_path):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    wrong_comparison = compare_projects([scan_project(fake_stm32_projects[0])])

    with pytest.raises(MasterError, match="不匹配"):
        apply_distillation(report, wrong_comparison, tmp_path / "preview")


def test_confirm_distillation_stores_master_in_one_transaction(
    fake_stm32_projects, fake_masters_dir, tmp_path
):
    """确认事务（重扫 → 重比 → 重建报告 → 暂存 → 落盘 → 入库）可不经 HTTP 直测。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    payload = {
        **report.to_dict(),
        "project_dirs": [str(p) for p in fake_stm32_projects],
    }

    meta = confirm_distillation(fake_masters_dir, fake_stm32_projects, payload)

    assert meta.platform == PLATFORM_STM32
    assert meta.sources == ("proj-a", "proj-b")
    stored = fake_masters_dir / PLATFORM_STM32
    assert (stored / "main.c").is_file()
    assert (stored / "main.c").read_text(encoding="utf-8") == main_c_template(
        PLATFORM_STM32
    )
    assert (stored / "sensors/dht11.c").is_file()
    assert not (stored / "ui/oled_fonts.c").exists()
    # 母版里的 .uvprojx = 确定性渲染产物（user/Project.uvprojx，工单 09），
    # 不是任何一份源工程的复制
    rendered = stored / "user" / "Project.uvprojx"
    assert rendered.is_file()
    assert rendered.read_text(encoding="utf-8") == report.uvprojx_preview


def test_confirm_rejects_config_file_disposition_change(fake_stm32_projects, fake_masters_dir):
    """用户确认时把 .uvprojx（工程配置文件）改成剔除 → 确认入库必须拒绝。

    判例 09 治本（工单 09 决策 7）：工程配置文件由确定性规则处理（渲染现写）、
    条目不可改动作——与基础设施同款强制；AI 手写整合 XML 结构残缺的场景从
    源头消失（渲染产物结构一致性由构造保证）。ticket 08 的结构校验保留为
    手工导入母版的安全网（见 analyze/validate 测试）。
    """
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        keep=tuple(d for d in report.keep if d.path != "project.uvprojx"),
        exclude=(
            *report.exclude,
            FileDecision("project.uvprojx", ACTION_EXCLUDE, reason="用户改的"),
        ),
    )
    payload = {
        **report.to_dict(),
        "project_dirs": [str(p) for p in fake_stm32_projects],
    }

    with pytest.raises(MasterError, match="工程配置文件必须保留"):
        confirm_distillation(fake_masters_dir, fake_stm32_projects, payload)

    assert list_masters(fake_masters_dir) == []  # 失败不留任何入库痕迹


def test_confirm_distillation_failure_leaves_no_trace(
    fake_stm32_projects, fake_masters_dir
):
    """确认失败（报告形状非法）不留半成品：暂存目录自灭，母版库不被触碰。"""
    with pytest.raises(MasterError):
        confirm_distillation(
            fake_masters_dir, fake_stm32_projects, {"platform": ""}
        )

    assert list_masters(fake_masters_dir) == []


def test_apply_cleans_up_on_mid_copy_failure(fake_stm32_projects, tmp_path):
    projects = _projects(fake_stm32_projects)
    comparison = compare_projects(projects)
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    output = tmp_path / "preview"
    (fake_stm32_projects[0] / "inc" / "stm32f10x_conf.h").unlink()  # 扫描后文件消失

    with pytest.raises(OSError):
        apply_distillation(report, comparison, output)
    assert not output.exists()


# ---------------------------------------------------------------------------
# 模板 main.c（ADR 0002）：母版自带确定性模板，旧工程 main.c 一律不进母版
# ---------------------------------------------------------------------------


def test_main_c_template_matches_platform():
    """模板 main.c 与平台匹配：stm32 Keil 风格、mspm0 CCS 风格，都是空工程。"""
    stm32 = main_c_template(PLATFORM_STM32)
    mspm0 = main_c_template(PLATFORM_MSPM0)

    assert stm32 != mspm0
    # stm32：寄存器操作风格（工单 09 决策 8），只依赖 stm32f10x.h（其 479 行
    # 已 include system_stm32f10x.h，SystemInit 声明在 79 行），时钟初始化
    assert "stm32f10x.h" in stm32
    assert "stm32f10x_conf.h" not in stm32  # USE_STDPERIPH_DRIVER/conf.h 机制不需要
    assert "SystemInit" in stm32
    # mspm0：CCS SysConfig 风格，SYSCFG_DL_init
    assert "ti_msp_dl_config.h" in mspm0
    assert "SYSCFG_DL_init" in mspm0
    # 共同形态：时钟初始化 + while(1) 空循环 + TODO 区，能直接编译烧录
    for content in (stm32, mspm0):
        assert "int main(void)" in content
        assert "while (1)" in content
        assert "TODO" in content
    # 确定性：同平台多次读取内容一致（非 AI 生成）
    assert main_c_template(PLATFORM_STM32) == stm32
    assert main_c_template(PLATFORM_MSPM0) == mspm0


def test_main_c_template_rejects_unknown_platform():
    with pytest.raises(MasterError, match="未知平台"):
        main_c_template("esp32")


def test_apply_writes_ccs_template_main_c(tmp_path):
    """mspm0 母版落盘同样写平台模板 main.c，结构分析仍通过（IDE 可打开）。"""
    ccs_a = make_fake_ccs_master_project(tmp_path / "ccs_a")
    ccs_b = make_fake_ccs_master_project(tmp_path / "ccs_b")  # 内容一致 → 全公共
    projects = [scan_project(ccs_a), scan_project(ccs_b)]
    # 全公共工程同样逐个进 AI 判定（判例 06）：基础设施 → keep
    decisions = tuple(
        FileDecision(path, ACTION_KEEP, reason="基础设施，基础必需")
        for path in compare_projects(projects).judgment
    )

    report = distill_master(FakeLLM(distillation=decisions), PLATFORM_MSPM0, projects)
    output = tmp_path / "preview"
    apply_distillation(report, compare_projects(projects), output)

    content = (output / "main.c").read_text(encoding="utf-8")
    assert content == main_c_template(PLATFORM_MSPM0)


def test_apply_renders_uvprojx_covering_kept_sources(fake_stm32_projects, tmp_path):
    """落盘后 .uvprojx 由确定性渲染器现写（工单 09，判例 09 治本）：文件树
    引用全部保留 .c/.s（剔除文件不可能有引用——按保留集合构造）、main.c
    条目指向模板落位、IncludePath 覆盖保留 .h 所在目录；入库前结构校验通过。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    projects = _projects(fake_stm32_projects)
    comparison = compare_projects(projects)
    output = tmp_path / "preview"

    apply_distillation(report, comparison, output)

    rendered = (output / "user" / "Project.uvprojx").read_text(encoding="utf-8")
    # 保留源码全量入树（含 merge 的整合产物 src/oled.c）
    assert r"..\src\system_stm32f10x.c" in rendered
    assert r"..\sensors\dht11.c" in rendered
    assert r"..\src\oled.c" in rendered
    # 被剔除的文件没有引用（构造即一致——渲染器只看保留集合）
    assert "oled_fonts" not in rendered
    # main.c 条目指向模板落位（工程根，相对 user/）
    assert r"..\main.c" in rendered
    # IncludePath 覆盖保留 .h 所在目录（inc/stm32f10x_conf.h → ..\inc）
    assert r"..\inc" in rendered
    # 渲染产物过入库结构校验（ticket 08 安全网）
    analyze_structure(output, PLATFORM_STM32)


# ---------------------------------------------------------------------------
# 基础设施（启动文件 / 链接脚本）：确定性保留，不交给 AI 判定
# ---------------------------------------------------------------------------


def test_scan_classifies_infrastructure(fake_stm32_projects):
    """启动文件候选（startup_stm32f10x_*.s）单独记录（跨工程去重，决策 2），
    非启动 .s 与链接脚本进 infrastructure：都不进扫描清单、不进 AI 判定。"""
    (fake_stm32_projects[0] / "startup_stm32f10x_md.s").write_text(
        "; startup", encoding="utf-8"
    )
    (fake_stm32_projects[0] / "src" / "custom.s").write_text(
        "; custom asm", encoding="utf-8"
    )

    structure = scan_project(fake_stm32_projects[0])

    assert structure.startup_files == ("startup_stm32f10x_md.s",)
    assert structure.infrastructure == ("src/custom.s",)
    assert "startup_stm32f10x_md.s" not in structure.files
    assert "startup_stm32f10x_md.s" not in structure.file_hashes
    assert "src/custom.s" not in structure.files


def test_distill_auto_keeps_infrastructure(fake_stm32_projects):
    """基础设施自动保留、排最前、带规则化原因，不占 AI 判定范围（判例 06：
    启动文件判错（剔除）会断掉空工程编译链，不交给 AI）。启动文件候选去重后
    保留份同样自动进 keep（决策 2）。"""
    for project in fake_stm32_projects:
        (project / "startup_stm32f10x_md.s").write_text("; startup", encoding="utf-8")
        (project / "startup_stm32f10x_hd.s").write_text("; startup", encoding="utf-8")
    llm = FakeLLM(distillation=DEFAULT_DECISIONS)

    report = _distill(fake_stm32_projects, llm)

    # 去重：优先 _md（与目标板 C8T6 中密度匹配），落选候选规则剔除
    startup_entry = next(d for d in report.keep if d.path == "startup_stm32f10x_md.s")
    assert startup_entry.reason == "平台基础设施：启动文件 / 链接脚本，确定性保留"
    excluded = {d.path: d for d in report.exclude}
    assert excluded["startup_stm32f10x_hd.s"].action == ACTION_EXCLUDE
    assert excluded["startup_stm32f10x_hd.s"].reason == (
        "启动文件替代：同一器件只需一份启动文件"
    )
    # 不进 AI 判定素材
    _, _, judgment_files, _ = llm.distill_calls[0]
    assert "startup_stm32f10x_md.s" not in {f.path for f in judgment_files}
    assert "startup_stm32f10x_hd.s" not in {f.path for f in judgment_files}


def test_distill_rejects_ai_on_infrastructure(fake_stm32_projects):
    """AI 判定基础设施（保留/整合/剔除）是越界——规则保留的文件 AI 从未见过。"""
    for project in fake_stm32_projects:
        (project / "startup_stm32f10x_md.s").write_text("; startup", encoding="utf-8")
    decisions = DEFAULT_DECISIONS + (
        FileDecision("startup_stm32f10x_md.s", ACTION_KEEP, reason="AI 判的"),
    )

    with pytest.raises(MasterError, match="无需 AI 判定"):
        _distill(fake_stm32_projects, FakeLLM(distillation=decisions))


def test_apply_copies_infrastructure(fake_stm32_projects, tmp_path):
    """基础设施与保留启动文件从第一个含它的工程复制落盘；用户确认也不能
    改成剔除/整合。"""
    for project in fake_stm32_projects:
        (project / "startup_stm32f10x_md.s").write_text("; startup", encoding="utf-8")
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    output = tmp_path / "preview"

    apply_distillation(report, _comparison(fake_stm32_projects), output)

    assert (output / "startup_stm32f10x_md.s").read_text(encoding="utf-8") == (
        "; startup"
    )

    # 用户把保留启动文件改成剔除 → 拒绝（编译链必需件不可改动作）
    report = replace(
        report,
        keep=tuple(d for d in report.keep if d.path != "startup_stm32f10x_md.s"),
        exclude=(
            *report.exclude,
            FileDecision("startup_stm32f10x_md.s", ACTION_EXCLUDE, reason="用户改的"),
        ),
    )
    with pytest.raises(MasterError, match="启动文件必须保留"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "bad")


def test_apply_renders_fixed_location_regardless_of_source(tmp_path):
    """源工程 .uvprojx 在 user/（真实结构，2026C/21F 同款）：落盘后渲染产物
    固定落位 user/Project.uvprojx（正点原子风格，与现母版一致），源 .uvprojx
    不复制；文件树按顶层目录分组、引用按保留集合构造。"""
    project = tmp_path / "proj2025"
    files = {
        "user/project.uvprojx": (
            '<Project><Targets><Target><Groups>'
            "<Group><GroupName>main</GroupName><Files>"
            "<File><FileName>main.c</FileName><FileType>1</FileType><FilePath>"
            r".\main.c</FilePath></File>"
            "</Files></Group>"
            "<Group><GroupName>sys</GroupName><Files>"
            "<File><FileName>delay.c</FileName><FileType>1</FileType><FilePath>"
            r".\..\sys\delay.c</FilePath></File>"
            "<File><FileName>startup_stm32f10x_md.s</FileName><FileType>2</FileType>"
            "<FilePath>"
            r".\..\sys\startup_stm32f10x_md.s</FilePath></File>"
            "</Files></Group>"
            "<Group><GroupName>code</GroupName><Files>"
            "<File><FileName>app.c</FileName><FileType>1</FileType><FilePath>"
            r".\..\code\app.c</FilePath></File>"
            "</Files></Group>"
            "</Groups></Target></Targets></Project>"
        ),
        "user/main.c": "/* 赛题 main */\n",
        "sys/delay.c": "/* 通用延时 */\n",
        "sys/delay.h": "#pragma once\n",
        "sys/startup_stm32f10x_md.s": "; startup\n",
        "code/app.c": "/* 赛题业务 */\n",
    }
    for rel, content in files.items():
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    comparison = compare_projects([scan_project(project)])
    ai_keep = {p for p in comparison.judgment if p.startswith("sys/")}
    ai_exclude = {p for p in comparison.judgment if p not in ai_keep}
    decisions = tuple(
        FileDecision(p, ACTION_KEEP, reason="基础必需") for p in sorted(ai_keep)
    ) + tuple(
        FileDecision(p, ACTION_EXCLUDE, reason="赛题业务") for p in sorted(ai_exclude)
    )
    report = distill_master(
        FakeLLM(distillation=decisions), "stm32", (scan_project(project),)
    )

    output = tmp_path / "preview"
    apply_distillation(report, comparison, output)

    root = ET.parse(output / "user" / "Project.uvprojx").getroot()
    files = [
        (f.findtext("FileName"), f.findtext("FilePath")) for f in root.iter("File")
    ]
    assert ("main.c", r"..\main.c") in files  # 模板 main.c 落位工程根
    assert ("delay.c", r"..\sys\delay.c") in files
    assert ("startup_stm32f10x_md.s", r"..\sys\startup_stm32f10x_md.s") in files
    assert ("app.c", r"..\code\app.c") not in files  # 剔除文件无引用
    assert (output / "sys" / "delay.c").is_file()
    assert (output / "main.c").is_file()  # 模板 main.c 在工程根
    # 源 .uvprojx 不复制：渲染产物是唯一工程文件
    assert list(output.rglob("*.uvprojx")) == [output / "user" / "Project.uvprojx"]


# ---------------------------------------------------------------------------
# 工程配置文件与启动文件去重（工单 09）：确定性规则处理
# ---------------------------------------------------------------------------


def test_scan_classifies_uvguix_as_ide_option(tmp_path):
    """.uvguix（Keil 界面布局，2026C/21F 真实工程成对出现）与 .uvoptx 同族
    （工单 09 决策 5 的补全）：规则剔除、带 IDE 用户选项原因、不进扫描清单。"""
    project = tmp_path / "proj"
    (project / "user").mkdir(parents=True)
    (project / "user" / "Project.uvprojx").write_text(
        FAKE_DISTILL_UVPROJX_A, encoding="utf-8"
    )
    (project / "user" / "Project.uvoptx").write_text(
        "<ProjectOpt/>", encoding="utf-8"
    )
    (project / "user" / "Project.uvguix.luoji").write_text("<GUI/>", encoding="utf-8")

    structure = scan_project(project)

    assert structure.residues == ("user/Project.uvguix.luoji", "user/Project.uvoptx")
    assert residue_reason("user/Project.uvoptx") == "IDE 用户选项：编译时自动重建"
    assert "user/Project.uvoptx" not in structure.files
    assert "user/Project.uvguix.luoji" not in structure.files


def test_startup_dedup_prefers_md_across_projects(fake_stm32_projects):
    """真实案例（2026C+21F 同款）：两个工程各带一份 md 启动（不同目录）——
    跨工程去重只保留一份（优先 _md，同 _md 时路径排序取第一份），落选份
    规则剔除（同一器件只需一份启动文件，否则 Reset_Handler 重复定义）。"""
    _write_startup(fake_stm32_projects[0], "key", "startup_stm32f10x_md.s", "; A")
    _write_startup(fake_stm32_projects[1], "sys", "startup_stm32f10x_md.s", "; B")

    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))

    kept = {d.path for d in report.keep}
    excluded = {d.path: d for d in report.exclude}
    assert "key/startup_stm32f10x_md.s" in kept  # 排序取第一份
    assert excluded["sys/startup_stm32f10x_md.s"].action == ACTION_EXCLUDE
    assert excluded["sys/startup_stm32f10x_md.s"].reason == STARTUP_REPLACEMENT_REASON


def test_startup_dedup_without_md_guard_fires_at_distill(fake_stm32_projects):
    """无 _md 候选（如 hd/vd）：按路径排序取第一份；密度守卫在报告预览推导
    时（入库前，决策 4）大声失败——目标板是中密度 C8T6，不能静默产出无法
    编译的母版。"""
    (fake_stm32_projects[0] / "startup_stm32f10x_hd.s").write_text(
        "; A", encoding="utf-8"
    )
    (fake_stm32_projects[1] / "startup_stm32f10x_vd.s").write_text(
        "; B", encoding="utf-8"
    )

    with pytest.raises(KeilProjectError, match="STM32F103C8T6"):
        _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))


def test_apply_rejects_eliminated_startup_restored(fake_stm32_projects, tmp_path):
    """落选启动文件不可改动作（决策 2）：用户确认时把它改回保留 → 拒绝——
    两份启动并存 = Reset_Handler 重复定义，宁可大声失败。"""
    _write_startup(fake_stm32_projects[0], "key", "startup_stm32f10x_md.s", "; A")
    _write_startup(fake_stm32_projects[1], "sys", "startup_stm32f10x_md.s", "; B")
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        exclude=tuple(
            d for d in report.exclude if d.path != "sys/startup_stm32f10x_md.s"
        ),
        keep=(
            *report.keep,
            FileDecision("sys/startup_stm32f10x_md.s", ACTION_KEEP, reason="用户改的"),
        ),
    )

    with pytest.raises(MasterError, match="落选启动文件必须剔除"):
        apply_distillation(
            report, _comparison(fake_stm32_projects), tmp_path / "preview"
        )


def test_confirm_rederives_uvprojx_preview(fake_stm32_projects, fake_masters_dir):
    """确认请求回传的 .uvprojx 预览不可信（与 main_c_preview 同款，决策 7）：
    确认时按最终决策集重推导，客户端改预览不影响落盘内容。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    payload = {
        **report.to_dict(),
        "uvprojx_preview": "<Project/>",
        "project_dirs": [str(p) for p in fake_stm32_projects],
    }

    confirm_distillation(fake_masters_dir, fake_stm32_projects, payload)

    rendered = (
        fake_masters_dir / PLATFORM_STM32 / "user" / "Project.uvprojx"
    ).read_text(encoding="utf-8")
    assert rendered != "<Project/>"
    assert "STM32F103C8" in rendered
    assert rendered == report.uvprojx_preview  # 权威预览 = 实际落盘


def test_apply_keeps_ccs_config_files_first_copy(tmp_path):
    """mspm0 的 .cproject/.project 确定性保留首份（决策 6）：不现写不重写，
    从第一个含它的工程复制；报告 keep 带规则原因、无 .uvprojx 预览（无现写）。"""
    ccs_a = make_fake_ccs_master_project(tmp_path / "ccs_a")
    ccs_b = make_fake_ccs_master_project(tmp_path / "ccs_b")  # 内容一致 → 全公共
    projects = [scan_project(ccs_a), scan_project(ccs_b)]
    decisions = tuple(
        FileDecision(path, ACTION_KEEP, reason="基础设施，基础必需")
        for path in compare_projects(projects).judgment
    )
    report = distill_master(FakeLLM(distillation=decisions), PLATFORM_MSPM0, projects)

    config_entries = [
        d for d in report.keep if d.path in (".project", "project.cproject")
    ]
    assert {d.path for d in config_entries} == {".project", "project.cproject"}
    assert all("确定性" in d.reason for d in config_entries)
    assert report.uvprojx_preview == ""  # mspm0 无现写

    output = tmp_path / "preview"
    apply_distillation(report, compare_projects(projects), output)

    assert (output / ".project").read_text(encoding="utf-8") == FAKE_CCS_PROJECT
    assert (output / "project.cproject").is_file()
    # 入库结构分析通过（IDE 可打开）
    analyze_structure(output, PLATFORM_MSPM0)


# 真实工程验收（工单 09 决策 9 的自动化部分）：判例 09 原案
# 2026C + 2021F/21F（元数据 sources 同名）；目录缺失（非验收机器）时跳过
REAL_STM32_PROJECTS = (
    Path.home() / "Desktop" / "2026C",
    Path.home() / "Desktop" / "2021F" / "21F",
)
requires_real_projects = pytest.mark.skipif(
    not all(p.is_dir() for p in REAL_STM32_PROJECTS),
    reason="真实工程目录不存在（判例 09 验收环境）",
)


@requires_real_projects
def test_real_projects_2026c_21f_distill_and_import(fake_masters_dir):
    """2026C + 21F 重提炼 → 确认入库 → 结构校验通过（工单 09 决策 9）。

    保留全部判定路径（假 LLM 替身，真实运行走 LLM；冲突文件判 exclude——
    保留动作对冲突文件非法）：启动文件去重（两份 md 只保留一份）、
    .uvoptx/.uvguix 规则剔除、.uvprojx 确定性渲染产物过入库结构校验——
    判例 09 的坏母版场景（AI 手写残缺 XML）从源头消失。
    """
    projects = [scan_project(p) for p in REAL_STM32_PROJECTS]
    comparison = compare_projects(projects)
    decisions = tuple(
        FileDecision(path, ACTION_KEEP, reason="基础必需")
        for path in comparison.judgment
        if path not in comparison.conflicts
    ) + tuple(
        FileDecision(path, ACTION_EXCLUDE, reason="冲突文件")
        for path in comparison.conflicts
    )
    report = distill_master(FakeLLM(distillation=decisions), PLATFORM_STM32, projects)

    # 启动文件去重：key/ 与 sys/ 两份 md 只保留一份（路径排序取第一份）
    kept_startups = [d.path for d in report.keep if d.path.endswith(".s")]
    assert kept_startups == ["key/startup_stm32f10x_md.s"]
    assert any(
        d.path == "sys/startup_stm32f10x_md.s"
        and d.action == ACTION_EXCLUDE
        and d.reason == STARTUP_REPLACEMENT_REASON
        for d in report.exclude
    )
    # IDE 用户选项规则剔除（两工程各带 .uvoptx + .uvguix.<用户名>，包含匹配）
    assert any(d.path.endswith(".uvoptx") for d in report.exclude)
    assert any(".uvguix" in d.path for d in report.exclude)
    # 渲染预览：C8T6 设备块 + 启动文件在树内
    assert "STM32F103C8" in report.uvprojx_preview
    assert "startup_stm32f10x_md.s" in report.uvprojx_preview

    # 完整确认事务：重扫 → 重比 → 落盘 → 渲染 → 结构校验 → 入库
    meta = confirm_distillation(
        fake_masters_dir,
        REAL_STM32_PROJECTS,
        {
            **report.to_dict(),
            "project_dirs": [str(p) for p in REAL_STM32_PROJECTS],
        },
    )

    assert meta.sources == ("2026C", "21F")
    stored = fake_masters_dir / PLATFORM_STM32
    assert (stored / "user" / "Project.uvprojx").is_file()
    # 母版里恰好一份启动文件（Reset_Handler 不重复定义）
    assert [p.name for p in stored.rglob("*.s")] == ["startup_stm32f10x_md.s"]


# ---------------------------------------------------------------------------
# 结构分析
# ---------------------------------------------------------------------------


def test_analyze_accepts_complete_master(tmp_path):
    analysis = analyze_structure(make_fake_master_project(tmp_path / "master"), PLATFORM_STM32)

    assert analysis.platform == PLATFORM_STM32
    assert analysis.warnings == ()


def test_analyze_requires_platform_config_file(tmp_path):
    master = make_fake_master_project(tmp_path / "master")
    (master / "project.uvprojx").unlink()

    with pytest.raises(MasterError, match=".uvprojx"):
        analyze_structure(master, PLATFORM_STM32)


def test_analyze_accepts_nested_uvprojx(tmp_path):
    """工程文件在子目录时结构分析同样通过（正点原子风格 USER/ 子目录）。"""
    master = tmp_path / "master"
    (master / "USER").mkdir(parents=True)
    (master / "USER" / "project.uvprojx").write_text(
        FAKE_DISTILL_UVPROJX_A, encoding="utf-8"
    )

    analysis = analyze_structure(master, PLATFORM_STM32)

    assert analysis.warnings == ()


def test_analyze_requires_ccs_project_description(tmp_path):
    master = make_fake_ccs_master_project(tmp_path / "ccs_master")
    (master / ".project").unlink()

    with pytest.raises(MasterError, match=".project"):
        analyze_structure(master, PLATFORM_MSPM0)


def test_analyze_warns_about_build_artifact_dirs(tmp_path):
    master = make_fake_master_project(tmp_path / "master")
    (master / "Debug").mkdir()
    (master / "Release").mkdir()

    analysis = analyze_structure(master, PLATFORM_STM32)

    assert len(analysis.warnings) == 2
    assert any("Debug" in w for w in analysis.warnings)


def test_analyze_rejects_unknown_platform(tmp_path):
    with pytest.raises(MasterError, match="未知平台"):
        analyze_structure(make_fake_master_project(tmp_path / "master"), "esp32")


# ---------------------------------------------------------------------------
# 母版库：入库 / 浏览 / 删除
# ---------------------------------------------------------------------------


def test_import_stores_master_with_meta_and_sources(
    fake_stm32_projects, fake_masters_dir, tmp_path
):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    preview = apply_distillation(
        report, _comparison(fake_stm32_projects), tmp_path / "preview"
    )

    meta = import_master(fake_masters_dir, PLATFORM_STM32, preview, sources=report.projects)

    assert meta.platform == PLATFORM_STM32
    assert meta.sources == ("proj-a", "proj-b")
    assert meta.warnings == ()
    # 工程文件就位（.uvprojx = 渲染产物在 user/ 下，工单 09），元数据在母版
    # 目录外的平级文件（不污染生成的工程）
    assert (fake_masters_dir / "stm32" / "main.c").is_file()
    assert (fake_masters_dir / "stm32" / "user" / "Project.uvprojx").is_file()
    assert not (fake_masters_dir / "stm32" / "master.json").exists()
    assert (fake_masters_dir / "stm32.json").is_file()


def test_import_replaces_existing_master_of_same_platform(fake_stm32_projects, fake_masters_dir):
    import_master(fake_masters_dir, PLATFORM_STM32, fake_stm32_projects[0])
    stale_file = fake_masters_dir / "stm32" / "stale.c"
    stale_file.write_text("old", encoding="utf-8")

    import_master(
        fake_masters_dir, PLATFORM_STM32, fake_stm32_projects[1], sources=("proj-b",)
    )

    assert not stale_file.exists()  # 旧母版被整体更换
    assert (fake_masters_dir / "stm32" / "project.uvprojx").is_file()
    assert get_master(fake_masters_dir, PLATFORM_STM32).sources == ("proj-b",)


def test_import_swap_failure_keeps_old_master_and_explains_occupation(
    monkeypatch, fake_masters_dir, tmp_path
):
    """旧母版被占用（如 Keil 开着）时替换失败：旧母版原封不动，错误中文说明。

    判例（真实事故）：替换失败的回滚里 rmtree 旧母版，把只被锁住部分的旧
    母版删成空壳——本测试是那次事故的回归测试。
    """
    import_master(fake_masters_dir, PLATFORM_STM32, make_fake_master_project(tmp_path / "old"))
    real_replace = os.replace

    def locked_replace(src, dst):
        if Path(dst).name.startswith(".stm32"):  # 模拟旧母版挪不动（WinError 5）
            raise PermissionError(13, "拒绝访问。")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", locked_replace)

    with pytest.raises(MasterError, match="占用"):
        import_master(
            fake_masters_dir, PLATFORM_STM32, make_fake_master_project(tmp_path / "new")
        )

    # 旧母版一个文件不少；新母版未入库；无残留备份目录
    assert (fake_masters_dir / "stm32" / "main.c").is_file()
    assert (fake_masters_dir / "stm32" / "project.uvprojx").is_file()
    assert not (fake_masters_dir / ".stm32.backup").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 独占：真实目录句柄锁")
def test_import_locked_subdirectory_keeps_old_master_intact(
    fake_masters_dir, tmp_path
):
    """端到端：无 share-delete 的目录句柄（Keil/资源管理器的真实锁法）锁住
    旧母版子目录时，替换失败且旧母版原封不动（WinError 5 的真实成因）。"""
    import ctypes

    import_master(fake_masters_dir, PLATFORM_STM32, make_fake_master_project(tmp_path / "old"))
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p
    handle = kernel32.CreateFileW(
        str(fake_masters_dir / "stm32" / "inc"),
        0x80000000, 0x3, None, 3, 0x02000000, None,  # 只共享读写、不共享删除
    )
    assert handle not in (None, ctypes.c_void_p(-1).value)
    try:
        with pytest.raises((MasterError, OSError), match="占用|拒绝访问|WinError"):
            import_master(
                fake_masters_dir, PLATFORM_STM32,
                make_fake_master_project(tmp_path / "new"),
            )
    finally:
        kernel32.CloseHandle(handle)

    # 旧母版一个文件不少（判例事故的回归：不删残）；新母版未入库
    assert (fake_masters_dir / "stm32" / "main.c").is_file()
    assert (fake_masters_dir / "stm32" / "project.uvprojx").is_file()
    assert not (fake_masters_dir / ".stm32.backup").exists()


def test_import_rejects_missing_config_without_touching_store(fake_masters_dir, tmp_path):
    import_master(
        fake_masters_dir, PLATFORM_STM32, make_fake_master_project(tmp_path / "good")
    )
    meta_before = (fake_masters_dir / "stm32.json").read_text(encoding="utf-8")
    broken = make_fake_master_project(tmp_path / "broken")
    (broken / "project.uvprojx").unlink()

    with pytest.raises(MasterError, match=".uvprojx"):
        import_master(fake_masters_dir, PLATFORM_STM32, broken)

    # 分析失败不落任何文件，既有母版与其元数据完好
    assert (fake_masters_dir / "stm32.json").read_text(encoding="utf-8") == meta_before
    assert (fake_masters_dir / "stm32" / "main.c").is_file()


def test_list_masters_sorted_by_platform(fake_stm32_projects, fake_masters_dir, tmp_path):
    import_master(fake_masters_dir, PLATFORM_STM32, fake_stm32_projects[0])
    import_master(
        fake_masters_dir,
        PLATFORM_MSPM0,
        make_fake_ccs_master_project(tmp_path / "ccs_src"),
    )

    metas = list_masters(fake_masters_dir)

    assert [m.platform for m in metas] == [PLATFORM_MSPM0, PLATFORM_STM32]


def test_list_masters_empty_when_dir_missing(tmp_path):
    assert list_masters(tmp_path / "nope") == []


def test_get_master_missing_raises(fake_masters_dir):
    with pytest.raises(MasterError, match="不存在"):
        get_master(fake_masters_dir, "stm32")


def test_get_master_rejects_path_traversal(fake_masters_dir):
    with pytest.raises(MasterError, match="非法平台名"):
        get_master(fake_masters_dir, "../evil")


def test_get_master_corrupt_meta_raises(fake_masters_dir, tmp_path):
    import_master(
        fake_masters_dir, PLATFORM_STM32, make_fake_master_project(tmp_path / "src")
    )
    (fake_masters_dir / "stm32.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(MasterError, match="元数据"):
        get_master(fake_masters_dir, "stm32")


def test_delete_master_removes_dir_and_meta(fake_masters_dir, tmp_path):
    import_master(
        fake_masters_dir, PLATFORM_STM32, make_fake_master_project(tmp_path / "src")
    )

    delete_master(fake_masters_dir, "stm32")

    assert not (fake_masters_dir / "stm32").exists()
    assert not (fake_masters_dir / "stm32.json").exists()
    assert list_masters(fake_masters_dir) == []


def test_delete_master_missing_raises(fake_masters_dir):
    with pytest.raises(MasterError, match="不存在"):
        delete_master(fake_masters_dir, "stm32")


# ---------------------------------------------------------------------------
# 端到端：导入 → 提炼 → 确认 → 入库
# ---------------------------------------------------------------------------


def test_full_distillation_flow(fake_stm32_projects, fake_masters_dir, tmp_path):
    projects = _projects(fake_stm32_projects)
    report = distill_master(FakeLLM(distillation=DEFAULT_DECISIONS), PLATFORM_STM32, projects)
    preview = apply_distillation(report, compare_projects(projects), tmp_path / "preview")

    meta = import_master(
        fake_masters_dir, PLATFORM_STM32, preview, sources=report.projects
    )

    assert meta.platform == PLATFORM_STM32
    stored = fake_masters_dir / "stm32"
    # 母版 main.c = 确定性模板，旧工程 main.c 不进母版（ADR 0002）
    assert (stored / "main.c").is_file()
    assert (stored / "main.c").read_text(encoding="utf-8") == main_c_template(
        PLATFORM_STM32
    )
    assert "proj-a 的赛题 main" not in (stored / "main.c").read_text(encoding="utf-8")
    assert (stored / "sensors/dht11.c").is_file()
    assert not (stored / "ui/oled_fonts.c").exists()
    # 母版可被生成器使用：结构分析通过（.uvprojx = 确定性渲染产物在 user/ 下）
    assert (stored / "user" / "Project.uvprojx").is_file()
    assert any(stored.rglob("*.uvprojx"))
