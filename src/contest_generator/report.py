"""提炼报告模型：判定条目与动作词表（schema 的唯一所有者）。

FileDecision 同时出现在三条路径上——AI 判定输出（llm 解析）、确定性规则
拼装（master 拼装报告）、确认请求回传（webapp 往返）——因此它的形状、
序列化与"merge 必须带整合产物全文与整合说明"不变量在这里只定义一次：
llm 层只负责 AI JSON 契约（提示词 + decisions 数组解析），master 层只负责
对比语义校验（路径范围 / 来源工程），形状校验都落到 FileDecision.from_dict。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ReportError(ValueError):
    """报告条目 / 报告形状非法，message 说明具体问题。"""


ACTION_KEEP = "keep"  # 保留：通用且基础建设必需
ACTION_MERGE = "merge"  # 整合：同路径多份内容不同，AI 读多份产出通用版本
ACTION_EXCLUDE = "exclude"  # 剔除：不通用 / 残留

# 判定动作词表：llm 提示词与 master 拼装共用，各自硬编码会静默漂移
DISTILL_ACTIONS = (ACTION_KEEP, ACTION_MERGE, ACTION_EXCLUDE)


@dataclass(frozen=True)
class FileDecision:
    """母版提炼时单个文件的判定：保留 / 整合（AI 产出通用版本）/ 剔除。

    merge 携带整合产物全文（content）与整合说明（explanation），选一份只是
    特例——可附 source 说明选了哪份，但落盘一律写 content。只覆盖需要判定
    的路径（同路径不同内容 + 独有文件）；所有工程内容一致的公共文件由
    master.compare_projects 确定性保留，不交给 AI。
    """

    path: str  # 相对工程目录的路径（与扫描清单同一套词表）
    action: str  # ACTION_KEEP / ACTION_MERGE / ACTION_EXCLUDE
    content: str = ""  # merge 时 AI 整合出的通用版本全文（其余动作必须为空）
    explanation: str = ""  # merge 时的整合说明（选一份时说明为何选它）
    source: str = ""  # merge 选一份特例时的来源工程名（其余动作必须为空）
    reason: str = ""  # AI 的中文理由（残留 / 模板替代条目为规则化原因）

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容 dict（确认请求按同一形状回传）。"""
        return {
            "path": self.path,
            "action": self.action,
            "content": self.content,
            "explanation": self.explanation,
            "source": self.source,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileDecision":
        """从 JSON 重建单个判定（形状校验唯一实现，AI 解析与确认报告共用）。

        任何结构 / 内容问题（非对象、缺 path、action 非法、merge 缺整合产物或
        整合说明、非 merge 带 content/explanation/source）都抛 ReportError——
        AI 输出与确认报告同样不可信，宁可大声失败也不要带病进入落盘流程。
        来源工程名是否真实含该文件由 master 层校验。
        """
        if not isinstance(data, dict):
            raise ReportError("判定条目必须是对象")
        path = data.get("path")
        if not isinstance(path, str) or not path:
            raise ReportError("判定条目缺少必填字段：path")
        action = data.get("action")
        if action not in DISTILL_ACTIONS:
            raise ReportError(f"判定条目的 action 非法：{action!r}")
        reason = data.get("reason", "")
        if not isinstance(reason, str):
            raise ReportError("判定条目的 reason 必须是字符串")
        content = data.get("content", "")
        explanation = data.get("explanation", "")
        source = data.get("source", "")
        if not isinstance(content, str):
            raise ReportError("判定条目的 content 必须是字符串")
        if not isinstance(explanation, str):
            raise ReportError("判定条目的 explanation 必须是字符串")
        if not isinstance(source, str):
            raise ReportError("判定条目的 source 必须是字符串")
        if action == ACTION_MERGE:
            if not content.strip():
                raise ReportError(
                    f"判定条目 {path!r} 的 merge 必须指定 content（整合产物全文）"
                )
            if not explanation.strip():
                raise ReportError(
                    f"判定条目 {path!r} 的 merge 必须指定 explanation（整合说明）"
                )
        elif content or explanation or source:
            raise ReportError(
                f"判定条目 {path!r} 只有 merge 才能带 content / explanation / source"
            )
        return cls(
            path=path,
            action=action,
            content=content,
            explanation=explanation,
            source=source,
            reason=reason,
        )
