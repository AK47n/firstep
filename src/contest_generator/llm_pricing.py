"""LLM 费用估算：观测 usage → 估算金额（纯函数 + 可配置单价表）。

展示层派生值：只算「估算花费」，不接账单、不算本地电费。单价默认值以
DeepSeek 官方定价页为参考（2026-08-18 曾大幅调价，勿把默认值当实时价），
用户可在设置页覆盖（工单 llm-cost-control/01）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

# 参考单价（元 / 百万 token）。官方定价波动大（2026-08-18 曾大幅调价），此处仅是
# 开箱即用的默认参考值——设置页可覆盖；0 单价 = 关闭该 provider 的估算。
# DeepSeek Flash 输入分缓存命中 / 未命中两档（官方差价 ~30 倍，估算必须拆分
# 计价）；默认值取「高峰时段」档（工具高峰使用多，估算偏保守不低估；用户可
# 在设置页按实际时段覆盖）。
DEFAULT_DEEPSEEK_PRICES: dict[str, float] = {
    "input_cache_hit_per_million": 0.10,
    "input_cache_miss_per_million": 3.0,
    "output_per_million": 9.0,
}
DEFAULT_LOCAL_PRICES: dict[str, float] = {
    "input_cache_hit_per_million": 0.0,
    "input_cache_miss_per_million": 0.0,
    "output_per_million": 0.0,
}

# DeepSeek Flash 官方价格参考表（2026-08 官方定价，单位元/百万 token）——
# 单源：设置页折叠面板经 /api/settings 的 price_reference 渲染展示，
# 用户可据此在输入框覆盖默认值；改价只改这一处。
DEEPSEEK_FLASH_PRICE_REFERENCE: dict[str, Any] = {
    "input_cache_hit": {"off_peak": 0.05, "peak": 0.10},
    "input_cache_miss": {"off_peak": 1.5, "peak": 3.0},
    "output": {"off_peak": 4.5, "peak": 9.0},
    "concurrent_connections": 2500,
    "as_of": "2026-08",
}

_SUPPORTED_PROVIDERS = ("deepseek", "local")

# 单价表可配置键（新形态：输入分缓存命中/未命中两档）
_PRICE_KEYS = (
    "input_cache_hit_per_million",
    "input_cache_miss_per_million",
    "output_per_million",
)


@dataclass(frozen=True)
class LLMPriceTable:
    """一个 provider 的单价表（元 / 百万 token）。

    输入分缓存命中 / 未命中两档（DeepSeek Flash 官方计价，差价 ~30 倍——
    估算必须拆分，见 estimate_llm_cost）；旧配置形态 {input_per_million,
    output_per_million} 兼容：input 视为未命中档（未命中是常态，保守），
    命中档用内置默认。
    """

    provider: str
    input_cache_hit_per_million: float
    input_cache_miss_per_million: float
    output_per_million: float

    def to_dict(self) -> dict[str, float]:
        return {
            "input_cache_hit_per_million": self.input_cache_hit_per_million,
            "input_cache_miss_per_million": self.input_cache_miss_per_million,
            "output_per_million": self.output_per_million,
        }

    @classmethod
    def from_dict(cls, provider: str, data: Mapping[str, Any]) -> "LLMPriceTable":
        if provider not in _SUPPORTED_PROVIDERS:
            raise ValueError(f"不支持的 provider：{provider!r}（支持 {_SUPPORTED_PROVIDERS}）")
        if not isinstance(data, Mapping):
            raise ValueError(f"{provider} 单价表必须是 JSON 对象")

        def _read_optional(key: str) -> float | None:
            if key not in data:
                return None
            value = data[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{provider} 单价字段 {key} 必须是数字")
            if value < 0:
                raise ValueError(f"{provider} 单价字段 {key} 不能为负")
            return float(value)

        def _read_required(key: str) -> float:
            value = _read_optional(key)
            if value is None:
                raise ValueError(f"{provider} 单价表缺少计费字段 {key}")
            return value

        hit = _read_optional("input_cache_hit_per_million")
        miss = _read_optional("input_cache_miss_per_million")
        if hit is None and miss is None:
            # 旧形态 {input_per_million, output_per_million}：input = 未命中档
            # （保守），命中档 = 内置默认（新字段缺省语义）
            miss = _read_required("input_per_million")
            hit = (
                DEFAULT_DEEPSEEK_PRICES["input_cache_hit_per_million"]
                if provider == "deepseek"
                else 0.0
            )
        else:
            if hit is None:
                hit = 0.0
            if miss is None:
                miss = 0.0
        return cls(
            provider=provider,
            input_cache_hit_per_million=hit,
            input_cache_miss_per_million=miss,
            output_per_million=_read_required("output_per_million"),
        )


# 计费时段词表（设置页「计费时段」选择器，单源）：高峰 = peak（白天比赛/集训
# 时段，官方价高）、空闲 = off_peak（夜间/低峰，官方价低）。period 决定
# 未覆盖时的基准价（官方该时段价）；用户输入框填值 = 覆盖基准。
PRICE_PERIODS = ("peak", "off_peak")

# 官方价格参考表 → 指定时段基准表（元/百万 token，单源派生）
def _deepseek_period_prices(period: str) -> dict[str, float]:
    if period not in PRICE_PERIODS:
        raise ValueError(f"未知计费时段：{period!r}（支持 {PRICE_PERIODS}）")
    ref = DEEPSEEK_FLASH_PRICE_REFERENCE
    return {
        "input_cache_hit_per_million": ref["input_cache_hit"][period],
        "input_cache_miss_per_million": ref["input_cache_miss"][period],
        "output_per_million": ref["output"][period],
    }


def default_price_tables(period: str = "peak") -> dict[str, LLMPriceTable]:
    """内置默认单价表（deepseek = 所选时段的官方价 + local 零成本）。

    period（工单 01 扩展）：计费时段（peak / off_peak）决定 deepseek 基准价；
    缺省 peak（与旧默认值同档）。"""
    return {
        "deepseek": LLMPriceTable.from_dict("deepseek", _deepseek_period_prices(period)),
        "local": LLMPriceTable.from_dict("local", DEFAULT_LOCAL_PRICES),
    }


def _pick_field(
    raw_entry: Mapping[str, Any],
    parsed: LLMPriceTable,
    base: LLMPriceTable,
    key: str,
    legacy: str | None = None,
) -> float:
    """部分覆盖合并：覆盖条目声明了该字段（或 legacy 旧字段）→ 用覆盖值；
    未声明 → 沿用时段基准值（base）。"""
    if key in raw_entry or (legacy and legacy in raw_entry):
        return getattr(parsed, key)
    return getattr(base, key)


def price_tables_from_config(
    raw: Mapping[str, Any] | None,
    period: str = "peak",
) -> dict[str, LLMPriceTable]:
    """config.json 的 llm_prices 覆盖 + 计费时段 → 单价表；缺省 / 部分缺省用
    时段基准价。

    部分覆盖语义：只覆盖某档（如 input_cache_miss_per_million）时，其余档
    沿用所选时段的官方基准价（不归零）；只写 deepseek 就只覆盖 deepseek，
    local 仍零成本。旧形态 {input_per_million} 兼容 = 未命中档覆盖。
    """
    tables = default_price_tables(period)
    if not raw or not isinstance(raw, Mapping):
        return tables
    for provider, raw_entry in raw.items():
        if not isinstance(raw_entry, Mapping):
            continue  # 脏条目静默跳过（展示层派生，不阻塞配置加载）
        try:
            parsed = LLMPriceTable.from_dict(provider, raw_entry)
        except ValueError:
            continue
        base = tables[provider]
        tables[provider] = LLMPriceTable(
            provider=provider,
            input_cache_hit_per_million=_pick_field(
                raw_entry, parsed, base, "input_cache_hit_per_million"
            ),
            input_cache_miss_per_million=_pick_field(
                raw_entry,
                parsed,
                base,
                "input_cache_miss_per_million",
                legacy="input_per_million",
            ),
            output_per_million=_pick_field(raw_entry, parsed, base, "output_per_million"),
        )
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
    """usage（prompt_tokens / completion_tokens + 缓存拆分）→ 估算金额（元）。

    DeepSeek Flash 官方输入价分缓存命中 / 未命中两档（差价 ~30 倍），拆分
    计价：usage 带 prompt_cache_hit_tokens / prompt_cache_miss_tokens 时
    分别按两档单价算；缺拆分字段（旧 API / 未上报）→ 全部按未命中档
    （保守，未命中是常态）。输出恒按 output 单价。缺字段 / 非数值 / 负数
    一律按 0 计（展示层防御，不抛）；token 计数为模型服务商上报值，估算
    仅供成本参考，不代表实际账单。
    """
    if not usage or not isinstance(usage, Mapping):
        return 0.0
    completion = _nonnegative_int(usage.get("completion_tokens"))
    prompt_hit = _nonnegative_int(usage.get("prompt_cache_hit_tokens"))
    prompt_miss = _nonnegative_int(usage.get("prompt_cache_miss_tokens"))
    if prompt_hit == 0 and prompt_miss == 0:
        # 无缓存拆分：全部按未命中档（保守；prompt_tokens 整体计价）
        prompt_hit = 0
        prompt_miss = _nonnegative_int(usage.get("prompt_tokens"))
    if prompt_hit == 0 and prompt_miss == 0 and completion == 0:
        return 0.0
    # 不在此处舍入：多次调用聚合时小金额要能累加，展示层再 round
    return (
        prompt_hit * table.input_cache_hit_per_million
        + prompt_miss * table.input_cache_miss_per_million
        + completion * table.output_per_million
    ) / 1_000_000


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value) if value > 0 else 0
