"""请求预算 wire 记账单源叶子模块（工单 budget-wire-unification/01）。

修复侧与推荐侧的请求体预算记账统一到本模块：wire 字节口径原语
（wire_size / fit_wire_budget，逐字迁自 fix_errors）与预算常量推导单源
（FIX_CONTEXT_TOTAL_BYTES / FIX_PREVIOUS_FIXES_CAP / REFERENCE_FULLTEXT_BYTES）。
叶子约束：本模块不 import 任何域模块（防环——llm→fix_errors 依赖链上任何
非叶子位置都无法被三方同时 import），llm.py / fix_errors.py 从本模块 import
并 re-export，既有测试 import 面不变。

wire 字节口径（工单 fix-request-budget/01 定案，budget-wire-unification/01
推广到推荐侧）：json.dumps ensure_ascii 序列化字节与 llm._chat 发送前预检
同口径（中文 \\uXXXX 转义 6 字节/字符、ASCII 1 字节），按字符数记账会低估
中文 6×；真实线格式是 json.dumps(payload).encode("utf-8") 且 ensure_ascii
默认开——「×3 字节」的 UTF-8 估算同样是假口径（旧推荐侧 cap 即此口径，
全中文最坏形态实发 ≈250KB 必炸 128KB 网关）。

段级记账原语（工单 real-acceptance/05）：request_segments /
payload_wire_size / format_segment_breakdown——把「哪一段占了多少」从注释里的
手算变成可执行代码。**尺寸断言口径（本单定的硬约定）**：任何尺寸类断言/记账
一律走发送前 wire 字节（wire_size / 本模块原语），不得用快照函数返回值或
JSON 估算代账——词表 models 与「选购方案」段文本重复、models 条数与实发段
字节不同源，估算必偏（工单 08 立单时按 format_wordlist_prompt 估 +1942B，
实发只 +770B；按 JSON 增量估则偏高）。
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

# ===========================================================================
# wire 字节口径原语
# ===========================================================================


def wire_size(content: str) -> int:
    """内容序列化进 JSON 字符串后的字节数（json.dumps ensure_ascii=True 口径，
    与 llm._chat 发送前预检一致）：中文 \\uXXXX 转义 6 字节/字符、ASCII 1
    字节——预算记账必须同口径，按字符数记账会低估中文 6×（工单
    fix-request-budget/01 的根因教训）。减 2 = 剥掉 json.dumps 加的首尾引号。
    """
    return len(json.dumps(content, ensure_ascii=True)) - 2


def fit_wire_budget(content: str, budget: int) -> str:
    """按 wire 字节预算截取最长前缀（工单 fix-request-budget/01，逐字迁自
    fix_errors._fit_wire_budget）：wire 字节数随前缀长度单调不减（每字符至少
    1 字节），二分 O(log n) 次序列化取最大保留前缀——中文 6 字节/字符时约保留
    预算的 1/6 字符，纯 ASCII 几乎全额保留（比统一按字符打折更贴内容）。预算
    内无需截断时原样返回。截断标注文案自身的 wire 字节由调用方追加并计入预算
    （对齐 fix 侧 read_file_contexts 既有做法：标注非免费、进记账，推导余量
    已含）。
    """
    if wire_size(content) <= budget:
        return content
    lo, hi = 0, len(content)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if wire_size(content[:mid]) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return content[:lo]


# ===========================================================================
# 段级记账原语（工单 real-acceptance/05）
# ===========================================================================
#
# 与 llm._chat_once 发送前预检**同一对象同一口径**：body_bytes =
# json.dumps(payload).encode("utf-8")。request_segments 只分解这一个对象，
# 不做任何估算——Σ段 = 实发 total 是**逐字节可断言**的（tests 用等式钉死），
# 这正是本单要的口径：账本与实测同源，不是「注释里手算得挺像」。

# message 段的键名形态（含角色，同 role 多条按序编号）：'msg0:system' /
# 'msg1:user' …——预检错误与近限告警都按此读，测试按名断言防漂移。
# 键名格式在此一处成形（`request_segments` 产出、消费方按 `msg{index}:{role}`
# 读取），不另设构造函数——多一层包装只会多一处要同步的地方。


def payload_wire_size(payload: Mapping[str, Any]) -> int:
    """整个请求体的实发字节数（= 发送前预检那一行，唯一真值口径）。

    口径与 llm 侧预检同源但**依赖方向不反**（叶子模块不 import 域模块）：
    两边都是 `len(json.dumps(payload).encode("utf-8"))`，llm 调本函数做预检。
    """
    return len(json.dumps(payload).encode("utf-8"))


def request_segments(payload: Mapping[str, Any]) -> dict[str, int]:
    """请求体的段级 wire 分解：每条 message（含角色）+ 顶层其余字段。

    每条 message 记该 message `content` 自身的 wire 字节（与
    BudgetTracker.request_sizes 的探针口径一致），顶层其余字段记
    「json.dumps({key: value}) − 2」（剥掉外层 {}，键名自身计入该段——
    字段是请求的一部分，不该漏账）。messages 键本身贡献的引号/冒号/逗号
    不含在任何一段里（几字节的 JSON 壳），所以 Σ段 ≤ total，差额就是壳——
    **不假装它为零**：对账断言写成「Σ段 + 壳 = total」，壳单独量。
    """
    segments: dict[str, int] = {}
    for index, message in enumerate(payload.get("messages") or ()):
        if not isinstance(message, Mapping):
            continue
        segments[f"msg{index}:{message.get('role') or '?'}"] = wire_size(
            str(message.get("content") or "")
        )
    for key, value in payload.items():
        if key == "messages":
            continue
        segments[str(key)] = len(json.dumps({key: value}).encode("utf-8")) - 2
    return segments


def format_segment_breakdown(
    payload: Mapping[str, Any],
    *,
    top: int = 4,
    keywords: Sequence[str] = (),
    total: int | None = None,
) -> str:
    """段级分解的可读单行（近限告警 / 预检拒发日志用）。

    只输出**元数据**（段名 + 字节数），不含任何请求内容——与观测面
    「不含 prompt / response」的脱敏契约一致。按字节降序取前 `top` 段；
    `keywords` 命中的段无视 top 恒列出（例如「被拒时至少要知道全文段和
    历史段占了多少」）。`total` 供调用方传入已算好的实发字节（热路径上
    避免重复序列化整个请求体）；缺省自算。空请求体等退化形态返回空串。
    """
    segments = request_segments(payload)
    if not segments or total == 0:
        return ""
    if total is None:
        total = payload_wire_size(payload)
    shell = payload_shell_wire_size(payload, segments=segments, total=total)
    ranked = sorted(segments.items(), key=lambda item: (-item[1], item[0]))
    picked = [item for item in ranked[: max(top, 0)]]
    if keywords:
        picked_keys = {key for key, _ in picked}
        picked.extend(
            item
            for item in ranked
            if item[0] not in picked_keys
            and any(keyword in item[0] for keyword in keywords)
        )
    shown = "/".join(f"{key}={value}B" for key, value in picked)
    rest = len(segments) - len(picked)
    if rest > 0:
        shown += f"/其余{rest}段"
    return f"{total}B（{shown}/JSON壳={shell}B）"


def payload_shell_wire_size(
    payload: Mapping[str, Any],
    *,
    segments: Mapping[str, int] | None = None,
    total: int | None = None,
) -> int:
    """JSON 壳（花括号 / 引号 / 逗号 / messages 键名）的 wire 字节。

    = payload_wire_size − Σ request_segments；恒 ≥ 0。对账等式
    「Σ段 + 壳 = total」即由此可断言（壳是残差，不许被并进任何内容段）。
    `segments` / `total` 供已有结果的调用方传入（避免重复分解 / 序列化）。
    """
    resolved = request_segments(payload) if segments is None else segments
    if total is None:
        total = payload_wire_size(payload)
    return total - sum(resolved.values())


# ===========================================================================
# 段级预算派生（工单 real-acceptance/05：基础段先扣，余量才给可裁段）
# ===========================================================================

# 统一请求余量下限（wire 字节）：每条请求线的最坏形态都必须 ≤
# llm.MAX_REQUEST_BYTES − 本值。单源的理由：此前各结构测试各写各的
# （select 两处写 2KB、fix / skeleton / clarify 写 10KB），没有任何一处
# 说明「为什么这条线是 2KB 那条是 10KB」——实际读法是**它们互不知情**：
# 推荐侧被词表段 15 次逐批增长一路啃到 2KB，另三条线没跟着动。统一到
# 单源后改一处即全改，且 docstring 必须写明为何取下界而不是更大。
#
# **不是测试专用常量**：生产侧由 llm._chat_once 经 `payload_budget_state`
# 消费（贴边留痕 / 超限拒发都按它判），结构测试用同一函数断言同一条下界
# ——「口径」与「执行」同源，不是两处各写一个数。
#
# 取 2048（2KB）的理由（工单 real-acceptance/05 实测）：推荐侧最坏形态
# （真实库 86 条摘要行 + 满额全文段 + 满额历史段 + 预筛注记）在**用满所有
# 段级预算**时已是本值左右，取 10KB 会让推荐侧直接越界（实测 HEAD 余量
# 仅 728B）——那是「把断言改到红」而不是「把请求改小」。10KB 是历史遗留：
# budget.py 的 FIX_CONTEXT_TOTAL_BYTES 推导里确实按 10KB 目标余量反推，
# 但推荐侧从没满足过同款余量。所以本单的选择是**如实统一到下界**，并在
# 下文把每段的实测值记账清楚——而不是继续在两个数之间各说各话。
REQUEST_RESERVE_BYTES = 2048


def payload_budget_state(
    payload: Mapping[str, Any],
    *,
    limit: int,
    total: int | None = None,
) -> dict[str, int | bool]:
    """一次请求体相对「硬限 + 统一余量」的位置（工单 real-acceptance/05）。

    发送前预检与结构测试**共用本函数**，所以「余量下界」只有一个判据来源：
    `within_reserve`（headroom ≥ reserve）= 合格；`near_limit`（≥90% 硬限）
    是要留痕的贴边形态；`over_limit` 是要拒发的超限形态。`total` 供调用方
    传入已算好的实发字节（热路径避免重复序列化整个请求体）。

    叶子约束下的依赖方向：本模块**不知道** MAX_REQUEST_BYTES 在哪（那是 llm
    的常量），`limit` 由调用方传入——本函数只负责「按统一口径算位置」。
    """
    if total is None:
        total = payload_wire_size(payload)
    headroom = limit - total
    return {
        "total": total,
        "limit": limit,
        "reserve": REQUEST_RESERVE_BYTES,
        "headroom": headroom,
        "within_reserve": headroom >= REQUEST_RESERVE_BYTES,
        "near_limit": total * 10 >= limit * 9,
        "over_limit": total > limit,
    }


# ===========================================================================
# 预算常量（推导单源，原分居 llm.py / fix_errors.py 的镜像注释合此）
# ===========================================================================

# 修复请求的文件上下文总预算（wire 字节，工单 fix-request-budget/01）：LLM
# 请求体有硬性大小限制（llm.py MAX_REQUEST_BYTES 128KB）。记账口径从「字符」
# 改为 json.dumps ensure_ascii 序列化字节（与 llm._chat 发送前预检同口径：
# 中文 \uXXXX 转义 6 字节/字符、ASCII 1 字节）——旧字符口径下 49152 字符
# 中文最坏 ≈295KB，单段超总量上限 2×+，修复循环最后防线断（预检 LLMError
# 无 kind → 快重试同尺寸必败）。
#
# 修复请求总量预算反推（全中文最坏口径，与 _chat 发送前预检一致——不按
# UTF-8 的 3 字节估）：系统提示词 ≈3.8KB（实测，约束 7 告警修复指引后）+
# JSON 壳 ≈0.15KB + 报错全文（4000 字符截断 + 标注）≈24.3KB + 赛题（4000
# 截断上限，2026C 实测 2626 / 2021F 实测 2796 均在内）≈24KB + main.c（4000
# + 标注）≈24.3KB + 回喂段（FIX_PREVIOUS_FIXES_CAP + 标注）≈15.5KB +
# dropped 清单 / 模块清单 / 平台 / 标题分隔 ≈5.3KB ≈ 96.9KB（实测）→ 文件
# 上下文余量 = 128KB − 10KB 目标余量 − 96.9KB ≈ 21.1KB →
# FIX_CONTEXT_TOTAL_BYTES = 23000（wire 字节，每文件截断标注 ≈0.12KB 含在
# 余量内）→ 本侧最坏形态**实测 120128B**（工单 real-acceptance/05 现算，
# .scratch/real-acceptance/probe-05-headroom-lines.txt），距硬限 10944B。
# 
# **口径更正（工单 real-acceptance/05）**：此前的记账注释写「≈119.5KB，余量
# ≈10.7KB ≥ 10KB」——那个数**是修复侧自己的**，被当成推荐侧预算的依据引用了
# 很久（推荐侧真实库最坏形态当时实测 128405B，差 6KB+）。同一份注释里的
# 「10KB 目标余量」也不是全局口径：推荐侧从没满足过它。本单起，**统一余量
# 单源 = REQUEST_RESERVE_BYTES**（下文），各侧结构测试都断言同一条下界；
# 每侧的最坏形态实测值由本模块的段级记账原语现算，不再手算。
# 最坏情况结构测试钉死（tests/test_llm.py::test_fix_prompt_worst_case_fits_request_budget），
# 改大任一上限即红。超预算的文件不发送、在提示词里点名（防静默丢失）。
FIX_CONTEXT_TOTAL_BYTES = 23000

# 修复请求回喂段合计截断上限（字符，工单 fix-request-budget/01）：previous_fixes
# 逐条（file:line status + reason）随轮数无界增长，是修复请求体预算的第二大
# 漏点（第一大是文件上下文旧字符口径，FIX_CONTEXT_TOTAL_BYTES 已改 wire 字节
# 记账）。与 llm.CLARIFICATION_HISTORY_CAP 同哲学：段级合计截头带标注
# （truncate_content 单源）——回喂只作「重试时逐字对齐重写」的判据，最坏形态
# （N 条长 reason）仍 ≤ 本上限 × 6 字节 + 标注 ≈ 15.5KB（推导见
# FIX_CONTEXT_TOTAL_BYTES 注释）。
FIX_PREVIOUS_FIXES_CAP = 2500

# 骨架参考段合计 wire 字节预算（工单 skeleton-smoke-refs/02 真机验收补）：
# 骨架 prompt 一次注入锚定 ∪ 手动多篇全文——单篇照 REFERENCE_FULLTEXT_BYTES
# 截断会 N 篇合计撑爆 MAX_REQUEST_BYTES（真机 2021F stm32 两篇 195232 字节
# > 131072，预检 502）。骨架基础段（题面/接口块/系统提示词/JSON 壳）最坏
# ≈88KB，给参考段合计 40KB → 最坏 ≈128KB 边缘——取值保守：多篇时每篇按
# 篇数均分本预算，短篇剩余不回收（实现简单优先，预检仍兜底）。
SKELETON_REFERENCE_TOTAL_BYTES = 40000

# 推荐侧全文注入 wire 字节预算（工单 budget-wire-unification/01）：旧口径
# REFERENCE_FULLTEXT_CAP=35000 字符按「×3 字节 ≈105KB ≤128KB 恒成立」估算
# ——但真实线格式是 json.dumps ensure_ascii=True（llm._chat 预检同口径），
# 中文实发 6 字节/字符：全中文最坏 35000 × 6 ≈ 210KB 单段超总量上限 1.6×，
# select 最坏形态结构测试 3B 口径假绿（同一载荷真实线 ≈256KB，红证实测
# 256001 字节 > 120832）。
#
# 取值反推（全中文最坏口径，与修复侧同款推导）：题面（4000 截断上限）× 6
# ≈ 24KB + 摘要 14 条 ≈ 7.6KB + 词表 ≈ 5.4KB（WORDLIST_PROMPT_BYTES
# 段级预算——工单 buy-guide/01 后词表行含选购方案名、体积过 3KB；
# wiki-modules-batch4 增补语音/身份方案后实测 4521，预算升 4700；
# wiki-modules-batch5 增补 I2C 增强件 4 方案 + 存储/数据记录新分类后完整
# wire 实测 4925，预算升 5200——全量送达 + 余量，2026-09-06；
# wiki-modules-batch6 增补环境监测 4 方案后完整 wire 实测 5201，预算升
# 5400——全量送达 + 余量，2026-09-07；
# wiki-modules-batch7 增补气体/空气 4 方案后完整 wire 实测 5495，预算升
# 5700——全量送达 + 余量，2026-09-08；
# wiki-modules-batch8 增补环境类第二组 4 方案（火焰/土壤湿度/人体红外/微波
# 雷达）后完整 wire 实测 5900，预算升 6100——全量送达 + 余量，2026-09-06）
# + 澄清历史
# （CLARIFICATION_HISTORY_CAP=2500 字符 × 6 ≈ 15KB + 标注）+ 契约文本 ≈ 1KB
# + 系统提示词 ≈ 3.3KB + JSON 壳 ≈ 0.1KB + 参考清单 / 全文段壳 ≈ 0.5KB ≈
# 60.3KB → 全文预算 = 128KB − 10KB 目标余量 − 60.3KB − 全文段壳 / 截断标注
# ≈ 0.4KB ≈ 60.3KB → REFERENCE_FULLTEXT_BYTES = 63000（按最坏情况结构测试
# 实测校准：词表段增量后总量 129165 > 129024 边界，全文降 1KB 至 63000 →
# ≈128252，距 MAX_REQUEST_BYTES−2KB 边界余 ≈770B；改大即红，见
# tests/test_llm.py::test_selection_prompt_worst_case_fits_request_budget）。
# 超出的截头带标注（TRUNCATION_NOTICE 文案沿用），不静默丢内容。
# 词表段变更配套（2026-09-06，wiki-modules-batch5）：词表完整 wire 实测 4925、
# 预算 4700→5200 → 词表段全量 4925 比截断形态 4700 多 225B → 全文降 500B 回
# 62500 保 2KB 边界余量（红证见 worst-case 结构测试实测）。
# 词表段变更配套（2026-09-08，wiki-modules-batch7）：词表完整 wire 实测 5495、
# 预算 5400→5700 → 词表段全量 5495 比截断形态 5300 多 195B → 全文降 500B 回
# 62000 保 2KB 边界余量（同 batch5 口径；红证见 worst-case 结构测试实测）。
# 词表段变更配套（2026-09-06，wiki-modules-batch8）：词表完整 wire 实测 5900、
# 预算 5700→6100 → 词表段全量 5900 比截断形态 5700 多 200B → 全文降 500B 回
# 61500 保 2KB 边界余量（同 batch5/7 口径；红证见 worst-case 结构测试实测）。
# 词表段变更配套（2026-09-09，wiki-modules-batch9）：词表完整 wire 实测 6341、
# 预算 6100→6600 → 词表段全量 6341 比截断形态 6100 多 241B → 全文降 500B 回
# 61000 保 2KB 边界余量（同 batch5/7/8 口径；红证见 worst-case 结构测试实测）。
# 词表段变更配套（2026-09-11，wiki-modules-batch10）：词表完整 wire 实测 6565、
# 预算 6600→6800 → 词表段全量 6565 比旧截断形态 6600 少 35B → 最坏形态总量
# −35B，全文 61000 不动（2KB 边界余量保持；llm.py 同款记账注释）。
# 词表段变更配套（2026-09-11，wiki-modules-batch11）：词表完整 wire 实测 7051、
# 预算 6800→7300 → 词表段全量 7051 比旧截断形态 6634 多 417B → 全文降 500B 回
# 60500 保 2KB 边界余量（同 batch5/7/8/9 口径；红证见 worst-case 结构测试实测）。
# 词表段变更配套（2026-09-12，wiki-modules-batch12）：词表完整 wire 实测 7239、
# 预算 7300→7500 → 词表段全量 7239 比旧截断形态 7134 多 105B → 全文降 100B 回
# 60400 保 2KB 边界余量（同 batch5/7/8/9 口径；红证见 worst-case 结构测试实测）。
# 词表段变更配套（2026-09-06，wiki-modules-batch13）：词表完整 wire 实测 7692、
# 预算两级上调 7500→7900（7600/7800 中间步）→ 词表段全量 7692 比旧截断形态
# 7334 多 358B → 全文两级降 100B 回 60100 保 2KB 边界余量（同 batch5/7/8/9/12
# 口径；红证见 worst-case 结构测试实测）。
# 词表段变更配套（2026-09-12，wiki-stm32-batch11/02）：词表完整 wire 实测
# 8259、预算 8300→8500 → 词表段全量 8259 比旧截断形态 8134 多 125B → 全文
# 27000 不动（worst-case 结构测试 + 真实库预算回归实测保持 ≥2KB 边界余量；
# batch12 口径：+105B 也仅降 100B——本批预算上调节省性复核后不动）。
# 模块摘要段入账（2026-09-06，wiki-modules-batch13 + module-preselect/02）：
# 摘要段从预算推导的「14 条 ≈ 7.6KB」涨为真实库 mspm0 84 条 ≈ 73.1KB wire
# （stm32 24 条 ≈ 12.2KB），**该增长从未入账**——旧推导只记账词表段逐批
# 增长。现状（摘要 73.1KB + 全文 60100）最坏形态实测：mspm0 195000B 超限
# 64KB、stm32 133578B 超限 2506B（.scratch/recommend-covered-check/
# measure_select_wire.py）；既有结构测试用固定 14 条假摘要因此假绿。修复：
# 摘要段经题面预筛排序 + MODULE_SUMMARY_BYTES=40000 段级预算截断（工单
# module-preselect/01，行边界、保底 20 条）→ 摘要段 ≤ 40000 入账；全文段
# 相应下调：固定段（题面 24K + 历史 15K + 词表 7.9K + 清单 4.1K + 系统
# 提示 ~3.8K + 壳/契约 ~1.7K ≈ 56.6K）→ 全文预算 = 128K − 2K 目标余量 −
# 56.6K − 40K（摘要段预算上界）≈ 29.4K → 取 27000（红证实测：校准脚本
# mspm0 最坏形态 28000 时 128605B ≤ 129024 边界余 419B 过紧；27000 保
# ~3KB 呼吸，单篇全文 ≈4500 中文字，两级注入「清单 → 点名 → 回读」下
# 足够——被测大参考文件 160K 字符仍按分段截断契约带标注送达）。
# 词表段变更配套（2026-09-17，工单 real-acceptance/08）：词表 models 补方案
# 裸名（B1 数据对齐——把「提示词给模型看过的名字」登记进闸认的合法 name 域，
# 模型照抄方案名不再被拒；现场 2022C 连续三轮挂在这一类名字上）→ 词表段实发
# 8849 → 9619（+770，受「全量送达 + 最坏形态留余量」双重约束，只收得下 15 条，
# 其余 38 条未入选——逐条裁定与清单见工单 08 与
# .scratch/recommend-domain-reject/patch-18-wordlist-models.py）。
# **基线已在边界内 97B**（HEAD 实测 mspm0 128927B，距 129024 自设边界仅 97B）→
# 任何有意义的词表补数据都必然越界，只能压缩余量 + 用满全文可降空间：
# 全文降 1400B 至 **25600**（该值当时读作「三条全文用例钉死的下限」——手动全文
# 25356B 必须原样送达，fit 上限 25600−166=25434 ≥ 25356，再低即
# test_select_prompt_embeds_manual_fulltexts_with_label 红。**工单 05 更正**：
# 该「下限」其实只是**一条**用例的**写死**夹具体量（那条夹具已改为按常量联动
# 推导），不是契约——真正的契约是「预算内原样送达、file_label 保留」，与夹具
# 字数无关）。
# 校准后实测 mspm0 **128293B**（距自设 2KB 边界 129024 余 731B、距硬限 131072
# 余 2779B——比基线余量 97B **更宽**，因为全文这一降比词表这一涨多）。下一个往
# 词表加内容的人：先看 measure-18-wordlist-budget.py 量两条传导路径（词表段 +
# 摘要段），别按 JSON 增量估；且入选顺序按**真机可达性**排（本批第一版按成本排，
# 真机当场打到顺延里的长句名，返工重排）。
#
# 25600 → **23400**（2026-09-17，工单 real-acceptance/05 段级重分配）。
# 上一段的 128293B/731B 是**不带预筛注记**的形态；生产路径带注记（webapp 预筛
# 发生时必须告知模型清单不是全量），实测 **128405B / 余量 619B**——比记账值又
# 紧 109B。本单把这笔账做成可执行段级账本（tests/test_llm.py::
# test_select_segment_ledger_matches_measured_segments），用它反推本常量：
#
#   上限 131072 − 统一余量 REQUEST_RESERVE_BYTES(2048) = 129024
#   先扣**基础段** 63341（题面 4000 中文 + 86 条预筛摘要行 + 预筛注记 +
#     输出契约；实发现量，库驱动，**不可裁**）
#   再扣条件规则段 3725（多实例 1222 + 同组互斥 618 + 题面核查 1885；
#     库内有对应标注才出段，同属不可裁）
#   再扣 system 提示词 5705 + JSON 壳 86 + 词表段预算 12150 + 候选清单段预算 4096
#   + 澄清历史段实测形态 15438
#   余量 = 129024 − 63341 − 3725 − 5705 − 86 − 12150 − 4096 − 15438 = 24483
#   全文段占「内容预算 + 段壳 ≈158」→ 取内容 23400（账本用满 **128099** ≤
#   129024，余 925B 呼吸位）；全文取 24400 则用满 129099 **超 75B** 即红，
#   23400 是当前基础段下的可行上界。
#
# 实施后实测（证据 .scratch/real-acceptance/verify-05-segment-budget.txt）：
#   mspm0 真实库最坏形态 **125476B（余 5596B）**、stm32 **124856B（余 6216B）**
#   ——同形态在工单 08 结束时为 128405B / 619B。比记账值宽松，因为本单同时
#   修掉了 `_fit_segment_wire` 的标注超预算（−281B）并降了全文段（−2200B）。
#   四条线现状：select mspm0 125476 / select stm32 124856 / clarify 91338 /
#   skeleton 67834 / fix 120128，全部满足统一余量下界 129024。
#
# **为什么不再抬一点**：词表段（预算 12150 / 实发 9623）虽有 2527B 未用满，
# 但那是工单 08 明确留的「不瘦身反而涨预算」位（闸的合法 name 数据，截断 =
# 模型看不到合法名），故本轮不再动它——腾空间的方向仍是**全文段**（本常量），
# 与 issue-08 同向。
#
# **本常量现在是「合计」预算（工单 05 规格评审补）**：`_selection_user_prompt`
# 此前对**每篇**全文各自 fit 到本值，篇数不受约束（模型可点名多篇、调用方也可
# 给多篇）→ N 篇 = N × 本值，段级账本不再是上界（实测 4 篇满额即 125634B 且
# 加篇即越界）。现按篇数均分（`_reference_fulltext_total_budget`，与骨架侧
# SKELETON_REFERENCE_TOTAL_BYTES 同款），单篇形态逐字节等价。
#
# 代价如实记账：本单同时把手动全文用例的夹具改为**按本常量联动推导**
# （tests/test_llm.py::test_select_prompt_embeds_manual_fulltexts_with_label：
# 旧夹具写死 700 份 = 25225B wire，超新预算必截断），并删掉该用例里
# 「必须超 4000 **字符**」的旧断言——4000 是字符口径的旧截断上限，在 23400B
# 级预算下与「预算内不截断」不可兼得；核心行为（不被旧上限截断、file_label
# 原样）改由 `TRUNCATION_NOTICE not in message` 直接守。
REFERENCE_FULLTEXT_BYTES = 23400

# 相关候选清单段合计 wire 字节预算（工单 02 相关候选自动扩容）：recommend
# 启 15 条相关候选后，清单段现实形态 ≈4.7KB（真实库简介 194-348 字/条，
# 远超 80 字/条的乐观估算——实测脚本 .scratch/ref-related-autoload/
# measure_suggestions_wire.py）。清单段 join 后整段截断（_fit_segment_wire，
# 标注用通用 TRUNCATION_NOTICE 文案「内容过长，已截断：仅展示前 N wire 字节」）
# ——最坏新形态 ≈128.2KB，距 MAX_REQUEST_BYTES（131072）余约 2.8KB、距
# 2KB 边界（129024，worst-case 结构测试断言）余约 830B；断言相应从 −6KB
# 收紧为 −2KB（红证先行校准，见 tests/test_llm.py::test_selection_prompt_worst_case_fits_request_budget）。
REFERENCE_SUGGESTIONS_MAX_WIRE_BYTES = 4096

# 相关候选条数上限（工单 02）：recommend 阶段候选清单扩容的条数上限——
# 题面外设词命中 → 得分降序截断，每轮成本增量 ~2-5K token（清单段 + 点名
# 后全文，全部受 REFERENCE_SUGGESTIONS_MAX_WIRE_BYTES / REFERENCE_FULLTEXT_BYTES
# 兜底）；相关候选两级照旧（清单 → 点名 → 回读），不直读。
RELATED_CANDIDATES_LIMIT = 15

# 骨架自动关联例程条数上限（工单 03）：骨架阶段按选中模块 / 题面把未锚定
# 相关例程全文注入参考段（与手动选参考同一通道），top-4 截断——全文经
# SKELETON_REFERENCE_TOTAL_BYTES 按篇均分兜底（4 篇 ≈10KB/篇，与既有骨架
# 最坏 3 篇形态同量级，worst-case 结构测试余量 ≥10KB 保持）。
SKELETON_RELATED_LIMIT = 4

# 模块摘要段 wire 字节预算（工单 module-preselect/01）：推荐提示词「模块库
# 可用模块」摘要行全量注入的段级预算——旧预算推导按「摘要 14 条 ≈ 7.6KB」
# 记账，真实库（批次 13 后 mspm0 84 条）摘要 wire 实测 73123B ≈ 73.1KB，
# 最坏形态 select 载荷实测 195000B > MAX_REQUEST_BYTES（131072）超限 64KB
# （stm32 线 24 条 12243B，最坏形态 133578B 亦超限 2506B）；结构测试
# test_selection_prompt_worst_case_fits_request_budget 用固定 14 条假摘要
# 样例因此假绿。本预算 = 摘要段的上界（预筛命中降序 + 预算截断，行边界），
# 截断后摘要段该值以内 + 调低 REFERENCE_FULLTEXT_BYTES 保 2KB 边界余量
# （红证校准见 test_recommend_real_library_budget，工单 02）。取 40000：
# 够 mspm0 线命中集常态送达（平均行 wire ≈ 870B，按 46 条 ≤ 预算），
# 同时给全文段留足；数值以红证实测为准（工单 02 校准）。
#
# 摘要行瘦身入账（2026-09-08，工单 preselect-visibility/01）：预筛仍截断的根因
# 不是预算太小而是行太长——完整行含套件段（占摘要字节 23.5%，且带淘宝/天猫
# 采购链接噪声），全库 stm32 86.6KB / mspm0 78.8KB。一级清单行改瘦身形态
# （slug + 有界首句 100 字符 + 依赖 + 多实例 + 副产物/互斥标记，套件段不进
# 一级行，manifest.ManifestSummary.lean_copy + to_line）后实测 stm32 28071B /
# mspm0 28062B（生产实现量得，非探针自算）——**全库可装，截断消失**（复测
# .scratch/library-audit/probe_lean_variants.py 走同一实现；不变量
# test_manifest.py::test_lean_summary_lines_fit_preselect_budget_for_real_library
# 断言余量 ≥5KB）。
# 本数值保持 40000 不动：仍是段级上界（库长大到装不下时截断机制照旧兜底）。
MODULE_SUMMARY_BYTES = 40000

# 预筛保底下限（工单 module-preselect/01）：预算截断后不足本数 → 扩到排序
# 后前 MIN_PRESELECT 条。覆盖保底：命中稀少时清单不过短（题面证据驱动的
# 命中集 + 前部常备模块都可见）。现实库形态 20 条 × 平均行 ≈ 17KB，远小于
# MODULE_SUMMARY_BYTES，保底不破坏预算。改小 = 清单可能过短漏覆盖；改大 =
# 保底形态接近全量（预筛失去意义），保持 20。
MIN_PRESELECT = 20
