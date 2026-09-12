"""模块简介拆段（工单 module-intro-detail/01）：`manifest.description` → 四问讲解。

**为什么存在**：简介（`manifest.description`）是模块文案的**单源**——AI 摘要行、
缓存指纹、结构守卫、参考关联全吃它，所以不能为「讲给人听」再养第二个字段（两处
必然漂移）。但简介按 AI 判据书写时天然是「一句话讲完接口 + 接线 + 场景」的长句，
第一次遇到这个模块的学生读不下去。本模块把同一份简介**机械拆段**成固定四问的
顺序展示，不改写一个字、不新增字段：

  这是干什么的 → 怎么接线 → 怎么用（接口） → 什么时候用 → （其它说明）

判据是标点切句 + 词法分类，不判语义：切不出、分不类的句子一律归入末段，**零丢
信息**——原简介的句子多重集 = 四段的句子多重集（不丢句、不重复、不造内容）。段间
按四问固定顺序重排，故拼接字符串不等同原文（存量简介常把适用场景写在接线之前），
判据是句子多重集。前端只渲染 `[{label, text}]`，不持有任何规则。

改写简介时的书写顺序（四拍）见 `CONTEXT.md` 的「简介」行判据⑤——拆段质量取决于
简介是否按四拍写；没按四拍写的存量简介照样能拆，只是分段可能粗一些。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "IntroSection",
    "LABEL_OVERVIEW",
    "LABEL_WIRING",
    "LABEL_USAGE",
    "LABEL_SCENARIO",
    "LABEL_OTHER",
    "intro_sections",
    "split_sentences",
]

# 四问标题（顺序即展示顺序，前端不重排）：文案单源在本文件——
# tests/js 侧只断言这些字符串出现在弹窗 HTML 里，不各自定义变体。
LABEL_OVERVIEW = "这是干什么的"
LABEL_WIRING = "怎么接线"
LABEL_USAGE = "怎么用（接口）"
LABEL_SCENARIO = "什么时候用"
LABEL_OTHER = "其它说明"

# 切句标点：中文句号 / 分号 / 叹号 / 问号 / 换行 + 英文分号。
# **英文句点不切**——简介里 `HX711_GAP_VALUE`、`pin_config.h`、`1.0` 这类
# 标识符与小数会被切坏（切坏了就是丢信息，不是排版问题）。
_SENTENCE_DELIM = re.compile(r"[。；！？\n\r;]+")

# 段落标记（简介可用空行分段）：切句时保护，避免把作者分好的段当作一次切割。
_PARAGRAPH_MARK = "\x00"

# —— 分类判据（词法，不判语义；顺序 = 优先级，先命中先归类）——
# 接口类最强：出现 C 函数调用形态 / 返回 / 电平极性，说明怎么用。
_USAGE_CALL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\s*\(")
_USAGE_WORDS = (
    "返回", "输出高", "输出低", "高电平", "低电平", "极性", "初始化",
    "接口", "默认上拉", "去抖", "超时",
)
# 接线类：线制 / 电源地 / 物理连接动作 / 引脚占用。
_WIRING_WORDS = (
    "三线制", "四线制", "两线制", "二线制", "五线制", "线制",
    "VCC", "GND", "SCL", "SDA",
    "接线", "接在", "接到", "接法", "供电", "占用", "引脚", "排针",
)
# 场景类：适用赛题功能（简介判据③「能力方向」的申报句）。**必须用强标记**
# （「用于」「适用」「常见于」这一类申报词）——弱词（检测 / 识别 / 显示 / 测量）
# 单独出现时是「这模块怎么干活」的实现细节（如「软 I2C 位操作读取」），拿它当段
# 判据会把几乎每句都塞进「什么时候用」（实测 93 个模块里 80 个），分段就废了。
_SCENARIO_MARKS = (
    "适用于", "可用于", "常用于", "用来", "常见于", "典型用法",
    "适合", "支持用于", "赛题功能",
)


@dataclass(frozen=True)
class IntroSection:
    """简介的一段讲解：`label` = 四问之一，`text` = 原简介里的句子（未改写）。"""

    label: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"label": self.label, "text": self.text}


def split_sentences(text: str) -> list[str]:
    """简介 → 句子列表（去首尾空白，无分隔符）。

    公开给测试与消费方对照口径用（与 `intro_sections` 同一套切割规则，避免测试
    自己写一份归一化把实现的合并行为掩盖掉）。零丢信息的不变量是对句子**多重集**
    成立（见 `intro_sections`）——不是拼接字符串逐字相等。
    """
    protected = re.sub(r"\n\s*\n", _PARAGRAPH_MARK, text)
    raw: list[str] = []
    for chunk in _SENTENCE_DELIM.split(protected):
        for piece in chunk.split(_PARAGRAPH_MARK):
            sentence = piece.strip()
            if sentence:
                raw.append(sentence)
    return raw


# 段内句子连接符 / 句尾悬空标点（重排后跨段两句本不相邻，需自己补标点）
_SENTENCE_JOIN = "。"
_TRAILING_PUNCT = "。；，、：！？,;:"


def _join_sentences(sentences: list[str]) -> str:
    """段内句子 → 展示文本：句尾悬空标点去掉，用句号连接（`a。b` 不是 `a；。b`）。"""
    return _SENTENCE_JOIN.join(s.rstrip(_TRAILING_PUNCT) for s in sentences)


def _classify(sentence: str, *, first: bool) -> str:
    """单句 → 段标题。`first` = 这是简介的第一句。

    优先级：**首句恒为「这是干什么的」** > 接口 > 接线 > 场景 > 其它说明。

    首句为什么强判：简介的第一句就是这东西的**定义槽**（存量简介普遍把「物理
    是什么 + 怎么用 + 接线」压在一句里，如 relay 那句含 `relay_set(`）——让词法
    覆盖它会把定义句判成「怎么用（接口）」，弹窗第一段标题就变成「怎么用」，
    等于把用户最想看的「这是什么」埋掉（实测 93 个模块里 57 个会这样）。
    首句之后才按词法分类：接口句里的函数调用是最强信号，用户也最关心。
    """
    if first:
        return LABEL_OVERVIEW
    if _USAGE_CALL.search(sentence) or any(word in sentence for word in _USAGE_WORDS):
        return LABEL_USAGE
    if any(word in sentence for word in _WIRING_WORDS):
        return LABEL_WIRING
    if any(mark in sentence for mark in _SCENARIO_MARKS):
        return LABEL_SCENARIO
    return LABEL_OTHER


# 展示顺序（其它说明固定垫底——它是兜底段，不参与四问排序）
_LABEL_ORDER = (LABEL_OVERVIEW, LABEL_WIRING, LABEL_USAGE, LABEL_SCENARIO, LABEL_OTHER)


def intro_sections(description: str) -> tuple[IntroSection, ...]:
    """模块简介 → 四问分段（有序、同类合并、零丢句）。

    空简介 / 全空白 → 空元组（调用方回落原样简介或整段不渲染）。同级句子按原
    顺序合并成一段（同标题只出一段，前端标题不重复）。

    **零丢信息不变量**：原简介切出的句子多重集 = 各段切出的句子多重集（去空白与
    标点后逐句相等）——不丢句、不重复、不造内容。段间重排会改变句序，也会让原本
    不相邻的两句直接相邻，故判据是句子多重集而非拼接字符串逐字相等。
    """
    sentences = split_sentences(description or "")
    if not sentences:
        return ()
    buckets: dict[str, list[str]] = {}
    for index, sentence in enumerate(sentences):
        label = _classify(sentence, first=index == 0)
        buckets.setdefault(label, []).append(sentence)
    return tuple(
        IntroSection(label=label, text=_join_sentences(buckets[label]))
        for label in _LABEL_ORDER
        if buckets.get(label)
    )