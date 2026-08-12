# 01 — LLM old_snippet 变形容忍（前缀归一化匹配兜底）

**What to build:** 修复 compile-error-fix/01 真机暴露的"LLM old_snippet 与文件逐字不匹配 → 修复白跑一轮"问题：`apply_fixes` 在精确匹配失败后增加**行首前缀归一化**兜底（容忍前导缩进差异 + 行尾注释省略），仍唯一命中才应用；prompt 侧引导 LLM 给出"从行首开始的语句片段"（可省缩进/注释）；报告透明标注归一化应用。安全边界：语句本体必须逐字一致，歧义仍跳过，不做模糊/语义匹配。

**Status:** resolved（2026-08-12 实施完成：1216 绿 + mypy 干净 + node 过；真机验收闭环：2026C 注入带注释错误行第 1 轮 applied → 重编译 0 Error(s)，对比历史第 1 轮 skipped）

## 真机验收记录（2026-08-12，真实链路）

**链路**：复制 2026C stm32 产物（out_2026C_stm32，uvprojx 在 user/）→ main.c 注入带行尾注释错误行 `    int zzz_fix_probe = UNDECLARED_SYMBOL_ZZZ;   /* 验收注入：制造编译错误 */`（157 行，历史 158 行同款形态）→ 真实 UV4 -j0 -r -b 编译采错（`..\main.c(157): error #20: identifier "UNDECLARED_SYMBOL_ZZZ" is undefined`，`..\` 形态归一生效，candidates=main.c）→ 真实 DeepSeek 修复第 1 轮 → **applied**（backup_id 20260812-165715）→ 重编译 **0 Error(s) 1 Warning(s)**（1 警历史固有非回归）。

**环境**：Keil µVision5（IDE；命令行构建工具为随 IDE 安装的 `UV4.exe`，历史命名延续 µVision4，非 µVision4 本体）+ ARM Compiler V5.06 update 7 (build 960)（AC5）——报错为 AC5 的 `path(line): error #xx:` 形态（`..\main.c(157): error #20: ...`），与 parse_compile_errors 的 UV4 正则兼容；若换 AC6/armclang 则为 `path:line:col:` 形态（CCS 正则，同样已支持）。

**第 1 轮收敛对比**：compile-error-fix/01 历史同形态注入，旧 prompt + 纯精确匹配第 1 轮 skipped（白跑 ~60s 真实调用，第 3 轮才 applied）；本次新 prompt 引导（old_snippet 给从行首开始的语句本体）下 LLM 输出可直接命中，第 1 轮即收敛——prompt 降变形率与匹配兜底双端生效。修复语义：LLM 删错误声明保留注释行（`new_snippet` = 注释），合法。

**归一化分支真机验证**（同一真实 main.c 上，无 LLM 成本）：多行块形态（错误行 + 锚点注释行，snippet 省略缩进/行尾注释）→ applied，reason=「按行首前缀归一化匹配应用」（报告透明）；语句本体差异（`;` 前多空格）→ skipped 如实报告。还原收敛态后终验 0 Error(s)。真机脚本 `.scratch/fix-snippet-match/real_fix.py`（复刻 webapp 装配，可复跑）。

**真机观察**：单行 body-only snippet 是文件行 raw 子串 → 精确路径天然命中；归一化兜底在真机上主要兜多行块省略缩进/注释形态（prompt 主动引导该形态）与含 \r 内容——与设计预期一致，不做冗余。

## 问题审视（2026-08-12，真机 + 代码双证据）

- **现象**：compile-error-fix/01 真机第 1 轮 158 行未应用（文件行 = `    int zzz_fix_probe = UNDECLARED_SYMBOL_ZZZ;   /* 验收注入：制造编译错误 */`，LLM 给出的 old_snippet 与该行不完全一致）→ 0 次匹配 → skipped → 白跑一轮真实 DeepSeek 调用（~60s）；第 3 轮 2 处 applied（80 行 TAGID_MASK 无注释后缀、精确匹配成功）——**变形多发生在带行尾注释/缩进的行**。
- **根因链**：`FIX_SYSTEM_PROMPT` 约束 2 要求"逐字一致（含缩进、注释、空格）"→ LLM 试图抄全行但必然轻微变形（缩进、行尾注释省略、空白差异）→ `apply_fixes` 用 `content.count(old_snippet)==1` 纯精确匹配 → count=0 跳过。**prompt 要求越严，LLM 越抄不齐**；匹配侧毫无容忍度，协议两端共同造成失败。
- **可安全容忍的差异**：① 前导缩进（LLM 常用 0/4 空格）；② 行尾注释省略（LLM 经常不抄 `/* ... */`）；③ 行尾空白/CRLF。**不可容忍**：语句本体任何字符差异、行内空白重组（`a=b` vs `a = b`）、片段短到跨行歧义。

## 决策记录（grilling 2026-08-12，与用户确认）

1. **匹配策略：精确匹配优先 + 行首前缀归一化兜底**——`old_snippet.strip()` 与文件某行 `strip()` 后比较，要求 **old_snippet 是匹配行的行首前缀（strip 后）**（多行片段 = 逐行连续前缀块）；全文件唯一命中才应用，多处 → 仍跳过。前缀规则天然容忍缩进 + 行尾注释省略；替换语义 = 匹配行的原始全文被 new_snippet 替换（`new_snippet=""` = 删整行，注释随行删除，可接受）。不做子串/模糊/语义匹配（防误伤）。
2. **prompt 配套（降低变形率）**：约束 2 改为引导"old_snippet 给从行首开始的语句本体片段，可省略前导缩进与行尾注释，但语句本体必须与文件逐字一致；需要删整行时给该语句本体即可"——与前缀规则对齐（LLM 给"短前缀"命中率最高）；保留"唯一匹配"要求。
3. **报告透明**：归一化应用的 FixResult reason 标注「按行首前缀归一化匹配应用」；跳过仍如实报告。前端第 10 栏逐条结果照常展示（reason 已展示）。
4. **不动**：循环机制（≤3 轮）、file 限清单严格解析、backup/rollback 语义、路径基准（compile-error-fix/01 已通）。
5. **范围外**：行号锚定匹配（line 字段目前仅提示用，LLM 行号可信度未经实证，不做）；LLM 输出诊断日志（若归一化后仍频繁失败再上）。

## 实施

1. **fix_errors.py**：`apply_fixes` 匹配分支扩展——精确 `count==1` 优先；`count==0` 时走 `_match_normalized(content, fix.old_snippet)`（按行 split，逐行 `strip()` 后行首前缀比较，单行片段匹配"是某行 strip 后前缀"、多行片段匹配"连续行块逐行前缀"，收集唯一命中）；`count==0` 且归一化也未唯一命中 → skipped（原文案）；归一化命中 → applied（reason 标注归一化）。歧义（归一化多处命中）→ skipped。
2. **llm.py**：`FIX_SYSTEM_PROMPT` 约束 2 改引导（见决策 2），约束 3 保持（new_snippet 空 = 删除）。**注意双端契约测试**（若有 prompt 断言测试同步改）。
3. **测试（红证先行）**：构造差异形态用例——丢缩进、丢行尾注释、行尾 CRLF、行内多空格，各形态当前实现全 skipped（红）→ 改进后 unique 命中 applied；歧义形态（前缀命 2 行）仍 skipped；语句本体不一致（`a = b` vs `a=b`）仍 skipped；多行片段连续块命中。真机复验：2026C 注入带注释错误行 → 一条龙循环第 1 轮即收敛（对比现状第 1 轮失败）。
4. **不动**：webapp / index.html / compile_runner / 循环状态机 / backup。

## 验收标准

- [x] pytest 全绿 + `mypy src` 干净 + node 语法过（2026-08-12：1216 通过（基线 1208 + 8 新用例），mypy Success 35 files，node --check 内联 JS 通过；前端本次零改动）
- [x] 归一化匹配单测：缩进（改造既有 indent 用例红转绿）/ 行尾注释 / CRLF / 行内多空格四形态红转绿（红证：实施前 7 failed）；归一化歧义（raw 0 次但 strip 前缀命中 2 行）跳过；语句本体不一致（`int x  = 1;` vs `int x = 1;`）仍跳过；多行块命中（连续行块逐行前缀）；new_snippet 空 = 删整行（含行尾换行）
- [x] 精确匹配路径零回归（既有单测全过，reason="" 语义未动）
- [x] 真机：2026C 注入"带行尾注释的错误行"→ 一条龙循环第 1 轮修复 applied（对比 compile-error-fix/01 历史第 1 轮 skipped）→ 重编译 0 Error(s)
- [x] 报告透明：归一化应用 reason 标注「按行首前缀归一化匹配应用」（单测断言 + 真机 main.c 上实测 reason 可见）

## 实施记录（2026-08-12）

- **fix_errors.py**：`apply_fixes` 精确 count==1 优先不变；count==0 时走 `_normalized_hits`（`_snippet_normalized_lines` 整体 strip + 逐行 strip + 去空行后，逐行必须是文件对应行 strip 后内容的行首前缀；多行片段 = 连续行块逐行前缀），唯一命中 → applied（reason=「按行首前缀归一化匹配应用」），0 次 → skipped（原文案），多处 → skipped（歧义文案区分归一化命中数）；`_line_span`（含行尾换行的字符区间）+ `_preserve_line_ending`（裸语句无行尾时补回原行尾，new_snippet="" 删整行不补）；模块 docstring / FixSuggestion 注释同步
- **llm.py**：`FIX_SYSTEM_PROMPT` 约束 2 改引导「old_snippet 给从行首开始的语句本体片段，可省略前导缩进与行尾注释，语句本体必须与文件逐字一致（含空格）——工具先精确匹配、失败时按行首前缀归一化匹配后替换；需要删除整行时给该语句本体即可」；模块注释同步；`test_fix_system_prompt_contract`（逐字一致 / 唯一匹配 / 文件清单）断言不破
- **test_fix_errors.py**：红证先行（实施前 7 failed 全红）→ 8 用例绿：丢缩进（既有 indent 用例改造红转绿）/ 丢行尾注释 / CRLF（契约回归：真 CRLF 文件经通读归一化精确命中 + `_normalized_hits` 匹配器层 \r\n 容忍）/ 行内多空格 / 归一化歧义跳过 / 语句本体差异跳过 / 多行块命中 / new_snippet="" 删整行
- **真机**：见上文真机验收记录（real_fix.py 复刻 webapp 装配，真实 DeepSeek 单轮）
- **不动**：webapp / index.html / compile_runner / sse / 生成器 / 库数据 / 循环状态机 / backup / rollback

## 文件边界

- **改**：`src/contest_generator/fix_errors.py`（匹配逻辑）、`src/contest_generator/llm.py`（prompt 约束 2）、`tests/test_fix_errors.py`（+ 红证用例）、`.scratch/fix-snippet-match/issues/01-snippet-normalization.md`（本工单）、`.scratch/fix-snippet-match/real_fix.py`（真机复跑脚本）
- **不动**：webapp / index.html / compile_runner / sse / 生成器 / 库数据 / test_llm.py
