"""LLM 客户端抽象与生产实现。

生产实现 DeepSeekLLM 走 DeepSeek Chat Completions API（base_url / api_key /
模型来自本机配置文件 config.py）；HTTP 传输可注入假件，网络调用不进测试。
LLM 承担三个职责：赛题→模块选择、main.c 骨架生成、模块简介生成与校验。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from .config import LLMConfig
from .manifest import ModuleManifest

SELECT_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手，熟悉 MSPM0G3507（CCS）与 "
    "STM32F103C8T6（Keil5）两条平台线。根据赛题在给定的模块库中选择合适的"
    "现成模块，为每个推荐给出简短理由（中文）。只输出 JSON 对象。"
)

SKELETON_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。为赛题生成 main.c 骨架：按模块初始化序列排好调用，"
    "只调用给定模块摘要中存在的接口，不确定的地方写成注释占位，保证可编译。"
)

SUMMARY_SYSTEM_PROMPT = "你是嵌入式 C 工程师。用中文一句话总结这段代码的功能，作为模块库简介。"


class LLMError(Exception):
    """LLM 调用或输出解析失败，message 说明具体问题。"""


@dataclass(frozen=True)
class ModuleSelection:
    """赛题 → 模块选择结果（AI 的原始推荐，未展开依赖）。

    依赖展开与生成前的增删由 selection.resolve_dependencies 在用户确认后
    统一处理——AI 输出后用户还可能增删，先展开的集合无法代表最终选择。
    """

    modules: tuple[str, ...]  # 模块 slug（AI 推荐顺序）
    reasons: dict[str, str]  # slug -> 推荐理由


class LLM(Protocol):
    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[str]
    ) -> ModuleSelection: ...

    def generate_main_skeleton(
        self, problem_text: str, module_summaries: Sequence[str]
    ) -> str: ...

    def summarize_module(self, code: str) -> str: ...


def build_manifest_summaries(manifests: Sequence[ModuleManifest]) -> list[str]:
    """模块库 manifest 摘要行（喂给 LLM 的可用模块清单）。

    行格式与 _summary_slugs 的反向解析耦合：改动格式须同步两处。
    """
    lines = []
    for manifest in manifests:
        line = f"- {manifest.slug}: {manifest.description}"
        if manifest.dependencies:
            line += f"（依赖: {', '.join(manifest.dependencies)}）"
        lines.append(line)
    return lines


class Transport(Protocol):
    """HTTP 传输接缝：生产用 urllib，测试注入假件。"""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> tuple[int, str]:
        """POST JSON，返回（HTTP 状态码, 响应体文本）。"""


class UrllibTransport:
    """基于标准库 urllib 的传输实现（项目零第三方依赖）。"""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> tuple[int, str]:
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            # 4xx/5xx 是业务失败，状态码透传给调用方转成 LLMError
            return exc.code, exc.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as exc:
            raise LLMError(f"无法连接 LLM 服务 {url}: {exc}") from exc


class DeepSeekLLM:
    """生产 LLM：调用 DeepSeek Chat Completions，结构化输出解析为 ModuleSelection。"""

    TIMEOUT_SECONDS = 120

    def __init__(self, config: LLMConfig, transport: Transport | None = None) -> None:
        self._config = config
        self._transport = transport or UrllibTransport()

    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[str]
    ) -> ModuleSelection:
        content = self._chat(
            [
                {"role": "system", "content": SELECT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _selection_user_prompt(problem_text, manifest_summaries),
                },
            ],
            json_mode=True,
        )
        return parse_module_selection(content, known_slugs=_summary_slugs(manifest_summaries))

    def generate_main_skeleton(
        self, problem_text: str, module_summaries: Sequence[str]
    ) -> str:
        user = _build_user_prompt(
            problem_text, "可选模块：", [f"- {summary}" for summary in module_summaries]
        )
        return self._chat(
            [
                {"role": "system", "content": SKELETON_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ]
        )

    def summarize_module(self, code: str) -> str:
        return self._chat(
            [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"```c\n{code}\n```"},
            ]
        )

    def _chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {"model": self._config.model, "messages": messages}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        url = self._config.base_url.rstrip("/") + "/chat/completions"
        status, body = self._transport.post(
            url,
            {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            payload,
            self.TIMEOUT_SECONDS,
        )
        if status != 200:
            raise LLMError(f"DeepSeek API 返回 {status}：{body[:200]}")
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMError(f"DeepSeek API 响应不是合法 JSON：{body[:200]}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"DeepSeek API 响应缺少 choices[0].message.content：{body[:200]}"
            ) from exc


def parse_module_selection(
    content: str, known_slugs: Sequence[str]
) -> ModuleSelection:
    """把模型返回的 JSON 文本解析校验为 ModuleSelection。

    任何结构 / 内容问题（非 JSON、缺模块数组、未知 slug、重复、字段类型错）
    都抛 LLMError——模型输出不可信，宁可大声失败也不要带病进入生成流程。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("modules"), list):
        raise LLMError("模型输出缺少 modules 数组")

    known = set(known_slugs)
    modules: list[str] = []
    reasons: dict[str, str] = {}
    for index, item in enumerate(data["modules"]):
        if not isinstance(item, dict):
            raise LLMError(f"modules[{index}] 必须是对象")
        slug = item.get("slug")
        if not isinstance(slug, str) or not slug:
            raise LLMError(f"modules[{index}] 缺 slug")
        if slug not in known:
            raise LLMError(f"模型推荐了库中不存在的模块：{slug}")
        if slug in modules:
            raise LLMError(f"模型重复推荐模块：{slug}")
        reason = item.get("reason", "")
        if not isinstance(reason, str):
            raise LLMError(f"模块 {slug} 的 reason 必须是字符串")
        modules.append(slug)
        reasons[slug] = reason
    return ModuleSelection(modules=tuple(modules), reasons=reasons)


def _build_user_prompt(problem_text: str, heading: str, items: Sequence[str]) -> str:
    """赛题 + 清单的 user 消息拼装（模块选择 / main.c 骨架共用）。"""
    lines = ["赛题：", problem_text, "", heading]
    lines.extend(items)
    return "\n".join(lines)


def _selection_user_prompt(problem_text: str, manifest_summaries: Sequence[str]) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    prompt = _build_user_prompt(problem_text, "模块库可用模块：", manifest_summaries)
    return prompt + '\n只返回 json 格式的 JSON 对象：{"modules": [{"slug": "...", "reason": "..."}]}'


def _summary_slugs(manifest_summaries: Sequence[str]) -> list[str]:
    """从摘要行提取 slug（行首 "- " 后的第一个冒号前）。"""
    slugs = []
    for line in manifest_summaries:
        if not line.startswith("- "):
            continue
        slug = line[2:].split(":", 1)[0].strip()
        if slug:
            slugs.append(slug)
    return slugs
