"""请求预算 wire 记账单源叶子模块（工单 budget-wire-unification/01）。

修复侧与推荐侧的请求体预算记账统一到本模块：wire 字节口径原语
（wire_size / fit_wire_budget，逐字迁自 fix_errors）与预算常量推导单源
（FIX_CONTEXT_TOTAL_BYTES / FIX_PREVIOUS_FIXES_CAP / REFERENCE_FULLTEXT_BYTES）。
叶子约束：本模块不 import 任何域模块（防环——llm→fix_errors 依赖链上任何
非叶子位置都无法被三方同时 import），llm.py / fix_errors.py 从本模块 import
并 re-export，既有测试 import 面不动。

wire 字节口径（工单 fix-request-budget/01 定案，budget-wire-unification/01
推广到推荐侧）：json.dumps ensure_ascii 序列化字节与 llm._chat 发送前预检
同口径（中文 \\uXXXX 转义 6 字节/字符、ASCII 1 字节），按字符数记账会低估
中文 6×；真实线格式是 json.dumps(payload).encode("utf-8") 且 ensure_ascii
默认开——「×3 字节」的 UTF-8 估算同样是假口径（旧推荐侧 cap 即此口径，
全中文最坏形态实发 ≈250KB 必炸 128KB 网关）。
"""

from __future__ import annotations

import json

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
# 余量内）→ 最坏形态总量 ≈119.5KB，余量 ≈10.7KB ≥ 10KB。最坏情况结构测试
# 钉死（tests/test_llm.py::test_fix_prompt_worst_case_fits_request_budget），
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

# 推荐侧全文注入 wire 字节预算（工单 budget-wire-unification/01）：旧口径
# REFERENCE_FULLTEXT_CAP=35000 字符按「×3 字节 ≈105KB ≤128KB 恒成立」估算
# ——但真实线格式是 json.dumps ensure_ascii=True（llm._chat 预检同口径），
# 中文实发 6 字节/字符：全中文最坏 35000 × 6 ≈ 210KB 单段超总量上限 1.6×，
# select 最坏形态结构测试 3B 口径假绿（同一载荷真实线 ≈256KB，红证实测
# 256001 字节 > 120832）。
#
# 取值反推（全中文最坏口径，与修复侧同款推导）：题面（4000 截断上限）× 6
# ≈ 24KB + 摘要 14 条 ≈ 7.6KB + 词表 ≈ 1.1KB + 澄清历史
# （CLARIFICATION_HISTORY_CAP=2500 字符 × 6 ≈ 15KB + 标注）+ 契约文本 ≈ 1KB
# + 系统提示词 ≈ 3.3KB + JSON 壳 ≈ 0.1KB + 参考清单 / 全文段壳 ≈ 0.5KB ≈
# 53.2KB（实测 53168 字节）→ 全文预算 = 128KB − 10KB 目标余量 − 53.2KB −
# 全文段壳 / 截断标注 ≈ 0.4KB ≈ 64.4KB → REFERENCE_FULLTEXT_BYTES = 67000
# （wire 字节）→ 最坏形态总量 ≈120.6KB，总余量 ≈10.5KB ≥ 10KB。最坏情况
# 结构测试钉死（tests/test_llm.py::
# test_selection_prompt_worst_case_fits_request_budget），改大即红。超出的
# 截头带标注（TRUNCATION_NOTICE 文案沿用），不静默丢内容。
REFERENCE_FULLTEXT_BYTES = 67000
