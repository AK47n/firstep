"""生成输出目标解析：桌面赛题目录命名与唯一化。

webapp 只负责收请求与调用 LLM；题名裁剪、Windows 文件名清洗和重名策略在
这里集中，避免把生成输出域逻辑塞进路由薄壳。
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from .context_manifest import CONTEXT_MANIFEST_FILENAME
from .platforms import PLATFORM_DIR_SUFFIXES

WINDOWS_RESERVED_FILENAMES = frozenset(
    {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
_INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*]+')
_FILENAME_WHITESPACE_RE = re.compile(r"\s+")
_TOPIC_LINE_MARKDOWN_RE = re.compile(r"^#{1,6}\s*")
_TOPIC_LINE_PREFIX_RE = re.compile(r"^[A-Za-z0-9]+\s*题\s*[:：]\s*")
_TOPIC_TRAILING_PAREN_RE = re.compile(r"（[^）]*(?:题|本科|高职|组)[^）]*）$")
# ASCII 兜底：非字母数字序列整体切词（保留运行号/字母 token，防 2026C 这类
# 名字在兜底时整段中文全丢）。
_ASCII_KEEP_WORDS_RE = re.compile(r"[^A-Za-z0-9]+")

# 中文短题名 → 英文目录名单词（工单 ascii-project-name/01）：历史赛题目录名
# 确定性来源——键 = topic_short_title 的提取结果（题面首行短题名），值 = 英文
# 短名（下划线连接单词，无空格无中文）。覆盖现题库全部 9 题；未收录题走
# ASCII 兜底（topic_en_title）。
TOPIC_EN_TITLES: dict[str, str] = {
    "自动行驶小车": "Auto_Car",
    "智能送药小车": "Smart_Medicine_Car",
    "小车跟随行驶系统": "Car_Following_System",
    "无线充电电动小车": "Wireless_Charging_Electric_Car",
    "电动小车动态无线充电系统": "Dynamic_Wireless_Charging_System",
    "坡道行驶电动小车": "Slope_Driving_Electric_Car",
    "2026年全国大学生电子设计竞赛赛区赛(TI杯)": "2026_TI_Cup",
    # 2026H（赛区赛暨模拟电子系统设计专题赛选拔赛）：题面首行与 2026C 同源
    # 但格式不同（全角括号 + 空格 + 破折号后缀），单独登记避免 ASCII 兜底丢字
    "2026 年全国大学生电子设计竞赛赛区赛（TI 杯）—— 暨模拟电子系统设计专题赛选拔赛赛题": "2026_TI_Cup_Analog_Electronics_Selection",
}


def topic_short_title(problem_text: str) -> str:
    """赛题题面首行 → 短题名（目录名用，确定性）。

    历史赛题首行形态：`自动行驶小车（H 题）` / `C 题：无线充电电动小车（本科）`
    / `# 基于无线通信的数字钥匙实验系统（C题）`——去掉 markdown 标题符、
    行首题号前缀与行尾（题号/组别）括号，得 `自动行驶小车` 式短名。
    """
    first = next(
        (line.strip() for line in problem_text.splitlines() if line.strip()), ""
    )
    line = _TOPIC_LINE_MARKDOWN_RE.sub("", first)
    line = _TOPIC_LINE_PREFIX_RE.sub("", line).strip()
    line = _TOPIC_TRAILING_PAREN_RE.sub("", line).strip()
    return line or first


def topic_en_title(short_title: str) -> str:
    """中文短题名 → 英文短名（目录名用，工单 ascii-project-name/01）。

    命中 TOPIC_EN_TITLES 字典直接返回（历史赛题确定性、可预期）；未命中走
    ASCII 兜底：保留字母数字 token、下划线连接（如「2026年全国…(TI杯)」→
    `2026_TI`）；兜底为空（纯中文字符串）→ 回退原短题名（保底可生成，提示
    补词即可），保证函数恒有值且不抛。
    """
    hit = TOPIC_EN_TITLES.get(short_title)
    if hit:
        return hit
    words = [w for w in _ASCII_KEEP_WORDS_RE.split(short_title) if w]
    fallback = "_".join(words)
    return fallback or short_title


def topic_dir_title(key: str, problem_text: str) -> str:
    """历史赛题目录名：`2024H_Auto_Car`（编号 + 英文短名，工单 ascii-project-name/01）。

    修订（2024H 复盘）：有历史赛题编号时目录名不再取 AI 简介首行——简介是
    长句（如“设计一个采用 TI MSPM0 系列 MCU 控制的自动行驶小车…”），目录名
    又长又每次生成都可能变；编号 + 短题名稳定、可预期。2024H 实测中文路径在
    CCS/gmake 链上乱码（工单 mspm0-cjk-path-fix/01 只修模板、管不住 CCS IDE
    重建 makefile），目录名改纯英文：编号 + 英文字典短名（ASCII，Windows
    gmake→cmd.exe 转码无损），彻底绕开编码链路。
    """
    en = topic_en_title(topic_short_title(problem_text))
    return f"{key}_{en}"


def windows_safe_folder_name(title: str) -> str:
    """AI 题名 → Windows 目录名：清非法字符、空白和保留设备名。"""
    name = _INVALID_FILENAME_CHARS_RE.sub("_", title)
    name = _FILENAME_WHITESPACE_RE.sub(" ", name).strip(" ._")
    if not name:
        name = "赛题工程"
    name = name[:80].rstrip(" .") or "赛题工程"
    if _is_windows_reserved_filename(name):
        name = f"{name}_"
    return name


def unique_desktop_topic_dir(desktop_dir: Path, title: str) -> Path:
    """桌面根 + 题名 → 唯一输出目录；重名追加时间，再冲突追加序号。

    [DEPRECATED]（工单 generate-conflict-guard/01）：webapp 已改用
    desktop_topic_dir_verdict——旧行为静默换名，多标签页连点会攒出一圈带
    时间戳的半成品目录。保留纯为兼容外部调用方（测试 / 脚本），不再被
    生成路由使用。
    """
    base = windows_safe_folder_name(title)
    candidate = desktop_dir / base
    if not candidate.exists():
        return candidate

    stamp_base = base.rstrip("_") or base
    stamped = f"{stamp_base}_{time.strftime('%Y%m%d-%H%M%S')}"
    candidate = desktop_dir / stamped
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = desktop_dir / f"{stamped}_{index}"
        if not candidate.exists():
            return candidate
        index += 1


class GenerationConflictError(Exception):
    """桌面同名工程已存在（工单 generate-conflict-guard/01）。

    与生成中途撞车的 OutputDirNotEmptyError 语义不同：这是「用户已经有一个
    同名完整工程」的正常业务拒绝——不静默换名攒目录（旧 unique_desktop_topic_dir
    行为），400 中文提示用户删除或改题名，绝不自动覆盖。
    """


class GenerationBusyError(Exception):
    """同名工程正在生成中（工单 generate-conflict-guard/01）。

    多标签页 / 并发请求同题并发生成：第二个请求拿 409 中文「正在生成中」，
    不浪费一次完整生成流程（也避免两个流程同时写同一目录交错留残渣）。
    """


def desktop_topic_dir_verdict(
    desktop_dir: Path, title: str
) -> tuple[Path, str]:
    """桌面同题目录裁决（工单 generate-conflict-guard/01）。

    返回 (候选目录, verdict)：候选目录 = 桌面根 + windows_safe 题名（不再
    追加时间戳，目录名稳定可预期）；verdict 三选一：

    - "new"    目录不存在，可直接生成；
    - "clean"  目录存在但既无 .contest_context.json 也无 main.c（空目录 /
               上次生成失败的半成品残渣），调用方清理后生成；
    - "exists" 目录存在且含完整工程标记（.contest_context.json 或 main.c），
               调用方 400 拒绝（不静默覆盖 / 改名）。

    完整工程判定取 .contest_context.json（新生成必有）或 main.c（老工程 /
    手工工程）：两者皆无 = 不可能是有用户价值的工程，按残渣清理。
    """
    candidate = desktop_dir / windows_safe_folder_name(title)
    if not candidate.exists():
        return candidate, "new"
    if (
        (candidate / CONTEXT_MANIFEST_FILENAME).exists()
        or (candidate / "main.c").exists()
    ):
        return candidate, "exists"
    return candidate, "clean"


def with_platform_suffix(title: str, platform: str) -> str:
    """目录标题 → 带平台后缀（工单 desktop-platform-suffix/01）。

    同一赛题在两个平台各生成各的目录：标题追加平台标记
    （Auto_Car_STM32 / Auto_Car_MSPM0），换平台同题不再撞「同名完整工程」
    护栏，同平台同题仍同名（护栏语义不变）。后缀映射单源在 platforms.py
    （PLATFORM_DIR_SUFFIXES，照 PLATFORM_CONFIG_FILE_SUFFIXES 先例）。

    未知平台大声失败（ValueError → 未登记 500）：映射缺 key 时静默返回
    无后缀目录会让新旧平台目录重新撞名——漂移暴露优于静默。
    """
    suffix = PLATFORM_DIR_SUFFIXES.get(platform)
    if suffix is None:
        raise ValueError(f"未知平台：{platform}")
    return f"{title}{suffix}"


def backup_project_dir(output_dir: Path) -> Path:
    """覆盖前快照（工单 generate-overwrite/01）：旧工程目录整体改名为
    `<name>.bak`（同目录、原子、零复制），返回备份路径。

    单份策略：目标 .bak 已存在（目录或文件皆处理）→ 先移除再改名——桌面
    不留多代 .bak 堆积。rename 失败（如 Keil 正打开工程文件占用 → WinError
    32）OSError 上抛，经 errors.py 映射 400「文件操作失败」——此时旧工程
    仍在原名目录未被破坏，用户关闭占用程序后重试即可，绝不遗留半状态。
    """
    backup = output_dir.with_name(output_dir.name + ".bak")
    if backup.exists() or backup.is_symlink():
        if backup.is_dir() and not backup.is_symlink():
            shutil.rmtree(backup)
        else:
            backup.unlink()
    output_dir.rename(backup)
    return backup


def _is_windows_reserved_filename(name: str) -> bool:
    """Windows 保留设备名含扩展名形态同样非法：CON 与 CON.txt 都要避开。"""
    stem = name.rstrip(" .").split(".", 1)[0].upper()
    return stem in WINDOWS_RESERVED_FILENAMES
