"""上传暂存域（工单 02）：stage.py 原语的专属测试。

暂存语义（穿越拒绝 / 目录名清洗 / 噪音跳过 / 上限 / 空清单 / 落盘）此前
全部内联在 webapp 路由里、HTTP 外不可测——本文件直接测原语本身；路由层的
行为等价由 tests/test_webapp.py 的 stage 测试覆盖。穿越规则吃
entry_store.is_unsafe_path 单源（行为变化：空段 a//b 从放行变拒绝），
噪音跳过与扫描侧 iter_project_files 同一套（treewalk.skip_project_noise，
首段文件夹名剥除后传）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.stage import (
    STAGE_MAX_TOTAL_BYTES,
    StageError,
    stage_project_files,
    staged_root,
)


def test_staged_root_derivation(tmp_path: Path) -> None:
    """暂存目录位置纯推导：母版库同级 staged/。"""
    assert staged_root(tmp_path / "masters") == tmp_path / "staged"


def test_max_total_bytes_constant() -> None:
    """上限常量：512MB（防误选大目录，文案带 512MB）。"""
    assert STAGE_MAX_TOTAL_BYTES == 512 * 1024 * 1024


@pytest.mark.parametrize(
    "rel",
    [
        "..",          # 裸上级段
        "../evil.c",   # 上级段夹带
        "/abs/evil.c",  # 绝对路径（前导 /）
        "C:/evil.c",   # 盘符
        "a//b",        # 空段（行为变化：原内联检查放行，is_unsafe_path 拒绝）
        "/evil.c",     # 前导 /（单独形态）
    ],
)
def test_traversal_rejected(tmp_path: Path, rel: str) -> None:
    """穿越六态全部 StageError（文案 = 原路由 HTTPException 逐字），不落盘。"""
    with pytest.raises(StageError, match="非法文件路径"):
        stage_project_files(tmp_path / "masters", [(rel, b"x")])


def test_traversal_message_repr_verbatim(tmp_path: Path) -> None:
    """文案逐字：带被拒路径的 repr（浏览器应传文件夹内相对路径）。"""
    with pytest.raises(StageError) as exc:
        stage_project_files(tmp_path / "masters", [("../evil.c", b"x")])
    assert str(exc.value) == "非法文件路径：'../evil.c'（浏览器应传文件夹内相对路径）"


def test_name_sanitization(tmp_path: Path) -> None:
    """目录名首段白名单清洗（现状逐字）：非法字符换 _（只影响返回名，写盘
    用原始 parts——返回名与真实目录名可分歧）、全空白回退 "upload"。"""
    # "&" 被清洗成 "_"（返回名），但写盘走原始 parts → 真实目录是 "proj&"：
    # 清洗只影响返回名是现状（Windows 上 *?/ 等字符写盘会 OSError→400）
    result = stage_project_files(tmp_path / "m", [("proj&/x.c", b"x")])
    assert result.name == "proj_"
    assert (result.parent / "proj&" / "x.c").read_bytes() == b"x"
    # 全白名单字符：原样保留
    result = stage_project_files(tmp_path / "m", [("a b-c_d.e/x.c", b"x")])
    assert result.name == "a b-c_d.e"
    assert (result / "x.c").read_bytes() == b"x"
    # 全空白首段（strip 后为空）→ 回退 "upload"；文件命中 .git 噪音不落盘
    # （纯空白目录名 Windows 无法写盘，借噪音文件测回退名本身）
    result = stage_project_files(tmp_path / "m", [("   /.git/config", b"x")])
    assert result.name == "upload"


def test_noise_skipped_any_depth_git_and_build_outputs(tmp_path: Path) -> None:
    """噪音跳过：.git 任意深度 + 构建产物目录（顶层 + Keil 输出任意层级），
    与扫描侧 iter_project_files 同一套规则；非噪音目录照常落盘。"""
    result = stage_project_files(
        tmp_path / "masters",
        [
            ("proj/.git/HEAD", b"ref: refs/heads/main\n"),
            ("proj/.git/hooks/pre-commit", b"x"),
            ("proj/src/.git/config", b"x"),      # 任意深度 .git
            ("proj/Debug/out.axf", b"x"),        # 顶层构建产物
            ("proj/Release/out.axf", b"x"),
            ("proj/Listings/p.lst", b"x"),
            ("proj/Objects/p.crf", b"x"),
            ("proj/src/Objects/x.o", b"x"),      # Keil 输出任意层级
            ("proj/main.c", b"int main(void){}"),
            ("proj/.vscode/settings.json", b"{}"),   # 非噪音：照常落盘
            ("proj/Debugger/target.c", b"x"),        # Debugger ≠ Debug：前缀不误杀
        ],
    )
    assert (result / "main.c").read_bytes() == b"int main(void){}"
    assert (result / ".vscode" / "settings.json").read_bytes() == b"{}"
    assert (result / "Debugger" / "target.c").read_bytes() == b"x"
    for noise in (".git", "Debug", "Release", "Listings", "Objects"):
        assert not (result / noise).exists()
    assert sorted(p.name for p in result.iterdir()) == [".vscode", "Debugger", "main.c"]


def test_files_land_with_content_and_dirs(tmp_path: Path) -> None:
    """落盘实况：相对路径原样落盘（含反斜杠归一）、目录自动建、内容逐字。"""
    result = stage_project_files(
        tmp_path / "masters",
        [
            ("proj\\src\\main.c", b"int main(void){}"),  # 反斜杠 → '/' 归一
            ("proj/inc/conf.h", b"#pragma once\n"),
            ("proj/src/deep/nested/x.txt", b"deep"),
        ],
    )
    assert result == tmp_path / "staged" / "proj"
    assert (result / "src" / "main.c").read_bytes() == b"int main(void){}"
    assert (result / "inc" / "conf.h").read_bytes() == b"#pragma once\n"
    assert (result / "src" / "deep" / "nested" / "x.txt").read_bytes() == b"deep"


def test_total_size_cap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """总量上限：跨文件累计超限 → StageError（文案逐字 = 512MB），已落的不回滚。"""
    monkeypatch.setattr("contest_generator.stage.STAGE_MAX_TOTAL_BYTES", 10)
    with pytest.raises(StageError, match="文件夹过大（超过 512MB），请只选择工程源码目录"):
        stage_project_files(
            tmp_path / "masters",
            [("proj/a.c", b"1234567"), ("proj/b.c", b"1234567")],
        )


def test_single_file_over_cap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """单文件即超限也拒绝（上限是总量不是单文件）。"""
    monkeypatch.setattr("contest_generator.stage.STAGE_MAX_TOTAL_BYTES", 10)
    with pytest.raises(StageError, match="文件夹过大"):
        stage_project_files(tmp_path / "masters", [("proj/big.bin", b"x" * 11)])


def test_empty_file_list_raises(tmp_path: Path) -> None:
    """空文件清单 → StageError（文案逐字，浏览器整夹上传逐文件）。"""
    with pytest.raises(StageError, match="没有收到任何文件（选择文件夹后浏览器会逐文件上传）"):
        stage_project_files(tmp_path / "masters", [])
