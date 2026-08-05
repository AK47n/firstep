"""LLM 客户端抽象。

生产实现（DeepSeek，base_url/key/模型可配置）在工单 04 落地；测试注入
固定返回的假实现（tests/conftest.py 的 FakeLLM）。LLM 承担三个职责：
赛题→模块选择、main.c 骨架生成、模块简介生成与校验。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ModuleSelection:
    """赛题 → 模块选择结果。"""

    modules: tuple[str, ...]  # 模块 slug，已按依赖递归展开
    reasons: dict[str, str]  # slug -> 推荐理由


class LLM(Protocol):
    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[str]
    ) -> ModuleSelection: ...

    def generate_main_skeleton(self, problem_text: str, module_summaries: Sequence[str]) -> str: ...

    def summarize_module(self, code: str) -> str: ...
