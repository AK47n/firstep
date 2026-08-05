"""母版提炼核心：扫描 / 对比 / AI 提炼报告 / 确认落盘 / 结构分析 / 母版库。

用 conftest 的假旧工程（proj-a / proj-b 同平台对）与假 LLM 驱动，断言报告
结构与确认流程落盘的磁盘结果（外部行为）。
"""

import shutil
from dataclasses import replace

import pytest

from contest_generator.master import (
    DistillationReport,
    MAIN_C_TEMPLATE_REASON,
    MasterError,
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
    scan_project,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    FileDecision,
)
from tests.fakes import (
    FAKE_DISTILL_UVPROJX_A,
    FAKE_DISTILL_UVPROJX_B,
    FakeLLM,
    make_fake_ccs_master_project,
    make_fake_master_project,
)

# 假工程对的判定范围（冲突 + 独有）与一份典型 AI 判定
# merge 携带整合产物全文（content）+ 整合说明（explanation）；选一份只是特例
MERGED_UVPROJX = FAKE_DISTILL_UVPROJX_A  # 特例：直接取 A 的全文，说明为何选它
MERGED_OLED = "/* 通用 OLED 驱动（整合版） */\nvoid oled_init(void);\n"
DEFAULT_DECISIONS = (
    FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用传感器驱动，应进母版"),
    FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="上一场比赛的字体表残留"),
    FileDecision(
        "project.uvprojx",
        ACTION_MERGE,
        content=MERGED_UVPROJX,
        explanation="取 include path 更全的 A 版本",
        source="proj-a",
        reason="include path 更全",
    ),
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


def _comparison(fake_stm32_projects):
    return compare_projects(_projects(fake_stm32_projects))


def _distill(fake_stm32_projects, llm):
    return distill_master(llm, PLATFORM_STM32, _projects(fake_stm32_projects))


# ---------------------------------------------------------------------------
# 扫描
# ---------------------------------------------------------------------------


def test_scan_detects_platform_and_lists_files(fake_stm32_projects):
    structure_a = scan_project(fake_stm32_projects[0])

    assert structure_a.name == "proj-a"
    assert structure_a.platform == PLATFORM_STM32
    assert structure_a.files == (
        "inc/stm32f10x_conf.h",
        "project.uvprojx",
        "sensors/dht11.c",
        "src/oled.c",
        "src/system_stm32f10x.c",
    )
    # 旧工程 main.c 单独记录（模板替代，ADR 0002），不进扫描清单也不读内容
    assert structure_a.main_c_files == ("main.c",)
    assert "main.c" not in structure_a.files
    assert "main.c" not in structure_a.file_hashes
    # .git 与构建产物目录不进清单
    assert ".git/HEAD" not in structure_a.files
    assert "Debug/out.axf" not in structure_a.files
    # 源码树内的残留单独记录、不进扫描清单也不读内容
    assert structure_a.residues == ("main.c.bak", "src/oled.o")
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
    assert structure.files == ("project.uvprojx", "src/real.c", "src/real.c.orig")


def test_scan_detects_ccs_platform(tmp_path):
    structure = scan_project(make_fake_ccs_master_project(tmp_path / "ccs_proj"))

    assert structure.platform == PLATFORM_MSPM0
    assert "project.cproject" in structure.files
    assert ".project" in structure.files


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
    assert "USER/project.uvprojx" in structure.files
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


# ---------------------------------------------------------------------------
# 对比
# ---------------------------------------------------------------------------


def test_compare_classifies_common_conflict_unique(fake_stm32_projects):
    comparison = _comparison(fake_stm32_projects)

    assert comparison.common == (
        "inc/stm32f10x_conf.h",
        "src/system_stm32f10x.c",
    )
    assert comparison.conflicts == ("project.uvprojx", "src/oled.c")
    assert comparison.unique == ("sensors/dht11.c", "ui/oled_fonts.c")
    # 旧工程 main.c 由模板替代：不进公共 / 冲突 / 独有分类，也就进不了 AI 判定
    assert comparison.main_c_files == ("main.c",)


def test_compare_records_which_projects_hold_each_path(fake_stm32_projects):
    comparison = _comparison(fake_stm32_projects)

    assert "main.c" not in comparison.by_path
    assert comparison.by_path["sensors/dht11.c"] == ("proj-a",)
    assert comparison.by_path["ui/oled_fonts.c"] == ("proj-b",)


def test_compare_unions_residues_across_projects(fake_stm32_projects):
    comparison = _comparison(fake_stm32_projects)

    assert comparison.residues == (
        "main.c.bak",
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

    for path in ("project.uvprojx", "src/oled.c", "sensors/dht11.c", "ui/oled_fonts.c"):
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
    # 公共文件确定保留，且排在最前；AI 判定跟随其后；main.c 不进 keep
    assert [d.path for d in report.keep] == [
        "inc/stm32f10x_conf.h",
        "src/system_stm32f10x.c",
        "sensors/dht11.c",
    ]
    assert report.keep[0].reason == "所有导入工程内容一致，属公共骨架"
    assert [d.path for d in report.merge] == ["project.uvprojx", "src/oled.c"]
    assert report.merge[0].source == "proj-a"
    # exclude = AI 判定（ui/oled_fonts.c）+ 规则识别的残留（确定性、排序）
    # + 旧工程 main.c（模板替代，规则化原因）
    assert [d.path for d in report.exclude] == [
        "ui/oled_fonts.c",
        "main.c.bak",
        "src/oled.hex",
        "src/oled.o",
        "ui/oled_fonts.c~",
        "main.c",
    ]
    assert "残留" in report.exclude[0].reason
    assert report.exclude[-1].reason == MAIN_C_TEMPLATE_REASON


def test_distill_passes_platform_names_and_summary_to_llm(fake_stm32_projects):
    llm = FakeLLM(distillation=DEFAULT_DECISIONS)

    _distill(fake_stm32_projects, llm)

    platform, names, judgment_files, summary = llm.distill_calls[0]
    assert platform == PLATFORM_STM32
    assert names == ("proj-a", "proj-b")
    assert "src/oled.c" in summary
    # 判定素材覆盖冲突 + 独有，含全文与持有工程；公共文件不传给 AI
    by_path = {f.path: f for f in judgment_files}
    assert set(by_path) == {
        "project.uvprojx",
        "src/oled.c",
        "sensors/dht11.c",
        "ui/oled_fonts.c",
    }
    oled_versions = by_path["src/oled.c"].versions
    assert len(oled_versions) == 2  # 冲突文件两个版本都传
    assert {v.projects for v in oled_versions} == {("proj-a",), ("proj-b",)}
    assert any("A 版本" in v.content for v in oled_versions)
    assert any("B 版本" in v.content for v in oled_versions)
    assert by_path["sensors/dht11.c"].versions[0].projects == ("proj-a",)
    assert "DHT11" in by_path["sensors/dht11.c"].versions[0].content
    assert by_path["ui/oled_fonts.c"].versions[0].projects == ("proj-b",)


def test_residues_never_reach_ai_material(fake_stm32_projects):
    """残留不进 AI 判定范围、不进两阶段摘要——AI 只看到冲突与独有文件。"""
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


def test_distill_ignores_ai_keep_on_common_path(fake_stm32_projects):
    """AI 把公共文件也判定 keep 时按冗余忽略，不中断提炼（现实 LLM 常见回显）。"""
    decisions = DEFAULT_DECISIONS + (
        FileDecision("inc/stm32f10x_conf.h", ACTION_KEEP, reason="公共骨架，应保留"),
    )

    report = _distill(fake_stm32_projects, FakeLLM(distillation=decisions))

    assert [d.path for d in report.keep].count("inc/stm32f10x_conf.h") == 1


def test_distill_rejects_merge_on_common_path(fake_stm32_projects):
    """公共文件判定 merge / exclude 是错误——公共文件必须保留。"""
    decisions = DEFAULT_DECISIONS + (
        FileDecision(
            "inc/stm32f10x_conf.h", ACTION_MERGE, source="proj-a", reason="取 proj-a 版本"
        ),
    )

    with pytest.raises(MasterError, match="公共文件必须保留"):
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
    # AI 漏判了两个冲突文件（只剩 keep 与 exclude）
    partial = tuple(d for d in DEFAULT_DECISIONS if d.action != ACTION_MERGE)
    llm = FakeLLM(distillation=partial)

    with pytest.raises(MasterError, match="缺少判定.*project.uvprojx"):
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
    assert (output / "project.uvprojx").read_text(encoding="utf-8") == MERGED_UVPROJX
    assert (output / "src/oled.c").read_text(encoding="utf-8") == MERGED_OLED
    assert "B 版本" not in (output / "src/oled.c").read_text(encoding="utf-8")
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

    rebuilt = DistillationReport.from_dict(report.to_dict())

    assert rebuilt == report
    # wire format 形状：确认请求按 to_dict 输出原样回传
    data = report.to_dict()
    assert set(data) == {"platform", "projects", "keep", "merge", "exclude",
                         "main_c_preview"}
    assert data["keep"][0] == {
        "path": "inc/stm32f10x_conf.h",
        "action": ACTION_KEEP,
        "content": "",
        "explanation": "",
        "source": "",
        "reason": "所有导入工程内容一致，属公共骨架",
    }
    assert data["merge"][0]["source"] == "proj-a"
    assert data["merge"][0]["content"] == MERGED_UVPROJX
    assert data["merge"][0]["explanation"]


def test_distill_report_carries_template_main_c_preview(fake_stm32_projects):
    """报告携带模板 main.c 全文预览：用户一次确认前能看到将要写入母版的 main.c。"""
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))

    assert report.main_c_preview == main_c_template(PLATFORM_STM32)
    assert report.main_c_preview  # 非空全文


def test_report_from_dict_derives_preview_from_platform(fake_stm32_projects):
    """确认请求回传的预览不可信：from_dict 按平台重推导，保证预览 = 实际落盘内容。

    预览是确定性展示素材（落盘永远写 main_c_template(platform)），客户端改它
    不会影响落盘内容，重推导保证报告自洽。
    """
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    data = report.to_dict()
    data["main_c_preview"] = "/* 伪造的预览 */"

    rebuilt = DistillationReport.from_dict(data)

    assert rebuilt.main_c_preview == main_c_template(PLATFORM_STM32)
    assert rebuilt.main_c_preview != "/* 伪造的预览 */"


def test_report_from_dict_rejects_malformed(fake_stm32_projects):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    data = report.to_dict()

    bad_cases = [
        "not a dict",
        {**data, "platform": ""},  # 缺平台
        {**data, "projects": []},  # 缺来源工程
        {**data, "keep": "not a list"},
        {**data, "merge": [{"path": "a.c", "action": "archive"}]},  # 条目形状非法
    ]
    for bad in bad_cases:
        with pytest.raises(MasterError):
            DistillationReport.from_dict(bad)


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
    # stm32：Keil 标准外设库风格，时钟初始化 SystemInit
    assert "stm32f10x_conf.h" in stm32
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

    report = distill_master(FakeLLM(distillation=()), PLATFORM_MSPM0, projects)
    output = tmp_path / "preview"
    apply_distillation(report, compare_projects(projects), output)

    content = (output / "main.c").read_text(encoding="utf-8")
    assert content == main_c_template(PLATFORM_MSPM0)
    assert "master's old main" not in content
    assert analyze_structure(output, PLATFORM_MSPM0).warnings == ()


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
    """工程文件在子目录时结构分析同样通过。"""
    master = tmp_path / "master"
    (master / "USER").mkdir(parents=True)
    (master / "USER" / "project.uvprojx").write_text("<Project/>", encoding="utf-8")

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
    # 工程文件就位，元数据在母版目录外的平级文件（不污染生成的工程）
    assert (fake_masters_dir / "stm32" / "main.c").is_file()
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
    # 母版可被生成器使用：结构分析通过（含 .uvprojx）
    assert any(stored.glob("*.uvprojx"))
