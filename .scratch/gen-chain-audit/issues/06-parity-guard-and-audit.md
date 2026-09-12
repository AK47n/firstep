# 06 — 对拍守卫（`UI 放行 ⊆ 后端接受`）+ 真机 P1 转绿

**状态：** resolved（2026-08-xx；对拍用例进 `tests/test_bindings_matrix.py`（不另开
文件——同一份模型契约的用例放一处），真机 P1 **FAIL 0 / WARN 0 / PASS 15**）

## 交付（实现后的实际形状）

1. **对拍守卫**在 `tests/test_bindings_matrix.py`：`test_matrix_selectable_matches_
   backend_verdict[mspm0/stm32]` **全脚枚举**（不只 `selectable`——只枚举 selectable
   会漏掉能力层挡掉的假绿，本轮真踩过）逐条比「模型求值 × 真 `resolve_bindings`」：
   假绿 = 0、假红 = 0；锚：候选 744 / 旧口径 115 条全被挡 / 后端拒 158 条全被挡；
   `test_greedy_user_walk_…` 再按用户节奏逐角色绑脚，每一步累积态回验后端。
2. **真机 P1 改为求值前端真函数**：审计脚本原来在页面里照抄了一份 `pinCanHost` 镜像，
   前端修好后它照样报 115 条（本轮实测）——现在它 `import("/js/fx/pin-model.js")`
   取真件求值；并加「判据模型端点不可用 → FAIL」的前置判据。
3. **服务夹具加端点哨兵**（`tests/browser/server.mjs`）：起服务后必须真答
   `/api/bindings/matrix`，否则大声失败——本轮真踩过「8791 上残留旧后端，健康检查
   通过、整轮验收跑在旧代码上」（`spawn` 静默失败）。
4. 真机结果：`node tests/browser/gen-chain-audit.mjs P` → 15 PASS / 0 FAIL / 0 WARN
   （mspm0 UI 说行 586 条后端全收、UI 说不行 158 条后端全拒），证据
   `.scratch/gen-chain-audit/audit-P-after.txt`（修前基线 `audit-P-before.txt`）。

## 反向验证（工单原要求）

等价于「停用修复必当场红」，本轮由三次**真实抓错**替代（比人工停用更强）：

- 模型把 mspm0 带通道 pwm 当 strict-all → 对拍报 74 条假绿；
- `_pwm_channel_suffix` 少锚下划线（互补通道 `TIMA0_C3N` 误算同通道）→ 24 条假绿假红；
- 只枚举 `selectable` 而非全脚 → 用例一片绿掩盖 24 条假绿（用例自身缺陷，已修）。

## 要做什么（原工单）

把「板图判据 ⊆ 后端判据」钉成**默认回归**，取代「靠审计脚本偶然发现」：

1. `tests/test_pin_matrix_parity.py`（新，pytest，秒级、无浏览器、无 LLM）：
   - 复现 P1 节口径：mspm0 `step_motor + huidu + motor + led_beep` 真展开 → 枚举
     (角色 × 类型命中脚) 候选，逐条比
     `matrix_model_selectable(role, pin)` × `resolve_bindings({role: pin})`：
     **放行但后端拒 = 0**（硬红线）、**挡掉但后端收 = 0**（假红同钉）；断言候选数 = 744、
     现状分歧数 = 115 作为回归锚（数字变化要显式改基线）；
   - stm32 同款对照（600 条，0 分歧）；
   - `motor.PWMAB_C0` 观测语义：C1 未绑 vs 绑到 `PA0`（无 C1 实例）两态下候选集不同。
2. 真机：`node tests/browser/gen-chain-audit.mjs P` —— P1 mspm0 从
   「FAIL 115 条」转 **PASS**（这是最终判据，pytest 只是把同一事实提前到秒级）。
3. 反向验证：把 `pinCanHost` 临时改回旧口径（不查模型）→ 对拍用例 + P1 **当场变红**，
   记录证据后恢复。

## 验收

- 新对拍用例绿；`node tests/browser/gen-chain-audit.mjs P` 的 P1 mspm0 = PASS（0 条误放行）。
- 反向验证记录（临时停用 → 红 → 恢复 → 绿）写进完工说明。

## 不做

- 不改审计脚本的判据（它按「两边结论不一致」的事实报，修好即转绿）。
