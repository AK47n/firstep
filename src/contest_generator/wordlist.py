"""硬件词表：电赛常见硬件名的两条目型清单（类别 / 具体型号）。

用途（工单 10）：
- 库外建议 name 的校验源——词表内条目（型号或类别）→ 显示；词表外型号 →
  降级为类别（模型给出词表内类别名时）或拒收（LLMError，宁可大声失败也不
  让编造的型号进展示）；
- 选模块提示词的科普素材（类别行 + 常见型号，模型凭它联想"视觉模块 →
  K230 / OpenMV"这类常识举例）。

可手补：直接编辑 wordlist.json 增删条目组（category + models），重启后生效
（DeepSeekLLM 构造时读盘）。词表是"不懂不要编造"的硬边界，不是品类铁律——
功能需求层仍只由题面证据推导（ADR 0007）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

WORDLIST_PATH = Path(__file__).parent / "wordlist.json"


class WordlistError(ValueError):
    """词表文件缺失、损坏或条目形状非法。"""


@dataclass(frozen=True)
class SolutionOption:
    """库外建议的一个可选方案（买件指引，工单 buy-guide/01）。

    全部字段为确定性知识（词表手补），LLM 不编造方案文本——只允许从
    solutions.name 里选一个作 selected（AI 建议高亮）。
    """

    name: str
    interface: str = ""  # 接口与实现难度一句话（如 "GPIO 中断 + NEC 解码"）
    price: str = ""  # 参考价档，文字区间（如 "￥2-5/套"）——不写精确数字
    note: str = ""  # 关键注意点（接线/供电/协议）
    suitable: str = ""  # 适用场景
    recommended: bool = False  # 词表知识定的推荐（每类至多 2 个）

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "interface": self.interface,
            "price": self.price,
            "note": self.note,
            "suitable": self.suitable,
            "recommended": self.recommended,
        }


@dataclass(frozen=True)
class HardwareWordGroup:
    """词表条目组：一个类别名 + 该类别的常见具体型号（两条目型的载体）。

    category 与 models 都是 name 的合法取值——解析器先按类别命中、再按型号
    命中；都不命中时走降级（模型给出词表内类别名）或拒收。

    solutions = 该类别/型号的选购方案（买件指引）；旧词表无该键 = 空（向后
    兼容，展示回退旧样式）。solutions 挂类别级（词表行级），型号级不单独
    定义方案——降级到类别名展示时同样有方案可看。
    """

    category: str
    models: tuple[str, ...]
    solutions: tuple[SolutionOption, ...] = ()


def load_wordlist(path: Path = WORDLIST_PATH) -> tuple[HardwareWordGroup, ...]:
    """读盘加载词表（形状校验：JSON 数组，每项 category 非空字符串 +
    models 为字符串数组；缺省 models 视为空）。畸形 = 大声失败。
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise WordlistError(f"硬件词表文件不存在：{path}") from None
    except OSError as exc:
        raise WordlistError(f"无法读取硬件词表 {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise WordlistError(f"硬件词表不是合法 JSON：{path}: {exc}") from exc
    if not isinstance(data, list):
        raise WordlistError(f"硬件词表必须是 JSON 数组：{path}")

    groups: list[HardwareWordGroup] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict) or not isinstance(item.get("category"), str) \
                or not item["category"]:
            raise WordlistError(f"硬件词表[{index}] 缺 category 或为空：{path}")
        models = item.get("models", [])
        if not isinstance(models, list) or not all(
            isinstance(model, str) and model for model in models
        ):
            raise WordlistError(f"硬件词表[{index}] 的 models 必须是字符串数组：{path}")
        solutions = _parse_solutions(item.get("solutions", ()), index, path)
        groups.append(
            HardwareWordGroup(
                category=item["category"],
                models=tuple(models),
                solutions=solutions,
            )
        )
    return tuple(groups)


def _parse_solutions(
    raw: Any, group_index: int, path: Path
) -> tuple[SolutionOption, ...]:
    """解析词表行的 solutions 数组（买件指引）；缺省 = 空（旧词表兼容）。

    形状非法 / 缺 name / recommended 非 bool → WordlistError 大声失败
    （词表是可手补的确定性知识，宁缺毋编：手补时写错立即暴露，不让错误的
    方案上车。price/interface/note/suitable 可空串——只显示，无硬约束）。
    """
    solutions: list[SolutionOption] = []
    if raw in (None, [], (), ""):
        return ()
    if not isinstance(raw, list):
        raise WordlistError(f"硬件词表[{group_index}] 的 solutions 必须是数组：{path}")
    for s_index, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) \
                or not item["name"]:
            raise WordlistError(
                f"硬件词表[{group_index}] solutions[{s_index}] 缺 name 或为空：{path}"
            )
        recommended = item.get("recommended", False)
        if not isinstance(recommended, bool):
            raise WordlistError(
                f"硬件词表[{group_index}] solutions[{s_index}] 的 "
                f"recommended 必须是布尔：{path}"
            )
        solutions.append(
            SolutionOption(
                name=item["name"],
                interface=_optional_str(item.get("interface")),
                price=_optional_str(item.get("price")),
                note=_optional_str(item.get("note")),
                suitable=_optional_str(item.get("suitable")),
                recommended=recommended,
            )
        )
    return tuple(solutions)


def _optional_str(value: Any) -> str:
    """可空字符串字段：None/缺失 → 空串；非字符串 → 空串（宽松不阻断）。"""
    return value if isinstance(value, str) else ""


def format_wordlist_prompt(groups: Sequence[HardwareWordGroup]) -> str:
    """选模块提示词的科普段：类别行 + 常见型号 + 选购方案名（紧凑形态）。

    模型读它联想库外建议的 name（类别名或型号名）与 examples（常识举例），
    并可从选购方案（solutions）里选 selected（AI 建议高亮，买件指引）。
    prompt 只列方案名与推荐标记（价格/接线/适用是界面展示数据，模型选型
    不需要——避免撑爆请求预算，最坏情形测试有预算守卫）。
    """
    lines = [
        "硬件词表（库外建议的 name 必须来自这里——类别名或具体型号名；"
        "具体型号不在词表内时，降级输出为它所属的类别名，并在 category 字段注明）："
    ]
    for group in groups:
        line = f"- {group.category}"
        if group.models:
            line += "：" + "、".join(group.models)
        if group.solutions:
            option_names = "; ".join(
                f"{option.name}{'（推荐）' if option.recommended else ''}"
                for option in group.solutions
            )
            line += f"｜选购方案：{option_names}"
        lines.append(line)
    return "\n".join(lines)


# 包内默认词表：随源码分发（可手补 wordlist.json），DeepSeekLLM 默认使用；
# 测试注入自定义词表时直接构造 HardwareWordGroup 或传自定义路径。
DEFAULT_WORDLIST: tuple[HardwareWordGroup, ...] = load_wordlist()


def category_names(groups: Sequence[HardwareWordGroup]) -> set[str]:
    """词表内全部类别名。"""
    return {group.category for group in groups}


def model_names(groups: Sequence[HardwareWordGroup]) -> set[str]:
    """词表内全部具体型号名（跨组收集）。"""
    return {model for group in groups for model in group.models}
