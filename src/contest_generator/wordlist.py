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
from typing import Sequence

WORDLIST_PATH = Path(__file__).parent / "wordlist.json"


class WordlistError(ValueError):
    """词表文件缺失、损坏或条目形状非法。"""


@dataclass(frozen=True)
class HardwareWordGroup:
    """词表条目组：一个类别名 + 该类别的常见具体型号（两条目型的载体）。

    category 与 models 都是 name 的合法取值——解析器先按类别命中、再按型号
    命中；都不命中时走降级（模型给出词表内类别名）或拒收。
    """

    category: str
    models: tuple[str, ...]


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
        groups.append(HardwareWordGroup(category=item["category"], models=tuple(models)))
    return tuple(groups)


def format_wordlist_prompt(groups: Sequence[HardwareWordGroup]) -> str:
    """选模块提示词的科普段：类别行 + 该类别常见型号（两条目型的可读形态）。

    模型读它联想库外建议的 name（类别名或型号名）与 examples（常识举例）。
    """
    lines = [
        "硬件词表（库外建议的 name 必须来自这里——类别名或具体型号名；"
        "具体型号不在词表内时，降级输出为它所属的类别名，并在 category 字段注明）："
    ]
    for group in groups:
        line = f"- {group.category}"
        if group.models:
            line += "：" + "、".join(group.models)
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
