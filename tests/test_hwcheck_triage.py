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
from pathlib import Path

import pytest

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
    triage_context_text,
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


def test_context_facts_whitelist_is_built_from_the_same_material():
    """白名单 = 本次接线表里的脚 + 本次工程模块集；整库词表另存一份。"""
    context = _context()
    assert context.facts.pins == {"PC13", "PB6", "PB7", "PA15"}  # 含板上共享脚
    assert {"led", "ml_mpu6050", "sr04"} <= context.facts.modules
    assert "delay" in context.facts.modules  # 框架件没有接线行，仍属本次工程
    assert "jy61p" in context.facts.known_modules  # 库内有、本次没选
    assert "jy61p" not in context.facts.modules


def test_context_rejects_empty_symptom():
    """没现象可分析（路由层另有 400；域层也不许拿空串去问模型）。"""
    with pytest.raises(HwCheckError):
        _context(symptom="   ")


def test_pins_quoted_from_the_material_are_allowed():
    """**材料里出现过的脚 = 上下文事实**（评审抓到的真缺陷）。

    上板清单的「不对先查」里就写着「stm32 板载三色 LED 在 PC13/PC14/PC15」
    （`hwcheck.render_checklist` 的原文），材料原样喂给模型——模型复述材料里
    的 `PC14` 却被白名单判非法，就会走成"重问 → 兜底降级"。判据必须与材料
    同一处装配：材料里出现过的脚放行，材料里没有的（`PA9`）照旧拒收。

    夹具里接线表只用了 `PC13`，所以 `PC14` 正是"只在材料里出现过"的那个脚。
    """
    baseline = _context()
    ladder = dict(_CHECKLIST[1])
    ladder["check"] = "① 先按一次复位；② 板载三色 LED 在 PC13/PC14/PC15（本程序用红灯）"
    with_material = build_triage_context(
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
    assert "PC14" in with_material.facts.pins      # 材料里写了，就算事实
    assert "PC14" not in baseline.facts.pins       # 材料里没写，就不算
    advice = parse_triage_advice(
        _advice(causes=["绿灯那一路（PC14）没接对"]), with_material
    )
    assert advice.causes
    # 材料里没有的脚照旧拒收（判据没被放宽成"什么脚都行"）
    with pytest.raises(TriageFactError):
        parse_triage_advice(_advice(causes=["PA9 上的线松了"]), with_material)
    with pytest.raises(TriageFactError):
        parse_triage_advice(_advice(causes=["绿灯那一路（PC14）没接对"]), baseline)


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
    assert context.facts.pins == frozenset()


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
    """原子写：落盘后不留 .tmp 半成品。"""
    write_hwcheck_record(tmp_path, record_with_symptom(empty_record(), "现象"))
    assert list(tmp_path.glob("*.tmp")) == []


def test_record_path_is_relative_to_the_project_dir(tmp_path):
    """记录走工程根旁车文件（与赛题工程的 .contest_*.json 同一落点习惯）。"""
    written = write_hwcheck_record(
        tmp_path, record_with_symptom(empty_record(), "现象")
    )
    assert written.parent == Path(tmp_path)
    assert written.name == HWCHECK_RECORD_FILENAME
