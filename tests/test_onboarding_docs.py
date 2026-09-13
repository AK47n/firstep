"""新手引导文档门禁（工单 newcomer-onboarding/01）：README 与 install.bat 必须存在、
面向纯新人（中文、含关键步骤与前置条件），防止回归为「只有代码没有说明书」。"""

from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _cjk_count(text: str) -> int:
    return len(_CJK_RE.findall(text))


def _install_bat_text() -> str:
    """install.bat 按 GBK 解码（与 CMD 在中文 Windows 上的解析一致）。"""
    return (ROOT / "install.bat").read_bytes().decode("gbk", errors="replace")


def _extract_shortcut_payload() -> str:
    """从 install.bat 提取桌面快捷方式负载的 Base64 串（唯一 set 点，命名即契约）。"""
    m = re.search(r"set\s+FIRSTEP_SHORTCUT_PS=([\w+/=]+)", _install_bat_text())
    assert m, "install.bat 缺少 FIRSTEP_SHORTCUT_PS 负载（桌面快捷方式，工单 beginner-shortcut/01）"
    return m.group(1)


def _shortcut_payload() -> str:
    """安装收尾那段快捷方式负载（UTF-16LE + Base64）解码后的 PowerShell 文本。"""
    return base64.b64decode(_extract_shortcut_payload()).decode("utf-16-le")


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


def test_install_bat_creates_desktop_shortcut():
    """install.bat 收尾建桌面快捷方式（工单 beginner-shortcut/01）：
    入口链路完整（wscript 跑 vbs + 幂等跳过），完成提示给出两个入口。"""
    text = _install_bat_text()
    payload = _shortcut_payload()
    assert "wscript.exe" in payload, "快捷方式未用 wscript.exe 起 start-app.vbs（会闪黑窗口）"
    assert "start-app.vbs" in payload, "快捷方式未指向 start-app.vbs"
    assert "Test-Path $p" in payload, "快捷方式缺幂等判据（重跑会覆盖用户改过的图标）"
    assert "快捷方式" in text, "install.bat 提示文案未提桌面快捷方式"
    done = text[text.rfind("安装完成"):]
    assert "firstep" in done and "start-app.vbs" in done, "安装完成提示未同时给出两个入口"


def test_install_bat_shortcut_payload_is_valid_powershell():
    """负载必须真的是可解析的 PowerShell（工单 beginner-shortcut/01）——手改坏 Base64 要当场红。"""
    payload = _shortcut_payload()
    assert "$env:FIRSTEP_ROOT" in payload, "负载未使用 FIRSTEP_ROOT 传工具根（cmd 不导出变量，会拿到空路径）"
    assert "firstep.lnk" in payload, "负载未创建 firstep.lnk"
    probe = (
        "$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
        + base64.b64encode(payload.encode("utf-8")).decode("ascii")
        + "'));"
        "$e=$null;[void][Management.Automation.Language.Parser]::ParseInput($t,[ref]$null,[ref]$e);"
        "if($e.Count){exit 1}"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", probe],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, f"快捷方式负载不是合法 PowerShell：{result.stdout}{result.stderr}"
