"""AI diff 应用域（工单 code-ide-ai/02）：/api/code/apply-diff（codeview.apply_code_diff）。

契约见 fx/ai-diff.js：hunks = [{line, title, lines:[{kind:"ctx"|"del"|"add",
text}]}]——应用以 old 段（ctx+del）整行精确匹配为锚点（line 仅展示语义）；
preview 只算不写；写模式 base_mtime_ns 冲突 409（与 save_code_file 同口径）。
"""

import pytest

from contest_generator.codeview import (
    CodeViewConflictError,
    CodeViewError,
    apply_code_diff,
)

MAIN = (
    "int main(void) {\n"
    "  // TODO: init sensor\n"
    "  init();\n"
    "  return 0;\n"
    "}\n"
)


def _proj(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "main.c").write_text(MAIN, encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.h").write_text("#pragma once\n", encoding="utf-8")
    return root


def _hunk(line, *rows):
    return {"line": line, "title": "", "lines": [
        {"kind": k, "text": t} for k, t in rows
    ]}


# ---------------------------------------------------------------------------
# preview：只算不写 + stats 准确性
# ---------------------------------------------------------------------------


def test_apply_diff_preview_does_not_write(tmp_path):
    root = _proj(tmp_path)
    before = (root / "main.c").read_text(encoding="utf-8")
    mtime = (root / "main.c").stat().st_mtime_ns

    out = apply_code_diff(root, "main.c", [_hunk(2,
        ("ctx", "int main(void) {"),
        ("del", "  // TODO: init sensor"),
        ("add", "  sensor_init();"),
        ("ctx", "  init();"),
    )], preview=True)

    assert out["new_content"] == (
        "int main(void) {\n  sensor_init();\n  init();\n  return 0;\n}\n"
    )
    assert out["stats"] == {"additions": 1, "deletions": 1, "hunks": 1}
    # 只算不写：磁盘原样 + mtime 不变
    assert (root / "main.c").read_text(encoding="utf-8") == before
    assert (root / "main.c").stat().st_mtime_ns == mtime


def test_apply_diff_write_success_and_stats(tmp_path):
    root = _proj(tmp_path)
    base = (root / "main.c").stat().st_mtime_ns

    out = apply_code_diff(root, "main.c", [_hunk(2,
        ("ctx", "int main(void) {"),
        ("del", "  // TODO: init sensor"),
        ("add", "  sensor_init();"),
        ("ctx", "  init();"),
    )], base_mtime_ns=base)

    assert out["saved"] is True
    assert out["stats"] == {"additions": 1, "deletions": 1, "hunks": 1}
    assert (root / "main.c").read_text(encoding="utf-8") == (
        "int main(void) {\n  sensor_init();\n  init();\n  return 0;\n}\n"
    )
    assert out["mtime_ns"] == str((root / "main.c").stat().st_mtime_ns)


def test_apply_diff_base_mtime_mismatch_is_409(tmp_path):
    root = _proj(tmp_path)

    with pytest.raises(CodeViewConflictError, match="已被外部修改"):
        apply_code_diff(root, "main.c", [_hunk(2,
            ("ctx", "int main(void) {"),
            ("del", "  // TODO: init sensor"),
            ("add", "  sensor_init();"),
            ("ctx", "  init();"),
        )], base_mtime_ns=1)


def test_apply_diff_conflict_409_priority_over_hunk_mismatch(tmp_path):
    """外部改盘后 hunk 通常也不再匹配——base 校验先于 hunk 应用（评审 s1
    整改）：语义应是 409「已被外部修改」而非 400「未匹配」——即 hunk 与磁盘
    内容不符 + base 过期，必须报 409。"""
    root = _proj(tmp_path)
    (root / "main.c").write_text("int main(void) {\n  // external edit\n}\n", encoding="utf-8")

    with pytest.raises(CodeViewConflictError, match="已被外部修改"):
        apply_code_diff(root, "main.c", [_hunk(2,
            ("del", "  // TODO: init sensor"),
            ("add", "  sensor_init();"),
        )], base_mtime_ns=1)


def test_apply_diff_preview_accepts_no_base_mtime(tmp_path):
    root = _proj(tmp_path)
    out = apply_code_diff(root, "main.c", [_hunk(1,
        ("add", "// v2"),
        ("ctx", "int main(void) {"),
    )], preview=True)
    assert out["new_content"].startswith("// v2\nint main(void) {")


# ---------------------------------------------------------------------------
# 应用正确性：首行替换 / 末尾插入 / 多 hunk 顺序 / 纯插入 / 子目录文件
# ---------------------------------------------------------------------------


def test_apply_diff_first_line_replace(tmp_path):
    root = _proj(tmp_path)
    out = apply_code_diff(root, "main.c", [_hunk(1,
        ("del", "int main(void) {"),
        ("add", "int main(void) {  // replaced"),
        ("ctx", "  // TODO: init sensor"),
    )], preview=True)
    assert out["new_content"].startswith(
        "int main(void) {  // replaced\n  // TODO: init sensor\n")


def test_apply_diff_tail_insert(tmp_path):
    root = _proj(tmp_path)
    out = apply_code_diff(root, "main.c", [_hunk(6,
        ("ctx", "}"),
        ("add", "// tail"),
    )], preview=True)
    assert out["new_content"].endswith("}\n// tail\n")


def test_apply_diff_multiple_hunks_in_order(tmp_path):
    root = _proj(tmp_path)
    out = apply_code_diff(root, "main.c", [
        _hunk(2,
            ("ctx", "int main(void) {"),
            ("del", "  // TODO: init sensor"),
            ("add", "  sensor_init();"),
            ("ctx", "  init();"),
        ),
        _hunk(5,
            ("ctx", "  return 0;"),
            ("add", "  return 1;"),
        ),
    ], preview=True)
    # old 段 = 非 add 行连续匹配：hunk1 消费 lines[0:3]（del 替换为 add），
    # hunk2 的 ctx+add = 在 return 0 后插入 return 1（ctx 保留）——unified
    # 语义：替换用 del+add，插入用 ctx+add；hunk 间磁盘行原样保留、顺序应用
    assert out["new_content"] == (
        "int main(void) {\n  sensor_init();\n  init();\n  return 0;\n"
        "  return 1;\n}\n"
    )


def test_apply_diff_subdir_file(tmp_path):
    root = _proj(tmp_path)
    out = apply_code_diff(root, "src/app.h", [_hunk(1,
        ("ctx", "#pragma once"),
        ("add", "// app"),
    )], preview=True)
    assert out["new_content"] == "#pragma once\n// app\n"


# ---------------------------------------------------------------------------
# 拒绝面：结构 / 锚点缺失 / 不匹配 / 路径越界 / 文件不存在
# ---------------------------------------------------------------------------


def test_apply_diff_rejects_bad_hunk_structure(tmp_path):
    root = _proj(tmp_path)
    with pytest.raises(CodeViewError, match="hunk"):
        apply_code_diff(root, "main.c", [{"line": 1, "lines": []}], preview=True)
    with pytest.raises(CodeViewError, match="行结构非法"):
        apply_code_diff(root, "main.c", [_hunk(1, ("replace", "x"))],
                        preview=True)
    with pytest.raises(CodeViewError, match="锚点"):
        apply_code_diff(root, "main.c", [_hunk(1, ("add", "x"))], preview=True)
    with pytest.raises(CodeViewError, match="行号非法"):
        apply_code_diff(root, "main.c", [_hunk(0, ("ctx", "x"))], preview=True)
    with pytest.raises(CodeViewError, match="hunk"):
        apply_code_diff(root, "main.c", "not-a-list", preview=True)


def test_apply_diff_rejects_unmatched_context(tmp_path):
    root = _proj(tmp_path)
    with pytest.raises(CodeViewError, match="未匹配"):
        apply_code_diff(root, "main.c", [_hunk(1,
            ("ctx", "int main(void) { garbage"),
            ("del", "  // TODO: init sensor"),
            ("add", "  sensor_init();"),
        )], preview=True)


def test_apply_diff_rejects_unsafe_path_and_missing(tmp_path):
    root = _proj(tmp_path)
    with pytest.raises(CodeViewError, match="非法路径|在输出目录之外"):
        apply_code_diff(root, "../evil.c", [_hunk(1, ("ctx", "x"))],
                        preview=True)
    with pytest.raises(CodeViewError, match="文件不存在"):
        apply_code_diff(root, "nope.c", [_hunk(1, ("ctx", "x"))],
                        preview=True)


def test_apply_diff_write_rejects_non_utf8(tmp_path):
    root = _proj(tmp_path)
    (root / "bin.dat").write_bytes(b"\xff\xfe")
    with pytest.raises(CodeViewError, match="不是 UTF-8"):
        apply_code_diff(root, "bin.dat", [_hunk(1, ("ctx", "x"))],
                        base_mtime_ns=(root / "bin.dat").stat().st_mtime_ns)
