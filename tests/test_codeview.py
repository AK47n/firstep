"""代码查看器域模块（工单 code-viewer/01）：目录打开与文件读取。

唯一出处 = codeview.py；安全约束与母版树 read_master_tree_file 同立场
（路径穿越 / 二进制 / 超限三类均 400 中文），逐条用例钉死拒绝面。
"""

import ast
import re
from pathlib import Path

import pytest

from contest_generator.codeview import (
    CODE_FILE_MAX_BYTES,
    CODE_RAW_MAX_BYTES,
    CODE_SEARCH_MAX_HITS,
    CODE_TREE_MAX_ENTRIES,
    CodeViewConflictError,
    CodeViewError,
    code_raw_media_type,
    create_code_entry,
    delete_code_entry,
    list_code_tree,
    name_rules_payload,
    read_code_file,
    read_code_file_bytes,
    rename_code_entry,
    save_code_file,
    search_code_files,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


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

    # 噪音目录（.git/Debug/Objects/Listings）一律不计入；全路径排序确定性；
    # 目录条目（is_dir: True，工单 code-tree-ops/01 起含空目录展示/删除）
    dirs = [e["path"] for e in entries if e.get("is_dir")]
    files = [e["path"] for e in entries if "size_bytes" in e]
    assert dirs == ["src"]
    assert files == ["main.c", "readme.md", "src/app.h"]
    # 文件条目带 mtime_ns（code-ide-flow/02 磁盘基线对比事实源；字符串，
    # 与 /api/code/file·save 同口径——JSON 大整数精度）
    assert {"path": "src", "is_dir": True} in entries
    main_entry = next(e for e in entries if e["path"] == "main.c")
    assert main_entry["size_bytes"] == 26
    assert isinstance(main_entry["mtime_ns"], str)
    assert main_entry["mtime_ns"].isdigit()
    assert main_entry["mtime_ns"] == str((root / "main.c").stat().st_mtime_ns)


def test_list_code_tree_includes_empty_dirs(tmp_path):
    root = _make_tree(tmp_path / "proj")
    (root / "include").mkdir()  # 空目录：纯文件清单看不到，树操作需要

    entries = list_code_tree(root)

    assert {"path": "include", "is_dir": True} in entries


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


# ---------------------------------------------------------------------------
# read_code_file 新字段：mtime_ns / utf8（工单 code-viewer-editor/01——
# 前端保存冲突检测与非 UTF-8 只读的依据）
# ---------------------------------------------------------------------------


def test_read_code_file_reports_mtime_ns_as_string(tmp_path):
    # 字符串契约（工单 code-viewer-editor/01）：ns ≈1.7e18 超 JS 安全整数，
    # JSON number 往返丢精度——必须字符串传输，前端原样回传
    root = _make_tree(tmp_path / "proj")

    info = read_code_file(root, "main.c")

    assert info["mtime_ns"] == str((root / "main.c").stat().st_mtime_ns)
    assert isinstance(info["mtime_ns"], str)


def test_read_code_file_utf8_flag_true_for_utf8(tmp_path):
    root = _make_tree(tmp_path / "proj")

    assert read_code_file(root, "readme.md")["utf8"] is True


def test_read_code_file_utf8_flag_false_for_gbk(tmp_path):
    root = _make_tree(tmp_path / "proj")
    (root / "gbk.c").write_bytes("// 中文注释\n".encode("gbk"))

    info = read_code_file(root, "gbk.c")

    assert info["utf8"] is False
    assert "\ufffd" in info["content"]  # errors=replace 展示口径：原码点不可复原


# ---------------------------------------------------------------------------
# save_code_file：写盘 roundtrip / 归一 / 冲突 409 / 拒绝面（工单 code-viewer-editor/01）
# ---------------------------------------------------------------------------


def test_save_code_file_writes_content_normalized(tmp_path):
    root = _make_tree(tmp_path / "proj")
    base = int(read_code_file(root, "main.c")["mtime_ns"])

    info = save_code_file(root, "main.c", "int helper(void) {\r\n\treturn 1;\r\n}\r\n", base)

    assert (root / "main.c").read_bytes() == b"int helper(void) {\n\treturn 1;\n}\n"
    assert info["path"] == "main.c"
    assert info["size_bytes"] == len(b"int helper(void) {\n\treturn 1;\n}\n")
    assert info["mtime_ns"] == str((root / "main.c").stat().st_mtime_ns)
    assert info["outline"] == [{"kind": "function", "name": "helper", "line": 1}]


def test_save_code_file_accepts_string_base_mtime(tmp_path):
    # 前端按字符串回传（JSON 精度契约），int 与数字字符串同接受
    root = _make_tree(tmp_path / "proj")
    base = read_code_file(root, "main.c")["mtime_ns"]
    assert isinstance(base, str)

    info = save_code_file(root, "main.c", "int a = 1;\n", base)

    assert (root / "main.c").read_bytes() == b"int a = 1;\n"
    assert info["mtime_ns"] == str((root / "main.c").stat().st_mtime_ns)


def test_save_code_file_rejects_non_numeric_base(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="缺少文件修改时间"):
        save_code_file(root, "main.c", "x\n", "abc")


def test_save_code_file_outline_null_for_non_c(tmp_path):
    root = _make_tree(tmp_path / "proj")
    base = read_code_file(root, "readme.md")["mtime_ns"]

    info = save_code_file(root, "readme.md", "# 新标题\n", base)

    assert info["outline"] is None


def test_save_code_file_conflict_when_disk_modified(tmp_path):
    root = _make_tree(tmp_path / "proj")
    base = read_code_file(root, "main.c")["mtime_ns"]
    target = root / "main.c"
    # 外部修改：显式把 mtime 拨快 1 秒（绕开文件系统时间戳分辨率抖动）
    st = target.stat()
    import os
    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))

    with pytest.raises(CodeViewConflictError, match="已被外部修改"):
        save_code_file(root, "main.c", "mine\n", base)


def test_save_code_file_accepts_fresh_base_after_rewrite(tmp_path):
    # 同一 mtime 基准保存两次：第二次先重读（模拟前端保存后刷新基准）
    root = _make_tree(tmp_path / "proj")
    base = read_code_file(root, "main.c")["mtime_ns"]
    save_code_file(root, "main.c", "int a = 1;\n", base)
    base2 = read_code_file(root, "main.c")["mtime_ns"]

    info = save_code_file(root, "main.c", "int a = 2;\n", base2)

    assert (root / "main.c").read_bytes() == b"int a = 2;\n"
    assert info["mtime_ns"] == str((root / "main.c").stat().st_mtime_ns)


@pytest.mark.parametrize(
    "rel_path",
    [
        "../outside.c",
        "src/../../outside.c",
        "a//b.c",
        "src/",
        "/etc/passwd",
        "C:/x.c",
        "src\\app.h",
    ],
)
def test_save_code_file_rejects_unsafe_paths(tmp_path, rel_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="非法路径"):
        save_code_file(root, rel_path, "x\n", 1)


def test_save_code_file_missing_file_is_400_error(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="文件不存在：nope.c"):
        save_code_file(root, "nope.c", "x\n", 1)


def test_save_code_file_rejects_oversize(tmp_path, monkeypatch):
    monkeypatch.setattr("contest_generator.codeview.CODE_FILE_MAX_BYTES", 16)
    root = _make_tree(tmp_path / "proj")
    base = (root / "main.c").stat().st_mtime_ns

    with pytest.raises(CodeViewError, match="文件超过预览上限（0MB）"):
        save_code_file(root, "main.c", "x" * 17, base)


def test_save_code_file_root_missing_is_400_error(tmp_path):
    with pytest.raises(CodeViewError, match="目录不存在"):
        save_code_file(tmp_path / "nope", "main.c", "x\n", 1)


def test_save_code_file_requires_text_content(tmp_path):
    root = _make_tree(tmp_path / "proj")
    base = read_code_file(root, "main.c")["mtime_ns"]

    with pytest.raises(CodeViewError, match="保存内容必须是文本"):
        save_code_file(root, "main.c", None, base)


def test_save_code_file_requires_base_mtime(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="缺少文件修改时间"):
        save_code_file(root, "main.c", "x\n", None)


def test_save_code_file_rejects_non_utf8_source_file(tmp_path):
    # 非 UTF-8（GBK）原文件拒绝保存：errors=replace 已丢码点，UTF-8 覆盖 =
    # 字节编码被改写 = 静默损坏（前端 utf8 标志的后端兜底）
    root = _make_tree(tmp_path / "proj")
    (root / "gbk.c").write_bytes("// 中文注释\n".encode("gbk"))
    base = (root / "gbk.c").stat().st_mtime_ns

    with pytest.raises(CodeViewError, match="不是 UTF-8 编码"):
        save_code_file(root, "gbk.c", "// 换我了\n", base)


# ---------------------------------------------------------------------------
# 树操作（工单 code-tree-ops/01）：create / rename / delete 核心函数
# ---------------------------------------------------------------------------


def test_create_code_file_creates_empty_and_returns_baseline(tmp_path):
    root = _make_tree(tmp_path / "proj")

    info = create_code_entry(root, "file", "sensor.c")

    assert info["path"] == "sensor.c"
    assert info["size_bytes"] == 0
    assert info["mtime_ns"] == str((root / "sensor.c").stat().st_mtime_ns)
    assert (root / "sensor.c").read_bytes() == b""
    # 创建后立即可读（打开 tab 的 /api/code/file 流程衔接顺畅）
    assert read_code_file(root, "sensor.c")["content"] == ""


def test_create_code_file_nested_parents_created(tmp_path):
    root = _make_tree(tmp_path / "proj")

    info = create_code_entry(root, "file", "src/drivers/uart.c")

    assert (root / "src" / "drivers" / "uart.c").is_file()
    assert info["path"] == "src/drivers/uart.c"


def test_create_code_file_existing_is_400(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="已存在"):
        create_code_entry(root, "file", "main.c")


def test_create_code_dir_creates_and_rejects_existing(tmp_path):
    root = _make_tree(tmp_path / "proj")

    assert create_code_entry(root, "dir", "include") == {"path": "include"}
    assert (root / "include").is_dir()
    with pytest.raises(CodeViewError, match="已存在"):
        create_code_entry(root, "dir", "include")
    with pytest.raises(CodeViewError, match="已存在"):
        create_code_entry(root, "dir", "src")


def test_create_code_entry_rejects_bad_kind(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="新建类型必须是 file 或 dir"):
        create_code_entry(root, "link", "x.c")


@pytest.mark.parametrize(
    "rel_path",
    [
        "../outside.c",
        "src/../../outside.c",
        "a//b.c",
        "src/",
        "/etc/passwd",
        "C:/x.c",
        "src\\app.h",
    ],
)
def test_create_code_entry_rejects_unsafe_path(tmp_path, rel_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="非法路径"):
        create_code_entry(root, "file", rel_path)


def test_rename_code_file_moves_and_returns_meta(tmp_path):
    root = _make_tree(tmp_path / "proj")
    old_mtime = (root / "main.c").stat().st_mtime_ns

    info = rename_code_entry(root, "main.c", "app.c")

    assert info["path"] == "app.c"
    assert info["mtime_ns"] == str(old_mtime)  # rename 不改 mtime
    assert not (root / "main.c").exists()
    assert (root / "app.c").is_file()


def test_rename_code_dir_moves_subtree(tmp_path):
    root = _make_tree(tmp_path / "proj")

    info = rename_code_entry(root, "src", "drivers")

    assert info == {"path": "drivers"}
    assert not (root / "src").exists()
    assert (root / "drivers" / "app.h").is_file()


def test_rename_code_idempotent_same_name(tmp_path):
    root = _make_tree(tmp_path / "proj")
    old_mtime = (root / "main.c").stat().st_mtime_ns

    info = rename_code_entry(root, "main.c", "main.c")

    assert info["path"] == "main.c"
    assert info["mtime_ns"] == str(old_mtime)


def test_rename_code_rejects_missing_source(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="不存在"):
        rename_code_entry(root, "nope.c", "x.c")


def test_rename_code_rejects_existing_target(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="已存在"):
        rename_code_entry(root, "main.c", "readme.md")


@pytest.mark.parametrize("bad_name", ["", "  ", "a/b", "a\\b", "a:b", ".", "..", "x" * 121, -1, None])
def test_rename_code_rejects_bad_name(tmp_path, bad_name):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="名称不合法"):
        rename_code_entry(root, "main.c", bad_name)


# ---------------------------------------------------------------------------
# 名称规则下发与执行同源（工单 cross-lang-mirror-c5a/01）
#
# 规则（非法字符集 + 长度上限）此前在 `_validate_entry_name` 里写字面量、前端
# `fx/code-tree-ops.js` 另写一份，两侧靠注释互指、零守卫。现在判据单源仍是
# codeview 的具名常量，但**下发 DTO、校验函数、前端兜底**三处必须逐字对齐：
# 下发口径比校验宽 → 前端放行、后端 400（用户填完名字才吃报错）；比校验窄 →
# 合法名字被前端拦死。故下发的每个字符与上限边界都在这里实打实过一遍。
# 前端**装载接线**（打开目录的响应真装进校验）由 `tests/js/code-tree-ops.test.mjs`
# 的源码守卫守——那是前端测试面的事，不在这里读 JS 源码。
# ---------------------------------------------------------------------------


def test_name_rules_payload_shape_and_no_duplicate_chars():
    rules = name_rules_payload()

    assert set(rules) == {"illegal", "max_len"}
    assert isinstance(rules["illegal"], str)
    assert isinstance(rules["max_len"], int)
    # 无重复字符（前端按它的长度渲染提示，重复会让文案与拒绝对不上）
    assert len(set(rules["illegal"])) == len(rules["illegal"])
    assert not set(rules["illegal"]) & set(" \t\r\n")


def test_create_code_entry_accepts_exactly_what_name_rules_allow(tmp_path):
    """规则放行的名字必须真能建出来（上限 = 恰好通过，多一个字符即拒）。"""
    rules = name_rules_payload()
    root = tmp_path / "proj"
    root.mkdir()

    for name in ("sensor.c", "新驱动_1.h", ".gitignore", "a" * rules["max_len"]):
        create_code_entry(root, "file", name)
        assert (root / name).exists()


def test_name_rules_cover_every_rejected_single_char(tmp_path):
    """下发的每个非法字符都真被后端拒；集合外的字符不许被误拒。

    `a/b` 这种**带正斜杠**的形态是设计内的「嵌套新建」语义（末段才是名字），
    故不在此例；它由 `test_create_code_entry_rejects_unsafe_path` 与
    `test_create_code_file_nested_parents_created` 两侧覆盖。其余字符逐个过
    `a<ch>b`：确认下发集合与后端实际拒绝面**逐字符对齐**（`:` 与 `\\` 被
    上游 `is_unsafe_path` 先拦成「非法路径」，同样是 400，只是文案不同）。
    """
    rules = name_rules_payload()
    root = tmp_path / "proj"
    root.mkdir()

    for ch in rules["illegal"]:
        if ch == "/":  # 路径分隔符：末段之外的段由 _resolve_in_root 管
            continue
        with pytest.raises(CodeViewError, match="名称不合法|非法路径"):
            create_code_entry(root, "file", "a" + ch + "b")
    for ch in ("'", ",", "-", "~", " "):
        create_code_entry(root, "file", "a" + ch + "b")


def test_create_code_entry_rejects_over_max_len(tmp_path):
    rules = name_rules_payload()
    root = tmp_path / "proj"
    root.mkdir()

    with pytest.raises(CodeViewError, match="名称不合法"):
        create_code_entry(root, "file", "a" * (rules["max_len"] + 1))


@pytest.mark.parametrize("rel_path", ["a*b/x.c", "a?b/x.c", "a<x/y>z.c", "a|b/c"])
def test_create_code_entry_rejects_illegal_mid_segment(tmp_path, rel_path):
    """**中间段**（目录名）也要过名称规则（工单 01 评审整改）。

    只校验末段时中间段直达 `mkdir`，未登记的 OSError 变 500——「`a*b.c` → 500」
    换个形态（`a*b/x.c`）复现，正是本工单要关掉的洞。
    """
    root = tmp_path / "proj"
    root.mkdir()

    with pytest.raises(CodeViewError, match="名称不合法"):
        create_code_entry(root, "file", rel_path)


def test_tree_create_illegal_name_is_400_and_leaves_no_half_product(tmp_path):
    """非法名必须 400 中文、且**不许留下半成品**（不能是未登记异常翻的 500）。

    `a*b.c` 此前直达 `os.open` → OSError → 500（既不是 400 也不是设计的拒绝面）；
    补口后判定前置在一切盘操作之前，被拒的名字连空文件都不该留下。
    """
    root = tmp_path / "proj"
    root.mkdir()

    with pytest.raises(CodeViewError, match="名称不合法"):
        create_code_entry(root, "file", "a*b.c")

    assert list(root.iterdir()) == []


def test_rename_code_illegal_name_message_names_the_char(tmp_path):
    """拒绝文案由常量现拼（工单 01 评审整改）：点名哪个字符非法，不含第二份字面量。"""
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="含非法字符") as exc:
        rename_code_entry(root, "main.c", "a*b.c")

    assert "*" in str(exc.value)


# ---------------------------------------------------------------------------
# 跨语言镜像守卫：JS 侧兜底常量必须等于后端常量（工单 cross-lang-mirror-c5a/01）
#
# 规则已经由后端下发（`POST /api/code/open` 的 name_rules），但前端仍持一份
# 「后端尚未下发时的启动兜底」——那份兜底同样是判据的第二处实现，必须与后端
# 逐字符一致，否则页面一打开（或后端旧版本）就按过期规则拦人。故读 JS 真源码
# 抠出两个常量的**值**再与后端比（不逐字比源码：`\` 的转义写法与 Python 不同）。
# 先例：tests/test_hwcheck.py 的通道词表镜像守卫、tests/test_library_invariants.py
# 的模块类别枚举镜像守卫。
# ---------------------------------------------------------------------------

_JS_FX_TREE_OPS = (
    REPO_ROOT / "src" / "contest_generator" / "static" / "js" / "fx" / "code-tree-ops.js"
)


def _js_source_literal(const_name: str) -> object:
    """抠出 JS 源码里 `const <name> = <字面量>;` 的字面量并求值。

    只认单行字符串 / 数字字面量（本模块两个常量都是）；形态变了即大声失败，
    不静默跳过——静默跳过等于这条守卫消失。
    """
    src = _JS_FX_TREE_OPS.read_text(encoding="utf-8")
    match = re.search(
        r"^export const " + re.escape(const_name) + r"\s*=\s*(.+?);\s*$",
        src,
        re.MULTILINE,
    )
    assert match, f"fx/code-tree-ops.js 里找不到 `export const {const_name} = ...`"
    try:
        return ast.literal_eval(match.group(1).strip())
    except (ValueError, SyntaxError) as exc:  # 形态变了（非字面量）= 守卫失效
        raise AssertionError(
            f"{const_name} 不再是可解析的字面量（{match.group(1).strip()!r}）：{exc}"
        ) from None


def test_js_name_rules_fallback_mirrors_backend():
    """前端兜底规则 == 后端单源规则（改任一侧此测试即红）。"""
    rules = name_rules_payload()
    js_illegal = _js_source_literal("CODE_TREE_NAME_ILLEGAL")
    js_max = _js_source_literal("CODE_TREE_NAME_MAX")

    assert set(js_illegal) == set(rules["illegal"]), (
        "fx/code-tree-ops.js 的 CODE_TREE_NAME_ILLEGAL 与后端 CODE_NAME_ILLEGAL 不一致："
        f"JS={js_illegal!r} Python={rules['illegal']!r}"
    )
    assert len(js_illegal) == len(set(js_illegal)), (
        "JS 兜底非法字符集有重复字符（提示文案长度会与拒绝对不上）"
    )
    assert js_max == rules["max_len"], (
        "fx/code-tree-ops.js 的 CODE_TREE_NAME_MAX 与后端 CODE_NAME_MAX_LEN 不一致："
        f"JS={js_max} Python={rules['max_len']}"
    )


def test_delete_code_file_removes(tmp_path):
    root = _make_tree(tmp_path / "proj")

    assert delete_code_entry(root, "readme.md") == {"removed": True}
    assert not (root / "readme.md").exists()


def test_delete_code_empty_dir_removes(tmp_path):
    root = _make_tree(tmp_path / "proj")
    (root / "empty").mkdir()

    assert delete_code_entry(root, "empty") == {"removed": True}
    assert not (root / "empty").exists()


def test_delete_code_nonempty_dir_is_400(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="目录非空"):
        delete_code_entry(root, "src")


def test_delete_code_missing_is_400(tmp_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="不存在"):
        delete_code_entry(root, "nope.c")


@pytest.mark.parametrize(
    "rel_path",
    [
        "../outside.c",
        "src/../../outside.c",
        "a//b.c",
        "src/",
        "/etc/passwd",
        "C:/x.c",
        "src\\app.h",
    ],
)
def test_delete_code_rejects_unsafe_path(tmp_path, rel_path):
    root = _make_tree(tmp_path / "proj")

    with pytest.raises(CodeViewError, match="非法路径"):
        delete_code_entry(root, rel_path)

