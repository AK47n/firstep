# 01 — mspm0 母版默认外设布局：空模板 syscfg 换默认外设（MSPM0 线"打开就能编译"闭环）

**What to build:** 2026-08-11 MSPM0 线真机验收（2026H 题）发现：mspm0 母版 syscfg 是 TI 空模板（只有时钟），而模块库全部 mspm0 实现（motor/huidu/key/ntb_time/oled/imu_uart/led_beep/delay）都直接引用 SysConfig 生成的宏（PWMAB_INST / DC_MOTOR_AIN1_PORT / IMU601_INST / OLED_INST / NTB_INST / MOTOR_PID_INST / HUIDU_L*_PIN / KEY_PORT / LED_BEEP_LED_PIN / GPIO_PWMAB_C0_IDX / DC_MOTOR_AA_IIDX 等 38 个），空模板生成的头里一个都没有 → 生成工程必然编译失败（use of undeclared identifier ×N）。已写好默认外设布局 `.scratch/real-run/mspm0_default.syscfg`（2026-08-11 本地 sysconfig_cli + gmake 全量构建验证 0 错 0 警），本工单把它落地为母版 syscfg，让"打开就能编译"在 mspm0 线成立。

**Blocked by:** 无

**Status:** open

## 需求

1. **`library/masters/mspm0/mspm0.syscfg` 整体替换为 `mspm0_default.syscfg` 内容**（配置里 masters_dir = `library/masters`，生效母版库；`~/.contest_generator/masters/mspm0` 是旧副本，不动）。实例与引脚：PWMAB（TIMG0，CC0→PA12 CC1→PA13 双通道 PWM）、MOTOR_PID（TIMG6，Basic_Periodic）、NTB（TIMG7，Basic_Periodic）、DC_MOTOR（输出 AIN1=PA0 AIN2=PA1 BIN1=PB18 BIN2=PA7 + 编码器中断 AA=PA16 AB=PA17 BA=PB19 BB=PB20）、HUIDU（8 路输入 PA22-27/PB4/PB5）、KEY（输入 PA2）、LED_BEEP（输出 PA3）、IMU601（UART0，RX 中断，PA11/PA10，115200）、OLED（I2C1 控制器，PB3/PB2，400k）、SYSTICK 无（delay 模块只依赖 CPUCLK_FREQ 忙等）。
2. **验收回归**：替换后重跑 2026H mspm0 全管线，生成产物**直接** gmake 构建 0 错（无需手工换 syscfg）。
3. **CONTEXT.md**：mspm0 词条补一句"母版 syscfg = 默认外设布局（模块代码与 syscfg 实例名绑定，改引脚不改实例名）"。

## 文件边界

- `library/masters/mspm0/mspm0.syscfg`：唯一代码/数据改动（用 `.scratch/real-run/mspm0_default.syscfg` 内容替换，保留文件头注释与 cliArgs）
- `.scratch/real-run/`：generate_check.py 已有 mspm0 支持（2f0d5ba/ad3eb71），如发现回归可小改，但预期零改动
- `CONTEXT.md`：补一句

## 验收

- [ ] 替换后 `python .scratch/real-run/generate_check.py --platform mspm0 --topic-file "sources/contest/2026H/26H/H题_车载平衡滚球运动控制系统.md" --clarify .scratch/real-run/clarify_2026H.json --add imu_uart,led_beep --drop pid,digit_uart,filter,ml_mpu6050 2026H` 全绿（推荐/骨架/生成/产物检查）
- [ ] 生成产物 `.scratch/real-run/out_2026H_mspm0/Debug` 下 `gmake all` 0 error（**不再需要手工换 syscfg**）
- [ ] 全量 pytest 绿 + mypy src 干净（syscfg 不参与测试，跑一遍确认无意外）
- [ ] 用户 CCS Theia 打开生成工程 GUI 编译复验（最终证明，可选——命令行已证）

## 实施提示词（复制到新会话）

```
落地 MSPM0 母版默认外设布局工单 .scratch/mspm0-syscfg-default/issues/01-syscfg-default.md：
1. 读工单文件 + .scratch/real-run/mspm0_default.syscfg（真机验证过的成品）+
   library/masters/mspm0/mspm0.syscfg（现空模板）
2. 把 mspm0_default.syscfg 内容整体替换进 library/masters/mspm0/mspm0.syscfg
   （保留原 cliArgs 头注释即可；实例名/宏名勿动——模块代码绑定）
3. 改 CONTEXT.md mspm0 词条补一句
4. 重跑验收命令（见工单验收节，clarify json 已存在），生成产物直接 gmake 构建
5. 全量测试 + mypy
6. 提交（数据改动，消息前缀 data:）+ 推送
注意：勿动 src/（syscfg 是母版文件，生成流程复制即生效）；勿动 ~/.contest_generator/
```
