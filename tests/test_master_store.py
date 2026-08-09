"""母版库 CRUD（入库 / 浏览 / 删除）与入库前结构分析（工单 01 随迁）。

用例自 test_master.py 随迁（语义断言零变化），母版库 CRUD 唯一出处 =
master_store.py；蒸馏编排用例留在 test_master.py。
"""

import os
import sys
from pathlib import Path

import pytest

from contest_generator.master import (
    apply_distillation,
    compare_projects,
    distill_master,
    scan_project,
)
from contest_generator.master_store import (
    MasterError,
    analyze_structure,
    delete_master,
    get_master,
    import_master,
    list_masters,
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


def _comparison(fake_stm32_projects):
    return compare_projects(_projects(fake_stm32_projects))


def _distill(fake_stm32_projects, llm):
    return distill_master(llm, PLATFORM_STM32, _projects(fake_stm32_projects))


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
# 结构测试（防回退，先例 errors.py 防漏登）：配置文件后缀表单源 platforms.py
# ---------------------------------------------------------------------------


def test_master_store_no_config_file_suffix_table():
    """工程配置文件后缀表单源 platforms.PLATFORM_CONFIG_FILE_SUFFIXES
    （工单 04）：master_store 不再自持 PLATFORM_CONFIG_FILES。"""
    import contest_generator.master_store as master_store

    assert not hasattr(master_store, "PLATFORM_CONFIG_FILES")
