"""文件类别生命周期：识别规则（残留 / 旧 main.c / 基础设施 / 二进制 / 工程
配置文件）+ 类别表（RULE_CATEGORIES）+ 扫描分类 + 启动文件跨工程去重。

工单 01 三轴拆块：用例自 test_master.py 随迁（语义断言零变化），类别概念
唯一出处 = categories.py。结构测试兜底防回退：master 只消费不定义。
"""

import dataclasses
from dataclasses import replace
from pathlib import Path

import pytest

from contest_generator.categories import (
    BINARY_FILE_REASON,
    CCS_CONFIG_REASON,
    MAIN_C_TEMPLATE_REASON,
    RULE_CATEGORIES,
    STARTUP_REPLACEMENT_REASON,
    UVPROJX_CONFIG_REASON,
    _CONFIG_FILE_SUFFIX_REASONS,
    config_file_reason,
    residue_reason,
)
from contest_generator.master import (
    ProjectComparison,
    ProjectStructure,
    apply_distillation,
    compare_projects,
    distill_master,
    scan_project,
)
from contest_generator.master_store import MasterError
from contest_generator.platforms import PLATFORM_CONFIG_FILE_SUFFIXES, PLATFORM_STM32
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
# 结构测试（防回退，先例 errors.py 防漏登）：master 只消费不定义
# ---------------------------------------------------------------------------


def test_master_consumes_categories_without_redefining():
    """master 不再自持类别定义：RULE_CATEGORIES 恒等引用 categories，
    规则函数一个不剩（工单 01：类别表与 classify 收进 categories.py）。"""
    import contest_generator.categories as categories
    import contest_generator.master as master

    assert master.RULE_CATEGORIES is categories.RULE_CATEGORIES
    for name in (
        "residue_reason",
        "main_c_reason",
        "infrastructure_reason",
        "config_file_reason",
    ):
        assert not hasattr(master, name)


def test_categories_startup_predicates_go_through_adapter():
    """启动谓词不再直连 keil（工单 04）：categories 模块级无谓词属性、无
    平台识别死常量（CONFIG_FILE_SUFFIXES 已删，后缀表单源 platforms.py）；
    谓词调用发生在蒸馏适配器实例上（模块无属性 = 结构防回退）。"""
    import contest_generator.categories as categories

    for name in ("is_startup_candidate", "is_md_startup", "CONFIG_FILE_SUFFIXES"):
        assert not hasattr(categories, name)


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


def test_config_file_reason_suffix_reasons_derived_from_platform_table():
    """表消费：后缀 → 原因映射由 PLATFORM_CONFIG_FILE_SUFFIXES 推导，无硬编码拷贝。

    工单 03：.uvprojx/.cproject/.project 字面量不再散落 categories 规则，
    新增平台 = 表加行 + 平台→原因一行（_CONFIG_FILE_SUFFIX_REASONS）。
    """
    assert set(_CONFIG_FILE_SUFFIX_REASONS) == {
        suffix
        for suffixes in PLATFORM_CONFIG_FILE_SUFFIXES.values()
        for suffix in suffixes
    }
    assert _CONFIG_FILE_SUFFIX_REASONS[".uvprojx"] == UVPROJX_CONFIG_REASON
    assert _CONFIG_FILE_SUFFIX_REASONS[".cproject"] == CCS_CONFIG_REASON
    assert _CONFIG_FILE_SUFFIX_REASONS[".project"] == CCS_CONFIG_REASON


@pytest.mark.parametrize(
    ("rel_path", "reason"),
    [
        ("project.uvprojx", UVPROJX_CONFIG_REASON),
        ("USER/Project.UVPROJX", UVPROJX_CONFIG_REASON),  # 大小写不敏感保持
        ("project.cproject", CCS_CONFIG_REASON),
        ("proj/.project", CCS_CONFIG_REASON),
        ("main.c", None),
        ("x.uvprojx.tmp", None),  # 整段 endswith，非中间包含
        ("", None),
    ],
)
def test_config_file_reason_verbatim(rel_path, reason):
    """行为逐字（工单 03 表消费后）：按后缀判定、大小写不敏感、返回规则化原因。"""
    assert config_file_reason(rel_path) == reason


# ---------------------------------------------------------------------------
# 扫描分类：残留 / 二进制 / 旧 main.c / 基础设施
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 类别文件不进 AI 判定素材：越界即报错，报告带规则化原因
# ---------------------------------------------------------------------------


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


def test_distill_rejects_ai_decision_on_residue(fake_stm32_projects):
    """残留由规则确定性剔除，AI 判定残留路径是越界——宁可大声失败。"""
    bad = (*DEFAULT_DECISIONS, FileDecision("src/oled.o", ACTION_EXCLUDE, reason="AI 也判残留"))

    with pytest.raises(MasterError, match="无需 AI 判定"):
        _distill(fake_stm32_projects, FakeLLM(distillation=bad))


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


# ---------------------------------------------------------------------------
# 启动文件跨工程去重（决策 2）：同一器件只需一份启动文件
# ---------------------------------------------------------------------------


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
    编译的母版。守卫错误在蒸馏适配器缝内翻译归 MasterError（工单 04，
    message 原样，HTTP 层 MasterError 同映射 400）。"""
    (fake_stm32_projects[0] / "startup_stm32f10x_hd.s").write_text(
        "; A", encoding="utf-8"
    )
    (fake_stm32_projects[1] / "startup_stm32f10x_vd.s").write_text(
        "; B", encoding="utf-8"
    )

    with pytest.raises(MasterError, match="STM32F103C8T6"):
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
