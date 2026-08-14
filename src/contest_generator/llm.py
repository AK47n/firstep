"""LLM 客户端抽象与生产实现。

生产实现 DeepSeekLLM 走 DeepSeek Chat Completions API（base_url / api_key /
模型来自本机配置文件 config.py）；HTTP 传输可注入假件，网络调用不进测试。
LLM 承担七类协议职责：赛题→模块选择、赛题简介生成（AI 预读题面给用户
一句话总览 + 功能要点）、main.c 骨架生成、模块简介生成与校验、母版提炼
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
import math
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Protocol, Sequence, TypeVar

from .budget import (
    FIX_PREVIOUS_FIXES_CAP,
    REFERENCE_FULLTEXT_BYTES,
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
from .manifest import ManifestSummary
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
    FunctionRequirement,
    ModuleSelection,
    OutOfLibrarySuggestion,
    REFERENCE_SOURCE_MANUAL,
    ReferenceSuggestion,
    SelectionError,
    build_module_selection,
)
from .topic_library import TopicDraft, validate_topic_key
from .wordlist import (
    DEFAULT_WORDLIST,
    HardwareWordGroup,
    format_wordlist_prompt,
)

# 截断标注契约（唯一出处）在 library.truncate_content / TRUNCATION_NOTICE
# （工单 03 迁共享层：reference_library 的逐文件截断同用此措辞，而其不能
# 运行时 import llm——环约束，TYPE_CHECKING 同款先例）——llm 导入重出。

# 模块推荐系统提示词（工单 10）：题面证据驱动的功能需求层 + 收敛自检。
# 行为要点与 ADR 0007 同源：逐句对照防脑补（找不出对应句的需求即脑补，删）、
# 实现覆盖检查机械产出库外建议（不是主观推荐）、库外建议 name 受硬件词表硬
# 约束（不懂不编、编造降级）、收敛循环以题面为裁判（删脑补 / 补遗漏 / 重查
# 覆盖）、题面证据不足以判定时向用户补问（有疑问一轮问全：一次性列全、
# 最多 10 条、不渐进追问）。
SELECT_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手，熟悉 MSPM0G3507（CCS）与 "
    "STM32F103C8T6（Keil5）两条平台线。分析赛题严格以题面原文为证据"
    "（赛题文本可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "）。"
    "题面已按句编号（如 1. 2. 3.），先逐句对照（每句对应一个功能需求或"
    "\"无功能\"），产出功能需求层：能力/外设级的稳定描述（声光提示 → "
    "LED/蜂鸣器、识别数字 → 视觉），粒度贴题面关键词；每条需求必须挂题面"
    "句子编号（sentence），找不出对应句的需求 = 脑补，删——禁止题外联想"
    "（\"送药小车所以需要视觉\"是脑补，题面要求识别数字才需要视觉）。"
    "逐条做实现覆盖检查：模块库里有实现 → 该需求的 modules（可勾选进工程）；"
    "无命中 → 库外建议 suggestions（name + 常识举例，仅展示、不进工程、"
    "不参与生成）。库外建议的 name 必须来自硬件词表（类别名或具体型号名，"
    "词表见用户消息）；具体型号不在词表内时，降级输出为它所属的类别名并"
    "在 category 字段注明，宁可给类别也不编造型号。以题面为裁判反复自检"
    "修订（删脑补 / 补遗漏 / 重查覆盖），连续两轮功能需求层一致即可保持"
    "不动。题面证据不足以判定时，在 questions 数组向用户补问，不要瞎猜；"
    "有疑问时一次性把所有疑问全部列出（宁全勿漏、每条具体可答、最多 10 条），"
    "用户一轮全部答完，不要分批渐进追问。用户已回答过的问题不要重复问，仅"
    "补充新疑问（与澄清阶段同规，问答历史在题面后的独立段）。只输出 JSON 对象。"
)

# 澄清阶段系统提示词（工单 01 推荐先澄清后收敛）：只看题面 + 已有问答历史，
# 输出仍存的疑问（空 = 澄清完成；有疑问一轮问全——一次性列全、最多 10 条、
# 不渐进追问）。不带模块库——疑问只来自题面证据不足，
# 与库内实现无关（库内有没有实现是收敛阶段的事）。
CLARIFY_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手。逐句核对赛题原文（赛题文本可能"
    "被截断，见末尾标注，" + TRUNCATION_NOTICE + "）：题面证据不足以判定某项"
    "要求（如识别方式、交互细节、性能指标）时向用户补问——有疑问时一次性把"
    "所有疑问全部列出（宁全勿漏、每条具体可答、最多 10 条），用户一轮全部"
    "答完，不要分批渐进追问；用户已回答过的问题"
    "不要重复问；没有疑问时输出空 questions 数组。只输出 JSON 对象。"
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

SKELETON_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。为赛题生成 main.c 骨架（赛题文本 / 模块接口过长"
    "可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "）：按所选模块的头文件"
    "接口排好初始化序列，带注释说明与预留编写区（TODO）。只调用给定接口中"
    "真实存在的函数，绝不凭空造函数；不确定的调用写成注释占位，保证骨架可编译。"
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

# 赛题简介生成（赛题简介步骤，wait-what 效果）：AI 预读题面给"这个赛题要
# 实现什么"的简短认知——第一行一句话总览 + 功能要点条目（把散落在题面各处
# 的全部实质要求整理出来，按性质分组，整体比原题短而清晰）。只展示给用户
# 确认理解，不进任何下游流程；纯文本契约，与参考文件简介同款（文本模式，
# 无结构化输出）。要求贴题面关键词、禁止脑补，与模块推荐的证据约束同源。
TOPIC_SUMMARY_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手，熟悉 MSPM0G3507（CCS）与 "
    "STM32F103C8T6（Keil5）两条平台线。为下面的赛题写一段简短简介"
    "（赛题文本可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "）："
    "第一行用一句话总览这个赛题要做一个什么样的装置 / 系统，随后每行一个"
    "功能要点（以「- 」开头），粒度贴题面关键词（如声光提示、测距、显示等）。"
    "把题面散落在各处的全部实质要求都整理出来：功能、约束（尺寸 / 电源 / "
    "精度等）、交互（按键 / 显示 / 声光提示等）按性质分组列成条目——条目数"
    "按题面实际要求来，不为省篇幅漏要求，也不要为凑条数拆句。严格以题面"
    "原文为证据，不要脑补题外功能。整体比原题短而清晰：压缩重复与过程性"
    "表述，保留全部实质要求。只输出简介文本，不要额外格式。"
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
SUMMARY_RETRY_LIMIT = 3

# 网络类失败的重试上限（工单 deepseek-retry-hardening/01）：网络层瞬断
# （连接重置 10054 / URLError / 超时 / 网关 5xx）3 连快重试大概率仍断
# （工单 reference-library-hygiene/03 真机 3/3 次运行撞此形态，重试 3 次
# 仍断、整轮推荐作废），改指数退避：最多重试 NETWORK_RETRY_LIMIT 次、间隔
# 按连续网络失败次数 2**n 秒（1/2/4/8）——序列由 tests/test_llm.py 钉死。
# 解析类仍走 SUMMARY_RETRY_LIMIT 快重试（工单 recommend-call-retry/01 行为
# 不变）。
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


def _truncate_content(content: str) -> str:
    """单内容截断（带标注）：超长内容只送前 EMBEDDED_CONTENT_CAP 字符。

    文案 / 标注唯一出处 = library.truncate_content（工单 03 迁共享层），此处
    只绑定 llm 的嵌内容预算常量；截断只影响发送素材，不改数据模型。
    """
    return truncate_content(content, EMBEDDED_CONTENT_CAP)


def _fit_fulltext_wire(fulltext: str) -> str:
    """全文注入的 wire 字节预算截断（工单 budget-wire-unification/01）：弃用
    字符 cap（REFERENCE_FULLTEXT_CAP「×3 字节」估算假口径——真实线
    json.dumps ensure_ascii=True 中文实发 6 字节/字符，全中文最坏形态必炸
    128KB 网关），改 wire 字节预算取最长前缀（budget.fit_wire_budget）+ 截头
    标注（TRUNCATION_NOTICE 文案沿用）——标注自身的 wire 字节计入预算（对齐
    fix 侧 read_file_contexts 既有做法：标注非免费，推导余量已含）。预算内
    原样返回（逐文件截断标注归 read_fulltext，此处零增删）。
    """
    fitted = fit_wire_budget(fulltext, REFERENCE_FULLTEXT_BYTES)
    if fitted != fulltext:
        fitted += (
            f"\n……（内容过长，已截断：仅展示前 {REFERENCE_FULLTEXT_BYTES} "
            f"wire 字节，原文共 {len(fulltext)} 字符；{TRUNCATION_NOTICE}）……\n"
        )
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


class LLMError(Exception):
    """LLM 调用或输出解析失败，message 说明具体问题。

    kind 区分错误类别（缺省 parse，向后兼容——存量单参构造全部按解析类）：
    network = 网络层瞬断（连接失败 / 超时 / 网关 5xx，重试有价值）；
    parse = 输出解析 / 业务失败。非 network 类别一律视为 parse。
    """

    def __init__(self, message: str, kind: str = ERROR_KIND_PARSE) -> None:
        super().__init__(message)
        self.kind = kind


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


class LLM(Protocol):
    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
        manual_fulltexts: Mapping[str, str] | None = None,
        clarifications: Sequence[tuple[str, str]] = (),
    ) -> ModuleSelection: ...

    def clarify(
        self, problem_text: str, clarifications: Sequence[tuple[str, str]]
    ) -> tuple[str, ...]: ...

    def summarize_topic(self, problem_text: str) -> str: ...

    def generate_main_skeleton(
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

    def topic_split_topics(self, pdf_text: str) -> tuple[TopicDraft, ...]: ...

    def topic_extract_number(self, text: str) -> str | None: ...


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
    ) -> None:
        self._config = config
        self._transport = transport or UrllibTransport()
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

        瞬时失败整次重问（_retry_parse，与归档判定同款兜底）：DeepSeek 偶发
        空内容 / 输出畸形会重问，最多 SUMMARY_RETRY_LIMIT 轮，仍失败大声抛错。
        """

        def parse(content: str) -> ModuleSelection:
            data = extract_module_selection_data(content)
            try:
                return build_module_selection(
                    data,
                    known_slugs=[s.slug for s in manifest_summaries],
                    known_reference_ids=[r.id for r in references],
                    hardware_words=self._hardware_words,
                )
            except SelectionError as exc:
                # 域判决错误由传输侧翻译回 LLMError（错误契约 502 / 文案逐字不变；
                # selection 不 import LLMError——否则与 llm → selection 既有边成环；
                # 翻译在闭包内，重试循环吃的是翻译后的 LLMError）
                raise LLMError(str(exc)) from exc

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
            ),
            parse=parse,
            label="模块选择",
            json_mode=True,
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

    def summarize_topic(self, problem_text: str) -> str:
        """赛题 → 简短简介（一句话总览 + 功能要点，文本模式，赛题简介步骤）。

        预读题面给用户"这个赛题要实现什么"的简短认知（wait-what 效果）：只
        展示、不进任何下游流程；赛题超长截断带标注（_truncate_content，与
        所有嵌内容调用同款预算）；瞬时失败整次重问（_retry_parse，与参考
        文件简介同款兜底）。
        """
        return self._retry_parse(
            system_prompt=TOPIC_SUMMARY_SYSTEM_PROMPT,
            user_prompt=_truncate_content(problem_text),
            parse=lambda content: content,
            label="赛题简介生成",
        )

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
                {
                    "role": "user",
                    "content": f"```c\n{_truncate_content(code)}\n```",
                },
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
        瞬时失败整次重问（_retry_parse ≤3 轮，与归档判定同款兜底）；域判决
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
        )

    def _retry_parse(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        parse: Callable[[str], RT],
        label: str,
        json_mode: bool = False,
    ) -> RT:
        """整次调用级重试（单调用契约共用原语，与批处理 _retry_batch 同哲学）。

        归档判定 / 逐文件简介这类"一次调用一个产物"的契约，LLM 异常或输出
        畸形时整次重问，仍失败大声抛错——宁可多花一次调用，也不带病进入归档 /
        入库流程（多文件归档此前无任何重试兜底，单次瞬时失败即整体放弃确认）。
        批内条目级补问（_retry_batch）服务"一批输出多个路径键控条目"的契约，
        这里是它的单调用孪生。

        错误类别分策略（工单 deepseek-retry-hardening/01）：网络类
        （LLMError.kind=network，连接失败 / 超时 / 网关 5xx）最多
        NETWORK_RETRY_LIMIT 次、按连续网络失败次数指数退避（1/2/4/8 秒，
        经 _backoff_sleep——真机教训：3 连快重试仍断、整轮推荐作废）；解析类
        （缺省 kind，空内容 / 畸形 JSON / 业务失败）保持 SUMMARY_RETRY_LIMIT
        次快重试（工单 recommend-call-retry/01 行为不变）。混合序列按每次
        失败各自记账：总尝试上限 = NETWORK_RETRY_LIMIT，解析类在第
        SUMMARY_RETRY_LIMIT 次尝试后仍失败即止。
        """
        last_error: Exception | None = None
        attempts = 0
        network_failures = 0
        while attempts < NETWORK_RETRY_LIMIT:
            attempts += 1
            try:
                content = self._chat(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    json_mode=json_mode,
                )
                return parse(content)
            except LLMError as exc:
                last_error = exc
                if exc.kind == ERROR_KIND_NETWORK:
                    network_failures += 1
                    if attempts >= NETWORK_RETRY_LIMIT:
                        break
                    _backoff_sleep(2 ** (network_failures - 1))
                elif attempts >= SUMMARY_RETRY_LIMIT:
                    break
        raise LLMError(
            f"{label}连续 {attempts} 次调用失败：{last_error}"
        ) from last_error

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

        模型一次输出大量 JSON 条目时偶发丢条目（判例 08：115 个文件一次返回
        漏了 1 个），严格解析失败后不整批重来：挖出已通过逐文件校验的合法
        条目（salvage——一个文件输出畸形只让它自己重问，好条目不连坐，见
        _extract_good_summaries / _extract_good_decisions），只对缺失路径补问，
        最多 SUMMARY_RETRY_LIMIT 轮；仍缺失就大声失败（宁可失败也不带病进
        下一阶段）。严格解析不校验覆盖（master 层职责）；这里知道素材范围，
        漏判即补问。跨轮去重：补问轮的响应可能复述已覆盖路径，同一路径只
        保留第一次结果。每次开始补问轮（重新发请求前）发射 retry 事件（契约
        唯一出处见 ProgressEvent）：轮次 1 起、缺失数 = 该轮要补问的文件数。
        """
        remaining = list(items)
        results: list[R] = []
        retry_round = 0
        for _ in range(SUMMARY_RETRY_LIMIT):
            if not remaining:
                break
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
            content = self._chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt(remaining)},
                ],
                json_mode=True,
            )
            try:
                parsed = parse(content, remaining)
            except LLMError:
                # 输出整体不可用（非 JSON / 形状错）——挖出合法条目只补问坏的，
                # 一个都挖不出才整批重问
                parsed = salvage(content, remaining)
                if not parsed:
                    continue
            results.extend(
                x for x in parsed if x.path not in {r.path for r in results}
            )
            covered = {r.path for r in results}
            missing = [x for x in remaining if x.path not in covered]
            if not missing:
                remaining = []
                break
            remaining = missing  # 漏判部分——只补问缺失路径
        if remaining:
            raise LLMError(
                f"{phase_label}多次补问后仍缺失 "
                + "、".join(sorted(x.path for x in remaining))[:300]
            )
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
        content = self._chat(
            [
                {"role": "system", "content": TOPIC_SPLIT_SYSTEM_PROMPT},
                {"role": "user", "content": _topic_split_user_prompt(pdf_text)},
            ],
            json_mode=True,
        )
        return parse_topic_split(content)

    def topic_extract_number(self, text: str) -> str | None:
        """从文本提取赛题编号（如 "2026C"）；不是赛题文本返回 None。

        与编号解析服务配套（topic_library.resolve_number 做确定性查库）：
        粘贴题面自动识别编号时走这里，AI 提取出的编号仍以查库结果为准。
        """
        content = self._chat(
            [
                {"role": "system", "content": TOPIC_NUMBER_SYSTEM_PROMPT},
                {"role": "user", "content": _topic_number_user_prompt(text)},
            ],
            json_mode=True,
        )
        return parse_topic_number(content)

    def _chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {"model": self._config.model, "messages": messages}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        body_bytes = json.dumps(payload).encode("utf-8")
        if len(body_bytes) > MAX_REQUEST_BYTES:
            # 体积断言兜底：所有嵌内容调用都应已截断 / 分批，仍超限说明有未兜底
            # 的长输入——请求发出前大声失败（可操作信息），而不是等网关 413
            raise LLMError(
                f"请求体过大（{len(body_bytes)} 字节 > {MAX_REQUEST_BYTES} 字节）："
                "嵌内容的调用应已按预算截断 / 分批，仍超限说明有未兜底的长输入"
                "（如异常巨大的赛题文本）——请减小输入或减少导入工程的文件大小"
            )
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
            if status == 413:
                # 网关的请求体大小限制；嵌内容调用已截断分批，仍出现说明有未
                # 兜底的超长输入（如超大赛题文本）——给出可操作提示
                raise LLMError(
                    "DeepSeek API 返回 413：请求体过大。嵌内容素材已按预算截断 / "
                    "分批发送，若仍触发，请检查赛题文本是否异常巨大，或减少导入"
                    "工程的文件数量与单文件大小"
                )
            if status >= 500:
                # 5xx = 网关 / 服务端瞬时故障（重试有价值，与连接失败同款指数
                # 退避）；4xx = 请求本身有问题（401 密钥 / 413 体积），保持
                # 缺省 parse 类快重试（与旧行为一致）——工单 deepseek-retry-
                # hardening/01 分策略
                raise LLMError(
                    f"DeepSeek API 返回 {status}：{body[:200]}",
                    kind=ERROR_KIND_NETWORK,
                )
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


def parse_clarify_questions(content: str) -> tuple[str, ...]:
    """把模型返回的澄清 JSON 解析校验为仍存疑问列表（空 = 澄清完成）。

    与 selection._parse_questions 同款宽松度：缺省 / 空 questions → 空元组
    （模型认为已无疑问，直接进收敛循环）；非空时必须是字符串数组——畸形
    输出抛 LLMError（模型输出不可信，宁可大声失败也不带病进收敛，与其它
    AI 契约同哲学）。
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
    return tuple(questions)


def parse_fix_suggestions(
    content: str, allowed_files: Sequence[str]
) -> tuple[FixSuggestion, ...]:
    """把模型返回的修复 JSON 严格解析为 FixSuggestion 列表（可空 = 无修复）。

    与其它 AI 契约同哲学（模型输出不可信，宁可大声失败也不带病进写回流程）：
    非 JSON / 非对象 / fixes 非数组 / 条目缺字段或字段类型错 / file 不在允许
    清单内 / old_snippet 为空 → 抛 LLMError（整次重问，_retry_parse ≤3 轮
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
    lines = ["赛题：", _truncate_content(problem_text)]
    if clarifications:
        lines.append(_clarification_history_segment(clarifications))
    lines.append(
        "只返回 json 格式的 JSON 对象："
        '{"questions": ["仍存的疑问，没有疑问时为空数组"]}'
    )
    return "\n".join(lines)


def _selection_user_prompt(
    problem_text: str,
    manifest_summaries: Sequence[ManifestSummary],
    references: Sequence[ReferenceSuggestion] = (),
    reference_fulltexts: Mapping[str, str] | None = None,
    manual_fulltexts: Mapping[str, str] | None = None,
    hardware_words: Sequence[HardwareWordGroup] = (),
    clarifications: Sequence[tuple[str, str]] = (),
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
        prompt += "\n\n" + format_wordlist_prompt(hardware_words)
    contract = (
        '{"requirements": [{"requirement": "功能需求（能力/外设级）", '
        '"sentence": 1（整数——对应题面句子编号，第 3 句就是 3；必须是整数，'
        '不是字符串"1"）, "modules": [{"slug": "库内命中模块", '
        '"reason": "为何满足该需求"}], "suggestions": [{"name": "硬件词表内的'
        '类别或型号名", "category": "词表外型号必填的所属类别名", "examples": '
        '["常识举例"]}]}], "questions": ["题面证据不足以判定时的补问，可省略"]'
    )
    if references:
        contract += ', "references": ["想读全文的参考文件 id，不需要可省略"]'
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
