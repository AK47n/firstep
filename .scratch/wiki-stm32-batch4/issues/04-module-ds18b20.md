# 04 — ds18b20 温度传感器（单总线位时序，手册 sensor--ds18b20-temp-sensor.md）

**要做什么：** 模块库 `ds18b20` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼单总线温度驱动为纯驱动切片（单 GPIO 双向：发送=OUT_PP、读位=IU+gpio_get；忙等 delay_us），API 与 mspm0 版完全对齐：`ds18b20_init()`（单脚配置 + 总线释放（读毕释放为输入））+ `ds18b20_read_temp()`→float（12bit 0.0625℃/LSB、负温补码；失败语义照 mspm0 .h 注释——失败返回约定值并保持上次缓存语义照 mspm0 实现）。

**关键事实（已取证，%TEMP%\batch4-facts.md）：** F1；页面默认 DQ=PB0（不照抄——本件默认 **PB1**，叠 MOTOR_B_DIR2：测温与单电机方向不同框；刻意不叠声光/传感站/总线环境件——测温+声光/环境站为常见组合）。命令：0xCC（跳过 ROM）/0x44（温度转换）/0xBE（读暂存区）；12bit 精度；负温补码（int16 直乘 0.0625）；位槽 2+12+50=64us 落 60-70us；复位 750us 低+释放 15us；转换等待 750ms。

**页面缺陷（修正+notes+守卫）：** ① **0x44 后无转换等待 L265-266（主缺陷）**——首次读回上电默认 85℃；补 **750ms** 等待（mspm0 批 6 修正沿用）；② `.h` 声明 `DS18B20_Reset(void)` 无定义 L330——剔除（或实现），notes；③ L51-66 三标题与内容错位、L107「MLX90614」串台、L143 DQ_OUT 注释相反——不落/注释正确化（页面串台记录 notes）；④ 位槽常量单源 .h（照 mspm0 批 6 口径：复位 750/释放 15/读槽 12/60 等）；⑤ 读毕释放总线（init 与 read 尾部 gpio_init IU——防总线占用）。

**引脚与默认脚：** pins `DS18B20_DATA`（type `gpio_out`，default **PB1**，macros `[DS18B20_GPIO, DS18B20_PIN]`）；pin_config.h 宏段：`#define DS18B20_GPIO GPIO_B` / `#define DS18B20_PIN Pin_1`（注释：默认 PB1 叠 MOTOR_B_DIR2——测温与单电机方向不同框；同选经绑定消解；PB1 现 1 角色二叠登记）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/ds18b20/code/ds18b20_stm32.c/.h`（独立 stm32 头；.c gpio_init/gpio_set/gpio_get + delay_us；方向切换宏；零引脚字面量/零标准库）
- [x] init：单脚配置 + 总线释放；read_temp：复位→0xCC→0x44→**750ms 等待**→复位→0xCC→0xBE→读 9 字节（按 mspm0 实现读取量——2 字节温度寄存器，页面原样）→int16 补码 ×0.0625f；读毕释放总线
- [x] 位槽常量 .h 单源（750/15/200/240/2+60/2+12+50/0.0625f/750 宏——照 mspm0 批 6 口径）
- [x] manifest.json platforms 增 stm32：files `[code/ds18b20_stm32.c, code/ds18b20_stm32.h]`、dependencies ["delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/ds18b20-temp-sensor.html`）、notes（手册路径+原页+网盘+缺陷 5 条+750ms 补等待+位槽常量+串台记录+默认脚推理+未上板）
- [x] pin_config.h 增 2 宏
- [x] 测试 `tests/test_module_ds18b20.py`：形状+宏存在+单选生成全流程+mspm0 零改动守卫+守卫（`750`ms 等待、`0xCC`/`0x44`/`0xBE`、`0.0625f`、位槽常量、无 `MLX90614`（源码）——页面串台仅 notes 记录、无 printf/GPIO_Init/RCC_、总线释放（read 尾部 `DATA_SET(1)`）+ **stm32 位槽时间轴守卫**（mspm0 镜像：读槽 64us/写槽 62us 落 60-70us）
- [x] test_pins.py 补 2 宏；test_default_layout.py 白名单 PB1 +1（二叠：MOTOR_B_DIR2）
- [x] UV4 矩阵（init+read_temp，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核（ds18b20 已在 wordlist lib_modules——mspm0 条目同 slug 已挂接）；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = 单总线位时序件（DATA_OUT = gpio_init OUT_PP、DATA_IN = gpio_init IU + gpio_get；忙等 delay_us 不占 TIMER；页面原式 PP+IPU 上拉）；默认 PB1（叠 motor MOTOR_B_DIR2——测温与单电机方向不同框；页面默认 PB0=MOTOR_B_DIR 不照抄）；**0x44 后补 DS18B20_CONVERT_MS 750ms 转换等待**（主缺陷修正——首次读回 85℃ 默认值，mspm0 批 6 沿用）+ 测试钉死；位槽时间轴常量单源 ds18b20_stm32.h（750/15/200/240/2+60/60+2/2+12+50/0.0625f/750——读槽 64us/写槽 62us 落 60-70us，测试按常量计算守卫）；页外未实现复位函数声明剔除（源码头零字面量，仅 manifest notes 精确记录）；页面注释串台（MLX90614/标题错位/DQ_OUT 注释相反/错别字）→ 不落/注释正确化（源码零串台 Token，BANNED 守卫）；读毕释放总线（init + read 尾部 DATA_OUT+SET(1)）；负温补码 `(~temp)+1`×−0.0625。UV4 矩阵 0 error/0 module warning（2026-09-06）→ verified=true；mspm0 条目零改动；提交 d36741b4（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
