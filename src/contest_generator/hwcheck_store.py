"""硬件检测工程的**落点与回读**（工单 module-hwcheck/02）——盘侧，与纯函数域层分开。

`hwcheck.py` 的边界是纯函数（字符串进 / 字符串出、不碰盘）；本模块是它的对偶：
**只做磁盘上"检测工程在哪儿、有哪些、那个目录还是不是检测工程"**，不渲染一行 C。

三件事：

* **命名与落点**（`hwcheck_output_name` / `resolve_hwcheck_output_dir`）：每次检测
  一个新子目录 `hwcheck-<平台>-<YYYYMMDD-HHMMSS>`，**天然不覆盖**——同秒连点两次
  就顺延一秒（宁可变名字，也不覆盖别人刚生成的工程）。
* **扫最近几次**（`list_hwcheck_projects`）：直接看父目录的磁盘实况，不是另一份
  记账（"最近工程记录"那份是赛题工作流的，检测工程不进去，见工单 02 决策）。
* **回读一次检测**（`read_hwcheck_project`）：给目录 → 平台 + 通道开关 + 选中的
  器件。判据 = 工程根 `.contest_context.json` 的 `kind == "hwcheck"`——赛题工程
  （kind 缺省 = contest）**不许**被当成检测工程读回来（这是 `kind` 字段存在的意义）。

父目录不存在 = 大声报错（用户把路径打错时不许静默建树）；父目录为空 / 还没建 =
空列表（"一次都没检测过"是正常状态，不是错误）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .context_manifest import (
    CONTEXT_KIND_HWCHECK,
    read_context_fields,
)
from .hwcheck import HwCheckConfig, HwCheckError
from .platforms import KNOWN_PLATFORMS

__all__ = [
    "DEFAULT_RECENT_LIMIT",
    "HWCHECK_DIR_PREFIX",
    "HwcheckProjectRef",
    "hwcheck_output_name",
    "list_hwcheck_projects",
    "parse_hwcheck_dir_name",
    "read_hwcheck_project",
    "resolve_hwcheck_output_dir",
]

# 子目录前缀（生成侧与扫描侧共用同一常量：改名只改这一处）
HWCHECK_DIR_PREFIX = "hwcheck"

# 目录名文法：hwcheck-<平台>-<YYYYMMDD>-<HHMMSS>（平台 = 词表内 slug）
_NAME_RE = re.compile(
    rf"^{HWCHECK_DIR_PREFIX}-(?P<platform>[a-z0-9_]+)-(?P<date>\d{{8}})-(?P<time>\d{{6}})$"
)

# 同秒撞车时的顺延上限（每次 +1 秒）：够大到不必担心，又不会真的转出一分钟
_MAX_BUMP_SECONDS = 120

# 扫最近几次的默认上限（检测页只展示最近几次，不做历史管理）
DEFAULT_RECENT_LIMIT = 10
_MAX_RECENT_LIMIT = 50


@dataclass(frozen=True)
class HwcheckProjectRef:
    """扫出来的一个检测工程（列表展示用；读内容走 read_hwcheck_project）。"""

    name: str
    dir: Path
    platform: str
    created_at: str  # 本地时间 "YYYY-MM-DD HH:MM:SS"（由目录名解出，不读文件 mtime）


def hwcheck_output_name(platform: str, moment: datetime) -> str:
    """检测工程子目录名（平台词表外大声失败——不许拼出 `hwcheck-nope-…`）。"""
    if platform not in KNOWN_PLATFORMS:
        known = "、".join(sorted(KNOWN_PLATFORMS))
        raise HwCheckError(f"未知平台 {platform!r}，已注册的平台：{known}")
    return f"{HWCHECK_DIR_PREFIX}-{platform}-{moment.strftime('%Y%m%d-%H%M%S')}"


def parse_hwcheck_dir_name(name: str) -> tuple[str, str] | None:
    """目录名 → （平台, "YYYY-MM-DD HH:MM:SS"）；不是本形态 = None。

    只认得出自己人：赛题工程目录（`2024H_Auto_Car_STM32`）、前缀像但平台瞎写
    （`hwcheck-nope-…`）、日期时间非法（`20261340`）一律 None——扫出来的列表
    因此不会混进别人的目录，也不会因为一个畸形目录名把整页带崩。
    """
    match = _NAME_RE.match(name or "")
    if match is None:
        return None
    platform = match.group("platform")
    if platform not in KNOWN_PLATFORMS:
        return None
    try:
        moment = datetime.strptime(
            match.group("date") + match.group("time"), "%Y%m%d%H%M%S"
        )
    except ValueError:
        return None  # 20261340 这类"格式对但日期不存在"
    return platform, moment.strftime("%Y-%m-%d %H:%M:%S")


def resolve_hwcheck_output_dir(
    parent: Path, platform: str, *, now: datetime | None = None
) -> Path:
    """在父目录下选一个**还不存在**的新子目录（选定阶段不落盘）。

    缺失的父目录 = HwCheckError：用户把输出位置打错时，静默替他建出一整棵树
    比报错更坏（他会以为工程生成到别处了）。同秒连点两次 → 顺延一秒，
    绝不复用已存在的目录（票面硬要求"不覆盖"）。
    """
    if not parent.is_dir():
        raise HwCheckError(
            f"输出父目录不存在：{parent} —— 请先建好它，或在检测页点「选择文件夹」换一个"
        )
    moment = now or datetime.now()
    for _ in range(_MAX_BUMP_SECONDS):
        candidate = parent / hwcheck_output_name(platform, moment)
        if not candidate.exists():
            return candidate
        moment += timedelta(seconds=1)
    raise HwCheckError(
        f"输出父目录 {parent} 下这一分钟内已经堆了太多检测工程，换个父目录再试"
    )


def list_hwcheck_projects(
    parent: Path, *, limit: int = DEFAULT_RECENT_LIMIT
) -> tuple[HwcheckProjectRef, ...]:
    """父目录里的检测工程，新 → 旧（父目录不在 = 空列表，不是错误）。

    排序按**目录名里的时间戳**（不读 mtime）：名字就是这次检测的身份，机器搬来
    搬去、备份还原都不会把顺序弄乱；同秒并列时按名字兜底保证确定性。
    `limit` 会被夹到 1..`_MAX_RECENT_LIMIT`（页面只展示最近几次，不做历史管理；
    0 / 负数没有"列全部"的语义，按 1 处理）。
    """
    if not parent.is_dir():
        return ()
    refs: list[HwcheckProjectRef] = []
    for entry in parent.iterdir():
        if not entry.is_dir():
            continue  # 同名文件不是工程（生成内核只建目录）
        parsed = parse_hwcheck_dir_name(entry.name)
        if parsed is None:
            continue
        platform, created_at = parsed
        refs.append(
            HwcheckProjectRef(
                name=entry.name, dir=entry, platform=platform, created_at=created_at
            )
        )
    refs.sort(key=lambda ref: (ref.created_at, ref.name), reverse=True)
    cap = max(1, min(int(limit), _MAX_RECENT_LIMIT))
    return tuple(refs[:cap])


def read_hwcheck_project(output_dir: Path) -> HwCheckConfig:
    """把一个已有目录读回检测配置（平台 + 两个通道开关 + 选中的器件）。

    判据 = 上下文清单的 `kind`，且**走 context_manifest.read_context_fields**
    （不自己解析 JSON）：`kind` 的解释（缺字段 / 未知值 = 赛题工程）与平台 /
    slugs / devices 的缺省补空只有那一个出口——本模块再解释一遍就是第二个判据
    来源，两边迟早漂（读侧归一 vs 自己 get 的语义还不一样）。不是 `hwcheck` →
    HwCheckError（赛题工程 / 旧清单都读不出来，这正是 `kind` 存在的意义）。

    通道开关从**实际进工程的模块集**反推（slugs 里 `debug_uart` / `oled` 在不在）
    ——比另存一份通道快照更可靠：用户手改过工程也读得对。器件选择**不反推**
    （slugs 里分不出"用户选的器件"与"它的依赖"），读清单的 `devices` 字段
    （工单 03 写侧落的）；旧清单缺字段 = 没选器件（向后兼容）。
    """
    fields = read_context_fields(output_dir)
    if fields is None:
        raise HwCheckError(
            f"这个目录不是检测工程（里面没有上下文清单 .contest_context.json）：{output_dir}"
        )
    if fields["kind"] != CONTEXT_KIND_HWCHECK:
        raise HwCheckError(
            f"这个目录不是检测工程（清单里 kind={fields['kind']!r}）：{output_dir}"
        )
    platform = fields["platform"]
    if platform not in KNOWN_PLATFORMS:
        raise HwCheckError(
            f"检测工程的清单里平台无法识别（{platform!r}）：{output_dir}"
        )
    return HwCheckConfig(
        platform=platform,
        debug_uart="debug_uart" in fields["slugs"],
        oled="oled" in fields["slugs"],
        devices=tuple(fields["devices"]),
    )
