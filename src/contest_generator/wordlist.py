"""硬件词表：电赛常见硬件名的两条目型清单（类别 / 具体型号）。

用途（工单 10）：
- 库外建议 name 的校验源——词表内条目（型号或类别）→ 显示；词表外型号 →
  降级为类别（模型给出词表内类别名时）或拒收（LLMError，宁可大声失败也不
  让编造的型号进展示）；
- 选模块提示词的科普素材（类别行 + 常见型号，模型凭它联想"视觉模块 →
  K230 / OpenMV"这类常识举例）。

买件指引（工单 buy-guide/01）：词表行可挂 solutions 选购方案；方案通过
lib_modules 声明「库内已有对应模块」（slug 列表）——加载时机械校验引用
必须命中源码树模块库（仓库根 library/modules），「库内已有」永不指向已
删除/改名的模块（工单 wordlist-lib-modules/01）。

可手补：直接编辑 wordlist.json 增删条目组（category + models），重启后生效
（DeepSeekLLM 构造时读盘）。词表是"不懂不要编造"的硬边界，不是品类铁律——
功能需求层仍只由题面证据推导（ADR 0007）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .tool_root import find_tool_root

WORDLIST_PATH = Path(__file__).parent / "wordlist.json"

# 源码树模块库（与词表同仓同 commit 分发）：词表引用校验的锚点。仓库开发
# 环境存在 → 加载即校验；pip/无源码树部署不存在 → 跳过（None = 不校验）。
# 工具根判定单源（工单 full-download/09）：此前按 parents[2] 推，源码直跑
# （PYTHONPATH=src）时会算成 <根>/src/library/modules 而校验静默失效。
_SOURCE_MODULES_DIR = find_tool_root(__file__) / "library" / "modules"


class WordlistError(ValueError):
    """词表文件缺失、损坏或条目形状非法。"""


def source_module_slugs() -> frozenset[str] | None:
    """源码树模块库的 slug 集（library/modules 子目录名）；不存在 = None。

    词表「库内已有」的语义锚 = 工具随附模块库（同仓同 commit），非运行时
    用户库根（运行库根可配置、测试临时库场景锚它必炸）。
    """
    if not _SOURCE_MODULES_DIR.is_dir():
        return None
    return frozenset(entry.name for entry in _SOURCE_MODULES_DIR.iterdir() if entry.is_dir())


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
    lib_modules: tuple[str, ...] = ()  # 库内已有对应模块 slug（加载时机械校验存在性）

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "interface": self.interface,
            "price": self.price,
            "note": self.note,
            "suitable": self.suitable,
            "recommended": self.recommended,
            "lib_modules": list(self.lib_modules),
        }


@dataclass(frozen=True)
class HardwareWordGroup:
    """词表条目组：一个类别名 + 该类别的常见具体型号（两条目型的载体）。

    category 与 models 都是 name 的合法取值——解析器先按类别命中、再按型号
    命中；都不命中时走降级（模型给出词表内类别名）或拒收。

    solutions = 该类别/型号的选购方案（买件指引）；旧词表无该键 = 空（向后
    兼容，展示回退旧样式）。solutions 挂类别级（词表行级），型号级不单独
    定义方案——降级到类别名展示时同样有方案可看。

    **口径（工单 real-acceptance/08，硬约定）：solutions 是界面导览文本
    （价格 / 接线 / 适用场景，给人看的），`models` 才是 name 的唯一合法域。**
    所以**给一行加/改方案时，若该方案的裸名（去括号后的前半句）是电赛真会买的
    硬件（能写进采购单的名词短语），必须同时把它登记进同一行的 `models`**——
    `format_wordlist_prompt` 会把方案名摆在模型眼前，只加 solutions 不加 models
    就是「提示词给什么看、闸就不认什么」，模型照抄方案名即被拒收
    （2022C 曾连续三轮挂在这上面）。判据与逐条裁定见该工单「修复方向 2 裁定规则」：
    入 = 可采购件名；不入 = 平台/主控本身、上位概念、句子或组合描述、与既有条目重复。
    """

    category: str
    models: tuple[str, ...]
    solutions: tuple[SolutionOption, ...] = ()


def load_wordlist(
    path: Path = WORDLIST_PATH,
    lib_slugs: frozenset[str] | None = None,
) -> tuple[HardwareWordGroup, ...]:
    """读盘加载词表（形状校验：JSON 数组，每项 category 非空字符串 +
    models 为字符串数组；缺省 models 视为空）。畸形 = 大声失败。

    lib_slugs = 词表 lib_modules 引用校验的已知 slug 集；None = 默认用源码树
    模块库（仓库根 library/modules 存在时校验，不存在 = 跳过——pip 部署无
    源码库）。引用不存在的 slug → WordlistError（词表是手补的确定性知识，
    「库内已有」宁缺毋编：写错立即暴露，不让错误标注上车）。
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

    if lib_slugs is None:
        lib_slugs = source_module_slugs()

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
        if lib_slugs is not None:
            _check_lib_modules(solutions, index, path, lib_slugs)
        groups.append(
            HardwareWordGroup(
                category=item["category"],
                models=tuple(models),
                solutions=solutions,
            )
        )
    return tuple(groups)


def _check_lib_modules(
    solutions: Sequence[SolutionOption],
    group_index: int,
    path: Path,
    lib_slugs: frozenset[str],
) -> None:
    """机械校验：方案的 lib_modules 引用必须命中已知 slug 集（否则大声失败）。"""
    for s_index, solution in enumerate(solutions):
        for slug in solution.lib_modules:
            if slug not in lib_slugs:
                raise WordlistError(
                    f"硬件词表[{group_index}] solutions[{s_index}] 的 lib_modules "
                    f"引用了库中不存在的模块 slug {slug!r}：{path}"
                )


def _parse_solutions(
    raw: Any, group_index: int, path: Path
) -> tuple[SolutionOption, ...]:
    """解析词表行的 solutions 数组（买件指引）；缺省 = 空（旧词表兼容）。

    形状非法 / 缺 name / recommended 非 bool / lib_modules 形状非法 →
    WordlistError 大声失败（词表是可手补的确定性知识，宁缺毋编：手补时写错
    立即暴露，不让错误的方案上车。price/interface/note/suitable 可空串——
    只显示，无硬约束）。
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
        lib_modules = _parse_lib_modules(item.get("lib_modules", ()), group_index, s_index, path)
        solutions.append(
            SolutionOption(
                name=item["name"],
                interface=_optional_str(item.get("interface")),
                price=_optional_str(item.get("price")),
                note=_optional_str(item.get("note")),
                suitable=_optional_str(item.get("suitable")),
                recommended=recommended,
                lib_modules=lib_modules,
            )
        )
    return tuple(solutions)


def _parse_lib_modules(
    raw: Any, group_index: int, s_index: int, path: Path
) -> tuple[str, ...]:
    """解析方案的 lib_modules（库内模块 slug 列表）；缺失 = 空（旧词表兼容）。

    非数组 / 元素非非空字符串 → WordlistError（形状硬约束，与 recommended 同
    严格度——slug 是机械校验的引用键，写错必须立即暴露）。
    """
    if raw in (None, [], (), ""):
        return ()
    if not isinstance(raw, list):
        raise WordlistError(
            f"硬件词表[{group_index}] solutions[{s_index}] 的 lib_modules "
            f"必须是数组：{path}"
        )
    for index, slug in enumerate(raw):
        if not isinstance(slug, str) or not slug:
            raise WordlistError(
                f"硬件词表[{group_index}] solutions[{s_index}] 的 "
                f"lib_modules 的元素必须是非空字符串（第 {index} 个）：{path}"
            )
    return tuple(raw)


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
