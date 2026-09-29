# -*- coding: utf-8 -*-
"""硬件检测：现象回填 + AI 排障（工单 module-hwcheck/08）——域层判据。

**为什么这样测**：本模块是硬件检测功能里 **LLM 的唯一入口**的两侧，判据全部
落在"进模型的东西"与"出模型的东西"上，都不必真调模型：

* 进去的（`triage_context_text`）：接线表 / 检测计划 / 清单与勾选 / 现象 ——
  缺哪一段，模型就只能猜（票面：上下文必须含这四样）。
* 出来的（`parse_triage_advice`）：形状 + **事实约束查表** —— 模型点出一个
  本次接线表里没有的引脚、或本次没选的库内模块，当场拒收（"不编造库内没有的
  接口或引脚"这条验收标准的可执行形态）。
* 模型不可用时（`fallback_advice`）：兜底文案**确定性**产出，且点名还没勾的
  清单项——不阻断、不假装是模型结论。
* 记录（`HwCheckRecord`）：现象 + 勾选 + 建议落盘 / 读回，坏值只丢自己那一段。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from contest_generator import atomic_io, hwcheck_triage
from contest_generator.hwcheck_errors import HwCheckError
from contest_generator.hwcheck_triage import (
    ADVICE_VERDICTS,
    DEFAULT_ISSUE_HINT,
    FALLBACK_REASON_PREFIX,
    HWCHECK_RECORD_FILENAME,
    TriageAdvice,
    TriageFactError,
    build_triage_context,
    empty_record,
    fallback_advice,
    parse_triage_advice,
    read_hwcheck_record,
    record_with_advice,
    record_with_checked,
    record_with_symptom,
    record_with_triage,
    triage_context_text,
    update_hwcheck_record,
    write_hwcheck_record,
)
from contest_generator.platforms import PLATFORM_STM32

# 一次真实形态的检测：stm32 + led + ml_mpu6050（含软 I2C 前置），串口在、屏不在
_WIRING = {
    "rows": [
        {"slug": "led", "role": "LED_RED（红灯）", "role_id": "LED_RED", "pin": "PC13"},
        {"slug": "ml_mpu6050", "role": "SCL", "role_id": "SCL", "pin": "PB6"},
        {"slug": "ml_mpu6050", "role": "SDA", "role_id": "SDA", "pin": "PB7"},
    ],
    "board_shares": [
        {"pin": "PA15", "note": "板载用户 LED 共用", "roles": ["LED"]},
    ],
    "order": [
        {"slug": "led", "description": "板载灯", "bring_up": True},
        {"slug": "ml_mpu6050", "description": "六轴姿态", "bring_up": False},
    ],
}

_SECTIONS = [
    {"slug": "led", "label": "LED", "plan": "点亮红灯通道，肉眼确认"},
    {
        "slug": "ml_mpu6050",
        "label": "MPU6050",
        "plan": "读 WHO_AM_I，期望 0x68；再回显六轴",
    },
]

_UNSPECIALIZED = [
    {"slug": "sr04", "label": "超声波", "plan": "初始化 + 总线扫描", "message": "未专精"}
]

_CHECKLIST = [
    {"id": "flash", "expect": "烧录报成功", "check": "探针插好没有"},
    {"id": "heartbeat", "expect": "LED 按节奏闪", "check": "先按一次复位"},
    {"id": "serial", "expect": "串口出现「板子活着」", "check": "TX/RX 交叉接"},
]

_KNOWN_MODULES = (
    "led", "delay", "debug_uart", "oled", "config",
    "ml_mpu6050", "sr04", "jy61p", "servo",
)

# 实际进工程的模块集（框架 + 通道 + 器件；`delay` / `config` 没有接线行，
# 但它们是本次检测的一部分——事实判据必须放行）
_PROJECT_MODULES = ("led", "delay", "debug_uart", "config", "ml_mpu6050", "sr04")


def _context(*, checked=("flash",), symptom="串口一行字都没有，灯也不闪"):
    return build_triage_context(
        platform=PLATFORM_STM32,
        devices=("led", "ml_mpu6050", "sr04"),
        modules=_PROJECT_MODULES,
        wiring=_WIRING,
        sections=_SECTIONS,
        unspecialized=_UNSPECIALIZED,
        checklist=_CHECKLIST,
        checked_ids=checked,
        symptom=symptom,
        known_modules=_KNOWN_MODULES,
    )


def _advice(**overrides) -> dict:
    payload = {
        "verdict": "wiring",
        "summary": "更像接线问题",
        "causes": ["串口 TX/RX 没交叉接"],
        "steps": ["把 PB6 / PB7 上的两根线拔下来重插一次"],
        "issue_hint": "",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# 进去的：上下文材料（接线表 + 检测计划 + 清单与勾选 + 现象）
# ---------------------------------------------------------------------------


def test_context_text_carries_wiring_plan_checklist_checked_and_symptom():
    """四样材料都在：模型只依据这里的事实说话。"""
    text = triage_context_text(_context())
    assert PLATFORM_STM32 in text
    assert "led 的 LED_RED（红灯） → PC13" in text
    assert "ml_mpu6050 的 SCL → PB6" in text
    assert "【接线表】" in text and "【建议检测顺序】" in text
    assert "led → ml_mpu6050" in text
    assert "[专精] ml_mpu6050" in text and "WHO_AM_I" in text
    assert "[未专精] sr04" in text
    assert "- [x] 烧录报成功" in text
    assert "- [ ] LED 按节奏闪" in text
    assert "串口一行字都没有，灯也不闪" in text


def test_context_facts_whitelist_is_built_from_board_and_selection_data():
    """白名单 = 本次接线行 + 板上共享脚 + **选型数据的平台默认脚**；整库词表另存一份。

    工单 hwcheck-hygiene/05：`PC14`/`PC15` 现在来自**数据**（led 在 stm32 上的板载
    三色通道），不再来自"清单文案里写过"。
    """
    context = _context()
    assert context.facts.pins == {"PC13", "PC14", "PC15", "PB6", "PB7", "PA15"}
    assert {"led", "ml_mpu6050", "sr04"} <= context.facts.modules
    assert "delay" in context.facts.modules  # 框架件没有接线行，仍属本次工程
    assert "jy61p" in context.facts.known_modules  # 库内有、本次没选
    assert "jy61p" not in context.facts.modules


def test_context_rejects_empty_symptom():
    """没现象可分析（路由层另有 400；域层也不许拿空串去问模型）。"""
    with pytest.raises(HwCheckError):
        _context(symptom="   ")


def test_pin_from_the_selection_data_is_a_fact_even_if_the_copy_omits_it():
    """**数据里有**的脚就算事实——不再看文案写没写（工单 hwcheck-hygiene/05）。

    旧口径的由来（评审抓到的真缺陷）仍然要挡住：模型复述材料里的 `PC14` 不该被判非法。
    区别在于**依据换了**——现在是"选型数据说 stm32 的板载 LED 有 PC14"，
    而不是"我们那句文案里碰巧写了 PC14"（文案与判据互为因果：改一句话就悄悄改了判据）。
    """
    context = _context()
    assert "PC14" in context.facts.pins, "选型数据里的板载 LED 脚没进白名单"
    advice = parse_triage_advice(_advice(causes=["绿灯那一路（PC14）没接对"]), context)
    assert advice.causes
    # 判据没被放宽成"什么脚都行"：数据里没有、接线表里也没有的脚照旧拒收
    with pytest.raises(TriageFactError):
        parse_triage_advice(_advice(causes=["PA9 上的线松了"]), context)


def test_pin_that_only_appears_in_the_copy_is_not_a_fact():
    """**只在文案里出现过**、不在数据里的脚，不再算上下文事实（工单 05）。

    这条是"文案不再当判据来源"的正面判据：把 `PX9` 写进清单文案，白名单**不该**跟着涨。
    """
    ladder = dict(_CHECKLIST[1])
    ladder["check"] = "② 板载指示灯在 PX9 那一排（文案里写的，数据里没有）"
    context = build_triage_context(
        platform=PLATFORM_STM32,
        devices=("led", "ml_mpu6050", "sr04"),
        modules=_PROJECT_MODULES,
        wiring=_WIRING,
        sections=_SECTIONS,
        unspecialized=_UNSPECIALIZED,
        checklist=(_CHECKLIST[0], ladder, _CHECKLIST[2]),
        checked_ids=("flash",),
        symptom="灯不亮",
        known_modules=_KNOWN_MODULES,
    )
    assert "PX9" not in context.facts.pins, (
        "文案里写过的脚被当成了上下文事实 —— 判据的来源又回到文案上去了"
    )
    with pytest.raises(TriageFactError):
        parse_triage_advice(_advice(causes=["PX9 那一排没插好"]), context)


def test_pin_from_the_detection_plan_is_still_a_fact():
    """**检测计划**里的脚仍算事实（工单 05 只授权把「上板清单文案」移出判据来源）。

    为什么这条必须钉住：计划那几段（逐件小节 plan / 通用件 plan / 顺序说明 / 自建件
    plan 与备注）来自**库内配方与器件数据**，而且原样印进 `triage_context_text` 给模型
    看。第一版整改把它们连同清单一起踢出白名单，模型复述自己看过的计划就会被判非法
    ——正是 `hwcheck-unknown-device/09` 修过的"材料说得的、判据说不得"（双轴评审当场
    证伪：计划里写 `PA2`，`facts.pins` 里没有它）。
    """
    planned = dict(_SECTIONS[1])
    planned["plan"] = "读 WHO_AM_I（I2C：PA2 = SCL / PA3 = SDA）"
    context = build_triage_context(
        platform=PLATFORM_STM32,
        devices=("led", "ml_mpu6050", "sr04"),
        modules=_PROJECT_MODULES,
        wiring=_WIRING,
        sections=(_SECTIONS[0], planned),
        unspecialized=_UNSPECIALIZED,
        checklist=_CHECKLIST,
        checked_ids=("flash",),
        symptom="读不到数据",
        known_modules=_KNOWN_MODULES,
    )
    assert {"PA2", "PA3"} <= context.facts.pins, "计划里的脚被判非法了（材料说得的、判据说不得）"
    advice = parse_triage_advice(_advice(causes=["PA3 那根 SDA 没接好"]), context)
    assert advice.causes


def test_heartbeat_check_has_no_dangling_number_when_the_led_hint_is_missing():
    """取不到板载 LED 数据时，那一条**整条不出现**（不留悬空的「② ③」）。

    spec「实现决策」：取不到时的行为必须明说——印个空位等于既没说、又把序号错位。
    这里直接喂一个数据里没有的平台（`require_known_platform` 挡住真实配置，所以从
    域层辅助函数进）。
    """
    from contest_generator.hwcheck import _heartbeat_check_text

    text = _heartbeat_check_text("没有这块板")
    assert "② ③" not in text and "②③" not in text, f"留了悬空序号：{text}"
    assert "③" not in text, f"只剩两条时不该出现 ③：{text}"
    assert text.startswith("① ") and "② " in text, f"序号没重排：{text}"
    # 有数据的平台照旧三条（灯那一句在里面）
    full = _heartbeat_check_text(PLATFORM_STM32)
    assert "③" in full and "PC13" in full


def test_pin_mentioned_in_the_symptom_is_allowed():
    """学生自己在现象里写的脚也是上下文事实（他说"我把线插到 PB7 了"）。"""
    context = _context(symptom="我把线从 PB7 挪到 PB9 试过，还是不行")
    advice = parse_triage_advice(_advice(steps=["先把 PB9 上的线插回 PB7"]), context)
    assert advice.steps


def test_context_without_devices_still_renders_the_lamp_only_path():
    """一件器件都不选（只验板子活着）也要能出材料——那条路是票面用户故事 4。"""
    context = build_triage_context(
        platform=PLATFORM_STM32,
        devices=(),
        modules=("led", "delay", "debug_uart", "config"),
        wiring={"rows": [], "board_shares": [], "order": []},
        sections=(),
        unspecialized=(),
        checklist=_CHECKLIST,
        checked_ids=(),
        symptom="什么都没看到",
        known_modules=_KNOWN_MODULES,
    )
    text = triage_context_text(context)
    assert "一件器件都没选" in text
    assert "什么都没看到" in text
    # 一件器件不选时，白名单里只剩**板子自己的事实**（工单 hwcheck-hygiene/05：
    # 板载 LED 那几个脚来自选型数据，与学生接没接线无关）——不再是空的。
    assert context.facts.pins == {"PC13", "PC14", "PC15"}, (
        "板载 LED 的脚是板子的事实，不该随「选没选器件」消失"
    )


# ---------------------------------------------------------------------------
# 出来的：形状校验 + 事实约束查表（不编造引脚 / 模块）
# ---------------------------------------------------------------------------


def test_parse_advice_accepts_context_names():
    """上下文里出现过的引脚名与模块名一律放行（led / PC13 / PB6 都是本次的）。"""
    advice = parse_triage_advice(
        _advice(steps=["先看 led 是不是真的在闪（PC13），再量 PB6 / PB7 通不通"]),
        _context(),
    )
    assert advice.verdict == "wiring"
    assert advice.steps[0].startswith("先看 led")
    assert advice.degraded is False


def test_parse_advice_rejects_invented_pin():
    """模型点出一个本次接线表里没有的脚 → 拒收（那就是编造接线）。

    类型是 `TriageFactError`（不是裸 `HwCheckError`）：LLM 层按类型把它译成
    `kind=domain` 并带理由重问一次——形状错与事实错分道，这条是分道的唯一判据。
    """
    with pytest.raises(TriageFactError) as exc_info:
        parse_triage_advice(_advice(causes=["PA9 上的线松了"]), _context())
    message = str(exc_info.value)
    assert "PA9" in message
    assert "接线表" in message
    assert isinstance(exc_info.value, HwCheckError)  # 仍是 400 那族（errors.py 已登记）


def test_parse_advice_rejects_module_that_is_not_in_this_detection():
    """库内有、本次没选的模块不许提（只选了 led + mpu6050，却让人去查 jy61p）。

    `jy61p` 没有下划线——判据不能靠"名字里有没有下划线"认模块（评审整改：
    旧注释说"形如 xxx_yyy"，与实现的 slug 词表命中判据不符）。
    """
    with pytest.raises(TriageFactError) as exc_info:
        parse_triage_advice(
            _advice(steps=["把 jy61p 拔下来单独测"]), _context()
        )
    assert "jy61p" in str(exc_info.value)


def test_shape_errors_stay_plain_hwcheck_errors():
    """形状错**不是**事实错：缺 summary 那类走解析类快重试，不能误判成域拒绝。"""
    with pytest.raises(HwCheckError) as exc_info:
        parse_triage_advice(_advice(summary=" "), _context())
    assert not isinstance(exc_info.value, TriageFactError)


def test_parse_advice_tolerates_technical_words_that_look_like_slugs():
    """`main_c` / `i2c_scl` 这类技术词与模块 slug 同形——查表无从判决，宁放过。"""
    advice = parse_triage_advice(
        _advice(steps=["打开 main_c 看一眼软 i2c_scl 的初始化顺序"]), _context()
    )
    assert advice.steps


@pytest.mark.parametrize(
    "payload",
    [
        "不是对象",
        _advice(verdict="hardware"),  # 词表外
        _advice(summary="   "),  # 没给判断
        _advice(causes=[]),  # 没有可能原因
        _advice(steps=[]),  # 没说下一步
        _advice(causes=["", "  "]),  # 全空条目
    ],
)
def test_parse_advice_rejects_bad_shape(payload):
    with pytest.raises(HwCheckError):
        parse_triage_advice(payload, _context())


def test_parse_advice_keeps_unknown_verdict_in_the_vocabulary():
    """证据不足时如实给 unknown（不硬凑分类）——它是词表内的合法值。"""
    assert "unknown" in ADVICE_VERDICTS
    advice = parse_triage_advice(_advice(verdict="unknown"), _context())
    assert advice.verdict == "unknown"
    assert advice.to_dict()["verdict_label"]


def test_parse_advice_issue_hint_defaults_to_the_repair_ticket_exit():
    """模型没给出口 → 用产品那句默认（票面：出口不能缺，不含糊其辞）。"""
    advice = parse_triage_advice(_advice(issue_hint=None), _context())
    assert advice.issue_hint == DEFAULT_ISSUE_HINT
    assert "修复单" in advice.issue_hint
    # 模型给了就原样用（产品不抢模型的话）
    given = parse_triage_advice(_advice(issue_hint="先把串口线换一根"), _context())
    assert given.issue_hint == "先把串口线换一根"


# ---------------------------------------------------------------------------
# 兜底：模型不可用不阻断
# ---------------------------------------------------------------------------


def test_fallback_advice_is_deterministic_and_names_unchecked_items():
    """兜底文案全部来自本次上下文：没勾的清单项 + 本次接线 + 反馈出口。"""
    context = _context(checked=("flash",))
    advice = fallback_advice(context)
    assert advice.degraded is True
    assert advice is not None
    assert advice.summary.startswith(FALLBACK_REASON_PREFIX)
    assert any("LED 按节奏闪" in cause for cause in advice.causes)
    assert any("串口出现" in cause for cause in advice.causes)
    assert not any("烧录报成功" in cause for cause in advice.causes)  # 已勾的不点名
    assert any("PC13" in step for step in advice.steps)  # 逐根核对来自本次接线表
    assert advice.issue_hint  # 出口不能缺
    assert fallback_advice(context) == advice  # 确定性


def test_fallback_advice_never_leaks_the_internal_failure_reason():
    """兜底建议正文不带模型失败原因（那是 message 的事）。

    真机判例：模型引用了本次没有的 `PA9`，拒收理由里带着这个引脚名——混进
    建议正文，学生会把它当成给自己的线索去查一个本次根本没接的脚。
    """
    advice = fallback_advice(_context())
    text = " ".join((advice.summary, *advice.causes, *advice.steps))
    assert "PA9" not in text and "jy61p" not in text
    assert FALLBACK_REASON_PREFIX in advice.summary


def test_fallback_advice_survives_an_empty_checklist():
    """清单为空（或全勾）时也给得出下一步——不因缺材料而变空壳。"""
    advice = fallback_advice(_context(checked=()))
    assert advice.degraded is True
    assert advice.causes
    assert advice.steps


def test_fallback_advice_with_everything_checked_says_so():
    """清单全勾上还不过 = 问题不在这几条通用项上（不含糊其辞）。"""
    advice = fallback_advice(
        _context(checked=tuple(item["id"] for item in _CHECKLIST))
    )
    assert any("全勾上" in cause for cause in advice.causes)


# ---------------------------------------------------------------------------
# 记录落盘与回读
# ---------------------------------------------------------------------------


def test_record_round_trip_preserves_symptom_checked_and_advice(tmp_path):
    """现象 + 勾选 + 建议一起落盘、一起读回（刷新回显的判据）。"""
    advice = parse_triage_advice(_advice(), _context())
    record = empty_record()
    record = record_with_checked(record, ["flash", "heartbeat"])
    record = record_with_symptom(record, "灯常亮不闪")
    record = record_with_advice(record, advice)
    write_hwcheck_record(tmp_path, record)

    path = tmp_path / HWCHECK_RECORD_FILENAME
    assert path.is_file()
    reloaded = read_hwcheck_record(tmp_path)
    assert reloaded.symptom == "灯常亮不闪"
    assert reloaded.checked_ids == ("flash", "heartbeat")
    assert reloaded.advice == advice
    assert reloaded.generated_at == record.generated_at


def test_record_keeps_first_timestamp_when_edited(tmp_path):
    """时间戳记的是"这一次检测"，不是"最后一次编辑"（后改不动它）。"""
    record = record_with_symptom(empty_record(), "灯不亮")
    stamp = record.generated_at
    assert stamp
    updated = record_with_symptom(record, "换了根线还是不亮")
    assert updated.generated_at == stamp


def test_record_missing_file_is_empty_not_an_error(tmp_path):
    """还没填过现象 = 空记录（正常状态，不 400）。"""
    assert read_hwcheck_record(tmp_path) == empty_record()


def test_record_corrupt_json_fails_loudly_with_the_filename(tmp_path):
    """坏 JSON 大声失败并点名文件——静默重置会抹掉学生填过的东西。"""
    (tmp_path / HWCHECK_RECORD_FILENAME).write_text("{不是 JSON", encoding="utf-8")
    with pytest.raises(HwCheckError) as exc_info:
        read_hwcheck_record(tmp_path)
    assert HWCHECK_RECORD_FILENAME in str(exc_info.value)
    # 坏 JSON 这一支照旧给"可删可修"的引导（工单 hwcheck-hygiene/04 明确保留）：
    # 它是**内容**坏了，删掉重填确实是出路；而"读不出来"那一支不许这么说。
    assert "删掉重填" in str(exc_info.value)


def test_record_read_failure_is_not_reported_as_corruption(tmp_path, monkeypatch):
    """**读不出来**（占用 / 权限 / IO）≠ 记录坏了：说真话，且**不许**让人删记录。

    照旧实现那句话术做就是**删掉自己填过的现象与勾选**——本单要挡的正是这个。
    """
    path = tmp_path / HWCHECK_RECORD_FILENAME
    path.write_text("{}", encoding="utf-8")
    real_read_text = Path.read_text

    def boom(self, *args, **kwargs):
        if self.name == HWCHECK_RECORD_FILENAME:
            raise PermissionError(13, "另一个程序正在使用此文件，进程无法访问。")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)
    with pytest.raises(HwCheckError) as exc_info:
        read_hwcheck_record(tmp_path)
    message = str(exc_info.value)
    assert "读不出来" in message, f"没说是「读不出来」：{message}"
    assert "占用" in message or "权限" in message, f"没给下一步（占用 / 权限）：{message}"
    assert "损坏" not in message, "把「读不出来」说成「损坏」= 又一次把失败伪装成别的东西"
    assert "删掉重填" not in message and "删" not in message, (
        f"读不出来时引导用户删记录 —— 照做就是删掉自己的现象与勾选：{message}"
    )


def test_record_rejects_non_object_and_bad_version(tmp_path):
    path = tmp_path / HWCHECK_RECORD_FILENAME
    path.write_text(json.dumps(["x"]), encoding="utf-8")
    with pytest.raises(HwCheckError):
        read_hwcheck_record(tmp_path)
    path.write_text(json.dumps({"version": "1"}), encoding="utf-8")
    with pytest.raises(HwCheckError):
        read_hwcheck_record(tmp_path)


def test_record_tolerates_bad_advice_and_bad_checked_entries(tmp_path):
    """建议那一段坏值只丢它自己——现象与勾选照常读回（回显不该全丢）。"""
    (tmp_path / HWCHECK_RECORD_FILENAME).write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-09-20T10:00:00+0800",
                "symptom": "屏全黑",
                "checked_ids": ["flash", "", 3, "flash"],
                "advice": {"verdict": "wiring", "summary": "", "causes": "不是数组"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    record = read_hwcheck_record(tmp_path)
    assert record.symptom == "屏全黑"
    assert record.checked_ids == ("flash",)
    assert record.advice is None  # 空建议 = 还没分析过，不装成有一条


def test_record_advice_survives_unknown_extra_fields(tmp_path):
    """手改 / 旧版本多写的字段不影响读回（向后兼容的宽容读）。"""
    (tmp_path / HWCHECK_RECORD_FILENAME).write_text(
        json.dumps(
            {
                "version": 1,
                "symptom": "灯闪但串口没字",
                "checked_ids": ["heartbeat"],
                "advice": {
                    "verdict": "wiring",
                    "summary": "串口线问题",
                    "causes": ["TX/RX 没交叉"],
                    "steps": ["对调 TX 与 RX"],
                    "future_field": {"x": 1},
                },
                "unknown_top": 5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    record = read_hwcheck_record(tmp_path)
    assert isinstance(record.advice, TriageAdvice)
    assert record.advice.causes == ("TX/RX 没交叉",)
    assert record.to_dict()["advice"]["degraded"] is False


def test_record_write_is_atomic_and_leaves_no_tmp(tmp_path):
    """原子写：落盘后不留 .tmp 半成品。

    判据用"目录里除记录文件外一个文件都没有"（工单 hwcheck-hygiene/03 起临时名带
    pid + 计数，`glob("*.tmp")` 那版匹配不到新名字 = 断言空转）。
    """
    write_hwcheck_record(tmp_path, record_with_symptom(empty_record(), "现象"))
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != HWCHECK_RECORD_FILENAME]
    assert leftovers == [], f"落盘后留下了临时文件：{leftovers}"


def test_record_path_is_relative_to_the_project_dir(tmp_path):
    """记录走工程根旁车文件（与赛题工程的 .contest_*.json 同一落点习惯）。"""
    written = write_hwcheck_record(
        tmp_path, record_with_symptom(empty_record(), "现象")
    )
    assert written.parent == Path(tmp_path)
    assert written.name == HWCHECK_RECORD_FILENAME


# ---------------------------------------------------------------------------
# 记录写的正确性形状：唯一临时名 + 原子替换 + 短临界区（工单 hwcheck-hygiene/03）
#
# 收走前的形状（本单要挡的）：固定临时名 `…json.tmp` + 无锁的"读-改-写"。
# 后果两条：① 两个写者抢同一个 `.tmp`（一个刚写完、另一个把同一文件截断，
# `replace` 落盘的可能就是半成品，或后一个的 `replace` 直接失败）；
# ② 两处入口各自读一份旧记录再整份写回 → 后写的那笔把先写的那笔盖掉。
# ---------------------------------------------------------------------------


def test_record_write_failure_leaves_no_tmp_residue(tmp_path):
    """坏写不许留半成品：替换失败时 `.tmp` 必须被清掉（收走前会留在工程根里）。"""
    with pytest.raises(OSError):
        # 目标是个**目录** → 替换必然失败（不管实现用 os.replace 还是 Path.replace）
        (tmp_path / HWCHECK_RECORD_FILENAME).mkdir()
        write_hwcheck_record(tmp_path, record_with_symptom(empty_record(), "现象"))
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != HWCHECK_RECORD_FILENAME]
    assert leftovers == [], f"写失败后留下了临时文件：{leftovers}"


def test_concurrent_record_writes_share_no_tmp_file(tmp_path, monkeypatch):
    """两个写者并发：**不许抢同一个临时名**——收走前抢了，先来的那个 `replace` 会落空。

    确定性做法：把**第一个** `replace` 卡住（此刻它的临时文件还在盘上），让第二个写者
    从头走完一遍；**第二个整条结算完**才放行第一个（`backlog-agent-sweep/01` 加的排序——
    两次真实 `os.replace` 重叠是 Windows 平台行为，会让这条用例在机器忙时假红）。
    · 收走前（固定名 `…json.tmp`）：第二个写者把**同一个**临时文件截断重写成自己的内容并
      替换掉；第一个放行后 `replace` 的源文件已经不在 → 报错（学生看到的就是"勾选存不上"）；
    · 收走后（pid + 计数）：各写各的临时文件，两个都落盘成功，目录里零残留。

    补丁**只打在目标模块看到的 `os` 上**（不是全局 `os.replace`）：本机同时跑着别的
    测试线程时，全局补丁会被"第一发 `replace`"这种跨用例的噪音消费掉（实测过一次偶发）。
    写实现归共享原语之后（工单 record-write-hardening/07），"目标模块"就是 `atomic_io`——
    注入点跟着搬家，**判据一字未动**（照样卡住第一发真实 `replace`）。
    """
    first_inside = threading.Event()
    release = threading.Event()
    calls = {"n": 0}
    real_replace = os.replace

    def slow_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            first_inside.set()
            assert release.wait(timeout=30), "等不到放行——判据自己失败，别挂住整场"
        return real_replace(src, dst)

    # 共享原语用的是 `os.replace` / `os.path` / `os.getpid`：整份换成一个"只看得到它"的替身
    monkeypatch.setattr(
        atomic_io,
        "os",
        SimpleNamespace(path=os.path, getpid=os.getpid, replace=slow_replace),
    )

    errors: list[BaseException] = []

    def writer(tag: str) -> None:
        try:
            write_hwcheck_record(tmp_path, record_with_symptom(empty_record(), tag))
        except BaseException as exc:  # noqa: BLE001 —— 线程里的异常要带回主线程断言
            errors.append(exc)

    first = threading.Thread(target=writer, args=("先到的",), daemon=True)
    first.start()
    assert first_inside.wait(timeout=30), "第一个写者没走到替换那一步"
    second = threading.Thread(target=writer, args=("后到的",), daemon=True)
    second.start()
    # ⚠ **让第二个整条走完（含它自己那发真实 `replace`）再放行第一个**（工单 backlog-agent-sweep/01）：
    # 两次真实 `os.replace` 一旦重叠，Windows 会对**同一目标**回 `PermissionError(13)` / `WinError 5`
    # ——那是**平台行为**，不是被测实现的缺陷（`record-write-hardening/07` 的对照读数：
    # 固定名实现 25/400、唯一临时名实现 30/400，两边无统计差别；本机负载下约 7% 命中）。
    # 排序之后这条用例只测"临时名互抢"这一件事，**判据一条没放宽**：
    # 固定临时名的实现里，第二个写者会把**同一个**临时文件吃掉（截断重写 + 换入），
    # 第一个放行后 `replace` 的源文件已经不在 → 报错照样红（反向验证读数见票尾）。
    second.join(timeout=30)
    assert not second.is_alive(), "第二个写者没在 30 秒内走完——判据自己失败，别挂住整场"
    release.set()
    first.join(timeout=30)
    second.join(timeout=30)

    assert errors == [], f"并发写报错（临时名互抢）：{errors!r}"
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != HWCHECK_RECORD_FILENAME]
    assert leftovers == [], f"并发写留下了残留：{leftovers}"
    assert read_hwcheck_record(tmp_path).symptom in {"先到的", "后到的"}


def test_update_hwcheck_record_does_not_lose_a_concurrent_field_write(tmp_path):
    """读-改-写整段在临界区里：A 写现象、B 写勾选同时进行 → **两笔都在**。

    确定性做法（照 `tests/test_full_task.py` 的并发先例）：把 A 卡在它自己的合并里
    （已进临界区），B 这时候进来。
    · 收走前（无锁、各自读一份再整份写回）：B 读到的是**空记录**（A 还没写），
      于是 B 落盘的只有勾选；A 随后落盘只有现象 → B 那笔丢了；
    · 收走后：B 在锁上等，A 写完它才**重读**——勾选与现象两笔都在。
    """
    entered = threading.Event()
    release = threading.Event()

    def slow_symptom(record):
        entered.set()
        assert release.wait(timeout=30), "等不到放行——判据自己失败，别挂住整场"
        return record_with_symptom(record, "灯常亮不闪")

    first = threading.Thread(
        target=lambda: update_hwcheck_record(tmp_path, slow_symptom), daemon=True
    )
    first.start()
    assert entered.wait(timeout=30), "第一个写者没进临界区"

    second = threading.Thread(
        target=lambda: update_hwcheck_record(
            tmp_path, lambda r: record_with_checked(r, ["heartbeat", "flash"])
        ),
        daemon=True,
    )
    second.start()
    release.set()
    first.join(timeout=30)
    second.join(timeout=30)

    on_disk = read_hwcheck_record(tmp_path)
    assert on_disk.symptom == "灯常亮不闪", "现象那笔丢了"
    assert on_disk.checked_ids == ("heartbeat", "flash"), "勾选那笔丢了（后写的盖掉了先写的）"


def test_record_with_triage_skips_the_stale_checked_snapshot(tmp_path):
    """排障那笔按字段合并：LLM 窗口里别人改过勾选 → **不写**我们手上那份旧快照。

    `base` = 调模型**之前**读到的那份；临界区里重读到的不等于它 = 这几秒里有人写过。
    """
    advice = parse_triage_advice(_advice(), _context())
    base = record_with_checked(empty_record(), ["flash"])
    fresh = record_with_checked(base, ["flash", "heartbeat"])  # 别人在窗口里又勾了一条

    merged = record_with_triage(
        fresh, base=base, symptom="灯常亮不闪", checked_ids=["flash"], advice=advice
    )
    assert merged.checked_ids == ("flash", "heartbeat"), "旧快照盖掉了别人的新勾选"
    assert merged.symptom == "灯常亮不闪"
    assert merged.advice == advice

    # 反向：窗口里**没人动过**（重读到的就是 base）→ 我们这份勾选仍是最新的，照写
    same = record_with_triage(
        base, base=base, symptom="灯常亮不闪", checked_ids=["flash", "oled"], advice=advice
    )
    assert same.checked_ids == ("flash", "oled")


# ---------------------------------------------------------------------------
# 自建器件事实（工单 hwcheck-unknown-device/09）
# ---------------------------------------------------------------------------

# 一件自建件（I2C，0x68，身份寄存器 0x75，期望 0x68）+ 一条本次接线行
# （支点 i2c_probe 的脚与库内件同脚 = 共总线）
_CUSTOM_ROW = {
    "slug": "mine_gyro",
    "name": "卖家给的六轴模块",
    "address_text": "0x68",
    "read8": "0xD1",
    "write8": "0xD0",
    "register_text": "0x75",
    "expect_text": "0x68",
    "echo_only": False,
    "notes": "卖家页写的 WHO_AM_I，SCL 接 PB6",
    "probe_form": "板上判定",
    "probes": True,
}

_WIRING_WITH_PROBE = {
    "rows": [
        {"slug": "i2c_probe", "role": "SCL", "role_id": "SCL", "pin": "PB6"},
        {"slug": "i2c_probe", "role": "SDA", "role_id": "SDA", "pin": "PB7"},
        {"slug": "ml_mpu6050", "role": "SCL", "role_id": "SCL", "pin": "PB6"},
    ],
    "board_shares": [],
    "order": [{"slug": "mine_gyro", "description": "自建件", "bring_up": False}],
}


def _custom_context(*, customs=(_CUSTOM_ROW,), wiring=_WIRING_WITH_PROBE):
    return build_triage_context(
        platform=PLATFORM_STM32,
        devices=("mine_gyro", "ml_mpu6050"),
        modules=("mine_gyro", "i2c_probe", "ml_mpu6050", "delay", "config"),
        wiring=wiring,
        sections=(),
        unspecialized=(),
        checklist=_CHECKLIST,
        checked_ids=("flash",),
        symptom="mine_gyro 串口报无应答",
        known_modules=_KNOWN_MODULES,
        customs=customs,
    )


def test_context_text_carries_the_custom_device_facts_section():
    """「自建器件事实」段：id / 名称 / 地址两种写法 / 寄存器 / 期望值 / 备注 /
    探测形态 / 共总线——模型据此才知道"这件该怎么查"。"""
    text = triage_context_text(_custom_context())
    for fragment in (
        "【自建器件】",
        "mine_gyro",
        "卖家给的六轴模块",
        "0x68",
        "0xD1",
        "0xD0",
        "0x75",
        "板上判定",
        "与库内件共总线：是",
        "你填的备注：",
    ):
        assert fragment in text, fragment
    assert "用户确认的事实" in text, "段落头要说明这些事实的来源与分量"


def test_context_without_custom_devices_keeps_the_old_text_verbatim():
    """票面硬要求：没有自建件时上下文**逐字**与改动前一致（新段落整段不印）。"""
    text = triage_context_text(_context())
    assert "【自建器件】" not in text
    assert "自建件" not in text


def test_custom_bus_sharing_is_computed_from_the_wiring_rows():
    """共总线判据来自接线行：支点（i2c_probe）的脚被别的模块也占着 = 是。"""
    context = _custom_context()
    assert context.customs_rows[0]["shared_with_library"] is True
    alone = {**_WIRING_WITH_PROBE,
             "rows": [row for row in _WIRING_WITH_PROBE["rows"]
                      if row["slug"] != "ml_mpu6050"]}
    context = _custom_context(wiring=alone)
    assert context.customs_rows[0]["shared_with_library"] is False


def test_custom_words_are_in_the_facts_whitelist():
    """白名单扩容：自建件的 id / 名称里的 slug 形词 / 地址——模型提它们不再被
    当"上下文里没有的东西"拒收。"""
    context = _custom_context()
    advice = _advice(
        summary="mine_gyro 无应答，更像地址或接线问题",
        causes=["卖家给的六轴模块的地址 0x68 可能写错（8 位写法 0xD0）"],
        steps=["核对 mine_gyro 的地址接线"],
    )
    parsed = parse_triage_advice(advice, context)
    assert parsed.verdict == "wiring"


def test_advice_rejects_a_custom_device_that_is_not_in_this_run():
    """反向判据：白名单不是照单全收——提一个**不在本次**的自建件仍被拒收。"""
    context = _custom_context()
    with pytest.raises(TriageFactError) as excinfo:
        parse_triage_advice(
            _advice(summary="更像 mine_other 的地址问题",
                    causes=["mine_other 没接好"],
                    steps=["检查 mine_other 的地址"]),
            context,
        )
    assert "mine_other" in str(excinfo.value)


def test_the_triage_prompt_says_custom_conclusions_come_from_user_facts():
    """提示词要写明：[自建件] 的结论来自用户确认的事实，不许说成"库内模块有问题"。"""
    from contest_generator.llm import HWCHECK_TRIAGE_SYSTEM_PROMPT

    assert "自建件" in HWCHECK_TRIAGE_SYSTEM_PROMPT
    assert "用户确认" in HWCHECK_TRIAGE_SYSTEM_PROMPT
    assert "库内模块" in HWCHECK_TRIAGE_SYSTEM_PROMPT


def test_a_custom_name_that_collides_with_a_library_slug_is_not_rejected():
    """白名单扩容的另一半：**名称**（票面「id / 名称 / 地址」里的那个"名称"）。

    学生给自己的件起名时很自然会带上看到的东西（"卖家给的 oled 模块"）——名称
    会**印进上下文材料**，模型复述它不该被判成"编造了本次没选的库内模块"
    （`oled` 正是库内 slug 且本次没选）。名称词单收一张表（`facts.custom_words`），
    **不动** `known_modules` / `modules` 那对既有判据。
    """
    context = _custom_context(customs=({**_CUSTOM_ROW, "name": "卖家给的 oled 模块"},))
    assert "oled" in context.facts.custom_words
    parsed = parse_triage_advice(
        _advice(
            summary="你那件 oled 模块更像地址问题",
            causes=["卖家给的 oled 模块的地址写成了 8 位写法"],
            steps=["核对 oled 模块的地址与接线"],
        ),
        context,
    )
    assert parsed.verdict == "wiring"


def test_advice_may_quote_the_custom_address_in_both_forms():
    """地址（7 位 + 8 位两种写法）在材料里，模型照手册复述它不该被拒。

    这条是**钉住射程**用的：地址既不是引脚也不是 slug 形词，今天的 token 判据
    本来就碰不到它——写下来是为了哪天判据放宽到"认数字 token"时这一格立刻变红，
    而不是悄悄把手册上的写法误杀。（票面「白名单扩容到 id / 名称 / 地址」里
    "地址"这一半的实现形态就是**这一格**：它印进材料、判据不碰它。）
    """
    context = _custom_context()
    parsed = parse_triage_advice(
        _advice(
            summary="0x68 没有应答（手册上另一种写法是 0xD0，读地址 0xD1）",
            causes=["0xD0 这个 8 位写法可能对应另一件器件"],
            steps=["把 0x68 与 0xD0 两个写法都核一遍"],
        ),
        context,
    )
    assert parsed.verdict == "wiring"


def test_a_custom_id_is_judged_regardless_of_case():
    """id 的判据不靠 slug 词形（`mine_MPU6050` 是合法 id，而 `_SLUG_TOKEN_RE`
    只认小写）：专用形态 `_CUSTOM_ID_RE` 让大小写混写的 id **也判得动**——
    提一个没选的 `mine_MPU6050` 照样拒收（不然这条反向判据在合法 id 上失效）。
    """
    context = _custom_context(
        customs=({**_CUSTOM_ROW, "slug": "mine_MPU6050", "name": "上限大写的件"},)
    )
    assert parse_triage_advice(
        _advice(summary="mine_MPU6050 没有应答"), context
    ).verdict == "wiring"
    with pytest.raises(TriageFactError) as excinfo:
        parse_triage_advice(_advice(summary="更像 mine_OTHER 的问题"), context)
    assert "mine_OTHER" in str(excinfo.value)


def test_a_custom_name_outside_this_run_is_not_judged():
    """**射程边界**（如实钉住，不是漏掉）：只有 id 形态的自建件判得动"在不在本次"。

    件名是用户自由文本（中文为主），"另一个件叫什么名字"没有可判据的词形；
    地址同理（不是 token）。这条把边界写成判据：提到一个本次没有的件名/地址
    **会放过**——与既有「整库也不认识的名字不判」同一条口径（误杀整份建议的
    代价比放过一个大）。要收窄它得先在域层立"登记表 ∩ 本次"的判据，另议。
    """
    context = _custom_context()
    parsed = parse_triage_advice(
        _advice(
            summary="更像卖家那件 bme280 的问题（地址可能是 0x76）",
            causes=["bme280 与本次这件不同"],
            steps=["核对 bme280 的地址 0x76"],
        ),
        context,
    )
    assert parsed.verdict == "wiring"


def test_a_library_module_outside_this_run_is_still_rejected():
    """反向判据的对照组：库内 slug 不在本次、也不在任何自建件名字里 → 照旧拒收。

    上一条给"名称里的词"开了口子，这一条保证口子只对着**本次自建件的名字**开：
    不是"提到任何库内 slug 都放行"。
    """
    context = _custom_context(customs=({**_CUSTOM_ROW, "name": "卖家给的 oled 模块"},))
    with pytest.raises(TriageFactError) as excinfo:
        parse_triage_advice(_advice(summary="更像 jy61p 的问题"), context)
    assert "jy61p" in str(excinfo.value)


def test_a_custom_device_without_an_address_prints_no_empty_address_line():
    """非 I2C 件没有地址（`address=None` 是合法状态，票面明确覆盖 SPI/UART 件）：
    上下文里**不该**出现「地址：（8 位写法：读  / 写 ）」这种空行——同段里
    寄存器那行有守卫、段头又承诺"空段整段不印"，漏这一行就是把一行空事实塞给模型。
    """
    blank = {**_CUSTOM_ROW, "address_text": "", "read8": "", "write8": ""}
    text = triage_context_text(_custom_context(customs=(blank,)))
    assert "【自建器件】" in text, "件本身仍在（它这一趟只是没有地址）"
    assert "地址：" not in text
    assert "8 位写法" not in text
