"""新手引导文档门禁（工单 newcomer-onboarding/01）：README 与 install.bat 必须存在、
面向纯新人（中文、含关键步骤与前置条件），防止回归为「只有代码没有说明书」。

另含下载渠道门禁（工单 newuser-download/01）：README 的「获取方式」必须只描述**线上真实存在**
的资产形态——曾经出现的 `firstep-full.7z.001~004` / 约 6 GB / 需第三方解压软件，在最新 release
上根本不存在（那只是 v1.0.0 那个 release 的形态），会把新用户直接带进死路。
"""

from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# 「获取方式」章的定位锚（README 章节标题；改标题就要同步改这里）
_README_DOWNLOAD_HEADING = "## 获取方式"

# 已下线 / 不存在的下载形态（工单 newuser-download/01）。
# 判据分两类，都只钉「叫用户去用」的写法，不钉「不需要它」的提醒——
# README 明确写「不用装 7-Zip」是有用的防坑说明，不该被门禁误伤：
#   A) 第三方解压工具名：命中工具名后回看 `_NEGATION_LOOKBACK` 个字符，取**最近**一个否定词，
#      距离在其允许窗口内 = 「不用它」的提醒，放行（长否定词窗口宽、短否定词窗口窄，
#      见 `_NEGATION_WINDOWS`）；工具名**后面**紧跟否定词的写法（`7-Zip 不用装`）也放行。
#      （不用正则写变长否定回看：Python 的 look-behind 不支持变长，而「可选否定前缀」写法会被
#       引擎从动词处另起一次空前缀匹配，反而把否定式判成命中——踩过。）
#   B) 7z 分卷文件名：本身就只可能出现在已下线渠道里，直接钉死。
_DEAD_TOOL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"7-?[Zz]ip", "README 仍在提第三方解压工具 7-Zip"),
    (r"Bandizip", "README 仍在提第三方解压工具 Bandizip"),
    (r"WinRAR", "README 仍在提第三方解压工具 WinRAR"),
)
_DEAD_CHANNEL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"firstep-full\.7z", "README 仍在提 v1.0.0 那个 7z 分卷形态（最新 release 上不存在）"),
    (r"7z\.001", "README 仍引用 7z 分卷文件名（已下线渠道）"),
    (r"解压\s*`?\.001", "README 在教解压 7z 分卷（已下线渠道）"),
)
# 否定词 → 「工具名与它的最大允许距离」。短否定词容易误判成正文里的「不」，窗口收紧；
# 长否定词不会误判，窗口放宽（否定 + 动词 + 工具名可能相隔十几个字）。
_NEGATION_WINDOWS: tuple[tuple[str, int], ...] = (
    ("无需", 16),
    ("不需", 16),
    ("没有", 16),
    ("不用", 10),
    ("不要", 10),
    ("别", 8),
    ("免", 8),
    ("不", 5),
    ("没", 4),
)
_NEGATION_LOOKBACK = 20
# 工具名**之后**的窗口只给这么宽：再远就可能是与工具无关的话（`用 7-Zip 打开，不用装插件`）。
# 收紧的代价是漏掉「7-Zip 也完全不需要装」这种（实测 5 字）绕嘴写法——可接受。
_NEGATION_TAIL_WINDOW = 4
_TAIL_NEGATION_RE = re.compile(r"\s*(?:不用|不必|不需要|无需|不需|免|别)")

# 「获取方式」章内**一个字都不许提**的第三方解压工具名（工单 newuser-download/01）：
# 新用户第一屏不该出现「要不要装解压软件」的疑问，那里的口径是「系统自带解压」。
# 提醒式写法（「不用装 Bandizip 也行」）放在常见问题里——那里由 `dead_channel_hits`
# 的否定式判据管，既不误伤提醒、也不放过推荐。
_DOWNLOAD_SECTION_BANNED = ("7-zip", "7zip", "bandizip", "winrar", "好压")


def _readme_text() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")


def dead_channel_hits(text: str) -> list[tuple[str, str]]:
    """返回「已下线渠道」的真实命中（原因，命中片段）；否定式提醒不算命中。

    A 类（第三方解压工具名）回看 `_NEGATION_LOOKBACK` 个字符，取**最近**一个否定词，
    距离在其允许窗口内 = 「不用它」的提醒，放行（长否定词窗口宽、短否定词窗口窄，
    见 `_NEGATION_WINDOWS`）；B 类（7z 分卷文件名）直接命中。
    探针 `.scratch/newuser-download/probe-01-guard-effectiveness.py` 对本函数做红/绿两向验证。
    """
    hits: list[tuple[str, str]] = []
    for pattern, why in _DEAD_TOOL_PATTERNS:
        for m in re.finditer(pattern, text):
            prefix = text[max(0, m.start() - _NEGATION_LOOKBACK): m.start()]
            negated = False
            for word, window in _NEGATION_WINDOWS:
                at = prefix.rfind(word)
                if at >= 0:
                    negated = len(prefix) - (at + len(word)) <= window
                    break  # 只看最近的那个否定词
            if not negated:
                tail = text[m.end(): m.end() + _NEGATION_TAIL_WINDOW]
                negated = bool(_TAIL_NEGATION_RE.match(tail))
            if negated:
                continue
            hits.append((why, m.group(0)))
    for pattern, why in _DEAD_CHANNEL_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            hits.append((why, m.group(0)))
    return hits


def _readme_download_section() -> str:
    """README「获取方式」章正文（到下一个二级标题为止）。"""
    text = _readme_text()
    start = text.find(_README_DOWNLOAD_HEADING)
    assert start >= 0, f"README 缺少「{_README_DOWNLOAD_HEADING}」章节（新用户第一屏的下载说明）"
    rest = text[start + len(_README_DOWNLOAD_HEADING):]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


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


def test_readme_download_channel_is_live_shape():
    """「获取方式」只描述线上真实存在的资产形态（工单 newuser-download/01）：

    当前完整包 = `firstep-full-<版本>.zip`（单卷、标准 zip、系统自带解压），
    新用户不需要第三方解压软件、也不需要去找 7z 分卷。
    `START-HERE.txt` 的断言留到工单 02（包内文件落地后再钉）。
    """
    text = _readme_text()
    hits = dead_channel_hits(text)
    assert not hits, f"README 出现已下线/不存在的下载形态：{hits}"

    section = _readme_download_section()
    lowered = section.lower()
    for banned in _DOWNLOAD_SECTION_BANNED:
        assert banned not in lowered, (
            f"「获取方式」不该提第三方解压工具「{banned}」——该处口径是 zip + 系统自带解压，"
            "出现它会让新用户以为要额外装软件"
        )
    assert "firstep-full-" in section, "「获取方式」未给出完整包资产名（用户不知道下哪个文件）"
    assert "releases/latest" in section, (
        "「获取方式」应指向 Releases 最新版页（写死某个 tag 深链会在下次发版后失效）"
    )
    assert re.search(r"自带解压|全部解压缩", section), "「获取方式」未说明用 Windows 自带解压即可"

    # 「哪个文件给谁下」：三行必须各自说明用途
    for row, who in (
        ("firstep-full-", "新用户"),
        ("firstep-update-", "已装用户"),
        ("sha256", "不用下"),
    ):
        line = next((ln for ln in section.splitlines() if ln.startswith("| ") and row in ln), "")
        assert line, f"「获取方式」缺少 `{row}` 的说明行"
        assert who in line, f"`{row}` 那行未写清给谁用（应含「{who}」）"


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
