"""LLM 费用估算：观测 usage → 估算金额（纯函数 + 可配置单价表）。

展示层派生值：只算「估算花费」，不接账单、不算本地电费。单价默认值以
DeepSeek 官方定价页为参考（2026-08-18 曾大幅调价，勿把默认值当实时价），
用户可在设置页覆盖（工单 llm-cost-control/01）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# 参考单价（元 / 百万 token）。官方定价波动大（2026-08 曾调价），此处仅是
# 开箱即用的默认参考值——设置页可覆盖；0 单价 = 关闭该 provider 的估算。
DEFAULT_DEEPSEEK_PRICES: dict[str, float] = {
    "input_per_million": 2.0,
    "output_per_million": 8.0,
}
DEFAULT_LOCAL_PRICES: dict[str, float] = {
    "input_per_million": 0.0,
    "output_per_million": 0.0,
}

_SUPPORTED_PROVIDERS = ("deepseek", "local")


@dataclass(frozen=True)
class LLMPriceTable:
    """一个 provider 的单价表（元 / 百万 token）。"""

    provider: str
    input_per_million: float
    output_per_million: float

    def to_dict(self) -> dict[str, float]:
        return {
            "input_per_million": self.input_per_million,
            "output_per_million": self.output_per_million,
        }

    @classmethod
    def from_dict(cls, provider: str, data: Mapping[str, Any]) -> "LLMPriceTable":
        if provider not in _SUPPORTED_PROVIDERS:
            raise ValueError(f"不支持的 provider：{provider!r}（支持 {_SUPPORTED_PROVIDERS}）")
        if not isinstance(data, Mapping):
            raise ValueError(f"{provider} 单价表必须是 JSON 对象")
        values: dict[str, float] = {}
        for key in ("input_per_million", "output_per_million"):
            value = data.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{provider} 单价字段 {key} 必须是数字")
            if value < 0:
                raise ValueError(f"{provider} 单价字段 {key} 不能为负")
            values[key] = float(value)
        return cls(provider=provider, **values)


def default_price_tables() -> dict[str, LLMPriceTable]:
    """内置默认单价表（deepseek 参考价 + local 零成本）。"""
    return {
        "deepseek": LLMPriceTable.from_dict("deepseek", DEFAULT_DEEPSEEK_PRICES),
        "local": LLMPriceTable.from_dict("local", DEFAULT_LOCAL_PRICES),
    }


def price_tables_from_config(
    raw: Mapping[str, Any] | None,
) -> dict[str, LLMPriceTable]:
    """config.json 的 llm_prices 覆盖 → 单价表；缺省 / 部分缺省用内置默认。

    部分覆盖语义：只写 deepseek 就只覆盖 deepseek，local 仍零成本。
    """
    tables = default_price_tables()
    if not raw or not isinstance(raw, Mapping):
        return tables
    for provider, entry in raw.items():
        if not isinstance(entry, Mapping):
            continue  # 脏条目静默跳过（展示层派生，不阻塞配置加载）
        try:
            tables[provider] = LLMPriceTable.from_dict(provider, entry)
        except ValueError:
            continue
    return tables


def price_tables_to_config(tables: Mapping[str, LLMPriceTable]) -> dict[str, dict[str, float]]:
    """单价表 → JSON 可存形态（完整表：GET /api/settings 直接展示生效单价）。

    与 price_tables_from_config 对偶（缺省合并默认 → 完整序列化）；config.json
    里存的是用户覆盖原文（_optional_dict 原样透传），不经此函数。
    """
    return {provider: table.to_dict() for provider, table in tables.items()}


def estimate_llm_cost(
    usage: Mapping[str, Any] | None,
    table: LLMPriceTable,
) -> float:
    """usage（prompt_tokens / completion_tokens）→ 估算金额（元）。

    缺字段 / 非数值 / 负数一律按 0 计（展示层防御，不抛）；token 计数为模型
    服务商上报值，估算仅供成本参考，不代表实际账单。
    """
    if not usage or not isinstance(usage, Mapping):
        return 0.0
    prompt = _nonnegative_int(usage.get("prompt_tokens"))
    completion = _nonnegative_int(usage.get("completion_tokens"))
    if prompt == 0 and completion == 0:
        return 0.0
    # 不在此处舍入：多次调用聚合时小金额要能累加，展示层再 round
    return (prompt * table.input_per_million + completion * table.output_per_million) / 1_000_000


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value) if value > 0 else 0
