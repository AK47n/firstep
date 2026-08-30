"""LLM 客户端抽象与生产实现。

生产实现 DeepSeekLLM 走 DeepSeek Chat Completions API（base_url / api_key /
模型来自本机配置文件 config.py）；HTTP 传输可注入假件，网络调用不进测试。
LLM 承担七类协议职责：赛题→模块选择、赛题预读（AI 预读题面给一句话
总览 + 决策点提醒——限定/约束/指定类事实，供后续步骤核对）、main.c 骨架
生成、模块简介生成与校验、母版提炼
判定（冲突/独有文件 → 保留/合并/剔除；两阶段：先读全文出摘要，再基于
摘要判定）、参考文件提炼归档判定、赛题库拆条 / 编号提取。
领域模型不在此处——赛题库模型在 topic_library，判定素材模型在 report，
模块推荐模型与收敛工作流在 selection，一致性校验结果模型在 library，进度
事件契约在 events（本模块只消费）。请求体有大小控制：所有嵌内容调用
（赛题 / 接口块 / 文件全文）超长截断（带标注，AI 知道读到的是截断内容；
参考全文例外——截断下沉 read_fulltext 逐文件完成，注入处只留
REFERENCE_FULLTEXT_BYTES wire 字节预算兜底）、摘要阶段多文件按预算分批发送、
发送前有序列化体积断言兜底——DeepSeek 网关对请求体有硬性大小限制，
一次性全发会 413。
"""

from __future__ import annotations

import json
import logging
import math
import time
import urllib.error
import uuid
import urllib.request
from email.utils import parsedate_to_datetime
from dataclasses import dataclass, field, replace
from numbers import Real
from typing import Any, Callable, Mapping, NoReturn, Protocol, Sequence, TypeVar

from .budget import (
    FIX_PREVIOUS_FIXES_CAP,
    REFERENCE_FULLTEXT_BYTES,
    SKELETON_REFERENCE_TOTAL_BYTES,
    fit_wire_budget,
    wire_size,
)
from .config import AppConfig
from .events import (
    EVENT_BATCH_DONE,
    EVENT_BATCH_START,
    EVENT_PHASE_DONE,
    EVENT_RETRY,
    EVENT_START,
    PHASE_DECIDE,
    PHASE_SUMMARY,
    ProgressEmitter,
    ProgressEvent,
    _emit,
)
from .fix_errors import FixSuggestion
from .library import TRUNCATION_NOTICE, ValidationResult, truncate_content
from .impact import ImpactAnalysis, ImpactError, build_impact_analysis
from .manifest import EXCLUSIVE_GROUP_TAG, ManifestSummary
from .report import (
    ACTION_MERGE,
    FileDecision,
    FileSummary,
    JudgmentFile,
    ReferenceCandidate,
    ReportError,
    VersionSummary,
)
from .selection import (
    BUY_VERDICTS,
    MAX_QUESTIONS,
    FunctionRequirement,
    ModuleSelection,
    OutOfLibrarySuggestion,
    REFERENCE_SOURCE_MANUAL,
    ReferenceSuggestion,
    SelectionError,
    build_module_selection,
    multi_instance_labels,
    multi_instance_vocab,
    parse_decision,
)
from .task_progress import TaskError, TaskPlan, build_task_plan
from .topic_preread import (
    MAX_QUOTE_LEN,
    MAX_REMINDERS,
    MAX_REMINDER_TEXT_LEN,
    PREREAD_STEP_NAMES,
    PrereadResult,
    normalize_preread,
)
from .wiring import WiringEntry, parse_wiring_entries
from .params import ParamList, build_params
from .topic_library import TopicDraft, validate_topic_key
from .wordlist import (
    DEFAULT_WORDLIST,
    HardwareWordGroup,
    SolutionOption,
    format_wordlist_prompt,
)


def sanitize_llm_usage(usage: Mapping[str, Any] | None) -> dict[str, int | float] | None:
    """Keep only numeric token-usage fields for logs / collector / SSE telemetry."""
    if not usage:
        return None
    result: dict[str, int | float] = {}
    for key, value in usage.items():
        if isinstance(key, str) and isinstance(value, Real) and not isinstance(value, bool):
            numeric = float(value)
            result[key] = int(numeric) if numeric.is_integer() else numeric
    return result or None


logger = logging.getLogger(__name__)

# 截断标注契约在 library.truncate_content / TRUNCATION_NOTICE
# （工单 03 迁共享层：reference_library 的逐文件截断同用此措辞，而其不能
# 运行时 import llm——环约束，TYPE_CHECKING 同款先例）——llm 导入重出。

# 模块推荐系统提示词（工单 10）：题面证据驱动的功能需求层 + 收敛自检。
# 行为要点与 ADR 0007 同源：逐句对照防脑补（找不出对应句的需求即脑补，删）、
# 实现覆盖检查机械产出库外建议（不是主观推荐）、库外建议 name 受硬件词表硬
# 约束（不懂不编、编造降级）、收敛循环以题面为裁判（删脑补 / 补遗漏 / 重查
# 覆盖）、题面证据不足且影响模块选择时向用户补问（有疑问一轮问全：一次性列全、
# 最多 selection.MAX_QUESTIONS 条、不渐进追问）。
SELECT_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手，熟悉 MSPM0G3507（CCS）与 "
    "STM32F103C8T6（Keil5）两条平台线。分析赛题严格以题面原文为证据"
    "（赛题文本可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "）。"
    "题面已按句编号（如 1. 2. 3.），先逐句对照（每句对应一个功能需求或"
    "\"无功能\"），产出功能需求层：能力/外设级的稳定描述（声光提示 → "
    "LED/蜂鸣器、识别数字 → 视觉），粒度贴题面关键词；每条需求必须挂题面"
    "句子编号（sentence），找不出对应句的需求 = 脑补，删——禁止题外联想"
    "（\"送药小车所以需要视觉\"是脑补，题面要求识别数字才需要视觉）。"
    "控制常识不算题外联想：沿无引导标记路径自主行驶 → 航向保持（陀螺仪/姿态"
    "传感器）；\"用时不大于 X 秒\"等时间限制是裁判侧指标，不据此推荐计时模块。"
    "逐条做实现覆盖检查：模块库里有实现 → 该需求的 modules（可勾选进工程）；"
    "无命中 → 库外建议 suggestions（name + 常识举例，仅展示、不进工程、"
    "不参与生成）。库外建议的 name 必须来自硬件词表（类别名或具体型号名，"
    "词表见用户消息）；具体型号不在词表内时，降级输出为它所属的类别名并"
    "在 category 字段注明，宁可给类别也不编造型号。每条库外建议按题面判断"
    "后在词表给出的选购方案（solutions）中选一个最适合本赛题的方案名填 "
    "selected（只从 solutions.name 里挑，不得自创方案名；方案列表看用户消息"
    "里的硬件词表，无合适方案则不填 selected）。以题面为裁判反复自检"
    "修订（删脑补 / 补遗漏 / 重查覆盖），连续两轮功能需求层一致即可保持"
    "不动。题面已明确给出的细节（如颜色、型号、数量、类型、位置点）绝不重复问；"
    "题面写明'自定/不限'的条目（如'起始点摆放方向自定'）就是题面已给出的答案，"
    "绝不问；题目中没有提到的细节就是没有限制：题面未提及的要求（如指示灯颜色"
    "亮度、提示方式等）与规格参数（如传感器几路、尺寸大小）一律视为无限制，按"
    "合理默认实现，不为此提问。题面证据不足且直接影响模块选择或方案核心结构的"
    "关键信息，才在 questions 数组向用户补问——规格参数（数量/路数/颜色/音调/"
    "时长）不构成补问理由；不要瞎猜；"
    "有疑问时一次性把所有疑问全部列出（每条具体可答、最多 "
    f"{MAX_QUESTIONS} 条），"
    "用户一轮全部答完，不要分批渐进追问。用户已回答过的问题不要重复问，仅"
    "补充新疑问（与澄清阶段同规，问答历史在题面后的独立段）。输出保持紧凑："
    "每条功能需求描述 ≤ 40 字、reason ≤ 20 字、不重复题面原文——只输出结论"
    "不输出分析过程。只输出 JSON 对象。"
)

# 澄清阶段系统提示词（工单 01 推荐先澄清后收敛）：只看题面 + 已有问答历史，
# 输出仍存的疑问（空 = 澄清完成；有疑问一轮问全——一次性列全、最多
# selection.MAX_QUESTIONS 条、不渐进追问）。不带模块库——疑问只来自题面证据不足，
# 与库内实现无关（库内有没有实现是收敛阶段的事）。
# 工单 clarify-dumb-questions/01：题面已明确给出的细节绝不重复问（用户报告
# 「前面都说了红色指示灯还问我颜色」）——逐句核对后再问，只问题面缺失的关键
# 信息；宁缺毋滥。工单 clarify-vision-relax/02：流程/时序/指示灯含义/计时
# 起止同属题面已给出的信息（真机 2021F Q3 场景：取药流程、红灯含义、总时间
# 起止全在题面正文，不应再问）。
CLARIFY_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手。逐句核对赛题原文（赛题文本可能"
    "被截断，见末尾标注，" + TRUNCATION_NOTICE + "）：题面已明确给出的细节"
    "（如已指定颜色、型号、数量、类型、位置点）绝不重复问——先逐句核对题面，"
    "确认某条信息题面确实没有给出，才可提问；题面写明'自定/不限/自由选择'的"
    "条目（如'起始点摆放方向自定'）就是题面已给出的答案，绝不问；题目中没有"
    "提到的细节就是没有限制"
    "（默认宽松）：题面未提及的要求（如指示灯颜色与亮度、蜂鸣器音调、提示时长"
    "与方式、传感器具体型号等）与规格参数（如灰度传感器几路、尺寸大小）一律"
    "视为无限制，按合理默认实现，不为此提问。题面证据不足"
    "且直接影响模块选择或方案核心结构的关键信息，才向用户补问——规格参数"
    "（数量/路数/颜色/音调/时长）不构成补问理由；"
    "有疑问时一次性把所有疑问全部列出（每条具体可答、最多 "
    f"{MAX_QUESTIONS} 条），用户一轮全部"
    "答完，不要分批渐进追问；用户已回答过的问题"
    "不要重复问；没有疑问时输出空 questions 数组。宁缺毋滥——题面已覆盖的"
    "信息不问、可合理假设的不问。题面已写明的流程/时序（谁先谁后、启动与"
    "返回次序）、指示灯含义、计时起止规则（如任务总时间从某动作开始计到某"
    "动作结束）绝不重复问——这些是题面给出的信息，基于题面回答即可。"
    "题面引用图（如图N）但当前文本没有图的描述"
    "时，不要要求用户补充图的内容——题面文本中通常已含图内标注文字（尺寸/"
    "位置等），基于已有标注推断并说明假设；只有影响核心决策的缺失信息才提问。"
    "只输出 JSON 对象。"
)

# 修订影响分析系统提示词（工单 revise-deepen/02）：评审新增赛题答疑 Q&A 对
# 既有模块推荐的影响。逐条 Q&A → 影响结论（影响哪些功能需求 → 建议模块
# 增/删/不变 + 理由）；输出**建议的最终模块集**（完整列表，diff 由工具算——
# spec「AI 只负责解释为什么，不负责算差异」）。Q&A 是权威材料（赛事组澄清）。
IMPACT_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手，熟悉 MSPM0G3507（CCS）与 "
    "STM32F103C8T6（Keil5）两条平台线。你在评审一组新增的赛题答疑 Q&A 对"
    "既有模块推荐的影响（赛题文本可能被截断，见末尾标注，"
    + TRUNCATION_NOTICE
    + "）。逐条核对新 Q&A（用户消息末尾独立段，权威澄清材料）：每条说明它"
    "影响哪些功能需求（引用功能需求层原文）、建议模块增 / 删 / 不变及理由；"
    "最后给出建议的最终模块集（**完整列表**，不是增量——从功能需求层出发："
    "保留仍被需求支撑的模块、删除被 Q&A 推翻或不再有需求支撑的模块、补充"
    "新需求命中的模块；只输出库内模块 slug）。只输出 JSON 对象。"
)

# 骨架「不声明未使用变量」规则的唯一表述：系统提示词与用户提示词在同一个 API
# 调用里都要说这件事（ticket 06 双端漂移教训：只改系统提示词会被用户消息尾句
# 「保证可编译」盖过——模型按用户消息行事）。此常量是唯一出处：改规则只动这里
# （契约测试 test_llm 双端断言）。真机 2026C stm32 曾出 UV4 4 警：s_lock_state /
# s_welcome_state / s_zone_state / s_expect_id 占位声明未用（#177-D declared but
# never referenced / #550-D set but never used），违背用户 0 错 0 警验收标准。
SKELETON_NO_UNUSED_RULE = (
    "不声明未使用的变量：main.c 里每个变量声明都必须被后续代码读取或赋值；"
    "预留状态一律写成注释（TODO）说明，不写占位声明（未使用的声明会产生"
    "编译警告，验收要求 0 警告）。"
)

# 题型框架强指令（工单 topic-framework/03）：框架段注入骨架 user prompt 时的
# 约束——必须保留框架结构，只填 TODO。单源常量（与 SKELETON_NO_UNUSED_RULE
# 同款：改约束只动这里，契约测试断言）。
SKELETON_FRAMEWORK_RULE = (
    "按此框架写 main.c：状态机枚举 / 调度循环 / 框架函数名保持原样，"
    "只在 `// TODO:` 处填当前所选模块接口的实现（实现不存在的调用写成注释"
    "占位，保证可编译）。框架段之外的赛题功能按需补充。"
)

# 深化系统提示词（工单 revise-deepen/04）：按功能需求清单逐条填充 main.c 的
# TODO 预留区——输出与需求清单对应（逐条可追踪，不做题外发挥）；只调真实
# 接口；保证可编译。深化不设自动循环，用户可重复触发。
DEEPEN_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。在现有 main.c 骨架上按功能需求清单逐条填充 TODO "
    "预留区（赛题文本 / 接口过长可能被截断，见末尾标注，"
    + TRUNCATION_NOTICE
    + "）：每条需求对应一段实现（可跨函数），不要遗漏任何一条需求、不要实现"
    "需求清单之外的功能（禁止题外发挥）；只调用给定接口中真实存在的函数，"
    "绝不凭空造函数；保留原有初始化序列与已有代码（那是用户可能手工编辑过的"
    "内容），只填充 TODO 预留区。"
    + SKELETON_NO_UNUSED_RULE
    + "输出完整 main.c（整个文件，不是片段），纯 C 代码，不要用 ``` 或 ~~~ "
    "代码围栏包裹，不要输出任何 Markdown 标记。"
)

# 任务拆解系统提示词（工单 task-progress/01）：把题面 + 功能需求层 + 评分点 +
# 模块接口 + 现有 main.c 拆成有序任务清单。任务 = 可独立执行并独立编译验证的
# main.c 增量；id 由域层按顺序分配，这里只产标题/描述/关联/前置/验收方式。
TASK_PLAN_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师与赛题施工队长。把赛题实现拆解为有序任务清单"
    "（赛题文本 / 接口过长可能被截断，见末尾标注，"
    + TRUNCATION_NOTICE
    + "）：每个任务 = 对现有 main.c 的一次可独立实现、可独立编译验证的增量"
    "（如「ADC 采样与显示」「PID 闭环」「循迹决策」）。规则："
    "① 覆盖题面全部实质要求与功能需求清单，不遗漏、不题外发挥；"
    "② 任务按实现顺序排列（基础在前、依赖在前），后续任务基于前序任务结果；"
    "③ 只调用给定接口中真实存在的函数；"
    "④ 粒度适中：一次任务对应一次 LLM 实现调用（约一段 TODO / 一个功能闭环），"
    "不要拆到单函数，也不要一个任务吃掉整个题；"
    "⑤ depends_on = 前置任务序号（1 起，本清单内的位置），无前置 = 空数组；"
    "⑥ score_refs = 关联评分点 id（只引用题面评分点清单里的 id，无评分点 = "
    "空数组；一条任务可关联多个评分点）；"
    "⑦ verify = 该任务完成后的验收方式：compile = 编译绿即算验证通过；"
    "manual = 需要上板观察现象人工确认（如循迹效果、显示内容正确性）。"
    "⑧ resources = 本任务将占用的互斥资源数组（引脚如 \"PA0\"、外设如 "
    "\"TIM1\"/\"UART0\"、中断如 \"TIM1_IRQn\"——只用模块接口清单里出现的真实"
    "名称；本任务不新增占用 = []；与其它任务共用的资源也要列出——后续资源"
    "总览据此发现联调冲突，重复不一定是错，但必须如实标注）。"
    "特别约定：resources 只允许硬件实体（引脚/外设/中断），禁止填模块名"
    "（如 xunji、led_beep）、函数名、宏名（如 LED_BEEP）——多个任务复用同一"
    "模块/函数不是硬件互斥冲突，模块复用不填 resources，只有引脚/外设/中断"
    "被两任务同时占用才算冲突暗雷。"
    '只输出 JSON 对象：{"tasks": [{"title": "短标题（8-16 字）", '
    '"description": "做什么、用哪些接口、落到 main.c 哪里（带 TODO 上下文）", '
    '"score_refs": ["s1"], "depends_on": [1, 2], "verify": "compile", '
    '"resources": ["PA0"]}]}'
)

# 单任务执行系统提示词（工单 task-progress/02）：在现有 main.c 上只实现一个
# 任务（其余已实现内容与手工编辑原样保留），文本模式输出整文件——深化同款
# 形状，prompt 约束"只实现本任务"。
TASK_EXECUTE_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。在现有 main.c 上实现**指定的这一个任务**"
    "（赛题文本 / 接口过长可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "）："
    "只实现任务描述里要求的功能，不实现清单中其他任务、不做题外发挥；"
    "保留原有初始化序列与已有代码（那是已完成的其它任务与用户手工编辑过的"
    "内容）；已有的实现即使看起来不完美也不要改（其它任务的成果）；"
    "只调用给定接口中真实存在的函数，绝不凭空造函数。"
    + SKELETON_NO_UNUSED_RULE
    + "若用户提供了【上板实测反馈】——那是用户把程序烧到真机运行后观察到的"
    "实际现象（如某功能不工作 / 行为异常）：你的任务变为按反馈修复该任务的"
    "实现，只改与反馈问题相关的部分（定位现象的功能点的初始化 / 调用 / 逻辑），"
    "不重写无关代码、不动其它任务成果。"
    + "输出完整 main.c（整个文件，不是片段），纯 C 代码，不要用 ``` 或 ~~~ "
    "代码围栏包裹，不要输出任何 Markdown 标记。"
)

# 买件方案商量系统提示词（工单 buy-discuss/01）：买件指引的选型讨论 + 用户
# 自定想法可行性校核（用户原话「用户的方法只是他的猜想，AI 校核一下这个
# 是不是真的可行并且跟用户进一步沟通」）。立场 = 顾问非裁判：verdict 是风险
# 意见，最终仍用户拍板（界面明确标注 AI 意见）；建议可指向词表方案比对。
# review 只在用户最新消息提出「词表外的自定方案」时输出（词表内方案讨论
# 无校核需求，仅回复）。输出 JSON 契约（json_object 模式）。
DISCUSS_SYSTEM_PROMPT = (
    "你是嵌入式硬件选型顾问。学生正在为赛题选购库外外设（词表给几个候选"
    "方案，你只当顾问，不替学生拍板）。回答学生的问题与想法（赛题文本 / "
    "方案清单过长可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "）："
    "结合赛题要求、所选平台（接口 / 引脚 / 定时器等资源）与词表方案比对，"
    "给出具体、可执行的建议；学生提出的想法若是词表外的自定方案（他手头"
    "已有的模块 / 自己的想法），要校核其可行性：接口与引脚资源、供电电压、"
    "题目所需要的功能是否对症、现场环境（光照 / 距离 / 干扰）是否适合，"
    "并与他进一步沟通（必要时反问关键信息）。verdict 三档含义：feasible = "
    "可行；risky = 可行但有风险（说明风险点）；infeasible = 本赛题不可行"
    "（说明理由并给出替代建议）。"
    '只输出 JSON 对象：{"reply": "回复文本", "review": {"verdict": '
    '"feasible" | "risky" | "infeasible", "reason": "校核理由", '
    '"suggestion": "替代建议（可指向词表方案）"}}；学生最新消息没有提出'
    "自定方案时，review 输出 null（只答问题）。"
)

# 任务商量（工单 task-chat/02）：用户对某个实现任务发表想法/纠正 → AI 先回应。
# 立场 = 任务顾问非执行者：回应结构（先判可行性 → 再说对任务实现的影响 →
# 给修正建议）；用户采纳哪条由前端 / dialog-adopt 端点处理，模型不替用户
# 决定。只输出 JSON 契约（json_object 模式，reply 必填）。
TASK_DISCUSS_SYSTEM_PROMPT = (
    "你是嵌入式 C 开发顾问。学生在做某个实现任务前 / 后，向你发表自己的想法"
    "或纠正（赛题文本 / 模块接口 / 对话历史过长可能被截断，见末尾标注，"
    + TRUNCATION_NOTICE + "）：结合当前任务描述、赛题要求、所选模块接口与"
    "当前 main.c 的实现情况，先判断学生的想法是否可行（不直接改代码——"
    "「做这一步」时才由任务执行实现），再说明它对本任务实现的影响（改哪里、"
    "涉及哪些接口 / 引脚 / 定时器），最后给出具体、可执行的修正建议；需要"
    "更多信息时反问关键问题。若学生的想法与现状冲突，明确指出冲突点与替代"
    "方案，不要含糊附和。"
    '只输出 JSON 对象：{"reply": "回复文本"}；reply 必须非空、用中文。'
)

# 步骤报告（工单 stepwise-deepen/01 + task-insight/01 + task-wiring-diagram/02）：
# 一步任务执行 + 编译验证刚完成，AI 用中文给学生写「我做了什么 + 接下来你要
# 做什么」两步简报 + 上板自检清单 + 本步接线引用。立场 = 执行者汇报，不是
# 顾问（执行已完成，不再讨论方案）；接线/上板指引必须落到模块接口清单里的
# 真实引脚/接口名（user_action 是学生接下来唯一的物理动作清单——把接线、
# 烧录、观察现象、确认动作一次说清，别让用户猜）；checklist 是 user_action
# 的结构化拆分（原子勾选项，供上板照单子逐条测）。wiring = 本步接线引用
# （工单 task-wiring-diagram/02）：**只给名字，图形由工程数据决定**——只能
# 引用【本工程接线数据】段里出现的引脚名与端子名（表行 + 板载供电/固定
# 资源行），严禁自造；每根线一条；本步无物理接线 = 不输出或空数组。只输出
# JSON 契约。
TASK_REPORT_SYSTEM_PROMPT = (
    "你是嵌入式 C 开发工程师。学生刚点「做这一步」并完成了某个实现任务，"
    "编译验证也已结束（赛题文本 / 模块接口过长可能被截断，见末尾标注，"
    + TRUNCATION_NOTICE + "）。请用中文给学生写一份本步骤简报，分四段："
    "what_changed = 本步做了什么——引用具体函数 / 引脚 / 定时器名说明改动，"
    "并注明编译验证结果；如有降级（如无工具链未验证）或警告，一并说明。"
    "user_action = 学生接下来需要做的物理动作——按模块接口清单把具体接线"
    "（如「把 PA0 接到灰度模块的 DIO」）、烧录、观察什么现象、确认后的操作"
    "一次说清；本步纯软件无物理动作时才可为空串，否则必须给出明确动作。"
    "checklist = 上板 / 验证检查清单（3-6 条，每条一句「应观察到什么；若不"
    "正常检查哪里」，原子可勾选——烧录后逐条测；本步纯软件无物理动作 = []）。"
    "wiring = 本步需要学生接着接的线（数组；本步无物理接线 = 不输出或空数组）"
    "——每条 {pin, target, note?}：pin = 板引脚丝印名（PA0 / PB6 / 3V3 / "
    "GND / 5V…），target = 端子名（模块角色 id 或 label、板载资源名、或引脚"
    "名自身），note = 简短中文说明（如极性注意），可省略。**只能引用"
    "【本工程接线数据】段里出现的引脚名与端子名**，每根线一条；严禁自造或"
    "幻想——查不到真实来源的名字会被后端直接丢弃，丢弃后本步就没有接线图。"
    '只输出 JSON 对象：{"what_changed": "做过的中文叙事", "user_action":'
    ' "接下来的中文动作", "checklist": ["应观察到什么；若不正常查哪里"],'
    ' "wiring": [{"pin": "PA0", "target": "DIO", "note": "注意极性"}]}；'
    "what_changed 必须非空，四段都用中文。"
)

# 参数识别（工单 param-tune/01）：扫描 main.c 里的可调**数值**参数——学生
# 上板调试最频繁的改值对象（阈值 / 速度 / PID 系数 / 延时 / 占空比）。立场 =
# 扫描器非改造者：只列参数不改代码（改值走确定性 apply，零 LLM）。anchor 是
# 声明行原文（后续按它做逐字节定位替换——必须与源码逐字节一致且 old_value
# 在其中恰好出现 1 次，否则无法确定性改值）。只输出 JSON 契约。
TASK_PARAM_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。学生在做上板调参，请你扫描给定 main.c（赛题文本 / "
    "接口过长可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "），找出**数值**"
    "类可调参数：阈值、速度、PID 系数、延时、占空比、采样次数、死区等——即"
    "学生上板时最可能想改的常量（#define 数值 / 变量初始化赋的数值字面量）。"
    "规则："
    "① 只列数值参数（整数 / 浮点 / 带后缀 1.2f、3000UL 等），不列结构开关、"
    "字符串、头文件引脚定义、计算表达式（如 a+b）、数组下标；"
    "② name = 参数标识（如 THRESHOLD）；label = 一句话中文含义（如"
    "「循迹阈值」）；old_value = 当前值的原文（**逐字节**：如 800 / 1.2f / "
    "3000UL，与 main.c 中完全一致）；"
    "③ anchor = 该参数的声明行原文（含缩进与注释，**必须与 main.c 逐字节一致**"
    "且其中 old_value 恰好出现 1 次——后续按 anchor 首现位置做确定性替换）；"
    "④ 同一数值被多处使用（多处定义 / 一处定义多处引用）：只列**定义处**一处，"
    "anchor 取定义行；"
    "⑤ 没有可调数值参数时输出空数组（不要编造）。"
    '只输出 JSON 对象：{"params": [{"name": "THRESHOLD", "label": "循迹阈值", '
    '"old_value": "800", "anchor": "#define THRESHOLD 800", "unit": "", '
    '"range_hint": "500-1000"}]}；unit / range_hint 可为空串。'
)

# 新想法 / 问题分析（工单 idea-fix/01）：用户随时抛来想法 → AI 先理解并分成
# 三类（new_task 新功能任务卡 / direct_fix 直接改现有代码 / discussion 先讨论
# 不动代码），三类都带「落地」所需的字段。立场 = 顾问兼策划：分析 + 给落地
# 方案，不直接改代码（改代码走 apply_idea_fix / 任务执行）。只输出 JSON 契约。
TASK_IDEA_SYSTEM_PROMPT = (
    "你是嵌入式 C 开发总顾问。用户随时抛来一个关于当前工程的新想法或发现的"
    "问题（赛题文本 / 模块接口过长可能被截断，见末尾标注，" + TRUNCATION_NOTICE
    + "）。先理解用户要什么，再判断它属于哪一类："
    "new_task = 新的功能需求（当前任务清单里还没有的任务，需要新增一张任务卡）；"
    "direct_fix = 对现有代码的直接修正（改某个已实现行为 / 阈值 / 引脚 / 状态机"
    "条件等）；discussion = 用户拿不准、想先聊聊（不直接动代码）。规则："
    "① new_task 时给出建议任务 new_task：title（短标题 8-16 字）、description"
    "（做什么、用哪些接口、落到 main.c 哪里）、score_refs（只引用题面评分点"
    "清单里的 id，无评分点 = []）、depends_on（清单内既有任务序号，1 起，"
    "无依赖 = []）、verify（compile | manual）；"
    "② direct_fix 时 fix_summary 用中文说明要改哪里、怎么改（具体到函数 / "
    "引脚 / 条件），affected_task_ids 列出可能被这次修正影响的既有任务 id"
    "（没有 = []）；"
    "③ discussion 时不改代码，reply 给出你的理解和建议，以及下一步可以怎么走；"
    "④ reply 必须用中文说明你对这个想法的理解与判断（为什么这样分类）。"
    '只输出 JSON 对象：{"kind": "new_task" | "direct_fix" | "discussion", '
    '"reply": "中文理解与判断", "new_task": {"title", "description", '
    '"score_refs", "depends_on", "verify"} | null, "fix_summary": "中文修正建议", '
    '"affected_task_ids": ["t1"]}'
)

# 全局工程级商量（工单 idea-suite/01）：学生针对**整个工程**的连续追问 →
# AI 工程总顾问回应（结合题面 / 需求 / 清单现状 / 接口 / 当前 main.c /
# 已采纳的全局结论）。立场 = 顾问非执行者：落地（转任务 / 转修正 / 采纳为
# 全局结论）由前端按钮与专用端点处理，模型不替用户决定。只输出 JSON。
TASK_GLOBAL_DISCUSS_SYSTEM_PROMPT = (
    "你是嵌入式 C 开发总顾问。学生正在就整个工程做连续追问（不是某个具体"
    "任务卡——任务卡有单独的商量入口；赛题文本 / 模块接口过长可能被截断，"
    "见末尾标注，" + TRUNCATION_NOTICE + "）。结合赛题要求、功能需求清单、"
    "任务清单现状（哪些已做 / 建议重做）、所选模块接口与当前 main.c 的实现"
    "情况，回答学生的问题——先判断可行性（利与弊），再说明对工程现状的"
    "影响（改哪里、涉及哪些接口 / 引脚 / 定时器 / 任务），最后给出具体、"
    "可执行的建议；需要更多信息时反问关键问题。若学生的想法与现状冲突，"
    "明确指出冲突点与替代方案，不要含糊附和。若工程已有采纳的全局结论"
    "（【工程级全局结论】段），回复须与之一致；冲突时指出并说明理由。"
    "不直接改代码——落地（转任务 / 转修正 / 采纳为全局结论）由学生决定。"
    '只输出 JSON 对象：{"reply": "回复文本"}；reply 必须非空、用中文。'
)

# 参数速调咨询（工单 params-chat-ai/01）：学生不知道现象该调哪个参数时来问
# → AI 嵌入式 C 调参顾问（结合当前已识别参数清单 + 题面 + 任务清单现状）。
# 立场 = 顾问非执行者：只推荐参数与方向，改值由学生在参数卡上完成。
# 只输出 JSON。
PARAMS_CHAT_SYSTEM_PROMPT = (
    "你是嵌入式 C 调参顾问。学生正在就当前工程的**参数调整**做多轮咨询"
    "（调试中不知道现象该调哪个参数时来找你）。你会拿到当前工程已识别的"
    "可调参数清单（参数名 / 中文含义 / 当前值 / 单位 / 建议范围 / 是否仍有效）、"
    "赛题与任务清单现状。回答规则："
    "一、先判断症状是否足够；信息不足时反问关键问题（现象、触发条件、期望效果）。"
    "二、推荐时**必须原样引用参数清单中真实存在的参数名**（如 THRESHOLD），"
    "每条回复可点名多个参数并按优先级排序（先调哪个、再调哪个、为什么）。"
    "三、每个推荐的参数说明：理由（症状 → 参数关联）、调整方向（增大 / 减小）、"
    "建议范围（优先用清单里的建议范围；没有则给粗略区间并标注「试」）、"
    "验证方法（改完点「应用」→ 编译验证 → 上板复测）。"
    "四、参数清单为空或未识别时：明确告诉学生还没识别参数，建议先点"
    "「识别 main.c 参数」；若症状更像代码逻辑 / 传感器 / 连接问题而非参数问题，"
    "如实说明并建议检查方向，不要硬凑参数。"
    "五、只做咨询，不直接改数值；不替学生决定必须改哪项，只给推荐与理由。"
    '只输出 JSON 对象：{"reply": "回复文本"}；reply 必须非空、用中文。'
)

# 想法直接修正（工单 idea-fix/01）：按用户想法做直接修正——只改想法相关的
# 实现，其余原样保留；不实现清单里的新功能（那走任务卡）。文本模式输出
# main.c 全文（与任务执行同形状，prompt 约束同款「只改指定内容」）。
IDEAFIX_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。按照用户的修正想法与 AI 分析给出的修正建议，在现有"
    "main.c 上做**直接修正**（赛题文本 / 模块接口过长可能被截断，见末尾标注，"
    + TRUNCATION_NOTICE + "）：只改修正建议里点名的实现（行为 / 阈值 / 引脚 / "
    "状态机条件等），不实现清单中的新功能任务、不做题外发挥；保留原有初始化"
    "序列与已有代码（那是已完成任务与用户手工编辑过的内容）；已有的实现即使"
    "看起来不完美也不要改；只调用给定接口中真实存在的函数，绝不凭空造函数。"
    + SKELETON_NO_UNUSED_RULE
    + "若【受影响任务】列出了清单中的任务——那是参考信息（修正可能影响它们），"
    "不要顺带修改它们的实现（是否重做由用户决定）。"
    "输出完整 main.c（整个文件，不是片段），纯 C 代码，不要用 ``` 或 ~~~ "
    "代码围栏包裹，不要输出任何 Markdown 标记。"
)

# 骨架 / 自检冒烟共用的接口块引导语（两处曾各抄一份，改一处忘另一处即分叉）
SKELETON_INTERFACES_HEADING = "所选模块的头文件接口（main.c 只调用这里真实存在的函数）："
SKELETON_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。为赛题生成 main.c 骨架（赛题文本 / 模块接口过长"
    "可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "）：按所选模块的头文件"
    "接口排好初始化序列，带注释说明与预留编写区（TODO）。只调用给定接口中"
    "真实存在的函数，绝不凭空造函数；不确定的调用写成注释占位，保证骨架可编译。"
    + SKELETON_NO_UNUSED_RULE
    + "输出纯 C 代码，不要用 ``` 或 ~~~ 代码围栏包裹，不要输出任何 Markdown 标记。"
)

SMOKE_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。为用户生成硬件自检冒烟 main.c（不是赛题逻辑实现）："
    "把每个所选模块初始化一遍、读一次/动一次，并把自检结果打印出来。只调用"
    "给定接口中真实存在的函数，绝不凭空造函数；不确定的调用写成注释占位，"
    "保证可编译。"
    + SKELETON_NO_UNUSED_RULE
    + "输出纯 C 代码，不要用 ``` 或 ~~~ 代码围栏包裹，不要输出任何 Markdown 标记。"
)

SUMMARY_SYSTEM_PROMPT = "你是嵌入式 C 工程师。用中文一句话总结这段代码的功能，作为模块库简介。"

# 简介校验判据③④的唯一表述：系统提示词与用户提示词在同一个 API 调用里都要说
# 这件事（ticket 06 双端漂移教训：判定范围曾只改系统提示词、漏改用户提示词，
# 模型按用户消息跳过公共文件当场失败）。此常量是唯一出处：改判据只动这里
# （契约测试 test_llm 双端断言）。判据① 与代码一致、② 硬件身份（library 侧
# 必填校验）不变；③ 能力方向 / ④ 无题绑定为 ADR 0009 新规——模块 = 纯驱动
# 切片，"XX 题专用"不再是合法模块类别（旧"专用性声明一致性"检查被④取代）。
VALIDATION_UNIVERSALITY_RULE = (
    "同时按模块形态新规检查（ADR 0009 判据③④）："
    "③ 能力方向——简介必须声明该模块可用于哪类赛题功能（如\"灰度循迹\"\"PID "
    "闭环控制\"\"K230 视觉帧解析\"），可列多项点明主能力；简介只描述硬件/协议/"
    "实现细节、未声明任何能力方向 → 判为不一致，issues 提示补写能力方向。"
    "④ 无题绑定——简介不得绑定具体赛题：出现题号/年份（如 2021F、2024H、"
    "2026C、2026H）、\"XX 题专用\"、具体题名或专用逻辑声明 → 判为不一致，"
    "issues 提示改写为普适能力描述；代码明显带赛题专用逻辑（题号/年份注释、"
    "赛题状态机、专用判定参数）→ 同样判为不一致，issues 提示按 ADR 0009 剥离"
    "决策逻辑（进生成骨架，决策素材可归档参考文件库）。"
)

VALIDATION_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。判断给定的模块简介与实际代码是否一致：简介描述的功能、"
    "接口、行为是否与代码相符。"
    + VALIDATION_UNIVERSALITY_RULE
    + "不一致时用中文指出具体差异。只输出 JSON 对象。"
)

JUDGMENT_SUMMARY_SYSTEM_PROMPT = (
    "你是嵌入式开发工程整理助手。导入的多个同平台旧工程里，有些文件需要判定"
    "去留：同一路径在不同工程里内容不同（冲突），或只出现在部分工程（独有），"
    "或所有工程内容一致（公共，同样要判）。逐文件读全文（超长文件已截断并在"
    "末尾标注，" + TRUNCATION_NOTICE + "）后，为每个内容版本用"
    "中文写一段简短摘要：说明它实现什么功能、是否通用、是否基础建设必需。"
    "必须为列出的每个文件输出摘要，一个都不能少。只输出 JSON 对象。"
)

# 判定范围与判据的唯一表述：系统提示词与用户提示词在同一个 API 调用里都要
# 说这件事，各自硬编码会静默漂移——ticket 06 曾只改系统提示词、漏改用户提示
# 词，模型按用户消息跳过公共文件，多工程提炼当场失败（"提炼报告缺少判定"）。
# 此常量是唯一出处：改判定范围 / 判据只动这里（契约测试 test_llm 双端断言）。
JUDGMENT_SCOPE = (
    "判定范围 = 公共 + 冲突 + 独有（全部文件）逐个判定。判定唯一判据：读文件"
    "内容后判断它是否通用、是否基础建设必需（ADR 0001）——官方外设库（STM32 "
    "标准外设库 / TI driverlib）、平台基础设施（启动 / system / CMSIS / 链接"
    "脚本 / 工程配置）、通用基础封装（如 delay 延时，写任何工程都要用）→ "
    "keep；具体项目 / 具体硬件相关的业务代码（传感器驱动、外设封装、赛题逻辑）"
    "→ exclude。不看重复次数与出现范围——公共文件（所有工程内容一致）同样"
    "逐个判定，可保留可剔除，内容一样不等于基础建设必需。工程配置文件"
    "（.uvprojx / .uvoptx / .cproject / .project 等）由确定性规则处理、不参与"
    "判定（ADR 0003）——AI 给出这类路径的判定是越界，会被系统拒绝。"
)

DISTILL_SYSTEM_PROMPT = (
    "你是嵌入式开发工程整理助手。用户导入了多个同平台旧工程，你需要根据文件"
    "内容摘要与结构配置对比判定哪些文件应该进母版（母版 = 空的最小系统板工程，"
    "能直接编译烧录）。"
    + JUDGMENT_SCOPE
    + "动作词表：keep（保留）/ merge（整合：同一路径多份内容不同时，读多份后"
    "整合出通用版本，选一份只是特例，必须给出整合产物全文与整合说明）/ "
    "exclude（剔除）。必须为每个待判文件给出动作，一个都不能少。只输出 JSON 对象。"
)

# 参考文件简介生成（工单 02）：配套资料（例程工程 / 说明书等）→ 中文简介草稿。
# 素材超长截断带标注（与所有嵌内容调用同款，TRUNCATION_NOTICE 唯一出处见上）。
REFERENCE_SUMMARY_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发资料整理助手。根据提供的配套资料内容"
    "（素材过长可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "）写一段中文"
    "简介：它是什么、用途、适用场景。只输出简介文本，不要额外格式。"
)

# 赛题预读（预读步骤，wait-what 效果 + 决策点提醒）：AI 预读题面给一句话
# 总览 + 决策点提醒列表（每条 = 影响步骤 + 提醒文本 + 题面原文引用）。用户
# 自己会通读题面，本调用不复述功能（那是评分点/推荐职责），只提炼"限定 /
# 约束 / 指定"类事实（必须 / 只能 / 不得 / 限定 / 采用……），让用户在后续
# 决策步骤（选平台 / 推荐 / 模块清单 / 引脚 / 骨架 / 深化）不踩题面已锁死的
# 坑。只展示给用户确认理解，不进任何下游流程；结构化 JSON 契约（机械校验
# 在 topic_preread 域），与纯文本摘要类调用不同。
PREREAD_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手，熟悉 MSPM0G3507（CCS）与 "
    "STM32F103C8T6（Keil5）两条平台线。预读下面的赛题（赛题文本可能被"
    "截断，见末尾标注，" + TRUNCATION_NOTICE + "），输出严格 JSON 对象，"
    "仅供用户在后续生成步骤中核对「题面已经锁死了什么」，不进任何下游流程。"
    "JSON 结构：{\"overview\": \"...\", \"reminders\": [{\"steps\": [...], "
    "\"text\": \"...\", \"quote\": \"...\"}]}。overview = 一句话总览这个赛题"
    "要做一个什么样的装置 / 系统。reminders = 最多 "
    + f"{MAX_REMINDERS} 条" + "，每条一个对象："
    "steps = 该提醒影响的下一个生成步骤编号数组——"
    + "、".join(f"{n}={PREREAD_STEP_NAMES[n]}" for n in PREREAD_STEP_NAMES)
    + "；若该限定不属于"
    "任何具体步骤（尺寸 / 电源 / 时长等通用要求）用空数组 []。text = 一到两"
    "句中文提醒（不超过 " + f"{MAX_REMINDER_TEXT_LEN} 字" + "），点明题面限定"
    "与影响（如「题面限定采用 TI "
    "MSPM0 系列，目标平台请选 MSPM0G3507」）。quote = 题面原文逐字短片段"
    "（不超过 " + f"{MAX_QUOTE_LEN} 字" + "），证明该限定的出处。"
    "只提炼限定 / 约束 / 指定类事实（必须 / 只能 / 不得 / 限定 / 采用……，"
    "例如限定芯片、指定器件、通信接口、尺寸电源时长等硬性指标）；题面的功能"
    "描述（如「小车需要循迹」）不是限定，不要输出。严格以题面原文为证据，"
    "不要脑补题外限定。只输出 JSON 对象，不要额外格式。"
)

# 英文目录短名生成（工单 ascii-project-name/02）：AI 给粘贴题面起一个纯英文
# 短名（如 Auto_Car），做桌面生成目录名——中文目录名在 Windows CCS/gmake 链上
# 乱码（工单 mspm0-cjk-path-fix/01 只修模板，管不住 CCS IDE 重建 makefile）。
# 纯文本契约，与模块简介同款：文本模式、无结构化输出、短名本身即整段输出
# （严格 ASCII：字母数字 + 下划线/连字符，3~5 个词，不含中文）。
TOPIC_EN_NAME_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手。为下面的赛题起一个英文短名，"
    "用作工程目录名（赛题文本可能被截断，见末尾标注，" + TRUNCATION_NOTICE
    + "）：只输出短名本身——纯 ASCII 字符（字母、数字、下划线或连字符），"
    "3~5 个词，每个词首字母大写并用下划线连接（如 Auto_Car、"
    "Smart_Medicine_Car、Car_Following_System）。不要输出任何多余格式、解释"
    "或引号，只输出短名一行。"
)

# 编译错误修复（工单 compile-error-fix/01 + fix-snippet-match/01）：贴报错 →
# 逐条修复建议（snippet 替换协议）。old_snippet 给从行首开始的语句本体片段
# （可省前导缩进 / 行尾注释，语句本体须逐字一致）——工具先精确匹配，失败时
# 按行首前缀归一化兜底，匹配失败 / 多处歧义跳过并报告「未应用」；file 只可
# 从提供的文件清单里选（越界路径由域模块 fix_errors.apply_fixes 拒绝，400
# 中文）。空输出（无 fix）合法 = 模型认为无法确定修复（结果 0 应用，用户可
# 换措辞重试）。域判决留在 fix_errors.py，本模块只做机械提取（提示词 +
# 严格解析）。约束 7（工单 fix-loop-warnings/01）：Warning 条目同款修复，
# 模块自带警告不瞎改。
FIX_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师，修复生成工程中的编译报错（文件内容可能被截断，"
    "见末尾标注，" + TRUNCATION_NOTICE + "）。逐条修复报错，只输出 JSON 对象："
    '{"fixes": [{"file": 文件相对路径, "line": 报错行号, "old_snippet": '
    '"现有内容片段", "new_snippet": "替换后内容", "reason": "修复理由"}]}。'
    "约束：1) file 必须来自提供的文件清单，且是相对路径；不要建议修改清单外"
    "的文件（含工程配置文件 / 构建产物，它们不参与修复）。2) old_snippet 给"
    "从行首开始的语句本体片段（如整条语句或函数调用），可以省略前导缩进与"
    "行尾注释，但语句本体必须与文件现有内容逐字一致（含空格）——工具先精确"
    "匹配，失败时按行首前缀归一化匹配后替换；需要删除整行时给该语句本体"
    "即可。片段要足够长、上下文足够独特，保证文件内唯一匹配；一处片段出现"
    "多次 = 该处不修（工具会跳过并报告未应用）。3) new_snippet 是替换后的"
    "内容；需要删除整行或整段时 new_snippet 给空字符串。4) 只修报错指出的"
    "问题，不要无关重构；一条报错给一处修复，多处报错可在 fixes 数组列出"
    "多处。5) 依据不足、无法确定精确修改时，宁可不输出该条（工具报告未应用）"
    "也不要乱改。6) 用户消息若带「上一轮修复应用结果」段（工单 "
    "fix-loop-progress/01）：其中未应用（skipped）的条目原因已写明——重试时"
    " old_snippet 必须从文件当前内容里逐字对齐后重写（行号只作提示，以文件"
    "内容为准），仍无法精确给出时放弃该条；不要重复输出与上一轮一模一样的"
    "建议。7) 编译输出中的 Warning（警告）条目同样逐条修复（工单 "
    "fix-loop-warnings/01）：未使用变量 / 函数（删除声明或补引用）、告警"
    "明确指出实质问题的照修；第三方库或模块自带警告（如宏重定义）不瞎改，"
    "依据不足时同约束 5 宁可不输出该条。"
)

# 归档判定（工单 02）：提炼时被剔除的业务代码是否值得归档为该赛题的参考文件。
# 判据 = 可复用的业务代码 / 学习参考（传感器驱动、外设封装、赛题逻辑实现、
# 算法），一次性杂物 / 配置噪声 / 无关文件不值得归档。与提炼判据同款双端
# 契约（系统提示词与用户提示词都带判据，见 _archive_judgment_user_prompt）。
ARCHIVE_JUDGMENT_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发工程整理助手。提炼旧工程时被剔除的"
    "文件，需要判断是否值得归档为该赛题的参考文件（素材过长可能被截断，见"
    "末尾标注，" + TRUNCATION_NOTICE + "）：归档价值 = 可复用的业务代码或学习"
    "参考（传感器驱动、外设封装、赛题逻辑实现、算法）；一次性杂物 / 配置噪声"
    " / 无关文件不值得归档。只输出 JSON 对象。"
)

# 设计报告草稿 LLM 输出层（工单 report-draft-demo/03）：方案论证 + 软件流程
# 结构化输出 {rationale, workflow}。软件流程为最后一段（渲染契约：报告模块
# 按 \n\n 分段、最后一段 = 软件流程，见 report_draft._split_llm_text），故
# 提示词约束 workflow 内部不用空行。
REPORT_DRAFT_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）参赛助手。根据赛题原文、功能需求清单、模块清单"
    "与引脚分配，为设计报告撰写两节草稿：rationale = 系统方案论证（为什么用"
    "这套架构 / 选型，结合题面与需求逐点论证，可用多个段落，段落间用空行）；"
    "workflow = 软件流程设计（主循环 / 关键流程，写成一段，段内不要用空行）。"
    "只输出 JSON 对象：{\"rationale\": \"...\", \"workflow\": \"...\"}。"
)

# 嵌内容上限（字符）：第一阶段提示词把每个内容版本全文嵌入，真实旧工程里的
# 巨型源码（如 stm32f10x.h ~800KB 标准库头）全文嵌入会撑爆上下文（判例 08：
# 三个真实工程修复前判定素材 47.6M 字符，修复后按此上限嵌入 29 万字符）。
# 截断只影响发送素材（文件头足以判断性质），keep 落盘仍复制工程原文全文，
# 不受截断影响。该上限是所有嵌内容调用（赛题 / 接口块 / 文件全文 / 参考
# 素材）的统一截断上限——_truncate_content 走这里；参考全文例外（工单 03：
# 截断下沉 read_fulltext 逐文件 + 注入处走更宽的 REFERENCE_FULLTEXT_BYTES
# wire 字节预算，常量在 budget）。
EMBEDDED_CONTENT_CAP = 4000

# 澄清历史段合计截断上限（字符，工单 recommend-speedup/01 D）：历史随补问
# 轮数无界增长，是请求体预算第二大漏点（2026-08-13 实测 20 条 ~9KB 尚可
# 控，防未来涨）。逐条 _truncate_content 之后整段再走本上限截头带标注——
# 历史只作"已答不重问"的判据，最坏形态（20 条长问答）仍 ≤ 本上限 × 6 字节
# ≈ 15KB（wire 口径，中文 6 字节/字符——历史段推导按 6B 计入 budget.
# REFERENCE_FULLTEXT_BYTES 的总量反推）。取值与 REFERENCE_FULLTEXT_BYTES
# 共同满足总量预算，最坏情况结构测试钉死（tests/test_llm.py），改大即红。
CLARIFICATION_HISTORY_CAP = 2500

# 两阶段输出的补问上限：模型一次输出大量 JSON 条目时偶发丢条目（判例 08：
# 115 个文件一次返回漏了 1 个），严格解析失败后只对缺失路径补问，最多补问
# 这么轮；仍缺失就大声失败——宁可失败也不带病进下一阶段。
SUMMARY_RETRY_LIMIT = 5

# 网络类失败的重试上限（工单 deepseek-retry-hardening/01）：网络层瞬断
# （连接重置 10054 / URLError / 超时 / 网关 5xx）3 连快重试大概率仍断
# （工单 reference-library-hygiene/03 真机 3/3 次运行撞此形态，重试 3 次
# 仍断、整轮推荐作废），改指数退避：最多重试 NETWORK_RETRY_LIMIT 次、间隔
# 按连续网络失败次数 2**n 秒（1/2/4/8）——序列由 tests/test_llm.py 钉死。
# 解析类仍走 SUMMARY_RETRY_LIMIT 快重试（工单 recommend-call-retry/01 机制不变；
# 2026-08-15 用户反馈“两次失败就停” → 与网络类对齐提高到 5 次总尝试）。
NETWORK_RETRY_LIMIT = 5

# 判定分批大小：一次问太多文件，模型会系统性漏掉小配置文件 / 点文件
# （判例 08：115 个文件一次返回漏 30 个，补问也不收敛——不是偶发，是批量
# 超载）。按此大小分批问，总输入 token 不变（每个文件只嵌入一次），漏判
# 从"必现"降为"偶发"，交给补问机制兜底。摘要阶段的分批同时受文件数上限
# （本常量，模型可靠性）与字符预算（MAX_SUMMARY_BATCH_CHARS，请求体上限）
# 双重约束，见 _judgment_batches。
JUDGMENT_BATCH_SIZE = 25

# 请求体预算（413 修复）：DeepSeek 网关对请求体有硬性大小限制（超限返回
# "413 Request Entity Too Large"），导入带标准外设库 / driverlib 的完整工程
# 时，摘要阶段把全部文件全文一次塞进一个请求必然超限。批预算远小于网关
# 限制，提示词开销与 JSON 转义不占预算余量。
MAX_SUMMARY_BATCH_CHARS = 24000  # 每批摘要请求的内容字符预算
MAX_REQUEST_BYTES = 128 * 1024  # 发送前断言：序列化请求体超过此字节数即大声失败（兜底）

# 拆条单次 LLM 调用的全文长度上限（工单 04）：超过即走确定性分块
# （topic_library.split_topics_document，纯文本规则切分）——flash 模型输出
# 预算有限（实测 max_tokens=8192 也截断），多年长 PDF 一次拆必静默漏题；
# 20K 字符 = 实测 163K 全量必截断后的安全块上限。
TOPIC_SPLIT_LLM_CHAR_CAP = 20000

# select（模块选择）输出上限（工单 llm-select-runaway/01 + select-truncation/01）：
# deepseek-v4-flash 曾无上限输出 ~20K tokens/次（疑似退化：逐句分析/自检过程
# 写进 JSON），单次等待 ~160s 且解析必然失败、重试重复烧钱。4096 只对
# **content** 生效（配合请求侧 thinking disabled——见 select_modules 调用处）：
# select 合理输出 < 2K tokens；超长 = 输出退化，被服务端截断 →
# finish_reason=length → _retry_parse 判确定性失败报 client 错误免重试，
# 字符侧守卫（SELECT_MAX_OUTPUT_CHARS）再兜底。**不要调大此值来容纳推理
# 输出**：v4-flash 思考模式默认开且 effort=high，select 这类确定性 JSON 任务
# 会让模型深度推理循环不收敛，max_tokens 全被 reasoning_content 吃掉、
# content 为空（实测 4096 / 16384 皆截断）——正确做法是关闭思考模式。
SELECT_MAX_OUTPUT_TOKENS = 4096
# 超长守卫阈值（字符）：响应内容超过即判输出失控，报 client 错误免重试
# （_retry_parse 对 client 错误 break——重试只会重复烧钱烧时间）。
SELECT_MAX_OUTPUT_CHARS = 60000

# 航向保持/姿态类组 id 前缀（工单 recommend-exclusive-groups/03）：提示词题面
# 核查条触发条件 = 库内存在该前缀的组（约定见库 manifest 登记，2024H =
# attitude-hold）。命名约定单源：组 id 改名或新增同前缀组只改这里。
ATTITUDE_GROUP_ID_PREFIX = "attitude"

# 观测响应留痕长度（字符）：只留前缀诊断信号（截断 / 退化 / 语义拒绝），
# 不破坏观测「不含 prompt / response」的脱敏契约。
CONTENT_EXCERPT_CHARS = 120

# 澄清阶段题面预算（工单 clarify-dumb-questions/01）：题面是澄清的唯一依据，
# 通用嵌内容预算（EMBEDDED_CONTENT_CAP=4000）下长赛题后半句被截（如送药小车
# 「点亮红色指示灯」句），模型问题面已明确的细节（用户报告「前面都说了红色
# 指示灯还问我颜色」）。wire 账本：全中文 ensure_ascii 6B/字符 → 12000×6=72KB
# + 澄清历史段（CLARIFICATION_HISTORY_CAP=2500 → 15KB）= 87KB < MAX_REQUEST_BYTES
# 128KB ✓；clarify 不带参考文件注入，无联动预算冲突。
CLARIFY_TOPIC_CAP = 12000


def _truncate_content(content: str) -> str:
    """单内容截断（带标注）：超长内容只送前 EMBEDDED_CONTENT_CAP 字符。

    文案 / 标注唯一出处 = library.truncate_content（工单 03 迁共享层），此处
    只绑定 llm 的嵌内容预算常量；截断只影响发送素材，不改数据模型。
    """
    return truncate_content(content, EMBEDDED_CONTENT_CAP)


def _clean_str_list(raw: Any) -> tuple[str, ...]:
    """可选字符串数组的宽松归一（checklist 等辅助字段，工单 task-insight/01
    ——评审整改：report_task_step 内联生成器与 task_progress._opt_str_list
    为同型复制，收敛到本函数防漂移）。

    非数组 = ()；数组内非 str / 空串项过滤；str 项 strip 后保留非空。
    """
    if not isinstance(raw, list):
        return ()
    return tuple(
        text.strip()
        for text in (s if isinstance(s, str) else "" for s in raw)
        if text.strip()
    )


def _fit_fulltext_wire(
    fulltext: str, budget: int = REFERENCE_FULLTEXT_BYTES
) -> str:
    """全文注入的 wire 字节预算截断（工单 budget-wire-unification/01）：弃用
    字符 cap（REFERENCE_FULLTEXT_CAP「×3 字节」估算假口径——真实线
    json.dumps ensure_ascii=True 中文实发 6 字节/字符，全中文最坏形态必炸
    128KB 网关），改 wire 字节预算取最长前缀（budget.fit_wire_budget）+ 截头
    标注（TRUNCATION_NOTICE 文案沿用）——标注自身的 wire 字节计入预算（对齐
    fix 侧 read_file_contexts 既有做法：标注非免费，推导余量已含）。预算内
    原样返回（逐文件截断标注归 read_fulltext，此处零增删）。budget 参数供
    骨架参考段等多篇注入按篇数均分（skeleton-smoke-refs/02）。
    """
    fitted = fit_wire_budget(fulltext, budget)
    if fitted != fulltext:
        fitted += (
            f"\n……（内容过长，已截断：仅展示前 {budget} "
            f"wire 字节，原文共 {len(fulltext)} 字符；{TRUNCATION_NOTICE}）……\n"
        )
    return fitted


# 硬件词表科普段 wire 字节预算（工单 buy-guide/01）：词表行含选购方案名后
# 体积上升（方案名是 selected 判决依据——模型必须看到全部类别的方案名才能
# 按题面选 selected，截掉尾部类别 = 该类别 selected 恒空、买件指引核心功能
# 折损）。预算取「默认词表完整 wire（实测 3170）+ 膨胀余量」= 4200：默认
# 词表全量送达（不截断）、未来加类/加方案留 ~1KB 余量，同时段级兜底防
# 词表无界膨胀撑爆请求预算（budget.REFERENCE_FULLTEXT_BYTES 推导里的
# 「词表」项按本预算计）。截断标注自身 wire 字节计入预算（fit 前预扣，
# 对齐 fit_wire_budget 文档契约「标注非免费、进记账」）。
WORDLIST_PROMPT_BYTES = 4200

# 词表段截断标注（单源；不用全局 TRUNCATION_NOTICE——词表截断是科普段压缩
# （后续类别仍由界面展示加载），与 content 截断契约（题面/参考）语义不同界，
# 避免干扰断言「内容不被截断」的调用方测试（fulltext 注入测试）。
WORDLIST_TRUNCATION_NOTICE = "\n……（硬件词表过长，已截断，仅保留前部类别与方案）……\n"


def _wordlist_prompt_segment(
    hardware_words: Sequence[HardwareWordGroup],
) -> str:
    """硬件词表科普段（wire 预算截断 + 标注）：只送预算内前缀。

    词表是科普素材不是判决依据（模型可以从截断前的类目联想到库外建议），
    截断只影响发送素材；完整词表仍在界面展示（载荷 solutions 来自词表
    数据模型，不经 prompt）。截断标注进预算：fit 到 (预算 − 标注 wire)，
    保证实发 ≤ 预算（对齐 fit_wire_budget 文档契约）。
    """
    segment = format_wordlist_prompt(hardware_words)
    fitted = fit_wire_budget(
        segment, WORDLIST_PROMPT_BYTES - wire_size(WORDLIST_TRUNCATION_NOTICE)
    )
    if fitted != segment:
        fitted += WORDLIST_TRUNCATION_NOTICE
    return fitted


def _clarification_history_segment(
    clarifications: Sequence[tuple[str, str]],
) -> str:
    """澄清问答历史段（Q/A 逐条）：逐条截断 + 段级合计预算兜底（工单
    recommend-speedup/01 D）。

    两条嵌入路径（clarify / select_modules 的历史段）共用同一组装——历史随
    补问轮数无界增长，逐条 _truncate_content（带标注）挡单条超长，整段
    CLARIFICATION_HISTORY_CAP 挡条数增长；截断只影响发送素材，不改数据模型。
    """
    lines = [
        line
        for question, answer in clarifications
        for line in (
            f"Q: {_truncate_content(question)}",
            f"A: {_truncate_content(answer)}",
        )
    ]
    segment = "\n".join(lines)
    if len(segment) > CLARIFICATION_HISTORY_CAP:
        segment = truncate_content(segment, CLARIFICATION_HISTORY_CAP)
    return segment


def _extract_good_summaries(
    content: str, batch: Sequence[JudgmentFile]
) -> list[FileSummary]:
    """从一次失败的批量摘要输出里挖出能通过严格校验的条目（补问只问缺失的）。

    逐文件粒度校验（判例 08：deploy_config.json 把多内容版本合并成一条，曾让
    同批 14 个合法摘要连坐、整批重问 3 轮全废）：一个文件输出畸形只让它自己
    重问，其他文件的合法摘要照常收下；输出里非本轮批次的路径条目忽略（补问
    轮模型偶发复述已覆盖路径，不该拖累本批校验）。
    """
    try:
        data = json.loads(content)
        wanted = {f.path for f in batch}
        entries = [
            item
            for item in data.get("summaries", [])
            if isinstance(item, dict) and item.get("path") in wanted
        ]
    except (json.JSONDecodeError, AttributeError):
        return []
    good: list[FileSummary] = []
    for f in batch:
        f_entries = [e for e in entries if e.get("path") == f.path]
        if not f_entries:
            continue
        try:
            good.extend(parse_summary_report(json.dumps({"summaries": f_entries}), [f]))
            continue
        except LLMError:
            pass
        # 模型把多内容版本合并成一条（判例 08：deploy_config.json 两版内容过于
        # 相似，模型屡次合并、补问不收敛）→ 确定性拆分回逐版本条目再校验
        reconciled = _split_merged_versions(f, f_entries)
        if reconciled is not None:
            try:
                good.extend(
                    parse_summary_report(json.dumps({"summaries": reconciled}), [f])
                )
            except LLMError:
                continue
    return good


def _split_merged_versions(
    file: JudgmentFile, entries: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """模型把多内容版本合并成一条摘要（projects 列了多个版本的全部工程名）。

    拆分条件严格：该路径发送词表含多个内容版本组，输出恰好一条条目、且其
    projects 恰好等于各版本组工程名的并集（不多不少）——此时模型读多份后
    写了一条"通用"摘要，拆回逐版本条目（摘要复制）。并集不匹配或形状不对
    则不拆（宁缺毋滥，留给补问轮）。拆出的版本摘要相同会让第二阶段看不出
    版本差异、倾向 exclude/keep 而非 merge——对内容高度相似的版本是合理近似
    （模型本来就认为差异可忽略）。
    """
    if len(file.versions) < 2 or len(entries) != 1:
        return None
    groups = file.version_groups
    union = frozenset().union(*groups)
    entry = entries[0]
    raw_versions = entry.get("versions")
    if not isinstance(raw_versions, list) or len(raw_versions) != 1:
        return None
    merged = raw_versions[0]
    if not isinstance(merged, dict):
        return None
    projects = merged.get("projects")
    summary = merged.get("summary")
    if (
        not isinstance(projects, list)
        or frozenset(projects) != union
        or not isinstance(summary, str)
        or not summary
    ):
        return None
    # 一条条目、多条 versions（模型契约：同一路径只出现一次，版本在 versions 里）
    return [
        {
            "path": file.path,
            "versions": [
                {"projects": sorted(group), "summary": summary} for group in groups
            ],
        }
    ]


def _extract_good_decisions(
    content: str,
    project_names: Sequence[str],
    batch: Sequence[FileSummary],
) -> tuple[FileDecision, ...]:
    """从一次失败的批量判定输出里挖出能通过严格校验的条目（补问只问缺失的）。

    与 _extract_good_summaries 同款逐文件粒度：一个条目畸形（如 merge 缺整合
    产物全文）只让它自己重问，好条目不连坐；输出里非本轮批次的路径条目忽略。
    """
    try:
        data = json.loads(content)
        entries = [item for item in data.get("decisions", []) if isinstance(item, dict)]
    except (json.JSONDecodeError, AttributeError):
        return ()
    good: list[FileDecision] = []
    for f in batch:
        entry = next((e for e in entries if e.get("path") == f.path), None)
        if entry is None:
            continue
        try:
            good.extend(
                parse_distillation_report(
                    json.dumps({"decisions": [entry]}), project_names
                )
            )
        except LLMError:
            continue
    return tuple(good)



# LLMError 类别（工单 deepseek-retry-hardening/01）：network = 网络层瞬断
# （_retry_parse 走指数退避，见 NETWORK_RETRY_LIMIT），parse = 输出解析 /
# 业务失败（快重试）。字符串常量单源：转换点（UrllibTransport / _chat 5xx）
# 与 _retry_parse 分策略都引用，测试同样引用（词表同款单源原则）。
ERROR_KIND_NETWORK = "network"
ERROR_KIND_PARSE = "parse"
ERROR_KIND_CLIENT = "client"
ERROR_KIND_RATE_LIMIT = "rate_limit"
ERROR_KIND_BUDGET = "budget"


@dataclass
class RetryBudget:
    """一条工作流共享的 LLM 调用次数 / 耗时上限；缺省不设限。"""

    max_attempts: int | None = None
    max_elapsed_seconds: float | None = None
    _clock: Callable[[], float] = time.monotonic
    _started_at: float = field(init=False)
    attempts: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.max_attempts is not None and self.max_attempts < 1:
            raise ValueError("max_attempts 必须 ≥ 1")
        if self.max_elapsed_seconds is not None and self.max_elapsed_seconds < 0:
            raise ValueError("max_elapsed_seconds 必须 ≥ 0")
        self._started_at = self._clock()

    def consume_attempt(self) -> int:
        elapsed = self._clock() - self._started_at
        if self.max_elapsed_seconds is not None and elapsed >= self.max_elapsed_seconds:
            raise LLMError(
                "LLM 工作流累计耗时预算已耗尽，请稍后重试、减少输入或调整预算",
                kind=ERROR_KIND_BUDGET,
            )
        if self.max_attempts is not None and self.attempts >= self.max_attempts:
            raise LLMError(
                "LLM 工作流累计尝试次数预算已耗尽，请稍后重试、减少输入或调整预算",
                kind=ERROR_KIND_BUDGET,
            )
        self.attempts += 1
        return self.attempts


def _content_excerpt(content: str) -> str:
    """响应内容 → 脱敏诊断摘要：换行压平为单空格、取前 CONTENT_EXCERPT_CHARS
    字符、超长加省略号。只留前缀信号（截断 / 退化 / 语义拒绝的判别线索），
    完整响应绝不进入观测与日志。"""
    flattened = " ".join(content.split())
    if len(flattened) <= CONTENT_EXCERPT_CHARS:
        return flattened
    return flattened[:CONTENT_EXCERPT_CHARS] + "…"


@dataclass(frozen=True)
class LLMCallObservation:
    """一条已脱敏的 LLM 调用观测；不包含 prompt / response / key / 文件内容。"""

    workflow_id: str
    sequence: int
    operation: str
    provider: str
    route: str
    model: str
    duration_ms: int
    attempts: int
    status: str
    final: bool
    call_id: int | None
    budget_attempt: int | None
    http_status: int | None
    error_kind: str | None
    parse_status: str
    request_bytes: int
    usage: Mapping[str, Any] | None = None
    content_excerpt: str | None = None

    def to_log_extra(self) -> dict[str, Any]:
        usage = sanitize_llm_usage(self.usage)
        return {
            "workflow_id": self.workflow_id,
            "sequence": self.sequence,
            "operation": self.operation,
            "provider": self.provider,
            "route": self.route,
            "model": self.model,
            "duration_ms": self.duration_ms,
            "attempts": self.attempts,
            "status": self.status,
            "final": self.final,
            "call_id": self.call_id,
            "budget_attempt": self.budget_attempt,
            "http_status": self.http_status,
            "error_kind": self.error_kind,
            "parse_status": self.parse_status,
            "request_bytes": self.request_bytes,
            "usage": usage,
            "content_excerpt": self.content_excerpt,
        }


@dataclass
class LLMObservationCollector:
    """工作流级 LLM 调用观测收集器：追加顺序号并只保存脱敏字段。"""

    workflow_id: str
    on_record: Callable[[], None] | None = None
    _started_at: float = field(default_factory=time.monotonic, init=False)
    _observations: list[LLMCallObservation] = field(default_factory=list, init=False)

    def record(self, observation: LLMCallObservation) -> LLMCallObservation:
        if observation.workflow_id != self.workflow_id:
            raise ValueError("观测 workflow_id 与 collector 不一致")
        if observation.sequence != len(self._observations) + 1:
            raise ValueError("观测 sequence 必须单调递增")
        self._observations.append(observation)
        if self.on_record is not None:
            try:
                self.on_record()
            except Exception:
                pass
        return observation

    def collect(
        self,
        *,
        operation: str,
        provider: str,
        route: str,
        model: str,
        duration_ms: int,
        attempts: int,
        status: str,
        final: bool,
        call_id: int | None,
        budget_attempt: int | None,
        http_status: int | None,
        error_kind: str | None,
        parse_status: str,
        request_bytes: int,
        usage: Mapping[str, Any] | None = None,
        content_excerpt: str | None = None,
    ) -> dict[str, Any]:
        observation = LLMCallObservation(
            workflow_id=self.workflow_id,
            sequence=len(self._observations) + 1,
            operation=operation,
            provider=provider,
            route=route,
            model=model,
            duration_ms=duration_ms,
            attempts=attempts,
            status=status,
            final=final,
            call_id=call_id,
            budget_attempt=budget_attempt,
            http_status=http_status,
            error_kind=error_kind,
            parse_status=parse_status,
            request_bytes=request_bytes,
            usage=sanitize_llm_usage(usage),
            content_excerpt=content_excerpt,
        )
        self.record(observation)
        return observation.to_log_extra()

    @property
    def elapsed_ms(self) -> int:
        return round((time.monotonic() - self._started_at) * 1000)

    @property
    def observations(self) -> tuple[dict[str, Any], ...]:
        return tuple(item.to_log_extra() for item in self._observations)


def create_llm_observation_collector(workflow_name: str) -> LLMObservationCollector:
    """创建一次逻辑工作流的观测收集器，workflow_id = 类型 + 随机实例 id。"""
    return LLMObservationCollector(f"{workflow_name}:{uuid.uuid4().hex}")


@dataclass(frozen=True)
class _ChatResult:
    """一次真实请求的响应内容与观测元数据（解析后补记 parse_status）。

    finish_reason = 服务端截断信号（工单 select-truncation/01）："length" =
    输出被 max_tokens 上限截断（推理模型 reasoning 与 content 共享上限，
    content 常为空串）——参数性确定性失败，重试必然同样截断，消费方免重试。
    """

    content: str
    operation: str
    started_at: float
    request_bytes: int
    http_status: int
    usage: Mapping[str, Any] | None
    call_id: int
    attempts: int
    budget_attempt: int | None
    finish_reason: str | None = None


class LLMError(Exception):
    """LLM 调用或输出解析失败，message 说明具体问题。

    kind 区分错误类别（缺省 parse，向后兼容——存量单参构造全部按解析类）：
    network = 网络层瞬断（连接失败 / 超时 / 网关 5xx，重试有价值）；
    parse = 输出解析 / 业务失败。非 network 类别一律视为 parse。
    """

    def __init__(self, message: str, kind: str = ERROR_KIND_PARSE, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after


# 分批 / 重试循环的条目类型限定：两阶段各自只有一对输入 / 输出类型（摘要
# 阶段：待判文件 → 摘要；判定阶段：摘要 → 判定）。用限定 TypeVar 表达而非
# Protocol——mypy 2.3.0 在 from __future__ import annotations 下对 Protocol
# 属性约束的结构匹配实测不生效。
I = TypeVar("I", JudgmentFile, FileSummary)  # 批内输入条目
R = TypeVar("R", FileSummary, FileDecision)  # 批处理输出条目
T = TypeVar("T", JudgmentFile, FileSummary)
RT = TypeVar("RT")  # 整次调用重试的返回类型（不限定：摘要 str / 归档路径元组）


def _file_chars(file: JudgmentFile) -> int:
    """一个待判文件的发送字符数：各内容版本截断后合计（分批预算按此近似）。"""
    return sum(len(_truncate_content(version.content)) for version in file.versions)


def _split_versions(file: JudgmentFile) -> list[JudgmentFile]:
    """单文件多版本合计超预算时按版本拆成单版本条目（批内路径不重复）。"""
    return [JudgmentFile(file.path, (version,)) for version in file.versions]


def _batches(
    items: Sequence[T],
    *,
    max_chars: int | None,
    size_of: Callable[[T], int] | None = None,
    split_oversized: Callable[[T], Sequence[T]] | None = None,
) -> tuple[tuple[T, ...], ...]:
    """按文件数上限（JUDGMENT_BATCH_SIZE）分批；max_chars 给定时同时受字符预算约束。

    两个约束各自对应一个判例：预算约束防请求体超网关限制（413）；文件数上限
    防单批超载导致模型系统性漏判小配置文件（判例 08：一次问 115 个文件漏 30
    个，补问不收敛）。两个不变量同时成立——漏判从"必现"降为"偶发"，交给
    补问机制兜底。分批只按"截断后内容字符数"近似——提示词开销与 JSON 转义
    远小于网关限制，预算本身留了余量。顺序保持输入顺序：摘要产物按批拼接后
    与发送顺序一致。

    摘要阶段（max_chars=MAX_SUMMARY_BATCH_CHARS）：批内各版本全文（截断后）
    合计不超预算、文件数不超上限，单文件多版本合计超预算时按版本拆批
    （split_oversized，同批内不出现同一路径两次——parse_summary_report 按
    路径校验批次覆盖，同批重复路径会让模型输出无法自证）。
    判定阶段（max_chars=None）：摘要产物已小，无请求体预算约束（见
    _decide_distillation 的分批说明）——只按文件数上限分批。
    """
    batches: list[list[T]] = []
    current: list[T] = []
    size = 0
    for item in items:
        if max_chars is not None:
            if size_of is None or split_oversized is None:
                raise ValueError(
                    "max_chars 给定时必须同时提供 size_of 与 split_oversized"
                )
            item_size = size_of(item)
            if item_size > max_chars:
                # 单文件多版本合计超预算：按版本拆批（同批内不重复路径）
                for unit in split_oversized(item):
                    unit_size = size_of(unit)
                    if current and (
                        size + unit_size > max_chars
                        or len(current) >= JUDGMENT_BATCH_SIZE
                        or any(f.path == item.path for f in current)
                    ):
                        batches.append(current)
                        current = []
                        size = 0
                    current.append(unit)
                    size += unit_size
                continue
            if current and (
                size + item_size > max_chars
                or len(current) >= JUDGMENT_BATCH_SIZE
            ):
                batches.append(current)
                current = []
                size = 0
            current.append(item)
            size += item_size
        else:
            if current and len(current) >= JUDGMENT_BATCH_SIZE:
                batches.append(current)
                current = []
            current.append(item)
    if current:
        batches.append(current)
    return tuple(tuple(batch) for batch in batches)


@dataclass(frozen=True)
class TopicFramework:
    """题型确定性框架段（工单 topic-framework/03）：注入骨架 prompt 的结构化载体。

    code = 框架全文（framework/main.c，不经 LLM 改写）；topic_type = 题型
    （词表 TOPIC_TYPES 值）；source = 来源条目标题（prompt 展示用——id 与
    标题可能不同（编辑改标题时 id=目录名不变），展示用标题更贴近用户认知。
    """

    code: str
    topic_type: str
    source: str


# 买件方案商量的校核意见（工单 buy-discuss/01）：verdict 三档词表单源在
# selection（BUY_VERDICTS——llm 与 selection 同引一处，防环反向），词表外值
# 由解析器修正回 feasible——用户想法校核意见是展示增强，宁可不标也不阻断讨论。


@dataclass(frozen=True)
class BuyReview:
    """AI 对用户自定想法的可行性校核（用户说话 = 猜想，AI 校核 + 进一步沟通）。

    verdict = feasible | risky | infeasible；reason = 校核理由（为什么）；
    suggestion = 替代建议（可指向词表方案，字符串自由文本）。
    """

    verdict: str
    reason: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "suggestion": self.suggestion,
        }


@dataclass(frozen=True)
class BuyDiscussion:
    """一轮买件方案讨论的产物：回复文本 + （可选）用户自定方案校核意见。

    review 为 None（解析缺失 / 用户未提自定方案）= 仅回复，无校核意见。
    """

    reply: str
    review: BuyReview | None = None


@dataclass(frozen=True)
class TaskDiscussion:
    """一轮任务商量的产物：AI 的回应文本（工单 task-chat/02）。

    只有 reply——讨论是沟通不是选型（无 review 结构）；回应的内容结构
    （可行性判断 → 影响 → 建议）由系统提示词引导，不落结构化字段。
    """

    reply: str


@dataclass(frozen=True)
class StepReport:
    """一步任务执行后的步骤报告（工单 stepwise-deepen/01 + task-insight/01 +
    task-wiring-diagram/02）。

    what_changed = AI 本步做了什么（改了什么逻辑/函数、编译验证结果、任何
    降级/警告），中文叙事；user_action = 用户接下来需要做的物理动作（烧录、
    接线——具体到模块接口清单里的引脚/接口名，如「把 PA0 接到 LED 模块的
    DIO」、观察什么现象、确认后如何操作）；纯软件无物理动作时可空串。
    checklist = 上板自检清单（3-6 条原子勾选项——「应观察到什么；若不正常
    检查哪里」，随轮次落盘渲染为可勾选备忘录；纯软件步无物理动作 = 空元组）。
    wiring = 本步需要接的线（工单 task-wiring-diagram/02：结构化引用——
    AI 只能给名字，图形由确定性数据决定）。形状提取在解析层（机械过滤），
    查表合法性由 task_progress 层调用 wiring.filter_wiring_entries 判决
    （本字段 = 引用清单，非法条目由下游丢弃，全丢 = 空元组走退化路径）。
    """

    what_changed: str
    user_action: str = ""
    checklist: tuple[str, ...] = ()
    wiring: tuple[WiringEntry, ...] = ()


# 新想法 / 问题分类词表（单源：解析层校验与前端消费共用）
IDEA_KIND_NEW_TASK = "new_task"  # 新功能需求 → 生成任务卡插入清单
IDEA_KIND_DIRECT_FIX = "direct_fix"  # 直接修正现有代码
IDEA_KIND_DISCUSSION = "discussion"  # 先讨论（不动代码，漏斗态）
IDEA_KINDS = frozenset({IDEA_KIND_NEW_TASK, IDEA_KIND_DIRECT_FIX, IDEA_KIND_DISCUSSION})


@dataclass(frozen=True)
class IdeaAnalysis:
    """一个「新想法 / 问题」的分析产物（工单 idea-fix/01）。

    kind = new_task | direct_fix | discussion；reply = AI 对这个想法的理解与
    判断（中文）；new_task = new_task 类时的建议任务形状（title/description/
    score_refs/depends_on/verify，非 new_task = None）；fix_summary = 直接
    修正的建议说明（direct_fix 时非空，改动预览的输入上下文）；affected_task_ids
    = 受影响的既有任务 id（两类修正都填，无影响 = 空元组）。
    """

    kind: str
    reply: str
    new_task: Mapping[str, Any] | None = None
    fix_summary: str = ""
    affected_task_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "reply": self.reply,
            "new_task": dict(self.new_task) if self.new_task is not None else None,
            "fix_summary": self.fix_summary,
            "affected_task_ids": list(self.affected_task_ids),
        }


class LLM(Protocol):
    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
        manual_fulltexts: Mapping[str, str] | None = None,
        clarifications: Sequence[tuple[str, str]] = (),
        qa_material: str = "",
    ) -> ModuleSelection: ...

    def clarify(
        self, problem_text: str, clarifications: Sequence[tuple[str, str]]
    ) -> tuple[str, ...]: ...

    def preread_topic(self, problem_text: str) -> PrereadResult: ...

    def name_topic_english(self, problem_text: str) -> str: ...

    def generate_main_skeleton(
        self,
        problem_text: str,
        module_interfaces: Sequence[str],
        reference_fulltexts: Mapping[str, str] | None = None,
        topic_framework: TopicFramework | None = None,
    ) -> str: ...

    def generate_smoke_main(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str: ...

    def summarize_module(self, code: str) -> str: ...

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult: ...

    def fix_compile_errors(
        self,
        error_text: str,
        file_contexts: Mapping[str, str],
        *,
        problem_text: str = "",
        platform: str = "",
        module_slugs: Sequence[str] = (),
        main_c: str = "",
        dropped_files: Sequence[str] = (),
        previous_fixes: Sequence[Mapping[str, Any]] = (),
    ) -> tuple[FixSuggestion, ...]: ...

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None = None,
    ) -> tuple[FileDecision, ...]: ...

    def reference_summarize(self, material: str) -> str: ...

    def reference_judge_archivable(
        self, candidates: Sequence[ReferenceCandidate]
    ) -> tuple[str, ...]: ...

    def analyze_impact(
        self,
        problem_text: str,
        requirements: Sequence[Mapping[str, Any]],
        current_slugs: Sequence[str],
        manifest_summaries: Sequence[ManifestSummary],
        new_qa_text: str,
        qa_count: int | None = None,
    ) -> ImpactAnalysis: ...

    def deepen_main_c(
        self,
        main_c: str,
        requirements: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        problem_text: str,
        qa_text: str,
    ) -> str: ...

    def plan_tasks(
        self,
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        score_points: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
    ) -> TaskPlan: ...

    def execute_task(
        self,
        main_c: str,
        task: Mapping[str, Any],
        note: str,
        module_interfaces: Sequence[str],
        problem_text: str,
        qa_text: str,
        feedback: str = "",
        global_note: str = "",
    ) -> str: ...

    def discuss_buy_options(
        self,
        problem_text: str,
        requirement: str,
        platform: str,
        solutions: Sequence[SolutionOption],
        history: Sequence[tuple[str, str]],
    ) -> BuyDiscussion: ...

    def discuss_task(
        self,
        task: Mapping[str, Any],
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
        history: Sequence[tuple[str, str]],
    ) -> TaskDiscussion: ...

    def discuss_global_idea(
        self,
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        score_points: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
        plan: Mapping[str, Any] | None,
        global_note: str,
        history: Sequence[tuple[str, str]],
    ) -> TaskDiscussion: ...

    def discuss_params(
        self,
        problem_text: str,
        params: Sequence[Mapping[str, Any]],
        plan: Mapping[str, Any] | None,
        history: Sequence[tuple[str, str]],
    ) -> TaskDiscussion: ...

    def scan_params(
        self,
        main_c: str,
        module_interfaces: Sequence[str],
    ) -> ParamList: ...

    def report_task_step(
        self,
        task: Mapping[str, Any],
        verify_result: Mapping[str, Any],
        diff_text: str,
        module_interfaces: Sequence[str],
        wiring_summary: str = "",
    ) -> StepReport: ...

    def analyze_idea(
        self,
        idea: str,
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        score_points: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
        plan: Mapping[str, Any] | None,
    ) -> IdeaAnalysis: ...

    def apply_idea_fix(
        self,
        idea: str,
        fix_summary: str,
        affected: Sequence[str],
        module_interfaces: Sequence[str],
        problem_text: str,
        qa_text: str,
        main_c: str,
        global_note: str = "",
    ) -> str: ...

    def topic_split_topics(self, pdf_text: str) -> tuple[TopicDraft, ...]: ...

    def topic_extract_number(self, text: str) -> str | None: ...

    def generate_report_draft(
        self,
        problem_text: str,
        requirements: Sequence[Mapping[str, Any]],
        manifest_summaries: Sequence[ManifestSummary],
        pin_summary: str,
    ) -> tuple[str, str]: ...


class Transport(Protocol):
    """HTTP 传输接缝：生产用 urllib，测试注入假件。"""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> tuple[int, str, Mapping[str, str]]:
        """POST JSON，返回（HTTP 状态码, 响应体文本, 响应头）。"""


class UrllibTransport:
    """基于标准库 urllib 的传输实现（项目零第三方依赖）。"""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> tuple[int, str, Mapping[str, str]]:
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return (
                    response.status,
                    response.read().decode("utf-8"),
                    dict(response.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            # 4xx/5xx 是业务失败，状态码与 Retry-After 透传给调用方分类。
            return (
                exc.code,
                exc.read().decode("utf-8", errors="replace"),
                dict(exc.headers.items()) if exc.headers else {},
            )
        except (urllib.error.URLError, OSError) as exc:
            # 网络层瞬断（连接重置 10054 / 超时 / DNS 失败）→ 标记 network 类，
            # _retry_parse 据此走指数退避重试（工单 deepseek-retry-hardening/01）
            raise LLMError(
                f"无法连接 LLM 服务 {url}: {exc}", kind=ERROR_KIND_NETWORK
            ) from exc


def _backoff_sleep(seconds: float) -> None:
    """退避等待（独立函数 = 测试 monkeypatch 接缝，见 _retry_parse）。

    网络重试不可真睡 1+2+4+8s：tests/test_llm.py monkeypatch 本函数记录
    序列——比直接打 llm 命名空间的 time.sleep 更窄，不污染全局 time 模块。
    """
    time.sleep(seconds)


def _http_error_kind(status: int) -> str:
    """HTTP 状态 → 重试分类（观测与重试分支同源）。"""
    if status == 429:
        return ERROR_KIND_RATE_LIMIT
    if status >= 500:
        return ERROR_KIND_NETWORK
    return ERROR_KIND_CLIENT


def _retry_after_seconds(
    headers: Mapping[str, str], *, now: Callable[[], float] = time.time
) -> float | None:
    """Retry-After 头解析：秒数或 HTTP-date；非法 / 缺失返回 None。"""
    raw = next((value for name, value in headers.items() if name.lower() == "retry-after"), None)
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(raw).timestamp() - now())
        except (TypeError, ValueError):
            return None


def _raise_retry_exhausted(label: str, attempts: int, last_error: Exception | None) -> NoReturn:
    """重试耗尽时保留最后一次错误分类，避免包装后退回 parse。"""
    kind = last_error.kind if isinstance(last_error, LLMError) else ERROR_KIND_PARSE
    retry_after = last_error.retry_after if isinstance(last_error, LLMError) else None
    raise LLMError(
        f"{label}连续 {attempts} 次调用失败：{last_error}",
        kind=kind,
        retry_after=retry_after,
    ) from last_error


def _unwrap_json_fence(content: str) -> str:
    """剥掉 Markdown 代码围栏外层（工单 local-llm-json-group/01，唯一出处）。

    仅当**整个输出**就是一个完整的 Markdown 代码围栏块（首行 ``` 或 ```lang
    开头、末行 ``` 结尾、中间不含围栏行）时剥掉外层返回内部文本；非围栏 /
    只有开头没结尾 / 内部含围栏行 / 空内容一律原样返回——绝不错伤合法内容。
    合法 JSON 文档不可能以反引号开头，故"首行 ``` 才剥"天然不会误伤合法
    JSON；中间出现整行 ```（嵌套/错乱围栏）无法可靠判结构，保守不剥。

    与 clex.strip_code_fences 分工不同（本函数是 JSON 输出的整体围栏判定，
    不共用其 C 源码围栏谓词——见 CONTEXT「C 词法层」；spec 定本函数为 llm 的
    唯一出处，不引 clex）：clex 剥 C 源码**首尾围栏行**（中间围栏可能是原文
    信息），这里要求**整个输出**恰为一个围栏块，多一行围栏/多一行尾随内容都
    拒绝剥——"绝不错伤"的判据不同，故独立实现。
    """
    text = content.strip()
    if not text:
        return content
    lines = text.split("\n")
    if len(lines) < 3:
        return content
    opening = lines[0].rstrip()
    if not opening.startswith("```") or "```" in opening[3:]:
        return content
    if lines[-1].strip() != "```":
        return content
    if any(line.strip().startswith("```") for line in lines[1:-1]):
        return content
    return "\n".join(lines[1:-1])


class DeepSeekLLM:
    """生产 LLM：调用 DeepSeek Chat Completions，结构化输出解析为 ModuleSelection。"""

    # 大批量判定 JSON 的生成时间实测可超 120 秒（判例 08：真实工程一批 25 个
    # 文件读全文出摘要，DeepSeek 生成 JSON 需要 2-5 分钟）——120 秒读超时会让
    # 提炼流程整段失败。300 秒对单批生成足够，网络瞬断仍是偶发失败（大声报错）。
    TIMEOUT_SECONDS = 300

    def __init__(
        self,
        config: AppConfig,
        transport: Transport | None = None,
        hardware_words: Sequence[HardwareWordGroup] | None = None,
        provider: str = "remote",
        retry_budget: RetryBudget | None = None,
        observation_collector: LLMObservationCollector | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or UrllibTransport()
        self._provider = provider
        self._retry_budget = retry_budget
        self._observation_collector = observation_collector
        self._call_sequence = 0
        # 硬件词表：库外建议 name 的校验源 + 提示词科普素材；缺省用包内默认
        # 词表（wordlist.json，可手补），测试可注入自定义词表
        self._hardware_words = (
            DEFAULT_WORDLIST if hardware_words is None else tuple(hardware_words)
        )

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
        manual_fulltexts: Mapping[str, str] | None = None,
        clarifications: Sequence[tuple[str, str]] = (),
        qa_material: str = "",
    ) -> ModuleSelection:
        """赛题 → 模块选择（工单 03 起带参考文件两级注入的清单 / 全文两个形态）。

        references = 该赛题 / 套件关联的参考文件清单（标题 + 一句话简介，
        两级注入第一级）；reference_fulltexts = 模型点名要读全文的参考文件
        （id → 全文，第二级）；manual_fulltexts = 用户手动指定的参考文件
        （id → 全文，工单 01 手动选参考资料——全文直读强制，无需模型点名）。
        三者都缺时行为与既有实现完全一致（提示词无参考段、输出契约无
        references 字段）。

        clarifications = 用户已澄清的问答历史（题面证据不足处的 Q/A，工单
        clarify-history-in-convergence：收敛循环每轮透传）——题面后的独立段
        （Q/A 逐条、不带编号、不并入题面），题面逐句编号跨轮稳定不受影响；
        缺省空 = 旧行为（无历史段）。

        工单 10 起输出功能需求层（requirements / suggestions / questions），
        顶层 modules 由需求层机械得出（build_module_selection，域判决在
        selection.py）；硬件词表进提示词作科普素材、作库外建议 name 的校验源。

        多实例推荐（工单 module-multi-instance/06）：模块清单行带「多实例」
        标注（ManifestSummary.to_line），模型按题面猜实例数输出 instances，
        解析层按同源能力清单校验（multi_instance_slugs——非多实例模块带
        instances = 幻觉，大声失败）。

        瞬时失败整次重问（_retry_parse，与归档判定同款兜底）：DeepSeek 偶发
        空内容 / 输出畸形会重问，最多 SUMMARY_RETRY_LIMIT 轮，仍失败大声抛错。
        """

        def parse(content: str) -> ModuleSelection:
            # 输出失控守卫（工单 llm-select-runaway/01）：deepseek-v4-flash 曾
            # 无上限输出 ~20K tokens/次（逐句分析/自检过程写进 JSON），超长必然
            # 解析失败且单次等待 ~160s。超过合理输出量级 = 模型退化/循环——
            # 报 client 错误免重试（_retry_parse 对 client break），不再重复烧钱
            # 烧时间。配合请求侧 max_tokens 截断双保险。
            if len(content) > SELECT_MAX_OUTPUT_CHARS:
                raise LLMError(
                    "模块选择输出异常超长（"
                    f"{len(content)} 字符 > {SELECT_MAX_OUTPUT_CHARS}）："
                    "疑似模型输出退化或循环（逐句分析写进 JSON），放弃重试——"
                    "请重试或检查模型配置",
                    kind=ERROR_KIND_CLIENT,
                )
            data = extract_module_selection_data(content)
            # 核验轮短标记（工单 01）：{"converged": true} = 模型自报与上一轮
            # 一致——无需求层可判，跳过域判决直接返回空选择（收敛驱动层据此
            # 用上一轮结果提前停）；严格 true 才算，false / 缺字段照常走判决
            if isinstance(data, Mapping) and data.get("converged") is True:
                return ModuleSelection(modules=(), reasons={}, converged=True)
            try:
                return build_module_selection(
                    data,
                    known_slugs=[s.slug for s in manifest_summaries],
                    known_reference_ids=[r.id for r in references],
                    hardware_words=self._hardware_words,
                    # 多实例能力清单（工单 module-multi-instance/06）：
                    # ManifestSummary.multi_instance 与清单行标注同源——模型
                    # 只在能力模块上猜实例数，解析层按同清单做能力校验
                    multi_instance_slugs=[
                        s.slug for s in manifest_summaries if s.multi_instance
                    ],
                )
            except SelectionError as exc:
                # 域判决错误由传输侧翻译回 LLMError（错误契约 502 / 文案逐字不变；
                # selection 不 import LLMError——否则与 llm → selection 既有边成环；
                # 翻译在闭包内，重试循环吃的是翻译后的 LLMError）。
                # kind=client 免重试（工单 select-domain-reject/01）：域拒绝 =
                # 模型输出与库内事实的客观矛盾（如给非多实例模块带 instances、
                # 幻觉模块名）——同参数重试模型稳定输出同样的幻觉（2021F 实测
                # digit_uart 连续 5 轮同样带 instances），重试只烧钱烧时间；
                # 报 client 错误立即结束，用户可重试或调整题面。
                raise LLMError(str(exc), kind=ERROR_KIND_CLIENT) from exc

        return self._retry_parse(
            system_prompt=SELECT_SYSTEM_PROMPT,
            user_prompt=_selection_user_prompt(
                problem_text,
                manifest_summaries,
                references,
                reference_fulltexts,
                manual_fulltexts,
                self._hardware_words,
                clarifications,
                qa_material,
            ),
            parse=parse,
            label="模块选择",
            operation="select_modules",
            json_mode=True,
            max_tokens=SELECT_MAX_OUTPUT_TOKENS,
            # 关闭思考模式（工单 select-truncation/01）：v4-flash 思考默认开
            # （effort=high），select 的「逐句对照/反复自检」要求让推理模型
            # 深度推理且循环不收敛——max_tokens 全被 reasoning_content 吃掉、
            # content 为空（finish_reason=length，实测 4096/16384 皆截断）→
            # 「模型返回的不是 JSON」连续 5 次失败。select 是确定性 JSON 任务，
            # 不需要思维链：关闭后 content 直接输出，等待 / 成本 / 截断齐解。
            thinking_disabled=True,
        )

    def clarify(
        self, problem_text: str, clarifications: Sequence[tuple[str, str]]
    ) -> tuple[str, ...]:
        """澄清阶段（工单 01 推荐先澄清后收敛）：只看题面 + 已有问答历史，
        输出仍存的疑问（空元组 = 澄清完成，可进收敛循环）。

        不带模块库——疑问只来自题面证据不足，与库内实现无关（库内有没有实现
        是收敛阶段的事，省一轮完整分析的成本）。历史逐条 "Q: … A: …" 送模型，
        避免重复问已回答过的问题；json_mode 解析 {"questions": [...]}，空数组
        = 无疑问（parse_clarify_questions，严格解析畸形输出）。

        瞬时失败整次重问（_retry_parse，与 select_modules 同款兜底）：空内容 /
        畸形输出重问至多 SUMMARY_RETRY_LIMIT 轮，仍失败大声抛错。
        """
        return self._retry_parse(
            system_prompt=CLARIFY_SYSTEM_PROMPT,
            user_prompt=_clarify_user_prompt(problem_text, clarifications),
            parse=parse_clarify_questions,
            label="澄清",
            json_mode=True,
        )

    def preread_topic(self, problem_text: str) -> PrereadResult:
        """赛题 → 赛题预读产物（一句话总览 + 决策点提醒，预读步骤）。

        预读题面给用户"题面已经锁死了什么"的认知（wait-what 效果 + 后续
        决策步骤提醒）：只展示、不进任何下游流程；赛题超长截断带标注
        （_truncate_content，与所有嵌内容调用同款预算）；结构化 JSON +
        机械校验（topic_preread.normalize_preread，引用必须命中题面）；
        瞬时失败整次重问（_retry_parse 兜底）。
        """
        return self._retry_parse(
            system_prompt=PREREAD_SYSTEM_PROMPT,
            user_prompt=_truncate_content(problem_text),
            parse=lambda content: parse_preread(content, problem_text),
            label="赛题预读",
            json_mode=True,
        )

    def name_topic_english(self, problem_text: str) -> str:
        """赛题题面 → 英文目录短名（工单 ascii-project-name/02，目录名用）。

        粘贴自定义题面生成时目录名取 AI 英文短名（如 Auto_Car）：题面超长
        截断带标注（_truncate_content，与所有嵌内容调用同款预算）；瞬时失败
        整次重问（_retry_parse，与模块简介同款兜底）；输出为纯文本短名，
        仅当整段非空才接受。
        """
        def parse(content: str) -> str:
            if not content.strip():
                raise LLMError("英文短名生成返回空内容")
            return content.strip()

        return self._retry_parse(
            system_prompt=TOPIC_EN_NAME_SYSTEM_PROMPT,
            user_prompt=_truncate_content(problem_text),
            parse=parse,
            label="英文短名生成",
        )

    def generate_main_skeleton(
        self,
        problem_text: str,
        module_interfaces: Sequence[str],
        reference_fulltexts: Mapping[str, str] | None = None,
        topic_framework: TopicFramework | None = None,
    ) -> str:
        def parse(content: str) -> str:
            if not content.strip():
                raise LLMError("骨架 main.c 生成返回空内容")
            return content

        return self._retry_parse(
            system_prompt=SKELETON_SYSTEM_PROMPT,
            user_prompt=_skeleton_user_prompt(
                problem_text,
                module_interfaces,
                reference_fulltexts,
                topic_framework,
            ),
            parse=parse,
            label="骨架 main.c 生成",
        )

    def generate_smoke_main(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str:
        def parse(content: str) -> str:
            if not content.strip():
                raise LLMError("冒烟 main.c 生成返回空内容")
            return content

        return self._retry_parse(
            system_prompt=SMOKE_SYSTEM_PROMPT,
            user_prompt=_smoke_user_prompt(problem_text, module_interfaces),
            parse=parse,
            label="冒烟 main.c 生成",
        )

    def summarize_module(self, code: str) -> str:
        return self._retry_parse(
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            user_prompt=f"```c\n{_truncate_content(code)}\n```",
            parse=lambda content: content,
            label="模块简介生成",
            operation="summarize_module",
        )

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult:
        return self._retry_parse(
            system_prompt=VALIDATION_SYSTEM_PROMPT,
            user_prompt=_validation_user_prompt(description, code),
            parse=parse_validation_result,
            label="简介一致性校验",
            operation="validate_module_description",
            json_mode=True,
        )

    def fix_compile_errors(
        self,
        error_text: str,
        file_contexts: Mapping[str, str],
        *,
        problem_text: str = "",
        platform: str = "",
        module_slugs: Sequence[str] = (),
        main_c: str = "",
        dropped_files: Sequence[str] = (),
        previous_fixes: Sequence[Mapping[str, Any]] = (),
    ) -> tuple[FixSuggestion, ...]:
        """编译报错修复建议（工单 compile-error-fix/01，json_mode）。

        报错全文 + 命中文件内容 + 题面 / 平台 / 模块 / main.c → 逐条 snippet
        替换建议（FixSuggestion）。previous_fixes（工单 fix-loop-progress/01）
        = 上一轮应用结果，渲染进用户消息独立段（空 = 无该段零回归）。严格
        解析：file 必须在提供的文件清单内、old_snippet 非空——畸形输出 /
        瞬时失败整次重问（_retry_parse ≤SUMMARY_RETRY_LIMIT 轮，与归档判定同款兜底）；域判决
        （路径白名单 / 精确匹配 / 备份回滚）在 fix_errors.py，本模块只做机械
        提取。
        """
        return self._retry_parse(
            system_prompt=FIX_SYSTEM_PROMPT,
            user_prompt=_fix_errors_user_prompt(
                error_text=error_text,
                file_contexts=file_contexts,
                dropped_files=dropped_files,
                problem_text=problem_text,
                platform=platform,
                module_slugs=module_slugs,
                main_c=main_c,
                previous_fixes=previous_fixes,
            ),
            parse=lambda content: parse_fix_suggestions(
                content, tuple(file_contexts)
            ),
            label="编译错误修复",
            json_mode=True,
            operation="fix_compile_errors",
        )

    def _retry_parse(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        parse: Callable[[str], RT],
        label: str,
        operation: str | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
        thinking_disabled: bool = False,
    ) -> RT:
        """整次调用级重试（单调用契约共用原语，与批处理 _retry_batch 同哲学）。

        HTTP / 网络错误由 _chat_once 先观测并分类；模型内容解析 / 领域校验在本层
        观测为 parse_error，避免把空内容 / 畸形 JSON / 领域拒绝记成成功调用。
        max_tokens = 输出上限（None = 不带字段，服务端默认）。
        thinking_disabled = 关闭思考模式（推理模型默认开且 effort=high，确定性
        JSON 任务会深度推理吃掉 max_tokens、content 为空——select 用）。
        """
        last_error: Exception | None = None
        attempts = 0
        network_failures = 0
        result: _ChatResult | None = None
        while attempts < NETWORK_RETRY_LIMIT:
            attempts += 1
            try:
                result = self._chat_once(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    json_mode=json_mode,
                    operation=operation or label,
                    attempt_number=attempts,
                    observe_success=False,
                    max_tokens=max_tokens,
                    thinking_disabled=thinking_disabled,
                )
                try:
                    parsed = parse(result.content)
                except LLMError as exc:
                    self._observe_chat_result(
                        result,
                        status="error",
                        parse_status="parse_error",
                        error_kind=exc.kind,
                    )
                    raise
                self._observe_chat_result(
                    result, status="success", parse_status="success"
                )
                return parsed
            except LLMError as exc:
                last_error = exc
                # 截断 = 参数性确定性失败（工单 select-truncation/01）：输出被
                # max_tokens 上限截断（finish_reason=length，推理模型下 content
                # 常为空串）——同参数重试必然同样截断，报 client 错误免重试，
                # 不再重复烧钱烧时间（曾 5 次重试全截断 = 「模型返回的不是 JSON」
                # 连续失败）。仅当本轮真实拿到截断响应且错误是解析类时转化
                # （字符超长守卫已是 client 错误，不重复包装）。
                if (
                    result is not None
                    and result.finish_reason == "length"
                    and exc.kind == ERROR_KIND_PARSE
                ):
                    last_error = LLMError(
                        "模型输出被 max_tokens 上限截断（finish_reason=length，"
                        "推理模型下 reasoning 与 content 共享上限、content 常为"
                        "空）——重试必然同样截断，已放弃重试；请重试或检查模型"
                        "配置",
                        kind=ERROR_KIND_CLIENT,
                    )
                    break
                if exc.kind in (ERROR_KIND_CLIENT, ERROR_KIND_BUDGET):
                    if exc.kind == ERROR_KIND_BUDGET:
                        raise
                    break
                if exc.kind == ERROR_KIND_RATE_LIMIT:
                    if attempts >= NETWORK_RETRY_LIMIT:
                        break
                    _backoff_sleep(
                        exc.retry_after if exc.retry_after is not None else 1.0
                    )
                elif exc.kind == ERROR_KIND_NETWORK:
                    network_failures += 1
                    if attempts >= NETWORK_RETRY_LIMIT:
                        break
                    _backoff_sleep(2 ** (network_failures - 1))
                elif attempts >= SUMMARY_RETRY_LIMIT:
                    break
        _raise_retry_exhausted(label, attempts, last_error)

    def reference_summarize(self, material: str) -> str:
        """配套资料（例程工程 / 说明书等）→ 中文简介草稿（文本模式，工单 02）。

        素材超长截断带标注（_truncate_content，与所有嵌内容调用同款预算）；
        瞬时失败整次重问（_retry_parse，与归档判定同款兜底）。
        """
        return self._retry_parse(
            system_prompt=REFERENCE_SUMMARY_SYSTEM_PROMPT,
            user_prompt=_truncate_content(material),
            parse=lambda content: content,
            label="参考文件简介生成",
        )

    def generate_report_draft(
        self,
        problem_text: str,
        requirements: Sequence[Mapping[str, Any]],
        manifest_summaries: Sequence[ManifestSummary],
        pin_summary: str,
    ) -> tuple[str, str]:
        """设计报告草稿 LLM 输出层（工单 report-draft-demo/03）：结构化输出
        {rationale: 方案论证, workflow: 软件流程}。

        输入 = 赛题原文 + 功能需求清单 + 模块摘要 + 引脚表摘要（全部由调用方
        装配，本操作只拼提示词与解析）。输出经 _parse_report_draft 严格解析
        （缺键 / 非字符串拒绝）；畸形输出 / 瞬时失败整次重问（_retry_parse，
        与归档判定同款兜底）——LLMError 由调用方捕获降级（空文本 + 报告占位
        节），不抛生成主链。workflow 契约 = 单段（渲染器按 \\n\\n 分段、最后
        一段 = 软件流程，提示词已约束段内不用空行）。
        """
        return self._retry_parse(
            system_prompt=REPORT_DRAFT_SYSTEM_PROMPT,
            user_prompt=_report_draft_user_prompt(
                problem_text, requirements, manifest_summaries, pin_summary
            ),
            parse=_parse_report_draft,
            label="设计报告草稿生成",
            json_mode=True,
        )

    def reference_judge_archivable(
        self, candidates: Sequence[ReferenceCandidate]
    ) -> tuple[str, ...]:
        """归档判定：被剔除的业务代码是否值得归档为该赛题的参考文件（json_mode）。

        返回值得归档的路径子集（可为空 = 没有文件值得归档）。输出经
        parse_archive_judgment 严格解析（词表外 / 重复路径拒绝，畸形抛
        LLMError——模型输出不可信，宁可大声失败也不带病进入归档流程）；
        畸形输出 / 瞬时失败整次重问（_retry_parse）。
        """
        return self._retry_parse(
            system_prompt=ARCHIVE_JUDGMENT_SYSTEM_PROMPT,
            user_prompt=_archive_judgment_user_prompt(candidates),
            parse=lambda content: parse_archive_judgment(
                content, [c.path for c in candidates]
            ),
            label="归档判定",
            json_mode=True,
        )

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None = None,
    ) -> tuple[FileDecision, ...]:
        """两阶段判定：先逐文件读全文出摘要，再基于摘要判定（两次 json_mode 调用）。

        兑现 ADR 0001 的"读内容判断"——判定素材含文件内容摘要，不再只有路径
        与配置摘要。第一阶段产物（摘要）只作为第二阶段输入，不进报告；判定
        条目的 reason 由 AI 带上摘要要点。两阶段产物都走严格解析，畸形 / 缺
        摘要抛 LLMError，宁可大声失败也不带病进确认流程。

        progress_emitter：可选进度发射器（默认 None 不发射，行为与现状一致）。
        start 由入口发射且总量先算定——阶段 1 批数 = _batches 算定的批数、
        阶段 2 批数 = ⌈摘要批内条目总和 / 批大小⌉（与 _decide_distillation
        实发批序同一 _batches 原语推导，见下方注释）；算定后同一批序列传给
        阶段循环，start 的批次总量与实际发射的批序列严格一致（契约测试断言）。
        发射失败是旁路（_emit），不影响提炼主流程。
        """
        summary_batches = _batches(
            judgment_files,
            max_chars=MAX_SUMMARY_BATCH_CHARS,
            size_of=_file_chars,
            split_oversized=_split_versions,
        )
        # 判定批数单源化：判定阶段 = 摘要产物按批大小分块（_decide_distillation
        # 内同一 _batches 原语、max_chars=None），摘要产物数 = 摘要批内条目总和
        # （批覆盖完整、一条目一摘要，与 _summarize_judgment_files 产物一一对应）
        # ——从同一批序列推导，杜绝独立公式与实发批序分叉（超预算按版本拆批时
        # 旧公式按 judgment_files 数算会少报，契约：start 总量 = 实际批序列）。
        decide_batch_count = math.ceil(
            sum(len(batch) for batch in summary_batches) / JUDGMENT_BATCH_SIZE
        )
        _emit(
            progress_emitter,
            ProgressEvent(
                type=EVENT_START,
                judgment_count=len(judgment_files),
                summary_batch_count=len(summary_batches),
                decide_batch_count=decide_batch_count,
            ),
        )
        file_summaries = self._summarize_judgment_files(
            platform, project_names, judgment_files, summary_batches, progress_emitter
        )
        return self._decide_distillation(
            platform, project_names, file_summaries, comparison_summary, progress_emitter
        )

    def _summarize_judgment_files(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        summary_batches: Sequence[Sequence[JudgmentFile]],
        progress_emitter: ProgressEmitter | None,
    ) -> tuple[FileSummary, ...]:
        """第一阶段：逐文件读全文出摘要（json_mode），解析校验为 FileSummary。

        大批量素材一次问完时，模型输出偶发丢条目 / JSON 截断（判例 08：真实
        工程 115 个文件一次返回漏 1 个；更大批量甚至系统性漏小配置文件，补问
        不收敛）。按请求体预算（MAX_SUMMARY_BATCH_CHARS，防网关 413）与文件数
        上限（JUDGMENT_BATCH_SIZE，防模型批量超载）分批问（_batches 原语，
        总输入 token 不变），批内严格解析失败后挖出已覆盖的合法条目、只对
        缺失文件补问，最多 SUMMARY_RETRY_LIMIT 轮——宁可在补问上多花一次调用，
        也不带病进第二阶段。

        批次循环层发射进度事件（契约唯一出处见 ProgressEvent）：每批开始发
        batch_start（带该批文件路径清单）、批完成发 batch_done（累计已处理文件
        数）、阶段结束发 phase_done；批数为 0 时不发射任何批事件，阶段直接完成。
        """
        results: list[FileSummary] = []
        for batch_index, batch in enumerate(summary_batches, start=1):
            _emit(
                progress_emitter,
                ProgressEvent(
                    type=EVENT_BATCH_START,
                    phase=PHASE_SUMMARY,
                    batch_index=batch_index,
                    batch_count=len(summary_batches),
                    paths=tuple(f.path for f in batch),
                ),
            )
            results.extend(
                self._summarize_batch(
                    platform, project_names, batch, progress_emitter, batch_index
                )
            )
            _emit(
                progress_emitter,
                ProgressEvent(
                    type=EVENT_BATCH_DONE,
                    phase=PHASE_SUMMARY,
                    batch_index=batch_index,
                    processed_count=len(results),
                ),
            )
        _emit(
            progress_emitter,
            ProgressEvent(
                type=EVENT_PHASE_DONE, phase=PHASE_SUMMARY, file_count=len(results)
            ),
        )
        return tuple(results)

    def _retry_batch(
        self,
        *,
        system_prompt: str,
        user_prompt: Callable[[Sequence[I]], str],
        parse: Callable[[str, Sequence[I]], Sequence[R]],
        salvage: Callable[[str, Sequence[I]], Sequence[R]],
        phase_label: str,
        items: Sequence[I],
        progress_emitter: ProgressEmitter | None,
        batch_index: int,
        phase: str,
    ) -> list[R]:
        """一批条目的重试 + 补问循环（摘要 / 判定两阶段共用的唯一原语）。

        批处理与 _retry_parse 共享错误分类：4xx client 不重试，429 读 Retry-After，
        网络 / 5xx 指数退避，预算耗尽立即抛出；输出畸形 / 漏条目仍走原有有限
        补问策略，且解析异常不会被记成成功观测。
        """
        remaining = list(items)
        results: list[R] = []
        retry_round = 0
        attempts = 0
        network_failures = 0
        last_error: Exception | None = None
        while remaining and attempts < NETWORK_RETRY_LIMIT:
            if retry_round:
                _emit(
                    progress_emitter,
                    ProgressEvent(
                        type=EVENT_RETRY,
                        phase=phase,
                        batch_index=batch_index,
                        retry_round=retry_round,
                        missing_count=len(remaining),
                    ),
                )
            retry_round += 1
            attempts += 1
            try:
                result = self._chat_once(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt(remaining)},
                    ],
                    json_mode=True,
                    operation=phase_label,
                    attempt_number=attempts,
                    observe_success=False,
                )
            except LLMError as exc:
                last_error = exc
                if exc.kind == ERROR_KIND_BUDGET:
                    raise
                if exc.kind == ERROR_KIND_CLIENT:
                    break
                if exc.kind == ERROR_KIND_RATE_LIMIT:
                    if attempts >= NETWORK_RETRY_LIMIT:
                        break
                    _backoff_sleep(
                        exc.retry_after if exc.retry_after is not None else 1.0
                    )
                    continue
                if exc.kind == ERROR_KIND_NETWORK:
                    network_failures += 1
                    if attempts >= NETWORK_RETRY_LIMIT:
                        break
                    _backoff_sleep(2 ** (network_failures - 1))
                    continue
                if attempts >= SUMMARY_RETRY_LIMIT:
                    break
                continue
            observed = False
            try:
                parsed = parse(result.content, remaining)
            except LLMError as exc:
                last_error = exc
                if exc.kind == ERROR_KIND_BUDGET:
                    raise
                if exc.kind == ERROR_KIND_CLIENT:
                    self._observe_chat_result(
                        result,
                        status="error",
                        parse_status="parse_error",
                        error_kind=exc.kind,
                    )
                    break
                # 输出整体不可用（非 JSON / 形状错）——挖出合法条目只补问坏的，
                # 一个都挖不出才按解析类有限重试。
                parsed = salvage(result.content, remaining)
                self._observe_chat_result(
                    result,
                    status="error",
                    parse_status="partial" if parsed else "parse_error",
                    error_kind=exc.kind,
                )
                observed = True
                if not parsed:
                    if attempts >= SUMMARY_RETRY_LIMIT:
                        break
                    continue
            results.extend(
                x for x in parsed if x.path not in {r.path for r in results}
            )
            covered = {r.path for r in results}
            missing = [x for x in remaining if x.path not in covered]
            if not missing:
                if not observed:
                    self._observe_chat_result(
                        result, status="success", parse_status="success"
                    )
                remaining = []
                break
            if not observed:
                self._observe_chat_result(
                    result,
                    status="error",
                    parse_status="partial",
                    error_kind=ERROR_KIND_PARSE,
                )
                last_error = LLMError(f"{phase_label}缺失 {len(missing)} 个条目")
            remaining = missing  # 漏判部分——只补问缺失路径
            if attempts >= SUMMARY_RETRY_LIMIT:
                break
        if remaining:
            detail = "、".join(sorted(x.path for x in remaining))[:300]
            if last_error is not None:
                kind = last_error.kind if isinstance(last_error, LLMError) else ERROR_KIND_PARSE
                retry_after = (
                    last_error.retry_after if isinstance(last_error, LLMError) else None
                )
                raise LLMError(
                    f"{phase_label}多次补问后仍缺失 {detail}：{last_error}",
                    kind=kind,
                    retry_after=retry_after,
                ) from last_error
            raise LLMError(f"{phase_label}多次补问后仍缺失 {detail}")
        return results

    def _summarize_batch(
        self,
        platform: str,
        project_names: Sequence[str],
        batch: Sequence[JudgmentFile],
        progress_emitter: ProgressEmitter | None,
        batch_index: int,
    ) -> list[FileSummary]:
        """一批文件的摘要 + 补问循环（见 _summarize_judgment_files 的分批说明）。

        参数化 _retry_batch（retry 事件发射在原语内，phase=summary）。
        """
        return self._retry_batch(
            system_prompt=JUDGMENT_SUMMARY_SYSTEM_PROMPT,
            user_prompt=lambda remaining: _summarize_user_prompt(
                platform, project_names, remaining
            ),
            parse=parse_summary_report,
            salvage=_extract_good_summaries,
            phase_label="第一阶段摘要",
            items=batch,
            progress_emitter=progress_emitter,
            batch_index=batch_index,
            phase=PHASE_SUMMARY,
        )

    def _decide_distillation(
        self,
        platform: str,
        project_names: Sequence[str],
        file_summaries: Sequence[FileSummary],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None,
    ) -> tuple[FileDecision, ...]:
        """第二阶段：基于摘要判定（json_mode），与第一阶段同款分批 + 补问机制。

        判定条数 = 待判文件数，同样可能被模型丢条目 / 截断（批量超载时系统性
        漏判，见 JUDGMENT_BATCH_SIZE）——按批问、批内漏判只补问缺失路径，
        保证返回的判定恰好覆盖全部待判文件（路径完整性由 master.assemble_
        report 再兜底校验）。
        判定按"已处理批的素材路径"过滤 + 全局去重（判例 08：提示词带完整结构
        对比清单，模型会幻觉复述其他批已判的路径、编造素材外路径（code/pid_
        debug.h）、或提前输出未处理批的路径——前两者让 assemble_report 的
        "多次判定"/"对比范围外路径"校验失败，提前输出则没读过该路径的摘要、
        判定不可信，还会挤掉该批正规判定）。只有"本批读过摘要"的判定收下；
        真实路径的漏判仍由批内补问兜底，过滤不会掩盖漏判。

        与第一阶段同款发射进度事件：批开始 batch_start（批文件清单 = 摘要路径）、
        批完成 batch_done（累计已处理文件数 = 已入批循环的文件累计数——判定
        会被素材范围过滤，不能按结果条数算）、阶段结束 phase_done。
        """
        results: list[FileDecision] = []
        seen: set[str] = set()
        batches = _batches(file_summaries, max_chars=None)
        processed = 0
        for batch_index, batch in enumerate(batches, start=1):
            _emit(
                progress_emitter,
                ProgressEvent(
                    type=EVENT_BATCH_START,
                    phase=PHASE_DECIDE,
                    batch_index=batch_index,
                    batch_count=len(batches),
                    paths=tuple(s.path for s in batch),
                ),
            )
            batch_paths = {s.path for s in batch}
            for decision in self._decide_batch(
                platform,
                project_names,
                batch,
                comparison_summary,
                progress_emitter,
                batch_index,
            ):
                if decision.path in batch_paths and decision.path not in seen:
                    seen.add(decision.path)
                    results.append(decision)
            processed += len(batch)
            _emit(
                progress_emitter,
                ProgressEvent(
                    type=EVENT_BATCH_DONE,
                    phase=PHASE_DECIDE,
                    batch_index=batch_index,
                    processed_count=processed,
                ),
            )
        _emit(
            progress_emitter,
            ProgressEvent(
                type=EVENT_PHASE_DONE,
                phase=PHASE_DECIDE,
                file_count=len(file_summaries),
            ),
        )
        return tuple(results)

    def _decide_batch(
        self,
        platform: str,
        project_names: Sequence[str],
        batch: Sequence[FileSummary],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None,
        batch_index: int,
    ) -> list[FileDecision]:
        """一批文件的判定 + 补问循环（见 _decide_distillation 的分批说明）。

        参数化 _retry_batch：判定阶段的严格解析不校验覆盖（master 层职责），
        补问只问缺失路径；素材范围外的判定由 _decide_distillation 按批过滤
        （retry 事件发射在原语内，phase=decide）。
        """
        return self._retry_batch(
            system_prompt=DISTILL_SYSTEM_PROMPT,
            user_prompt=lambda remaining: _distill_user_prompt(
                platform, project_names, remaining, comparison_summary
            ),
            parse=lambda content, remaining: parse_distillation_report(
                content, project_names
            ),
            salvage=lambda content, remaining: _extract_good_decisions(
                content, project_names, remaining
            ),
            phase_label="提炼判定",
            items=batch,
            progress_emitter=progress_emitter,
            batch_index=batch_index,
            phase=PHASE_DECIDE,
        )

    def topic_split_topics(self, pdf_text: str) -> tuple[TopicDraft, ...]:
        """短全文（≤ TOPIC_SPLIT_LLM_CHAR_CAP）单次调 LLM 拆条，json_mode +
        严格解析。全文全量直传不截断（截断 = flash 模型静默漏题根因之一）；
        超长全文应走 topic_library.split_topics_document 确定性分块——这里
        收到超长输入 = 调用方未按路由契约，请求发出前大声失败（与
        MAX_REQUEST_BYTES 兜底同哲学）。
        """
        if len(pdf_text) > TOPIC_SPLIT_LLM_CHAR_CAP:
            raise LLMError(
                f"拆条调用收到超长全文（{len(pdf_text)} 字符 > "
                f"{TOPIC_SPLIT_LLM_CHAR_CAP} 字符）：应走确定性分块"
                "（topic_library.split_topics_document），把全文塞给模型会因"
                "输出预算截断而静默漏题"
            )
        return self._retry_parse(
            system_prompt=TOPIC_SPLIT_SYSTEM_PROMPT,
            user_prompt=_topic_split_user_prompt(pdf_text),
            parse=parse_topic_split,
            label="赛题拆条",
            operation="topic_split_topics",
            json_mode=True,
        )

    def topic_extract_number(self, text: str) -> str | None:
        """从文本提取赛题编号（如 "2026C"）；不是赛题文本返回 None。

        与编号解析服务配套（topic_library.resolve_number 做确定性查库）：
        粘贴题面自动识别编号时走这里，AI 提取出的编号仍以查库结果为准。
        """
        return self._retry_parse(
            system_prompt=TOPIC_NUMBER_SYSTEM_PROMPT,
            user_prompt=_topic_number_user_prompt(text),
            parse=parse_topic_number,
            label="赛题编号提取",
            operation="topic_extract_number",
            json_mode=True,
        )

    def analyze_impact(
        self,
        problem_text: str,
        requirements: Sequence[Mapping[str, Any]],
        current_slugs: Sequence[str],
        manifest_summaries: Sequence[ManifestSummary],
        new_qa_text: str,
        qa_count: int | None = None,
    ) -> ImpactAnalysis:
        """修订影响分析（工单 revise-deepen/02）：逐条新 Q&A → 影响结论 +
        建议模块集。

        输入 = 题面 + 功能需求层（推荐产物摘要）+ 当前模块集 + 模块库摘要 +
        新 Q&A（独立段，权威材料）。输出 JSON 由 impact.build_impact_analysis
        域判决（对照 build_module_selection 先例：任何结构 / 内容问题大声
        失败）；域判决错误由传输侧翻译回 LLMError（错误契约 502，impact 不
        import LLMError——与 llm → selection 边同款防环）。

        qa_count（可选）= 新 Q&A 条数，透传解析层做「逐条覆盖」校验（漏判
        大声失败，宁严勿假绿）。

        瞬时失败整次重问（_retry_parse，与 select_modules 同款兜底）：空内容 /
        畸形输出重问至多 SUMMARY_RETRY_LIMIT 轮，仍失败大声抛错。
        """
        known_slugs = [summary.slug for summary in manifest_summaries]

        def parse(content: str) -> ImpactAnalysis:
            try:
                return build_impact_analysis(
                    extract_module_selection_data(content),
                    known_slugs=known_slugs,
                    qa_count=qa_count,
                )
            except ImpactError as exc:
                raise LLMError(str(exc)) from exc

        return self._retry_parse(
            system_prompt=IMPACT_SYSTEM_PROMPT,
            user_prompt=_impact_user_prompt(
                problem_text,
                requirements,
                current_slugs,
                manifest_summaries,
                new_qa_text,
            ),
            parse=parse,
            label="影响分析",
            operation="analyze_impact",
            json_mode=True,
        )

    def deepen_main_c(
        self,
        main_c: str,
        requirements: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        problem_text: str,
        qa_text: str,
    ) -> str:
        """深化（工单 revise-deepen/04）：按功能需求逐条填充 main.c 的 TODO。

        输入 = 现有 main.c（含 TODO）+ 功能需求清单 + 模块接口清单 + 题面与
        Q&A；输出 = 实现后的 main.c 全文（文本模式，非 JSON——输出就是代码）。
        需求清单逐条注入（每条需求一行，带序号），prompt 要求逐条对应、不做
        题外发挥；接口块与骨架同源（build_skeleton_interfaces），保证只调真实
        函数。瞬时失败整次重问（_retry_parse，与骨架同款兜底）。
        """
        return self._retry_parse(
            system_prompt=DEEPEN_SYSTEM_PROMPT,
            user_prompt=_deepen_user_prompt(
                main_c, requirements, module_interfaces, problem_text, qa_text
            ),
            parse=lambda content: content,
            label="深化实现",
            operation="deepen_main_c",
        )

    def plan_tasks(
        self,
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        score_points: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
    ) -> TaskPlan:
        """任务拆解（工单 task-progress/01）：题面 + 功能需求 + 评分点 + 接口 +
        现有 main.c → 有序任务清单。

        输入 = 现有 main.c（含 TODO）+ 功能需求清单 + 评分点清单 + 模块接口
        清单 + 题面与 Q&A；输出 JSON 由 task_progress.build_task_plan 域判决
        （id 顺序分配 / depends_on 序号转 id / score_refs 校验 / verify 词表
        修正）；域判决错误由传输侧翻译回 LLMError（错误契约 502，task_progress
        不 import LLMError——与 llm → selection 边同款防环，但 build_task_plan
        在 llm 层调用，TaskError 在此翻译）。畸形输出 / 瞬时失败整次重问
        （_retry_parse ≤SUMMARY_RETRY_LIMIT 轮）。
        """
        known_score_ids = [
            str(point.get("id", f"score-{index}"))
            for index, point in enumerate(score_points, 1)
            if isinstance(point, Mapping)
        ]

        def parse(content: str) -> TaskPlan:
            try:
                return build_task_plan(
                    extract_module_selection_data(content),
                    known_score_ids=known_score_ids,
                )
            except TaskError as exc:
                raise LLMError(str(exc)) from exc

        return self._retry_parse(
            system_prompt=TASK_PLAN_SYSTEM_PROMPT,
            user_prompt=_task_plan_user_prompt(
                problem_text,
                qa_text,
                requirements,
                score_points,
                module_interfaces,
                main_c,
            ),
            parse=parse,
            label="任务拆解",
            operation="plan_tasks",
            json_mode=True,
        )

    def execute_task(
        self,
        main_c: str,
        task: Mapping[str, Any],
        note: str,
        module_interfaces: Sequence[str],
        problem_text: str,
        qa_text: str,
        feedback: str = "",
        global_note: str = "",
    ) -> str:
        """单任务执行（工单 task-progress/02 + task-feedback/02）：在现有
        main.c 上只实现一个任务；feedback 非空 = 上板反馈修复轮（用户烧录
        实测现象，prompt 按反馈修）；global_note 非空 = 工程级全局结论
        （工单 idea-suite/01：全局商量采纳的结论，prompt 独立段注入——任何
        一步执行都与之保持一致，空串 = 未采纳，调用形状逐字节不变）。

        输入 = 现有 main.c + 任务描述 + 用户补充说明（note）+ 上板反馈
        （feedback，可选）+ 工程级全局结论（global_note，可选）+ 模块接口
        清单 + 题面与 Q&A；输出 = 实现后的 main.c 全文（文本模式，与深化同
        形状）。瞬时失败整次重问（_retry_parse，与骨架同款兜底）；空结果由
        域层 run_task 拒绝（TaskError）。
        """
        return self._retry_parse(
            system_prompt=TASK_EXECUTE_SYSTEM_PROMPT,
            user_prompt=_task_execute_user_prompt(
                main_c, task, note, module_interfaces, problem_text, qa_text,
                feedback, global_note,
            ),
            parse=lambda content: content,
            label="任务执行",
            operation="execute_task",
        )

    def discuss_buy_options(
        self,
        problem_text: str,
        requirement: str,
        platform: str,
        solutions: Sequence[SolutionOption],
        history: Sequence[tuple[str, str]],
    ) -> BuyDiscussion:
        """买件方案商量（工单 buy-discuss/01）：一轮讨论回复 + 用户自定方案校核。

        输入 = 题面 + 需求句 + 平台 + 词表方案 + 讨论历史（用户 / AI 交替）；
        输出 JSON 由解析器校验：reply 空 / 缺失 = 整次重问（_retry_parse，
        对话语境回复为空毫无价值）；review 缺失 / 形状坏 = None（校核是
        增强，不阻断讨论）；verdict 词表外 = 修正回 feasible（展示层三态）。
        用户最新消息未提自定方案时模型被指示输出 review:null——解析层不
        区分「没提」与「模型没判出」，都按 None 对待（宁缺毋标不误导）。
        """

        def parse(content: str) -> BuyDiscussion:
            data = extract_module_selection_data(content)
            reply = data.get("reply")
            if not isinstance(reply, str) or not reply.strip():
                raise LLMError("讨论回复为空：模型未输出 reply 或为空串")
            review = data.get("review")
            if not isinstance(review, dict):
                return BuyDiscussion(reply=reply, review=None)
            verdict = str(review.get("verdict", "")).strip()
            if verdict not in BUY_VERDICTS:
                verdict = "feasible"
            return BuyDiscussion(
                reply=reply,
                review=BuyReview(
                    verdict=verdict,
                    reason=str(review.get("reason", "")).strip(),
                    suggestion=str(review.get("suggestion", "")).strip(),
                ),
            )

        return self._retry_parse(
            system_prompt=DISCUSS_SYSTEM_PROMPT,
            user_prompt=_discuss_user_prompt(
                problem_text, requirement, platform, solutions, history
            ),
            parse=parse,
            label="买件方案商量",
            operation="discuss_buy_options",
            json_mode=True,
        )

    def discuss_task(
        self,
        task: Mapping[str, Any],
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
        history: Sequence[tuple[str, str]],
    ) -> TaskDiscussion:
        """任务商量（工单 task-chat/02）：一轮讨论回复（任务顾问）。

        输入 = 任务描述 + 题面 + Q&A + 需求行 + 模块接口 + 当前 main.c +
        讨论历史（用户 / AI 交替）；输出 JSON 由解析器校验：reply 空 /
        缺失 = 整次重问（_retry_parse，对话语境回复为空毫无价值）。
        """

        def parse(content: str) -> TaskDiscussion:
            data = extract_module_selection_data(content)
            reply = data.get("reply")
            if not isinstance(reply, str) or not reply.strip():
                raise LLMError("任务商量回复为空：模型未输出 reply 或为空串")
            return TaskDiscussion(reply=reply.strip())

        return self._retry_parse(
            system_prompt=TASK_DISCUSS_SYSTEM_PROMPT,
            user_prompt=_task_discuss_user_prompt(
                task, problem_text, qa_text, requirements, module_interfaces, main_c, history
            ),
            parse=parse,
            label="任务商量",
            operation="discuss_task",
            json_mode=True,
        )

    def discuss_global_idea(
        self,
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        score_points: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
        plan: Mapping[str, Any] | None,
        global_note: str,
        history: Sequence[tuple[str, str]],
    ) -> TaskDiscussion:
        """全局工程级商量（工单 idea-suite/01）：一轮全局讨论回复（工程总顾问）。

        输入 = 题面 + Q&A + 功能需求 + 评分点 + 清单现状 + 模块接口 + 当前
        main.c + 已采纳全局结论（global_note）+ 讨论历史（用户 / AI 交替，
        最后一条 user = 本轮消息——单通道，无独立 message 参数，与任务商量
        同款防错位设计）；输出 JSON 由解析器校验：reply 空 / 缺失 = 整次
        重问（_retry_parse，对话语境回复为空毫无价值）。
        """

        def parse(content: str) -> TaskDiscussion:
            data = extract_module_selection_data(content)
            reply = data.get("reply")
            if not isinstance(reply, str) or not reply.strip():
                raise LLMError("全局商量回复为空：模型未输出 reply 或为空串")
            return TaskDiscussion(reply=reply.strip())

        return self._retry_parse(
            system_prompt=TASK_GLOBAL_DISCUSS_SYSTEM_PROMPT,
            user_prompt=_global_idea_user_prompt(
                problem_text,
                qa_text,
                requirements,
                score_points,
                module_interfaces,
                main_c,
                plan,
                global_note,
                history,
            ),
            parse=parse,
            label="全局商量",
            operation="discuss_global_idea",
            json_mode=True,
        )

    def discuss_params(
        self,
        problem_text: str,
        params: Sequence[Mapping[str, Any]],
        plan: Mapping[str, Any] | None,
        history: Sequence[tuple[str, str]],
    ) -> TaskDiscussion:
        """参数速调咨询（工单 params-chat-ai/01）：一轮调参诊断回复（调参顾问）。

        输入 = 题面 + 当前可调参数清单（逐条含 valid——锚失效标「已失效」，
        引导 AI 不推荐该参数）+ 任务清单现状 + 讨论历史（用户 / AI 交替，
        最后一条 user = 本轮消息——单通道防错位，与全局商量同款）；输出 JSON
        由解析器校验：reply 空 / 缺失 = 整次重问（_retry_parse，诊断语境
        回复为空毫无价值）。
        """

        def parse(content: str) -> TaskDiscussion:
            data = extract_module_selection_data(content)
            reply = data.get("reply")
            if not isinstance(reply, str) or not reply.strip():
                raise LLMError("参数速调咨询回复为空：模型未输出 reply 或为空串")
            return TaskDiscussion(reply=reply.strip())

        return self._retry_parse(
            system_prompt=PARAMS_CHAT_SYSTEM_PROMPT,
            user_prompt=_params_chat_user_prompt(problem_text, params, plan, history),
            parse=parse,
            label="参数速调商量",
            operation="discuss_params",
            json_mode=True,
        )

    def report_task_step(
        self,
        task: Mapping[str, Any],
        verify_result: Mapping[str, Any],
        diff_text: str,
        module_interfaces: Sequence[str],
        wiring_summary: str = "",
    ) -> StepReport:
        """步骤报告（工单 stepwise-deepen/01 + task-wiring-diagram/02）：一步
        执行 + 编译验证完成后的汇报简报。

        输入 = 任务描述 + 编译验证结果（status / message / compile）+ 代码
        diff 摘要 + 模块接口清单 + 本工程接线数据摘要（wiring_summary，工单
        task-wiring-diagram/02：wiring 字段的引用白名单——AI 只准引用这里
        出现的引脚名与端子名）；输出 JSON 由解析器校验：what_changed 空 /
        缺失 = 整次重问（_retry_parse——汇报里"做了什么"为空毫无价值）；
        user_action 缺失 = 空串（纯软件步无物理动作，降级路径允许）；wiring
        缺失 / 形状坏 = 空元组（本步无接线引用；合法性由下游查表判决）。
        """

        def parse(content: str) -> StepReport:
            data = extract_module_selection_data(content)
            what_changed = data.get("what_changed")
            if not isinstance(what_changed, str) or not what_changed.strip():
                raise LLMError("步骤报告缺少 what_changed：模型未输出或为空串")
            user_action = data.get("user_action")
            if not isinstance(user_action, str):
                user_action = ""
            checklist = data.get("checklist")
            checklist_items = _clean_str_list(checklist)
            return StepReport(
                what_changed=what_changed.strip(),
                user_action=user_action.strip(),
                checklist=checklist_items,
                wiring=parse_wiring_entries(data.get("wiring")),
            )

        return self._retry_parse(
            system_prompt=TASK_REPORT_SYSTEM_PROMPT,
            user_prompt=_task_report_user_prompt(
                task, verify_result, diff_text, module_interfaces, wiring_summary
            ),
            parse=parse,
            label="步骤报告",
            operation="report_task_step",
            json_mode=True,
        )

    def scan_params(
        self,
        main_c: str,
        module_interfaces: Sequence[str],
    ) -> ParamList:
        """参数识别（工单 param-tune/01）：扫描 main.c 可调数值参数表。

        输入 = 现有 main.c + 模块接口清单；输出 JSON 由 params.build_params
        域判决（name/label/old_value/anchor 非空、anchor 逐字节存在于
        main_c、anchor 内 old_value 恰好 1 次——不满足 = 无法确定性改值，
        整次重问；unit/range_hint 宽松；空参数表合法）。域判决错误由传输侧
        翻译回 LLMError（_retry_parse ≤SUMMARY_RETRY_LIMIT 轮，与
        build_task_plan 同款契约）。
        """

        def parse(content: str) -> ParamList:
            try:
                return build_params(extract_module_selection_data(content), main_c)
            except TaskError as exc:
                raise LLMError(str(exc)) from exc

        return self._retry_parse(
            system_prompt=TASK_PARAM_SYSTEM_PROMPT,
            user_prompt=_param_scan_user_prompt(main_c, module_interfaces),
            parse=parse,
            label="参数识别",
            operation="scan_params",
            json_mode=True,
        )

    def analyze_idea(
        self,
        idea: str,
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        score_points: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
        plan: Mapping[str, Any] | None,
    ) -> IdeaAnalysis:
        """新想法 / 问题分析（工单 idea-fix/01）：理解 + 分类 + 落地建议。

        输入 = 想法文本 + 题面 + Q&A + 功能需求行 + 评分点 + 模块接口 +
        当前 main.c + 任务清单（未拆解 = None）；输出 JSON 由解析器校验：
        kind 词表外 / reply 空 = 整次重问（_retry_parse——分类与理解都为空
        毫无价值）；new_task 非 new_task 类时强制置 None（防模型在讨论类
        也塞任务状）；affected_task_ids 缺省空元组。深层形状校验（任务字段
        合法性）交给 insert_task_from_idea 域层（本层只做机械形状提取）。
        """

        def parse(content: str) -> IdeaAnalysis:
            data = extract_module_selection_data(content)
            kind = data.get("kind")
            if kind not in IDEA_KINDS:
                raise LLMError(
                    f"想法分析 kind 非法：{kind!r}"
                    "（只允许 new_task / direct_fix / discussion）"
                )
            reply = data.get("reply")
            if not isinstance(reply, str) or not reply.strip():
                raise LLMError("想法分析缺少 reply：模型未输出或为空串")
            new_task = data.get("new_task")
            if new_task is not None and not isinstance(new_task, dict):
                raise LLMError("想法分析 new_task 必须是 JSON 对象或 null")
            fix_summary = data.get("fix_summary")
            if not isinstance(fix_summary, str):
                fix_summary = ""
            raw_affected = data.get("affected_task_ids") or []
            if not isinstance(raw_affected, list) or any(
                not isinstance(item, str) for item in raw_affected
            ):
                raise LLMError("想法分析 affected_task_ids 必须是字符串数组")
            return IdeaAnalysis(
                kind=kind,
                reply=reply.strip(),
                new_task=(
                    dict(new_task)
                    if kind == IDEA_KIND_NEW_TASK and new_task is not None
                    else None
                ),
                fix_summary=fix_summary.strip(),
                affected_task_ids=tuple(
                    item.strip() for item in raw_affected if item.strip()
                ),
            )

        return self._retry_parse(
            system_prompt=TASK_IDEA_SYSTEM_PROMPT,
            user_prompt=_idea_user_prompt(
                idea,
                problem_text,
                qa_text,
                requirements,
                score_points,
                module_interfaces,
                main_c,
                plan,
            ),
            parse=parse,
            label="想法分析",
            operation="analyze_idea",
            json_mode=True,
        )

    def apply_idea_fix(
        self,
        idea: str,
        fix_summary: str,
        affected: Sequence[str],
        module_interfaces: Sequence[str],
        problem_text: str,
        qa_text: str,
        main_c: str,
        global_note: str = "",
    ) -> str:
        """想法直接修正（工单 idea-fix/01）：按用户想法改现有代码。

        输入 = 想法文本 + 修正建议 + 受影响任务 id + 模块接口 + 题面/Q&A +
        当前 main.c + 工程级全局结论（global_note，可选——工单 idea-suite/01，
        与任务执行同注入：非空才插【工程级全局结论】段）；输出 = 修正后的
        main.c 全文（文本模式，与任务执行同形状——prompt 约束只改想法相关
        的实现）。瞬时失败整次重问（_retry_parse，与骨架同款兜底）；空结果
        由域层 run_direct_fix 拒绝（TaskError）。
        """
        return self._retry_parse(
            system_prompt=IDEAFIX_SYSTEM_PROMPT,
            user_prompt=_idea_fix_user_prompt(
                idea,
                fix_summary,
                affected,
                module_interfaces,
                problem_text,
                qa_text,
                main_c,
                global_note,
            ),
            parse=lambda content: content,
            label="想法修正",
            operation="apply_idea_fix",
        )

    def _observe_call(
        self,
        *,
        operation: str,
        started_at: float,
        request_bytes: int,
        status: str,
        http_status: int | None,
        parse_status: str,
        error_kind: str | None = None,
        usage: Mapping[str, Any] | None = None,
        call_id: int | None = None,
        attempts: int = 1,
        final: bool = True,
        budget_attempt: int | None = None,
        content_excerpt: str | None = None,
    ) -> None:
        """记录一条无素材的 LLM 调用观测；请求和响应内容绝不进入日志。"""
        observation: dict[str, Any] = {
            "operation": operation,
            "provider": "local" if self._provider == "local" else "deepseek",
            "route": self._provider,
            "model": self._config.model,
            "duration_ms": round((time.monotonic() - started_at) * 1000),
            "attempts": attempts,
            "status": status,
            "final": final,
            "call_id": call_id,
            "budget_attempt": budget_attempt,
            "http_status": http_status,
            "error_kind": error_kind,
            "parse_status": parse_status,
            "request_bytes": request_bytes,
            "usage": sanitize_llm_usage(usage),
            "content_excerpt": content_excerpt,
        }
        if self._observation_collector is not None:
            observation = self._observation_collector.collect(**observation)
        logger.info("LLM 调用观测", extra={"llm_observation": observation})

    def _observe_chat_result(
        self,
        result: _ChatResult,
        *,
        status: str,
        parse_status: str,
        error_kind: str | None = None,
    ) -> None:
        self._observe_call(
            operation=result.operation,
            started_at=result.started_at,
            request_bytes=result.request_bytes,
            status=status,
            http_status=result.http_status,
            parse_status=parse_status,
            error_kind=error_kind,
            usage=result.usage,
            call_id=result.call_id,
            attempts=result.attempts,
            budget_attempt=result.budget_attempt,
            content_excerpt=_content_excerpt(result.content),
        )

    def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
        operation: str = "chat",
        attempt_number: int = 1,
    ) -> str:
        """兼容直调用法的文本返回入口；错误分类与 _retry_parse 同款重试。"""
        last_error: Exception | None = None
        attempts = 0
        network_failures = 0
        while attempts < NETWORK_RETRY_LIMIT:
            attempts += 1
            try:
                return self._chat_once(
                    messages,
                    json_mode=json_mode,
                    operation=operation,
                    attempt_number=attempt_number + attempts - 1,
                ).content
            except LLMError as exc:
                last_error = exc
                if exc.kind == ERROR_KIND_BUDGET:
                    raise
                if exc.kind == ERROR_KIND_CLIENT:
                    raise
                if exc.kind == ERROR_KIND_RATE_LIMIT:
                    if attempts >= NETWORK_RETRY_LIMIT:
                        break
                    _backoff_sleep(
                        exc.retry_after if exc.retry_after is not None else 1.0
                    )
                    continue
                if exc.kind == ERROR_KIND_NETWORK:
                    network_failures += 1
                    if attempts >= NETWORK_RETRY_LIMIT:
                        break
                    _backoff_sleep(2 ** (network_failures - 1))
                    continue
                if attempts >= SUMMARY_RETRY_LIMIT:
                    break
        _raise_retry_exhausted(operation, attempts, last_error)

    def _chat_once(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
        operation: str = "chat",
        attempt_number: int = 1,
        observe_success: bool = True,
        max_tokens: int | None = None,
        thinking_disabled: bool = False,
    ) -> _ChatResult:
        self._call_sequence += 1
        call_id = self._call_sequence
        budget_attempt: int | None = None
        payload: dict[str, Any] = {"model": self._config.model, "messages": messages}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if thinking_disabled:
            # 关闭思考模式（工单 select-truncation/01）：deepseek-v4-flash /
            # v4-pro 思考模式默认开（effort=high），确定性 JSON 任务会让模型
            # 深度推理且循环不收敛，max_tokens 全被 reasoning_content 吃掉、
            # content 为空（finish_reason=length → 解析必失败）。结构化输出
            # 不需要思维链——显式关闭，content 直接输出（官方参数：
            # {"thinking": {"type": "disabled"}}，OpenAI Chat Completions 格式）
            payload["thinking"] = {"type": "disabled"}
        body_bytes = json.dumps(payload).encode("utf-8")
        started_at = time.monotonic()
        request_bytes = len(body_bytes)
        if self._retry_budget is not None:
            try:
                budget_attempt = self._retry_budget.consume_attempt()
            except LLMError as exc:
                self._observe_call(
                    operation=operation,
                    started_at=started_at,
                    request_bytes=request_bytes,
                    status="error",
                    http_status=None,
                    parse_status="not_sent",
                    error_kind=exc.kind,
                    call_id=call_id,
                    attempts=attempt_number,
                    budget_attempt=None,
                )
                raise
        if len(body_bytes) > MAX_REQUEST_BYTES:
            self._observe_call(
                operation=operation,
                started_at=started_at,
                request_bytes=request_bytes,
                status="error",
                http_status=None,
                parse_status="not_sent",
                error_kind=ERROR_KIND_CLIENT,
                call_id=call_id,
                attempts=attempt_number,
                budget_attempt=budget_attempt,
            )
            # 体积断言兜底：所有嵌内容调用都应已截断 / 分批，仍超限说明有未兜底
            # 的长输入——请求发出前大声失败（可操作信息），而不是等网关 413
            raise LLMError(
                f"请求体过大（{len(body_bytes)} 字节 > {MAX_REQUEST_BYTES} 字节）："
                "嵌内容的调用应已按预算截断 / 分批，仍超限说明有未兜底的长输入"
                "（如异常巨大的赛题文本）——请减小输入或减少导入工程的文件大小",
                kind=ERROR_KIND_CLIENT,
            )
        url = self._config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        try:
            response = self._transport.post(
                url,
                headers,
                payload,
                self.TIMEOUT_SECONDS,
            )
            status, body = response[:2]
            response_headers = response[2] if len(response) == 3 else {}
        except LLMError as exc:
            self._observe_call(
                operation=operation,
                started_at=started_at,
                request_bytes=request_bytes,
                status="error",
                http_status=None,
                parse_status="not_started",
                error_kind=exc.kind,
                call_id=call_id,
                attempts=attempt_number,
                budget_attempt=budget_attempt,
            )
            raise
        if status != 200:
            error_kind = _http_error_kind(status)
            self._observe_call(
                operation=operation,
                started_at=started_at,
                request_bytes=request_bytes,
                status="error",
                http_status=status,
                parse_status="not_started",
                error_kind=error_kind,
                call_id=call_id,
                attempts=attempt_number,
                budget_attempt=budget_attempt,
            )
            if status == 413:
                # 网关的请求体大小限制；嵌内容调用已截断分批，仍出现说明有未
                # 兜底的超长输入（如超大赛题文本）——给出可操作提示
                raise LLMError(
                    "DeepSeek API 返回 413：请求体过大。嵌内容素材已按预算截断 / "
                    "分批发送，若仍触发，请检查赛题文本是否异常巨大，或减少导入"
                    "工程的文件数量与单文件大小",
                    kind=ERROR_KIND_CLIENT,
                )
            if status == 429:
                raise LLMError(
                    f"DeepSeek API 返回 429：请求过于频繁",
                    kind=ERROR_KIND_RATE_LIMIT,
                    retry_after=_retry_after_seconds(response_headers),
                )
            if status >= 500:
                # 5xx = 网关 / 服务端瞬时故障（重试有价值，与连接失败同款指数退避）。
                raise LLMError(
                    f"DeepSeek API 返回 {status}：{body[:200]}",
                    kind=ERROR_KIND_NETWORK,
                )
            raise LLMError(
                f"DeepSeek API 返回 {status}：{body[:200]}", kind=ERROR_KIND_CLIENT
            )
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            self._observe_call(
                operation=operation,
                started_at=started_at,
                request_bytes=request_bytes,
                status="error",
                http_status=status,
                parse_status="invalid_response_json",
                error_kind=ERROR_KIND_PARSE,
                call_id=call_id,
                attempts=attempt_number,
                budget_attempt=budget_attempt,
            )
            raise LLMError(f"DeepSeek API 响应不是合法 JSON：{body[:200]}") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            self._observe_call(
                operation=operation,
                started_at=started_at,
                request_bytes=request_bytes,
                status="error",
                http_status=status,
                parse_status="missing_content",
                error_kind=ERROR_KIND_PARSE,
                call_id=call_id,
                attempts=attempt_number,
                budget_attempt=budget_attempt,
            )
            raise LLMError(
                f"DeepSeek API 响应缺少 choices[0].message.content：{body[:200]}"
            ) from exc
        if json_mode:
            # 本地 7B 模型偶发把 JSON 包进 Markdown 代码围栏（```json … ```），
            # 严格解析器不接受——单点剥外层，覆盖全部 json_mode 调用；剥 = no-op
            # 对 DeepSeek 零影响（从不包围栏），文本模式原样不动（骨架 ```c
            # 围栏等合法内容不被 mangle）（工单 local-llm-json-group/01）
            content = _unwrap_json_fence(content)
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        # 截断信号（工单 select-truncation/01）：取 choices[0].finish_reason，
        # "length" = 输出被 max_tokens 截断（推理模型下 content 常为空）——
        # 供 _retry_parse 判确定性失败免重试；缺字段 = None（兼容无该键响应）
        try:
            finish_reason = data["choices"][0].get("finish_reason")
        except (KeyError, IndexError, TypeError):
            finish_reason = None
        result = _ChatResult(
            content=content,
            operation=operation,
            started_at=started_at,
            request_bytes=request_bytes,
            http_status=status,
            usage=usage,
            call_id=call_id,
            attempts=attempt_number,
            budget_attempt=budget_attempt,
            finish_reason=finish_reason,
        )
        if observe_success:
            self._observe_chat_result(
                result, status="success", parse_status="success"
            )
        return result


# ---------------------------------------------------------------------------
# 本地路由（工单 local-llm-routing/02）：本地方法集 / 失联提示唯一出处 + 组合式
# RoutingLLM + build_llm 构造接线
# ---------------------------------------------------------------------------

# 本地方法集：{preread_topic, summarize_module, reference_summarize, clarify,
# validate_module_description, reference_judge_archivable}——赛题预读 + 两个
# 纯文本摘要（模块简介 / 参考素材简介）+ 澄清 / 简介一致性校验 / 归档判定
# （spike 实测内容合理；格式障碍（围栏）已被
# 工单 local-llm-json-group/01 的 _unwrap_json_fence 移除，JSON 调用可稳定解析）。
# 能力事实，硬编码为常量不做用户可配。常量单源：RoutingLLM 派发与测试都引用它。
LOCAL_LLM_METHODS = frozenset(
    {
        "preread_topic",
        "summarize_module",
        "reference_summarize",
        "clarify",
        "validate_module_description",
        "reference_judge_archivable",
    }
)

# 本地失联提示文案（唯一出处）：RoutingLLM 包装 local 委托抛出的最终 LLMError
# 时附上；测试与前端都引用它。用户裁决大声失败，不自动回退 DeepSeek。
LOCAL_LLM_UNAVAILABLE_MESSAGE = (
    "本地模型服务不可用：请启动 Ollama，或到设置页清空本地模型配置以改用 DeepSeek"
)
# 本地模型加载/运行失败（Ollama 在运行但 llama-server 崩溃：模型过大 / 内存不足）
# 的提示文案——区别于「未启动」，避免误导用户去启动本就运行着的 Ollama。
LOCAL_LLM_LOAD_FAILED_MESSAGE = (
    "本地模型加载或运行失败（Ollama 服务在运行但模型进程崩溃，常见原因：模型过大"
    "超出内存，如 30B 模型需约 19GB 而常见机器只有 16GB）：请换更小的模型"
    "（如 qwen3:8b），或到设置页清空本地模型配置以改用 DeepSeek"
)


def _local_error_hint(exc: LLMError) -> str:
    """本地失联提示分类：按错误特征选文案。

    llama-server 崩溃特征（500 响应体含 llama-server / failed to allocate /
    exit status）→ 加载失败文案（模型过大 / 内存不足）；连接被拒绝 → 未启动
    文案；其余未知形态 → 通用兜底文案。
    """
    message = str(exc)
    if "llama-server" in message or "failed to allocate" in message or "exit status" in message:
        return LOCAL_LLM_LOAD_FAILED_MESSAGE
    return LOCAL_LLM_UNAVAILABLE_MESSAGE


class RoutingLLM:
    """组合式 LLM：本地方法集走 local 实例、其余方法走 remote 实例。

    本地方法集 = LOCAL_LLM_METHODS（六个方法：赛题预读（结构化 JSON）+ 两
    个纯文本摘要 + 澄清 / 简介一致性校验 / 归档判定）；方法集外方法绝不落到
    local。local 委托抛出的最终 LLMError 被包装附可操作提示
    （LOCAL_LLM_UNAVAILABLE_MESSAGE），错误类别（kind）保持、沿用委托内既有
    重试机制（网络类指数退避照常），**不**自动回退远程（用户裁决大声失败）。
    """

    def __init__(self, remote: LLM, local: LLM) -> None:
        self._remote = remote
        self._local = local

    def _delegate(self, method: str) -> LLM:
        """派发决策唯一处：读本地方法集常量——集合内方法 → local，集合外 → remote。

        常量是行为开关而非装饰：改 LOCAL_LLM_METHODS 即改派发（测试以
        「落 local 的方法集 = 常量」断言分叉即红）。
        """
        return self._local if method in LOCAL_LLM_METHODS else self._remote

    def _local_call(self, method: str, call: Callable[[LLM], RT]) -> RT:
        """按方法集路由调用 + 本地失联包装（本地方法集共用原语）。

        _delegate 选委托后执行；仅当委托是 local 时才做失联包装（集合与派发
        同源——集合缩了自动退化为 remote 直通，不会把远程错误误包装成本地
        提示）。错误类别（kind）保持。
        """
        delegate = self._delegate(method)
        try:
            return call(delegate)
        except LLMError as exc:
            if delegate is not self._local:
                raise
            raise self._wrap_local_error(exc) from exc

    def _wrap_local_error(self, exc: LLMError) -> LLMError:
        """本地失联大声失败：包装附分类可操作提示（_local_error_hint），错误类别
        （kind）保持。

        已带任一提示文案（防御嵌套路由）则原样返回，避免重复包装。
        """
        if (
            LOCAL_LLM_UNAVAILABLE_MESSAGE in str(exc)
            or LOCAL_LLM_LOAD_FAILED_MESSAGE in str(exc)
        ):
            return exc
        return LLMError(f"{_local_error_hint(exc)}（{exc}）", kind=exc.kind)

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
        manual_fulltexts: Mapping[str, str] | None = None,
        clarifications: Sequence[tuple[str, str]] = (),
        qa_material: str = "",
    ) -> ModuleSelection:
        return self._remote.select_modules(
            problem_text,
            manifest_summaries,
            references,
            reference_fulltexts,
            manual_fulltexts,
            clarifications,
            qa_material,
        )

    def clarify(
        self, problem_text: str, clarifications: Sequence[tuple[str, str]]
    ) -> tuple[str, ...]:
        return self._local_call(
            "clarify", lambda delegate: delegate.clarify(problem_text, clarifications)
        )

    def preread_topic(self, problem_text: str) -> PrereadResult:
        return self._local_call(
            "preread_topic", lambda delegate: delegate.preread_topic(problem_text)
        )

    def name_topic_english(self, problem_text: str) -> str:
        return self._remote.name_topic_english(problem_text)

    def generate_main_skeleton(
        self,
        problem_text: str,
        module_interfaces: Sequence[str],
        reference_fulltexts: Mapping[str, str] | None = None,
        topic_framework: TopicFramework | None = None,
    ) -> str:
        return self._remote.generate_main_skeleton(
            problem_text,
            module_interfaces,
            reference_fulltexts,
            topic_framework,
        )

    def generate_smoke_main(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str:
        return self._remote.generate_smoke_main(problem_text, module_interfaces)

    def summarize_module(self, code: str) -> str:
        return self._local_call(
            "summarize_module", lambda delegate: delegate.summarize_module(code)
        )

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult:
        return self._local_call(
            "validate_module_description",
            lambda delegate: delegate.validate_module_description(description, code),
        )

    def fix_compile_errors(
        self,
        error_text: str,
        file_contexts: Mapping[str, str],
        *,
        problem_text: str = "",
        platform: str = "",
        module_slugs: Sequence[str] = (),
        main_c: str = "",
        dropped_files: Sequence[str] = (),
        previous_fixes: Sequence[Mapping[str, Any]] = (),
    ) -> tuple[FixSuggestion, ...]:
        return self._remote.fix_compile_errors(
            error_text,
            file_contexts,
            problem_text=problem_text,
            platform=platform,
            module_slugs=module_slugs,
            main_c=main_c,
            dropped_files=dropped_files,
            previous_fixes=previous_fixes,
        )

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None = None,
    ) -> tuple[FileDecision, ...]:
        return self._remote.distill_master(
            platform,
            project_names,
            judgment_files,
            comparison_summary,
            progress_emitter,
        )

    def reference_summarize(self, material: str) -> str:
        return self._local_call(
            "reference_summarize",
            lambda delegate: delegate.reference_summarize(material),
        )

    def reference_judge_archivable(
        self, candidates: Sequence[ReferenceCandidate]
    ) -> tuple[str, ...]:
        return self._local_call(
            "reference_judge_archivable",
            lambda delegate: delegate.reference_judge_archivable(candidates),
        )

    def topic_split_topics(self, pdf_text: str) -> tuple[TopicDraft, ...]:
        return self._remote.topic_split_topics(pdf_text)

    def topic_extract_number(self, text: str) -> str | None:
        return self._remote.topic_extract_number(text)

    def analyze_impact(
        self,
        problem_text: str,
        requirements: Sequence[Mapping[str, Any]],
        current_slugs: Sequence[str],
        manifest_summaries: Sequence[ManifestSummary],
        new_qa_text: str,
        qa_count: int | None = None,
    ) -> ImpactAnalysis:
        # 影响分析走 remote（质量优先，不走本地方法集——LOCAL_LLM_METHODS
        # 不含本方法，集合外方法恒落 remote）
        return self._remote.analyze_impact(
            problem_text,
            requirements,
            current_slugs,
            manifest_summaries,
            new_qa_text,
            qa_count,
        )

    def generate_report_draft(
        self,
        problem_text: str,
        requirements: Sequence[Mapping[str, Any]],
        manifest_summaries: Sequence[ManifestSummary],
        pin_summary: str,
    ) -> tuple[str, str]:
        # 报告草稿走 remote（质量优先，不进本地方法集——LOCAL_LLM_METHODS
        # 不含本方法，集合外方法恒落 remote）
        return self._remote.generate_report_draft(
            problem_text, requirements, manifest_summaries, pin_summary
        )

    def deepen_main_c(
        self,
        main_c: str,
        requirements: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        problem_text: str,
        qa_text: str,
    ) -> str:
        # 深化走 remote（质量优先，不进本地方法集）
        return self._remote.deepen_main_c(
            main_c, requirements, module_interfaces, problem_text, qa_text
        )

    def plan_tasks(
        self,
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        score_points: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
    ) -> TaskPlan:
        # 任务拆解走 remote（质量优先，不进本地方法集——拆解质量决定
        # 整个任务推进的可用性，本地小模型拆粒度偏差大）
        return self._remote.plan_tasks(
            problem_text,
            qa_text,
            requirements,
            score_points,
            module_interfaces,
            main_c,
        )

    def execute_task(
        self,
        main_c: str,
        task: Mapping[str, Any],
        note: str,
        module_interfaces: Sequence[str],
        problem_text: str,
        qa_text: str,
        feedback: str = "",
        global_note: str = "",
    ) -> str:
        # 单任务执行走 remote（质量优先，不进本地方法集）
        return self._remote.execute_task(
            main_c, task, note, module_interfaces, problem_text, qa_text, feedback,
            global_note,
        )

    def discuss_buy_options(
        self,
        problem_text: str,
        requirement: str,
        platform: str,
        solutions: Sequence[SolutionOption],
        history: Sequence[tuple[str, str]],
    ) -> BuyDiscussion:
        # 买件方案商量走 remote（讨论质量优先，不进本地方法集）
        return self._remote.discuss_buy_options(
            problem_text, requirement, platform, solutions, history
        )

    def discuss_task(
        self,
        task: Mapping[str, Any],
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
        history: Sequence[tuple[str, str]],
    ) -> TaskDiscussion:
        # 任务商量走 remote（讨论质量优先，不进本地方法集）
        return self._remote.discuss_task(
            task, problem_text, qa_text, requirements, module_interfaces, main_c, history
        )

    def discuss_global_idea(
        self,
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        score_points: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
        plan: Mapping[str, Any] | None,
        global_note: str,
        history: Sequence[tuple[str, str]],
    ) -> TaskDiscussion:
        # 全局商量走 remote（讨论质量优先，不进本地方法集）
        return self._remote.discuss_global_idea(
            problem_text,
            qa_text,
            requirements,
            score_points,
            module_interfaces,
            main_c,
            plan,
            global_note,
            history,
        )

    def discuss_params(
        self,
        problem_text: str,
        params: Sequence[Mapping[str, Any]],
        plan: Mapping[str, Any] | None,
        history: Sequence[tuple[str, str]],
    ) -> TaskDiscussion:
        # 参数速调咨询走 remote（讨论质量优先，不进本地方法集）
        return self._remote.discuss_params(problem_text, params, plan, history)

    def report_task_step(
        self,
        task: Mapping[str, Any],
        verify_result: Mapping[str, Any],
        diff_text: str,
        module_interfaces: Sequence[str],
        wiring_summary: str = "",
    ) -> StepReport:
        # 步骤报告走 remote（汇报质量优先，不进本地方法集）
        return self._remote.report_task_step(
            task, verify_result, diff_text, module_interfaces, wiring_summary
        )

    def scan_params(
        self,
        main_c: str,
        module_interfaces: Sequence[str],
    ) -> ParamList:
        # 参数识别走 remote（识别质量决定参数表可用性，不进本地方法集）
        return self._remote.scan_params(main_c, module_interfaces)

    def analyze_idea(
        self,
        idea: str,
        problem_text: str,
        qa_text: str,
        requirements: Sequence[Mapping[str, Any]],
        score_points: Sequence[Mapping[str, Any]],
        module_interfaces: Sequence[str],
        main_c: str,
        plan: Mapping[str, Any] | None,
    ) -> IdeaAnalysis:
        # 想法分析走 remote（分类质量决定落地路径，不进本地方法集）
        return self._remote.analyze_idea(
            idea,
            problem_text,
            qa_text,
            requirements,
            score_points,
            module_interfaces,
            main_c,
            plan,
        )

    def apply_idea_fix(
        self,
        idea: str,
        fix_summary: str,
        affected: Sequence[str],
        module_interfaces: Sequence[str],
        problem_text: str,
        qa_text: str,
        main_c: str,
        global_note: str = "",
    ) -> str:
        # 想法修正走 remote（代码改动质量优先，不进本地方法集）
        return self._remote.apply_idea_fix(
            idea, fix_summary, affected, module_interfaces, problem_text, qa_text,
            main_c, global_note,
        )


def build_llm(
    config: AppConfig,
    retry_budget: RetryBudget | None = None,
    observation_collector: LLMObservationCollector | None = None,
    transport: Transport | None = None,
) -> LLM:
    """按配置构造 LLM（webapp 的 AppContext.llm_factory 默认值）。

    本地 base_url 为空 → 普通 DeepSeekLLM（≡ 现状，零回归）；非空 → RoutingLLM
    （remote = 主配置实例，local = 本地 base_url / 本地 model，且不携带远程
    api_key——本地请求默认无认证；本地 model 空串时沿用主 model，保证请求体
    model 非空）。
    """
    if not config.local_llm_base_url:
        return DeepSeekLLM(
            config,
            transport=transport,
            retry_budget=retry_budget,
            observation_collector=observation_collector,
        )
    local_config = replace(
        config,
        api_key="",
        base_url=config.local_llm_base_url,
        model=config.local_llm_model or config.model,
    )
    return RoutingLLM(
        remote=DeepSeekLLM(
            config,
            transport=transport,
            provider="remote",
            retry_budget=retry_budget,
            observation_collector=observation_collector,
        ),
        local=DeepSeekLLM(
            local_config,
            transport=transport,
            provider="local",
            retry_budget=retry_budget,
            observation_collector=observation_collector,
        ),
    )


def extract_module_selection_data(content: str) -> dict[str, Any]:
    """把模型返回的 JSON 文本做机械形状提取，返回校验前的原始 dict。

    只做两处机械检查：JSON 解析（非 JSON 抛 LLMError）与顶层必须是对象
    （文案逐字）——语义校验（字段必填 / 类型 / known / 重复 / 需求→顶层
    模块 / 词表 / 怪癖）全部在 selection.build_module_selection（域判决单址），
    llm 只做传输。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError("模型输出必须是 JSON 对象")
    return data


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
        file.path: file.version_groups for file in judgment_files
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


def parse_preread(content: str, problem_text: str) -> PrereadResult:
    """预读 JSON 解析 + 机械校验（topic_preread.normalize_preread）。

    非 JSON / 顶层形状错误抛 LLMError（整次重问，_retry_parse 兜底）；
    条目级问题（引用不命中题面 / 非法 steps / 空 text）由 normalize_preread
    宽松过滤——预读是纯展示，宁可少显示一条也不整次失败。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    try:
        return normalize_preread(data, problem_text)
    except ValueError as exc:
        raise LLMError(str(exc)) from exc


def parse_clarify_questions(content: str) -> tuple[str, ...]:
    """把模型返回的澄清 JSON 解析校验为仍存疑问列表（空 = 澄清完成）。

    与 selection._parse_questions 同款宽松度：缺省 / 空 questions → 空元组
    （模型认为已无疑问，直接进收敛循环）；非空时必须是字符串数组——畸形
    输出抛 LLMError（模型输出不可信，宁可大声失败也不带病进收敛，与其它
    AI 契约同哲学）。超出 MAX_QUESTIONS 条截尾保留前 N 条（与提示词同源，
    工单 clarify-no-restriction/01：防问题轰炸）。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError("澄清结果必须是 JSON 对象")
    questions = data.get("questions")
    if questions in (None, [], ()):
        return ()
    if not isinstance(questions, list) or not all(
        isinstance(question, str) and question for question in questions
    ):
        raise LLMError("澄清结果的 questions 必须是字符串数组")
    return tuple(questions[:MAX_QUESTIONS])


def parse_fix_suggestions(
    content: str, allowed_files: Sequence[str]
) -> tuple[FixSuggestion, ...]:
    """把模型返回的修复 JSON 严格解析为 FixSuggestion 列表（可空 = 无修复）。

    与其它 AI 契约同哲学（模型输出不可信，宁可大声失败也不带病进写回流程）：
    非 JSON / 非对象 / fixes 非数组 / 条目缺字段或字段类型错 / file 不在允许
    清单内 / old_snippet 为空 → 抛 LLMError（整次重问，_retry_parse ≤SUMMARY_RETRY_LIMIT 轮
    兜底）。new_snippet 可为空（删除语义），reason 可为空串。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError("修复结果必须是 JSON 对象")
    fixes = data.get("fixes")
    if fixes in (None, [], ()):
        return ()
    if not isinstance(fixes, list):
        raise LLMError("修复结果的 fixes 必须是数组")
    allowed = frozenset(allowed_files)
    result: list[FixSuggestion] = []
    for index, item in enumerate(fixes):
        if not isinstance(item, dict):
            raise LLMError(f"修复结果[{index}] 必须是对象")
        file = item.get("file")
        line = item.get("line")
        old_snippet = item.get("old_snippet")
        new_snippet = item.get("new_snippet")
        reason = item.get("reason")
        if not isinstance(file, str) or not file:
            raise LLMError(f"修复结果[{index}] 缺 file")
        if file not in allowed:
            raise LLMError(f"修复结果[{index}] 的 file 不在提供的文件清单内：{file}")
        if not isinstance(line, int) or line < 0:
            raise LLMError(f"修复结果[{index}] 的 line 必须是行号")
        if not isinstance(old_snippet, str) or not old_snippet:
            raise LLMError(f"修复结果[{index}] 缺 old_snippet")
        if not isinstance(new_snippet, str):
            raise LLMError(f"修复结果[{index}] 的 new_snippet 必须是字符串")
        if not isinstance(reason, str):
            raise LLMError(f"修复结果[{index}] 的 reason 必须是字符串")
        result.append(
            FixSuggestion(
                file=file,
                line=line,
                old_snippet=old_snippet,
                new_snippet=new_snippet,
                reason=reason,
            )
        )
    return tuple(result)


def _fix_errors_user_prompt(
    *,
    error_text: str,
    file_contexts: Mapping[str, str],
    dropped_files: Sequence[str] = (),
    problem_text: str = "",
    platform: str = "",
    module_slugs: Sequence[str] = (),
    main_c: str = "",
    previous_fixes: Sequence[Mapping[str, Any]] = (),
) -> str:
    """修复请求的用户消息（决策记录 6）：报错全文 + 命中文件内容（截断已在
    域模块 fix_errors.read_file_contexts 完成，此处原样嵌入）+ 题面 / 平台 /
    模块 / main.c（走统一截断 _truncate_content）。无文件上下文（降级模式，
    决策记录 5）时显式告知模型按报错全文判断——仍可修，只是不精准。

    previous_fixes（工单 fix-loop-progress/01）：上一轮应用结果回喂——独立段
    「上一轮修复应用结果」（标题固定，测试断言用），位置在文件上下文之后、
    工程上下文之前；空列表 = 无该段（提示词与旧行为逐字节一致，零回归）。
    海量条目时段级合计截断（FIX_PREVIOUS_FIXES_CAP，工单 fix-request-budget/01：
    截头带标注，truncate_content 单源——与澄清历史段同哲学）。
    """
    parts: list[str] = ["【编译报错全文】", _truncate_content(error_text)]
    if file_contexts:
        parts.append("【输出目录内文件内容】")
        for path, body in file_contexts.items():
            parts.append(f"=== {path} ===\n{body}")
        if dropped_files:
            parts.append(
                "（以下文件超出上下文预算，未发送："
                + "、".join(dropped_files)
                + "——不要建议修改未发送的文件）"
            )
    else:
        parts.append(
            "（未定位到可读取的源码文件：只能依据报错全文判断——若仍能确定"
            "修改位置，请给出正确文件名与精确的 old_snippet，工具会按文件实际"
            "内容精确匹配）"
        )
    if previous_fixes:
        lines = [
            "【上一轮修复应用结果】（line 只作提示，以文件当前内容为准）"
        ]
        for fix in previous_fixes:
            entry = f"- {fix['file']}:{fix['line']} {fix['status']}"
            if fix["reason"]:
                entry += f"：{fix['reason']}"
            lines.append(entry)
        segment = "\n".join(lines)
        if len(segment) > FIX_PREVIOUS_FIXES_CAP:
            # 段级合计截断（工单 fix-request-budget/01）：条目数无界增长是
            # 请求体预算漏点，截头带标注——回喂只作对齐重写判据，尾部条目
            # 裁掉不丢关键信息（首条 = 最近的上一轮结果）
            segment = truncate_content(segment, FIX_PREVIOUS_FIXES_CAP)
        parts.append(segment)
    parts.append("【工程上下文】")
    if problem_text:
        parts.append("赛题原文：\n" + _truncate_content(problem_text))
    if platform:
        parts.append("目标平台：" + platform)
    if module_slugs:
        parts.append("选中模块：" + "、".join(module_slugs))
    if main_c:
        parts.append("main.c：\n" + _truncate_content(main_c))
    return "\n\n".join(parts)


def _build_user_prompt(problem_text: str, heading: str, items: Sequence[str]) -> str:
    """赛题 + 清单的 user 消息拼装（模块选择 / main.c 骨架共用）。

    赛题文本与清单条目都走截断（_truncate_content，带标注）——模块选择与
    骨架生成的请求体同样受预算约束，未兜底的长赛题 / 大接口块不再 413。
    """
    lines = ["赛题：", _truncate_content(problem_text), "", heading]
    lines.extend(_truncate_content(item) for item in items)
    return "\n".join(lines)


def _clarify_user_prompt(
    problem_text: str, clarifications: Sequence[tuple[str, str]]
) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    # 题面预算用 CLARIFY_TOPIC_CAP（澄清唯一依据，4000 通用预算截断长赛题会
    # 导致模型问题面已明确的细节——工单 clarify-dumb-questions/01）
    lines = ["赛题：", truncate_content(problem_text, CLARIFY_TOPIC_CAP)]
    if clarifications:
        lines.append(_clarification_history_segment(clarifications))
    lines.append(
        "只返回 json 格式的 JSON 对象："
        '{"questions": ["仍存的疑问，没有疑问时为空数组"]}'
    )
    return "\n".join(lines)


def _requirement_lines(
    requirements: Sequence[Mapping[str, Any]], heading: str
) -> list[str]:
    """功能需求清单的编号行（深化 / 任务拆解共用，单源防分叉）。

    每行 = "{序号}. {需求原文}（题面句子 N）"——题面句子注记可追踪来源；
    requirements 为空 → 空列表（调用方保证已有空段判断）。库外建议带既有
    「已定方案」结论（工单 buy-discuss/02）时，需求行下追加注记缩进行
    （wordlist = 「已定：<方案名>」；custom = 「已定·自定：<名>；AI 审核：
    <verdict>」）——写码阶段 AI 据此知悉用户买件决策。
    """
    lines = ["", heading]
    for index, req in enumerate(requirements, 1):
        requirement = req.get("requirement", "") if isinstance(req, Mapping) else ""
        lines_note = (
            f"（题面句子 {req.get('sentence', '')}）"
            if isinstance(req, Mapping) and req.get("sentence")
            else ""
        )
        lines.append(f"{index}. {requirement}{lines_note}")
        if isinstance(req, Mapping):
            for suggestion in req.get("suggestions") or []:
                if not isinstance(suggestion, Mapping):
                    continue
                note = _decision_note(suggestion)
                if note:
                    lines.append(f"    · {suggestion.get('name', '')} → {note}")
    return lines


def _decision_note(suggestion: Mapping[str, Any]) -> str:
    """库外建议的「已定方案」注记（工单 buy-discuss/02；单源，读载荷 dict）。

    形状校验走 selection.parse_decision（契约主人，评审项 buy-discuss/04 收敛
    ——不再自行宽松读取 source/verdict）：decision 缺失 / 损坏 = ""（不注记，
    旧载荷行为逐字节不变）；wordlist = 「（已定：<方案名>）」；custom =
    「（已定·自定：<名>；AI 审核：<verdict>）」（verdict 空 = 无审核不注记）。
    此处只读不重建，展示增强零判定。
    """
    decision = parse_decision(suggestion.get("decision"))
    if decision is None:
        return ""
    if decision.source == "wordlist":
        return f"（已定：{decision.name}）"
    # note 承载自定想法全文（前端 name 截 30 字、全文放 note）：注记必带全文
    # ——只给截断名，长自定想法进不了写码上下文（评审项 spec/②）
    note_text = f"；{decision.note}" if decision.note and decision.note != decision.name else ""
    verdict_text = f"；AI 审核：{decision.verdict}" if decision.verdict else ""
    return f"（已定·自定：{decision.name}{note_text}{verdict_text}）"


def _deepen_user_prompt(
    main_c: str,
    requirements: Sequence[Mapping[str, Any]],
    module_interfaces: Sequence[str],
    problem_text: str,
    qa_text: str,
) -> str:
    """深化的 user 消息（工单 revise-deepen/04）：题面 + 需求清单 + 接口 +
    Q&A + 现有 main.c。各段截断带标注（_truncate_content / _fit_fulltext_wire
    同款预算）。"""
    lines = ["赛题：", _truncate_content(problem_text)]
    if qa_text:
        lines += ["", "赛题答疑（赛事组 Q&A，权威澄清）：", _fit_fulltext_wire(qa_text)]
    if requirements:
        lines += _requirement_lines(
            requirements, "功能需求清单（逐条填充，不要遗漏、不要题外发挥）："
        )
    lines += ["", SKELETON_INTERFACES_HEADING]
    lines.extend(_truncate_content(block) for block in module_interfaces)
    lines += ["", "现有 main.c（在 TODO 预留区填充实现，其余内容原样保留）：", main_c]
    return "\n".join(lines)


def _task_plan_user_prompt(
    problem_text: str,
    qa_text: str,
    requirements: Sequence[Mapping[str, Any]],
    score_points: Sequence[Mapping[str, Any]],
    module_interfaces: Sequence[str],
    main_c: str,
) -> str:
    """任务拆解的 user 消息（工单 task-progress/01）：题面 + Q&A + 功能需求
    清单 + 评分点清单 + 接口 + 现有 main.c。各段截断带标注（_truncate_content
    / _fit_fulltext_wire 同款预算）。"""
    lines = ["赛题：", _truncate_content(problem_text)]
    if qa_text:
        lines += ["", "赛题答疑（赛事组 Q&A，权威澄清）：", _fit_fulltext_wire(qa_text)]
    if requirements:
        lines += _requirement_lines(
            requirements, "功能需求清单（任务必须逐条覆盖，不遗漏、不题外发挥）："
        )
    if score_points:
        pt_lines = ["", "题面评分点（score_refs 只引用这里的 id）："]
        for index, point in enumerate(score_points, 1):
            if not isinstance(point, Mapping):
                continue
            pid = point.get("id", f"score-{index}")
            score_text = (
                f"{point.get('score')} 分"
                if isinstance(point.get("score"), (int, float))
                and not isinstance(point.get("score"), bool)
                else "未标分"
            )
            pt_lines.append(f"- {pid}｜{point.get('description', '')}（{score_text}）")
        lines += pt_lines
    lines += ["", SKELETON_INTERFACES_HEADING]
    lines.extend(_truncate_content(block) for block in module_interfaces)
    lines += ["", "现有 main.c（任务是填入 TODO 预留区的增量，其余内容原样保留）：", main_c]
    return "\n".join(lines)


def _task_execute_user_prompt(
    main_c: str,
    task: Mapping[str, Any],
    note: str,
    module_interfaces: Sequence[str],
    problem_text: str,
    qa_text: str,
    feedback: str = "",
    global_note: str = "",
) -> str:
    """单任务执行的 user 消息（工单 task-progress/02 + task-feedback/02 +
    task-chat/01 + idea-suite/01）：任务描述 + 补充框 + 对话结论 + 上板反馈 +
    工程级全局结论 + 题面 + Q&A + 接口 + 现有 main.c。

    补充框（note）独立段（用户对本次执行的附加说明，如"循迹用 10ms
    定时器"），为空 = 无该段；对话结论（dialog_note，任务卡「和 AI 商量」
    里用户采纳的 AI 回复全文，工单 task-chat/01）另立一段（放在 note 段
    之后——对话语义晚于预填写说明、早于烧录反馈）；上板实测反馈（feedback）
    再另立一段（真实烧录后的现象，对话语义晚于预填写说明）；工程级全局
    结论（global_note，工单 idea-suite/01：全局商量采纳的结论——任何一步
    执行都与之保持一致）在 feedback 段后、赛题段前（全局语境比单次反馈更
    上位）；四者为空 = 无对应段（既有调用形状逐字节不变）。"""
    lines = [
        "【本次要实现的单个任务】",
        f"任务：{task.get('title', '')}",
        f"描述：{task.get('description', '')}",
    ]
    if note:
        lines += ["", "【用户补充说明（本次执行的附加要求）】", note]
    dialog_note = task.get("dialog_note", "")
    if isinstance(dialog_note, str) and dialog_note.strip():
        lines += [
            "",
            "【用户沟通结论（采纳自对话，按此修正实现）】",
            dialog_note.strip(),
        ]
    if feedback:
        lines += ["", "【上板实测反馈（按反馈修复，不重写无关部分）】", feedback]
    if global_note:
        lines += [
            "",
            "【工程级全局结论（采纳自全局商量，本次实现须与之保持一致）】",
            _truncate_content(global_note),
        ]
    lines += ["", "赛题：", _truncate_content(problem_text)]
    if qa_text:
        lines += ["", "赛题答疑（赛事组 Q&A，权威澄清）：", _fit_fulltext_wire(qa_text)]
    lines += ["", SKELETON_INTERFACES_HEADING]
    lines.extend(_truncate_content(block) for block in module_interfaces)
    lines += [
        "",
        "现有 main.c（只实现上述任务描述要求的功能，其余内容原样保留）：",
        main_c,
    ]
    return "\n".join(lines)


def _task_report_user_prompt(
    task: Mapping[str, Any],
    verify_result: Mapping[str, Any],
    diff_text: str,
    module_interfaces: Sequence[str],
    wiring_summary: str = "",
) -> str:
    """步骤报告的 user 消息（工单 stepwise-deepen/01 + task-wiring-diagram/02）：
    任务描述 + 编译验证结果 + 代码 diff 摘要 + 本工程接线数据 + 模块接口清单。
    各段截断带标注（_truncate_content 同款预算）；diff 空 = 无该段（写盘前
    main.c 变化未知时按无变化处理）；wiring_summary 空 = 无该段（无接线清单
    / 无板数据——AI 按不输出 wiring 处理）；接口段空 = 无该段。
    任务类 prompt 分段与 _task_execute_user_prompt 同构（接口段文本一致）——
    改动时两处核对（漂移即分叉，见 SKELETON_INTERFACES_HEADING 双份教训）。
    """
    lines = ["【本步任务（刚执行完）】"]
    lines.append(f"任务：{task.get('title', '')}")
    if task.get("description"):
        lines.append(f"描述：{task.get('description', '')}")
    verify_cause = verify_result.get("verify_cause", "")
    if verify_cause == "manual":
        lines.append("验收方式：manual（需上板人工确认）")
    elif task.get("verify") == "manual":
        lines.append("验收方式：manual（需上板人工确认）")
    dialog_note = task.get("dialog_note", "")
    if isinstance(dialog_note, str) and dialog_note.strip():
        lines += [
            "",
            "【用户沟通结论（采纳自对话，按此总结本步与后续动作）】",
            dialog_note.strip(),
        ]
    lines += ["", "【编译验证结果】"]
    status = verify_result.get("status", "")
    status_label = {"verified": "已验证（编译绿）", "unverified": "未验证",
                    "failed": "失败（修一轮仍红）"}.get(status, status)
    lines.append(f"状态：{status_label}")
    message = verify_result.get("message", "")
    if message:
        lines.append(f"说明：{message}")
    compile_result = verify_result.get("compile") or {}
    compile_summary = compile_result.get("summary", "") if isinstance(compile_result, Mapping) else ""
    if compile_summary:
        lines.append(f"编译摘要：{_truncate_content(str(compile_summary))}")
    if diff_text.strip():
        lines += ["", "【代码变化（diff 摘要，可能被截断）】", _truncate_content(diff_text)]
    if wiring_summary.strip():
        # 本工程接线数据（工单 task-wiring-diagram/02）：wiring 字段的引用
        # 白名单——表行与 README「引脚接线表」同源（wiring_summary_text）
        lines += ["", str(wiring_summary)]
    if module_interfaces:
        lines += ["", SKELETON_INTERFACES_HEADING]
        lines.extend(_truncate_content(block) for block in module_interfaces)
    return "\n".join(lines)


def _param_scan_user_prompt(
    main_c: str,
    module_interfaces: Sequence[str],
) -> str:
    """参数识别的 user 消息（工单 param-tune/01）：模块接口清单 + 当前 main.c。

    段序 = 接口 → main.c（识别对象）。各段截断带标注（_truncate_content
    同款预算）；接口段为空 = 无该段（main.c 单独也可识别）。
    """
    lines: list[str] = []
    if module_interfaces:
        lines += [SKELETON_INTERFACES_HEADING]
        lines.extend(_truncate_content(block) for block in module_interfaces)
    lines += ["", "当前 main.c（识别其中的可调数值参数，anchor 取声明行原文）：", main_c]
    return "\n".join(lines)


def _idea_plan_summary(plan: Mapping[str, Any] | None) -> list[str]:
    """想法分析的清单状态摘要行（工单 idea-fix/01）。

    plan 未拆解（None）= 一行说明；已拆解 = 每任务一行「tN｜标题｜状态｜依赖
    [tX]」（状态为 pending/doing/verified/unverified/failed/skipped 中文
    短词）——AI 据此判断新想法是不是清单里已有任务（避免重复建卡）与受影响
    任务。行内 _truncate_content 挡单条超长。
    """
    if plan is None:
        return ["", "【当前任务清单】", "（尚未拆解任务清单——无既有任务可受影响）"]
    tasks = plan.get("tasks") if isinstance(plan, Mapping) else None
    if not isinstance(tasks, list) or not tasks:
        return ["", "【当前任务清单】", "（清单为空——无既有任务可受影响）"]
    status_label = {
        "pending": "待做",
        "doing": "执行中",
        "verified": "已验证",
        "unverified": "未验证",
        "failed": "失败",
        "skipped": "已跳过",
    }
    lines = ["", "【当前任务清单（id｜标题｜状态｜依赖）】"]
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        task_id = str(task.get("id", ""))
        title = str(task.get("title", ""))
        status = status_label.get(str(task.get("status", "")), str(task.get("status", "")))
        deps = [str(d) for d in (task.get("depends_on") or []) if isinstance(d, str)]
        dep_text = "、".join(deps) if deps else "-"
        lines.append(f"- {task_id}｜{_truncate_content(title)}｜{status}｜依赖：{dep_text}")
    return lines


def _idea_user_prompt(
    idea: str,
    problem_text: str,
    qa_text: str,
    requirements: Sequence[Mapping[str, Any]],
    score_points: Sequence[Mapping[str, Any]],
    module_interfaces: Sequence[str],
    main_c: str,
    plan: Mapping[str, Any] | None,
) -> str:
    """想法分析的 user 消息（工单 idea-fix/01）：想法 + 题面 + Q&A + 功能需求
    + 评分点 + 清单状态 + 接口 + 现有 main.c。各段截断带标注（_truncate_content
    / _fit_fulltext_wire 同款预算）；想法段靠前（它是本调用要分析的主体）。
    """
    lines = ["【用户的新想法 / 发现的问题】", _truncate_content(idea)]
    lines += ["", "赛题：", _truncate_content(problem_text)]
    if qa_text:
        lines += ["", "赛题答疑（赛事组 Q&A，权威澄清）：", _fit_fulltext_wire(qa_text)]
    if requirements:
        lines += _requirement_lines(
            requirements, "功能需求清单（任务必须逐条覆盖，不遗漏、不题外发挥）："
        )
    if score_points:
        pt_lines = ["", "题面评分点（score_refs 只引用这里的 id）："]
        for index, point in enumerate(score_points, 1):
            if not isinstance(point, Mapping):
                continue
            pid = point.get("id", f"score-{index}")
            score_text = (
                f"{point.get('score')} 分"
                if isinstance(point.get("score"), (int, float))
                and not isinstance(point.get("score"), bool)
                else "未标分"
            )
            pt_lines.append(f"- {pid}｜{point.get('description', '')}（{score_text}）")
        lines += pt_lines
    lines += _idea_plan_summary(plan)
    lines += ["", SKELETON_INTERFACES_HEADING]
    lines.extend(_truncate_content(block) for block in module_interfaces)
    lines += ["", "现有 main.c（想法的落点参考）：", main_c]
    return "\n".join(lines)


def _idea_fix_user_prompt(
    idea: str,
    fix_summary: str,
    affected: Sequence[str],
    module_interfaces: Sequence[str],
    problem_text: str,
    qa_text: str,
    main_c: str,
    global_note: str = "",
) -> str:
    """想法直接修正的 user 消息（工单 idea-fix/01 + idea-suite/01）：想法 +
    修正建议 + 受影响任务 + 工程级全局结论 + 接口 + 题面/Q&A + 现有 main.c
    （与任务执行 prompt 同构——改动时两处核对，见 SKELETON_INTERFACES_HEADING
    双份教训）。

    工程级全局结论（global_note，工单 idea-suite/01：全局商量采纳的结论——
    修正亦须与之保持一致）在受影响任务段后、赛题段前（与 _task_execute_
    user_prompt 同位置语义）；空 = 无该段（既有调用形状逐字节不变）。
    """
    lines = ["【用户的想法 / 发现的问题】", _truncate_content(idea)]
    if fix_summary:
        lines += ["", "【修正建议（AI 分析时给出，按此修正）】", _truncate_content(fix_summary)]
    if affected:
        lines += [
            "",
            "【受影响任务（参考信息——修正可能影响它们的实现，不要顺带修改）】",
            "、".join(affected),
        ]
    if global_note:
        lines += [
            "",
            "【工程级全局结论（采纳自全局商量，本次修正须与之保持一致）】",
            _truncate_content(global_note),
        ]
    lines += ["", "赛题：", _truncate_content(problem_text)]
    if qa_text:
        lines += ["", "赛题答疑（赛事组 Q&A，权威澄清）：", _fit_fulltext_wire(qa_text)]
    lines += ["", SKELETON_INTERFACES_HEADING]
    lines.extend(_truncate_content(block) for block in module_interfaces)
    lines += [
        "",
        "现有 main.c（只按修正建议改，其余内容原样保留）：",
        main_c,
    ]
    return "\n".join(lines)


def _solutions_list_text(solutions: Sequence[SolutionOption]) -> str:
    """词表方案的讨论用全量清单（每方案一行：名称 + 接口 / 价格 / 适用字段）。

    买件商量需要接口 / 价格 / 适用等细节（与“仅名称”的 prompt 科普段
    format_wordlist_prompt 紧凑版不同界——讨论是选型决策上下文）。
    """
    lines = []
    for solution in solutions:
        head = f"- {solution.name}"
        if solution.interface:
            head += f"｜接口：{solution.interface}"
        if solution.price:
            head += f"｜价格：{solution.price}"
        if solution.recommended:
            head += "（词表推荐）"
        if solution.lib_modules:
            head += f"｜库内已有：{'、'.join(solution.lib_modules)}"
        lines.append(head)
        if solution.note:
            lines.append(f"  注意：{solution.note}")
        if solution.suitable:
            lines.append(f"  适用：{solution.suitable}")
    return "\n".join(lines)


def _discuss_history_segment(
    history: Sequence[tuple[str, str]],
) -> str:
    """讨论历史段（用户 / AI 交替逐条；旧 → 新）：逐条 _truncate_content 挡
    单条超长 + 段级合计 CLARIFICATION_HISTORY_CAP 兜底（**字符帽**，与
    _clarification_history_segment 同口径——truncate_content 而非
    fit_wire_budget，避免中文 6 字节/字符把 2500 帽折成 ~416 字符的实截断
    异常；评审项 buy-discuss/06 修正）。"""
    lines = []
    for role, content in history:
        speaker = "用户" if role == "user" else "AI"
        lines.append(f"{speaker}：{_truncate_content(content)}")
    if not lines:
        return ""
    segment = "\n".join(lines)
    if len(segment) > CLARIFICATION_HISTORY_CAP:
        segment = truncate_content(segment, CLARIFICATION_HISTORY_CAP)
    return segment


def _discuss_user_prompt(
    problem_text: str,
    requirement: str,
    platform: str,
    solutions: Sequence[SolutionOption],
    history: Sequence[tuple[str, str]],
) -> str:
    """买件方案商量的 user 消息（工单 buy-discuss/01）：题面 + 需求句 + 平台 +
    词表方案（全量细节）+ 讨论历史（旧 → 新）+ 用户最新一轮消息。各段截断带
    标注（_truncate_content / _discuss_history_segment）；方案段固定小体积。
    """
    lines = ["【赛题】", _truncate_content(problem_text)]
    if requirement:
        lines += ["", "【本需求（该库外建议对应的功能要求）】", requirement]
    if platform:
        lines += ["", "【所选平台】", platform]
    if solutions:
        lines += ["", "【词表选购方案（只顾问，不替你拍板；方案来自词表知识）】"]
        lines.append(_solutions_list_text(solutions))
    history_text = _discuss_history_segment(history)
    if history_text:
        lines += ["", "【讨论历史（旧 → 新）】", history_text]
    lines += [
        "",
        "【你的最新消息】",
        history[-1][1] if history else "",
        "",
        "请按系统提示词中的 json 契约输出（reply 必填，review 按规则输出）。",
    ]
    return "\n".join(lines)


def _task_discuss_user_prompt(
    task: Mapping[str, Any],
    problem_text: str,
    qa_text: str,
    requirements: Sequence[Mapping[str, Any]],
    module_interfaces: Sequence[str],
    main_c: str,
    history: Sequence[tuple[str, str]],
) -> str:
    """任务商量的 user 消息（工单 task-chat/02）：任务描述 + 题面 + Q&A（空则
    无段）+ 功能需求行 + 模块接口 + 当前 main.c + 讨论历史（旧 → 新，逐条
    字符帽）+ 用户最新一轮消息。各段截断带标注（_truncate_content /
    _discuss_history_segment / _requirement_lines 先例）。

    注意：任务类 prompt 的分段拼装与 _task_execute_user_prompt 同构（赛题 /
    Q&A / 接口 / main.c 四段文本一致，段序与标题因语义不同而有差异）——
    改其中一处时须两处核对（漂移即分叉，见 SKELETON_INTERFACES_HEADING 的
    双份教训）。
    """
    lines = ["【当前任务】"]
    lines.append(f"任务：{task.get('title', '')}")
    if task.get("description"):
        lines.append(f"描述：{task.get('description', '')}")
    lines += ["", "【赛题】", _truncate_content(problem_text)]
    if qa_text:
        lines += ["", "赛题答疑（赛事组 Q&A，权威澄清）：", _fit_fulltext_wire(qa_text)]
    requirement_lines = _requirement_lines(requirements, "【功能需求层】")
    if requirement_lines:
        lines += ["", requirement_lines[0]]
        lines.extend(requirement_lines[1:])
    lines += ["", SKELETON_INTERFACES_HEADING]
    lines.extend(_truncate_content(block) for block in module_interfaces)
    lines += ["", "当前 main.c（讨论对象，不直接修改——采纳后才由任务执行实现）：", main_c]
    history_text = _discuss_history_segment(history)
    if history_text:
        lines += ["", "【讨论历史（旧 → 新）】", history_text]
    lines += ["", "【你的最新消息】", history[-1][1] if history else ""]
    return "\n".join(lines)


def _global_idea_user_prompt(
    problem_text: str,
    qa_text: str,
    requirements: Sequence[Mapping[str, Any]],
    score_points: Sequence[Mapping[str, Any]],
    module_interfaces: Sequence[str],
    main_c: str,
    plan: Mapping[str, Any] | None,
    global_note: str,
    history: Sequence[tuple[str, str]],
) -> str:
    """全局商量的 user 消息（工单 idea-suite/01）：题面 + Q&A + 功能需求 +
    评分点 + 清单现状 + 接口 + 当前 main.c + 已采纳全局结论 + 讨论历史（旧 →
    新，逐条字符帽）+ 用户最新一轮消息。各段截断带标注（_truncate_content /
    _fit_fulltext_wire / _requirement_lines / _idea_plan_summary /
    _discuss_history_segment 先例）。

    历史为单通道：最后一条 user = 本轮消息（无独立 message 参数——与任务
    商量同款防错位设计，评审整改项）。全局结论段放 main.c 段后（讨论语境
    最上位），空 = 无该段。
    """
    lines = ["【赛题】", _truncate_content(problem_text)]
    if qa_text:
        lines += ["", "赛题答疑（赛事组 Q&A，权威澄清）：", _fit_fulltext_wire(qa_text)]
    if requirements:
        lines += _requirement_lines(
            requirements, "功能需求清单（工程必须逐条覆盖，不遗漏、不题外发挥）："
        )
    if score_points:
        pt_lines = ["", "题面评分点（任务 score_refs 只引用这里的 id）："]
        for index, point in enumerate(score_points, 1):
            if not isinstance(point, Mapping):
                continue
            pid = point.get("id", f"score-{index}")
            score_text = (
                f"{point.get('score')} 分"
                if isinstance(point.get("score"), (int, float))
                and not isinstance(point.get("score"), bool)
                else "未标分"
            )
            pt_lines.append(f"- {pid}｜{point.get('description', '')}（{score_text}）")
        lines += pt_lines
    lines += _idea_plan_summary(plan)
    lines += ["", SKELETON_INTERFACES_HEADING]
    lines.extend(_truncate_content(block) for block in module_interfaces)
    lines += ["", "当前 main.c（工程现状，讨论对象——不直接修改）：", main_c]
    if global_note.strip():
        lines += [
            "",
            "【工程级全局结论（学生已采纳的先前商讨结论，回复须与之保持一致）】",
            _truncate_content(global_note),
        ]
    history_text = _discuss_history_segment(history)
    if history_text:
        lines += ["", "【讨论历史（旧 → 新）】", history_text]
    lines += ["", "【你的最新消息】", history[-1][1] if history else ""]
    return "\n".join(lines)


def _params_chat_user_prompt(
    problem_text: str,
    params: Sequence[Mapping[str, Any]],
    plan: Mapping[str, Any] | None,
    history: Sequence[tuple[str, str]],
) -> str:
    """参数速调咨询的 user 消息（工单 params-chat-ai/01）：题面 + 当前可调
    参数清单（AI 只能推荐这里的参数名——逐条 name/label/当前值/单位/建议范围/
    有效性）+ 任务清单现状 + 讨论历史（旧 → 新）+ 用户最新一轮消息。各段截断
    带标注（_truncate_content / _idea_plan_summary / _discuss_history_segment
    先例）。

    历史为单通道：最后一条 user = 本轮消息（无独立 message 参数——与任务
    商量 / 全局商量同款防错位设计）。参数清单恒渲染：空 = 明确「未识别」，
    引导 AI 如实说明并建议下一步，而非硬凑推荐。
    """
    lines = ["【赛题】", _truncate_content(problem_text)]
    lines += ["", "【当前可调参数清单（AI 只能推荐这里的参数名，请原样引用）】"]
    param_items = [p for p in params if isinstance(p, Mapping)]
    if not param_items:
        lines.append(
            "（尚未识别可调参数——请如实告知学生，并建议先点「识别 main.c 参数」）"
        )
    for index, p in enumerate(param_items, 1):
        name = str(p.get("name", ""))
        label = str(p.get("label", ""))
        old_value = str(p.get("old_value", ""))
        unit = str(p.get("unit", ""))
        range_hint = str(p.get("range_hint", ""))
        valid = p.get("valid", True)
        parts = [f"{name}（{label}）", f"当前值：{old_value}"]
        if unit:
            parts.append(f"单位：{unit}")
        if range_hint:
            parts.append(f"建议范围：{range_hint}")
        parts.append("状态：有效" if valid else "状态：已失效（main.c 已改动，需重新识别）")
        lines.append(f"- {index}. " + "｜".join(parts))
    lines += _idea_plan_summary(plan)
    history_text = _discuss_history_segment(history)
    if history_text:
        lines += ["", "【讨论历史（旧 → 新）】", history_text]
    lines += ["", "【你的最新消息】", history[-1][1] if history else ""]
    return "\n".join(lines)


def _impact_user_prompt(
    problem_text: str,
    requirements: Sequence[Mapping[str, Any]],
    current_slugs: Sequence[str],
    manifest_summaries: Sequence[ManifestSummary],
    new_qa_text: str,
) -> str:
    """修订影响分析的 user 消息（工单 revise-deepen/02）：题面 + 功能需求层 +
    当前模块集 + 模块库摘要 + 新 Q&A 独立段。各段截断带标注（_truncate_content
    与所有嵌内容调用同款预算）；Q&A 独立段（不并入题面——题面逐句编号不受
    影响）。"""
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    prompt = _build_user_prompt(
        problem_text,
        "模块库可用模块：",
        [summary.to_line() for summary in manifest_summaries],
    )
    if requirements:
        lines = ["", "既有功能需求层（逐条核验新 Q&A 的影响引用这里的原文）："]
        for index, req in enumerate(requirements, 1):
            requirement = req.get("requirement", "") if isinstance(req, Mapping) else ""
            sentence = req.get("sentence", "") if isinstance(req, Mapping) else ""
            lines.append(
                f"- {index}. {requirement}（题面句子 {sentence}）"
            )
        prompt += "\n".join(lines)
    lines = ["", "当前模块集（生成时选定，含依赖展开）：", "、".join(current_slugs)]
    prompt += "\n".join(lines)
    prompt += (
        "\n\n【新增赛题答疑 Q&A（赛事组权威澄清，逐条核对影响）】\n"
        + _fit_fulltext_wire(new_qa_text)
        + "\n\n只返回 json 格式的 JSON 对象："
        '{"impacts": [{"qa_index": 1, "requirement_refs": ["受影响的'
        '功能需求原文"], "add": ["新增模块 slug"], "remove": ["移除模块 '
        'slug"], "reason": "中文理由"}], "suggested_slugs": ["建议的最终'
        '模块集完整列表（只含库内 slug）"]}'
    )
    return prompt


def _selection_user_prompt(
    problem_text: str,
    manifest_summaries: Sequence[ManifestSummary],
    references: Sequence[ReferenceSuggestion] = (),
    reference_fulltexts: Mapping[str, str] | None = None,
    manual_fulltexts: Mapping[str, str] | None = None,
    hardware_words: Sequence[HardwareWordGroup] = (),
    clarifications: Sequence[tuple[str, str]] = (),
    qa_material: str = "",
) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    prompt = _build_user_prompt(
        problem_text, "模块库可用模块：", [s.to_line() for s in manifest_summaries]
    )
    if references:
        lines = [
            "",
            "关联参考文件（标题 + 一句话简介；如需阅读全文，在输出的 references "
            "数组里列出想读的 id，系统随后给出全文）：",
        ]
        for ref in references:
            note = (
                "（用户手动指定，全文已直接给出，无需点名）"
                if ref.source == REFERENCE_SOURCE_MANUAL
                else ""
            )
            lines.append(f"- {ref.id}: {ref.title} —— {ref.description}{note}")
        prompt += "\n".join(lines)
    if reference_fulltexts:
        lines = ["", "以下是你要求阅读全文的参考文件："]
        for ref in references:
            fulltext = reference_fulltexts.get(ref.id)
            if fulltext is not None:
                # 空文件也嵌入（带文件名标注的空白块）——静默丢弃会让模型以为
                # 它点名的文件没给，与"读到什么就是什么"的截断契约一致。
                # 截断两级（工单 03 + budget-wire-unification/01）：read_fulltext
                # 逐文件截断（每文件 REFERENCE_FILE_CAP 带标注），此处只做
                # wire 字节预算兜底（_fit_fulltext_wire——旧 4000 总截断吞掉
                # 尾部文件；旧字符 cap 3B 估算假口径已弃）
                lines.append(
                    f"- {ref.id}: {ref.title}：\n```\n"
                    f"{_fit_fulltext_wire(fulltext)}\n```"
                )
        prompt += "\n".join(lines)
    if manual_fulltexts:
        # 手动选参考资料（工单 01）：全文直读强制（read_fulltext 已带 file_label
        # 文件名标注 + 逐文件截断标注，此处只做 wire 字节预算兜底
        # （_fit_fulltext_wire——工单 03 放宽旧 4000 总截断吞掉尾部文件；
        # budget-wire-unification/01 弃字符 cap 改 wire 记账）
        lines = ["", "以下为你手动指定的参考文件全文（用户显式选择，直接作学习素材）："]
        for ref in references:
            fulltext = manual_fulltexts.get(ref.id)
            if fulltext is not None:
                lines.append(
                    f"- {ref.id}: {ref.title}：\n```\n"
                    f"{_fit_fulltext_wire(fulltext)}\n```"
                )
        prompt += "\n".join(lines)
    if qa_material:
        # 赛题答疑 Q&A（工单 qa-material/01）：赛事组对题面的澄清问答，权威
        # 材料——题面/参考段之后、用户澄清之前的独立段（原文直引，不并入题面
        # 不影响逐句编号；收敛判定的对照句编号保持稳定）。空材料不出段（缺省
        # = 旧行为逐字节）。wire 预算兜底照 _fit_fulltext_wire（长 Q&A 截断带
        # 标注，模型知道材料不完整）。
        prompt += (
            "\n\n【赛题答疑（赛事组 Q&A，权威澄清，题面有歧义处以这里为准）】\n"
            + _fit_fulltext_wire(qa_material)
        )
    if clarifications:
        # 澄清问答历史（工单 clarify-history-in-convergence）：题面 / 参考段之后
        # 的独立段——Q/A 逐条、不带编号、不并入题面（题面逐句编号跨轮稳定，
        # 收敛判定的对照句编号依赖它）。空历史不出段（缺省 = 旧行为逐字节）。
        # 历史段截断（工单 recommend-speedup/01 D）：随补问轮数无界增长，逐条
        # + 合计两级截断（_clarification_history_segment，带标注）。
        lines = ["", "用户已澄清的问题（题面证据不足处用户已补充的回答，不要重复问）："]
        lines.append(_clarification_history_segment(clarifications))
        prompt += "\n".join(lines)
    if hardware_words:
        prompt += "\n\n" + _wordlist_prompt_segment(hardware_words)
    # 多实例猜测规则段（工单 module-multi-instance/06，key 泛化 key-multi-instance/05）：
    # 库内有多实例模块才出段（与参考/澄清段同款条件段先例——最坏情形请求预算零成本，
    # 旧库提示词逐字节不变）；内置变体 token 词表与中文标签单源 = selection 策略表
    # 投影（multi_instance_vocab / multi_instance_labels：提示词可见契约与解析校验
    # 同源，改词表/标签只改策略行）
    has_multi = any(summary.multi_instance for summary in manifest_summaries)
    if has_multi:
        vocab = multi_instance_vocab()
        labels = multi_instance_labels()
        multi_slugs = {
            summary.slug
            for summary in manifest_summaries
            if summary.multi_instance is not None
        }
        per_module = [
            f"{slug} 变体 = {labels[slug]}，内置 {'/'.join(tokens)}，其余空串"
            for slug, tokens in vocab.items()  # 策略登记序（led → key），确定性
            if slug in multi_slugs
        ]
        all_tokens = [
            token for slug in vocab if slug in multi_slugs for token in vocab[slug]
        ]
        prompt += (
            "\n\n多实例规则（硬约束）：instances 字段**只允许**出现在清单带"
            "「多实例」标注的模块条目上——**未标注的模块输出 instances 会被系统"
            "直接拒绝整轮结果**（模块 digit_uart 曾因此整轮失败）。其余模块条目"
            "绝不输出 instances 字段。多实例模块按题面数量输出 instances 数组："
            "每条 {\"name\": 显示名, \"variant\": 变体}（"
            + "；".join(per_module)
            + "）；数量不超过清单标注"
            "上限；题面未明确数量时省略；引脚自动分配，不输出 pin；不为非多实例"
            "模块输出 instances。"
        )
    # 功能组互斥规则段（工单 recommend-exclusive-groups/03）：库内存在互斥组才
    # 出段（与多实例规则段同款条件段先例——最坏情形预算成本仅新增段体量，旧库
    # 提示词逐字节不变）；组统计从摘要投影（清单带「同组互斥」标注），零参数
    # 传递——条件与正文同源，不存在两侧漂移。成员计数按摘要视图（已按目标平台
    # 过滤）：单成员组（该平台无可选，如 stm32 的 gray-track 仅 pid）= 不出段
    # （spec「单成员组 / 无组库 → 无提示词段」）
    group_stats: dict[str, tuple[int, str]] = {}  # 组 id -> (该平台成员数, label)
    for summary in manifest_summaries:
        if summary.exclusive_group is None:
            continue
        count, label = group_stats.get(
            summary.exclusive_group.id, (0, summary.exclusive_group.label)
        )
        group_stats[summary.exclusive_group.id] = (count + 1, label)
    group_ids = {gid for gid, (count, _) in group_stats.items() if count >= 2}
    if group_ids:
        prompt += (
            f"\n\n{EXCLUSIVE_GROUP_TAG}（硬约束）：清单带「{EXCLUSIVE_GROUP_TAG}」"
            "标注的模块共用同一传感器/同一功能，同一题内**只推荐一个**；同组多个"
            "被推荐 = 配置页出现两份相同硬件配置（2024H 复盘）。按题面择优推荐一个"
            "即可，同组其它候选由系统展示给用户选择。"
        )
    # 题面核查条（工单 recommend-exclusive-groups/03）：库内存在航向保持类组
    # （组 id 前缀 ATTITUDE_GROUP_ID_PREFIX）才出段——无引导线/无指示标记直线
    # 行驶的题面必须荐姿态传感器，否则直线段无法完成（2024H 复盘：AI 曾漏
    # mpu6050/陀螺仪）；组名取库内实际 label（同组 label 经 01 库级校验逐字一致）
    attitude_groups = {
        gid for gid in group_ids if gid.startswith(ATTITUDE_GROUP_ID_PREFIX)
    }
    if attitude_groups:
        label = group_stats[min(attitude_groups)][1]
        prompt += (
            "\n\n题面核查（硬约束）：无引导线/无其他指示标记/沿直线自主行驶 → "
            f"必须从清单「{label}」组中推荐一个；漏推荐 = 直线段无法完成"
            "（2024H 复盘）。"
        )
    # 输出契约：旧库（无多实例模块）用旧契约逐字节不变（验收②——旧推荐无
    # instances 现行为不变，模型照旧不输出该字段）；多实例库扩展 instances 形状
    if has_multi:
        contract = (
            '{"requirements": [{"requirement": "功能需求（能力/外设级）", '
            '"sentence": 1（整数——对应题面句子编号，第 3 句就是 3；必须是整数，'
            '不是字符串"1"）, "modules": [{"slug": "库内命中模块", '
            '"reason": "为何满足该需求", "instances": [{"name": "显示名", '
            f'"variant": "{"/".join(all_tokens)} 或空串（仅多实例模块，'
            '按题面数量）"}]}], "suggestions": [{"name": "硬件词表内的'
            '类别或型号名", "category": "词表外型号必填的所属类别名", "examples": '
            '["常识举例"]}]}], "questions": ["题面缺失且影响模块选择的关键补问，可省略"]'
        )
    else:
        contract = (
            '{"requirements": [{"requirement": "功能需求（能力/外设级）", '
            '"sentence": 1（整数——对应题面句子编号，第 3 句就是 3；必须是整数，'
            '不是字符串"1"）, "modules": [{"slug": "库内命中模块", '
            '"reason": "为何满足该需求"}], "suggestions": [{"name": "硬件词表内的'
            '类别或型号名", "category": "词表外型号必填的所属类别名", "examples": '
            '["常识举例"]}]}], "questions": ["题面缺失且影响模块选择的关键补问，可省略"]'
        )
    if references:
        contract += ', "references": ["想读全文的参考文件 id，不需要可省略"]'
    # 输出契约：评分点是题面可选增强信息；模型无法识别评分表时省略或返回空数组，
    # 由 selection 层按可选信息降级，不阻断模块推荐。
    contract = (
        contract
        + ', "score_points": [{"id": "评分点编号", '
        '"part": "basic/development/unknown", "description": "评分点描述", '
        '"score": 10 或 null, "sentence_refs": [1]}]'
    )
    return prompt + "\n只返回 json 格式的 JSON 对象：" + contract + "}"



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
        "独有）。读全文（超长文件已截断，见文件末尾标注，" + TRUNCATION_NOTICE
        + "）后为每个内容版本写一段中文摘要。同一路径在多个工程里"
        "内容不同（冲突）时，每个内容版本必须各输出一条 versions 条目，projects "
        "精确列出持有该版本内容的工程——把不同内容的版本合并成一条是错误：",
    ]
    for file in judgment_files:
        multi = len(file.versions) > 1
        for index, version in enumerate(file.versions, start=1):
            label = (
                f"版本 {index}（{'、'.join(version.projects)}）"
                if multi
                else f"（{'、'.join(version.projects)}）"
            )
            lines.append(
                f"- {file.path} {label}：\n"
                f"```c\n{_truncate_content(version.content)}\n```"
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
            "多份内容不同时，读多份后整合出通用版本，选一份只是特例）/ exclude（剔除）。",
            JUDGMENT_SCOPE,
            "merge 必须给出整合产物全文 content 与整合说明 explanation（选一份时可附"
            "source 说明选了哪份）。判定理由带上摘要要点。只返回 json 格式的 JSON 对象：",
            '{"decisions": [{"path": "...", "action": "keep|merge|exclude", '
            '"content": "merge 时必填的整合产物全文", '
            '"explanation": "merge 时必填的整合说明（选一份时说明为何选它）", '
            '"source": "merge 选一份时可选填的来源工程名", "reason": "中文理由"}]}',
        ]
    )
    return "\n".join(lines)


def parse_archive_judgment(content: str, paths: Sequence[str]) -> tuple[str, ...]:
    """把模型返回的归档判定 JSON 解析校验为值得归档的路径列表。

    路径词表约束（未知路径 / 重复路径拒绝）与 build_module_selection 同款——
    模型输出不可信，宁可大声失败也不要带病进入归档流程。空列表合法（没有
    文件值得归档），由调用方决定如何呈现。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("archive"), list):
        raise LLMError("模型输出缺少 archive 数组")

    known = set(paths)
    result: list[str] = []
    for index, item in enumerate(data["archive"]):
        if not isinstance(item, str) or not item:
            raise LLMError(f"archive[{index}] 必须是字符串")
        if item not in known:
            raise LLMError(f"模型判定归档了素材外的路径：{item}")
        if item in result:
            raise LLMError(f"模型重复判定归档：{item}")
        result.append(item)
    return tuple(result)


def _parse_report_draft(content: str) -> tuple[str, str]:
    """把模型返回的设计报告草稿 JSON 解析校验为 (方案论证, 软件流程)。

    模型输出不可信，宁可大声失败也不带病进报告：缺键 / 非字符串拒绝
    （LLMError → 整次重问 → 仍失败由调用方捕获降级为空文本 + 占位节）。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError("模型输出不是 JSON 对象")
    rationale = data.get("rationale")
    workflow = data.get("workflow")
    if not isinstance(rationale, str) or not rationale:
        raise LLMError("模型输出缺少 rationale 字段")
    if not isinstance(workflow, str) or not workflow:
        raise LLMError("模型输出缺少 workflow 字段")
    return rationale, workflow


def _report_draft_user_prompt(
    problem_text: str,
    requirements: Sequence[Mapping[str, Any]],
    manifest_summaries: Sequence[ManifestSummary],
    pin_summary: str,
) -> str:
    """设计报告草稿用户提示词：题面 + 功能需求清单 + 模块摘要 + 引脚表摘要。
    提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求。"""
    lines = [f"赛题原文：\n{_truncate_content(problem_text)}", ""]
    lines.append("功能需求清单（句子编号 = 题面句号）：")
    for req in requirements:
        sentence = req.get("sentence")
        sentence_text = f"（句子 {sentence}）" if isinstance(sentence, int) else ""
        lines.append(f"- {req.get('requirement')}{sentence_text}")
    lines.append("")
    lines.append("模块清单：")
    lines.extend(summary.to_line() for summary in manifest_summaries)
    lines.append("")
    lines.append(f"引脚分配表：\n{pin_summary}")
    lines.append("")
    lines.append(
        '只返回 json 格式的 JSON 对象：{"rationale": "方案论证（段落间用空行）",'
        ' "workflow": "软件流程（单段，不要用空行）"}'
    )
    return "\n".join(lines)


def _archive_judgment_user_prompt(
    candidates: Sequence[ReferenceCandidate],
) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    lines = ["待判断是否值得归档的文件（已被判定剔除出母版，附剔除理由）："]
    for candidate in candidates:
        lines.append(
            f"- {candidate.path}（理由：{candidate.reason}）：\n"
            f"```\n{_truncate_content(candidate.content)}\n```"
        )
    lines.append(
        "只返回 json 格式的 JSON 对象："
        '{"archive": ["值得归档的路径", ...]}'
    )
    return "\n".join(lines)


def _validation_user_prompt(description: str, code: str) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    return (
        f"模块简介：\n{_truncate_content(description)}\n\n实际代码：\n"
        f"```c\n{_truncate_content(code)}\n```\n\n"
        + VALIDATION_UNIVERSALITY_RULE
        + "\n判断简介与实际代码是否一致，只返回 json 格式的 JSON 对象："
        '{"consistent": true/false, "issues": "不一致时用中文指出差异，一致时为空字符串"}'
    )


def _skeleton_user_prompt(
    problem_text: str,
    module_interfaces: Sequence[str],
    reference_fulltexts: Mapping[str, str] | None = None,
    topic_framework: TopicFramework | None = None,
) -> str:
    """main.c 骨架生成的 user 消息：赛题 + 接口块 + 可选题型框架段 + 可选参考段。

    topic_framework（工单 topic-framework/03）非空时在参考段**之前**插题型框架段
    （确定性注入——直接从参考条目 framework/main.c 读来，不经 LLM 改写）：强指令
    SKELETON_FRAMEWORK_RULE（单源——"必须保留框架结构，只在 TODO 位填实现"）。
    框架段 = 强约束（必须保留的结构）与参考全文（弱约束学习素材）互补：「框架
    代码段走确定性注入、学习说明走 LLM 段」（决策点 3）。None / 空 = 现行为逐
    字节不变。reference_fulltexts 非空时在输出指令前插参考段（每条 id 标注 +
    截断全文），并加改写约束：参考资料里有的功能 → 适配当前所选模块接口的
    草稿实现；没有的 → 保持 TODO。
    """
    prompt = _build_user_prompt(
        problem_text,
        SKELETON_INTERFACES_HEADING,
        module_interfaces,
    )
    if topic_framework:
        prompt += (
            f"\n\n### 题型框架：{topic_framework.topic_type}"
            f"（来源 {topic_framework.source}）——必须保留的 main.c 结构：\n"
            f"```c\n{topic_framework.code}\n```\n"
            + SKELETON_FRAMEWORK_RULE
        )
    if reference_fulltexts:
        per_ref_budget = max(
            0, SKELETON_REFERENCE_TOTAL_BYTES // len(reference_fulltexts)
        )
        ref_parts = ["参考资料（可作实现草稿，不要整段照抄）："]
        for ref_id, fulltext in reference_fulltexts.items():
            ref_parts.append(
                f"### 参考资料 {ref_id}\n{_fit_fulltext_wire(fulltext, per_ref_budget)}"
            )
        prompt += "\n\n" + "\n\n".join(ref_parts)
        prompt += (
            "\n\n参考资料里有的功能，改写为适配当前所选模块接口的草稿实现"
            "（保证可编译）；参考资料里没有的功能，保持 TODO。"
        )
    return prompt + (
        "\n\n输出 main.c 骨架：按模块初始化序列排好调用，带注释与预留编写区（TODO），"
        "不确定的调用写成注释占位，不凭空造函数，保证可编译。"
        "所有 #include 只写头文件名（如 #include \"motor_stm32.h\"），"
        "不要带 code/、modules/ 等目录前缀。"
        + SKELETON_NO_UNUSED_RULE
    )


def _smoke_user_prompt(problem_text: str, module_interfaces: Sequence[str]) -> str:
    """自检冒烟 main.c 的 user 消息：赛题 + 接口块 + 逐模块自检与输出通道规则。"""
    prompt = _build_user_prompt(
        problem_text,
        SKELETON_INTERFACES_HEADING,
        module_interfaces,
    )
    return prompt + (
        "\n\n输出硬件自检冒烟 main.c（只自检，不实现赛题逻辑）："
        "对每个所选模块按顺序写一段自检——注释标注模块名 → 初始化该模块 → "
        "读一次/动一次 → 打印结果。"
        "输出通道按所选模块决定：如果所选模块里有 oled，初始化 OLED 并在 OLED 上"
        "逐段显示「模块名 OK/FAIL」（用 OLED_ShowString / OLED_ShowNum，"
        "不要用 printf/sprintf/snprintf）；如果同时有 debug_uart，串口用 "
        "debug_uart_send 同步回显同一行；如果只有 debug_uart 没有 oled，就用"
        "debug_uart_send 输出。"
        "接口块里标注「无平台 XX 版本」的模块，留注释「该模块无 XX 版本，未自检」"
        "（XX 照接口块里的平台名写，如 stm32 / mspm0）。"
        "所有 #include 只写头文件名（如 #include \"led.h\"），"
        "不要带 code/、modules/ 等目录前缀。"
        "不确定的调用写成注释占位，不凭空造函数，保证可编译。"
        + SKELETON_NO_UNUSED_RULE
    )


# ---------------------------------------------------------------------------
# 赛题库协议（工单 01）：长 PDF 拆条（年份 / 编号 / 题面全文）+ 编号提取
#
# 编号 = 年份（4 位数字）+ 题号（字母），合称 key（如 "2026C"）。拆条与编号
# 提取都是 json_mode 调用，输出走严格解析（parse_topic_split /
# parse_topic_number）——畸形输出抛 LLMError，宁可不放行也不带病进校对 /
# 入库流程（与模块简介校验同款：宁可大声失败也不带病入库）。
# ---------------------------------------------------------------------------

# 赛题编号格式与校验的唯一出处已回 topic_library（validate_topic_key），
# 拆条 / 编号提取的提示词与解析在这里消费，不重新定义。

TOPIC_SPLIT_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）赛题整理助手。用户会给你一份历年赛题 PDF 的全文。"
    "把其中每一道赛题拆成一条：year = 年份（4 位数字，如 2026）、number = 题号"
    "（单个大写字母，如 C）、problem_text = 题面全文（原样保留，不做摘要、"
    "不改写）。只输出 JSON 对象。"
)

TOPIC_NUMBER_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）赛题整理助手。判断给定文本是否来自某道具体赛题"
    "（题面原文）：是则提取它的编号（年份 + 单个大写字母题号，如 2026C），"
    "否则 key 给空串。只输出 JSON 对象：{\"key\": \"2026C\"} 或 {\"key\": \"\"}。"
)


def parse_topic_split(content: str) -> tuple[TopicDraft, ...]:
    """把模型返回的拆条 JSON 解析校验为 TopicDraft 列表。

    任何结构 / 内容问题（非 JSON、缺 topics 数组、条目缺字段、年份 / 题号
    格式非法、题面为空、编号重复）都抛 LLMError——模型输出不可信，宁可大声
    失败也不带病进入用户校对 / 入库流程。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("topics"), list):
        raise LLMError("模型输出缺少 topics 数组")
    if not data["topics"]:
        # 一份真实真题 PDF 不可能零赛题：空结果 = 模型读错 / 素材不是真题，
        # 大声失败比让用户面对空校对页更可操作（与"宁可大声失败"同哲学）
        raise LLMError("模型没有拆出任何赛题（PDF 可能不含赛题，或文本抽取失败）")
    drafts: list[TopicDraft] = []
    seen: set[str] = set()
    for index, item in enumerate(data["topics"]):
        if not isinstance(item, dict):
            raise LLMError(f"topics[{index}] 必须是对象")
        year = item.get("year")
        number = item.get("number")
        problem_text = item.get("problem_text")
        if not isinstance(year, str) or not year:
            raise LLMError(f"topics[{index}] 缺 year")
        if not isinstance(number, str) or not number:
            raise LLMError(f"topics[{index}] 缺 number")
        if not isinstance(problem_text, str) or not problem_text.strip():
            raise LLMError(f"topics[{index}] 缺题面或题面为空")
        draft = TopicDraft(year=year, number=number, problem_text=problem_text)
        message = validate_topic_key(draft.key)
        if message:
            raise LLMError(f"topics[{index}] {message}")
        if draft.key in seen:
            raise LLMError(f"模型重复拆出同一编号：{draft.key}")
        seen.add(draft.key)
        drafts.append(draft)
    return tuple(drafts)


def parse_topic_number(content: str) -> str | None:
    """把模型返回的编号提取 JSON 解析校验为 key（无编号返回 None）。

    任何结构 / 内容问题（非 JSON、缺 key、key 格式非法）都抛 LLMError。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError("编号提取结果必须是 JSON 对象")
    key = data.get("key", "")
    if not isinstance(key, str):
        raise LLMError("编号提取结果的 key 必须是字符串")
    if not key:
        return None
    message = validate_topic_key(key)
    if message:
        raise LLMError(message)
    return key


def _topic_split_user_prompt(pdf_text: str) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求。
    # 拆条全文全量直传不截断（截断 = 静默漏题）；长度由调用方按
    # TOPIC_SPLIT_LLM_CHAR_CAP 路由保证
    return (
        "历年赛题 PDF 全文：\n"
        + pdf_text
        + "\n\n只返回 json 格式的 JSON 对象："
        '{"topics": [{"year": "2026", "number": "C", "problem_text": "题面全文"}]}'
    )


def _topic_number_user_prompt(text: str) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    return (
        "文本：\n"
        + _truncate_content(text)
        + "\n\n只返回 json 格式的 JSON 对象：{\"key\": \"2026C\"} 或 {\"key\": \"\"}"
    )
