"""赛题预读域：LLM 输出的结构化预读结果的机械规范化（防幻觉）。

生成页步骤 2「赛题预读：关键信息与提醒」的产物契约唯一出处：一次预读
调用返回 {overview, reminders}——overview = 一句话总览（这个赛题要做一个
什么样的装置 / 系统）；reminders = 决策点提醒列表，每条 {steps, text,
quote}（steps = 影响的后续步骤编号，空列表 = 通用限定，如尺寸 / 电源 /
时长）。

项目铁律（AI 输出不可信）：LLM 输出在这里做机械过滤——steps 洗白（只认
PREREAD_STEPS 枚举；洗白后空 = 通用组）、quote 必须命中题面原文（空白
归一后子串匹配，不命中即丢弃引用但保留提醒）、长度与条数上限。产出
PrereadResult 纯数据，展示层专用，不进任何下游流程。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 步骤语义（编号 → 步骤名）：提示词与前端分组的单源；编号集派生为 PREREAD_STEPS。
# 3 目标平台 / 5 AI 推荐模块 / 6 模块清单 / 7 引脚配置 / 8 main.c 骨架 /
# 11 修订与深化。
PREREAD_STEP_NAMES = {
    3: "目标平台",
    5: "AI 推荐模块",
    6: "模块清单",
    7: "引脚配置",
    8: "main.c 骨架",
    11: "修订与深化",
}

# 预读提醒可锚定的后续步骤（生成页步骤编号；空 = 通用限定）。
PREREAD_STEPS = frozenset(PREREAD_STEP_NAMES)

MAX_REMINDERS = 12
MAX_OVERVIEW_LEN = 120
MAX_REMINDER_TEXT_LEN = 200
MAX_QUOTE_LEN = 120

_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class PrereadReminder:
    """一条决策点提醒：影响步骤 + 提醒文本 + 题面原文引用（可为空）。"""

    steps: tuple[int, ...]  # 影响的后续步骤编号（空元组 = 通用限定）
    text: str
    quote: str = ""


@dataclass(frozen=True)
class PrereadResult:
    """赛题预读产物：一句话总览 + 决策点提醒列表（展示层专用）。"""

    overview: str
    reminders: tuple[PrereadReminder, ...] = ()

    def to_dict(self) -> dict:
        return {
            "overview": self.overview,
            "reminders": [
                {"steps": list(r.steps), "text": r.text, "quote": r.quote}
                for r in self.reminders
            ],
        }


def normalize_whitespace(text: str) -> str:
    """空白归一（去全部空白，含换行 / 全角空格）：引用匹配的规范化形式。

    折行、多余空格、全角空格在归一后全部消失——短引用匹配用"去空白"比
    "压成单空格"更稳：题面原文与模型引用之间少一格 / 多一格都不会误判。
    """
    return _WS_RE.sub("", text)


def quote_in_problem(problem_text: str, quote: str) -> bool:
    """引用是否命中题面：空白归一后子串匹配（模型常折行 / 带多余空格）。"""
    needle = normalize_whitespace(quote)
    if not needle:
        return False
    return needle in normalize_whitespace(problem_text)


def _clean_steps(raw: object) -> tuple[int, ...]:
    """steps 洗白：只认 PREREAD_STEPS 枚举；bool 不算 int；重复合并保序。"""
    if not isinstance(raw, list):
        return ()
    seen: list[int] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if value in PREREAD_STEPS and value not in seen:
            seen.append(value)
    return tuple(seen)


def _clean_text(raw: object) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return ""
    return raw.strip()[:MAX_REMINDER_TEXT_LEN]


def _clean_quote(raw: object, problem_text: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return ""
    quote = raw.strip()[:MAX_QUOTE_LEN]
    return quote if quote_in_problem(problem_text, quote) else ""


def normalize_preread(data: object, problem_text: str) -> PrereadResult:
    """LLM 输出 → 规范化 PrereadResult（机械防幻觉过滤）。

    顶层形状错误（非对象 / overview 缺失或非字符串 / reminders 存在但非
    数组）抛 ValueError（调用方转 LLMError 整次重问）；条目级问题宽松过滤：
    引用不命中题面 → 丢弃引用保留提醒；非法 steps → 洗白（空 = 通用组）；
    text 为空 → 丢弃整条；超长截断；超出条数截尾保留前 N 条。
    """
    if not isinstance(data, dict):
        raise ValueError("预读结果必须是 JSON 对象")
    overview = data.get("overview")
    if not isinstance(overview, str) or not overview.strip():
        raise ValueError("预读结果缺少总览 overview")
    raw_reminders = data.get("reminders", [])
    if raw_reminders in (None, []):
        raw_reminders = []
    if not isinstance(raw_reminders, list):
        raise ValueError("预读结果的 reminders 必须是数组")
    reminders: list[PrereadReminder] = []
    for item in raw_reminders:
        if len(reminders) >= MAX_REMINDERS:
            break
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("text"))
        if not text:
            continue
        reminders.append(
            PrereadReminder(
                steps=_clean_steps(item.get("steps")),
                text=text,
                quote=_clean_quote(item.get("quote"), problem_text),
            )
        )
    return PrereadResult(
        overview=overview.strip()[:MAX_OVERVIEW_LEN],
        reminders=tuple(reminders),
    )
