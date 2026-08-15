# 04 — startup 弱 handler `B .` 死循环修复（现状雷，grilling 顺带立项）

**What to build:** 母版启动文件 `library/masters/stm32/key/startup_stm32f10x_md.s` 的弱中断 handler 默认体是 `B .`（原地死循环）。生成工程无 isr.c、ml_nvic 无条件使能 RXNE 中断（`ml_uart.c` CR1 恒置 + `ml_nvic.c` 无条件 ISER）——任何模块的 `uart_init(...,0x01)` 开中断后，收到第一个字节即进弱 handler 死循环（编译全绿、运行即挂，硬编码扫描实证）。修复 = 弱 handler 默认体改 `BX LR`（返回，不再卡死）。

**Blocked by:** 无（与 01 并行，文件不重叠）

**Status:** resolved（2026-08-15）

## 需求

1. **弱 handler 默认体**：`library/masters/stm32/key/startup_stm32f10x_md.s` 中所有弱中断 handler 的 `B .` 改 `BX LR`（约 30 处，UART1/2/3、EXTI、TIM 等全部——弱 handler 语义 = 未实现时安全返回）；强 handler（工程已定义的）与向量表不动。注意：这只是"不卡死"——RX 数据仍无人消费（全解候选 ② 的 ISR 名联动范围，本单不做）。
2. **测试**：红证先行——断言 startup 存在弱 handler `B .`（红）→ 修复后断言 `B .` 计数为 0（或仅非 handler 处）且 `BX LR` 计数 ≈ 弱 handler 数；生成产物回归（copytree 带过来的 startup 同断言）。
3. **真机**：2026C `--reuse-recommend --add motor`（全默认）→ UV4 0 错 0 警回归（汇编改动编译验证）；产物 startup 断言。

## 文件边界

- `library/masters/stm32/key/startup_stm32f10x_md.s`：唯一文件（零 src/ 改动）
- 测试文件自定（建议 tests/test_pin_unlock_startup.py 新文件）
- 铁律：独立 worktree（从最新 main 建）

## 验收

- [x] pytest 全绿 + mypy src 干净
- [x] 红证已验（弱 handler `B .` 断言红 → 绿 + BX LR 计数）
- [x] 真机：2026C 全默认 UV4 0 错 0 警 + 产物 startup 断言
- [x] 独立 worktree + 提交 + 推送（PR）

## 验收记录（2026-08-15）

- 修复：`library/masters/stm32/key/startup_stm32f10x_md.s` 10 处弱 handler
  默认体 `B .` → `BX LR`（9 个异常 handler + Default_Handler 共享体；
  NMI/HardFault/…/SysTick 各自一块 + 43 外设别名共享一块 = 全弱 handler
  默认体清零），Dummy 注释同步改「return immediately; strong handler
  overrides」；向量表 58 DCD / 53 [WEAK] 导出 / Reset_Handler / 其余汇编
  逐字节不动（diff 仅 10 行指令 + 1 行注释）。
- 测试 `tests/test_pin_unlock_startup.py` +4：全文零 `B .`；10 个弱 dummy
  PROC 块各含 BX LR（BX LR 总数 11 = 10 默认体 + stackheap 既有 1 处）；
  [WEAK] 53 / DCD 58 结构钉；generate() 产物 copytree 逐字节同母版 + 同断言。
  红证：修复前 3 红（B . 10 处命中），修复后 4 绿；全量 1468 绿 + mypy
  src 41 文件干净。
- 真机：2026C `--reuse-recommend --clarify`（20 条指纹匹配零警告）
  `--add motor`（8 模块 = 缓存 7 + motor）→ 生成 49 文件、产物门禁全过、
  UV4 `-j0 -r -b` 全量重建 **0 错 0 警** exit 0；产物 startup 逐字节 ==
  母版、B . = 0、BX LR = 11（断言脚本
  .scratch/real-run/assert_product_startup_04.py，证据日志
  check_2026C_pin_unlock_04.log 留档主检出 real-run）。
- 真机机制注记：webapp 以内存 replace 的 AppConfig 启动（库目录指向本
  worktree，不写盘不碰用户 config.json，launcher
  .scratch/real-run/launch_webapp_pin_unlock_04.py 不提交）——分类器拦了
  两种写 config 的方案后采用此零写入路径，跑完即还原（无持久状态）。
- 范围外留痕：RX 数据无人消费（ISR 名联动 = 全解候选 ②）不做，弱 handler
  现在安全返回——死循环雷拆除，中断不触发即无副作用。

## 实施提示词（复制到新会话）

```
实施 startup 弱 handler 死循环修复工单 .scratch/pin-unlock-stm32/issues/04-startup-weak-handler.md：
1. 读工单 + spec 关键事实节 + 最新 main 的 library/masters/stm32/key/startup_stm32f10x_md.s
   （弱 handler 区域在 265-280 行附近）
2. 全部弱中断 handler 默认体 B . → BX LR（向量表/强 handler/其余汇编不动）
3. 红证先行（B . 计数断言红）→ 修复转绿（B . 清零 + BX LR 计数）；
   生成产物 copytree 回归断言
4. 真机：2026C --reuse-recommend --add motor（全默认）UV4 0 错 0 警 + 产物断言
5. 提交 + 推送开 PR
注意：独立 worktree（从最新 main 建）；单文件边界；只改仓库 library/masters/stm32/；
与 01/03 并行（文件不重叠）；RX 数据无人消费问题不在本单范围（全解候选 ②）
```
