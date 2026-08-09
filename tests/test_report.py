"""判定模型：判定素材（JudgmentFile/FileVersion）的形状与不变量测试。

条目与容器（FileDecision / DistillationReport）的形状校验测试在 test_llm
（AI 解析路径）与 test_master（报告拼装 / 确认路径）；本文件只测素材模型的
版本分组不变量——分组是模型唯一声明的不变量，手工构造带病素材必须大声失败。
结构自证：扫描/对比模型（ProjectStructure / ProjectComparison）定义单址
report.py，master↔archive 依赖环已拆（master 对 archive 保留函数级延迟导入，
链约束非环）。
"""

from pathlib import Path

import pytest

from contest_generator.report import FileVersion, JudgmentFile, ReportError


def test_version_groups_returns_disjoint_groups():
    """版本分组：每个内容版本一组持有工程名（内容一致的工程合并为一个版本）。"""
    file = JudgmentFile(
        "sensors/dht11.c",
        (
            FileVersion(content="/* 版 A */", projects=("proj-a",)),
            FileVersion(content="/* 版 B */", projects=("proj-b", "proj-c")),
        ),
    )

    assert file.version_groups == (frozenset({"proj-a"}), frozenset({"proj-b", "proj-c"}))


def test_judgment_file_rejects_empty_versions():
    """没有内容版本的素材无意义（AI 无内容可读）——构造即大声失败。"""
    with pytest.raises(ReportError, match="缺少内容版本"):
        JudgmentFile("sensors/dht11.c", ())


def test_judgment_file_rejects_version_without_projects():
    """内容版本必须至少有一个持有工程。"""
    with pytest.raises(ReportError, match="无持有工程"):
        JudgmentFile(
            "sensors/dht11.c",
            (FileVersion(content="/* 版 A */", projects=()),),
        )


def test_judgment_file_rejects_overlapping_version_groups():
    """版本分组不变量：一个工程在同一路径只有一个内容版本，组间不得重叠。

    重叠说明素材构造器按内容哈希分组失败（或手工拼错），解析词表 /
    合并拆分都会拿错分组——构造时拦截。
    """
    with pytest.raises(ReportError, match="工程名重叠"):
        JudgmentFile(
            "sensors/dht11.c",
            (
                FileVersion(content="/* 版 A */", projects=("proj-a", "proj-b")),
                FileVersion(content="/* 版 B */", projects=("proj-b",)),
            ),
        )


# ---------------------------------------------------------------------------
# 结构自证（grep 式先例，见 test_include_contract.py）：扫描/对比模型单址
# report.py + master↔archive 依赖环已拆
# ---------------------------------------------------------------------------


def test_scan_compare_models_single_origin():
    """ProjectStructure / ProjectComparison 定义单址 = report.py。"""
    import contest_generator.report as report

    src_root = Path(report.__file__).parent
    for model in ("ProjectStructure", "ProjectComparison"):
        hits = [
            path.name
            for path in sorted(src_root.glob("*.py"))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith(f"class {model}")
        ]
        assert hits == ["report.py"], f"{model} 应单址 report.py"


def test_master_archive_cycle_broken():
    """环已拆：archive 无 from .master import；master 无 class 定义。

    master 对 archive 的函数级延迟导入（confirm_distillation 内）保留——链
    约束（master 不 import 参考库族，工单 C3），非避环；master 模块级零 class
    （MasterError 在 master_store.py）。
    """
    import contest_generator.archive as archive
    import contest_generator.master as master

    archive_text = Path(archive.__file__).read_text(encoding="utf-8")
    assert "from .master import" not in archive_text
    master_text = Path(master.__file__).read_text(encoding="utf-8")
    assert not [
        line
        for line in master_text.splitlines()
        if line.startswith("class ")
    ], "master 不应有模块级 class 定义"
