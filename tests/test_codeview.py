"""代码查看器域模块（工单 code-viewer/01）：目录打开与文件读取。

唯一出处 = codeview.py；安全约束与母版树 read_master_tree_file 同立场
（路径穿越 / 二进制 / 超限三类均 400 中文），逐条用例钉死拒绝面。
"""

import pytest

from contest_generator.codeview import (
    CODE_FILE_MAX_BYTES,
    CODE_RAW_MAX_BYTES,
    CODE_SEARCH_MAX_HITS,
    CODE_TREE_MAX_ENTRIES,
    CodeViewError,
    code_raw_media_type,
    list_code_tree,
    read_code_file,
    read_code_file_bytes,
    search_code_files,
)


def _make_tree(root):
    """造一棵典型工程树：正文文件 + 噪音目录（.git / Debug / Objects / Listings）。"""
    (root / "src").mkdir(parents=True)
    (root / "Debug").mkdir(parents=True)
    (root / "Objects").mkdir(parents=True)
    (root / ".git").mkdir(parents=True)
    (root / "Listings").mkdir(parents=True)
    (root / "main.c").write_bytes(b"int main(void){return 0;}\n")
    (root / "src" / "app.h").write_text("#pragma once\n", encoding="utf-8")
    (root / "readme.md").write_text("# 工程\n", encoding="utf-8")
    (root / "Debug" / "main.obj").write_bytes(b"\x00\x01")
    (root / "Objects" / "main.o").write_bytes(b"\x00\x01")
    (root / "Listings" / "main.lst").write_text("x", encoding="utf-8")
    (root / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    return root# ---------------------------------------------------------------------------
# list_code_tree：清单结构 / 噪音跳过 / 上限 / 目录不存在
# ---------------------------------------------------------------------------


def test_list_code_tree_returns_flat_sorted_entries(tmp_path):
    root = _make_tree(tmp_path / "proj")

    entries = list_code_tree(root)

    assert [e["path"] for e in entries] == [
        "main.c",
        "readme.md",
        "src/app.h",
    ]  # 噪音目录（.git/Debug/Objects/Listings）一律不计入；全路径排序确定性
    assert entries[0] == {"path": "main.c", "size_bytes": 26}


def test_list_code_tree_missing_dir_is_400_error(tmp_path):
    with pytest.raises(CodeViewError, match="目录不存在"):
        list_code_tree(tmp_path / "nope")


def test_list_code_tree_rejects_file_root(tmp_path):
    f = tmp_path / "a.c"
    f.write_text("x", encoding="utf-8")

    with pytest.raises(CodeViewError, match="目录不存在"):
        list_code_tree(f)


def test_list_code_tree_caps_entries(tmp_path, monkeypatch):
    monkeypatch.setattr("contest_generator.codeview.CODE_TREE_MAX_ENTRIES", 3)
    root = tmp_path / "big"
    root.mkdir()
    for i in range(4):
        (root / f"f{i}.txt").write_text("x", encoding="utf-8")

    with pytest.raises(CodeViewError, match="目录文件过多"):
        list_code_tree(root)


# ---------------------------------------------------------------------------
# read_code_file：正常读取 / 换行归一 / 三类 400 / 文件缺失
# ---------------------------------------------------------------------------


def test_read_code_file_returns_content_normalized(tmp_path):
    root = _make_tree(tmp_path / "proj")
    (root / "main.c").write_bytes(b"int main(void){\r\n\treturn 0;\r\n}\r\n")

    info = read_code_file(root, "main.c")

    assert info["path"] == "main.c"
    assert info["size_bytes"] == (root / "main.c").stat().st_size  # 原始字节数
    assert info["content"] == "int main(void){\n\treturn 0;\n}\n"  # \r\n 归一
    assert info["outline"] == [{"kind": "function", "name": "main", "line": 1}]


def test_read_code_file_missing_file_is_400_error(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="文件不存在：nope.c"):
        read_code_file(root, "nope.c")


@pytest.mark.parametrize(
    "rel_path",
    [
        "../outside.c",
        "src/../../outside.c",
        "a//b.c",  # 空段
        "src/",  # 尾空段
        "/etc/passwd",  # 绝对路径
        "C:/x.c",  # NTFS ADS 冒号
        "src\\app.h",  # 反斜杠
    ],
)
def test_read_code_file_rejects_unsafe_paths(tmp_path, rel_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="非法路径"):
        read_code_file(root, rel_path)


def test_read_code_file_rejects_binary(tmp_path):
    root = _make_tree(tmp_path / "proj")
    (root / "blob.bin").write_bytes(b"PNG\x00\x01\x02")

    with pytest.raises(CodeViewError, match="二进制文件不可预览"):
        read_code_file(root, "blob.bin")


def test_read_code_file_rejects_oversize(tmp_path, monkeypatch):
    monkeypatch.setattr("contest_generator.codeview.CODE_FILE_MAX_BYTES", 2 * 1024 * 1024)
    root = _make_tree(tmp_path / "proj")
    (root / "big.c").write_text("x" * (2 * 1024 * 1024 + 1), encoding="utf-8")

    with pytest.raises(CodeViewError, match="文件超过预览上限（2MB）"):
        read_code_file(root, "big.c")


def test_read_code_file_root_missing_is_400_error(tmp_path):
    with pytest.raises(CodeViewError, match="目录不存在"):
        read_code_file(tmp_path / "nope", "main.c")


def test_constants_are_sane():
    assert CODE_TREE_MAX_ENTRIES == 5000
    assert CODE_FILE_MAX_BYTES == 1024 * 1024


def test_read_code_file_outline_functions_defines_includes_sorted(tmp_path):
    root = _make_tree(tmp_path / "proj")
    (root / "main.c").write_bytes(
        '#include "app.h"\n'
        "#define LED_GPIO 2\n"
        "void setup(void) {}\n"
        "int main(void) {\n"
        "    return 0;\n"
        "}\n".encode("utf-8")
    )

    info = read_code_file(root, "main.c")

    assert info["outline"] == [
        {"kind": "include", "name": "app.h", "line": 1},
        {"kind": "define", "name": "LED_GPIO", "line": 2},
        {"kind": "function", "name": "setup", "line": 3},
        {"kind": "function", "name": "main", "line": 4},
    ]  # 按行号归并；条件块内 #define（include guard）不收


def test_read_code_file_outline_null_for_non_c(tmp_path):
    root = _make_tree(tmp_path / "proj")
    (root / "README.md").write_bytes("# 工程\n".encode("utf-8"))
    (root / "app.syscfg").write_bytes(b"board:\n")

    assert read_code_file(root, "README.md")["outline"] is None
    assert read_code_file(root, "app.syscfg")["outline"] is None


# ---------------------------------------------------------------------------
# search_code_files：命中 / 大小写 / 上限 / 跳过 / 空 q（工单 code-viewer/02）
# ---------------------------------------------------------------------------


def _search_tree(root):
    (root / "src").mkdir(parents=True)
    (root / "main.c").write_bytes(
        "#include <stdio.h>\n// 主函数入口\nvoid helper(void) {\n\tint val = 0;\n}\n".encode("utf-8")
    )
    (root / "readme.md").write_bytes("# MAIN 入口\n".encode("utf-8"))
    (root / "Debug").mkdir()
    (root / "Debug" / "main.obj").write_bytes(b"keyword\x00\x01")
    (root / ".git").mkdir()
    (root / ".git" / "x").write_text("keyword", encoding="utf-8")
    (root / "blob.bin").write_bytes(b"x\x00y")
    return root


def test_search_matches_ignoring_case(tmp_path):
    root = _search_tree(tmp_path / "proj")

    result = search_code_files(root, "HeLpEr")

    assert result["truncated"] is False
    assert result["hits"] == [{"path": "main.c", "line": 3, "text": "void helper(void) {"}]


def test_search_matches_chinese(tmp_path):
    root = _search_tree(tmp_path / "proj")

    result = search_code_files(root, "主函数")

    assert [h["line"] for h in result["hits"]] == [2]


def test_search_skips_noise_binary_and_oversize(tmp_path, monkeypatch):
    monkeypatch.setattr("contest_generator.codeview.CODE_FILE_MAX_BYTES", 16)
    root = _search_tree(tmp_path / "proj")
    (root / "big.txt").write_bytes(b"keyword " * 10)  # 超 16B → 跳过

    result = search_code_files(root, "keyword")

    assert result["hits"] == []  # 噪音（Debug/.git）+ 二进制（blob.bin）+ 超限（big.txt）全跳过
    assert result["files_scanned"] == 4  # main.c/readme.md/blob.bin/big.txt；噪音目录不计入


def test_search_truncates_at_max_hits(tmp_path, monkeypatch):
    monkeypatch.setattr("contest_generator.codeview.CODE_SEARCH_MAX_HITS", 2)
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.c").write_bytes(b"hit\nhit\nhit\n")

    result = search_code_files(root, "hit")

    assert len(result["hits"]) == 2
    assert result["hits"][0]["line"] == 1
    assert result["truncated"] is True


def test_search_snippet_trims_long_lines(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    line = "前" * 100 + "KEY" + "后" * 100
    (root / "a.c").write_bytes(line.encode("utf-8"))

    result = search_code_files(root, "key")

    text = result["hits"][0]["text"]
    assert "KEY" in text
    assert len(text) <= 125  # 两侧各 60 + 命中词 3 + 两个省略号
    assert text.startswith("…") and text.endswith("…")


def test_search_no_hits_reports_scanned(tmp_path):
    root = _search_tree(tmp_path / "proj")

    result = search_code_files(root, "zzz不存在zzz")

    assert result == {"hits": [], "truncated": False, "files_scanned": 3}


def test_search_empty_query_is_400_error(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    with pytest.raises(CodeViewError, match="搜索关键词不能为空"):
        search_code_files(root, "   ")


def test_search_missing_dir_is_400_error(tmp_path):
    with pytest.raises(CodeViewError, match="目录不存在"):
        search_code_files(tmp_path / "nope", "x")


# ---------------------------------------------------------------------------
# read_code_file_bytes / code_raw_media_type：md 预览图片字节（工单 code-viewer-md-preview/02）
# ---------------------------------------------------------------------------


def test_read_code_file_bytes_returns_image_and_media_type(tmp_path):
    root = _make_tree(tmp_path / "proj")
    (root / "images").mkdir()
    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    (root / "images" / "a.png").write_bytes(png)

    assert read_code_file_bytes(root, "images/a.png") == png
    assert code_raw_media_type("a.png") == "image/png"
    assert code_raw_media_type("b.jpg") == "image/jpeg"
    assert code_raw_media_type("c.JPEG") == "image/jpeg"      # 大小写宽容
    assert code_raw_media_type("d.gif") == "image/gif"
    assert code_raw_media_type("e.webp") == "image/webp"
    assert code_raw_media_type("f.bmp") == "image/bmp"
    assert code_raw_media_type("g.ico") == "image/x-icon"
    assert code_raw_media_type("h.svg") == "image/svg+xml"


def test_code_raw_media_type_rejects_non_image(tmp_path):
    with pytest.raises(CodeViewError, match="不支持的图片类型"):
        code_raw_media_type("main.c")
    with pytest.raises(CodeViewError, match="不支持的图片类型"):
        code_raw_media_type("no-ext")


def test_read_code_file_bytes_rejects_non_image_file(tmp_path):
    root = _make_tree(tmp_path / "proj")
    (root / "code.c").write_bytes(b"int x;")

    with pytest.raises(CodeViewError, match="不支持的图片类型"):
        read_code_file_bytes(root, "code.c")


@pytest.mark.parametrize(
    "rel_path",
    [
        "../outside.png",
        "images/../../outside.png",
        "/etc/passwd",
        "C:/x.png",
        "images\\a.png",
        "a//b.png",
    ],
)
def test_read_code_file_bytes_rejects_unsafe_paths(tmp_path, rel_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="非法路径"):
        read_code_file_bytes(root, rel_path)


def test_read_code_file_bytes_missing_file_is_400_error(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="文件不存在：nope.png"):
        read_code_file_bytes(root, "nope.png")


def test_read_code_file_bytes_root_missing_is_400_error(tmp_path):
    with pytest.raises(CodeViewError, match="目录不存在"):
        read_code_file_bytes(tmp_path / "nope", "a.png")


def test_read_code_file_bytes_allows_nul_inside_image(tmp_path):
    # 图片 = 二进制语义：文件内 NUL 不拒绝（与 read_code_file 文本预览口径不同）
    root = _make_tree(tmp_path / "proj")
    (root / "n.png").write_bytes(b"\x89PNG\x00\x00123")

    assert read_code_file_bytes(root, "n.png") == b"\x89PNG\x00\x00123"


def test_read_code_file_bytes_rejects_oversize(tmp_path, monkeypatch):
    monkeypatch.setattr("contest_generator.codeview.CODE_RAW_MAX_BYTES", 16)
    root = _make_tree(tmp_path / "proj")
    (root / "big.png").write_bytes(b"x" * 17)

    with pytest.raises(CodeViewError, match="图片超过预览上限（8MB）"):
        read_code_file_bytes(root, "big.png")

