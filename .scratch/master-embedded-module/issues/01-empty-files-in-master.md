# 01 — 母版内嵌模块条目（files 空 = 实现内嵌母版，消除 stm32 误报"缺平台版本"）

**What to build:** stm32 母版内嵌逐飞 ML 驱动层（ml_libs/ml_oled、ml_delay、ml_led、ml_pwm、ml_tim、ml_gpio、ml_exti、ml_nvic、ml_uart、ml_i2c、ml_systick、ml_adc，uvprojx 已注册、2026C/21F 真机编译过），但模块库 manifest 的 platform 条目只登记"模块携带"的实现（mspm0 全量、stm32 的 digit_uart/pid/ml_mpu6050 等 code 层）——"实现内嵌母版"无法表达，平台检查 `manifest.platforms.get(platform)` 对 oled/delay/led_beep/key/motor 一律误报"缺平台版本（生成将失败）"。本工单给 manifest 加"空 files = 母版内嵌"语义并补数据，让平台检查与生成流程认母版内嵌实现。

**Blocked by:** 无

**Status:** resolved（2026-08-10 已合 main，PR #41 merged，merge commit bc4408f，997 绿 + mypy 干净）

## 需求

1. **manifest 空 files 语义**（manifest.py `_parse_file_list`）：files 允许空数组，语义 = 该平台实现已内嵌母版、无模块文件需复制/注册/校验。PlatformEntry.docstring 与 ManifestError 文案同步说明（空 files 合法，但平台条目本身必填）。
2. **复制跳过**（generator.py `_copy_module_files`）：空 files 条目不复制、不加 include 目录（现状循环天然跳过，补显式语义注释即可）。
3. **门禁并入母版头**（generator.py `_check_main_calls`）：接口集 = 模块头 + 母版头（corpus.master_headers 已收集，直接并入）——main.c 调母版内嵌模块的 ml_* API 不再误报未定义。mspm0 母版无 .h，并入为空，无副作用。
4. **平台检查**（selection.py）：有条目即过（现状已如此，不动）。
5. **数据补录**（library/modules/*/manifest.json 直接改，走库根自动提交）：
   - `oled` / `delay` / `led_beep` 加 stm32 空条目：`{"files": [], "verified": true, "hardware_bound": false, "notes": "实现内嵌母版 ml_libs/ml_oled.c/h + ml_oled_font.h（逐飞 ML 库，2026C/21F 真机编译过）", "kit": "", "source_url": ""}`（delay → ml_delay.c/h；led_beep → ml_led.c/h，蜂鸣器与 mspm0 版同为占位空实现）
   - `digit_uart` / `ml_mpu6050` 的 stm32 条目 verified 翻 true（文件来自 21F 且真机编译过：digit_uart.o / ml_mpu6050.o）；**`pid` 的 verified 翻 true 挪至工单 02 一并实施**（01/02 并行会双改 pid/manifest.json，02 补 pid_isr.c 时顺手翻）
6. **不动的**：key / motor 不加空条目（stm32 侧缺 code 层胶水：21F 的 code/motor.c + user/isr.c 编码器中断计数未入库，空条目 = 生成的 main.c 调 motor_init 等函数过不了门禁——归工单 02 补录）；imu_uart / ntb_time / huidu 真缺 stm32 实现，警告保留。
7. **CONTEXT.md** 功能库词条（第 17 行）补一句：模块平台条目 files 空 = 实现内嵌母版（随母版进工程，不复制不注册）。

## 文件边界

- `src/contest_generator/manifest.py`：_parse_file_list 放开空校验 + PlatformEntry / 相关 docstring
- `src/contest_generator/generator.py`：_check_main_calls 并入母版头（~3 行）；_copy_module_files 空 files 注释
- `src/contest_generator/selection.py`：不动（验证性检查）
- `library/modules/{oled,delay,led_beep}/manifest.json`：加 stm32 空条目
- `library/modules/{digit_uart,ml_mpu6050,pid}/manifest.json`：verified 翻 true
- `tests/`：manifest 空 files 解析用例（含"空 files 平台条目合法、无 files 数组仍报错"）；平台检查空条目无 missing 警告；_copy_module_files 空条目跳过；_check_main_calls 母版头函数不误报（语料构造带 master_headers）
- `CONTEXT.md`：功能库词条补句

## 验收

- [x] 全量测试绿 + mypy 干净（979 绿，mypy 32 文件干净）
- [x] oled/delay/led_beep 选入 stm32 生成：平台检查无 missing 警告、生成成功、输出无模块文件、uvprojx 不新增注册（母版已含）
- [x] main.c 调 ml_oled_* / ml_delay_ms 等母版函数过门禁（不报未定义）
- [x] digit_uart/ml_mpu6050/pid 在 stm32 上不再报"未验证"（pid 条目未动、由工单 02 翻 verified）
- [x] imu_uart/ntb_time/huidu 在 stm32 上仍报 missing（回归）
- [x] mspm0 全量回归无变化
- [x] 独立 worktree + 独立 commit，工作区其他未提交修改不混入

## Comments

- 2026-08-10 立项（用户排查 AI 推荐警告：stm32 生成报 8 个 missing + 3 个 unverified）：逐模块核实——oled/delay/led_beep/key/motor 的 stm32 实现内嵌母版（21F 编译过 ml_oled.o/ml_delay.o/ml_pwm.o/ml_tim.o/ml_gpio.o/ml_exti.o/ml_nvic.o/ml_uart.o，母版 uvprojx 已注册 13 个 ml_*）；key/motor 的 code 层胶水（21F code/motor.c + user/isr.c）未入库，空条目过不了门禁 → 归工单 02；imu_uart（21F 用 I2C MPU6050/罗盘，无 UART IMU 代码）/ ntb_time（NTB 是 MSPM0 专属外设）/ huidu（stm32 灰度巡线在 pid 模块的 gray_track 内）真缺，警告保留。方案选 A（空 files 母版内嵌），用户 2026-08-10 确认
- 2026-08-10 实施完成：_parse_file_list 放开空数组（PlatformEntry docstring 同步）；_check_main_calls 接口集并入母版头（format_interface_blocks 复用，slug="母版"）；_copy_module_files 空条目注释；save_manifest 结构校验同步放开（"空文件列表"措辞随语义更新）+ 空条目可存测试；数据补录 oled/delay/led_beep stm32 空条目 + digit_uart/ml_mpu6050 verified 翻 true；pid 未动（归工单 02）。验收全勾，PR #41（worktree firstep-master-embedded，branch master-embedded-01，commit 37bffb0）
