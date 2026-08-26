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
    import_master_direct,
    list_masters,
    master_health,
    master_key_files,
    master_stats,
    master_tree_files,
    read_master_file,
    read_master_tree_file,
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
    make_fake_ccs_theia_master_project,
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


def test_import_mspm0_theia_master_analyzes_clean(fake_masters_dir, tmp_path):
    """Theia 20.5 母版入库：结构分析无警告（整理后无构建产物目录），
    sources 元数据 = TI 示例工程名，工程文件就位（首个真机 mspm0 母版）。"""
    source = make_fake_ccs_theia_master_project(tmp_path / "theia_src")

    meta = import_master(
        fake_masters_dir,
        PLATFORM_MSPM0,
        source,
        sources=("empty_LP_MSPM0G3507_nortos_ticlang",),
    )

    assert meta.platform == PLATFORM_MSPM0
    assert meta.warnings == ()
    assert meta.sources == ("empty_LP_MSPM0G3507_nortos_ticlang",)
    imported = fake_masters_dir / "mspm0"
    assert (imported / "project.cproject").is_file()
    assert (imported / ".project").is_file()
    assert (imported / "main.c").is_file()
    assert (imported / "mspm0.syscfg").is_file()
    assert (fake_masters_dir / "mspm0.json").is_file()


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
# 关键文件目录（工单 master-library-ui/01）：白名单单源 + 磁盘实况
# ---------------------------------------------------------------------------


def _make_stm32_master_with_key_files(masters_dir: Path) -> None:
    """手工搭一个与真实母版同布局的关键文件目录（stm32：根级 main.c /
    pin_config.h / led_instances.h + user/Project.uvprojx）。

    不经 import_master：假 .uvprojx 的源码引用是根级相对路径（.\main.c 等），
    真实布局下用户子目录会触发结构校验的引用缺失——白名单目录函数只吃目录
    实况，不依赖元数据与结构校验。
    """
    master = masters_dir / "stm32"
    (master / "user").mkdir(parents=True)
    (master / "main.c").write_text("/* master's old main */\n", encoding="utf-8")
    (master / "pin_config.h").write_text("/* board pins */\n", encoding="utf-8")
    (master / "led_instances.h").write_text("/* led channels */\n", encoding="utf-8")
    (master / "user" / "Project.uvprojx").write_text("/* keil */\n", encoding="utf-8")


def test_master_key_files_stm32_catalog_with_exists_and_size(fake_masters_dir, tmp_path):
    _make_stm32_master_with_key_files(fake_masters_dir)

    infos = master_key_files(fake_masters_dir, PLATFORM_STM32)

    assert [i.path for i in infos] == [
        "main.c",
        "pin_config.h",
        "led_instances.h",
        "user/Project.uvprojx",
    ]
    assert [i.label for i in infos] == [
        "模板 main.c",
        "板级引脚宏",
        "LED 多实例通道宏",
        "Keil 工程配置",
    ]
    assert all(i.exists for i in infos)
    assert all(i.size_bytes > 0 for i in infos)
    assert infos[0].size_bytes == (fake_masters_dir / "stm32" / "main.c").stat().st_size


def test_master_key_files_missing_file_flags_false(fake_masters_dir, tmp_path):
    _make_stm32_master_with_key_files(fake_masters_dir)
    (fake_masters_dir / "stm32" / "pin_config.h").unlink()

    infos = master_key_files(fake_masters_dir, PLATFORM_STM32)

    assert not infos[1].exists
    assert infos[1].size_bytes == 0


def test_master_key_files_mspm0_catalog(fake_masters_dir, tmp_path):
    master = make_fake_ccs_theia_master_project(tmp_path / "theia_src")
    (master / ".cproject").write_text("/* ccs config */\n", encoding="utf-8")
    import_master(fake_masters_dir, PLATFORM_MSPM0, master)

    infos = master_key_files(fake_masters_dir, PLATFORM_MSPM0)

    assert [i.path for i in infos] == ["main.c", "mspm0.syscfg", ".cproject"]
    assert all(i.exists for i in infos)
    assert infos[2].label == "CCS 工程配置"


def test_master_key_files_mspm0_whitelist_path_not_present_false(fake_masters_dir, tmp_path):
    """假 Theia 母版只写 project.cproject（非白名单点文件 .cproject）→ 缺失标注。"""
    import_master(
        fake_masters_dir,
        PLATFORM_MSPM0,
        make_fake_ccs_theia_master_project(tmp_path / "theia_src"),
    )

    infos = master_key_files(fake_masters_dir, PLATFORM_MSPM0)

    assert infos[2].path == ".cproject"
    assert not infos[2].exists


def test_master_key_files_platform_not_in_library_raises(fake_masters_dir):
    with pytest.raises(MasterError, match="不存在"):
        master_key_files(fake_masters_dir, PLATFORM_STM32)


def test_master_key_files_unknown_platform_raises(fake_masters_dir):
    (fake_masters_dir / "vxworks").mkdir(parents=True)

    with pytest.raises(MasterError, match="未知平台"):
        master_key_files(fake_masters_dir, "vxworks")


def test_master_key_files_missing_catalog_raises(fake_masters_dir, monkeypatch):
    """已知平台没配白名单 = 开发错误（platforms.py 与白名单不同模块，漏配是
    真实风险）：大声失败，绝不静默回空清单误导浏览（评审修正）。"""
    _make_stm32_master_with_key_files(fake_masters_dir)
    monkeypatch.setattr(
        "contest_generator.master_store.MASTER_KEY_FILES", {PLATFORM_MSPM0: ()}
    )

    with pytest.raises(MasterError, match="白名单未配置"):
        master_key_files(fake_masters_dir, PLATFORM_STM32)


def test_master_key_files_rejects_path_traversal(fake_masters_dir):
    with pytest.raises(MasterError, match="非法平台名"):
        master_key_files(fake_masters_dir, "../evil")


# ---------------------------------------------------------------------------
# 关键文件内容（工单 master-library-ui/02）：白名单墙按需读取
# ---------------------------------------------------------------------------


def test_read_master_file_returns_content_with_meta(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)
    disk = fake_masters_dir / "stm32" / "pin_config.h"

    result = read_master_file(fake_masters_dir, PLATFORM_STM32, "pin_config.h")

    assert result["path"] == "pin_config.h"
    assert result["label"] == "板级引脚宏"
    # size_bytes = 磁盘字节数（Windows 文本写入含 \r\n）；content = 换行归一化后全文
    assert result["size_bytes"] == disk.stat().st_size
    assert result["content"] == "/* board pins */\n"


def test_read_master_file_rejects_outside_whitelist(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)

    with pytest.raises(MasterError, match="非关键文件"):
        read_master_file(fake_masters_dir, PLATFORM_STM32, "inc/stm32f10x_conf.h")
    with pytest.raises(MasterError, match="非关键文件"):
        read_master_file(fake_masters_dir, PLATFORM_STM32, "../evil.c")
    with pytest.raises(MasterError, match="非关键文件"):
        read_master_file(fake_masters_dir, PLATFORM_STM32, "MAIN.C")  # 大小写敏感


def test_read_master_file_whitelisted_but_missing_raises(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)
    (fake_masters_dir / "stm32" / "led_instances.h").unlink()

    with pytest.raises(MasterError, match="关键文件缺失"):
        read_master_file(fake_masters_dir, PLATFORM_STM32, "led_instances.h")


def test_read_master_file_platform_not_in_library_raises(fake_masters_dir):
    with pytest.raises(MasterError, match="不存在"):
        read_master_file(fake_masters_dir, PLATFORM_STM32, "main.c")


def test_read_master_file_replaces_invalid_utf8(fake_masters_dir):
    """读文本惯例 utf-8 errors=\"replace\"：非 UTF-8 字节（如 GBK 注释）不崩，
    替换为 U+FFFD——与 skeleton.read_module_sources 同读法（母版关键文件可含
    GBK 注释，如 21F pin_config.h）。"""
    _make_stm32_master_with_key_files(fake_masters_dir)
    (fake_masters_dir / "stm32" / "pin_config.h").write_bytes(b"\xff\xfe hello")

    result = read_master_file(fake_masters_dir, PLATFORM_STM32, "pin_config.h")

    assert "\ufffd\ufffd hello" == result["content"]


# ---------------------------------------------------------------------------
# 母版体检（工单 master-library-ui-2/01）：健康 + 体积统计
# ---------------------------------------------------------------------------


def test_master_health_ok_for_complete_master(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)

    health = master_health(fake_masters_dir, PLATFORM_STM32)

    assert health.ok is True
    assert health.missing_key_files == ()
    assert health.config_file_ok is True
    assert health.artifact_dirs == ()


def test_master_health_flags_missing_key_file(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)
    (fake_masters_dir / "stm32" / "pin_config.h").unlink()

    health = master_health(fake_masters_dir, PLATFORM_STM32)

    assert health.ok is False
    assert health.missing_key_files == ("pin_config.h",)


def test_master_health_flags_missing_config_file(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)
    (fake_masters_dir / "stm32" / "user" / "Project.uvprojx").unlink()

    health = master_health(fake_masters_dir, PLATFORM_STM32)

    assert health.ok is False
    assert health.config_file_ok is False


def test_master_health_flags_artifact_dirs(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)
    (fake_masters_dir / "stm32" / "Debug").mkdir()

    health = master_health(fake_masters_dir, PLATFORM_STM32)

    assert health.ok is False
    assert health.artifact_dirs == ("Debug",)


def test_master_health_platform_not_in_library_raises(fake_masters_dir):
    with pytest.raises(MasterError, match="不存在"):
        master_health(fake_masters_dir, PLATFORM_STM32)


def test_master_health_unknown_platform_raises(fake_masters_dir):
    (fake_masters_dir / "vxworks").mkdir(parents=True)

    with pytest.raises(MasterError, match="未知平台"):
        master_health(fake_masters_dir, "vxworks")


def test_master_stats_counts_files_and_bytes(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)

    stats = master_stats(fake_masters_dir, PLATFORM_STM32)

    expected = sum(
        (fake_masters_dir / "stm32" / p).stat().st_size
        for p in ("main.c", "pin_config.h", "led_instances.h", "user/Project.uvprojx")
    )
    assert stats.total_size_bytes == expected
    assert stats.file_count == 4
    assert stats.big_files == ()


def test_master_stats_skips_artifact_dirs(fake_masters_dir):
    """体积/文件数走统一噪音跳过：构建产物目录（如 Debug/）不计入。"""
    _make_stm32_master_with_key_files(fake_masters_dir)
    (fake_masters_dir / "stm32" / "Debug").mkdir(parents=True)
    (fake_masters_dir / "stm32" / "Debug" / "x.obj").write_bytes(b"\0" * 10)

    stats = master_stats(fake_masters_dir, PLATFORM_STM32)

    assert stats.file_count == 4


def test_master_stats_big_files_threshold_and_top10(fake_masters_dir):
    """big_files：仅严格大于 BIG_FILE_THRESHOLD_BYTES（256KB）的文件，
    按大小降序取 Top 10；恰好等于阈值与更小的文件不入列。"""
    _make_stm32_master_with_key_files(fake_masters_dir)
    master = fake_masters_dir / "stm32"
    (master / "edge.bin").write_bytes(bytes(256 * 1024))  # 恰好阈值：不入列
    (master / "small.txt").write_text("ok")
    # 12 个大文件（300..311KB）：只保留最大的 10 个
    for i in range(12):
        (master / f"big_{i:02d}.bin").write_bytes(bytes((300 + i) * 1024))

    stats = master_stats(fake_masters_dir, PLATFORM_STM32)

    paths = [bf.path for bf in stats.big_files]
    assert len(paths) == 10
    assert paths[0] == "big_11.bin"  # 311KB 最大
    assert paths[-1] == "big_02.bin"  # 302KB 第 10 大
    assert "big_01.bin" not in paths  # 301KB 第 11 大：出列
    assert "big_00.bin" not in paths
    assert "edge.bin" not in paths
    assert "small.txt" not in paths


def test_master_stats_platform_not_in_library_raises(fake_masters_dir):
    with pytest.raises(MasterError, match="不存在"):
        master_stats(fake_masters_dir, PLATFORM_STM32)


def test_master_stats_unknown_platform_raises(fake_masters_dir):
    (fake_masters_dir / "vxworks").mkdir(parents=True)

    with pytest.raises(MasterError, match="未知平台"):
        master_stats(fake_masters_dir, "vxworks")


# ---------------------------------------------------------------------------
# 文件树（工单 master-library-ui-2/02）：全部文件清单 + 树内文件内容
# ---------------------------------------------------------------------------


def test_master_tree_files_lists_all_with_noise_skip(fake_masters_dir):
    """树清单 = 统一噪音跳过后的全部文件（构建产物目录 / .git 不计入），
    排序确定性（目录序），每条 {path, size_bytes}。"""
    _make_stm32_master_with_key_files(fake_masters_dir)
    master = fake_masters_dir / "stm32"
    (master / "user" / "main.c").write_text("int main(void){}\n", encoding="utf-8")
    (master / "Debug").mkdir()
    (master / "Debug" / "main.o").write_bytes(b"\0" * 8)
    (master / ".git").mkdir()
    (master / ".git" / "HEAD").write_text("ref", encoding="utf-8")

    files = master_tree_files(fake_masters_dir, PLATFORM_STM32)

    paths = [f.path for f in files]
    assert set(paths) == {
        "main.c",
        "pin_config.h",
        "led_instances.h",
        "user/Project.uvprojx",
        "user/main.c",
    }
    assert ".git/HEAD" not in paths
    assert "Debug/main.o" not in paths
    assert all(isinstance(f.size_bytes, int) and f.size_bytes > 0 for f in files)
    # 排序确定性：同输入两次调用逐条相等（跨平台路径序语义不同，不做具体序断言）
    assert files == master_tree_files(fake_masters_dir, PLATFORM_STM32)


def test_master_tree_files_platform_not_in_library_raises(fake_masters_dir):
    with pytest.raises(MasterError, match="不存在"):
        master_tree_files(fake_masters_dir, PLATFORM_STM32)


def test_read_master_tree_file_returns_content(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)
    master = fake_masters_dir / "stm32"
    (master / "user" / "oled.c").write_text("void oled_init(void){}\n", encoding="utf-8")

    result = read_master_tree_file(fake_masters_dir, PLATFORM_STM32, "user/oled.c")

    assert result["path"] == "user/oled.c"
    assert result["size_bytes"] == (master / "user" / "oled.c").stat().st_size
    assert result["content"] == "void oled_init(void){}\n"


def test_read_master_tree_file_rejects_traversal(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)

    # 拒绝面与 entry_store.is_unsafe_path 对齐：.. 任意层级 / 空段 / 首字符
    # 斜杠（绝对路径）/ 反斜杠 / 冒号（NTFS ADS）
    for path in (
        "../evil.c",
        "user/../../evil.c",
        "a//b.c",
        "..\\windir.c",
        "/abs.c",
        "a:b.c",
    ):
        with pytest.raises(MasterError, match="非法路径"):
            read_master_tree_file(fake_masters_dir, PLATFORM_STM32, path)


def test_read_master_tree_file_rejects_binary(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)
    (fake_masters_dir / "stm32" / "blob.bin").write_bytes(b"ab\x00cd")

    with pytest.raises(MasterError, match="二进制"):
        read_master_tree_file(fake_masters_dir, PLATFORM_STM32, "blob.bin")


def test_read_master_tree_file_rejects_oversize(fake_masters_dir):
    """超过 TREE_FILE_MAX_PREVIEW_BYTES（1MB）拒绝——大文件不读全文。"""
    _make_stm32_master_with_key_files(fake_masters_dir)
    (fake_masters_dir / "stm32" / "big.c").write_bytes(b" " * (1024 * 1024 + 1))

    with pytest.raises(MasterError, match="预览上限"):
        read_master_tree_file(fake_masters_dir, PLATFORM_STM32, "big.c")


def test_read_master_tree_file_missing_raises(fake_masters_dir):
    _make_stm32_master_with_key_files(fake_masters_dir)

    with pytest.raises(MasterError, match="文件不存在"):
        read_master_tree_file(fake_masters_dir, PLATFORM_STM32, "nope.c")


def test_read_master_tree_file_platform_not_in_library_raises(fake_masters_dir):
    with pytest.raises(MasterError, match="不存在"):
        read_master_tree_file(fake_masters_dir, PLATFORM_STM32, "main.c")


# ---------------------------------------------------------------------------
# 免提炼快速导入（工单 master-library-ui-2/04）：直接替换同平台母版
# ---------------------------------------------------------------------------


def test_import_master_direct_replaces_existing_master(fake_masters_dir, tmp_path):
    """免提炼入库：结构校验通过 → 直接替换同平台旧母版，sources = [源目录名]，
    元数据与库内文件均随替换更新。"""
    _make_stm32_master_with_key_files(fake_masters_dir)  # 旧母版
    source = make_fake_master_project(tmp_path / "official_template")

    meta = import_master_direct(fake_masters_dir, PLATFORM_STM32, source)

    assert meta.platform == PLATFORM_STM32
    assert meta.sources == ("official_template",)
    assert meta.warnings == ()
    # 库内 main.c 已被新源替换（源 main.c 内容 ≠ 旧母版 main.c）
    assert (
        fake_masters_dir / "stm32" / "main.c"
    ).read_text(encoding="utf-8") == source.joinpath("main.c").read_text(encoding="utf-8")
    assert (fake_masters_dir / ".stm32.importing").exists() is False
    assert (fake_masters_dir / ".stm32.backup").exists() is False


def test_import_master_direct_structure_failure_leaves_store_intact(
    fake_masters_dir, tmp_path
):
    """结构校验失败（源缺工程配置文件）→ 旧母版零盘面改动。"""
    _make_stm32_master_with_key_files(fake_masters_dir)
    before = (fake_masters_dir / "stm32" / "main.c").read_text(encoding="utf-8")
    bad_dir = tmp_path / "bad_src"
    bad_dir.mkdir()
    (bad_dir / "main.c").write_text("void main(void){}\n", encoding="utf-8")

    with pytest.raises(MasterError, match="工程配置文件"):
        import_master_direct(fake_masters_dir, PLATFORM_STM32, bad_dir)

    assert (fake_masters_dir / "stm32" / "main.c").read_text(encoding="utf-8") == before
    assert (fake_masters_dir / "stm32").is_dir()


def test_import_master_direct_source_dir_missing_raises(fake_masters_dir, tmp_path):
    with pytest.raises(MasterError, match="源目录不存在"):
        import_master_direct(fake_masters_dir, PLATFORM_STM32, tmp_path / "nope")


def test_import_master_direct_invalid_platform_raises(fake_masters_dir, tmp_path):
    source = make_fake_master_project(tmp_path / "src")

    with pytest.raises(MasterError, match="非法平台名"):
        import_master_direct(fake_masters_dir, "../evil", source)



# ---------------------------------------------------------------------------
# 结构测试（防回退，先例 errors.py 防漏登）：配置文件后缀表单源 platforms.py
# ---------------------------------------------------------------------------


def test_master_store_no_config_file_suffix_table():
    """工程配置文件后缀表单源 platforms.PLATFORM_CONFIG_FILE_SUFFIXES
    （工单 04）：master_store 不再自持 PLATFORM_CONFIG_FILES。"""
    import contest_generator.master_store as master_store

    assert not hasattr(master_store, "PLATFORM_CONFIG_FILES")
