# 03 — mq2 烟雾检测传感器（ADC 模拟量薄封装，手册 sensor--mq-2-sensor.md）

**要做什么：** 模块库新增 `mq2` 条目（仅 mspm0）：从手册提炼 MQ-2 驱动为纯驱动切片——**ADC 薄封装**（依赖库内 adc 模块共读板载 ADC12_0 MEM0，照 us016 先例，不新开 ADC 通道）：`mq2_init()` + `mq2_read_percent()`（出 0-100% 浓度百分比）；notes 写明 MQ 系读数是相对值非 ppm 精标；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 01/02/04 独立）。

**状态：** claimed

**验收：**

- [ ] 代码提炼：`code/mq2.c/h`（去 main/printf；函数名规范化 `mq2_init/read_percent`；页面 ADC 中断（`ADC12_0_INST_IRQHandler` + `gCheckADC`）改依赖 adc 模块轮询读（共享实例 IRQHandler 强符号唯一）；`Get_Adc_Value` 30 次平均改 5 次快速平均（us016 先例）；页面 `Adc_Init`/`Get_MQ2_Percentage_value` 归一）
- [ ] 配方：`mq2_init` = adc_init(ADC_1, ADC_Channel_0)；`mq2_read_percent` = adc_get(ADC_1, ADC_Channel_0) 5 次均值 → `(float)value/4095.0f*100.0f`（页面 4095/100 原式；AO 电压线性对应百分比区间，模块可调电阻控阈值）；页面 `GET_DO` 宏未用 → 不声明 DO 角色（notes 说明）
- [ ] 母版 `mspm0.syscfg`：**无新实例**——仅 ADC12_0 段注释补 mq2 薄封装共读 MEM0（默认 PA24/A0_3，与 adc/us016 同槽）；默认 PA24 与批次 5 tcs34725 SDA 重叠系 MEM0 槽位唯一所致（同选经引脚绑定消解），重叠说明登记 test_pin_bindings
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS：`"ADC12_0": (..., "mq2")`
- [ ] `manifest.json`：dependencies ["adc"]；pins `MQ2_AO_CH0` = adc PA24；notes 含手册路径+原页+网盘链接+改造要点+MQ 系相对值非 ppm+预热要求+DO 未声明+编译记录；verified=true
- [ ] wordlist.json「感知传感器」类补录 MQ-2 方案（lib_modules 挂接）+ models 词条
- [ ] 测试：test_pins 无需增 MSPM0_DEFAULT_MAP（adc 角色无 GPIO 组/外设落点，us016 先例）；test_pin_bindings PA24 注释补 mq2；test_syscfg_prune ADC12_0 消费方 mq2 断言；新增 test_module_mq2.py（薄封装 = 依赖 adc 无新实例 + 百分比公式 4095/100 守卫 + 无 IRQHandler 守卫）
- [ ] 编译验证：run_mq2_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录
- [ ] 中文提交 + 工单 resolved + code-review
