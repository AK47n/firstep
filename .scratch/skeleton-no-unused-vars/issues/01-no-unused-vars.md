# 01 — 骨架未用变量 4 警：预留占位声明产生编译警告，违背「0 错 0 警」验收标准

**What to build:** main.c 骨架生成提示词补「不声明未使用变量」约束（双端）——真机 2026C stm32 曾出 UV4 4 Warning（骨架 s_lock_state / s_welcome_state / s_zone_state / s_expect_id 第 29~32 行占位声明未用，AI 内联状态区残留），违背用户验收标准 0 错 0 警；现行提示词无此约束，靠后续重跑侥幸消除，无结构保证。

**Status:** 待实施（实施提示词见文末）

## 现状证据（2026-08-14 读码核实）

- **真机证据**：工单 module-universalization/05 验收记录第 60 行——2026C stm32 全管线 UV4 **0 Error(s)、4 Warning(s)**，警告 = LLM 骨架 main.c 的未使用变量声明（s_lock_state / s_welcome_state / s_zone_state / s_expect_id，第 29~32 行），「AI 内联状态区时的残留声明，非解散回归」。Keil 警告形态：#177-D declared but never referenced / #550-D set but never used。
- **现状**：`.scratch/real-run/out_2026C/main.c`（最终版）靠后续重跑消除 4 警——LLM 偶发达标，无提示词约束兜底。
- **提示词现状**：`SKELETON_SYSTEM_PROMPT`（`llm.py:113-119`）只有「保证骨架可编译」级约束，无未用变量规则；`_skeleton_user_prompt`（`llm.py:1934-1944`）尾句同样只有「保证可编译」。
- **双端教训**（ticket 06 判例）：判定范围 / 判据只改系统提示词、漏改用户提示词 → 模型按用户消息行事当场失败。骨架同款风险：尾句「保证可编译」是模型最直接读到的指令，规则必须同一调用双端都带（常量单源，照 VALIDATION_UNIVERSALITY_RULE 先例）。
- **失败形态**：未用变量警告不进修复循环（T3 修复循环只对 errors 触发），也不阻断产物——用户拿到带警告工程，违背 0 错 0 警标准。「warning 纳入修复循环」留作后续候选（未立单）。

## 修复方向（实施会话定措辞，红证先行）

1. **常量单源 + 双端**：新增 `SKELETON_NO_UNUSED_RULE`（唯一出处，照 VALIDATION_UNIVERSALITY_RULE 先例）——规则语义建议：**不声明未使用的变量：每个声明都必须被后续代码读取或赋值；预留状态一律写成注释（TODO），不写占位声明（未使用的声明产生编译警告）**。拼入 `SKELETON_SYSTEM_PROMPT` 与 `_skeleton_user_prompt` 尾句（同一 API 调用双端在场）。
2. **契约测试红证**：`test_skeleton_prompt_carries_no_unused_var_rule`——`_skeleton_user_prompt("赛题", ("x.h",))` 与 `SKELETON_SYSTEM_PROMPT` 双端断言规则关键词（如「未使用的变量」「占位声明」）；现行代码跑红 → 加常量后绿。注意 `_skeleton_user_prompt` 尚未入 tests/test_llm.py 的 import 面（需补）。
3. **真机复跑验证（核心验收）**：2026C 重生成骨架走 UV4 编译 → **0 Error(s) 0 Warning(s)**——提示词约束是概率性改善，必须真机证明对已复现形态（lock_control/zone 解散后内联状态区）有效；若仍出未用变量警 → 提示词措辞回炉，本工单不关。

## 实施边界

- src：`src/contest_generator/llm.py`（SKELETON_NO_UNUSED_RULE 常量 + 两处提示词拼入）。`generator.py` / `webapp.py` / `index.html` / `fix_errors.py` / `.scratch/real-run/generate_check.py` 零改动。
- tests：`tests/test_llm.py`（双端契约测试；`_skeleton_user_prompt` 补入 import 面）。既有骨架提示词测试（test_generate_main_skeleton_routes...、TRUNCATION_NOTICE 契约）不破。
- 不动：修复循环 / 事件词表 / 前端 / generate_check CLI。

## 验收标准

- [ ] 红证：契约测试在现行提示词下跑红（规则词不在双端）
- [ ] 修复后：契约测试绿 + 既有测试全绿 + `mypy src` 干净
- [ ] 真机：服务 8000 + `python .scratch/real-run/generate_check.py --reuse-recommend 2026C` → UV4 0 Error(s) 0 Warning(s)（警告数从构建日志确认；旧输出目录 out_2026C_stm32 若存在先删，generate_check 不清理旧 out）
- [ ] `git status` 只出现预期文件

## 实施提示词（新会话粘贴）

> 工单：`.scratch/skeleton-no-unused-vars/issues/01-no-unused-vars.md`（先读全文）。
> 任务：骨架生成提示词补「不声明未使用变量」约束（双端常量单源），红证先行，真机 2026C 复跑验证 0 警。
> 文件边界：只动 `src/contest_generator/llm.py` + `tests/test_llm.py`；`generator.py` / `webapp.py` / `index.html` / `fix_errors.py` / `.scratch/real-run/generate_check.py` 零改动。
> 关键：`SKELETON_NO_UNUSED_RULE` 常量唯一出处（照 VALIDATION_UNIVERSALITY_RULE 先例），`SKELETON_SYSTEM_PROMPT` 与 `_skeleton_user_prompt` 尾句同一调用双端拼入（ticket 06 双端漂移教训）；契约测试双端断言（`_skeleton_user_prompt` 需补入 tests/test_llm.py import 面）。
> 真机验收：服务 8000（启动命令见记忆 server-start-playbook）→ `python .scratch/real-run/generate_check.py --reuse-recommend 2026C`（先删旧 out_2026C_stm32）→ UV4 构建日志 0 Error(s) 0 Warning(s) 才算闭环；证据写 Comments，Status 改 resolved，docs 提交推送。

## Comments
