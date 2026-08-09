# 2021F 智能送药小车 — AI 开发纲要

> **⚠️ 铁律：每次修改代码后，必须同步更新以下三者，保持完全一致：**
> 1. **代码中的注释**（函数注释、行内注释、参数说明）
> 2. **本文档（CLAUDE.md）**（参数值、行号引用、状态机描述、OLED 显示内容）
> 3. **memory 文件**（如有涉及，同步更新 `~/.claude/projects/.../memory/` 下的相关记忆）
>
> 如果代码出现了改变，有可能是其他人有用意的改的，需要进行询问而不是改回
## 项目概述

2021 全国大学生电子设计竞赛 F 题：智能送药小车。STM32F103C8T6（Cortex-M3, 72MHz, 64KB Flash, 20KB RAM）+ K230 AI 摄像头。小车沿黑线巡线，经十字/T字路口，靠 K230 识别病房数字（1~8），自主导航到目标病房送药并返程。

**⚠️ 关键约束：** 运行在裸机 10ms 定时中断（TIM3 ISR → `pid_control()`），无 RTOS，无动态内存分配。所有状态机运行在中断上下文，OLED I2C 刷新在主循环。

---

## 硬件架构

```
STM32F103C8T6
├── 8路灰度传感器      → 黑线巡线 + 十字/T字路口检测
├── MPU6050 (陀螺仪)    → 转弯角度控制（200Hz INT 中断 + 卡尔曼融合）
├── HMC5883L (磁力计)   → 偏航角观测（卡尔曼融合输入）
├── 2路编码器电机       → PID 速度闭环 + 差速转弯
├── K230 AI摄像头       → UART1 115200bps 发送数字识别结果
├── OLED 128x64 (I2C)  → 4行×16字符调试显示
├── LED 红/绿 (PA11/12) → 状态指示
└── PB5 药物检测        → 放药启动(HIGH)/取药返程(LOW)
```

**K230 通信协议（CSV，det_uart.py → UART1）：**
```
--- frame N | M targets ---
数字,置信度,x1,y1,x2,y2,cx,cy,宽,高
```
K230 屏幕分辨率 1280×720，`cx` 和 `cy` 直接对应像素坐标。

---

## 项目文件结构

```
├── README.md                    ← 项目简介
├── CLAUDE.md                   ← 本文件（AI 开发纲要）
├── det_uart.py                 ← K230 端 Python 脚本
├── 2021F_智能送药小车.pdf       ← 竞赛题目
├── mp_deployment_source/       ← K230 模型部署文件（拷贝到 SD 卡 /sdcard/）
│   ├── deploy_config.json      ← 模型配置（8类数字，320×320，置信度0.4）
│   └── *.kmodel                ← 训练好的 AnchorBaseDet 模型
├── code/                       ← 应用层（★核心修改区★）
│   ├── pid.c / pid.h           ← PID控制 + 全部导航状态机（主文件）
│   ├── pid_debug.c             ← pid.c 的调试变体（参数可能不同，注意区分）
│   ├── motor.c / motor.h       ← 电机 + 编码器驱动
│   ├── gray_track.c / gray_track.h  ← 灰度传感器巡线 + 路口检测
│   ├── digit_uart.c / digit_uart.h  ← K230 UART 协议解析
│   └── filter.c / filter.h     ← 卡尔曼 + Mahony 滤波器
├── ml_libs/                    ← STM32 外设驱动库（少改）
│   ├── ml_oled.c/h             ← OLED 128x64 I2C 驱动
│   ├── ml_uart.c/h             ← UART 底层驱动
│   ├── ml_mpu6050.c/h          ← MPU6050 陀螺仪驱动
│   ├── ml_hmc5883l.c/h         ← HMC5883L 磁力计驱动
│   ├── ml_tim.c/h              ← 定时器/PWM
│   ├── ml_gpio.c/h, ml_exti.c/h, ml_nvic.c/h, ml_adc.c/h
│   ├── ml_i2c.c/h, ml_delay.c/h, ml_led.c/h, ml_pwm.c/h
│   └── headfile.h              ← 总头文件
├── sys/                        ← CMSIS 系统文件（不改）
│   ├── stm32f10x.h, system_stm32f10x.c/h
│   ├── core_cm3.h, core_cmFunc.h, core_cmInstr.h
│   └── startup_stm32f10x_hd.s, startup_stm32f10x_md.s
└── user/                       ← 用户入口 + Keil 工程
    ├── main.c                  ← 主循环（阶段1→2→3）
    ├── isr.c                   ← 中断服务（TIM3 pid_control + UART1 RX）
    └── Project.uvprojx         ← Keil MDK 工程文件
```

---

## K230 部署指南

### 镜像烧录

- **镜像下载**：[勘智开发者社区-资料下载](https://developer.canaan-creative.com/resource)，根据开发板型号选择对应版本的最新镜像
- **Micropython Daily Build**：每日定时编译更新的固件，包含最新特性，请谨慎选择
- **镜像烧录教程**：[烧录固件 — CanMV K230](https://developer.canaan-creative.com/k230_canmv_docs/zh/latest/zh/userguide/01_burning_image.html)

### 上板运行

镜像烧录结束后，连接开发板接通电源；

在 IDE 连接开发板的前提下，将 `mp_deployment_source` 文件夹和测试图片 `test.jpg` 拷贝到盘符 `CanMV/sdcard/` 目录下；

然后在 IDE 中选择 **文件 → 打开文件**，打开部署包中提供的脚本，点击左下角按钮运行。

> **💡 脱机运行：** 如需脱离 IDE 独立运行（仅供电、不连电脑），需使 K230 上电后自动执行数字识别脚本。两种方法：
> 1. 将 `det_uart.py` 改名为 `main.py` 拷贝到 `/sdcard/` 目录下（CanMV 上电自动执行 `main.py`）
> 2. 在 CanMV IDE 中：**工具 → Save open script to CanMV board (as main.py)**

> **⚠️ 注意：** 请注意部署脚本中的文件或目录的路径，如果路径错误，请修改为正确的路径再运行。

### 附注

如果在部署过程中有任何问题，请在 [勘智问答社区](https://developer.canaan-creative.com/qa) 发帖交流，技术人员会给您帮助。

---

## 执行模型

```
main() 主循环（轮询）:
  ├── digit_uart_parse()        ← 解析 K230 UART 帧 → digit_result
  ├── 阶段1: K230 识别数字 → 锁定 dest_index
  ├── 阶段2: 等待药物放上(PB5=HIGH) → car_started=1
  └── 阶段3: OLED 刷新（检查 oled_dirty 标志）

TIM3 ISR（10ms 周期，硬实时）:
  └── pid_control():
      ├── 编码器读数 + 速度 PID 计算
      ├── ★ 全部导航状态机（十字路口 + K230决策 + 远端导航 + 药房）
      ├── OLED 缓冲区更新（每200ms，写 oled_line1~2 各8字符，置 oled_dirty=1）
      └── 电机占空比输出（motorA_duty / motorB_duty）
```

**⚠️ 关键：** 所有导航逻辑运行在 ISR 中，不能阻塞、不能 `delay_ms()`、不能用 `malloc()`。用状态机 + 计数器实现延时。

---

## 导航模型（★最重要★）

### 场地布局
```
起始区 ──→ [第1路口:病房1/2] ──→ [第2路口:病房3~8动态决策]
                                     │
                      ┌──────────────┼──────────────┐
                      ↓ 直行          ↓ 左转          ↓ 右转
                  [大T字路口]      (进中部病房)    (进中部病房)
                   ↙      ↘
             [小T:Q3]   [小T:Q4]     ← 每个小T各有1张牌
```

- **病房1、2**：位置固定，第1路口两侧（不需要K230识别）
- **病房3~8**：随机分布在中部2个 + 远端4个位置
- **第2路口**：K230 识别数字决定方向（左转/右转/直行）
- **直行后**：进入"远端导航"（大T路口 → 2个小T路口）

### 路由表（route_table，pid.c）
```c
dest=1: {LEFT, NONE}
dest=2: {RIGHT, NONE}
dest=3~8: {STRAIGHT, K230_DECIDE, NONE}  // 第1路口直行，第2路口K230决策
```

### 路径记忆（path_memory）
去程记录每个十字路口的动作，返程倒序读取并逆转（左↔右，直行不变）。

---

## 核心状态机（pid.c `pid_control()`）

### 1. 十字路口状态机（cross_state）

| 状态 | 说明 |
|------|------|
| `CROSS_NORMAL` | 巡线 + K230识别 + 等待路口检测(cross_detect) |
| `CROSS_STRAIGHT` | 直行通过路口（200ms 直行 → 冷却） |
| `CROSS_TURN` | 转弯（先直行过路口中心 → 60°陀螺仪旋转 → 冷却） |
| `CROSS_COOLDOWN` | 冷却期：巡线但不检测路口（800ms） |

**转弯函数：** `turn_left_70()` / `turn_right_70()` — 参数：`phase`（0=直行阶段, 1=转弯阶段）、`cnt`、`start_yaw`。返回值：0=PID输出中, 1=开环旋转中, 2=完成。

### 2. K230 动态路口决策（第2路口）

```
CROSS_COOLDOWN 结束 → k230_approach_state=1 (Y-center逼近)
  → 巡线 + 监控 K230 cy≈110（FAR_Y_CENTER）
  → 停车+识别 1秒 (k230_approach_state=2，停车即flush开窗口，不分两段)
  → 锁存决策 (k230_decision_ready=1, k230_saved_action)
  → 继续巡线等物理路口 (cross_detect)
  → 物理路口触发 → 使用已锁存的决策转弯
```

**关键变量：**
- `k230_approach_state`: 0=空闲 1=巡线逼近 2=停车+识别（已合并，3=废弃）
- `k230_decision_ready`: 1=Y-center识别已完成，等待物理路口
- `k230_saved_action`: 锁存的决策结果
- `k230_is_second_turn`: 标记当前转弯来自第2路口K230决策（用于左右转直行延迟区分）
- `K230_RECOG_WINDOW = 100` (1000ms 识别窗口)
- `FAR_Y_CENTER = 110` (Y-center阈值：第2路口/小T用，实测校准值)
- `FAR_Y_CENTER_LARGE_T = 110` (大T路口专用Y-center阈值，与小T共用同一值)
- `FAR_Y_TOLERANCE = 100` (Y坐标容差)
- `FAR_Y_STABLE_CNT = 5` (稳定帧数 5×10ms=50ms)

**兜底：** Y-center 2秒超时 + 物理路口检测 → 跳过Y-center直接停车识别

### 3. 远端导航（far_nav，大T+小T路口）

第2路口K230决策直行后激活（`far_nav_pending=1` → `far_nav_init()`）。

**状态机 `far_state`：**
```
FAR_LARGE_T_APPROACH   → 巡线+cy监控 → Y-center停车(200ms)
FAR_LARGE_T_STOPPED    → 短暂停车
FAR_LARGE_T_SCAN_LEFT  → 左转10°扫描Q3卡牌
FAR_LARGE_T_RECOGNIZE  → 识别窗口锁定Q3的2张牌 → 排除法推Q4
FAR_LARGE_T_TURN_BACK  → 右转10°回正
FAR_LARGE_T_TO_JUNCTION→ 巡线到物理路口
FAR_LARGE_T_TURN       → 60°转弯进分支（复用 turn_left_70/turn_right_70，使用 TURN_TARGET_DEG）
FAR_LARGE_T_COOLDOWN   → ★巡线冷却不停车（与CROSS_COOLDOWN一致）→ 进小T干路

FAR_SMALL_T_APPROACH   → 巡线+cy监控 → Y-center停车(1秒) ★
                        → ★使用连续miss重置逻辑：命中+1且清零miss_cnt，连续5帧未命中才清零stable_cnt
                        → 兜底超时2s + t_cross_detect物理路口触发
FAR_SMALL_T_STOPPED    → 停车+识别(1秒，停车即flush开窗口，不分两段)
FAR_SMALL_T_RECOGNIZE  → ★已废弃：识别已合并到FAR_SMALL_T_STOPPED中
FAR_SMALL_T_TO_JUNCTION→ ★巡线到物理路口（t_cross_detect检测路口再转弯）
FAR_SMALL_T_TURN       → 转弯进病房(60°，复用 turn_left_70/turn_right_70)
FAR_SMALL_T_COOLDOWN   → ★巡线冷却不停车（与CROSS_COOLDOWN一致）→ route_complete=1 → 药房检测
```

**关键函数：**
- `far_check_y_center(y_center)`: 检测是否有数字 cy ≈ 指定Y阈值（不同路口传入不同阈值）
- `far_recog_scan()`: 累积各数字最高置信度 + 运行平均 cx（每次更高置信度检测均计入平均，抑制偶发噪声帧对左右分配的翻转）
- `far_recog_top_n(n, out)`: 取置信度最高的N个数字
- `far_small_realtime_calc()`: 小T识别窗口内实时计算左/右分配 + 转弯方向（纯读取，不修改状态）

**关键参数：**
- `FAR_Y_CENTER = 110`（第2路口/小T/大T共用）, `FAR_Y_TOLERANCE = 100`, `FAR_Y_STABLE_CNT = 5`
- `FAR_SCAN_DEG = 10.0f` (大T路口左转扫描Q3角度)
- `FAR_RECOG_WINDOW = 100` (1000ms), `FAR_RECOG_WARMUP = 5` (预热帧数)
- 转弯角度复用 `TURN_TARGET_DEG = 60.0f`（`FAR_TURN_TARGET_DEG = 70.0f` 已定义但未使用）
- 停车时间：大T=200ms, 小T=1000ms（1秒）
- `YCENTER_SUPPRESS_CYCLES = 25`（冷却结束进入巡线后Y-center抑制周期数，25×10ms=0.25s，改0即关闭）

### 4. 病房到达 + 返程

- `route_complete=1` → 延迟500ms → 停车区黑白块图案（`parking_block_detect()`）或全白保底（`all_white_detect()`）→ 进入病房
- 病房内：检测药物被取走(PB5=LOW) → 160°掉头 → 冷却 → 启动返程模式
- 返程：`path_memory` 倒序逆转 → 回药房（起始区）
- **⚠️ 代码中 `in_pharmacy` / `PHARMACY_WAIT_LIFT` 等命名沿用旧版，实际指"到达病房"**
- **返程到站停车（停车区黑白块图案检测）：**
  - 返程最后路口转弯完成后，`all_return_done` 在 cooldown 第一个周期立即置 1，封锁后续路口检测
  - `all_return_done=1` 后全速行驶 2 秒（200 帧），再降至 `BASE_SPEED × RETURN_ARRIVE_SPEED_RATIO`（40%），既保证效率又确保停车区可靠检测
  - 每帧检测 `parking_block_detect() || all_white_detect()` → `arrive_cnt` 累加；连续5帧(50ms)非停车图案才递减一次（抗噪递减）
  - `arrive_cnt >= 3` → `return_arrived=1` → 永久停车+绿灯
  - 已到达后 `return_arrived` 锁存，防止传感器噪声重启电机

### 5. 停车区黑白块检测（`parking_block_detect()`，gray_track.c）

停车区地面贴有黑色胶带条和白色间隙（横条图案），各约 2~3 个传感器宽度。
灰度传感器经过时产生 ≥2 个独立的黑色段，这是区分"正常巡线（只有1条黑线）"和"停车区"的关键特征。

**算法：** 扫描 8 路传感器，统计连续黑传感器的段数（runs of black）。≥2 段 → 停车区图案。
**示例：** `11000110`（2段黑）、`10011000`（2段黑）、`11100011`（1段黑，走全白保底）
**保底：** `all_white_detect()` 作为后墙白线保底，两者 OR 触发停车。

---

## OLED 显示（每200ms刷新，2行×8字符大字模式 16×32px）

大字模式使用 `OLED_ShowCharBig()` / `OLED_ShowStringBig()`（ml_oled.c），将原有 8×16 字库 2× 缩放至 16×32 像素。
每行 8 个字符，两行覆盖全屏（128×64）。仅显示数字识别信息，不再显示传感器/角度/电机等调试数据。

| 场景 | L1（pages 0-3） | L2（pages 4-7） |
|------|-----------------|-----------------|
| 默认巡线（去程） | `DEST: X` | `GO >>` |
| 默认巡线（返程） | `DEST: X` | `<< RET` |
| 远端导航中 | `DEST: X` | `FAR NAV` |
| 远端返程中 | `DEST: X` | `FAR RET` |
| 病房到达（等待取药） | `DEST: X` | `PHARM` |
| 到站停车 | `DEST: X` | `ARRIVED` |
| **第2路口K230识别中** | `L:X R:Y`（按cx分左右） | `JUNC 2` / `TURN L` / `TURN R` |
| **大T路口识别** | `L:XY`（Q3两张牌） | `R:ZW`（Q4两张牌） |
| **小T路口识别** | `L:X R:Y`（左右数字） | `TURN L` / `TURN R` |

**数据来源：**
- 第2路口：扫描 `cand_conf[1..8]` 和 `cand_cx[]`，cx最小=左，cx最大=右
- 大T路口：`far_q3_cards[]`（左/Q3）、`far_q4_cards[]`（右/Q4）
- 小T路口：`far_small_realtime_calc()` 实时计算左右分配

**OLED 缓冲区**（pid.c）：
- `oled_line1[32]`、`oled_line2[32]`：各存放 8 字符（`FMT8` 宏空格填充），供主循环大字渲染
- `oled_line3[32]`、`oled_line4[32]`：保留但不再使用（置空字符串）
- `oled_dirty`：ISR 每 200ms 置 1，主循环消费后清零

**主循环渲染**（main.c 阶段3）：
```c
OLED_ShowStringBig(1, 1, oled_line1);
OLED_ShowStringBig(2, 1, oled_line2);
```
阶段1/2 仍使用普通 8×16 字体（`OLED_ShowString`），因为大字模式启动前需先清屏。

---

## 修改指南

### 如果要在小T路口加新行为
1. 在 `far_nav_control()` 的 `FAR_SMALL_T_*` 的 case 中添加状态
2. 参数在 pid.c 第 52 行附近（`FAR_Y_CENTER` 等宏定义）
3. OLED 大字显示在 pid.c 第 1313 行附近（`oled_line1/2` 构建区，`FMT8` 宏）

### 如果要在第2路口加新行为
1. 修改 `k230_approach_state` 状态机（在 `CROSS_NORMAL` case 顶部）
2. 物理路口触发逻辑在 pid.c `if(action == CROSS_ACTION_K230_DECIDE)` 处
3. OLED 大字显示检查 `k230_approach_state` / `k230_decision_ready` / `recognition_active`

### 如果要修改识别参数
- 识别窗口长度：`K230_RECOG_WINDOW`（第2路口）或 `FAR_RECOG_WINDOW`（远端）
- Y-center 容差：`FAR_Y_TOLERANCE`
- 稳定帧数：`FAR_Y_STABLE_CNT`
- K230置信度阈值：`deploy_config.json` 中的 `confidence_threshold`

### 如果要修改转弯角度
- 常规路口/小T/大T：`turn_left_70()` / `turn_right_70()` → 修改 `TURN_TARGET_DEG`（当前 60.0f）
- 药房掉头：`turn_left_200()` / `turn_right_200()` → 修改 `PHARMACY_TURN_DEG`（当前 160.0f）

### 如果要修改转弯占空比
- `TURN_DUTY = 6000` (12%)：转弯时**正转轮**占空比
- `TURN_DUTY_REV = 10000` (20%)：转弯时**反转轮**占空比，补偿电机反转方向更大的摩擦
- 调整原则：反转轮需要更高占空比才能与正转轮出力均衡，实现真正的原地差速转弯
- 如果反转轮仍偏慢 → 增大 `TURN_DUTY_REV`；如果反转轮过冲 → 减小 `TURN_DUTY_REV`

### 如果要修正巡线中心偏置（线不在传感器正中间）
- 先确认偏移方向：线在 D5-D6 之间（偏右）说明右轮偏强/左轮偏弱，车有天然左转趋势
- 线在 D3-D4 之间（偏左）说明左轮偏强/右轮偏弱，车有天然右转趋势
- **左右轮速度缩放**：`MOTOR_A_SCALE` / `MOTOR_B_SCALE`（pid.c `motor_target_set` 上方，当前 A=1.40f / B=0.70f）
  - 线偏右 → 减小 `MOTOR_B_SCALE`（抑制右轮）或增大 `MOTOR_A_SCALE`（补偿左轮），如 `MOTOR_B_SCALE = 0.95f`
  - 线偏左 → 减小 `MOTOR_A_SCALE` 或增大 `MOTOR_B_SCALE`
  - 精细调整步长 0.01~0.02，观察线是否回到 D4-D5 之间
- 此缩放影响所有速度闭环巡线，不影响开环转弯（转弯用 `TURN_DUTY`/`TURN_DUTY_REV`）

### 如果要修改转弯直行延迟
- 常规路口：`GO_STRAIGHT_MS = 200`
- 大T左转：`GO_STRAIGHT_MS_FAR_LEFT = 200`，右转：`GO_STRAIGHT_MS_FAR_RIGHT = 200`
- 第2路口K230左转：`GO_STRAIGHT_MS_K230_LEFT = 200`，右转：`GO_STRAIGHT_MS_K230_RIGHT = 200`
- 第2路口K230决策通过 `k230_is_second_turn` 标志自动选择对应延迟

### 如果要修改转弯后冷却行为
- **所有冷却状态统一使用 `line_pid_track()` 巡线不停车**，与 `CROSS_COOLDOWN` 一致
- 远端导航冷却（`FAR_LARGE_T_COOLDOWN` / `FAR_SMALL_T_COOLDOWN`）返回 `0`（让速度PID运行）
- 远端返程冷却（`FAR_RET_SMALL_T_COOLDOWN` / `FAR_RET_LARGE_T_COOLDOWN`）返回 `0`（让速度PID运行）
- 冷却时间由 `COOLDOWN_MS = 800` 控制，冷却期内仅抑制路口检测
- 如果新增冷却状态需要停车：用 `motorA_duty(0); motorB_duty(0);` + `return 1;`（跳过速度PID）

### 如果要调整快速接近速度（dest 3~8 送药提速）

dest 3~8 送药过程在第一个路口前使用 `FAST_BASE_SPEED`（默认 25.0），在 `cross_detect()` 检测到第一个全黑十字路口时自动降回 `BASE_SPEED`（15.0）。dest 1~2 和返程全程不受影响。

- **快速阶段太快（过冲/脱线）**：减小 `FAST_BASE_SPEED`（如 20.0、18.0），或减少 `RAMP_CYCLES` 使加速更平缓
- **快速阶段不够快**：增大 `FAST_BASE_SPEED`（如 28.0、30.0），注意观察转弯时不脱线
- **第一个路口未触发降速**：检查 `cross_detect()` 是否正常（8 路全黑才触发），确认物理路口黑胶带完整
- **返程也被加速（不应出现）**：检查 `fast_approach` 复位逻辑，`line_pid_track()` 中已用 `!return_mode` 保护
- **快速接近期间转弯需更大推力**：可单独增大 `MOTOR_A_SCALE`/`MOTOR_B_SCALE` 补偿高速下的不对称

### 如果要调试巡线微摆
- **陀螺前馈增益**：`GYRO_DAMP_GAIN`（pid.c `line_pid_track` 顶部，当前 = 0 已关闭）
  - 如需启用：微摆不减 → 逐步增大到 0.03~0.08
  - 巡线反应变迟钝 → 减小到 0.01~0.02
- **PD参数**：`pid_init(&line_pid, ...)`（main.c:41），P=1.0, D=2.5
  - P 过大 → 过冲振荡 → 减小 P（可到 0.6~0.8）
  - D 过大 → 高频抖动 → 减小 D（可到 1.5~2.0）
- **死区**：`LINE_DEADBAND`（默认 0.5）
  - 中心附近仍微摆 → 增大到 0.8~1.0
  - 小偏差纠正太慢 → 减小到 0.2
- **⚠️ 已移除 EMA 滤波**：EMA 低通滤波与 D 项互相矛盾（EMA 抹平变化 → D 项失效），现在传感器偏差直接进 PD，D 项即时响应变化率。如传感器有偶发毛刺，可用死区过滤，不要加 EMA。

### 如果要调整停车区检测（黑白块图案 + 全白保底）

停车检测现在使用 `parking_block_detect() || all_white_detect()`，前者检测黑白交替块图案（≥2个独立黑色段），后者为后墙白线保底。

- **停车区误触发（正常巡线时误判为停车区）**：增加黑色段阈值。`parking_block_detect()` 当前要求 `black_segments >= 2`，可改为 `>= 3`（要求至少3段黑块才触发）
- **停车区未触发（到了停车区但不停）**：
  - 先确认 OLED L1 显示的实际传感器值，看黑色段数是否 ≥2
  - 如果是 `11100011` 类单段宽黑块图案 → 走全白保底触发，需确认后墙白线确实存在
  - 如果停车区黑白块太宽（单段黑横跨4+传感器）→ 调整胶带间距使黑色段落在2~3传感器宽
- **过度依赖全白保底**：增大 `arrive_cnt` 阈值（当前3），或增大 `arrive_black_cnt` 递减阈值（当前5）使全白检测更严格
- **速度过快冲过停车区**：减小 `RETURN_ARRIVE_SPEED_RATIO`（当前 0.40），如 0.30 或 0.25
- **返程最后段太慢**：增大 `RETURN_ARRIVE_SPEED_RATIO`，如 0.50 或 0.60
- **终点停车后又启动**：检查 `return_arrived` 锁存逻辑是否被意外清零（返程启动时在 pid.c:1555 行重置）

### 常用模式（遵循现有代码风格）
- 延时 = `static int cnt = N; if(--cnt <= 0) { ... }` (每周期减1, 10ms/周期)
- 新状态 = 在 enum 末尾添加，在 switch 中添加 case
- 新全局变量 = 在 pid.c 文件顶部用 `static` 声明
- OLED 显示 = 写 `oled_line1~2` 缓冲区（各8字符，`FMT8` 宏填充）+ `oled_dirty = 1`

---

## 调试开关

| 宏 | 位置 | 作用 |
|----|------|------|
| `DEBUG_FORCE_DEST` | main.c:6 | 强制锁定目的地(1~8)，0=正常 |
| `K230_DEBUG` | main.c:9 | 上电后显示K230原始检测数据 |
| `DEBUG_TURN_ON_ALL_WHITE` | pid.c:46 | 全白触发转弯（无场地时调试用） |
| `DEBUG_STOP_AFTER_TURN` | pid.c:45 | 转弯完成后永久停车（观察角度） |
| `GYRO_DAMP_GAIN` | pid.c:69 | 陀螺前馈增益(0=关闭, 0.03~0.10推荐)，当前=0 |
| `LINE_DEADBAND` | pid.c:70 | 中心死区阈值(0~2)，越大越不敏感 |
| `MOTOR_A_SCALE` | pid.c:22 | 左轮速度缩放(默认1.40，>1=补偿弱侧) |
| `MOTOR_B_SCALE` | pid.c:23 | 右轮速度缩放(默认0.70，<1=抑制强侧) |
| `RETURN_ARRIVE_SPEED_RATIO` | pid.c:72 | 返程最后路口→终点白线段降速比例(0.40=40%)，all_return_done后2秒(200帧)生效 |
| `YCENTER_SUPPRESS_CYCLES` | pid.c:60 | 转弯后进入巡线时Y-center抑制周期数(25×10ms=0.25s)，改0即关闭，CROSS_COOLDOWN和大T冷却结束时置此值 |
| `FAST_BASE_SPEED` | pid.c:31 | dest 3~8 送药过程第一个路口前的高速基础速度(默认25.0，正常15.0)，仅送药过程生效，返程不变 |
| `fast_approach` / `fast_approach_init_done` | pid.c:114-115 | 快速接近模式标志 + 一次性初始化标记（因定时器在car_started=1后才启动） |

---

## 编译与烧录

1. 打开 `user/Project.uvprojx`（Keil MDK v5）
2. 编译器：ARMCC V5.06 update 7
3. 目标：STM32F103C8 (或 C6)
4. Build → `user/Objects/Project.hex`
5. 用 ST-Link烧录 HEX 到 STM32
