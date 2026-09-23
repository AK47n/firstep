"""「资料 → 事实草稿」的域层（工单 hwcheck-unknown-device/07）。

学生贴一段资料（卖家页文字 / 手册抽取文本 / 模块照片的视觉描述），模型做**一次**
机械抽取：把关键事实填进一份严格形状的草稿。本模块拥有草稿的**形状与校验**——
模型输出不可信，宁可大声失败重问，也不让一个编出来的地址被填进表单。

## 三条硬边界（spec「资料 → 事实草稿」）

* **草稿一律不落盘生效**：本模块没有任何写盘函数；草稿只变成页面表单的预填，
  用户逐字段确认/修改后走**既有的保存路径**（`my_devices.save_device`，那里才是
  校验与落盘的判据本体）。
* **每条有值的事实必须带原文出处片段**，且片段必须是**资料原文里真实存在**的
  一段（归一化后子串匹配）——这是"绝不编造"的机械判据：模型引了一段资料里
  没有的话，`DeviceDraftFactError` 当场拒收（域拒绝，LLM 层带理由重问一次，
  仍不行端点降级为纯手填）。
* **AI 不写代码、不生成判据、不决定探测动作**：本模块的 import 面不含任何
  渲染 / 生成侧模块（`tests/test_my_device_draft.py` 有结构守卫）——探测程序
  永远由确认后的定义走确定性渲染。

## 与 `my_devices` 的分工

字段区间与词表**复用** `my_devices` 的常量（7 位地址区间 / 总线词表 / 长度上限）
——草稿在抽的时候就按"能存进定义"的标准挡一遍，等用户确认时再炸是浪费一趟。
但草稿**不是** `CustomDevice`：它没有 id（id 由用户起，页面从名称派生建议），
也没有 created_at 这类落盘事实——那是确认之后的事。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .hwcheck_errors import HwCheckError
from .my_devices import (
    ADDRESS7_MAX,
    ADDRESS7_MIN,
    BUS_VOCABULARY,
    NAME_MAX_CHARS,
    NOTES_MAX_CHARS,
)

__all__ = [
    "DRAFT_FIELDS",
    "MISSING_TEXT",
    "SOURCE_MAX_CHARS",
    "DeviceDraft",
    "DeviceDraftError",
    "DeviceDraftFactError",
    "draft_payload",
    "empty_draft",
    "parse_device_draft",
]


class DeviceDraftError(HwCheckError):
    """草稿形状 / 数值不合法（LLM 层转解析类重问；端点映射 400 中文）。

    与 `DeviceDraftFactError` 分开一个子类，是为了让"模型没按契约输出"（形状、
    区间、词表——参数性问题，快重试可能修好）与"模型编造了出处"（本地域判决：
    输出与给定资料的事实矛盾——带被拒理由重问一次）分道，照
    `hwcheck_triage` 的两类拒绝先例。
    """


class DeviceDraftFactError(DeviceDraftError):
    """出处片段不在资料原文里 = 编造（域拒绝，带理由重问一次）。"""


# 草稿字段白名单（= 自建件定义的六个事实字段；id 由用户起，不在抽取范围）
DRAFT_FIELDS = ("name", "bus", "address", "register", "expect", "notes")

# 抽不到的那句话（文案单源：前端照渲染，不自己编第二句）
MISSING_TEXT = "手册里没找到"

# 出处片段长度上限：出处是"页面上能对上原文的一句话"，不是资料的复读——
# 模型把整段资料当出处贴回来既没用也挤爆 UI。
SOURCE_MAX_CHARS = 300

_FIELD_LABELS = {
    "name": "名称",
    "bus": "总线",
    "address": "地址",
    "register": "身份寄存器",
    "expect": "期望值",
    "notes": "备注",
}

_WS_RE = re.compile(r"\s+")
_INT_RE = re.compile(r"^(0[xX][0-9A-Fa-f]+|\d+)$")


@dataclass(frozen=True)
class DeviceDraftField:
    """一个字段的抽取结果：值（归一后的表单显示形态）+ 原文出处片段。

    `found=False` = 资料里没找到（value / source 都是空串——**不编**默认值）。
    """

    value: str = ""
    source: str = ""
    found: bool = False


@dataclass(frozen=True)
class DeviceDraft:
    """一次抽取的草稿：六字段各一份结果（校验在 `parse_device_draft`）。"""

    fields: Mapping[str, DeviceDraftField]

    def field(self, key: str) -> DeviceDraftField:
        return self.fields[key]


def empty_draft() -> DeviceDraft:
    """全字段未抽取的空草稿（AI 不可用 / FakeLLM 缺省 = 纯手填的起点）。"""
    return DeviceDraft(fields={key: DeviceDraftField() for key in DRAFT_FIELDS})


def parse_device_draft(raw: object, material_text: str) -> DeviceDraft:
    """模型输出的原始 JSON（llm 已解析为 dict）→ 校验归一为 DeviceDraft。

    三类拒收：字段白名单外的（多一个 / 少一个都是拒——模型必须显式给
    `{"value": null, "source": ""}` 表示"没找到"）；数值 / 词表不合法的；
    出处片段不在原文里的（编造，域拒绝）。全部中文点名是哪个字段为什么。
    """
    if not isinstance(raw, Mapping):
        raise DeviceDraftError(
            "草稿必须是一个 JSON 对象（六个字段各一个 {value, source}）——"
            f"这回拿到的是 {type(raw).__name__}"
        )
    unknown = sorted(set(map(str, raw)) - set(DRAFT_FIELDS))
    if unknown:
        raise DeviceDraftError(
            "草稿里出现了白名单之外的字段：" + "、".join(unknown)
            + f"（只允许：{'、'.join(DRAFT_FIELDS)}）——不要自己发明字段"
        )
    missing = [key for key in DRAFT_FIELDS if key not in raw]
    if missing:
        raise DeviceDraftError(
            "草稿缺字段：" + "、".join(missing)
            + "——资料里没找到也要给 {\"value\": null, \"source\": \"\"}，不许省略"
        )
    fields: dict[str, DeviceDraftField] = {}
    for key in DRAFT_FIELDS:
        fields[key] = _parse_field(key, raw[key], material_text)
    return DeviceDraft(fields=fields)


def draft_payload(draft: DeviceDraft) -> dict[str, Any]:
    """页面载荷：六字段各 {value, source, found} + 没找到的清单与那句话。"""
    missing = [key for key in DRAFT_FIELDS if not draft.field(key).found]
    return {
        "fields": {
            key: {
                "value": draft.field(key).value,
                "source": draft.field(key).source,
                "found": draft.field(key).found,
            }
            for key in DRAFT_FIELDS
        },
        "missing": missing,
        "missing_text": MISSING_TEXT,
    }


# ---------------------------------------------------------------------------
# 内部：字段级校验（判据都在这里，上面只负责编排）
# ---------------------------------------------------------------------------


def _parse_field(key: str, raw_field: object, material_text: str) -> DeviceDraftField:
    label = _FIELD_LABELS[key]
    if not isinstance(raw_field, Mapping) or set(raw_field) - {"value", "source"}:
        raise DeviceDraftError(
            f"{label}（{key}）必须是 {{\"value\": …, \"source\": …}} 两个键——"
            f"这回拿到的是 {type(raw_field).__name__}"
        )
    source = raw_field.get("source")
    if source is None:
        source = ""
    if not isinstance(source, str):
        raise DeviceDraftError(f"{label}的出处片段必须是字符串")
    source = source.strip()
    if len(source) > SOURCE_MAX_CHARS:
        raise DeviceDraftError(
            f"{label}的出处片段太长（{len(source)} 字符，上限 {SOURCE_MAX_CHARS}）——"
            "出处是原文里的一小段，不是资料的复读"
        )
    raw_value = raw_field.get("value")
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        # 没找到：value / source 都归空（模型给了出处却没给值 = 自相矛盾，也按没找到）
        return DeviceDraftField()
    value = _parse_value(key, raw_value, label)
    if not source:
        raise DeviceDraftError(
            f"{label}抽到了值（{value}）却没给原文出处片段——每条事实都要能对回"
            "资料原文，没有出处的值不予采信"
        )
    if _normalize(source) not in _normalize(material_text):
        raise DeviceDraftFactError(
            f"{label}的出处片段在资料原文里找不到：{source!r}——"
            "只准逐字引用给定资料里的内容，不许改写、不许编造"
        )
    return DeviceDraftField(value=value, source=source, found=True)


def _parse_value(key: str, raw_value: object, label: str) -> str:
    """字段值 → 归一的表单显示形态（数值统一 0xNN 十六进制）。"""
    if key == "name":
        if not isinstance(raw_value, str):
            raise DeviceDraftError(f"{label}必须是字符串")
        text = raw_value.strip()
        if not text:
            raise DeviceDraftError(f"{label}不能是空串（没找到就给 null）")
        if len(text) > NAME_MAX_CHARS:
            raise DeviceDraftError(
                f"{label}太长了（{len(text)} 字，上限 {NAME_MAX_CHARS} 字）"
            )
        return text
    if key == "bus":
        if not isinstance(raw_value, str) or raw_value.strip() not in BUS_VOCABULARY:
            raise DeviceDraftError(
                f"{label} {raw_value!r} 不在词表里（{'、'.join(BUS_VOCABULARY)}）"
                "——不确定就让用户手选「其它 / 不确定」"
            )
        return raw_value.strip()
    if key == "notes":
        if not isinstance(raw_value, str):
            raise DeviceDraftError(f"{label}必须是字符串")
        text = raw_value.strip()
        if len(text) > NOTES_MAX_CHARS:
            raise DeviceDraftError(
                f"{label}太长了（{len(text)} 字，上限 {NOTES_MAX_CHARS} 字）"
            )
        return text
    # address / register / expect：整数（十进制或 0x 十六进制写法都收），区间照定义层
    number = _parse_int(raw_value, label)
    limit = 1 << 8 if key in ("register", "expect") else 1 << 7
    low, high = (ADDRESS7_MIN, ADDRESS7_MAX) if key == "address" else (0, limit - 1)
    if not low <= number <= high:
        shown = f"0x{number:X}"
        if key == "address":
            raise DeviceDraftError(
                f"{label} {shown} 不是 7 位地址（合法区间 "
                f"0x{ADDRESS7_MIN:02X}–0x{ADDRESS7_MAX:02X}）——"
                "手册里常见的 8 位写法（0xD0 这种）要换算成 7 位再填"
            )
        raise DeviceDraftError(f"{label} {shown} 不是 8 位（0x00–0xFF）")
    return f"0x{number:02X}"


def _parse_int(raw_value: object, label: str) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, str)):
        raise DeviceDraftError(f"{label}必须是整数（0x 十六进制或十进制写法都行）")
    text = str(raw_value).strip()
    if not _INT_RE.fullmatch(text):
        raise DeviceDraftError(
            f"{label} {raw_value!r} 不是合法数值（0x 十六进制或十进制写法）"
        )
    return int(text, 0)


def _normalize(text: str) -> str:
    """出处比对的归一：去所有空白 + 小写——引用时多换行 / 大小写出入不算编造。"""
    return _WS_RE.sub("", text).lower()
