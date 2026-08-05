"""LLM 客户端抽象与生产实现。

生产实现 DeepSeekLLM 走 DeepSeek Chat Completions API（base_url / api_key /
模型来自本机配置文件 config.py）；HTTP 传输可注入假件，网络调用不进测试。
LLM 承担四个职责：赛题→模块选择、main.c 骨架生成、模块简介生成与校验、
母版提炼判定（冲突/独有文件 → 保留/合并/剔除；两阶段：先读全文出摘要，
再基于摘要判定）。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from .config import AppConfig
from .manifest import ModuleManifest
from .report import ACTION_MERGE, FileDecision, ReportError

SELECT_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手，熟悉 MSPM0G3507（CCS）与 "
    "STM32F103C8T6（Keil5）两条平台线。根据赛题在给定的模块库中选择合适的"
    "现成模块，为每个推荐给出简短理由（中文）。只输出 JSON 对象。"
)

SKELETON_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。为赛题生成 main.c 骨架：按所选模块的头文件接口排好初始化序列，"
    "带注释说明与预留编写区（TODO）。只调用给定接口中真实存在的函数，绝不凭空造函数；"
    "不确定的调用写成注释占位，保证骨架可编译。"
)

SUMMARY_SYSTEM_PROMPT = "你是嵌入式 C 工程师。用中文一句话总结这段代码的功能，作为模块库简介。"

VALIDATION_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。判断给定的模块简介与实际代码是否一致：简介描述的功能、"
    "接口、行为是否与代码相符。不一致时用中文指出具体差异。只输出 JSON 对象。"
)

JUDGMENT_SUMMARY_SYSTEM_PROMPT = (
    "你是嵌入式开发工程整理助手。导入的多个同平台旧工程里，有些文件需要判定"
    "去留：同一路径在不同工程里内容不同（冲突），或只出现在部分工程（独有）。"
    "逐文件读全文后，为每个内容版本用中文写一段简短摘要：说明它实现什么功能、"
    "是否通用、是否基础建设必需。只输出 JSON 对象。"
)

DISTILL_SYSTEM_PROMPT = (
    "你是嵌入式开发工程整理助手。用户导入了多个同平台旧工程，你需要根据文件"
    "内容摘要与结构配置对比判定哪些文件应该进母版（母版 = 空的最小系统板工程，"
    "能直接编译烧录）。判定唯一判据：读文件内容后判断它是否基础建设必需——"
    "官方外设库（STM32 标准外设库 / TI driverlib）、平台基础设施（启动 / system / "
    "CMSIS / 链接脚本 / 工程配置）、通用基础封装（如 delay 延时，写任何工程都"
    "要用）→ keep；具体项目 / 具体硬件相关的业务代码（传感器驱动、外设封装、"
    "赛题逻辑）→ exclude。不看重复次数与出现范围——公共文件（所有工程内容"
    "一致）同样逐个判定，可保留可剔除，内容一样不等于基础建设必需。动作词表："
    "keep（保留）/ merge（整合：同一路径多份内容不同时，读多份后整合出通用"
    "版本，选一份只是特例，必须给出整合产物全文与整合说明）/ exclude（剔除）。"
    "只输出 JSON 对象。"
)

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


@dataclass(frozen=True)
class ValidationResult:
    """模块简介与实际代码的一致性校验结果。"""

    consistent: bool  # 简介与代码是否一致
    issues: str = ""  # 不一致时 AI 指出的具体差异（一致时为空）


@dataclass(frozen=True)
class JudgmentFile:
    """待判文件素材：路径 + 每个内容版本及其持有工程（AI 判定前先读全文出摘要）。

    覆盖 master 判定范围（公共 + 冲突 + 独有，全部文件）。同一路径内容
    不同的每个版本都传（AI 读全部版本后判定）；内容一致的工程合并为一个版本。
    """

    path: str
    versions: tuple[FileVersion, ...]


@dataclass(frozen=True)
class FileVersion:
    """同一路径下的一个内容版本：全文 + 持该版本的工程名。"""

    content: str
    projects: tuple[str, ...]


@dataclass(frozen=True)
class VersionSummary:
    """第一阶段摘要产物：一个内容版本的摘要 + 持该版本的工程名。"""

    projects: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class FileSummary:
    """第一阶段摘要产物：一个待判文件各内容版本的摘要（第二阶段的判定素材）。"""

    path: str
    versions: tuple[VersionSummary, ...]


class LLM(Protocol):
    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[str]
    ) -> ModuleSelection: ...

    def generate_main_skeleton(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str: ...

    def summarize_module(self, code: str) -> str: ...

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult: ...

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
    ) -> tuple[FileDecision, ...]: ...


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

    def __init__(self, config: AppConfig, transport: Transport | None = None) -> None:
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
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str:
        return self._chat(
            [
                {"role": "system", "content": SKELETON_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _skeleton_user_prompt(problem_text, module_interfaces),
                },
            ]
        )

    def summarize_module(self, code: str) -> str:
        return self._chat(
            [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"```c\n{code}\n```"},
            ]
        )

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult:
        content = self._chat(
            [
                {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _validation_user_prompt(description, code),
                },
            ],
            json_mode=True,
        )
        return parse_validation_result(content)

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
    ) -> tuple[FileDecision, ...]:
        """两阶段判定：先逐文件读全文出摘要，再基于摘要判定（两次 json_mode 调用）。

        兑现 ADR 0001 的"读内容判断"——判定素材含文件内容摘要，不再只有路径
        与配置摘要。第一阶段产物（摘要）只作为第二阶段输入，不进报告；判定
        条目的 reason 由 AI 带上摘要要点。两阶段产物都走严格解析，畸形 / 缺
        摘要抛 LLMError，宁可大声失败也不带病进确认流程。
        """
        file_summaries = self._summarize_judgment_files(
            platform, project_names, judgment_files
        )
        content = self._chat(
            [
                {"role": "system", "content": DISTILL_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _distill_user_prompt(
                        platform, project_names, file_summaries, comparison_summary
                    ),
                },
            ],
            json_mode=True,
        )
        return parse_distillation_report(content, project_names)

    def _summarize_judgment_files(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
    ) -> tuple[FileSummary, ...]:
        """第一阶段：逐文件读全文出摘要（json_mode），解析校验为 FileSummary。"""
        content = self._chat(
            [
                {"role": "system", "content": JUDGMENT_SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _summarize_user_prompt(
                        platform, project_names, judgment_files
                    ),
                },
            ],
            json_mode=True,
        )
        return parse_summary_report(content, judgment_files)

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


def parse_distillation_report(
    content: str, project_names: Sequence[str]
) -> tuple[FileDecision, ...]:
    """把模型返回的提炼判定 JSON 文本解析校验为 FileDecision 列表。

    条目形状校验（action 词表、merge 必须带整合产物全文与说明等）委托
    report.FileDecision.from_dict——报告模型是唯一所有者；这里只做 AI 契约
    专属检查：JSON 外层、decisions 数组、来源工程必须在导入列表、路径不重复。
    任何问题都抛 LLMError——模型输出不可信，宁可大声失败也不要带病进入确认
    流程。路径与对比范围的完整性由 master.assemble_report 校验（llm 层
    不知道对比范围）。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("decisions"), list):
        raise LLMError("模型输出缺少 decisions 数组")

    names = set(project_names)
    decisions: list[FileDecision] = []
    seen: set[str] = set()
    for index, item in enumerate(data["decisions"]):
        if not isinstance(item, dict):
            raise LLMError(f"decisions[{index}] 必须是对象")
        try:
            decision = FileDecision.from_dict(item)
        except ReportError as exc:
            raise LLMError(f"decisions[{index}] {exc}") from exc
        if (
            decision.action == ACTION_MERGE
            and decision.source
            and decision.source not in names
        ):
            raise LLMError(
                f"decisions[{index}] 的来源工程不在导入列表中：{decision.source}"
            )
        if decision.path in seen:
            raise LLMError(f"模型重复判定文件：{decision.path}")
        seen.add(decision.path)
        decisions.append(decision)
    return tuple(decisions)


def parse_summary_report(
    content: str, judgment_files: Sequence[JudgmentFile]
) -> tuple[FileSummary, ...]:
    """把模型返回的第一阶段摘要 JSON 解析校验为 FileSummary 列表。

    任何结构 / 内容问题（非 JSON、缺 summaries、未知或重复路径、缺某个内容
    版本的摘要、摘要为空、版本工程名对不上）都抛 LLMError——摘要残缺会让
    第二阶段基于残缺素材判定，宁可大声失败也不要带病进第二阶段。版本按"持
    该版本的工程名"匹配发送的词表（内容一致的工程归一个版本，工程名是唯一
    不重不漏的分组键）。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("summaries"), list):
        raise LLMError("模型输出缺少 summaries 数组")

    expected: dict[str, tuple[frozenset[str], ...]] = {
        file.path: tuple(frozenset(v.projects) for v in file.versions)
        for file in judgment_files
    }
    seen_paths: set[str] = set()
    summaries: list[FileSummary] = []
    for index, item in enumerate(data["summaries"]):
        if not isinstance(item, dict):
            raise LLMError(f"summaries[{index}] 必须是对象")
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise LLMError(f"summaries[{index}] 缺 path")
        if path not in expected:
            raise LLMError(f"摘要里出现非待判文件：{path}")
        if path in seen_paths:
            raise LLMError(f"模型重复摘要文件：{path}")
        seen_paths.add(path)
        raw_versions = item.get("versions")
        if not isinstance(raw_versions, list):
            raise LLMError(f"{path} 的 versions 必须是列表")
        versions: list[VersionSummary] = []
        for v_index, version in enumerate(raw_versions):
            if not isinstance(version, dict):
                raise LLMError(f"{path} versions[{v_index}] 必须是对象")
            projects = version.get("projects")
            if not isinstance(projects, list) or not projects or not all(
                isinstance(p, str) and p for p in projects
            ):
                raise LLMError(f"{path} versions[{v_index}] 的 projects 非法")
            summary = version.get("summary")
            if not isinstance(summary, str) or not summary:
                raise LLMError(f"{path} versions[{v_index}] 缺摘要或摘要为空")
            versions.append(VersionSummary(projects=tuple(projects), summary=summary))
        summaries.append(FileSummary(path=path, versions=tuple(versions)))

    for path, groups in expected.items():
        if path not in seen_paths:
            raise LLMError(f"摘要缺少文件：{path}")
        entry = next(s for s in summaries if s.path == path)
        got_groups = [frozenset(v.projects) for v in entry.versions]
        # 版本必须不重不漏恰好覆盖发送的词表：缺一个版本或多报一个（同一组
        # 工程名出两份摘要）都是畸形输出，宁可大声失败也不带病进第二阶段
        for group in groups:
            if got_groups.count(group) != 1:
                raise LLMError(
                    f"{path} 缺少内容版本的摘要：{'、'.join(sorted(group))}"
                )
        for got in got_groups:
            if got not in groups:
                raise LLMError(
                    f"{path} 的摘要含未知内容版本：{'、'.join(sorted(got))}"
                )
    return tuple(summaries)


def parse_validation_result(content: str) -> ValidationResult:
    """把模型返回的校验 JSON 文本解析校验为 ValidationResult。

    任何结构 / 内容问题（非 JSON、缺 consistent、字段类型错）都抛 LLMError——
    模型输出不可信，宁可大声失败也不要放行未校验的简介入库。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError("校验结果必须是 JSON 对象")
    if "consistent" not in data:
        raise LLMError("校验结果缺少必填字段 consistent")
    if not isinstance(data["consistent"], bool):
        raise LLMError("校验结果的 consistent 必须是布尔值")
    issues = data.get("issues", "")
    if not isinstance(issues, str):
        raise LLMError("校验结果的 issues 必须是字符串")
    return ValidationResult(consistent=data["consistent"], issues=issues)


def _build_user_prompt(problem_text: str, heading: str, items: Sequence[str]) -> str:
    """赛题 + 清单的 user 消息拼装（模块选择 / main.c 骨架共用）。"""
    lines = ["赛题：", problem_text, "", heading]
    lines.extend(items)
    return "\n".join(lines)


def _selection_user_prompt(problem_text: str, manifest_summaries: Sequence[str]) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    prompt = _build_user_prompt(problem_text, "模块库可用模块：", manifest_summaries)
    return prompt + '\n只返回 json 格式的 JSON 对象：{"modules": [{"slug": "...", "reason": "..."}]}'


def _summarize_user_prompt(
    platform: str,
    project_names: Sequence[str],
    judgment_files: Sequence[JudgmentFile],
) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    names = "、".join(project_names)
    lines = [
        f"平台：{platform}",
        f"导入的工程：{names}",
        "",
        "需要判定的文件（同一路径出现多个内容版本 = 冲突；只出现在部分工程 = "
        "独有）。读全文后为每个内容版本写一段中文摘要：",
    ]
    for file in judgment_files:
        for version in file.versions:
            lines.append(
                f"- {file.path}（{'、'.join(version.projects)}）：\n"
                f"```c\n{version.content}\n```"
            )
    lines.append(
        "只返回 json 格式的 JSON 对象："
        '{"summaries": [{"path": "...", "versions": [{"projects": ["工程名"], '
        '"summary": "中文摘要"}]}]}'
    )
    return "\n".join(lines)


def _distill_user_prompt(
    platform: str,
    project_names: Sequence[str],
    file_summaries: Sequence[FileSummary],
    comparison_summary: str,
) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    names = "、".join(project_names)
    lines = [
        f"平台：{platform}",
        f"导入的工程：{names}",
        "",
        "待判文件内容摘要（已读全文的要点）：",
    ]
    for summary in file_summaries:
        for version in summary.versions:
            lines.append(
                f"- {summary.path}（{'、'.join(version.projects)}）：{version.summary}"
            )
    lines.extend(
        [
            "",
            "结构与配置对比：",
            comparison_summary,
            "",
            "对每个需要判定的文件路径给出动作：keep（保留）/ merge（整合：同一路径"
            "多份内容不同时，读多份后整合出通用版本，选一份只是特例）/ exclude（剔除）。"
            "判定唯一判据：读文件内容后判断是否通用（不依赖具体赛题）、是否基础建设"
            "必需（平台基础设施 / 工程配置），不看重复次数与出现范围。merge 必须给出"
            "整合产物全文 content 与整合说明 explanation。公共文件已确定保留，不在判定"
            "范围内，不要列进 decisions；只判定冲突与独有文件。判定理由带上摘要要点。"
            "只返回 json 格式的 JSON 对象：",
            '{"decisions": [{"path": "...", "action": "keep|merge|exclude", '
            '"content": "merge 时必填的整合产物全文", '
            '"explanation": "merge 时必填的整合说明（选一份时说明为何选它）", '
            '"source": "merge 选一份时可选填的来源工程名", "reason": "中文理由"}]}',
        ]
    )
    return "\n".join(lines)


def _validation_user_prompt(description: str, code: str) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    return (
        f"模块简介：\n{description}\n\n实际代码：\n```c\n{code}\n```\n\n"
        '判断简介与实际代码是否一致，只返回 json 格式的 JSON 对象：'
        '{"consistent": true/false, "issues": "不一致时用中文指出差异，一致时为空字符串"}'
    )


def _skeleton_user_prompt(problem_text: str, module_interfaces: Sequence[str]) -> str:
    """main.c 骨架生成的 user 消息：赛题 + 所选模块头文件接口块（见 skeleton.py）。"""
    prompt = _build_user_prompt(
        problem_text,
        "所选模块的头文件接口（main.c 只调用这里真实存在的函数）：",
        module_interfaces,
    )
    return prompt + (
        "\n\n输出 main.c 骨架：按模块初始化序列排好调用，带注释与预留编写区（TODO），"
        "不确定的调用写成注释占位，不凭空造函数，保证可编译。"
    )


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
