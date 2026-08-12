"""编译错误回填自愈域模块测试（工单 compile-error-fix/01 验收项）。

覆盖：报错解析（UV4 / CCS / 混合多文件 / 无文件引用降级 / 垃圾文本不崩）、
路径安全（`../` 逃逸、绝对路径、非法扩展名 → FixError → 400 中文登记
errors.py）、替换协议（精确成功 / 缩进不匹配跳过并报告 / 多处歧义跳过）、
备份与回滚（写回前备份存在、回滚后文件内容恢复原样）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.errors import error_entry
from contest_generator.fix_errors import (
    FIX_BACKUPS_DIRNAME,
    CompileError,
    FixError,
    FixResult,
    FixSuggestion,
    apply_fixes,
    backup_files,
    collect_candidate_paths,
    fix_backup_root,
    parse_compile_errors,
    read_file_contexts,
    restore_backup,
)


# ---------------------------------------------------------------------------
# 报错解析：UV4 格式 / CCS 格式 / 混合多文件 / 无文件引用降级 / 垃圾文本
# ---------------------------------------------------------------------------


def test_parse_uv4_format():
    text = r'..\out\code\main.c(123): error #20: identifier "x" is undefined'
    errors = parse_compile_errors(text)
    assert errors == (
        CompileError(path="../out/code/main.c", line=123, message=text),
    )


def test_parse_uv4_warning_and_column():
    errors = parse_compile_errors(
        'main.c(15,7): warning #177-D: variable "t" was declared but never referenced'
    )
    assert errors == (
        CompileError(path="main.c", line=15, message='main.c(15,7): warning #177-D: variable "t" was declared but never referenced'),
    )


def test_parse_ccs_format():
    text = "code/sub/mod.c:45: error: use of undeclared identifier 'x'"
    assert parse_compile_errors(text) == (
        CompileError(path="code/sub/mod.c", line=45, message=text),
    )


def test_parse_ccs_with_column_and_fatal():
    errors = parse_compile_errors("main.c:45:3: fatal error: no such file or directory")
    assert errors == (CompileError(path="main.c", line=45, message="main.c:45:3: fatal error: no such file or directory"),)


def test_parse_armclang_format_matches_ccs():
    """armclang（Keil AC6）报错与 CCS 同形 path:line:col: error:。"""
    text = "code/pid.c:12:22: error: use of undeclared identifier 'k'"
    assert parse_compile_errors(text) == (
        CompileError(path="code/pid.c", line=12, message=text),
    )


def test_parse_mixed_multiple_files():
    text = (
        "Build started: Project: demo\n"
        r'..\out\code\main.c(123): error #20: identifier "x" is undefined' + "\n"
        "code/sub/mod.c:45: error: use of undeclared identifier 'y'\n"
        r'..\out\code\main.c(130): warning #177-D: variable "z" was declared but never referenced' + "\n"
        "code/pid.c:12:22: error: too few arguments to function call\n"
        "Target not created\n"
    )
    errors = parse_compile_errors(text)
    assert [(e.path, e.line) for e in errors] == [
        ("../out/code/main.c", 123),
        ("code/sub/mod.c", 45),
        ("../out/code/main.c", 130),
        ("code/pid.c", 12),
    ]


def test_parse_no_file_reference_degrades():
    """无文件引用的报错（如链接错误 / 裸 message）→ 空元组（降级模式）。"""
    text = (
        "error #20: identifier \"x\" is undefined\n"
        "L6200E: Symbol foo multiply defined (by main.o and bar.o)\n"
        "*** Target not created ***\n"
    )
    assert parse_compile_errors(text) == ()


def test_parse_garbage_text_does_not_crash():
    garbage = (
        "Target not created\n"
        "Build started: 2026/08/12 10:30:00\n"
        "▶ 进度 100% ▓▓▓▓▓\n"
        "Total time: 00:01:23.456\n"
        "。，！？的回复 😀 (12) : error\n"
    )
    assert parse_compile_errors(garbage) == ()
    assert parse_compile_errors("") == ()


def test_parse_windows_absolute_path_is_degraded():
    """绝对形态（C: 盘符或反斜杠开头）解析不到相对引用——绝对路径不 resolve
    到输出目录内，必须走降级而非读盘（防越界读）。"""
    errors = parse_compile_errors(r"C:\proj\main.c(5): error #20: boom")
    assert errors == ()
    errors = parse_compile_errors(r"\proj\main.c(5): error #20: boom")
    assert errors == ()


# ---------------------------------------------------------------------------
# 文件定位：白名单扩展名 / 路径安全 / 存在性 / 去重保序
# ---------------------------------------------------------------------------


def test_collect_candidate_paths_ordered_deduped(tmp_path):
    (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "mod.c").write_text("int mod(void) { return 1; }\n", encoding="utf-8")
    errors = (
        CompileError(path="main.c", line=1, message="main.c(1): error #20: x"),
        CompileError(path="code/mod.c", line=1, message="code/mod.c:1: error: x"),
        CompileError(path="main.c", line=2, message="main.c(2): warning #177-D: y"),
    )
    assert collect_candidate_paths(tmp_path, errors) == ("main.c", "code/mod.c")


def test_collect_candidate_paths_skips_unsafe_missing_and_non_source(tmp_path):
    (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    errors = (
        CompileError(path="../escape.c", line=1, message="x"),  # 穿越
        CompileError(path="/etc/passwd.c", line=1, message="x"),  # 绝对路径
        CompileError(path="missing.c", line=1, message="x"),  # 不存在
        CompileError(path="out/demo.axf", line=1, message="x"),  # 非白名单扩展名
        CompileError(path="main.c", line=1, message="x"),  # 合法
    )
    assert collect_candidate_paths(tmp_path, errors) == ("main.c",)


def test_read_file_contexts_returns_contents(tmp_path):
    (tmp_path / "main.c").write_text("int x = 1;\n", encoding="utf-8")
    contexts, dropped = read_file_contexts(tmp_path, ("main.c",))
    assert dict(contexts) == {"main.c": "int x = 1;\n"}
    assert dropped == ()


def test_read_file_contexts_missing_file_skipped(tmp_path):
    contexts, dropped = read_file_contexts(tmp_path, ("missing.c",))
    assert contexts == ()
    assert dropped == ()


def test_read_file_contexts_truncates_long_lines(tmp_path):
    """单文件 500 行上限：超长文件只发前 500 行，带截断标注（不脑补缺失）。"""
    (tmp_path / "big.c").write_text(
        "\n".join(f"line {i}" for i in range(600)), encoding="utf-8"
    )
    contexts, dropped = read_file_contexts(tmp_path, ("big.c",))
    content = dict(contexts)["big.c"]
    assert "已截断" in content and "按所见内容判断" in content
    assert content.count("line ") <= 500


def test_read_file_contexts_total_budget_drops_tail(tmp_path):
    """总预算上限：超预算的剩余文件不发送、点名返回（防静默丢失）。"""
    from contest_generator.fix_errors import FIX_CONTEXT_TOTAL_CHARS

    chunk = "x" * 1024 + "\n"
    for name in ("a.c", "b.c"):
        (tmp_path / name).write_text(chunk * (FIX_CONTEXT_TOTAL_CHARS // 1024 + 4), encoding="utf-8")
    contexts, dropped = read_file_contexts(tmp_path, ("a.c", "b.c"))
    assert [p for p, _ in contexts] == ["a.c"]
    assert dropped == ("b.c",)


# ---------------------------------------------------------------------------
# 替换应用：精确成功 / 缩进不匹配跳过并报告 / 多处歧义跳过
# ---------------------------------------------------------------------------


def _make_project(tmp_path) -> Path:
    out = tmp_path / "project"
    out.mkdir()
    (out / "main.c").write_text("int x = 1;\nint main(void) { return x; }\n", encoding="utf-8")
    (out / "code").mkdir()
    (out / "code" / "mod.c").write_text("int mod(void) { return 1; }\n", encoding="utf-8")
    return out


def _backup_root(tmp_path) -> Path:
    return tmp_path / "fix-backups"


def test_apply_fixes_exact_match_writes_file_and_backs_up(tmp_path):
    out = _make_project(tmp_path)
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=1, old_snippet="int x = 1;", new_snippet="int x = 2;", reason="修复初始化")],
        out,
        _backup_root(tmp_path),
    )
    assert report.backup_id  # 写回前已备份
    assert report.results == (
        FixResult(file="main.c", line=1, status="applied", reason=""),
    )
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 2;\nint main(void) { return x; }\n"
    # 备份存在且内容是写回前原样（输出目录外）
    backup_dir = _backup_root(tmp_path) / report.backup_id
    assert backup_dir.is_dir()
    assert (backup_dir / "main.c").read_text(encoding="utf-8") == "int x = 1;\nint main(void) { return x; }\n"


def test_apply_fixes_indent_mismatch_skipped_and_reported(tmp_path):
    out = _make_project(tmp_path)
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=2, old_snippet="  int main(void)", new_snippet="  int win(void)", reason="缩进多了空格")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "skipped"
    assert "未应用" in result.reason and "精确匹配失败" in result.reason
    assert report.backup_id == ""  # 无应用 → 不备份
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 1;\nint main(void) { return x; }\n"


def test_apply_fixes_ambiguous_snippet_skipped(tmp_path):
    out = _make_project(tmp_path)
    (out / "main.c").write_text("int x = 1;\nint y = 1;\nint main(void) { return x + y; }\n", encoding="utf-8")
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=1, old_snippet="int", new_snippet="long", reason="歧义")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "skipped"
    assert "歧义" in result.reason
    assert "int x = 1;\nint y = 1;\n" in (out / "main.c").read_text(encoding="utf-8")


def test_apply_fixes_multiple_fixes_same_file_sequential(tmp_path):
    out = _make_project(tmp_path)
    fixes = [
        FixSuggestion(file="main.c", line=1, old_snippet="int x = 1;", new_snippet="int x = 2;", reason="a"),
        FixSuggestion(file="main.c", line=1, old_snippet="int x = 2;", new_snippet="int x = 3;", reason="b"),
        FixSuggestion(file="code/mod.c", line=1, old_snippet="return 1;", new_snippet="return 0;", reason="c"),
    ]
    report = apply_fixes(fixes, out, _backup_root(tmp_path))
    assert [r.status for r in report.results] == ["applied", "applied", "applied"]
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 3;\nint main(void) { return x; }\n"
    assert (out / "code" / "mod.c").read_text(encoding="utf-8") == "int mod(void) { return 0; }\n"
    backup_dir = _backup_root(tmp_path) / report.backup_id
    assert (backup_dir / "main.c").is_file() and (backup_dir / "code" / "mod.c").is_file()


# ---------------------------------------------------------------------------
# 路径安全：../ 逃逸、绝对路径、非法扩展名 → FixError（400 中文，登记 errors.py）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "file",
    [
        "../evil.c",  # 穿越
        "..\\evil.c",  # 反斜杠穿越
        "/etc/passwd.c",  # 绝对路径
        "C:/windows/system32/evil.c",  # 带驱动器绝对路径
        "out/main.axf",  # 非白名单扩展名
        "project.uvprojx",  # 工程配置
        "readme.txt",
        "noext",  # 无扩展名
        "code/mod.c.tmp",  # 后缀不在白名单
    ],
)
def test_apply_fixes_rejects_unsafe_paths(tmp_path, file):
    out = _make_project(tmp_path)
    with pytest.raises(FixError):
        apply_fixes(
            [FixSuggestion(file=file, line=1, old_snippet="x", new_snippet="y", reason="")],
            out,
            _backup_root(tmp_path),
        )


def test_apply_fixes_rejects_missing_target_file(tmp_path):
    out = _make_project(tmp_path)
    with pytest.raises(FixError, match="不存在"):
        apply_fixes(
            [FixSuggestion(file="ghost.c", line=1, old_snippet="x", new_snippet="y", reason="")],
            out,
            _backup_root(tmp_path),
        )


def test_fix_error_mapped_to_400_chinese():
    """FixError 已登记 errors.py → 400 + 中文 message（验收：拒绝 400 中文）。"""
    status, message = error_entry(FixError("修复目标路径不安全：../evil.c"))
    assert status == 400
    assert message == "修复目标路径不安全：../evil.c"


# ---------------------------------------------------------------------------
# 备份与回滚：备份存在 / 回滚恢复原样 / 非法备份编号拒绝
# ---------------------------------------------------------------------------


def test_restore_backup_restores_original_contents(tmp_path):
    out = _make_project(tmp_path)
    original = (out / "main.c").read_text(encoding="utf-8")
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=1, old_snippet="int x = 1;", new_snippet="int x = 2;", reason="")],
        out,
        _backup_root(tmp_path),
    )
    assert (out / "main.c").read_text(encoding="utf-8") != original
    restored = restore_backup(_backup_root(tmp_path), report.backup_id, out)
    assert restored == ("main.c",)
    assert (out / "main.c").read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    "backup_id",
    ["../evil", "..\\evil", "/etc/passwd", "C:\\windows"],
)
def test_restore_backup_rejects_unsafe_backup_id(tmp_path, backup_id):
    with pytest.raises(FixError):
        restore_backup(_backup_root(tmp_path), backup_id, _make_project(tmp_path))


def test_restore_backup_missing_backup_raises(tmp_path):
    with pytest.raises(FixError, match="备份不存在"):
        restore_backup(_backup_root(tmp_path), "20260812-000000", _make_project(tmp_path))


def test_restore_backup_missing_output_dir_raises(tmp_path):
    out = _make_project(tmp_path)
    backup_id = backup_files(_backup_root(tmp_path), {"main.c": out / "main.c"})
    with pytest.raises(FixError, match="输出目录不存在"):
        restore_backup(_backup_root(tmp_path), backup_id, tmp_path / "gone")


def test_backup_files_mirrors_paths(tmp_path):
    out = _make_project(tmp_path)
    backup_id = backup_files(_backup_root(tmp_path), {"main.c": out / "main.c", "code/mod.c": out / "code" / "mod.c"})
    assert backup_id.startswith("20")  # timestamp 形态（2026-...）
    assert (_backup_root(tmp_path) / backup_id / "main.c").is_file()
    assert (_backup_root(tmp_path) / backup_id / "code" / "mod.c").is_file()


def test_backup_id_unique_on_collision(tmp_path):
    out = _make_project(tmp_path)
    root = _backup_root(tmp_path)
    first = backup_files(root, {"main.c": out / "main.c"})
    (root / first).mkdir(exist_ok=True)  # 模拟同秒再次备份
    second = backup_files(root, {"main.c": out / "main.c"})
    assert first != second
    assert (root / second).is_dir()


def test_fix_backup_root_derivation():
    assert fix_backup_root(Path("/tmp/work")) == Path("/tmp/work") / FIX_BACKUPS_DIRNAME
