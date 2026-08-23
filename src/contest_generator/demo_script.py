"""随工程生成「演示脚本」—— 纯确定性渲染，零 LLM 调用。

工单 report-draft-demo/01：生成工程时自动附带 演示脚本.md。render_demo_script
是纯函数（评分点 / 功能需求清单（dict 形状直传）/ 依赖展开后的 manifest 集 →
完整演示脚本文本），数据全部来自 generate() 既有参数，零新增依赖。

结构：
- 头段：标题 + 生成方式声明 + 演示前准备（编译烧录 / 接线 / 自检，指向
  README 对应章节）；
- 评分点分区组织（有评分点时）：每评分点一小节——操作 / 预期现象 / 对应
  功能需求 / 对应模块；评分点与需求经题面句子编号桥接（score.sentence_refs
  ↔ requirement.sentence 同编号体系），桥接不上的需求独立成条进
  「补充功能需求演示」节，不丢弃（spec「数据不丢」精神：需求是演示条目
  输入，漏演即丢分）；
- 降级链：无评分点 = 功能需求驱动（每需求一小节）；两者皆无 = 模块清单验证
  演示项（模块兜底，不空文件）；
- 尾部：「演示注意事项」注明请按实物调整。

操作 / 预期现象 = 结构化模板文字（基于需求描述 + 命中模块能力方向——对应
模块行带 manifest 描述，spec 逐字规定）；评分点分区 / 分值 / 句子引用文案与
README 评分点验收清单同源（复用 readme 的 _score_part_label /
_score_value_text / _sentence_refs_text，spec「同包内共享」预告）。畸形需求
（缺 requirement 键 / sentence 非整数 / 编号非 1 起）防御性跳过。utf-8、尾部
换行、不含时间戳——同一输入两次调用产出逐字节一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .manifest import ModuleManifest
from .readme import _score_part_label, _sentence_refs_text, _score_value_text

if TYPE_CHECKING:
    from .selection import ScorePoint

# 演示脚本输出文件名（生成写侧单源，generator 消费）
DEMO_SCRIPT_FILENAME = "演示脚本.md"

# 固定引导语（spec 逐字规定）
_HEADER = """# 演示脚本

> 本脚本由生成器按评分点 / 功能需求 / 模块清单确定性渲染（不含 AI 生成内容），
> 请按实物接线与现场情况调整演示顺序与细节。

## 演示前准备

- 编译烧录：按 README.md「快速上手：编译 + 烧录」操作
- 硬件接线：按 README.md「引脚接线表」完成
- 模块自检：按 README.md「验证顺序清单」逐项验证
"""

_FOOTER = """## 演示注意事项

> 请按实物调整：本脚本由生成器自动产出，实际演示请以现场硬件与评委要求为准。
"""

# 未桥接文案（确定性话术，不编造）
_NO_REQUIREMENT = "未关联到具体需求"
_NO_MODULES = "未命中库内模块"


@dataclass(frozen=True)
class CleanRequirement:
    """畸形过滤后的需求条目（spec 桥接 + 文案渲染的最小形状）。"""

    requirement: str
    sentence: int  # 题面句子编号，1 起（与 score.sentence_refs 同编号体系）
    modules: tuple[str, ...]  # 库内命中 slug（保序）


def render_demo_script(
    score_points: Sequence[ScorePoint] | None = None,
    requirements: Sequence[Mapping[str, Any]] | None = None,
    manifests: Sequence[ModuleManifest] | None = None,
) -> str:
    """渲染演示脚本完整文本（确定性模板，零 LLM 调用）。

    score_points = 评分点（ScorePoint 序列，缺省 / 空 = 功能需求驱动）；
    requirements = 功能需求清单 dict 形状直传（generate() requirements 参数
    同形状：键 requirement / sentence / modules / suggestions）——渲染器只读
    前三键，畸形条目防御性跳过；
    manifests = 依赖展开后的 manifest 集（模块兜底模式清单 + 对应模块行带
    manifest 描述（能力方向），库外 slug 只显 slug）。

    评分点小节：`### {id} {description}（{分区} · {分值}）` + 操作（演示
    「描述」，refs 非空附「，对应句子 N、M」）/ 预期现象 / 对应功能需求
    （sentence ∈ refs 的需求，原序、`；` 分隔）/ 对应模块（关联需求 modules
    并集保序，`、` 分隔，slug 带 manifest 描述）。桥接不上的需求独立成条进
    补充节。返回文本恒以单个尾部换行收尾（幂等——同输入两次调用逐字节
    一致）。
    """
    points = tuple(score_points or ())
    reqs: list[CleanRequirement] = []
    for raw in requirements or ():
        cleaned = _clean_requirement(raw)
        if cleaned is not None:
            reqs.append(cleaned)
    manifests = tuple(manifests or ())

    lines: list[str] = [_HEADER.rstrip("\n")]
    if points:
        linked: set[int] = set()
        lines.append("")
        lines.append("## 评分点演示")
        for point in points:
            lines.append("")
            lines.append(_score_point_section(point, reqs, linked, manifests))
        extra = [req for req in reqs if id(req) not in linked]
        if extra:
            lines.append("")
            lines.append("## 补充功能需求演示")
            for req in extra:
                lines.append("")
                lines.append(_requirement_section(req, manifests))
    elif reqs:
        lines.append("")
        lines.append("## 功能需求演示")
        for req in reqs:
            lines.append("")
            lines.append(_requirement_section(req, manifests))
    else:
        lines.append("")
        lines.append("## 模块验证演示")
        for manifest in manifests:
            lines.append(f"- {manifest.slug}：{manifest.description}")
    lines.append("")
    lines.append(_FOOTER.rstrip("\n"))

    # 恒以单个尾部换行收尾（幂等）：rstrip 去尾部空行再补一个 \n
    return "\n".join(lines).rstrip("\n") + "\n"


def _clean_requirement(req: Mapping[str, Any]) -> CleanRequirement | None:
    """需求 dict → CleanRequirement；畸形（缺 requirement 键或非字符串 /
    sentence 非整数（含 bool，int 子类）/ 编号非 1 起）返回 None（防御性
    跳过，不阻断渲染）。"""
    requirement = req.get("requirement")
    if not isinstance(requirement, str) or not requirement:
        return None
    sentence = req.get("sentence")
    if not isinstance(sentence, int) or isinstance(sentence, bool) or sentence < 1:
        return None
    modules = req.get("modules")
    if not isinstance(modules, (list, tuple)):
        modules = ()
    slugs = tuple(slug for slug in modules if isinstance(slug, str))
    return CleanRequirement(requirement, sentence, slugs)


def _score_point_section(
    point: ScorePoint,
    reqs: Sequence[CleanRequirement],
    linked: set[int],
    manifests: Sequence[ModuleManifest],
) -> str:
    """单评分点小节（多行，`\n` 连接）。桥接 = 需求.sentence ∈ point.
    sentence_refs（同编号体系）；关联到的需求记入 linked（补充节排除）。
    对应模块 = 关联需求 modules 并集保序。"""
    related = [req for req in reqs if req.sentence in point.sentence_refs]
    linked.update(id(req) for req in related)

    lines = [
        f"### {point.id} {point.description}"
        f"（{_score_part_label(point.part)} · {_score_value_text(point.score)}）",
        "",
        _operation_line(point.description, point.sentence_refs),
        f"- 预期现象：「{point.description}」按题面要求呈现",
        "- 对应功能需求：" + _requirement_names(related),
        "- 对应模块：" + _module_names(related, manifests),
    ]
    return "\n".join(lines)


def _requirement_section(
    req: CleanRequirement, manifests: Sequence[ModuleManifest]
) -> str:
    """单需求小节（功能需求驱动 / 补充节共用）。"""
    title = (
        f"### {req.requirement}（句子 {req.sentence}）"
        if req.sentence
        else f"### {req.requirement}"
    )
    return "\n".join(
        [
            title,
            "",
            "- 对应模块：" + _module_names([req], manifests),
            f"- 操作：演示「{req.requirement}」",
            f"- 预期现象：「{req.requirement}」相关现象正常呈现",
        ]
    )


def _operation_line(description: str, refs: Sequence[int]) -> str:
    """操作行：refs 非空附「，对应句子 N、M」（文案与 README 同源）。"""
    if refs:
        return f"- 操作：演示「{description}」，对应{_sentence_refs_text(refs)}"
    return f"- 操作：演示「{description}」"


def _requirement_names(reqs: Sequence[CleanRequirement]) -> str:
    """对应功能需求列：`需求文本（句子 N）；…`；空 = 未关联话术。"""
    if not reqs:
        return _NO_REQUIREMENT
    return "；".join(
        f"{req.requirement}（句子 {req.sentence}）" for req in reqs
    )


def _module_names(
    reqs: Sequence[CleanRequirement], manifests: Sequence[ModuleManifest]
) -> str:
    """对应模块列：关联需求 modules 并集保序（需求序 × 需求内序），slug 带
    manifest 描述（能力方向，spec 逐字规定；库外 slug 只显 slug）；空 =
    未命中话术。"""
    descriptions = {m.slug: m.description for m in manifests}
    names: list[str] = []
    for req in reqs:
        for slug in req.modules:
            if slug in names:
                continue
            desc = descriptions.get(slug)
            names.append(f"{slug}（{desc}）" if desc else slug)
    return "、".join(names) if names else _NO_MODULES
