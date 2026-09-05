"""Markdown 资料库（给人看的资料库）：素材库 .md 清单收集 / 过滤 / 路径安全解析 / 全文读取。

素材库（sources/materials）全量 Markdown 递归清单（批次 = 素材根下第一级目录），
名字串过滤（文件名 / 批次 / 完整路径，大小写不敏感），解析端路径安全
（is_unsafe_path）与存在性校验，非法 / 缺失抛 ReferenceError（webapp 映射
400，与参考文件库 / pdf_library 同通道）。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from contest_generator.md_library import (
    MD_ASSET_MAX_BYTES,
    MD_FILE_MAX_BYTES,
    asset_media_type,
    list_markdowns,
    read_markdown,
    resolve_markdown,
    resolve_md_asset,
)
from contest_generator.reference_library import ReferenceError


def _make_materials(root: Path) -> Path:
    """搭一个两批次素材根：A 批含嵌套 .md + 干扰文件（.txt / .PDF），B 批含大写扩展名 .MD。

    write_bytes 而非 write_text：Windows 上 write_text 默认 newline=None 会把
    \n 转成 \r\n（大小断言按字节数算，必须确定论）。
    """
    a = root / "lckfb-地猛星移植手册"
    a.mkdir(parents=True)
    (a / "sensor--mpu6050-six-axis-sensor.md").write_bytes(
        "# mpu6050\n\n正文内容\n".encode("utf-8")
    )
    (a / "模块索引.md").write_bytes("# 索引\n".encode("utf-8"))
    (root / "lckfb-地猛星移植手册" / "readme.txt").write_bytes(b"not a md")
    b = root / "2026_06_电赛视觉资料"
    b.mkdir(parents=True)
    (b / "笔记.MD").write_bytes("# 大写扩展名\n".encode("utf-8"))
    return root


def test_list_markdowns_collects_nested_with_batch_and_size(tmp_path):
    root = _make_materials(tmp_path / "materials")
    mds = list_markdowns(root)
    by_name = {p["name"]: p for p in mds}
    assert set(by_name) == {"sensor--mpu6050-six-axis-sensor.md", "模块索引.md", "笔记.MD"}  # 干扰文件不收
    mp = by_name["sensor--mpu6050-six-axis-sensor.md"]
    assert mp["rel_path"] == "lckfb-地猛星移植手册/sensor--mpu6050-six-axis-sensor.md"
    assert mp["batch"] == "lckfb-地猛星移植手册"
    assert mp["size_bytes"] == len("# mpu6050\n\n正文内容\n".encode("utf-8"))
    assert by_name["笔记.MD"]["batch"] == "2026_06_电赛视觉资料"


def test_list_markdowns_sorted_by_batch_then_path(tmp_path):
    root = _make_materials(tmp_path / "materials")
    mds = list_markdowns(root)
    assert [p["batch"] for p in mds] == [
        "2026_06_电赛视觉资料", "lckfb-地猛星移植手册", "lckfb-地猛星移植手册",
    ]
    # 批次内按路径排（rel_path 码点序："s" < "模"，sensor 页在索引前）
    assert [p["name"] for p in mds[1:]] == [
        "sensor--mpu6050-six-axis-sensor.md", "模块索引.md",
    ]


def test_list_markdowns_filters_by_filename_batch_and_path_case_insensitive(tmp_path):
    root = _make_materials(tmp_path / "materials")
    assert [p["name"] for p in list_markdowns(root, name="mpu6050")] == [
        "sensor--mpu6050-six-axis-sensor.md"
    ]
    assert [p["name"] for p in list_markdowns(root, name="地猛星")] == [
        "sensor--mpu6050-six-axis-sensor.md", "模块索引.md",
    ]  # 命中批次（批次内按 rel_path 码点序排）
    assert list_markdowns(root, name="不存在的关键词") == []


def test_list_markdowns_missing_root_returns_empty(tmp_path):
    assert list_markdowns(tmp_path / "不存在") == []


def test_list_markdowns_each_entry_has_int_mtime(tmp_path):
    root = _make_materials(tmp_path / "materials")
    rel = "lckfb-地猛星移植手册/sensor--mpu6050-six-axis-sensor.md"
    os.utime(root / rel, (1_000_000_000, 1_000_000_000))
    mds = list_markdowns(root)
    assert all(isinstance(p["mtime"], int) for p in mds)
    by_name = {p["name"]: p for p in mds}
    assert by_name["sensor--mpu6050-six-axis-sensor.md"]["mtime"] == 1_000_000_000


def test_resolve_markdown_happy_path(tmp_path):
    root = _make_materials(tmp_path / "materials")
    rel = "lckfb-地猛星移植手册/sensor--mpu6050-six-axis-sensor.md"
    assert resolve_markdown(root, rel).is_file()


@pytest.mark.parametrize(
    "bad", ["../secret.md", "..\\secret.md", "/etc/passwd.md", "a//b.md", "c:/win.md", ".."]
)
def test_resolve_markdown_rejects_unsafe_paths(tmp_path, bad):
    root = _make_materials(tmp_path / "materials")
    with pytest.raises(ReferenceError):
        resolve_markdown(root, bad)


def test_resolve_markdown_missing_or_non_md_raises(tmp_path):
    root = _make_materials(tmp_path / "materials")
    with pytest.raises(ReferenceError):
        resolve_markdown(root, "不存在.md")
    with pytest.raises(ReferenceError):  # 存在但不是 .md
        resolve_markdown(root, "lckfb-地猛星移植手册/readme.txt")
    with pytest.raises(ReferenceError):  # 素材根缺失
        resolve_markdown(tmp_path / "不存在", "x.md")


def test_read_markdown_returns_full_content_normalized(tmp_path):
    root = _make_materials(tmp_path / "materials")
    rel = "lckfb-地猛星移植手册/sensor--mpu6050-six-axis-sensor.md"
    (root / rel).write_bytes("# 标题\r\n\r\n正文\r\n".encode("utf-8"))
    got = read_markdown(root, rel)
    assert got["rel_path"] == rel
    assert got["name"] == "sensor--mpu6050-six-axis-sensor.md"
    assert got["size_bytes"] == len("# 标题\r\n\r\n正文\r\n".encode("utf-8"))
    assert got["content"] == "# 标题\n\n正文\n"  # 换行归一化 \r\n → \n


def test_read_markdown_rejects_oversize(tmp_path):
    root = _make_materials(tmp_path / "materials")
    big = root / "lckfb-地猛星移植手册" / "大文件.md"
    big.write_bytes(b"a" * (MD_FILE_MAX_BYTES + 1))
    with pytest.raises(ReferenceError, match="文件过大"):
        read_markdown(root, "lckfb-地猛星移植手册/大文件.md")


def test_read_markdown_rejects_missing(tmp_path):
    root = _make_materials(tmp_path / "materials")
    with pytest.raises(ReferenceError):
        read_markdown(root, "不存在.md")


# —— 附属资源（手册图片等）：resolve_md_asset / asset_media_type ——


def test_resolve_md_asset_happy_path(tmp_path):
    root = _make_materials(tmp_path / "materials")
    (root / "lckfb-地猛星移植手册" / "images").mkdir()
    (root / "lckfb-地猛星移植手册" / "images" / "img1.png").write_bytes(b"\x89PNG")
    rel = "lckfb-地猛星移植手册/images/img1.png"
    assert resolve_md_asset(root, rel).is_file()
    assert asset_media_type(resolve_md_asset(root, rel)) == "image/png"


@pytest.mark.parametrize(
    "bad", ["../secret.png", "..\\secret.png", "/etc/passwd", "a//b.png", "c:/win.png", ".."]
)
def test_resolve_md_asset_rejects_unsafe_paths(tmp_path, bad):
    root = _make_materials(tmp_path / "materials")
    with pytest.raises(ReferenceError, match="非法文件路径"):
        resolve_md_asset(root, bad)


def test_resolve_md_asset_missing_raises(tmp_path):
    root = _make_materials(tmp_path / "materials")
    with pytest.raises(ReferenceError, match="不存在"):
        resolve_md_asset(root, "lckfb-地猛星移植手册/images/无.png")


def test_resolve_md_asset_rejects_non_image_ext(tmp_path):
    root = _make_materials(tmp_path / "materials")
    (root / "lckfb-地猛星移植手册" / "images").mkdir()
    (root / "lckfb-地猛星移植手册" / "images" / "page.html").write_text("<html>", encoding="utf-8")
    with pytest.raises(ReferenceError, match="不支持的资源类型"):
        resolve_md_asset(root, "lckfb-地猛星移植手册/images/page.html")


def test_resolve_md_asset_rejects_oversize(tmp_path):
    root = _make_materials(tmp_path / "materials")
    d = root / "lckfb-地猛星移植手册" / "images"
    d.mkdir(parents=True)
    (d / "大图.png").write_bytes(b"a" * (MD_ASSET_MAX_BYTES + 1))
    with pytest.raises(ReferenceError, match="文件过大"):
        resolve_md_asset(root, "lckfb-地猛星移植手册/images/大图.png")


def test_asset_media_type_mapping():
    assert asset_media_type(Path("x.gif")) == "image/gif"
    assert asset_media_type(Path("x.JPG")) == "image/jpeg"
    assert asset_media_type(Path("x.webp")) == "image/webp"
    assert asset_media_type(Path("x.svg")) == "image/svg+xml"
    assert asset_media_type(Path("x.bin")) == "application/octet-stream"
