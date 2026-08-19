# spec：b1-adc-servo —— 高频外设模块补齐（adc + servo）

## 问题陈述

电赛新题经常要求模拟量采集（电压监测 / 电位器调参 / 光敏检测）与舵机角度控制（云台转向 / 打靶 / 机械臂），但模块库没有对应实现：推荐链路只能输出「库外建议」（仅展示、不进工程），学生必须自己写驱动，与「打开就能编译、直接开写」的目标相悖。用户定调：主要精力做新题目，先补 adc + servo 两个最高频、素材最足的模块，双平台都要。

## 方案

新增两个普适模块（纯驱动切片，照 ADR 0009）：

### adc（模拟采样）

- 统一 API（双平台对偶）：`adc_init(adc_id, channel)` / `adc_get(adc_id, channel)` 返回 12 位采样值。
- stm32：**内嵌母版**（平台条目 files 空，照 led/oled/delay 先例）——母版 ml_libs 已有 `ml_adc.h`（`adc_pin_init` / `adc_init(ADCx_enum, ADCINx_enum)` / `adc_get`，通道枚举 PA0-PC5），母版接口块自动进骨架（build_master_interface_blocks），API 名天然对偶。
- mspm0：自有文件 `code/adc_mspm0.c/h`——从参考库 ADC12 driverlib 例程（adc12_single_conversion.c + .syscfg）提炼单次转换封装，API 名与 stm32 对偶。
- 引脚角色：`adc`（类型级能力已登记 PIN_ROLE_TYPES，板定义已带 `adc:ADC_Channel_N` token）；声明多通道角色（如 ADC_CH0 / ADC_CH1），默认脚 stm32 = PA0/PA1，mspm0 按板定义。

### servo（舵机角度）

- 统一 API（双平台对偶）：`servo_init(servo_id, channel)` / `servo_set_angle(servo_id, angle)`（0-180°，内部映射 50Hz / 0.5-2.5ms 脉宽）。
- stm32：自有文件 `code/servo_stm32.c/h`——基于母版 `ml_pwm`（`pwm_pin_init` / `pwm_init` / `pwm_update`，MAX_DUTY=50000），pwm 类型级解锁现成（任意 TIM 通道脚可绑）。
- mspm0：自有文件 `code/servo_mspm0.c/h`——基于 PWM 跨族迁移底座（pin_family.h 双分支，照 motor 先例）。
- 角度映射常量（周期 / 脉宽 / 占空比换算）在模块头文件单源，双平台共用同一份换算逻辑。
- 引脚角色：`pwm`（类型级解锁现成）。

## 用户故事

1. 作为参赛学生，题面要求「测量电压并显示」——AI 推荐命中 adc 模块，步骤 6 勾选，步骤 7 板图把 ADC 角色绑到实际引脚，骨架接口块含 adc_init/adc_get，生成工程编译 0 error 0 warning，我在 TODO 区直接写采集逻辑。
2. 作为参赛学生，题面要求「舵机转到指定角度」——同样链路命中 servo，servo_set_angle 直接可用。
3. 作为补录者，两个模块都支持 stm32 + mspm0 双平台，未上板真机验证的条目照现有机制标记（verified / 平台警告），不影响生成。
4. 作为工具维护者，模块库即数据库——新模块入库后推荐链路自动按能力命中，无需改推荐代码。

## 实现决策

- adc stm32 条目 files 空（内嵌母版），mspm0 条目 files = adc_mspm0.c/h；servo 双平台条目 files = 各自 .c/.h。
- adc mspm0 实现只做单次转换 + 轮询读取（v1），多通道各自初始化；DMA / 序列 / 定时器触发留范围外。
- servo 双平台共享角度换算：`angle → 占空比`（0.5-2.5ms / 20ms），stm32 用 pwm_update 写，mspm0 按 pin_family 分支写 PWMAB 或 TIMG 通道。
- manifest pins：adc 声明 `adc` 角色（required=false 或 true 视 API 需要，默认脚可绑）；servo 声明 `pwm` 角色（必选）。
- 平台条目 verified：stm32 adc = true（母版 ml_adc 已验证）；其余条目按编译矩阵结果标 verified（编译过 = true，未上板在 notes 注明），hardware_bound 照实。
- 模块依赖：两者皆无依赖（delay 不需要；servo 直接操作 PWM 寄存器/库）。

## 测试决策

- manifest 结构测试（照 test_module_* 先例）：slug / 描述四要素（能力方向、无题绑定）/ 平台条目形状 / pins 声明校验。
- API 对偶断言（照 test_module_motor_parity 先例）：双平台同名函数（adc_init/adc_get、servo_init/servo_set_angle）从各自头文件机械提取比对。
- 编译矩阵验收：stm32（UV4）+ mspm0（gmake 全量重建）0 error——照现有真机验收脚本/测试先例跑生成工程。
- 引脚绑定测试（照 test_pin_unlock_* 先例）：adc/pwm 类型级绑定 + 默认脚解析 + 渲染（pin_config.h / syscfg $assign）。
- 骨架接口块测试：选中模块后 build_skeleton_interfaces 含 adc/servo 头文件块。

## 范围外

- hc_sr04（超声波）、dht11（温湿度）——第二批。
- adc 的 DMA / 多通道序列 / 定时器触发（mspm0 例程多，后续按需补）。
- servo 多实例（multi_instance 机制已存在，servo 暂单实例，留扩展）。
- 真机硬件验证（工具环境无板；未上板条目照现有平台警告机制标注）。

## 补充说明

- 素材：stm32 ml_adc/ml_pwm 已在母版库；mspm0 ADC12 参考例程与塔克R3 舵机例程已在参考文件库，提炼后不动参考库。
- 语言规范：spec / 工单 / 提交信息中文。
