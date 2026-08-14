# 01 — CLI 修复循环对偶补齐：发 previous_fixes + 超时停条件（不碰「前端驱动」定案）

**What to build:** CLI 修复循环（`.scratch/real-run/generate_check.py`）与 web 产品路径两个行为分化缺口补齐。「前端状态机驱动循环，本路由单次编译」（`webapp.py:796`）与「继续按钮 CLI 非交互无对偶」是既定设计，**本工单不推翻、不做后端循环**——只补两处对偶缺口：

1. **CLI 不发 previous_fixes**（`generate_check.py:451` 注释「本工单循环不依赖停滞回喂」是实施捷径，不是设计定案）：该字段是 fix-loop-progress/01 之后协议的一等元素（服务端已支持：`webapp.py:725/745/765` 可选透传，零改动），FIX_SYSTEM_PROMPT 约束 6 靠它抑制「重复输出与上一轮一模一样的建议」——CLI 循环第 2 轮起与 web 行为分化，验收路径 ≠ 产品路径。
2. **CLI 无超时停条件**：前端有（`index.html:1793-1796`），CLI 的 `uv4_build`/`gmake_build` 丢弃 `CompileRun.timed_out`（`generate_check.py:142-168, 171-195`），`run_fix_loop`（:534-565）超时后把半截输出当 error_text 喂下一轮——白烧一次 LLM 调用 + 误报轮上限文案。

**Status:** resolved

## 设计定案（已代决，实施会话不再重开）

1. **build_fix_payload 增可选参数 `previous_fixes`**（默认 None → 不进 payload，保持「缺省两必填键」语义）；`run_fix_loop` 每轮从上一轮 done 载荷取 `done["fixes"]` 作 previous_fixes 传下一轮（对齐前端 `index.html:1724` 的 `previousDone.fixes` 回喂）。服务端 webapp.py 零改动。
2. **timed_out 停条件**：`run_fix_loop` 在重编译结果上检查 `run.timed_out` → 即停，文案对齐前端超时停法（「编译超时」语义，不停进下一轮）；半截输出不再作 error_text。
3. **契约注释与对偶测试同步**：`generate_check.py:449-455` 注释改写（previous_fixes 不再是「不带」）；`tests/test_generate_check_contract.py` 的 `FIX_CONTRACT_FIELDS` 钉同步——新增「带 previous_fixes = 恰七字段」用例 + 既有「全输入恰六字段」「缺省两键」用例语义不动（该钉的强制点是键集合一致，注释同步改）；文件头注释同步（:49 附近「六字段清单」）。

## 实施边界

- 只动 `.scratch/real-run/generate_check.py` + `tests/test_generate_check_contract.py`。
- **零改动**：src/ 全部（webapp / fix_errors / llm / generator / index.html——并行工单在改 llm.py / generator.py，一个都不碰）。

## 验收标准

- [ ] 红证先行：先写「带 previous_fixes = 恰七字段」契约用例 → 现行 build_fix_payload 无此参数必红（TypeError/断言失败记录）→ 实施后绿
- [ ] 超时停条件测试：合成 timed_out 的 CompileRun → 循环即停 + 文案断言 + 不产生 LLM 调用
- [ ] 全量 pytest 绿（基线 1369）+ 契约钉全绿
- [ ] （推荐）真机 CLI 回归：`python .scratch/real-run/generate_check.py` 2026C `--reuse-recommend` 正常管线 UV4 0 错 0 警；（可选）注错单轮 probe 观察第 2 轮请求体带 previous_fixes
- [ ] `git status` 只出现预期文件

## 实施提示词（新会话粘贴）

> 工单：`.scratch/cli-fix-loop-parity/issues/01-previous-fixes-timeout.md`（先读全文，设计已定案勿重开）。
> 环境：`cd C:\Users\luoji\Desktop\firstep` → `git worktree add ../firstep-wt-cli-fix-loop -b cli-fix-loop-parity-01` → `cd ../firstep-wt-cli-fix-loop`（必须独立 worktree，主检出有并行工单）。
> 文件边界：只动 `.scratch/real-run/generate_check.py` + `tests/test_generate_check_contract.py`；src/ 全目录一个都不碰（并行工单在改 llm.py / generator.py）。
> 关键：「前端状态机驱动循环」是定案，本工单只补对偶缺口；previous_fixes 缺省 None 不进 payload（缺省两键语义不动）；超时停文案对齐前端。
> 验收：红证记录 → 实施绿 + 契约钉全绿 + 全量 pytest 绿 +（推荐）真机 CLI 回归；提交格式 `fix: ...（工单 cli-fix-loop-parity/01，N 绿——...）` + docs 一笔；`gh pr create --body-file`；不 force push；证据写本文件 Comments，Status → resolved，推送。

## Comments

### 2026-08-14 实施 + 验收闭环（cli-fix-loop-parity-01 分支 d7f0d0c）

**红证先行**（tests/test_generate_check_contract.py 先行落测，实施前跑红）：
- `test_build_fix_payload_with_previous_fixes_has_exactly_seven_fields` → TypeError: build_fix_payload() got an unexpected keyword argument 'previous_fixes'
- `test_build_fix_payload_omits_empty_optionals`（加传 previous_fixes=()）→ 同 TypeError
- `test_run_fix_loop_round2_payload_includes_previous_fixes` → ValueError: too many values to unpack (expected 3, got 4)（重编译解包三元组处）
- `test_run_fix_loop_rebuild_timeout_stops_without_next_llm_call` → 同 ValueError
- 红因恰是两缺口本身：现状无 previous_fixes 参数 + 编译函数丢 timed_out

**实施绿**：1372 绿（基线 1369 + 3 新用例 + 1 扩写），契约钉 45/45 绿；src 全目录零改动、webapp.py 零改动（服务端 previous_fixes 可选透传已有）。
- `build_fix_payload` 增可选 `previous_fixes`（缺省 None 不进 payload；缺省两必填键语义不动——缺省/空省用例绿证；非空才发与前端 previousDone.fixes 真值判定一致）
- `run_fix_loop`：每轮 done 后记 fixes，第 2 轮起作 previous_fixes 回喂（单元断言：轮 1 请求体无该键、轮 2 请求体 == 轮 1 done.fixes 全等）；重编译 `timed_out` → 「第 N 轮重编译超时，已停止循环——可修改工程后重新运行本脚本」即停（核心文案「重编译超时，已停止循环」对齐前端 index.html:1793-1796），半截输出不进 error_text，fix_stream 恰 1 次调用（旧形态白烧第 2 轮 LLM）
- `uv4_build`/`gmake_build` 返回四元组 (passed, 摘要, 原文, timed_out)，CompileRun.timed_out 不再丢弃；check_topic 首编解包 `_timed_out` 沿用旧路径（compile_passed(None)=False → 进修复循环——首编超时停不在本工单范围，见遗留）

**真机 CLI 回归**（worktree 起服务 8000，HEAD 基线；GENERATE_CHECK_CACHE_DIR 指主检出 cache 复用 recommend_2026C.json）：
- `python .scratch/real-run/generate_check.py --reuse-recommend --clarify clarify_2026C.json 2026C` ✓ 通过——缓存复用 7 模块 0 补问；骨架 7139 字符 拦截 0 处；生成 49 文件；[产物] 门禁全过；**[真机] UV4 exit=0 Build Time 00:00:02（0 错误 0 警）**；汇总 2026C: ✓ 通过，exit 0
- 首跑曾 502（/api/skeleton DeepSeek「Remote end closed connection without response」——服务端瞬态网络失败，发生于骨架段、生成/编译未到，非本工单改动；同命令重跑即过，佐证瞬态）
- 可选「注错单轮 probe 第 2 轮请求体带 previous_fixes」未做真机（分钟级 LLM 烧卡）：由契约单元测试 test_run_fix_loop_round2_payload_includes_previous_fixes 行为级覆盖（轮 2 payload previous_fixes == 轮 1 done.fixes 全等，与真机 probe 同断言面）

**遗留**：首编（check_topic 初编译）超时仍沿用旧路径进修复循环（半截输出喂第 1 轮 LLM）——本工单超时停条件按设计只落在循环内重编译；如需处理可另立工单。
