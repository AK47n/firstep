# -*- coding: utf-8 -*-
"""「资料 → 事实草稿」的域层（工单 hwcheck-unknown-device/07）。

模型把学生贴的资料（卖家页文字 / 手册抽取文本 / 照片描述）抽成**草稿**：每条
事实带原文出处片段，抽不到的留空。判据重点（都是"静默出错最伤"的地方）：

① **字段白名单**：模型输出里多一个字段、少一个字段都不收（输出不可信，宁可
   大声失败重问——照 `selection.build_module_selection` 的先例）；
② **出处片段 = 反编造判据**：每条有值的事实必须带一段**原文里真实存在**的
   片段（归一化后子串匹配）——模型引了一段资料里没有的话 = 编造，当场拒收
   （域拒绝，带理由重问一次，仍不行降级为纯手填）；
③ **数值合法**：地址 7 位（0x08–0x77）、寄存器 / 期望值 8 位——照定义层的
   同一个区间，草稿里就该把填错的挡住，而不是等用户确认时再炸；
④ **抽不到 = 留空 + 一句"手册里没找到"**（文案单源在域层，前端照渲染）——
   不编一个默认值出来；
⑤ **本链路不产出任何 C**：草稿是表单的预填，探测程序永远由确认后的定义走
   确定性渲染（结构守卫钉住 import 面）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contest_generator.hwcheck_errors import HwCheckError
from contest_generator.my_device_draft import (
    DRAFT_FIELDS,
    MISSING_TEXT,
    SOURCE_MAX_CHARS,
    DeviceDraft,
    DeviceDraftError,
    DeviceDraftFactError,
    draft_payload,
    empty_draft,
    parse_device_draft,
)

MATERIAL = (
    "BMP280 气压传感器模块。供电 3.3V。I2C 地址：0x76（SDO 接地时）或 0x77。"
    "芯片 ID 寄存器 0xD0，读回值应为 0x58。"
)


def _raw(**overrides) -> dict:
    """一份模型输出的"好草稿"（全字段有值 + 出处片段），用关键字覆盖出坏形态。"""
    data = {
        "name": {"value": "BMP280", "source": "BMP280 气压传感器模块"},
        "bus": {"value": "i2c", "source": "I2C 地址：0x76"},
        "address": {"value": "0x76", "source": "I2C 地址：0x76"},
        "register": {"value": "0xD0", "source": "芯片 ID 寄存器 0xD0"},
        "expect": {"value": "0x58", "source": "读回值应为 0x58"},
        "notes": {"value": "SDO 接地时 0x76", "source": "SDO 接地时"},
    }
    for key, value in overrides.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return data


# ---------------------------------------------------------------------------
# 好草稿：解析、归一、载荷形状
# ---------------------------------------------------------------------------


def test_a_good_extraction_parses_and_normalizes():
    draft = parse_device_draft(_raw(), MATERIAL)
    assert draft.field("name").value == "BMP280"
    assert draft.field("address").value == "0x76"
    # 整数与十进制写法归一到同一个 0xNN 显示
    assert draft.field("register").value == "0xD0"
    assert draft.field("bus").value == "i2c"
    assert draft.field("name").found is True


def test_integer_and_decimal_notations_normalize_to_the_same_hex():
    draft = parse_device_draft(_raw(address={"value": 118, "source": "I2C 地址：0x76"}), MATERIAL)
    assert draft.field("address").value == "0x76"
    draft = parse_device_draft(_raw(register={"value": "208", "source": "芯片 ID 寄存器 0xD0"}), MATERIAL)
    assert draft.field("register").value == "0xD0"


def test_the_payload_shape_is_exact_and_fields_carry_their_quotes():
    payload = draft_payload(parse_device_draft(_raw(), MATERIAL))
    assert set(payload) == {"fields", "missing", "missing_text"}
    assert set(payload["fields"]) == set(DRAFT_FIELDS)
    entry = payload["fields"]["address"]
    assert set(entry) == {"value", "source", "found"}
    assert entry["value"] == "0x76"
    assert entry["source"] == "I2C 地址：0x76"
    assert payload["missing"] == []
    assert payload["missing_text"] == MISSING_TEXT


# ---------------------------------------------------------------------------
# 白名单：多一个 / 少一个字段都不收
# ---------------------------------------------------------------------------


def test_a_field_outside_the_whitelist_is_rejected():
    with pytest.raises(DeviceDraftError) as excinfo:
        parse_device_draft({**_raw(), "driver": {"value": "bme280.c", "source": "驱动"}}, MATERIAL)
    assert "白名单" in str(excinfo.value)


def test_a_missing_field_is_rejected():
    with pytest.raises(DeviceDraftError) as excinfo:
        parse_device_draft(_raw(notes=None), MATERIAL)
    assert "notes" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 反编造：每条有值的事实必须带"原文里真实存在"的出处片段
# ---------------------------------------------------------------------------


def test_a_fact_without_a_source_quote_is_rejected():
    with pytest.raises(DeviceDraftError) as excinfo:
        parse_device_draft(_raw(address={"value": "0x76", "source": ""}), MATERIAL)
    assert "出处" in str(excinfo.value)


def test_a_source_quote_not_in_the_material_is_fabrication():
    with pytest.raises(DeviceDraftFactError) as excinfo:
        parse_device_draft(
            _raw(address={"value": "0x76", "source": "地址手册第 3 页写明 0x76"}),
            MATERIAL,
        )
    assert isinstance(excinfo.value, HwCheckError)
    assert "原文" in str(excinfo.value)


def test_the_source_quote_matches_across_whitespace_and_case():
    draft = parse_device_draft(
        _raw(name={"value": "BMP280", "source": "bmp280  气压传感器"}),
        MATERIAL,
    )
    assert draft.field("name").found is True


def test_an_overlong_source_quote_is_rejected():
    with pytest.raises(DeviceDraftError) as excinfo:
        parse_device_draft(
            _raw(name={"value": "BMP280", "source": "B" * (SOURCE_MAX_CHARS + 1)}),
            MATERIAL,
        )
    assert "出处" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 数值合法：区间与写法照定义层
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["0x00", "0x07", "0x78", "0xFF", "3.3", "abc", True])
def test_an_out_of_range_or_non_numeric_address_is_rejected(bad):
    with pytest.raises(DeviceDraftError):
        parse_device_draft(_raw(address={"value": bad, "source": "I2C 地址：0x76"}), MATERIAL)


@pytest.mark.parametrize("bad", ["0x100", "-1", "1.5"])
def test_an_out_of_range_register_is_rejected(bad):
    with pytest.raises(DeviceDraftError):
        parse_device_draft(_raw(register={"value": bad, "source": "芯片 ID 寄存器 0xD0"}), MATERIAL)


def test_an_unknown_bus_word_is_rejected():
    with pytest.raises(DeviceDraftError) as excinfo:
        parse_device_draft(_raw(bus={"value": "i2c2", "source": "I2C 地址：0x76"}), MATERIAL)
    assert "总线" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 抽不到：留空 + "手册里没找到"（不编默认值）
# ---------------------------------------------------------------------------


def test_unextracted_fields_come_back_empty_with_the_honest_note():
    raw = {key: {"value": None, "source": ""} for key in DRAFT_FIELDS}
    draft = parse_device_draft(raw, MATERIAL)
    for key in DRAFT_FIELDS:
        assert draft.field(key).found is False
        assert draft.field(key).value == ""
    payload = draft_payload(draft)
    assert payload["missing"] == list(DRAFT_FIELDS)
    assert payload["missing_text"] == "手册里没找到"


def test_partially_extracted_draft_lists_only_its_missing_fields():
    raw = {**_raw(), "register": {"value": None, "source": ""}, "expect": {"value": None, "source": ""}}
    payload = draft_payload(parse_device_draft(raw, MATERIAL))
    assert payload["missing"] == ["register", "expect"]
    assert payload["fields"]["register"]["found"] is False


def test_empty_draft_is_the_all_missing_draft():
    payload = draft_payload(empty_draft())
    assert payload["missing"] == list(DRAFT_FIELDS)
    for entry in payload["fields"].values():
        assert entry == {"value": "", "source": "", "found": False}


# ---------------------------------------------------------------------------
# 形状健壮：非对象 / 字段非对象 / 值类型怪
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["not json data", [], None, {"name": "BMP280"}])
def test_malformed_shapes_are_rejected(raw):
    with pytest.raises(DeviceDraftError):
        parse_device_draft(raw, MATERIAL)


def test_a_non_string_name_is_rejected():
    with pytest.raises(DeviceDraftError):
        parse_device_draft(_raw(name={"value": 123, "source": "BMP280 气压传感器模块"}), MATERIAL)


# ---------------------------------------------------------------------------
# 结构守卫：这条链路不产出任何 C（AI 不写代码、不生成判据）
# ---------------------------------------------------------------------------


def test_the_draft_chain_imports_nothing_that_renders_c():
    """草稿模块的 import 面不允许出现任何渲染 / 生成侧模块。

    spec 的硬边界：AI 在这条链路里只填表单草稿；探测程序永远由**确认后的定义**
    走确定性渲染。这条用 grep 式判据钉住（先例：`test_entry_store.py` 的单址
    守卫）——将来有人图省事在草稿里"顺手"生成点什么，这条当场红。
    """
    source = Path(__file__).parents[1].joinpath(
        "src", "contest_generator", "my_device_draft.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "import hwcheck", "from .hwcheck import", "from .generator import",
        "render_main_c", "render_checklist", "resolve_custom_sections",
    ):
        assert forbidden not in source, f"草稿链路不许出现 {forbidden!r}"


def test_the_draft_json_contract_is_the_documented_one():
    """系统提示词里的 JSON 契约字段与域层白名单一致（改白名单忘了改提示词 = 模型
    永远输出旧形状、永远被拒）。"""
    from contest_generator.llm import DEVICE_DRAFT_SYSTEM_PROMPT

    for field in DRAFT_FIELDS:
        assert f'"{field}"' in DEVICE_DRAFT_SYSTEM_PROMPT, field
    assert "null" in DEVICE_DRAFT_SYSTEM_PROMPT, "契约要说清抽不到给 null"
