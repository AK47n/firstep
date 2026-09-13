"""PowerShell 5.1 编码门禁：仓库内 .ps1 必须存成 UTF-8 with BOM。

背景：Windows PowerShell 5.1 对无 BOM 的 .ps1 按系统 ANSI 代码页（中文系统为
GBK/CP936）解码。UTF-8 中文注释的字节流被 GBK 双字节硬配对后，若行尾恰好
留下一个"前导字节"，它与换行符 0x0A 构成无效配对、被解码器双双丢弃——
换行符消失，注释行与下一行代码合并为一行，下一行整行被注释吞掉（"行解析
错位"，实际表现为变量/语句丢失、行为与源码不符）。

是否吞行取决于逐字节配对路径（0x80 单字节映射 € 会翻转配对奇偶性），无法
用字符数奇偶推断，因此约定：所有 .ps1 一律 UTF-8 with BOM（EF BB BF），
引擎据此按 UTF-8 解码，不存在上述问题。sources/ 下的第三方/vendored 脚本
不受本约定管辖。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_UTF8_BOM = b"\xef\xbb\xbf"

# sources/ 为赛题素材与第三方源码（vendored），不适用本仓库脚本约定；
# node_modules/ 同理（npm 装的第三方包，工单 module-intro-detail/05 引入 playwright
# 真机验收后才出现——包内的 .ps1 是别人写的，我们不改，也管不着）；
# .venv/ 与 venv/ 是**本机虚拟环境**（`install.bat` / `python -m venv` 生成）：
# venv 自带的 `Scripts\Activate.ps1` 由标准库生成、无 BOM，不是我们的脚本，也随时会被重建
# ——2026-09-13 工单 newuser-download/07 在真身跑过 install.bat 后，这个门禁第一次撞上它。
_EXCLUDE_PREFIXES = (
    ROOT / "sources",
    ROOT / "node_modules",
    ROOT / ".venv",
    ROOT / "venv",
)


def _is_repo_script(path: Path) -> bool:
    absolute = path.resolve()
    return not any(str(absolute).startswith(str(p.resolve())) for p in _EXCLUDE_PREFIXES)


def test_all_ps1_files_have_utf8_bom():
    """仓库内所有 .ps1 必须带 UTF-8 BOM（PS 5.1 无 BOM 会按 ANSI 解码导致吞行）。"""
    ps1_files = sorted(
        p for p in ROOT.rglob("*.ps1")
        if p.is_file() and _is_repo_script(p)
    )
    offenders = []
    for path in ps1_files:
        head = path.read_bytes()[:3]
        if head != _UTF8_BOM:
            offenders.append(path.relative_to(ROOT))
    assert not offenders, (
        "以下 .ps1 缺少 UTF-8 BOM（PS 5.1 会按 ANSI/GBK 解码，中文注释可能吞掉下一行代码）：\n"
        + "\n".join(str(p) for p in offenders)
    )


def test_no_nonascii_ps1_without_bom():
    """冗余兜底：含非 ASCII 字节的 .ps1 必须有 BOM（若 _UTF8_BOM 规则被放宽仍有此防线）。"""
    ps1_files = sorted(
        p for p in ROOT.rglob("*.ps1")
        if p.is_file() and _is_repo_script(p)
    )
    offenders = []
    for path in ps1_files:
        data = path.read_bytes()
        has_non_ascii = any(b >= 0x80 for b in data)
        if has_non_ascii and data[:3] != _UTF8_BOM:
            offenders.append(path.relative_to(ROOT))
    assert not offenders, (
        "以下含中文/非 ASCII 的 .ps1 缺少 UTF-8 BOM（PS 5.1 下中文注释会被 ANSI 解码并可能吞行）：\n"
        + "\n".join(str(p) for p in offenders)
    )
