"""生成输出目标解析：桌面赛题目录命名与唯一化。"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.generation_output import (
    TOPIC_EN_TITLES,
    backup_project_dir,
    desktop_topic_dir_verdict,
    topic_dir_title,
    topic_en_title,
    topic_short_title,
    unique_desktop_topic_dir,
    windows_safe_folder_name,
    with_platform_suffix,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32


@pytest.mark.parametrize(
    ("problem_text", "expected"),
    [
        # 历史赛题首行真实形态（2024H 复盘：目录名 = 编号 + 短题名）
        ("自动行驶小车（H 题）\n一、 任务\n", "自动行驶小车"),
        ("智能送药小车（F题）\n【本科组】\n", "智能送药小车"),
        ("小车跟随行驶系统（C 题）\n一、 任务\n", "小车跟随行驶系统"),
        ("C 题：无线充电电动小车（本科）\n1. 任务\n", "无线充电电动小车"),
        ("# 基于无线通信的数字钥匙实验系统（C题）\n", "基于无线通信的数字钥匙实验系统"),
        ("电动小车动态无线充电系统（A 题）\n", "电动小车动态无线充电系统"),
    ],
)
def test_topic_short_title_extracts_short_name_from_first_line(problem_text, expected):
    """首行短题名提取：去掉 markdown 标题符 / 行首题号前缀 / 行尾（题号/组别）括号。"""
    assert topic_short_title(problem_text) == expected


def test_topic_short_title_keeps_unparseable_first_line():
    """首行没有题号/括号形态 → 原样保留（不猜不删）。"""
    assert topic_short_title("2026C 数字钥匙题面全文（长 PDF 拆条入库）") == (
        "2026C 数字钥匙题面全文（长 PDF 拆条入库）"
    )


def test_topic_dir_title_prefixes_key_with_ascii_english():
    """历史赛题目录名 = 编号 + 英文短名（工单 ascii-project-name/01：中文路径
    在 CCS/gmake 链上乱码，目录名改纯英文）。"""
    assert topic_dir_title("2024H", "自动行驶小车（H 题）\n") == "2024H_Auto_Car"
    assert topic_dir_title("2021F", "智能送药小车（F题）\n") == "2021F_Smart_Medicine_Car"


def test_topic_en_title_dictionary_covers_all_library_topics():
    """内置字典覆盖现题库全部 8 题的短题名（topic_short_title 提取结果）。"""
    from pathlib import Path
    topics_root = (
        Path(__file__).resolve().parents[1] / "library" / "topics"
    )
    assert topics_root.is_dir(), "题库目录缺失（library/topics）"
    for entry in topics_root.iterdir():
        md = entry / "topic.md"
        if not md.is_file():
            continue
        first = md.read_text(encoding="utf-8").splitlines()[0].strip()
        short = topic_short_title(first)
        assert short in TOPIC_EN_TITLES, (
            f"题库 {entry.name} 短题名 {short!r} 未收录进 TOPIC_EN_TITLES"
        )


def test_topic_en_title_ascii_fallback_keeps_alnum_tokens():
    """字典未命中：ASCII 兜底保留字母数字 token、下划线连接。"""
    assert topic_en_title("2027年全国电子设计竞赛(F题)") == "2027_F"
    assert topic_en_title("ECCI D 2027") == "ECCI_D_2027"


def test_topic_en_title_falls_back_to_chinese_when_no_ascii():
    """纯中文兜底 → 回退原短题名（保底可生成）。"""
    assert topic_en_title("完全中文题名") == "完全中文题名"


def test_windows_safe_folder_name_cleans_invalid_chars_and_empty_title():
    assert windows_safe_folder_name('  A<>:"/\\|?*  B  ') == "A_ B"
    assert windows_safe_folder_name(" / ") == "赛题工程"


@pytest.mark.parametrize("name", ["CON", "CON.txt", "prn.md", "COM1.log", "LPT9.tmp"])
def test_windows_safe_folder_name_avoids_reserved_device_names(name):
    assert windows_safe_folder_name(name).endswith("_")


def test_unique_desktop_topic_dir_adds_timestamp_then_counter(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    (desktop / "CON_").mkdir(parents=True)
    (desktop / "CON_20260819-153000").mkdir()
    monkeypatch.setattr("contest_generator.generation_output.time.strftime", lambda fmt: "20260819-153000")

    assert unique_desktop_topic_dir(desktop, "CON") == desktop / "CON_20260819-153000_2"


def test_desktop_topic_dir_verdict_new_when_missing(tmp_path):
    """目录不存在 → "new"：候选目录 = 桌面根 + 清洗后题名（无时间戳后缀）。"""
    desktop = tmp_path / "Desktop"

    path, verdict = desktop_topic_dir_verdict(desktop, "2024H_Auto_Car")

    assert verdict == "new"
    assert path == desktop / "2024H_Auto_Car"
    # 保留名清洗照常（CON → CON_）
    assert desktop_topic_dir_verdict(desktop, "CON") == (desktop / "CON_", "new")


def test_desktop_topic_dir_verdict_clean_marks_half_baked(tmp_path):
    """目录存在但无 .contest_context.json / main.c（半成品残渣）→ "clean"。"""
    desktop = tmp_path / "Desktop"
    half = desktop / "Auto_Car"
    half.mkdir(parents=True)
    (half / ".ccsproject").write_text("<projectOptions/>", encoding="utf-8")

    path, verdict = desktop_topic_dir_verdict(desktop, "Auto_Car")

    assert verdict == "clean"
    assert path == half
    # 空目录同样按残渣清理
    empty = desktop / "Empty_Dir"
    empty.mkdir()
    assert desktop_topic_dir_verdict(desktop, "Empty_Dir") == (empty, "clean")


def test_desktop_topic_dir_verdict_exists_when_complete(tmp_path):
    """有 main.c 或 .contest_context.json 任一 = 完整工程 → "exists"（不覆盖）。"""
    desktop = tmp_path / "Desktop"
    with_main = desktop / "With_Main"
    with_main.mkdir(parents=True)
    (with_main / "main.c").write_text("int main(void) {}\n", encoding="utf-8")
    with_manifest = desktop / "With_Manifest"
    with_manifest.mkdir()
    (with_manifest / ".contest_context.json").write_text("{}", encoding="utf-8")

    assert desktop_topic_dir_verdict(desktop, "With_Main")[1] == "exists"
    assert desktop_topic_dir_verdict(desktop, "With_Manifest")[1] == "exists"


def test_with_platform_suffix_appends_known_platform_marker():
    """平台目录后缀（工单 desktop-platform-suffix/01）：同题两个平台各生成
    各的目录——标题追加平台标记（2024H_Auto_Car_STM32 / Auto_Car_MSPM0），
    双平台目录不再同名。后缀映射与 PLATFORM_CONFIG_FILE_SUFFIXES 同域单源。"""
    assert with_platform_suffix("2024H_Auto_Car", PLATFORM_STM32) == "2024H_Auto_Car_STM32"
    assert with_platform_suffix("Auto_Car", PLATFORM_MSPM0) == "Auto_Car_MSPM0"


def test_with_platform_suffix_raises_on_unknown_platform():
    """未知平台大声失败（工单 desktop-platform-suffix/01）：映射缺 key 时静默
    生成无后缀目录会让新旧平台目录重新撞名——漂移暴露优于静默。"""
    with pytest.raises(ValueError, match="未知平台：esp32"):
        with_platform_suffix("Auto_Car", "esp32")


def test_backup_project_dir_renames_to_single_bak(tmp_path):
    """覆盖前快照（工单 generate-overwrite/01）：旧工程整体改名为 <name>.bak
    （原子、零复制）；原目录消失、备份含全部内容，返回备份路径。"""
    project = tmp_path / "Auto_Car_STM32"
    project.mkdir()
    (project / "main.c").write_text("旧工程", encoding="utf-8")
    (project / ".contest_context.json").write_text('{"旧": true}', encoding="utf-8")

    backup = backup_project_dir(project)

    assert backup == tmp_path / "Auto_Car_STM32.bak"
    assert not project.exists()
    assert (backup / "main.c").read_text(encoding="utf-8") == "旧工程"
    assert (backup / ".contest_context.json").read_text(encoding="utf-8") == '{"旧": true}'


def test_backup_project_dir_replaces_previous_bak(tmp_path):
    """单份策略（工单 generate-overwrite/01）：目标 .bak 已存在（上一代备份）
    → 先移除再改名——桌面不留多代 .bak 堆积。"""
    project = tmp_path / "Auto_Car_STM32"
    project.mkdir()
    (project / "main.c").write_text("第二代", encoding="utf-8")
    # 上一代备份：既有目录残留 + 一棵空垃圾子目录也一并清走
    old_bak = tmp_path / "Auto_Car_STM32.bak"
    old_bak.mkdir()
    (old_bak / "main.c").write_text("第一代", encoding="utf-8")
    (old_bak / "trash").mkdir()

    backup = backup_project_dir(project)

    assert backup == old_bak
    assert (backup / "main.c").read_text(encoding="utf-8") == "第二代"
    assert not (backup / "trash").exists()


def test_backup_project_dir_unlinks_bak_file_that_is_not_dir(tmp_path):
    """防御（工单 generate-overwrite/01）：.bak 位被同名文件占用（非目录）→
    unlink 后改名，不让 rename 撞已存在文件失败。"""
    project = tmp_path / "Auto_Car_STM32"
    project.mkdir()
    (project / "main.c").write_text("新一代", encoding="utf-8")
    (tmp_path / "Auto_Car_STM32.bak").write_text("挡路的文件", encoding="utf-8")

    backup = backup_project_dir(project)

    assert backup == tmp_path / "Auto_Car_STM32.bak"
    assert (backup / "main.c").read_text(encoding="utf-8") == "新一代"


def test_backup_project_dir_rename_failure_leaves_original(tmp_path, monkeypatch):
    """原目录不受影响（工单 generate-overwrite/01 四场景之一）：包夹/占用导致
    rename 失败（如 Keil 打开工程文件 → WinError 32）→ OSError 上抛（经
    errors.py 映射 400「文件操作失败」），旧工程仍在原名目录未被破坏。"""
    project = tmp_path / "Auto_Car_STM32"
    project.mkdir()
    (project / "main.c").write_text("旧工程", encoding="utf-8")
    (project / ".contest_context.json").write_text('{"旧": true}', encoding="utf-8")

    def _boom_rename(self, target):
        raise OSError(32, "另一个程序正在使用此文件，无法重命名")

    monkeypatch.setattr(Path, "rename", _boom_rename)

    with pytest.raises(OSError):
        backup_project_dir(project)

    # 原目录与内容未动、无 .bak 残留（未产生半状态）
    assert (project / "main.c").read_text(encoding="utf-8") == "旧工程"
    assert (project / ".contest_context.json").read_text(encoding="utf-8") == '{"旧": true}'
    assert not (tmp_path / "Auto_Car_STM32.bak").exists()
