"""PDF 资料库（给人看的资料库）：素材库 PDF 清单收集 / 过滤 / 路径安全解析。

素材库（sources/materials）全量 PDF 递归清单（批次 = 素材根下第一级目录），
名字串过滤（文件名 / 批次 / 完整路径，大小写不敏感），解析端路径安全
（is_unsafe_path）与存在性校验，非法 / 缺失抛 ReferenceError（webapp 映射
400，与参考文件库同通道）。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from contest_generator.pdf_library import (
    list_pdfs,
    pdf_page_count,
    resolve_pdf,
    trash_pdf,
)
from contest_generator.reference_library import ReferenceError
from tests.topic_pdf_fakes import make_multi_page_pdf


def _make_materials(root: Path) -> Path:
    """搭一个两批次素材根：A 批含嵌套 PDF + 干扰文件，B 批含大写扩展名 PDF。"""
    a = root / "2026_04_地猛星配套资料" / "6 TB6612电机驱动资料" / "3.芯片手册"
    a.mkdir(parents=True)
    (a / "TB6612FNG Datasheet.pdf").write_bytes(b"%PDF-1.4\nfake a")
    (root / "2026_04_地猛星配套资料" / "readme.txt").write_text("not a pdf", encoding="utf-8")
    b = root / "2026_06_电赛视觉资料"
    b.mkdir(parents=True)
    (b / "09_泰山派原理图.PDF").write_bytes(b"%PDF-1.4\nfake b")
    return root


def test_list_pdfs_collects_nested_with_batch_and_size(tmp_path):
    root = _make_materials(tmp_path / "materials")
    pdfs = list_pdfs(root)
    by_name = {p["name"]: p for p in pdfs}
    assert set(by_name) == {"TB6612FNG Datasheet.pdf", "09_泰山派原理图.PDF"}  # 干扰文件不收
    tb = by_name["TB6612FNG Datasheet.pdf"]
    assert tb["rel_path"] == "2026_04_地猛星配套资料/6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf"
    assert tb["batch"] == "2026_04_地猛星配套资料"
    assert tb["size_bytes"] == len(b"%PDF-1.4\nfake a")
    assert by_name["09_泰山派原理图.PDF"]["batch"] == "2026_06_电赛视觉资料"


def test_list_pdfs_sorted_by_batch_then_path(tmp_path):
    root = _make_materials(tmp_path / "materials")
    pdfs = list_pdfs(root)
    assert [p["batch"] for p in pdfs] == ["2026_04_地猛星配套资料", "2026_06_电赛视觉资料"]


def test_list_pdfs_filters_by_filename_batch_and_path_case_insensitive(tmp_path):
    root = _make_materials(tmp_path / "materials")
    assert [p["name"] for p in list_pdfs(root, name="tb6612")] == ["TB6612FNG Datasheet.pdf"]
    assert [p["name"] for p in list_pdfs(root, name="视觉资料")] == ["09_泰山派原理图.PDF"]  # 命中批次
    assert [p["name"] for p in list_pdfs(root, name="芯片手册")] == ["TB6612FNG Datasheet.pdf"]  # 命中路径
    assert list_pdfs(root, name="不存在的关键词") == []


def test_list_pdfs_missing_root_returns_empty(tmp_path):
    assert list_pdfs(tmp_path / "不存在") == []


def test_list_pdfs_each_entry_has_int_mtime(tmp_path):
    root = _make_materials(tmp_path / "materials")
    rel = "2026_04_地猛星配套资料/6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf"
    os.utime(root / rel, (1_000_000_000, 1_000_000_000))
    pdfs = list_pdfs(root)
    assert all(isinstance(p["mtime"], int) for p in pdfs)
    by_name = {p["name"]: p for p in pdfs}
    assert by_name["TB6612FNG Datasheet.pdf"]["mtime"] == 1_000_000_000


def test_resolve_pdf_happy_path(tmp_path):
    root = _make_materials(tmp_path / "materials")
    rel = "2026_04_地猛星配套资料/6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf"
    assert resolve_pdf(root, rel).is_file()


@pytest.mark.parametrize(
    "bad", ["../secret.pdf", "..\\secret.pdf", "/etc/passwd.pdf", "a//b.pdf", "c:/win.pdf", ".."]
)
def test_resolve_pdf_rejects_unsafe_paths(tmp_path, bad):
    root = _make_materials(tmp_path / "materials")
    with pytest.raises(ReferenceError):
        resolve_pdf(root, bad)


def test_resolve_pdf_missing_or_non_pdf_raises(tmp_path):
    root = _make_materials(tmp_path / "materials")
    with pytest.raises(ReferenceError):
        resolve_pdf(root, "不存在.pdf")
    with pytest.raises(ReferenceError):  # 存在但不是 PDF
        resolve_pdf(root, "2026_04_地猛星配套资料/readme.txt")
    with pytest.raises(ReferenceError):  # 素材根缺失
        resolve_pdf(tmp_path / "不存在", "x.pdf")


def test_pdf_page_count_reads_real_pdf(tmp_path):
    root = _make_materials(tmp_path / "materials")
    rel = "2026_06_电赛视觉资料/09_手册_多页.pdf"
    make_multi_page_pdf(root / rel, [("", "page 1"), ("", "page 2"), ("", "page 3")])
    assert pdf_page_count(root, rel) == 3


def test_pdf_page_count_rejects_zero_byte_and_corrupt(tmp_path):
    root = _make_materials(tmp_path / "materials")
    (root / "2026_06_电赛视觉资料/空文件.pdf").write_bytes(b"")
    with pytest.raises(ReferenceError):
        pdf_page_count(root, "2026_06_电赛视觉资料/空文件.pdf")
    (root / "2026_06_电赛视觉资料/损坏.pdf").write_bytes(b"not a pdf at all")
    with pytest.raises(ReferenceError):
        pdf_page_count(root, "2026_06_电赛视觉资料/损坏.pdf")


def test_pdf_page_count_rejects_unsafe_or_missing(tmp_path):
    root = _make_materials(tmp_path / "materials")
    with pytest.raises(ReferenceError):  # 非法路径（resolve_pdf 通道）
        pdf_page_count(root, "../secret.pdf")
    with pytest.raises(ReferenceError):  # 不存在
        pdf_page_count(root, "不存在.pdf")
    # 素材根缺失：先 resolve_pdf 炸（存在性），不落 fitz
    with pytest.raises(ReferenceError):
        pdf_page_count(tmp_path / "不存在", "x.pdf")


# ---------------------------------------------------------------------------
# 回收删除（工单 06）：疑似重复组成员 → trash_dir/日期/rel_path 镜像（不真删）
# ---------------------------------------------------------------------------

REL_B = "2026_06_电赛视觉资料/09_泰山派原理图.PDF"


def test_trash_pdf_moves_file_out_of_library(tmp_path):
    root = _make_materials(tmp_path / "materials")
    trash = tmp_path / ".trash-pdf"
    to = trash_pdf(root, REL_B, trash)
    assert not (root / REL_B).exists()
    assert to == f"{time.strftime('%Y-%m-%d')}/{REL_B}"
    assert (trash / to).read_bytes() == b"%PDF-1.4\nfake b"  # 内容原样落盘
    assert [p["name"] for p in list_pdfs(root)] == ["TB6612FNG Datasheet.pdf"]  # 回收后不入清单


def test_trash_pdf_rejects_unsafe_or_missing(tmp_path):
    root = _make_materials(tmp_path / "materials")
    with pytest.raises(ReferenceError):
        trash_pdf(root, "../secret.pdf", tmp_path / ".trash-pdf")
    with pytest.raises(ReferenceError):
        trash_pdf(root, "不存在.pdf", tmp_path / ".trash-pdf")
    with pytest.raises(ReferenceError):  # 素材根缺失（resolve_pdf 通道）
        trash_pdf(tmp_path / "不存在", "x.pdf", tmp_path / ".trash-pdf")


def test_trash_pdf_conflict_appends_numeric_suffix(tmp_path):
    root = _make_materials(tmp_path / "materials")
    trash = tmp_path / ".trash-pdf"
    to = trash_pdf(root, REL_B, trash)
    (root / REL_B).write_bytes(b"%PDF-1.4\nfake b")  # 重建同路径文件再删
    to1 = trash_pdf(root, REL_B, trash)
    date = time.strftime("%Y-%m-%d")
    assert to1 == f"{date}/2026_06_电赛视觉资料/09_泰山派原理图_1.PDF"
    (root / REL_B).write_bytes(b"%PDF-1.4\nfake b")
    to2 = trash_pdf(root, REL_B, trash)
    assert to2 == f"{date}/2026_06_电赛视觉资料/09_泰山派原理图_2.PDF"
    assert (trash / to).exists() and (trash / to1).exists() and (trash / to2).exists()


def test_trash_pdf_trash_root_blocked_raises(tmp_path):
    """回收根不可写（被文件占位）：OSError 明确失败，不静默。"""
    root = _make_materials(tmp_path / "materials")
    block = tmp_path / "阻塞文件"
    block.write_text("x", encoding="utf-8")
    with pytest.raises(OSError):
        trash_pdf(root, REL_B, block)
