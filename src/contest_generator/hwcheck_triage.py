"""硬件检测：**现象回填 + AI 排障**（工单 module-hwcheck/08）——域层纯逻辑 + 记录落盘。

本模块是本功能里 **LLM 的唯一入口**的两侧：

* **进去的东西**（`TriageContext` / `triage_context_text`）：接触线表与引脚绑定、
  这一趟的检测计划（专精小节 + 通用降级件）、上板清单与**勾选状态**、学生填的现象。
  上下文与白名单**同一处装配**——判据（"这句话能不能说"）与材料（"模型看到什么"）
  分成两个来源，迟早漂（`wiring.py` 那条"引用白名单 = 材料本身"的先例）。
* **出来的东西**（`parse_triage_advice`）：机械形状 + **事实约束查表**。板上的
  引脚名与库内模块名是**可查表**的两类话题词，模型说了不在本次上下文里的那种
  （例：只选了 led 却让你去查 `ml_mpu6050`、或点出一个本次接线表里没有的 `PA9`），
  当场拒收（`HwCheckError` → LLM 层转 `LLMError` 重问 → 仍不行由端点降级）。
  中文自由文本不做查表（编不出可核查的假名——真出现了也无从判决，宁放过不误杀）。

**检测没过是正常结果**，所以建议里必须有出口：`issue_hint` 给"必要时反馈成一张
修复单"的说法；兜底文案（`fallback_advice`）也照这个口径写——模型不可用时
**不阻断**：记录照常落盘，页面拿兜底建议并提示可重试。

记录落盘（`HwCheckRecord`，工程根 `.contest_hwcheck_record.json`）：现象 + 勾选
+ 建议三者随**这一次检测**走，刷新后由 `/api/hwcheck/project` 回显。文件坏 /
版本非法 → `HwCheckError`（400 中文点名该删哪个文件）；**建议**那一块坏值只丢
它自己（旧版本 / 手改兼容），现象与勾选照常读回——回显不该因为一段建议而全丢。
"""

from __future__ import annotations

import itertools
import json
import os
import re
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .hwcheck_custom import PROBE_MODULE_SLUG
from .hwcheck_errors import HwCheckError
from .my_devices import DEVICE_ID_PREFIX

__all__ = [
    "ADVICE_VERDICTS",
    "DEFAULT_ISSUE_HINT",
    "FALLBACK_REASON_PREFIX",
    "HWCHECK_RECORD_FILENAME",
    "HWCHECK_RECORD_VERSION",
    "HwCheckRecord",
    "TriageAdvice",
    "TriageContext",
    "TriageFacts",
    "TriageFactError",
    "VERDICT_LABELS",
    "build_triage_context",
    "build_triage_facts",
    "check_advice_facts",
    "empty_record",
    "fallback_advice",
    "parse_triage_advice",
    "read_hwcheck_record",
    "record_with_advice",
    "record_with_checked",
    "record_with_symptom",
    "record_with_triage",
    "triage_context_text",
    "update_hwcheck_record",
    "write_hwcheck_record",
]

# 检测记录文件名（写侧单源：端点 / 前端 / 测试共用一处）
HWCHECK_RECORD_FILENAME = ".contest_hwcheck_record.json"

# 记录版本（向后兼容读：未知版本按已知字段读，缺省补默认）
HWCHECK_RECORD_VERSION = 1

# 唯一临时名的**进程内**单调计数（跨进程靠 pid 区分；同进程两个写者靠它区分）
_TMP_COUNTER = itertools.count(1)

# 定性词表（单源）：模型必须先判"这更像哪一类问题"，页面按它上标签。
# unknown = 证据不足（允许——比硬凑一个分类诚实）。
ADVICE_VERDICTS: tuple[str, ...] = ("wiring", "device", "code", "unknown")

# 定性 → 页面标签（文案单源在域层：端点 / 前端 / 测试引用同一份）
VERDICT_LABELS: dict[str, str] = {
    "wiring": "更像接线问题",
    "device": "更像器件本身的问题",
    "code": "更像程序 / 库内驱动的问题",
    "unknown": "证据还不够，先按下面的线索查",
}

# 兜底文案的开头（判据：页面据此认出"这是降级建议"，不假装是模型结论）
FALLBACK_REASON_PREFIX = "AI 排障暂时用不了"

# 引脚名形态（stm32 / mspm0 两平台都是 `P<端口><序号>`：PA0 / PC13 / PB24）。
# 前后不许再跟标识符字符——`PAGE12` 这种偶然串不算引脚名。
_PIN_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])P[A-Z]\d{1,2}(?![A-Za-z0-9_])")
# 词形 token（小写开头，可含数字 / 下划线）——**只在库内 slug 词表里找命中者**
# 时才成立判据：`jy61p`（无下划线）与 `ml_mpu6050` 都是模块名形态，靠"有没有
# 下划线"分不出来；而 `main_c` / `i2c_scl` / `keil` 这类技术词查表不命中，
# 自然放过（宁放过不误杀整份建议）。`WHO_AM_I` 这类大写 token 不在 slug 词表里，
# 也不会被误判。
_SLUG_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])[a-z][a-z0-9_]*[a-z0-9](?![A-Za-z0-9_])")

# 自建件 id 形态（`mine_` + C 标识符字符，工单 09）。**不靠 `_SLUG_TOKEN_RE`**：
# 那一支只认小写 token，而 `my_devices.DEVICE_ID_PATTERN` 允许大写
# （`mine_MPU6050` 是合法 id）——用 slug 词形判 id 会让大小写混写的 id
# **两个方向都判不到**（提到没选的也不拒）。这里前缀照文法小写、后半段大小写不挑。
_CUSTOM_ID_RE = re.compile(
    rf"(?<![A-Za-z0-9_]){re.escape(DEVICE_ID_PREFIX)}[A-Za-z0-9_]+(?![A-Za-z0-9_])"
)

# 兜底建议里最多点名几条没勾的清单项（全列会变成一堵墙，学生反而不看）
_FALLBACK_MAX_UNCHECKED = 4

# 反馈出口的默认文案（模型没给 issue_hint 时用它）：票面要求"建议里要给'必要时
# 把问题反馈成一张修复单'的出口，不含糊其辞"——出口是**产品承诺**，不是让模型
# 选项可给可不给（文案单源在这里，兜底建议与模型建议共用一句）。
DEFAULT_ISSUE_HINT = (
    "排查完还是指向库内驱动 / 模块本身（而不是接线），那就反馈成一张修复单："
    "把这个检测工程目录、串口最后几行、以及哪一件没过一起写进去。"
)


class TriageFactError(HwCheckError):
    """**事实约束拒收**（引脚 / 模块不在本次上下文里）——与形状错分开的类型。

    为什么值得单独一个类型：形状错（缺 summary、verdict 词表外）是"模型这次
    没按契约输出"，事实错是"模型说了本次检测里不存在的东西"——后者是**本地域
    判决**（CONTEXT.md「错误映射」：模型输出与库内事实的矛盾 = domain），
    LLM 层据此给它 `kind=ERROR_KIND_DOMAIN` 并**带被拒理由重问一次**
    （`domain_retry`），而不是当成畸形输出走 parse 快重试。异常类型是这条分道
    的唯一判据（拿字符串猜 kind 正是仓库明令避免的）。
    """


# ---------------------------------------------------------------------------
# 数据形状
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TriageAdvice:
    """一次排障建议（LLM 产物或兜底文案）。

    verdict = 定性（`ADVICE_VERDICTS` 词表内）；summary = 一句话判断；
    causes = 可能原因（逐条）；steps = 下一步查什么（逐条）；issue_hint =
    "必要时反馈成修复单"的出口说法（可空串）；degraded = 这条是兜底吗
    （模型不可用时为 True——页面据此显示"可重试"，且不把它当成模型结论）。
    """

    verdict: str = "unknown"
    summary: str = ""
    causes: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()
    issue_hint: str = ""
    degraded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "verdict_label": VERDICT_LABELS.get(self.verdict, VERDICT_LABELS["unknown"]),
            "summary": self.summary,
            "causes": list(self.causes),
            "steps": list(self.steps),
            "issue_hint": self.issue_hint,
            "degraded": self.degraded,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TriageAdvice | None":
        """宽容读回（记录文件里的建议）：形状不对 → None（只丢这一段）。

        判据（与 `to_dict` 对偶）：verdict 词表外 → unknown；summary /
        issue_hint 非字符串 → 空串；causes / steps 逐条取非空字符串，
        全坏 = 空元组。**空建议（summary 空且两条都空）→ None**：那等于没有
        建议，页面按"还没分析过"渲染。
        """
        verdict = raw.get("verdict")
        if verdict not in ADVICE_VERDICTS:
            verdict = "unknown"
        summary = raw.get("summary")
        summary = summary.strip() if isinstance(summary, str) else ""
        causes = _clean_str_tuple(raw.get("causes"))
        steps = _clean_str_tuple(raw.get("steps"))
        issue_hint = raw.get("issue_hint")
        issue_hint = issue_hint.strip() if isinstance(issue_hint, str) else ""
        degraded = bool(raw.get("degraded"))
        if not summary and not causes and not steps:
            return None
        return cls(
            verdict=verdict,
            summary=summary,
            causes=causes,
            steps=steps,
            issue_hint=issue_hint,
            degraded=degraded,
        )


@dataclass(frozen=True)
class TriageFacts:
    """事实约束的白名单（可查表的那几类话题词）。

    pins = 本次接线表与板上共享脚里出现的引脚名（含 3V3 / GND 这类供电脚名）；
    modules = 本次检测涉及的模块 slug（器件 + 依赖 + 框架）；known_modules =
    **整库**模块 slug（判"编造了本次没有的件"用）；customs = 本次选中的
    **自建件** id（`mine_*`——工单 09：库内词表判不到它们，单独一张表，且它
    还要**反向判**在不在本次）；custom_words = 本次自建件**名称里**的 slug 形词
    （工单 09：件名可能正好含库内 slug——"卖家给的 oled 模块"——名称会印进
    上下文材料，模型复述它不该被判成编造）。
    """

    pins: frozenset[str]
    modules: frozenset[str]
    known_modules: frozenset[str]
    customs: frozenset[str] = frozenset()
    custom_words: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TriageContext:
    """一次排障的输入（材料 + 白名单同一处装配）。

    rows = 接线行（`hwcheck_board` 投影的 rows，逐行 {slug, role, pin}）；
    order = 建议顺序（[{slug, description, bring_up}]）；sections = 专精小节载荷
    （slug / label / plan）；unspecialized = 通用降级件（slug / label / plan /
    message）；checklist = 上板清单（{id, expect, check}）；checked_ids = 已勾选的
    清单项 id；symptom = 学生填的现象；facts = 事实约束白名单；
    customs_rows = **自建器件事实**（工单 09：检测页计划载荷那几行，加上排障侧
    派生的 `shared_with_library`——这些是**用户确认的事实**，不是库内验证过的
    驱动结论，材料段与白名单都要带上它们）。
    """

    platform: str
    devices: tuple[str, ...]
    rows: tuple[Mapping[str, Any], ...]
    order: tuple[Mapping[str, Any], ...]
    sections: tuple[Mapping[str, Any], ...]
    unspecialized: tuple[Mapping[str, Any], ...]
    checklist: tuple[Mapping[str, Any], ...]
    checked_ids: tuple[str, ...]
    symptom: str
    facts: TriageFacts
    customs_rows: tuple[Mapping[str, Any], ...] = ()

    @property
    def unchecked_ids(self) -> tuple[str, ...]:
        """还没勾的清单项 id（保序）——兜底建议据此点名。"""
        return tuple(
            str(item.get("id", ""))
            for item in self.checklist
            if str(item.get("id", "")) and str(item.get("id", "")) not in self.checked_ids
        )


@dataclass(frozen=True)
class HwCheckRecord:
    """一次检测的记录：现象 + 勾选 + 建议（工程根旁车文件，刷新回显）。

    generated_at = 首次写下时间戳（后续更新保留：它记的是"这一次检测"，
    不是"最后一次编辑"）；advice = 最近一次排障建议（None = 还没分析过）。
    """

    version: int = HWCHECK_RECORD_VERSION
    generated_at: str = ""
    symptom: str = ""
    checked_ids: tuple[str, ...] = ()
    advice: TriageAdvice | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "symptom": self.symptom,
            "checked_ids": list(self.checked_ids),
            "advice": self.advice.to_dict() if self.advice is not None else None,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "HwCheckRecord":
        """读回侧解释链（文件 → 模型）：顶层坏形状 → HwCheckError；建议宽容丢。

        version 非整数 → 大声失败（那不是本模块能解释的文件）；symptom /
        generated_at 非字符串 → 空串；checked_ids 逐条取非空字符串
        （坏值不误伤整份记录，与 idea_chat 同哲学）；advice 形状坏 → None。
        """
        version = raw.get("version", HWCHECK_RECORD_VERSION)
        if not isinstance(version, int) or isinstance(version, bool):
            raise HwCheckError(f"检测记录 version 非法：{version!r}")
        generated_at = raw.get("generated_at", "")
        if not isinstance(generated_at, str):
            generated_at = ""
        symptom = raw.get("symptom", "")
        if not isinstance(symptom, str):
            symptom = ""
        raw_advice = raw.get("advice")
        advice = (
            TriageAdvice.from_dict(raw_advice)
            if isinstance(raw_advice, Mapping)
            else None
        )
        return cls(
            version=version,
            generated_at=generated_at,
            symptom=symptom,
            checked_ids=_clean_str_tuple(raw.get("checked_ids")),
            advice=advice,
        )


def empty_record() -> HwCheckRecord:
    """空记录（还没填过现象——读回时的兜底形状，不 400）。"""
    return HwCheckRecord()


def _stamped(record: HwCheckRecord) -> HwCheckRecord:
    """首次写时补时间戳（记的是"这一次检测"的开头，后改不动它——单源）。"""
    if record.generated_at:
        return record
    return replace(record, generated_at=_now_stamp())


def record_with_symptom(record: HwCheckRecord, symptom: str) -> HwCheckRecord:
    """填 / 改现象（纯函数）：保留勾选与建议，首次写时补时间戳。"""
    return replace(
        _stamped(record),
        symptom=symptom.strip() if isinstance(symptom, str) else "",
    )


def record_with_checked(
    record: HwCheckRecord, checked_ids: Sequence[str]
) -> HwCheckRecord:
    """更新勾选状态（纯函数）：保序去重，空串丢弃。"""
    return replace(
        _stamped(record),
        checked_ids=_dedup_str(checked_ids),
    )


def record_with_advice(record: HwCheckRecord, advice: TriageAdvice) -> HwCheckRecord:
    """记下这一次的建议（纯函数）：最新覆盖（重试成功后旧兜底建议被换掉）。"""
    return replace(
        _stamped(record),
        advice=advice,
    )


def record_with_triage(
    record: HwCheckRecord,
    *,
    base: HwCheckRecord,
    symptom: str,
    checked_ids: Sequence[str],
    advice: TriageAdvice,
) -> HwCheckRecord:
    """排障那一笔的**按字段合并**（纯函数；工单 hwcheck-hygiene/03）。

    三个字段的归属不一样，所以合并规则也不一样：

    * **现象 / 建议是本笔的**——用户刚提交的那句话与刚算出来的建议，无条件是它；
    * **勾选不是本笔的**（它归清单端点，勾一条写一次）。`base` = 调模型**之前**读到的那份：
      临界区里重读到的 `record` 与它相同 = 这几秒里没人动过 → 我们手上那份勾选还是最新的，
      照写；**不同 = 清单端点刚写过**（比我们这份新）→ 跳过勾选，旧快照不许盖掉别人的新值。

    这正是"丢更新"最真实的形态：LLM 那几秒正是学生继续勾清单的时候。
    """
    merged = record_with_symptom(record, symptom)
    merged = record_with_advice(merged, advice)
    if record == base:
        merged = record_with_checked(merged, checked_ids)
    return merged


# ---------------------------------------------------------------------------
# 读-改-写的**短临界区**（工单 hwcheck-hygiene/03）
#
# 两处入口（清单勾选 / 排障回填）都走"读 → 合并 → 写"，中间没有锁时后写的那笔
# 会把先写的那笔盖掉。形状上刻意**不照** `webapp._generation_guard`（那是"每键互斥 +
# 冲突 409"）：记录写是"勾一条写一次"的高频轻动作，409 会让学生在生成期间连勾选都存不了。
# 一把**按记录路径**的进程内锁（锁只护"重读到落盘"这几毫秒，LLM 那条路径的调用留在锁外）。
# ---------------------------------------------------------------------------

_RECORD_LOCKS: dict[str, threading.Lock] = {}
_RECORD_LOCKS_GUARD = threading.Lock()
# 记账：这张表**只增不减**（每个见过的记录路径一把锁）。本地工具一次会话见过的检测工程
# 数量有限（几十到几百），每把锁几十字节；不值得为它引弱引用——弱引用会把"锁还被某个写者
# 持有时被回收、下一个写者拿到另一把锁"变成真竞态（比这点常驻内存坏得多）。


def _record_lock(path: Path) -> threading.Lock:
    """取这条记录路径对应的锁（同一路径恒同一把；首用才建）。

    键按 `normcase(abspath(...))` 归一：Windows 上盘符大小写 / 正反斜杠的两种写法指的是
    同一个文件，用原样字符串当键会给它们各发一把锁 = 等于没锁。
    """
    key = os.path.normcase(os.path.abspath(path))
    with _RECORD_LOCKS_GUARD:
        lock = _RECORD_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _RECORD_LOCKS[key] = lock
        return lock


def update_hwcheck_record(
    output_dir: Path, merge: Callable[[HwCheckRecord], HwCheckRecord]
) -> HwCheckRecord:
    """读-改-写整段进**短临界区**：重读 → 合并 → 写；返回落盘后的记录。

    `merge` 是纯函数（`record_with_*` 那一族），**只碰自己那几个字段**——这就是
    "不丢更新"的形状：临界区里那份是**重读**的，别人在临界区外改过的字段原样带过去。

    **跨 LLM 时延的路径必须把调用留在临界区之外**（排障端点：先算建议，再拿
    `record_with_triage` 进来合并）——否则学生填一次现象，锁要按住一整次模型调用，
    期间勾选全在门外排队。
    """
    path = output_dir / HWCHECK_RECORD_FILENAME
    with _record_lock(path):
        record = merge(read_hwcheck_record(output_dir))
        write_hwcheck_record(output_dir, record)
        return record


# ---------------------------------------------------------------------------
# 上下文装配（材料 + 白名单同一处）
# ---------------------------------------------------------------------------


def build_triage_facts(
    *,
    rows: Sequence[Mapping[str, Any]],
    board_shares: Sequence[Mapping[str, Any]],
    modules: Sequence[str],
    known_modules: Sequence[str],
    material_texts: Sequence[str] = (),
    customs: Sequence[str] = (),
    custom_words: Sequence[str] = (),
) -> TriageFacts:
    """白名单装配（纯函数）：引脚名来自**本次接线行 + 板上共享脚 + 材料里出现过的
    脚**，模块名来自本次检测的模块集与整库词表，自建件 id 与"件名里的词"各一张
    表（工单 09）。

    引脚判据取"接线表里出现的脚"而不是"板定义全部脚"：模型点出一个本次
    材料里根本没有的脚（`PA9`），那正是"编造接线"——放行它比拒收坏处大。

    `material_texts` = 模型**看得到的那些字**（上板清单的「应看到 / 不对先查」、
    逐件检测计划、现象本身）——评审抓到的真缺陷：上板清单里就写着「stm32 板载
    三色 LED 在 PC13/PC14/PC15」「地猛星用户 LED 是 PA15」（`hwcheck.render_checklist`），
    模型复述材料里的 `PC13` 反被白名单判非法 → 重问 → 兜底降级。判据与材料必须
    同一处装配：**材料里出现过的脚就是上下文事实**，允许引用。
    """
    pins: set[str] = set()
    for row in rows:
        pin = row.get("pin")
        if isinstance(pin, str) and pin:
            pins.add(pin)
    for item in board_shares:
        pin = item.get("pin")
        if isinstance(pin, str) and pin:
            pins.add(pin)
    for text in material_texts:
        if isinstance(text, str) and text:
            pins.update(_PIN_TOKEN_RE.findall(text))
    return TriageFacts(
        pins=frozenset(pins),
        modules=frozenset(str(slug) for slug in modules if slug),
        known_modules=frozenset(str(slug) for slug in known_modules if slug),
        customs=frozenset(str(slug) for slug in customs if slug),
        custom_words=frozenset(str(word) for word in custom_words if word),
    )


def build_triage_context(
    *,
    platform: str,
    devices: Sequence[str],
    modules: Sequence[str],
    wiring: Mapping[str, Any],
    sections: Sequence[Mapping[str, Any]],
    unspecialized: Sequence[Mapping[str, Any]],
    checklist: Sequence[Mapping[str, Any]],
    checked_ids: Sequence[str],
    symptom: str,
    known_modules: Sequence[str],
    customs: Sequence[Mapping[str, Any]] = (),
) -> TriageContext:
    """一次排障的上下文（纯函数）。

    `wiring` = `hwcheck_board` 投影的板侧视图 dict（rows / order / board_shares…）；
    `modules` = **实际进工程的模块集**（`hwcheck_modules(config)`：框架 + 通道 +
    器件），接线行 / 小节 / 通用件 / 选中器件也一并归并进来——框架件 `delay`
    没有引脚、`config` 也不在接线表里，只靠接线行归并的话，模型提一句 `delay`
    就会被事实判据误杀。现象为空 → `HwCheckError`（没现象可分析；路由层另有
    `_require_str` 的 400）。

    `customs`（工单 09）= 检测页计划载荷里自建件的那几行（`view.board["custom"]`）。
    每行补一个排障侧派生的 `shared_with_library`（这件借的总线上还有没有库内件
    ——判据 = 支点 `i2c_probe` 的脚是否被别的模块也占着）：共总线时"先查同一条
    总线上的库内件"才是有效线索，单挂时那句话反而是误导。
    """
    text = symptom.strip() if isinstance(symptom, str) else ""
    if not text:
        raise HwCheckError("请先把板上的实际现象填上（哪一件、哪个通道、看到什么），再来让 AI 分析")
    rows = tuple(dict(row) for row in wiring.get("rows", ()) or ())
    order = tuple(dict(item) for item in wiring.get("order", ()) or ())
    checklist_rows = tuple(dict(item) for item in checklist)
    section_rows = tuple(dict(item) for item in sections)
    generic_rows = tuple(dict(item) for item in unspecialized)
    customs_rows = tuple(dict(row) for row in customs)
    probe_pins = {
        row.get("pin") for row in rows if row.get("slug") == PROBE_MODULE_SLUG
    }
    for row in customs_rows:
        row["shared_with_library"] = any(
            row2.get("pin") in probe_pins
            and row2.get("slug") not in (PROBE_MODULE_SLUG, row.get("slug"))
            and not str(row2.get("slug", "")).startswith(DEVICE_ID_PREFIX)
            for row2 in rows
        )
    modules_in_play: list[str] = []
    for candidates in (
        list(modules),
        [row.get("slug") for row in rows],
        [item.get("slug") for item in order],
        [item.get("slug") for item in section_rows],
        [item.get("slug") for item in generic_rows],
        list(devices),
    ):
        for slug in candidates:
            if isinstance(slug, str) and slug and slug not in modules_in_play:
                modules_in_play.append(slug)
    return TriageContext(
        platform=platform,
        devices=tuple(str(slug) for slug in devices),
        rows=rows,
        order=order,
        sections=section_rows,
        unspecialized=generic_rows,
        checklist=checklist_rows,
        checked_ids=_dedup_str(checked_ids),
        symptom=text,
        facts=build_triage_facts(
            rows=rows,
            board_shares=wiring.get("board_shares", ()) or (),
            modules=modules_in_play,
            known_modules=known_modules,
            # 材料里出现过的脚也算上下文事实（清单的「不对先查」里就写着
            # PC13/PC14/PC15 这类板载 LED 脚——模型复述它不该被判非法）
            material_texts=_material_texts(
                checklist_rows, section_rows, generic_rows, order,
                customs_rows, text,
            ),
            # 自建件 id 与"件名里的词"各一张表（工单 09）：库内词表判不到 mine_*，
            # 件名又可能正好含库内 slug（"卖家给的 oled 模块"），两张表各管一条判据
            customs=[row.get("slug") for row in customs_rows],
            custom_words=[
                token
                for row in customs_rows
                for token in _SLUG_TOKEN_RE.findall(str(row.get("name", "")))
            ],
        ),
        customs_rows=customs_rows,
    )


def _material_texts(
    checklist: Sequence[Mapping[str, Any]],
    sections: Sequence[Mapping[str, Any]],
    unspecialized: Sequence[Mapping[str, Any]],
    order: Sequence[Mapping[str, Any]],
    customs: Sequence[Mapping[str, Any]],
    symptom: str,
) -> tuple[str, ...]:
    """模型看得到的那些自由文本（引脚白名单的补充来源，见 build_triage_facts）。

    只收**会印进 `triage_context_text` 的字段**：清单的 expect / check、小节的
    plan、通用件计划、顺序里的 description、自建件的 plan / 备注（工单 09）、
    以及学生填的现象——收多了会放行模型没见过的脚，收少了就是评审抓到的那条
    "材料说得的、判据说不得"。
    """
    chunks: list[str] = [symptom]
    for item in checklist:
        chunks.append(str(item.get("expect", "")))
        chunks.append(str(item.get("check", "")))
    for item in sections:
        chunks.append(str(item.get("plan", "")))
    for item in unspecialized:
        chunks.append(str(item.get("plan", "")))
        chunks.append(str(item.get("message", "")))
    for item in order:
        chunks.append(str(item.get("description", "")))
    for item in customs:
        chunks.append(str(item.get("plan", "")))
        chunks.append(str(item.get("notes", "")))
    return tuple(chunk for chunk in chunks if chunk)


def triage_context_text(context: TriageContext) -> str:
    """上下文 → 模型看到的材料（纯函数；材料与白名单同一处装配）。

    逐段：平台与器件 → 接线表（模块 / 端子 / 板脚）→ 这一趟的检测计划 →
    **自建器件事实**（工单 09）→ 上板清单与勾选状态 → 学生填的现象。空段整段
    不印（不印"（空）"那种噪声：模型读到空标题会以为漏了数据）。
    """
    lines: list[str] = [f"平台：{context.platform}"]
    if context.devices:
        lines.append("本次要测的器件：" + "、".join(context.devices))
    else:
        lines.append("本次一件器件都没选（只验「板子活着」与烧录链路）")

    if context.rows:
        lines.append("")
        lines.append("【接线表】（模块 / 端子 → 板上的脚）")
        for row in context.rows:
            role = str(row.get("role", "")) or str(row.get("role_id", ""))
            lines.append(f"- {row.get('slug', '')} 的 {role} → {row.get('pin', '')}")

    if context.order:
        lines.append("")
        lines.append("【建议检测顺序】（前一件不通，后一件的现象不可信）")
        lines.append(
            " → ".join(str(item.get("slug", "")) for item in context.order)
        )

    if context.sections or context.unspecialized:
        lines.append("")
        lines.append("【这一趟真测哪几件】")
        for section in context.sections:
            lines.append(f"- [专精] {section.get('slug', '')}：{section.get('plan', '')}")
        for section in context.unspecialized:
            lines.append(
                f"- [未专精] {section.get('slug', '')}：{section.get('plan', '')}"
                "（只验初始化与总线扫描，判不了通断）"
            )

    if context.customs_rows:
        lines.append("")
        lines.append(
            "【自建器件】（学生自己登记的库外件——下面每一项都是**用户确认的事实**，"
            "不是库内验证过的驱动结论）"
        )
        for row in context.customs_rows:
            lines.append(
                f"- [自建件] {row.get('slug', '')}（{row.get('name', '')}）："
                f"{row.get('plan', '')}"
            )
            address = str(row.get("address_text", ""))
            # 非 I2C 件没有地址（`address=None` 是合法状态）：**整行不印**——
            # 印「地址：（8 位写法：读  / 写 ）」就是把一行空事实塞给模型，
            # 与本函数「空段整段不印」同一条纪律（评审抓到的那处）。
            if address:
                lines.append(
                    f"      地址：{address}"
                    f"（8 位写法：读 {row.get('read8', '')} / 写 {row.get('write8', '')}）"
                )
            register = str(row.get("register_text", ""))
            if register:
                expect = str(row.get("expect_text", ""))
                detail = f"      身份寄存器：{register}"
                if expect:
                    detail += f"，期望读回 {expect}"
                elif row.get("echo_only"):
                    detail += "（没填期望值，这一趟只回显读到的字节，不判）"
                lines.append(detail)
            notes = str(row.get("notes", ""))
            if notes:
                lines.append(f"      你填的备注：{notes}")
            lines.append(f"      本次探测形态：{row.get('probe_form', '')}")
            lines.append(
                "      与库内件共总线："
                + ("是" if row.get("shared_with_library") else "否")
            )

    if context.checklist:
        lines.append("")
        lines.append("【上板确认清单】（[x] = 学生已勾选）")
        for item in context.checklist:
            mark = "x" if str(item.get("id", "")) in context.checked_ids else " "
            lines.append(f"- [{mark}] {item.get('expect', '')}")
            check = str(item.get("check", ""))
            if check:
                lines.append(f"      不对先查：{check}")

    lines.append("")
    lines.append("【学生填的实际现象】")
    lines.append(context.symptom)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 建议解析（机械形状 + 事实约束查表）
# ---------------------------------------------------------------------------


def parse_triage_advice(raw: object, context: TriageContext) -> TriageAdvice:
    """模型输出 → 建议（校验不过 → `HwCheckError`，由 LLM 层转重问）。

    形状判据：对象；verdict 在词表内；summary 非空；causes / steps 各至少一条
    非空字符串。事实判据（`check_advice_facts`）：引脚名必须在本次接线表里，
    库内模块名必须在本次检测的模块集里。
    """
    if not isinstance(raw, Mapping):
        raise HwCheckError("排障建议必须是 JSON 对象")
    verdict = raw.get("verdict")
    if verdict not in ADVICE_VERDICTS:
        allowed = " / ".join(ADVICE_VERDICTS)
        raise HwCheckError(f"排障建议 verdict 非法：{verdict!r}（只允许 {allowed}）")
    summary = raw.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise HwCheckError("排障建议缺少 summary：模型没给出判断")
    causes = _clean_str_tuple(raw.get("causes"))
    steps = _clean_str_tuple(raw.get("steps"))
    if not causes:
        raise HwCheckError("排障建议缺少 causes：至少要给一条可能原因")
    if not steps:
        raise HwCheckError("排障建议缺少 steps：至少要说下一步查什么")
    issue_hint = raw.get("issue_hint")
    issue_hint = issue_hint.strip() if isinstance(issue_hint, str) else ""
    advice = TriageAdvice(
        verdict=str(verdict),
        summary=summary.strip(),
        causes=causes,
        steps=steps,
        # 模型没给出口 = 用产品那句默认（票面：出口不能缺）
        issue_hint=issue_hint or DEFAULT_ISSUE_HINT,
    )
    violations = check_advice_facts(advice, context.facts)
    if violations:
        raise TriageFactError(
            "排障建议引用了本次检测上下文里没有的东西——"
            + "；".join(violations)
            + "（只准引用上面接线表与检测计划里出现的引脚名与模块名）"
        )
    return advice


def check_advice_facts(
    advice: TriageAdvice, facts: TriageFacts
) -> tuple[str, ...]:
    """事实约束查表（纯函数）→ 违规说明元组（空 = 通过）。

    三类可查表的话题词：
    * **引脚名**（`P[A-Z]<数字>` 形态）必须在本次接线表 / 板上共享脚里；
    * **库内模块 slug**（在整库 slug 词表里命中的小写 token——`ml_mpu6050` 与
      `jy61p` 都算，**不要求带下划线**）必须在本次模块集里："只选了 led 却让你
      去查 ml_mpu6050"就是这一类；
    * **自建件**（工单 09）：`mine_*` 形态的 id 必须在**本次**的自建件集里
      （不在 = 编造，照拒）；件**名称里**的 slug 形词放行（名称会印进材料，
      而它可能正好撞上库内 slug——"卖家给的 oled 模块"）。
    整库也不认识的名字不判（`main_c` / `i2c_scl` 这类技术词与模块 slug 同形，
    查表无从判决；误杀整份建议的代价比放过一个大）。
    """
    text = "\n".join(
        (advice.summary, *advice.causes, *advice.steps, advice.issue_hint)
    )
    violations: list[str] = []
    for pin in dict.fromkeys(_PIN_TOKEN_RE.findall(text)):
        if pin not in facts.pins:
            violations.append(f"引脚 {pin} 不在本次接线表里")
    # 自建件 id 走**自己那一张表**（工单 09）：库内 slug 词表里没有 `mine_*`，
    # 而 id 的大小写不受 slug 词形约束——专用形态 + 专用表，两个方向都判得动。
    for token in dict.fromkeys(_CUSTOM_ID_RE.findall(text)):
        if token not in facts.customs:
            violations.append(f"自建件 {token} 不在本次检测里")
    for token in dict.fromkeys(_SLUG_TOKEN_RE.findall(text)):
        if token.startswith(DEVICE_ID_PREFIX):
            continue  # 自建件 id 归上面那一遍（大小写无关），不在这张表里重判
        # 件名里的词（工单 09）：名称会印进上下文材料，而它可能正好撞上库内
        # slug（"卖家给的 oled 模块"）——模型复述材料，不该被判成编造。
        if token in facts.custom_words:
            continue
        if token in facts.known_modules and token not in facts.modules:
            violations.append(f"模块 {token} 不在本次检测的模块集里")
    return tuple(violations)


# ---------------------------------------------------------------------------
# 兜底建议（模型不可用时不阻断）
# ---------------------------------------------------------------------------


def fallback_advice(context: TriageContext) -> TriageAdvice:
    """模型不可用时的**确定性**兜底建议（不猜、不说假话）。

    内容全部来自本次上下文：没勾的清单项、本次接线表的头几根线、以及"必要时
    反馈成修复单"的出口。`degraded=True` —— 页面据此显示"可重试"，且不把这段
    文案当成模型结论（与"检测没过是正常结果"同一口径：给下一步，不含糊）。

    **不带模型失败原因**：那句原文由端点放进响应的 `message` 字段（页面单独
    显示）——把"模型引用了 PA9 / jy61p"这类内部拒收理由混进建议正文，学生会
    以为那是给他的线索。
    """
    unchecked_ids = context.unchecked_ids
    causes: list[str] = []
    for item in context.checklist:
        if str(item.get("id", "")) not in unchecked_ids:
            continue
        if len(causes) >= _FALLBACK_MAX_UNCHECKED:
            break
        causes.append(f"还没确认这条：{item.get('expect', '')}")
    if not causes:
        causes.append("清单已经全勾上了——那问题多半不在这几条通用项上")
    if context.rows:
        wires = "；".join(
            f"{row.get('slug', '')} 的 {row.get('role', '')} → {row.get('pin', '')}"
            for row in context.rows[:4]
        )
        wire_step = f"逐根核对接线（先这四根）：{wires}"
    else:
        wire_step = "本趟没有器件接线——先确认烧录链路（探针 / 供电 / 型号）"
    steps = (
        wire_step,
        "按「建议检测顺序」一件一件来：前一件不通，后一件的现象就不可信",
        "把现象写具体一点（哪一件、哪个通道、串口最后一行、灯闪不闪），再点一次「让 AI 分析」",
        "若板上已经报 FAIL / 初始化返回失败，那更像库内驱动的问题——把检测目录、串口最后几行、"
        "哪一件没过一起反馈成一张修复单",
    )
    summary = f"{FALLBACK_REASON_PREFIX}：先按下面的线索自查"
    if len(unchecked_ids) < len(context.checklist):
        summary += f"（清单里还有 {len(unchecked_ids)} 条没确认）"
    return TriageAdvice(
        verdict="unknown",
        summary=summary,
        causes=tuple(causes),
        steps=steps,
        issue_hint=(
            "排查完还是指向驱动 / 库内模块，而不是接线——"
            "把这个检测工程目录和现象一起反馈，我们可以照着开一张修复单"
        ),
        degraded=True,
    )


# ---------------------------------------------------------------------------
# 记录落盘与回读
# ---------------------------------------------------------------------------


def read_hwcheck_record(output_dir: Path) -> HwCheckRecord:
    """读一次检测的记录；无文件 = 空记录（还没填过，不 400）。

    坏 JSON / 非对象 / version 非法 → `HwCheckError` 400 中文（点名该删哪个
    文件）：静默重置会把学生填过的现象与勾选悄悄抹掉，那比报错坏得多。
    """
    path = output_dir / HWCHECK_RECORD_FILENAME
    if not path.is_file():
        return empty_record()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HwCheckError(
            f"检测记录 {HWCHECK_RECORD_FILENAME} 损坏（不是合法 JSON）：{exc} —— "
            "可以把它删掉重填，或修好 JSON 再看"
        ) from exc
    if not isinstance(data, Mapping):
        raise HwCheckError(f"检测记录 {HWCHECK_RECORD_FILENAME} 必须是 JSON 对象")
    return HwCheckRecord.from_dict(data)


def write_hwcheck_record(output_dir: Path, record: HwCheckRecord) -> Path:
    """写记录（原子写：**唯一临时名** → `os.replace`；坏写不落半成品也不留残渣）。

    临时名带 **pid + 进程内单调计数**（工单 hwcheck-hygiene/03，照 `codeview.py` 的
    `f".tmp-{os.getpid()}"` 先例再进一步）：固定名 `.tmp` 在两个写者并发时会互抢——
    一个刚写完、另一个把同一文件截断，`replace` 落盘的可能就是半成品，或者后一个
    `replace` 直接失败（源文件已经不在）。同进程内两个写者也必须不同名，所以加计数。
    """
    path = output_dir / HWCHECK_RECORD_FILENAME
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}")
    try:
        tmp.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    finally:
        # 异常路径不留残渣（`replace` 成功时 tmp 已经不在了；失败时它还在）
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:  # pragma: no cover —— 清不掉也不该把原异常盖掉
                pass
    return path


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------


def _clean_str_tuple(raw: object) -> tuple[str, ...]:
    """任意值 → 非空字符串元组（保序去重；坏条目丢弃，不误伤整份）。"""
    if not isinstance(raw, (list, tuple)):
        return ()
    return _dedup_str(
        item.strip() for item in raw if isinstance(item, str) and item.strip()
    )


def _dedup_str(values: Iterable[object]) -> tuple[str, ...]:
    """保序去重（空串 / 非字符串丢弃）。

    参数按**任意可迭代对象**收：调用方既有 `Sequence[str]` 也有生成器
    （`_clean_str_tuple`），标成 `Sequence[str]` 反而是假的（评审整改：
    原来写 `Sequence[str] | Any`，`Any` 一沾就把类型信息全吞了）。
    """
    out: list[str] = []
    for value in values:
        text = value.strip() if isinstance(value, str) else ""
        if text and text not in out:
            out.append(text)
    return tuple(out)


def _now_stamp() -> str:
    """时间戳（与任务迭代记录同格式）。"""
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
