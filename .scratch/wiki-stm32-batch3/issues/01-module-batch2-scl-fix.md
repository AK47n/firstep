# 01 — 批次 2 回修：六件软 I2C 的 SCL 未初始化为输出（前置缺陷修复）

**要做什么：** 修复批次 2 六件（aht10/bh1750/sht20/sht30/at24c02/ags10）stm32 实现的**真 bug**：SCL 引脚从未 `gpio_init` 为输出——F1 复位后 GPIO 为浮空输入，`gpio_set(SCL,...)` 写 ODR 无效 → 总线 SCL 无法驱动（编译绿、未上板未暴露，真机必死）。修复 = 各件 `init()` 开头补 `gpio_init(<SLUG>_SCL_GPIO, <SLUG>_SCL_PIN, OUT_OD); <SLUG>_SCL(1);`（开漏输出 + 空闲置高），六件矩阵复跑 0/0，六件测试追加 **SCL OUT_OD 初始化守卫**（防回潮），notes 追加修正记录。

**关键事实：**
- 缺陷示例：`library/modules/aht10/code/aht10_stm32.c` L124-138 `aht10_init` 无 SCL gpio_init（只有 SDA_OUT 在 iic_start 里重配）；全树 grep `OUT_OD` 仅 SDA 命中——六件同构（同一模板生成）。
- 修复样式（本批 I2C 件同类）：`gpio_init(<SLUG>_SCL_GPIO, <SLUG>_SCL_PIN, OUT_OD);` + `<SLUG>_SCL(1);`——放在 init 首段（上电延时前或后均可，须在首条总线操作前）；SDA 保持现状（OUT_OD/IU 运行时切换正确，不动）。
- 修复后行为：SCL 开漏输出（与总线协议一致，外上拉并存），空闲高电平；与 mspm0 侧/页面原式（OUT_OD）一致。

**被谁阻塞：** 无——可立即开始（独立于本批六件新条目）。

**状态：** resolved

**实施清单：**
- [x] 逐件核对六文件（aht10/bh1750/sht20/sht30/at24c02/ags10 的 `*_stm32.c`）：确认 init 缺 SCL 初始化 → 补上（样式如上）；若某件已有则跳过并记录
- [x] 六件 `manifest.json` notes 追加「SCL 初始化缺陷回修（批次 3/01）：补 gpio_init SCL OUT_OD + 置高」；verified 保持 true
- [x] 六件测试 `tests/test_module_<slug>.py` 追加守卫：断言文件文本含 `gpio_init(<SLUG>_SCL_GPIO, <SLUG>_SCL_PIN, OUT_OD)`（或宏形式，实现为准）
- [x] UV4 矩阵复跑（六件，照 run_<slug>_matrix.py 配方）→ 0 error/0 module warning
- [x] pytest 相关测试绿；中文提交 → resolved → 结论回填

**验收标准：** 六件修复 + 守卫 + 矩阵 0/0 + 提交中文；真机验证留笔记（未上板项目）。

## 结论（2026 批次 3/01 实施回填）

- **核对结果**：六件并不全是「从未初始化」——实际核查：
  - `aht10`：**缺陷实锤**（init L124-138 无任何 SCL gpio_init，全树 OUT_OD 仅 SDA 命中）→ 已补 `gpio_init(AHT10_SCL_GPIO, AHT10_SCL_PIN, OUT_OD)` + `AHT10_SCL(1)`（init 首段、50ms 稳定前）。
  - `sht30`：SCL 已有 gpio_init 但为**页面原式推挽 OUT_PP 且无置高**（批次 2 全批唯一一派，工作前提=模块上拉）→ 按批次 3 回修口径统一为 `OUT_OD` + 置高（`gpio_set(SHT30_SCL_GPIO, SHT30_SCL_PIN, 1)`）；SDA 保持页面原式 PP/IF 不动，notes 记录差异。
  - `bh1750`/`sht20`/`at24c02`/`ags10`：批次 2 已含 `gpio_init(..., SCL..., OUT_OD)` + 置高 → **核验通过，零代码改动**（notes 记录「已合规」）。
- **测试守卫**：六件 `tests/test_module_<slug>.py` 各追加 `test_<slug>_stm32_scl_init_guard`（断言剥离注释后文本含 `gpio_init(<SLUG>_SCL_GPIO, <SLUG>_SCL_PIN, OUT_OD)` + `<SLUG>_SCL(1)`）——pytest 42 passed。
- **矩阵复跑**：六件 `<slug>` 单选生成 → UV4（C:/Keil5 V5.06u7）全部 `0 Error(s), 0 Warning(s)`、`compile_passed: True`、exit 0（产物 .scratch/wiki-stm32-batch3/matrix/<slug>/）。
- **notes**：六件 manifest stm32.notes 追加「批次 3/01 回修」记录（aht10 补初始化说明 / sht30 PP→OD 差异记录 / 其余四件核验通过）；verified 保持 true。
- **未上板**：真机验证留后续（本批收尾统一安排）。
