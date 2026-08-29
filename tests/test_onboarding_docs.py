"""新手引导文档门禁（工单 newcomer-onboarding/01）：README 与 install.bat 必须存在、
面向纯新人（中文、含关键步骤与前置条件），防止回归为「只有代码没有说明书」。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _cjk_count(text: str) -> int:
    return len(_CJK_RE.findall(text))


def test_readme_exists_and_is_chinese():
    """README.md 存在、非空、中文为主（新手说明书，不是英文说明）。"""
    readme = ROOT / "README.md"
    assert readme.is_file(), "缺少 README.md（新手说明书，工单 newcomer-onboarding/01）"
    text = readme.read_text(encoding="utf-8", errors="replace")
    assert len(text.strip()) > 200, "README.md 内容过短"
    assert _cjk_count(text) >= 30, "README.md 中文字符不足（应为中文说明书）"


def test_readme_covers_newcomer_essentials():
    """README 覆盖纯新人需要知道的事：Python 版本、API key、板子/IDE、安装与启动。"""
    readme = ROOT / "README.md"
    assert readme.is_file(), "缺少 README.md"
    text = readme.read_text(encoding="utf-8", errors="replace").lower()
    for needle in ("3.13", "python", "deepseek", "api key", "keil", "ccs",
                   "install.bat", "start-app"):
        assert needle in text, f"README.md 缺少关键内容：{needle}"
    for needle in ("stm32f103c8t6", "mspm0g3507"):
        assert needle in text, f"README.md 未提及板子型号：{needle}"


def test_install_bat_exists_and_chinese():
    """install.bat 存在、GBK 中文提示、含安装主流程（建虚拟环境 + 装依赖）。"""
    bat = ROOT / "install.bat"
    assert bat.is_file(), "缺少 install.bat（一键安装脚本，工单 newcomer-onboarding/01）"
    raw = bat.read_bytes()
    assert b"\xef\xbb\xbf" not in raw[:3], "install.bat 不应是 UTF-8 BOM（CMD 按 ANSI 解析）"
    # GBK 解码尝试（与 CMD 中文 Windows 默认一致）
    try:
        text = raw.decode("gbk")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")
    assert _cjk_count(text) >= 20, "install.bat 中文提示不足"
    for needle in ("pip install -e .", ".venv", "python.org"):
        assert needle in text, f"install.bat 缺少安装主流程：{needle}"


def test_start_app_bat_has_health_and_chinese_popups():
    """start-app.bat（工单 newcomer-onboarding/02）：用 /api/health 判定端口归属、
    失败分支弹中文提示（不再静默 exit /b 1）。"""
    bat = ROOT / "start-app.bat"
    assert bat.is_file(), "缺少 start-app.bat"
    text = bat.read_bytes().decode("gbk", errors="replace")
    assert "/api/health" in text, "start-app.bat 未使用 /api/health 判定本应用"
    assert "Popup" in text, "start-app.bat 失败分支无弹窗"
    assert "启动失败" in text, "start-app.bat 弹窗标题非中文"
    assert ".venv\\Scripts\\python.exe" in text, "start-app.bat 未优先 .venv"
