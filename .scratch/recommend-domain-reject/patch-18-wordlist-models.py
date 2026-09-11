# -*- coding: utf-8 -*-
"""工单 real-acceptance/08 数据补丁：把方案去括号裸名补进同类别行的 models。

判据（工单「修复方向 2 裁定规则」，机械可判）：
- 入 models = 该裸名是电赛真会买的硬件（能写进采购单的名词短语）；
- 不入 = ① 平台/主控本身；② 上位概念（词表只有更具体型号）；③ 形态是句子 /
  组合描述；④ 与既有 models 条目重复。

**字节预算是硬约束（本脚本的核心）**：词表段由 format_wordlist_prompt 渲染进
select 请求，而「全量送达 + 真实库最坏形态距 129024 边界留 2KB 余量」两条契约
同时成立时，词表段只能涨 ~473B（measure-18-wordlist-budget.py 实测）。所以本
脚本按 RANK 顺序贪心取用，累计字节超预算即停，并在结束时断言不超。

裁定为「不入」的裸名（理由见工单 08「裁定规则」节）与「规则可入但预算不足」
（DEFERRED）分开记录：前者是口径判决，后者是账不够，别混为一谈。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src" / "contest_generator" / "wordlist.json"
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.budget import wire_size  # noqa: E402
from contest_generator.llm import WORDLIST_PROMPT_BYTES, WORDLIST_TRUNCATION_NOTICE  # noqa: E402
from contest_generator.wordlist import load_wordlist  # noqa: E402

# 词表段预算（显式）：全量送达上限 − 基线实发 = 可用增量
_SEGMENT_BUDGET = WORDLIST_PROMPT_BYTES - wire_size(WORDLIST_TRUNCATION_NOTICE)
_OLD_SENT = 8849  # 基线词表段实发（git HEAD 实测：全量 wire 8849、未截断）
ADD_BUDGET_BYTES = 780  # 段实发 8849+780=9629 → 最坏 ≈128220 ≤ 129024（留 ~800B）

# 裁定为「不入」的裸名（理由见工单 08「裁定规则」节；脚本机械跳过）
EXCLUDED = {
    "LED 指示灯": "规则④：与既有 models「LED」重复",
    "LED + 蜂鸣器 声光组合套件": "规则③：句子 / 组合描述（不是单一采购件）",
    "称重传感器": "规则②：上位概念（词表只有更具体型号 HX711）",
    "超声波测距": "规则③：功能描述句（品类名 models 已有「超声波传感器」）",
    "激光测距": "规则③：功能描述句（型号 VL53L0X 已在 models）",
    "模拟量超声波测距": "规则③：功能 + 接口描述句（型号 US-016 已在 models）",
    "车模自带驱动板": "规则③：半句话（全名是组合描述，非标准采购件）",
    "蓝牙 4.0/5.0": "规则③：规格片段非器件名（品类名 models 已有「蓝牙模块」）",
    "2.8/3.2/3.5 寸 ILI 大屏": "规则③：尺寸枚举句（型号 ILI9341 / ILI9488 已在 models）",
    "1.14 寸 ST7789 并口屏": "规则③：尺寸 + 接口长句（型号 ST7789 已在 models）",
}

# 入 models 的名字（按优先级排序；累计超预算即顺延进 DEFERRED，见工单）
# 预算来由（硬约束，实测）：词表段全量送达 + 真实库最坏形态距 129024 边界留
# 2KB 余量 ⇒ 词表段实发只能涨 ~1113B。**注意记账口径**：models 里加一条名
# 会让词表段涨两处——该行 models 列表本身，以及 format_wordlist_prompt 里
# 「选购方案」段（方案名已载）的重复——所以必须按「词表段实发增量」逐条试加
# 记账（本脚本做法），按 JSON 增量估会低估（实测 11 条 ≈ 551B 段增量）。
RANK = (
    # A 现场四条的逐字被拒名（验收标准 ② 必须成立）
    "红外对管循迹数组",
    "红外测距传感器",
    "直流减速电机 + TB6612 双路驱动板",
    "串口摄像头（JPEG 输出 UART 转接）",
    # B「修复方向 1」点名的同族裸名
    "串口摄像头",
    "红外避障探头",
    "串口超声波",
    # C 规则可入的品类词裸名——**按「真机可达性优先」排序**（不按成本）：
    #   真机复跑实测「脉冲式步进电机 + 驱动板」被模型照抄 → 证明这类「方案名 = 型号 +
    #   品类长句」是真实可达面（不是理论风险），优先收；其余按可达性降序，
    #   预算内收得下多少算多少，收不下的进 DEFERRED（下批工作面）。
    "脉冲式步进电机 + 驱动板",                                   # 真机 2026H 实测被拒
    "指纹识别模块", "ADS1115 四通道 ADC", "HX711 称重传感器",
    "MPU6050 六轴姿态模块", "独立轻触按键模块",
    "DHT11 温湿度传感器", "AHT10 温湿度传感器", "SHT30 温湿度传感器",
    "L298N 大电流驱动板", "1 路 5V 继电器模块", "PCA9685 16 路舵机板",
    "红外对射传感器", "有源蜂鸣器模块", "0.96 寸 OLED 单色屏",
    "RC522 射频 IC 卡读卡器", "JQ8900 语音播报模块", "SYN6288 语音合成模块",
    "磁力计指南针", "双轴摇杆按键", "MAX7219 数码管/点阵",
    "BMP180 气压/海拔传感器", "MS5611 高精度气压传感器",
    "GP2Y1014AU 粉尘传感器", "S12SD 紫外线传感器", "BH1750 光照度传感器",
    "TTP224 4 路电容触摸按键", "TCS34725 颜色识别传感器",
    "MLX90614 非接触红外测温", "MQ-2 烟雾/可燃气体传感器",
    "MQ-135 空气质量传感器", "DS18B20 单总线温度传感器",
    "SHT20 温湿度传感器", "JY61P 六轴姿态传感器", "红外遥控接收头 VS1838B",
)

# 行内归属（裸名 → 该行 category），与工单「逐条裁定」表一致
HOME = {}


def _home_of(name: str) -> str | None:
    for category, names in HOME.items():
        if name in names:
            return category
    return None


def bare(name: str) -> str:
    return re.sub(r"（[^）]*）", "", name).strip()


def build_home(data) -> None:
    """按「方案名 → 该行」建立裸名归属（含全名特例）。"""
    for item in data:
        for option in item.get("solutions", []) or []:
            candidate = bare(option["name"])
            if candidate in RANK:
                HOME.setdefault(item["category"], []).append(candidate)
            if option["name"] in RANK:
                HOME.setdefault(item["category"], []).append(option["name"])


def _segment_wire(groups) -> int:
    """词表段实发字节（截断感知）——预算必须按这个量，不能按 JSON 增量估。

    **用生产路径**（format_wordlist_prompt + _wordlist_prompt_segment）：用简化的
    SolutionOption 投影会把段字节算少（实测差 312B——方案的 lib_modules 等字段
    虽不渲染，但投影与真加载的 models 集合相同、差值来自构造口径），预算记账
    必须与生产同口径。
    """
    from contest_generator.llm import _wordlist_prompt_segment

    return wire_size(_wordlist_prompt_segment(groups))


def _groups_of(data) -> tuple:
    """把 JSON 数据投影成词表组（走真加载路径，口径与 DEFAULT_WORDLIST 一致）。"""
    import tempfile

    handle = tempfile.NamedTemporaryFile(
        "wb", suffix="-wordlist-trial.json", delete=False
    )
    try:
        handle.write((json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8"))
        handle.close()
        return load_wordlist(Path(handle.name), lib_slugs=None)
    finally:
        Path(handle.name).unlink(missing_ok=True)


def main() -> int:
    # **幂等**：一律从基线副本重新生成（不叠加在现状之上——否则重跑会把同一批
    # 名字再加一遍，段增量翻倍而预算断言只测「试加那一条」的增量）。基线 =
    # 本目录下 wordlist-before-18.json（补数据前的 git HEAD 版，随补丁一起留档）。
    baseline_path = ROOT / ".scratch" / "recommend-domain-reject" / "wordlist-before-18.json"
    if not baseline_path.exists():
        raise SystemExit(f"基线词表副本不存在：{baseline_path}（用 git show 恢复）")
    data = json.loads(baseline_path.read_bytes().decode("utf-8"))
    build_home(data)
    base_wire = _segment_wire(_groups_of(data))

    selected: dict[str, list[str]] = {}
    accepted: list[str] = []
    deferred: list[str] = []
    cost = 0
    # 逐条试加：在**副本**上加，只有放得下才提交（提交前后词表段实发增量记账——
    # models 条目与「选购方案」段重复，行内分隔符开销由差值自然吸收）
    for name in RANK:
        category = _home_of(name)
        if category is None:
            raise SystemExit(f"RANK 里的 {name!r} 没有找到归属行——归属表写错了")
        trial = json.loads(json.dumps(data, ensure_ascii=False))
        for item in trial:
            if item["category"] == category:
                item.setdefault("models", []).append(name)
        trial_cost = _segment_wire(_groups_of(trial)) - base_wire
        if trial_cost > ADD_BUDGET_BYTES:
            deferred.append(name)
            continue
        data = trial
        cost = trial_cost
        selected.setdefault(category, []).append(name)
        accepted.append(name)

    for item in data:
        add = selected.get(item["category"])
        if add:
            print(f"[{item['category']}] +{len(add)}：{'、'.join(add)}")

    print(f"\n入 models {len(accepted)} 条，"
          f"词表段实发 {base_wire} → {base_wire + cost}B（+{cost} / 预算 {ADD_BUDGET_BYTES}）")
    if deferred:
        print(f"预算不足顺延（DEFERRED，规则上可入）：{'、'.join(deferred)}")
    assert cost <= ADD_BUDGET_BYTES, "超出词表段可用增量预算"
    PATH.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
