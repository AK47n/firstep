工单 pin-unlock-stm32/04：stm32 母版 startup 弱 handler 默认体 `B .`（原地死循环）→ `BX LR`（安全返回）。

**雷**：生成工程无 isr.c、ml_nvic 无条件使能 RXNE——任何模块 `uart_init(...,0x01)` 开中断后收到第一个字节即进弱 handler 死循环（编译全绿、运行即挂，硬编码扫描实证）。

**修复**（单文件边界，零 src 改动）：
- `library/masters/stm32/key/startup_stm32f10x_md.s`：10 处弱 handler 默认体 `B .` → `BX LR`（9 个异常 handler 各自一块 + Default_Handler 43 外设别名共享一块）；Dummy 注释同步改为「return immediately; strong handler overrides」
- 向量表 58 DCD / 53 `[WEAK]` 导出 / Reset_Handler / 其余汇编逐字节不动（diff 仅 10 行指令 + 1 行注释）

**测试**（`tests/test_pin_unlock_startup.py` +4，红证先行）：
- 全文零 `B .`（修复前 10 处命中 → 红，修复后绿）
- 10 个弱 dummy PROC 块各含 `BX LR`；BX LR 总数 11 = 10 默认体 + `__user_initial_stackheap` 既有 1 处
- 结构钉：`[WEAK]` 53 / DCD 58 不变（handler 不丢、向量表不动）
- generate() 产物 copytree 逐字节同母版 + 同断言

**真机**：2026C `--reuse-recommend --clarify`（20 条指纹匹配零警告）`--add motor`（8 模块）→ 产物门禁全过、UV4 `-j0 -r -b` 全量重建 **0 错 0 警** exit 0；产物 startup 逐字节 == 母版、B . = 0、BX LR = 11。

全量 pytest **1468 绿** + mypy src 41 文件干净。

范围外留痕：RX 数据无人消费（ISR 名联动 = 全解候选 ②）不做——弱 handler 现在安全返回，死循环雷拆除，中断不触发即无副作用。
