"""LLM 费用估算纯函数与单价表（工单 llm-cost-control/01）。"""

from __future__ import annotations

import pytest

from contest_generator.llm_pricing import (
    DEFAULT_DEEPSEEK_PRICES,
    DEFAULT_LOCAL_PRICES,
    LLMPriceTable,
    estimate_llm_cost,
)


def test_estimate_llm_cost_uses_input_and_output_rates():
    """输入输出 token 分别按对应单价计费（元）。"""
    table = LLMPriceTable(
        provider="deepseek",
        input_per_million=2.0,
        output_per_million=8.0,
    )
    usage = {"prompt_tokens": 500_000, "completion_tokens": 100_000}
    # 0.5 * 2 + 0.1 * 8 = 1.0 + 0.8 = 1.8
    assert estimate_llm_cost(usage, table) == pytest.approx(1.8)


def test_estimate_llm_cost_zero_when_no_usage_fields():
    """缺 usage 字段 / 空 dict → 0 元（不炸）。"""
    table = LLMPriceTable("deepseek", 2.0, 8.0)
    assert estimate_llm_cost({}, table) == 0.0
    assert estimate_llm_cost(None, table) == 0.0
    assert estimate_llm_cost({"prompt_tokens": 10}, table) == pytest.approx(10 / 1e6 * 2.0)


def test_estimate_llm_cost_ignores_non_numeric_and_negative():
    """非法字段（字符串 / 负数 / 小数）按 0 处理，防御脏数据。"""
    table = LLMPriceTable("deepseek", 2.0, 8.0)
    usage = {"prompt_tokens": "100", "completion_tokens": -5, "extra": 3.14}
    assert estimate_llm_cost(usage, table) == 0.0


def test_local_prices_default_to_zero_cost():
    """本地默认单价 = 0 成本（不估算电费/机器）。"""
    assert DEFAULT_LOCAL_PRICES == {"input_per_million": 0.0, "output_per_million": 0.0}
    local = LLMPriceTable.from_dict("local", DEFAULT_LOCAL_PRICES)
    assert estimate_llm_cost({"prompt_tokens": 1_000_000, "completion_tokens": 500_000}, local) == 0.0


def test_deepseek_default_prices_present():
    """内置 DeepSeek 参考单价存在且非负（注释标明以官方为准，设置页可改）。"""
    assert DEFAULT_DEEPSEEK_PRICES["input_per_million"] >= 0
    assert DEFAULT_DEEPSEEK_PRICES["output_per_million"] >= 0


def test_price_table_roundtrip_and_validation():
    """from_dict / to_dict 往返；非法值（负数 / 非数字 / 未知 provider）大声失败。"""
    table = LLMPriceTable("deepseek", 2.5, 9.5)
    assert LLMPriceTable.from_dict("deepseek", table.to_dict()) == table

    with pytest.raises(ValueError):
        LLMPriceTable.from_dict("deepseek", {"input_per_million": -1.0, "output_per_million": 8.0})
    with pytest.raises(ValueError):
        LLMPriceTable.from_dict("deepseek", {"input_per_million": "2", "output_per_million": 8.0})
    with pytest.raises(ValueError):
        LLMPriceTable.from_dict("unknown", {"input_per_million": 1.0, "output_per_million": 1.0})
    with pytest.raises(ValueError):
        LLMPriceTable.from_dict("deepseek", {"output_per_million": 8.0})
