"""母版提炼核心：扫描 / 对比 / AI 提炼报告 / 确认落盘 / 结构分析 / 母版库。

用 conftest 的假旧工程（proj-a / proj-b 同平台对）与假 LLM 驱动，断言报告
结构与确认流程落盘的磁盘结果（外部行为）。
"""

import shutil
from dataclasses import replace

import pytest

from contest_generator.llm import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    FileDecision,
)
from contest_generator.master import (
    DistillationReport,
    MasterError,
    analyze_structure,
    apply_distillation,
    build_comparison_summary,
    build_judgment_files,
    compare_projects,
    delete_master,
    distill_master,
    get_master,
    import_master,
    list_masters,
    scan_project,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from tests.fakes import (
    FAKE_DISTILL_UVPROJX_B,
    FakeLLM,
    make_fake_ccs_master_project,
    make_fake_master_project,
)

# 假工程对的判定范围（冲突 + 独有）与一份典型 AI 判定
DEFAULT_DECISIONS = (
    FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用传感器驱动，应进母版"),
    FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="上一场比赛的字体表残留"),
    FileDecision("project.uvprojx", ACTION_MERGE, source="proj-a", reason="include path 更全"),
    FileDecision("src/oled.c", ACTION_MERGE, source="proj-b", reason="B 版本较新"),
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
    proj_a, proj_b = fake_stm32_projects

    structure_a = scan_project(proj_a)
    structure_b = scan_project(proj_b)

    assert structure_a.name == "proj-a"
    assert structure_a.platform == PLATFORM_STM32
    assert structure_a.files == (
        "inc/stm32f10x_conf.h",
        "main.c",
        "project.uvprojx",
        "sensors/dht11.c",
        "src/oled.c",
        "src/system_stm32f10x.c",
    )
    # 公共文件在两个工程里内容哈希一致
    assert structure_a.file_hashes["main.c"] == structure_b.file_hashes["main.c"]
    # .git 与构建产物目录不进清单
    assert ".git/HEAD" not in structure_a.files
    assert "Debug/out.axf" not in structure_a.files


def test_scan_ignores_build_artifacts_in_other_project(fake_stm32_projects):
    structure_b = scan_project(fake_stm32_projects[1])

    assert ".git/HEAD" not in structure_b.files
    assert "Release/oled.o" not in structure_b.files


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
        "main.c",
        "src/system_stm32f10x.c",
    )
    assert comparison.conflicts == ("project.uvprojx", "src/oled.c")
    assert comparison.unique == ("sensors/dht11.c", "ui/oled_fonts.c")


def test_compare_records_which_projects_hold_each_path(fake_stm32_projects):
    comparison = _comparison(fake_stm32_projects)

    assert comparison.by_path["main.c"] == ("proj-a", "proj-b")
    assert comparison.by_path["sensors/dht11.c"] == ("proj-a",)
    assert comparison.by_path["ui/oled_fonts.c"] == ("proj-b",)


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
    # 公共文件确定保留，且排在最前；AI 判定跟随其后
    assert [d.path for d in report.keep] == [
        "inc/stm32f10x_conf.h",
        "main.c",
        "src/system_stm32f10x.c",
        "sensors/dht11.c",
    ]
    assert report.keep[0].reason == "所有导入工程内容一致，属公共骨架"
    assert [d.path for d in report.merge] == ["project.uvprojx", "src/oled.c"]
    assert report.merge[0].source == "proj-a"
    assert [d.path for d in report.exclude] == ["ui/oled_fonts.c"]
    assert "残留" in report.exclude[0].reason


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
        FileDecision("main.c", ACTION_KEEP, reason="公共骨架，应保留"),
    )

    report = _distill(fake_stm32_projects, FakeLLM(distillation=decisions))

    assert [d.path for d in report.keep].count("main.c") == 1


def test_distill_rejects_merge_on_common_path(fake_stm32_projects):
    """公共文件判定 merge / exclude 是错误——公共文件必须保留。"""
    decisions = DEFAULT_DECISIONS + (
        FileDecision("main.c", ACTION_MERGE, source="proj-a", reason="取 proj-a 版本"),
    )

    with pytest.raises(MasterError, match="公共文件必须保留"):
        _distill(fake_stm32_projects, FakeLLM(distillation=decisions))


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
    assert (output / "main.c").read_text(encoding="utf-8").startswith("#include")
    assert (output / "sensors/dht11.c").is_file()
    # merge：project.uvprojx 取 proj-a（include path 更全），oled.c 取 proj-b
    assert ".\\inc;.\\src" in (output / "project.uvprojx").read_text(encoding="utf-8")
    assert "B 版本" in (output / "src/oled.c").read_text(encoding="utf-8")
    # exclude：不复制
    assert not (output / "ui/oled_fonts.c").exists()


def test_apply_user_edited_merge_source_wins(fake_stm32_projects, tmp_path):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    # 用户确认时把 oled.c 的来源从 proj-b 改成 proj-a
    report = replace(
        report,
        merge=tuple(
            replace(d, source="proj-a") if d.path == "src/oled.c" else d
            for d in report.merge
        ),
    )
    output = tmp_path / "preview"

    apply_distillation(report, _comparison(fake_stm32_projects), output)

    assert "A 版本" in (output / "src/oled.c").read_text(encoding="utf-8")


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


def test_distill_rejects_merge_source_without_the_file(fake_stm32_projects):
    # proj-b 里没有 sensors/dht11.c，选它作来源在确认前就必须被拦截
    bad = tuple(
        FileDecision(d.path, ACTION_MERGE, "proj-b", d.reason)
        if d.path == "sensors/dht11.c"
        else d
        for d in DEFAULT_DECISIONS
    )

    with pytest.raises(MasterError, match="不含文件"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))


def test_distill_rejects_conflict_classified_as_keep(fake_stm32_projects):
    # 冲突文件（同路径不同内容）必须 merge 指定来源；keep 没有"取哪份"的信息
    bad = tuple(
        FileDecision(d.path, ACTION_KEEP, reason="两版都可")
        if d.path == "src/oled.c"
        else d
        for d in DEFAULT_DECISIONS
    )

    with pytest.raises(MasterError, match="必须指定来源工程"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))


def test_report_round_trips_through_json(fake_stm32_projects):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))

    rebuilt = DistillationReport.from_dict(report.to_dict())

    assert rebuilt == report
    # wire format 形状：确认请求按 to_dict 输出原样回传
    data = report.to_dict()
    assert set(data) == {"platform", "projects", "keep", "merge", "exclude"}
    assert data["keep"][0] == {
        "path": "inc/stm32f10x_conf.h",
        "action": ACTION_KEEP,
        "source": "",
        "reason": "所有导入工程内容一致，属公共骨架",
    }
    assert data["merge"][0]["source"] == "proj-a"


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


def test_apply_rejects_user_edited_bad_merge_source(fake_stm32_projects, tmp_path):
    # 报告本身没问题，但用户确认时把独有文件改成 merge、来源却是不含它的工程
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    report = replace(
        report,
        keep=tuple(d for d in report.keep if d.path != "sensors/dht11.c"),
        merge=(
            *report.merge,
            FileDecision("sensors/dht11.c", ACTION_MERGE, "proj-b", reason="用户改的"),
        ),
    )

    with pytest.raises(MasterError, match="不含文件"):
        apply_distillation(report, _comparison(fake_stm32_projects), tmp_path / "preview")


def test_apply_rejects_comparison_mismatch(fake_stm32_projects, tmp_path):
    report = _distill(fake_stm32_projects, FakeLLM(distillation=DEFAULT_DECISIONS))
    wrong_comparison = compare_projects([scan_project(fake_stm32_projects[0])])

    with pytest.raises(MasterError, match="不匹配"):
        apply_distillation(report, wrong_comparison, tmp_path / "preview")


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
    assert (stored / "main.c").is_file()
    assert (stored / "sensors/dht11.c").is_file()
    assert not (stored / "ui/oled_fonts.c").exists()
    # 母版可被生成器使用：结构分析通过（含 .uvprojx）
    assert any(stored.glob("*.uvprojx"))
