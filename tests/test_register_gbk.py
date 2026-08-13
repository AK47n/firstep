"""素材录入脚本 GBK 兜底：UTF-8 失败回退 gb18030 转码、二进制跳过计数可见。

防回归工单 register-gbk-guard/01：MSPM0_MOTOR 批次 7 个 GBK 源码（motor_set_speed.c /
motor_crc.c 等）曾因 iter_text_files 仅试 UTF-8 而静默漏录。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTER_MATERIALS = REPO_ROOT / ".scratch" / "register_materials.py"

GBK_NOTE = "// 电机速度设定\n"


def _load_register_materials():
    spec = importlib.util.spec_from_file_location("register_materials", REGISTER_MATERIALS)
    assert spec is not None and spec.loader is not None, f"加载失败: {REGISTER_MATERIALS}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reg = _load_register_materials()


@pytest.fixture
def material_tree(tmp_path) -> Path:
    """三件套：UTF-8 文件 / GBK 中文注释文件 / 二进制文件。"""
    src = tmp_path / "materials"
    src.mkdir()
    (src / "note.txt").write_text("// UTF-8 注释\n", encoding="utf-8")
    (src / "gbk_note.c").write_bytes(GBK_NOTE.encode("gbk"))
    (src / "firmware.bin").write_bytes(bytes(range(256)))
    return src


def test_iter_text_files_gbk_fallback(material_tree, capsys):
    with pytest.raises(UnicodeDecodeError):
        (material_tree / "gbk_note.c").read_text(encoding="utf-8")  # 夹具判别力：确非 UTF-8

    files = reg.iter_text_files(material_tree)
    assert set(files) == {"note.txt", "gbk_note.c"}
    assert files["gbk_note.c"] == GBK_NOTE  # 中文注释逐字断言
    out = capsys.readouterr().out
    assert "[转码] gbk_note.c（gbk→utf-8）" in out
    assert "[跳过] 1 个非文本文件未入库" in out


def test_old_utf8_only_logic_loses_gbk(material_tree, capsys, monkeypatch):
    """判别力红证：模拟旧逻辑（仅 utf-8、无 gb18030 兜底）时 GBK 文件丢失。"""
    monkeypatch.setattr(reg, "_read_transcoded", lambda path: None)

    files = reg.iter_text_files(material_tree)
    assert "note.txt" in files
    assert "gbk_note.c" not in files  # 旧缺陷形态：GBK 源码静默漏录
    assert "[跳过] 2 个非文本文件未入库" in capsys.readouterr().out


def test_skip_summary_printed_even_when_zero(tmp_path, capsys):
    """N=0 也打一行——可见性本身就是目的。"""
    src = tmp_path / "m"
    src.mkdir()
    (src / "a.txt").write_text("x", encoding="utf-8")

    files = reg.iter_text_files(src)
    assert files == {"a.txt": "x"}
    assert "[跳过] 0 个非文本文件未入库" in capsys.readouterr().out
