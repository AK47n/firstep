"""LLM 费用估算纯函数与单价表（工单 llm-cost-control/01）。"""

from __future__ import annotations

import pytest

from contest_generator.llm_pricing import (
    DEFAULT_DEEPSEEK_PRICES,
    DEFAULT_LOCAL_PRICES,
    DEEPSEEK_FLASH_PRICE_REFERENCE,
    LLMPriceTable,
    default_price_tables,
    estimate_llm_cost,
    price_tables_from_config,
)


def test_estimate_llm_cost_uses_input_and_output_rates():
    """输入（未命中档）输出 token 分别按对应单价计费（元）。"""
    table = LLMPriceTable(
        provider="deepseek",
        input_cache_hit_per_million=0.10,
        input_cache_miss_per_million=2.0,
        output_per_million=8.0,
    )
    usage = {"prompt_tokens": 500_000, "completion_tokens": 100_000}
    # 0.5 * 2 + 0.1 * 8 = 1.0 + 0.8 = 1.8（无缓存拆分 → 全未命中档）
    assert estimate_llm_cost(usage, table) == pytest.approx(1.8)


def test_estimate_llm_cost_zero_when_no_usage_fields():
    """缺 usage 字段 / 空 dict → 0 元（不炸）。"""
    table = LLMPriceTable("deepseek", 0.10, 2.0, 8.0)
    assert estimate_llm_cost({}, table) == 0.0
    assert estimate_llm_cost(None, table) == 0.0
    assert estimate_llm_cost({"prompt_tokens": 10}, table) == pytest.approx(10 / 1e6 * 2.0)


def test_estimate_llm_cost_ignores_non_numeric_and_negative():
    """非法字段（字符串 / 负数 / 小数）按 0 处理，防御脏数据。"""
    table = LLMPriceTable("deepseek", 0.10, 2.0, 8.0)
    usage = {"prompt_tokens": "100", "completion_tokens": -5, "extra": 3.14}
    assert estimate_llm_cost(usage, table) == 0.0


def test_local_prices_default_to_zero_cost():
    """本地默认单价 = 0 成本（不估算电费/机器）。"""
    assert DEFAULT_LOCAL_PRICES == {
        "input_cache_hit_per_million": 0.0,
        "input_cache_miss_per_million": 0.0,
        "output_per_million": 0.0,
    }
    local = LLMPriceTable.from_dict("local", DEFAULT_LOCAL_PRICES)
    assert estimate_llm_cost({"prompt_tokens": 1_000_000, "completion_tokens": 500_000}, local) == 0.0


def test_deepseek_default_prices_present():
    """内置 DeepSeek 参考单价存在且非负（注释标明以官方为准，设置页可改）。"""
    assert DEFAULT_DEEPSEEK_PRICES["input_cache_hit_per_million"] >= 0
    assert DEFAULT_DEEPSEEK_PRICES["input_cache_miss_per_million"] >= 0
    assert DEFAULT_DEEPSEEK_PRICES["output_per_million"] >= 0


def test_flash_price_reference_shape():
    """官方价格参考表（设置页折叠面板数据源）：四档价格 + 并发 + 日期，单源。"""
    ref = DEEPSEEK_FLASH_PRICE_REFERENCE
    assert ref["input_cache_hit"] == {"off_peak": 0.05, "peak": 0.10}
    assert ref["input_cache_miss"] == {"off_peak": 1.5, "peak": 3.0}
    assert ref["output"] == {"off_peak": 4.5, "peak": 9.0}
    assert ref["concurrent_connections"] == 2500
    assert ref["as_of"]


def test_default_price_tables_follow_period():
    """计费时段决定未覆盖基准价：peak = 高峰官方价，off_peak = 空闲官方价。"""
    peak = default_price_tables("peak")["deepseek"]
    assert peak.input_cache_hit_per_million == pytest.approx(0.10)
    assert peak.input_cache_miss_per_million == pytest.approx(3.0)
    assert peak.output_per_million == pytest.approx(9.0)

    off = default_price_tables("off_peak")["deepseek"]
    assert off.input_cache_hit_per_million == pytest.approx(0.05)
    assert off.input_cache_miss_per_million == pytest.approx(1.5)
    assert off.output_per_million == pytest.approx(4.5)

    with pytest.raises(ValueError):
        default_price_tables("evening")


def test_price_tables_from_config_period_base_with_override():
    """覆盖优先于时段基准：off_peak 基准 + deepseek 覆盖 = 覆盖值生效，
    local 未覆盖 = 零成本。"""
    tables = price_tables_from_config(
        {"deepseek": {"input_cache_miss_per_million": 2.0, "output_per_million": 8.0}},
        period="off_peak",
    )
    assert tables["deepseek"].input_cache_miss_per_million == 2.0
    assert tables["deepseek"].input_cache_hit_per_million == pytest.approx(0.05)
    assert tables["local"].input_cache_miss_per_million == 0.0


def test_price_table_roundtrip_and_validation():
    """from_dict / to_dict 往返；非法值（负数 / 非数字 / 未知 provider）大声失败。"""
    table = LLMPriceTable("deepseek", 0.10, 3.0, 9.5)
    assert LLMPriceTable.from_dict("deepseek", table.to_dict()) == table

    with pytest.raises(ValueError):
        LLMPriceTable.from_dict("deepseek", {"input_cache_miss_per_million": -1.0, "output_per_million": 8.0})
    with pytest.raises(ValueError):
        LLMPriceTable.from_dict("deepseek", {"input_cache_miss_per_million": "2", "output_per_million": 8.0})
    with pytest.raises(ValueError):
        LLMPriceTable.from_dict("unknown", {"input_cache_hit_per_million": 1.0, "input_cache_miss_per_million": 1.0, "output_per_million": 1.0})
    with pytest.raises(ValueError):
        LLMPriceTable.from_dict("deepseek", {"output_per_million": 8.0})


def test_price_table_legacy_input_field_means_cache_miss():
    """旧配置形态 {input_per_million, output_per_million} 兼容：input = 未命中档
    （保守），命中档 = 内置默认（未显式配置时）。"""
    table = LLMPriceTable.from_dict(
        "deepseek", {"input_per_million": 2.0, "output_per_million": 8.0}
    )
    assert table.input_cache_miss_per_million == 2.0
    assert table.input_cache_hit_per_million == pytest.approx(
        DEEPSEEK_FLASH_PRICE_REFERENCE["input_cache_hit"]["peak"]
    )
    assert table.output_per_million == 8.0


def test_estimate_llm_cost_splits_cache_hit_and_miss():
    """输入按缓存命中/未命中两档分别计价（官方差价 ~30 倍，拆分是计价前提）。"""
    table = LLMPriceTable("deepseek", 0.10, 3.0, 9.0)
    usage = {
        "prompt_cache_hit_tokens": 900_000,
        "prompt_cache_miss_tokens": 100_000,
        "prompt_tokens": 1_000_000,
        "completion_tokens": 100_000,
    }
    # 0.9*0.1 + 0.1*3 + 0.1*9 = 0.09 + 0.3 + 0.9 = 1.29
    assert estimate_llm_cost(usage, table) == pytest.approx(1.29)


def test_estimate_llm_cost_falls_back_to_all_miss():
    """缺缓存拆分字段（旧 API / 未上报）→ 全部按未命中档（保守，不低估）。"""
    table = LLMPriceTable("deepseek", 0.10, 3.0, 9.0)
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 100_000}
    # 1.0*3 + 0.1*9 = 3.9（比拆分路径贵——保守）
    assert estimate_llm_cost(usage, table) == pytest.approx(3.9)
