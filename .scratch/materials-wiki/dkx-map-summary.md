# 地阔星（dkx-stm32f103c8t6）wiki 模块页 ↔ 库内模块 slug 映射表 · 总结

- 主表 `dkx-map.tsv`（77 行，表头 `page_file | cat | wiki_slug | wiki_title | lib_slug | stm32_entry | stm32_files | action | f4_suspect | code_blocks | 备注`）与 D 类附表 `dkx-d-appendix.tsv`（24 个库侧模块，无地阔星页面对应；含 stm32 条目/文件/库侧描述截取）：**映射轮次的工作产物，未随仓库保存**（`dkx-pages.json` 同理）——本文件的统计与关键判定即该轮次快照的留档。
- 重生成：`python .scratch/materials-wiki/dkx_extract.py` → `python .scratch/materials-wiki/dkx_build_map.py`。注意 `action` 按**当前** manifest 现算（该 slug 无 stm32 条目 = A、有 = C），故重生成不会复现映射轮次的 A61/B9/C7 快照——要历史分类以本文件为准。
- 判定与备注全文在表内；本文件为统计与关键判定说明。

## 全景统计

| 项 | 件数 |
|---|---|
| 页面总数 | 77（目录 79 个 md = 77 页 + 模块索引/网盘索引） |
| A 新增 stm32 条目（库有 mspm0/母版、无 stm32 条目、页面有驱动） | **61** |
| B 新模块（库内无任何对应，需建新 slug） | **9** |
| C 已有 stm32-核对（库已有 stm32 条目/母版内嵌） | **7** |
| F4 嫌疑页（页面代码含 `RCC_AHB1PeriphClockCmd`/`GPIO_OType`） | **6** |
| D 无页面对应（库模块无地阔星页面，附表） | **24** |

校验：77 行与页面文件一一对齐；每行 stm32_entry/files/action 与 manifest 实况复核一致；f4 标志与全量 grep 复核一致（Y×6 均命中、其余均无命中）。

## B 类（9 个，库内无任何对应 → 新 slug 建议）

| wiki_slug | 建议新 slug | 独立/重叠判断（理由见备注列） |
|---|---|---|
| ec01g-nbiot-gps-module | ec01g | 独立：NB-IoT+GPS AT 模块，无线族 as32/nrf24l01/hc05/zigbee_* 均不同器件协议 |
| esp01s-wifi-module | esp01s | 独立：库无 WiFi 模块；与 LoRa/2.4G/蓝牙无重叠 |
| neo-6m-gps-module | neo_6m | 独立：库无 GPS；与 imu_uart/open_mv4 仅「UART 帧解析」结构相似、器件协议不同 |
| vl53l0x-laser-distance-sensor | vl53l0x | 独立：库无 ToF；与 ir_distance（红外反射模拟量）原理不同（飞行时间 I2C vs ADC） |
| ec11 | ec11 | 独立：库无旋转编码器模块；ntb_time 为系统毫秒时间戳（无重叠）；key 为独立按键；motor 编码器读数为电机测速闭环属另一域 |
| 4x4-keyboard | key_matrix | 独立：库 key = N 路独立按键 GPIO 读取，本页 = 4 行输出+4 列输入行列扫描 16 键，扫描机制不同（仅同属「按键输入」大类，非重叠） |
| 2-8-and-3-2-color-sreen | ili9341 | 独立（半重叠）：ILI9341 不在 lcd 六合一（ST7735/GC9A01/ST7789V2/V3/ST7735S）；页面触摸 XPT2046 与 tp_xpt2046 同芯可复用 |
| 3-5-ili9488-color-screen | ili9488 | 独立（半重叠）：同上，ILI9488 不在 lcd 变体组；触摸同芯可复用 |
| 1-14-color-screen | st7789_para | 独立：控制器 ST7789V 与 lcd 的 V2/V3 同族，但接口为 8 位并口（lcd 全系软 SPI），驱动结构不同；若 lcd 未来支持并口可并入变体 |

## C 类（7 个，库已有 stm32 条目/母版内嵌 → 仅核对）

- sg90-steering-engine → servo（标题/器件匹配；stm32 files: code/servo.h,code/servo_stm32.c）
- tb6612-motor-drive-module → motor（TB6612 双路驱动逐字对应）
- mpu6050-six-axis-sensor → ml_mpu6050（库 mspm0+stm32 双平台；source_url 为采购链接故非 ①）
- 0-91-color-screen → oled（页面实为 0.91 寸 SSD1306 128×32 单色 OLED，库 oled 已支持 oled_set_res(OLED_RES_128X32) → 归 oled 而非 lcd — 与初始提示不同，以页面规格为准）
- 0-96-iic-single-screen → oled（SSD1306 I2C 默认形态，库 notes「同家族仅核对不提炼」）
- 0-96-single-spi-screen → oled（SSD1306 SPI，库 SPI 变体批次 12/07 决策 B 已并入）
- 1-3-single-oled-screen → oled（1.3 寸 SH1106 128×64 单色 OLED = oled 显示家族，notes 明示 ZJY130S0700WG01 同家族；SH1106 与 SSD1306 初始化序列略异 → 并入 oled 变体）

## F4 嫌疑页（6 个，页面代码含 F4 风格调用，与 F103 标题矛盾，需甄别）

- control--relay-module.md（命中 ×3）
- control--sg90-steering-engine.md（命中 ×1）
- screen--0-96-color-screen.md（命中 ×3）
- screen--0-96-single-spi-screen.md（命中 ×3）
- screen--1-47-color-screen.md（命中 ×3）
- sensor--mq-3-sensor.md（命中 ×2）

## D 类附表（24 个库模块无地阔星页面对应；列值以 manifest 实况为准）

- stm32=Y（20 个）：adc（母版内嵌）、beep、config、coord_detect、debug_uart、delay（母版内嵌）、digit_uart、filter、ir_beam、k230（母版内嵌）、key、led（母版内嵌）、led_beep、ntb_time、pid（含 gray_track）、uart、uwb_uart、zigbee_link、zigbee_uart、zigbee_uart_key
- stm32=N（4 个）：imu_uart（mspm0 纯驱动，无 wiki 来源）、step_motor（mspm0 母版引脚，无 wiki 来源）、jy61p（dmx 页 jy61p-measurement-sensor 存在但地阔星无对应）、open_mv4（dmx 页 open-mv4-camera 存在但地阔星无对应）

注：任务举例的 jy61p/open_mv4 已列入附表，但二者当前 manifest 实为 stm32=N（仅 mspm0 条目），非「stm32 条目存在」——附表已在 stm32_entry 列如实记录。

## 关键判定说明

1. **大小写敏感**：`Infrared-distance-sensor`/`Infrared-decoding-coding-module` 与库 source_url 逐字符一致 → ① 精确匹配（ir_distance、ir_remote_tx）。页面 slug 与库 slug 的短版对换仅发生在 dht11（页=dht11=库 slug）。
2. **灰/循迹二页分流**：`Infrared-tracking-sensor`（TCRT5000，DO=1 黑线）→ huidu（库描述「黑线检测（1=黑线）」逐字对应）；`grayscale-sensor`（单路模拟灰度读值）→ xunji（库「8 路灰度读取（位图）+ 巡线核心」）。两库模块互为邻域（huidu=读值、xunji=读值+巡线核心），页面均为单通道示例，此分流为二选一判定，已在备注写明。
3. **1-8-touch-color-screen**：① 归 tp_xpt2046（其 source_url 即本页）；页面同时含 1.8 寸 ST7735S 屏驱动（lcd 1.8 变体），屏/触两件零耦合，备注已记述。
4. **max7219 双页**：8-bit-led-tube（① source_url）与 max7219-matrix-display（② 同芯片双形态：库描述明示 BCD 数码管 + 4合1 点阵 write_matrix 级联）→ 同库 slug。
5. **无 wiki 来源的库模块**（delay/led/adc/k230 等母版内嵌件）与 imu_uart/step_motor 等无地阔星页面对应者，全部收进 D 附表，其列值以 manifest 实况为准。
