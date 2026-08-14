"""编译错误回填自愈域模块测试（工单 compile-error-fix/01 验收项）。

覆盖：报错解析（UV4 / CCS / 混合多文件 / 无文件引用降级 / 垃圾文本不崩）、
路径安全（`../` 逃逸、绝对路径、非法扩展名 → FixError → 400 中文登记
errors.py）、替换协议（精确成功 / 行首前缀归一化兜底 applied / 歧义与语句
本体差异跳过）、匹配判决直测（match_snippet 四态纯函数，工单 fix-match-seam/01：
判决语义 / 理由文案单源 / 协议对偶 / 结构钉）、备份与回滚（写回前备份存在、
回滚后文件内容恢复原样）。
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from contest_generator.errors import error_entry
from contest_generator.events import (
    EVENT_APPLY_RESULT,
    EVENT_FIX_START,
    EVENT_PARSE_DONE,
    ProgressEvent,
)
from contest_generator.fix_errors import (
    FIX_BACKUPS_DIRNAME,
    CompileError,
    FixError,
    FixResult,
    FixSuggestion,
    SnippetMatch,
    _reason_for,
    apply_fixes,
    backup_files,
    collect_candidate_paths,
    fix_backup_root,
    match_snippet,
    parse_compile_errors,
    read_file_contexts,
    restore_backup,
    run_fix_round,
    summarize_compile_output,
)
from tests.fakes import FakeLLM


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
# 编译输出数字汇总（工单 compile-experience-ui/01）：UV4 汇总行优先、无汇总
# 退行级、空安全（红证：实施前本组断言失败）
# ---------------------------------------------------------------------------


def test_summarize_uv4_summary_line_takes_values():
    """UV4 汇总行（3 Error 5 Warning）→ 直接取汇总值，不数行。"""
    text = (
        r'..\main.c(10): error #20: identifier "x" is undefined' + "\n"
        "3 Error(s), 5 Warning(s).\n"
    )
    assert summarize_compile_output(text, parse_compile_errors(text)) == {
        "errors": 3,
        "warnings": 5,
    }


def test_summarize_uv4_summary_line_no_comma():
    """真机形态 "0 Error(s) 0 Warning(s)." 无逗号分隔——同样命中汇总行。"""
    text = "Build started: Project: fake\n0 Error(s) 0 Warning(s).\n"
    assert summarize_compile_output(text, parse_compile_errors(text)) == {
        "errors": 0,
        "warnings": 0,
    }


def test_summarize_uv4_summary_takes_precedence_over_line_count():
    """汇总行优先：与行级计数不一致时以汇总值为准（2 条错误行但汇总 1）。"""
    text = (
        "..\\main.c(10): error #20: x\n"
        "..\\main.c(12): error #20: y\n"
        "1 Error(s), 0 Warning(s).\n"
    )
    assert summarize_compile_output(text, parse_compile_errors(text)) == {
        "errors": 1,
        "warnings": 0,
    }


def test_summarize_falls_back_to_line_level_without_summary():
    """无汇总行（CCS / gmake）→ 行级计数：warning 按消息含 "warning" 判定。"""
    text = (
        "code/main.c:10: error: use of undeclared identifier 'x'\n"
        "code/mod.c:12: warning: variable 't' was declared but never referenced\n"
        "code/pid.c:15: error: too few arguments to function call\n"
    )
    parsed = parse_compile_errors(text)
    assert summarize_compile_output(text, parsed) == {"errors": 2, "warnings": 1}


def test_summarize_warning_detection_case_insensitive():
    parsed = parse_compile_errors("main.c:5: WARNING #177-D: unused variable 'z'")
    assert summarize_compile_output("", parsed) == {"errors": 0, "warnings": 1}


def test_summarize_garbage_text_empty_safe():
    garbage = "Target not created\nTotal time: 00:01:23\n"
    assert summarize_compile_output(garbage, parse_compile_errors(garbage)) == {
        "errors": 0,
        "warnings": 0,
    }
    assert summarize_compile_output("", ()) == {"errors": 0, "warnings": 0}


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


def test_collect_uv4_dotdot_resolves_via_uvprojx_benchmark(tmp_path):
    """真机验收补（2026-08-12 红证）：UV4 报错路径相对 .uvprojx 所在子目录
    （`..\\main.c(158)` 形态），须按工程文件基准解析回工程根；修复前该形态
    is_unsafe_path 全拒 → 候选为空（主链路降级死局）。
    """
    out = tmp_path / "proj"
    user = out / "user"
    user.mkdir(parents=True)
    (user / "Project.uvprojx").write_text("<x/>", encoding="utf-8")
    (out / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    errors = (
        CompileError(
            path="../main.c",
            line=158,
            message='..\\main.c(158): error: #20: identifier "x" is undefined',
        ),
    )
    assert collect_candidate_paths(out, errors) == ("main.c",)


def test_collect_uv4_dotdot_escape_still_rejected(tmp_path):
    """真机验收补：`..\\` 形态仍防穿越——按基准解析后越出工程根必须降级。"""
    out = tmp_path / "proj"
    user = out / "user"
    user.mkdir(parents=True)
    (user / "Project.uvprojx").write_text("<x/>", encoding="utf-8")
    (out / "main.c").write_text("x", encoding="utf-8")
    (tmp_path / "outside.c").write_text("x", encoding="utf-8")
    for path in ("../../outside.c", "../outside.c"):
        errors = (CompileError(path=path, line=1, message=f"{path}(1): error: x"),)
        assert collect_candidate_paths(out, errors) == ()


def test_collect_gmake_dotdot_resolves_via_build_dir_benchmark(tmp_path):
    """工单 gmake-fix-path-resolution/01 红证（真机形态）：tiarmclang 报错路径
    相对构建工作目录（mspm0 产物 Debug/，含 subdir_rules.mk），形如
    `../main.c:1:10: fatal error`——须按构建工作目录基准解析回工程根；修复前
    该形态对工程根 / .cproject 两基准全 miss → 候选为空（修复链路降级死局）。
    """
    out = tmp_path / "proj"
    debug = out / "Debug"
    debug.mkdir(parents=True)
    (debug / "subdir_rules.mk").write_text("", encoding="utf-8")
    (out / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    errors = (
        CompileError(
            path="../main.c",
            line=1,
            message="../main.c:1:10: fatal error: 'nonexistent_probe_fixloop.h' "
            "file not found",
        ),
    )
    assert collect_candidate_paths(out, errors) == ("main.c",)


def test_collect_dotdot_prefix_strip_fallback_without_benchmarks(tmp_path):
    """工单 gmake-fix-path-resolution/01 红证（未知形态兜底）：无任何工程文件 /
    构建目录基准时，`../` 前缀逐级剥除后按工程根解析——`../main.c` → main.c、
    `../code/mod.c` → code/mod.c 命中；剥除后仍不在工程内 / 不存在 → 降级。
    """
    out = tmp_path / "proj"
    out.mkdir(parents=True)
    (out / "main.c").write_text("x", encoding="utf-8")
    (out / "code").mkdir()
    (out / "code" / "mod.c").write_text("x", encoding="utf-8")
    errors = (
        CompileError(path="../main.c", line=1, message="x"),
        CompileError(path="../code/mod.c", line=1, message="x"),
    )
    assert collect_candidate_paths(out, errors) == ("main.c", "code/mod.c")


def test_collect_gmake_dotdot_escape_still_rejected(tmp_path):
    """工单 gmake-fix-path-resolution/01 红证：构建目录基准 + 剥前缀兜底仍防
    穿越——工程内不存在的文件（../outside.c / 深层 ../../outside.c）与绝对
    路径一律降级，剥前缀不得把工程外文件骗进候选。"""
    out = tmp_path / "proj"
    debug = out / "Debug"
    debug.mkdir(parents=True)
    (debug / "subdir_rules.mk").write_text("", encoding="utf-8")
    (out / "main.c").write_text("x", encoding="utf-8")
    (tmp_path / "outside.c").write_text("x", encoding="utf-8")
    for path in ("../outside.c", "../../outside.c", "/etc/passwd.c"):
        errors = (CompileError(path=path, line=1, message=f"{path}(1): error: x"),)
        assert collect_candidate_paths(out, errors) == ()


def test_collect_ccs_relative_keeps_working(tmp_path):
    """真机验收补：CCS 相对形态（.cproject 在工程根）不受基准逻辑影响。"""
    out = tmp_path / "proj"
    code = out / "code"
    code.mkdir(parents=True)
    (out / ".cproject").write_text("<x/>", encoding="utf-8")
    (code / "mod.c").write_text("int x;\n", encoding="utf-8")
    errors = (
        CompileError(path="code/mod.c", line=1, message="code/mod.c:1: error: x"),
    )
    assert collect_candidate_paths(out, errors) == ("code/mod.c",)


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
    from contest_generator.fix_errors import FIX_CONTEXT_TOTAL_BYTES

    chunk = "x" * 1024 + "\n"
    for name in ("a.c", "b.c"):
        (tmp_path / name).write_text(chunk * (FIX_CONTEXT_TOTAL_BYTES // 1024 + 4), encoding="utf-8")
    contexts, dropped = read_file_contexts(tmp_path, ("a.c", "b.c"))
    assert [p for p, _ in contexts] == ["a.c"]
    assert dropped == ("b.c",)


def test_read_file_contexts_budget_accounts_wire_bytes_chinese(tmp_path):
    """wire 字节记账（工单 fix-request-budget/01，红证：旧字符口径下本断言必
    红——49152 字符中文单段 ≈295KB 远超预算）：全中文文件截断后嵌入体的
    json.dumps 序列化字节 ≤ 总预算 + 截断标注，字符口径记账会低估中文 6×。"""
    from contest_generator.fix_errors import FIX_CONTEXT_TOTAL_BYTES

    (tmp_path / "big.c").write_text(
        "\n".join("中" * 50 for _ in range(3000)), encoding="utf-8"
    )
    contexts, dropped = read_file_contexts(tmp_path, ("big.c",))
    assert dropped == ()
    body = dict(contexts)["big.c"]
    assert "上下文预算限制" in body  # 预算截断标注在场
    assert len(json.dumps(body, ensure_ascii=True)) - 2 <= FIX_CONTEXT_TOTAL_BYTES + 160
    # 中文 6 字节/字符：保留字符数约为预算的 1/6（远小于旧 49152 字符口径）
    assert len(body) < FIX_CONTEXT_TOTAL_BYTES // 6 + 100


def test_read_file_contexts_budget_keeps_ascii_near_budget(tmp_path):
    """字节记账对 ASCII 友好：wire ≈ 字符数，接近预算的 ASCII 文件整段保留
    不截（钉死字节口径不误伤 ASCII——字符口径若按中文 6× 打折会过度截断）。"""
    from contest_generator.fix_errors import FIX_CONTEXT_TOTAL_BYTES

    content = "x" * (FIX_CONTEXT_TOTAL_BYTES - 200)
    (tmp_path / "a.c").write_text(content, encoding="utf-8")
    contexts, dropped = read_file_contexts(tmp_path, ("a.c",))
    assert dropped == ()
    assert dict(contexts)["a.c"] == content  # 未截断（wire ≤ 预算）


def test_fit_wire_budget_exact_and_maximal():
    """_fit_wire_budget（工单 fix-request-budget/01）：任何预算下截取结果
    wire ≤ 预算；预算内原样返回；截断时取最长前缀（多一字即超）；空预算 →
    空串。"""
    from contest_generator.fix_errors import _fit_wire_budget, _wire_size

    content = "中" * 5000 + "x" * 5000
    for budget in (0, 1, 100, 1000, 23000):
        assert _wire_size(_fit_wire_budget(content, budget)) <= budget
    fitted = _fit_wire_budget(content, 23000)
    assert _wire_size(fitted) <= 23000 < _wire_size(fitted + content[len(fitted)])
    assert _fit_wire_budget("x" * 10, 0) == ""


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


def test_apply_fixes_indent_mismatch_normalized_applied(tmp_path):
    """丢缩进形态（工单 fix-snippet-match/01 红转绿）：old_snippet 前导缩进与
    文件不一致——精确匹配失败（红），行首前缀归一化唯一命中 → applied。"""
    out = _make_project(tmp_path)
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=2, old_snippet="  int main(void)", new_snippet="  int win(void)", reason="缩进多了空格")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "applied"
    assert "归一化匹配应用" in result.reason  # 报告透明（决策 3）
    assert report.backup_id  # 有应用 → 已备份
    # 归一化替换语义 = 匹配行的原始全文被 new_snippet 替换（工单决策 1）
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 1;\n  int win(void)\n"
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 1;\n  int win(void)\n"


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


# ---------------------------------------------------------------------------
# 行首前缀归一化兜底匹配（工单 fix-snippet-match/01）：四形态红转绿 + 边界
# ---------------------------------------------------------------------------


def test_apply_fixes_trailing_comment_normalized_applied(tmp_path):
    """丢行尾注释形态（红证：原实现 raw 前缀带空格/缺注释 → 0 次匹配 skipped）。"""
    out = _make_project(tmp_path)
    (out / "main.c").write_text("int x = 1;   /* init */\nint main(void) { return x; }\n", encoding="utf-8")
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=1, old_snippet="  int x = 1;", new_snippet="int x = 2;", reason="缺注释+缩进变形")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "applied"
    assert "归一化匹配应用" in result.reason
    assert report.backup_id
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 2;\nint main(void) { return x; }\n"


def test_apply_fixes_crlf_file_roundtrip_applied(tmp_path):
    """行尾 CRLF 形态（契约回归）：真 CRLF 文件（newline="" 落盘）在 apply_fixes
    通读时被 universal newlines 归一为 \\n（决策 1 ③ 的端到端路径），精确匹配
    照常 applied，写回保持 CRLF 行尾。"""
    out = _make_project(tmp_path)
    (out / "main.c").write_text(
        "int x = 1;\r\nint main(void) { return x; }\r\n", encoding="utf-8", newline=""
    )
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=1, old_snippet="int x = 1;", new_snippet="int x = 2;", reason="CRLF 文件")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "applied"
    on_disk = (out / "main.c").read_text(encoding="utf-8", newline="")
    assert on_disk == "int x = 2;\r\nint main(void) { return x; }\r\n"


def test_normalized_hits_tolerates_crlf_content():
    """匹配器层面的 CRLF 容忍（红证：新表面，旧实现按子串匹配对含 \\r 内容
    0 命中）：内容若带 \\r\\n（非文本模式读取等路径进入匹配器），归一化匹配
    （strip 逐行）仍唯一命中。"""
    from contest_generator.fix_errors import _normalized_hits

    hits = _normalized_hits(
        "int x = 1;\r\nint main(void) { return x; }\r\n", "int x = 1;\n"
    )
    assert hits == (0,)
    hits = _normalized_hits("int x = 1;\r\nint x = 1;\r\n", "int x = 1;")
    assert len(hits) == 2  # 歧义在调用方处理


def test_apply_fixes_inline_spaces_normalized_applied(tmp_path):
    """行内多空格形态（红证：snippet 行尾多空格 → raw 0 次匹配；strip 后前缀命中）。"""
    out = _make_project(tmp_path)
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=1, old_snippet="int x = 1; ", new_snippet="int x = 2;", reason="行尾多空格")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "applied"
    assert "归一化匹配应用" in result.reason
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 2;\nint main(void) { return x; }\n"


def test_apply_fixes_normalized_ambiguous_skipped(tmp_path):
    """归一化兜底多处命中仍跳过（红证：raw 0 次但 strip 前缀命中 2 行）。"""
    out = _make_project(tmp_path)
    (out / "main.c").write_text("int a = 1;  /* one */\nint a = 2;  /* two */\n", encoding="utf-8")
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=1, old_snippet="  int a =", new_snippet="long a =", reason="歧义")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "skipped"
    assert "歧义" in result.reason
    assert report.backup_id == ""
    assert (out / "main.c").read_text(encoding="utf-8") == "int a = 1;  /* one */\nint a = 2;  /* two */\n"


def test_apply_fixes_body_whitespace_diff_skipped(tmp_path):
    """语句本体不一致仍跳过（行内空白重组不可容忍，决策 1）。"""
    out = _make_project(tmp_path)
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=1, old_snippet="int x  = 1;", new_snippet="int x = 2;", reason="本体空格差异")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "skipped"
    assert "未应用" in result.reason
    assert report.backup_id == ""
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 1;\nint main(void) { return x; }\n"


def test_apply_fixes_multiline_block_normalized_applied(tmp_path):
    """多行片段 = 连续行块逐行前缀命中（红证：raw 多行逐字不匹配）。"""
    out = _make_project(tmp_path)
    (out / "main.c").write_text(
        "int a = 1;  /* one */\nint b = 2;\nint c = 3;\nint main(void) { return a + b + c; }\n",
        encoding="utf-8",
    )
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=1, old_snippet="    int a = 1;\n    int b = 2;", new_snippet="int a = 1;\nint b = 20;", reason="两行块")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "applied"
    assert "归一化匹配应用" in result.reason
    assert (out / "main.c").read_text(encoding="utf-8") == "int a = 1;\nint b = 20;\nint c = 3;\nint main(void) { return a + b + c; }\n"


def test_apply_fixes_normalized_delete_whole_line(tmp_path):
    """new_snippet 空串 = 删整行（匹配行的原始全文被替换为空）。"""
    out = _make_project(tmp_path)
    (out / "main.c").write_text("int x = 1;\nint main(void) { return x; }  /* entry */\n", encoding="utf-8")
    report = apply_fixes(
        [FixSuggestion(file="main.c", line=2, old_snippet="    int main(void)", new_snippet="", reason="删整行")],
        out,
        _backup_root(tmp_path),
    )
    result = report.results[0]
    assert result.status == "applied"
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 1;\n"


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
# 匹配判决直测（工单 fix-match-seam/01）：match_snippet 纯函数——零文件系统，
# 红证用例全集（fix-snippet-match/01 的判决语义）从 apply_fixes 端到端迁移到
# 判决层直测；端到端行为用例（写回 + 备份）保留在上方，双保险不回归
# ---------------------------------------------------------------------------


def test_match_snippet_exact_unique():
    """精确子串唯一匹配 → exact：替换区间 = 子串区间，snippet = new_snippet
    原样（无换行保护——子串替换语义）。"""
    match = match_snippet(
        "int x = 1;\nint main(void) { return x; }\n", "int x = 1;", "int x = 2;"
    )
    assert match.status == "exact"
    assert (match.start, match.end) == (0, 10)  # "int x = 1;" = 10 字符
    assert match.snippet == "int x = 2;"
    assert match.count == 1 and match.via_normalized is False


def test_match_snippet_indent_diff_normalized():
    """丢缩进形态（红证迁移）：前导缩进与文件不一致 → 精确 0 次，归一化唯一命中。"""
    match = match_snippet(
        "int x = 1;\nint main(void) { return x; }\n",
        "  int main(void)",
        "  int win(void)",
    )
    assert match.status == "normalized"
    assert (match.start, match.end) == (11, 40)  # 行区间（含行尾换行）
    assert match.snippet == "  int win(void)\n"  # 行尾换行保护补回
    assert match.count == 1


def test_match_snippet_trailing_comment_normalized():
    """丢行尾注释形态（红证迁移）：old_snippet 省略行尾注释 → 归一化命中整行。"""
    match = match_snippet(
        "int x = 1;   /* init */\nint main(void) { return x; }\n",
        "  int x = 1;",
        "int x = 2;",
    )
    assert match.status == "normalized"
    assert (match.start, match.end) == (0, 24)  # "int x = 1;   /* init */\n" 整行
    assert match.snippet == "int x = 2;\n"


def test_match_snippet_crlf_content_normalized():
    """CRLF 形态（红证迁移）：\\r 让精确子串 0 次，归一化逐行 strip 命中；替换
    保留原行尾 \\r\\n（换行保护）。"""
    match = match_snippet(
        "int x = 1;\r\nint main(void) { return x; }\r\n",
        "int x = 1;\n",
        "int x = 2;",
    )
    assert match.status == "normalized"
    assert (match.start, match.end) == (0, 12)  # "int x = 1;\r\n" = 12 字符
    assert match.snippet == "int x = 2;\r\n"
    assert match.count == 1


def test_match_snippet_inline_spaces_normalized():
    """行内多空格形态（红证迁移）：snippet 行尾多空格 → 精确 0 次，strip 后
    前缀命中（行尾空白容忍）。"""
    match = match_snippet(
        "int x = 1;\nint main(void) { return x; }\n",
        "int x = 1; ",
        "int x = 2;",
    )
    assert match.status == "normalized"
    assert (match.start, match.end) == (0, 11)
    assert match.snippet == "int x = 2;\n"


def test_match_snippet_ambiguous_exact_multiple():
    """精确子串多处出现 → ambiguous（不模糊替换），count = 精确出现次数，
    via_normalized=False（与归一化歧义的 reason 文案区分，见 _reason_for）。"""
    match = match_snippet("int x = 1;\nint y = 1;\n", "int", "long")
    assert match.status == "ambiguous"
    assert (match.start, match.end) == (-1, -1) and match.snippet == ""
    assert match.count == 2
    assert match.via_normalized is False


def test_match_snippet_ambiguous_normalized_multiple():
    """归一化多处命中 → ambiguous，count = 命中行数，via_normalized=True
    （来源判别字段，实施补录见工单实施记录）。"""
    match = match_snippet(
        "int a = 1;  /* one */\nint a = 2;  /* two */\n",
        "  int a =",
        "long a =",
    )
    assert match.status == "ambiguous"
    assert (match.start, match.end) == (-1, -1) and match.snippet == ""
    assert match.count == 2
    assert match.via_normalized is True


def test_match_snippet_body_diff_none():
    """语句本体不一致（行内空白重组）→ none：前缀比较失败，不模糊替换。"""
    match = match_snippet(
        "int x = 1;\nint main(void) { return x; }\n",
        "int x  = 1;",
        "int x = 2;",
    )
    assert match.status == "none"
    assert (match.start, match.end) == (-1, -1) and match.snippet == ""
    assert match.count == 0


def test_match_snippet_multiline_block_normalized():
    """多行片段 = 连续行块逐行前缀命中（红证迁移）：替换区间 = 整块行区间。"""
    match = match_snippet(
        "int a = 1;  /* one */\nint b = 2;\nint c = 3;\nint main(void) { return a + b + c; }\n",
        "    int a = 1;\n    int b = 2;",
        "int a = 1;\nint b = 20;",
    )
    assert match.status == "normalized"
    assert (match.start, match.end) == (0, 33)  # 前两行整块（含行尾换行）
    assert match.snippet == "int a = 1;\nint b = 20;\n"
    assert match.count == 1


def test_match_snippet_delete_whole_line_normalized():
    """new_snippet 空串 = 删整行：替换区间 = 整行（含换行），snippet = 空
    （空替换不补换行，整块删除）。"""
    match = match_snippet(
        "int x = 1;\nint main(void) { return x; }  /* entry */\n",
        "    int main(void)",
        "",
    )
    assert match.status == "normalized"
    assert (match.start, match.end) == (11, 53)  # 第二行整行（含换行）
    assert match.snippet == ""


def test_reason_for_wordings_verbatim():
    """四条文案逐字锚定（决策 2/3 单源）：exact 无文案 / normalized 标注 /
    none 与两种歧义三条 skipped 文案——改文案只动 _reason_for，本测试锁死现状
    （count 插值不变）。"""
    assert (
        _reason_for(
            SnippetMatch(status="exact", start=0, end=1, snippet="x", count=1)
        )
        == ""
    )
    assert (
        _reason_for(
            SnippetMatch(status="normalized", start=0, end=1, snippet="x", count=1)
        )
        == "按行首前缀归一化匹配应用"
    )
    assert (
        _reason_for(SnippetMatch(status="none", start=-1, end=-1, snippet="", count=0))
        == "未应用：文件内未找到 old_snippet（精确匹配失败，可能缩进 / 内容不一致）"
    )
    assert (
        _reason_for(
            SnippetMatch(status="ambiguous", start=-1, end=-1, snippet="", count=3)
        )
        == "未应用：old_snippet 在文件内出现 3 次（歧义，要求唯一匹配）"
    )
    assert (
        _reason_for(
            SnippetMatch(
                status="ambiguous",
                start=-1,
                end=-1,
                snippet="",
                count=2,
                via_normalized=True,
            )
        )
        == "未应用：old_snippet 按行首前缀归一化在文件内多处命中（2 处，歧义，要求唯一匹配）"
    )


def test_match_snippet_docstring_dual_with_fix_system_prompt():
    """协议对偶（决策记录 4，照 test_generate_check_contract 词表对偶先例）：
    匹配协议关键语义（行首前缀归一化 / 唯一匹配）在 FIX_SYSTEM_PROMPT 约束 2
    与 match_snippet docstring 同时存在——提示词改协议忘改判决、或判决改语义
    忘改提示词，任一侧红。"""
    from contest_generator.llm import FIX_SYSTEM_PROMPT

    assert "行首前缀归一化" in FIX_SYSTEM_PROMPT
    assert "唯一匹配" in FIX_SYSTEM_PROMPT
    doc = inspect.getdoc(match_snippet)
    assert doc is not None
    assert "行首前缀归一化" in doc
    assert "唯一匹配" in doc


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


# ---------------------------------------------------------------------------
# run_fix_round 单轮编排（工单 fix-session-homing/01）：假 LLM + 临时目录真实
# 语料，不依赖 HTTP/SSE（直调，对照 test_selection._run_recommendation 先例）——
# 事件序列 + done 载荷形状的家
# ---------------------------------------------------------------------------


def test_run_fix_round_event_sequence_and_done_payload(tmp_path):
    """事件序列（parse_done → fix_start → apply_result×n）+ done 载荷形状
    （keys 全等 + degraded / parsed / fixes 语义）+ 上下文透传——与路由直调
    （test_webapp _fix_stream）同语义同参。"""
    out = _make_project(tmp_path)
    emitted: list[ProgressEvent] = []
    llm = FakeLLM(
        fixes=(
            FixSuggestion(
                file="main.c", line=1, old_snippet="int x = 1;",
                new_snippet="int x = 2;", reason="修复初始化",
            ),
            FixSuggestion(
                file="code/mod.c", line=1, old_snippet="return 1;",
                new_snippet="return 0;", reason="修复返回值",
            ),
        )
    )
    done = run_fix_round(
        llm,
        error_text='main.c(1): error #20: identifier "x" is undefined\n'
                  "code/mod.c:1: error: return type mismatch",
        output_dir=out,
        backup_root=_backup_root(tmp_path),
        problem_text="赛题：做个小车",
        platform="stm32",
        module_slugs=("dht11", "oled"),
        main_c="int main(void) { return 0; }",
        emit=emitted.append,
    )
    assert [e.type for e in emitted] == [
        EVENT_PARSE_DONE,
        EVENT_FIX_START,
        EVENT_APPLY_RESULT,
        EVENT_APPLY_RESULT,
    ]
    parse_done = emitted[0]
    assert parse_done.error_count == 2 and parse_done.file_count == 2
    # done 载荷形状：keys 全等（与 /api/fix-errors 逐字一致）+ 语义
    assert set(done) == {"output_dir", "backup_id", "degraded", "parsed", "fixes"}
    assert done["output_dir"] == str(out)
    assert done["degraded"] is False
    assert done["parsed"] == [
        {"path": "main.c", "line": 1, "message": 'main.c(1): error #20: identifier "x" is undefined'},
        {"path": "code/mod.c", "line": 1, "message": "code/mod.c:1: error: return type mismatch"},
    ]
    assert done["fixes"] == [
        {"file": "main.c", "line": 1, "status": "applied", "reason": ""},
        {"file": "code/mod.c", "line": 1, "status": "applied", "reason": ""},
    ]
    assert done["backup_id"]
    # 文件已写回 + 备份（与路由直调同语义）
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 2;\nint main(void) { return x; }\n"
    backup_dir = _backup_root(tmp_path) / done["backup_id"]
    assert (backup_dir / "main.c").is_file()
    # 上下文透传（题面 / 平台 / 模块 / main.c）——与 llm.fix_compile_errors 同参
    call = llm.fix_errors_calls[0]
    assert call[0] == 'main.c(1): error #20: identifier "x" is undefined\ncode/mod.c:1: error: return type mismatch'
    assert call[1] == {
        "main.c": "int x = 1;\nint main(void) { return x; }\n",
        "code/mod.c": "int mod(void) { return 1; }\n",
    }
    assert call[2] == "赛题：做个小车" and call[3] == "stm32"
    assert call[4] == ("dht11", "oled") and call[5] == "int main(void) { return 0; }"


def test_run_fix_round_degraded_mode_and_emit_none(tmp_path):
    """报错无文件引用 → 降级模式：degraded=True / fixes=[] / backup_id=""
    （与路由直调同语义）；emit=None（旁路跳过）照常返回 done 载荷。"""
    out = _make_project(tmp_path)
    done = run_fix_round(
        FakeLLM(),  # 默认空 fixes
        error_text="L6200E: Symbol foo multiply defined (by main.o and bar.o)",
        output_dir=out,
        backup_root=_backup_root(tmp_path),
    )
    assert done["degraded"] is True
    assert done["fixes"] == [] and done["backup_id"] == ""
    assert done["parsed"] == []


def test_run_fix_round_emitter_failure_bypassed(tmp_path):
    """发射器抛错 → 旁路吞掉（spec「发射 seam」），主流程照常返回 done 载荷。"""
    out = _make_project(tmp_path)

    def boom(event: ProgressEvent) -> None:
        raise RuntimeError("发射器挂了")

    done = run_fix_round(
        FakeLLM(),
        error_text="main.c(1): error #20: boom",
        output_dir=out,
        backup_root=_backup_root(tmp_path),
        emit=boom,
    )
    assert done["degraded"] is False
    assert done["parsed"][0]["path"] == "main.c"


# 上一轮应用结果回喂（工单 fix-loop-progress/01）：形状校验（非法 → FixError
# → 400 中文，登记 errors.py）/ 合法转传 LLM / 缺省空零回归（done 载荷与
# 事件序列不动，previous 只进 LLM 素材）


@pytest.mark.parametrize(
    "invalid",
    [
        "main.c",  # 非对象
        {"file": 1, "line": 1, "status": "applied", "reason": ""},  # file 非字符串
        {"file": "main.c", "line": "1", "status": "applied", "reason": ""},  # line 非整数
        {"file": "main.c", "line": 1, "status": "rejected", "reason": ""},  # status 越枚举
        {"file": "main.c", "line": 1, "status": "applied", "reason": 3},  # reason 非字符串
        {"line": 1, "status": "applied", "reason": ""},  # 缺 file
    ],
)
def test_run_fix_round_previous_fixes_invalid_shape(tmp_path, invalid):
    """形状校验：每项 dict + file/status/reason 字符串 + line 整数 + status ∈
    {applied, skipped}——非法 → FixError 且登记 errors.py → 400 中文
    （验收：非法项 400，大声失败不静默丢弃）。"""
    out = _make_project(tmp_path)
    with pytest.raises(FixError, match="previous_fixes") as exc_info:
        run_fix_round(
            FakeLLM(),
            error_text="main.c(1): error #20: boom",
            output_dir=out,
            backup_root=_backup_root(tmp_path),
            previous_fixes=(invalid,),
        )
    status, message = error_entry(exc_info.value)
    assert status == 400
    assert message == str(exc_info.value)


def test_run_fix_round_previous_fixes_not_array(tmp_path):
    """previous_fixes 本身不是数组（dict / null 形态）→ FixError（400 中文），
    不落 500——路由原样透传，形状判决全归域层。"""
    out = _make_project(tmp_path)
    with pytest.raises(FixError, match="数组"):
        run_fix_round(
            FakeLLM(),
            error_text="main.c(1): error #20: boom",
            output_dir=out,
            backup_root=_backup_root(tmp_path),
            previous_fixes={"file": "main.c"},
        )


def test_run_fix_round_previous_fixes_passthrough_to_llm(tmp_path):
    """合法 previous_fixes → 原样转传 llm.fix_compile_errors（逐项只留四字段）；
    done 载荷形状与事件序列不动（previous 只进 LLM 素材，不发射新事件）。"""
    out = _make_project(tmp_path)
    emitted: list[ProgressEvent] = []
    llm = FakeLLM(
        fixes=(
            FixSuggestion(file="main.c", line=1, old_snippet="int x = 1;",
                          new_snippet="int x = 2;", reason="修复初始化"),
        )
    )
    previous = (
        {"file": "main.c", "line": 1, "status": "skipped",
         "reason": "未应用：文件内未找到 old_snippet（精确匹配失败，可能缩进 / 内容不一致）"},
        {"file": "code/mod.c", "line": 1, "status": "applied", "reason": ""},
    )
    done = run_fix_round(
        llm,
        error_text="main.c(1): error #20: boom",
        output_dir=out,
        backup_root=_backup_root(tmp_path),
        previous_fixes=previous,
        emit=emitted.append,
    )
    assert [e.type for e in emitted] == [
        EVENT_PARSE_DONE,
        EVENT_FIX_START,
        EVENT_APPLY_RESULT,
    ]
    assert set(done) == {"output_dir", "backup_id", "degraded", "parsed", "fixes"}
    assert llm.fix_errors_calls[0][6] == previous


def test_run_fix_round_no_previous_zero_regression(tmp_path):
    """缺省空 = 行为与现有一致：透传空元组、done 载荷形状不变（验收：空列表
    零回归——贴文本模式 / 旧调用零改动）。"""
    out = _make_project(tmp_path)
    llm = FakeLLM(
        fixes=(
            FixSuggestion(file="main.c", line=1, old_snippet="int x = 1;",
                          new_snippet="int x = 2;", reason="修复初始化"),
        )
    )
    done = run_fix_round(
        llm,
        error_text="main.c(1): error #20: boom",
        output_dir=out,
        backup_root=_backup_root(tmp_path),
    )
    assert set(done) == {"output_dir", "backup_id", "degraded", "parsed", "fixes"}
    assert done["fixes"] == [
        {"file": "main.c", "line": 1, "status": "applied", "reason": ""}
    ]
    assert llm.fix_errors_calls[0][6] == ()


# ---------------------------------------------------------------------------
# 结构钉（工单 fix-session-homing/01，对照 recommend-orchestration-homing 先例）：
# /api/fix-errors 路由只取参 + 转调 + SSE 包装，五步编排整体归 run_fix_round——
# 管线内部原语回 webapp 即红（AST 断言，参照 test_webapp.py 同款切片风格）
# ---------------------------------------------------------------------------

_WEBAPP_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "contest_generator" / "webapp.py"
)
_FIX_ERRORS_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "contest_generator" / "fix_errors.py"
)


def _webapp_tree() -> ast.Module:
    return ast.parse(_WEBAPP_PATH.read_text(encoding="utf-8"))


def test_webapp_imports_run_fix_round_not_pipeline_primitives():
    """结构钉：webapp 的 fix_errors import 面收敛到 run_fix_round + 外壳原语——
    五步管线内部符号（apply_fixes / collect_candidate_paths / read_file_contexts）
    再被 webapp 直接 import 即红（编排回路由 = 域函数被架空）。parse_compile_errors
    仍被 /api/compile 使用（编译结果 parsed_errors，compile-verdict-align/01），
    不在钉内。"""
    tree = _webapp_tree()
    imported: set[str] = set()
    for node in ast.walk(tree):
        # 相对 import 在 AST 中 module 为 "fix_errors"（level=1），绝对形态为
        # "contest_generator.fix_errors"——统一按末段匹配
        if isinstance(node, ast.ImportFrom) and (
            node.module is not None and node.module.split(".")[-1] == "fix_errors"
        ):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
    assert "run_fix_round" in imported, "run_fix_round 未入 webapp import（编排未归位）"
    leaked = imported & {"apply_fixes", "collect_candidate_paths", "read_file_contexts"}
    assert not leaked, f"管线内部原语回 webapp import：{sorted(leaked)}"


def test_fix_errors_route_body_free_of_pipeline_calls():
    """结构防回退：/api/fix-errors 路由函数体不含五步管线直接调用（parse /
    collect / read / apply / llm.fix_compile_errors）——编排归位 run_fix_round，
    路由只剩取参 + 转调 + SSE 包装（emit.done 收尾保留，决策记录 4）。"""
    tree = _webapp_tree()
    routes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "fix_errors"
    ]
    assert len(routes) == 1, "webapp.py 应恰好一个 fix_errors 路由函数"
    route = routes[0]
    forbidden: list[ast.Call] = []
    for node in ast.walk(route):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in {
            "parse_compile_errors",
            "collect_candidate_paths",
            "read_file_contexts",
            "apply_fixes",
        }:
            forbidden.append(node)
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "llm"
            and node.func.attr == "fix_compile_errors"
        ):
            forbidden.append(node)
    assert not forbidden, (
        "/api/fix-errors 路由含五步管线调用，编排必须归 run_fix_round："
        + "；".join(ast.unparse(node) for node in forbidden)
    )


def test_apply_fixes_body_free_of_matching_primitives():
    """结构钉（工单 fix-match-seam/01 决策记录 5）：写回循环只消费 match_snippet
    判决——apply_fixes 函数体再出现 content.count( 直调 / _normalized_hits(
    直调即红（匹配判决必须经 match_snippet 单源，改匹配规则不用动写回循环）；
    正向钉：判决确经 match_snippet（接缝消失即红）。"""
    tree = ast.parse(_FIX_ERRORS_PATH.read_text(encoding="utf-8"))
    funcs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "apply_fixes"
    ]
    assert len(funcs) == 1, "fix_errors.py 应恰好一个 apply_fixes 函数"
    func = funcs[0]
    forbidden: list[ast.Call] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "_normalized_hits":
            forbidden.append(node)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "count"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "content"
        ):
            forbidden.append(node)
    assert not forbidden, (
        "apply_fixes 直调匹配原语，判决必须经 match_snippet："
        + "；".join(ast.unparse(node) for node in forbidden)
    )
    calls = [
        node
        for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "match_snippet"
    ]
    assert calls, "apply_fixes 未调用 match_snippet（判决接缝消失）"
