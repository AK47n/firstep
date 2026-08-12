# 03 — pid 剥离决策层（双平台巡线套装瘦身）

**What to build:** pid 模块瘦身为纯驱动（ADR 0009），双平台分别剥离决策层：stm32 侧 gray_track 十字路口检测 + pid_isr 10ms 调度 → 骨架；mspm0 侧 gray_track_mspm0 启停线检测 + LAP 状态机 → 骨架。保留驱动：PID 控制器（pid_cal / pid_control）+ 灰度读取（gray_track 双平台）。manifest 描述按判据四要素重写（能力方向 = PID 闭环控制 + 灰度循迹驱动）；deps 按剥离后实际依赖更新——若 ball_detect / digit_uart / ml_mpu6050 只被滚球决策层使用 → 移出 deps（决策层素材走参考文件库：21F / 26H 原工程在 sources/，归档路径实施时确认）。**先决依赖：工单 01 已闭环（结构测试 + EXCEPTION_REGISTRY 例外注册表已立）——本工单清理 pid 后必须删除注册表对应条目（不删 = 存量校验红）。注意与工单 04（ball_detect）交叉。**

**Status:** resolved（2026-08-12 实施闭环，1095 绿 + mypy 干净 + 双平台编译 0 错，见下方实施记录）

## 实施（细节实施会话定）

1. stm32 侧：pid.c / gray_track.c 保留 PID + 灰度读取，十字路口检测移出；pid_isr.c 评估——10ms 调度移出后若文件为空壳则删除（骨架自建定时器调度）。
2. mspm0 侧：gray_track_mspm0.c 保留灰度读取，启停线检测 + LAP 状态机移出；pid_mspm0.c 保留 PID。
3. manifest.json：description 四要素；deps 与剥离后一致。
4. 决策素材：21F / 26H 原工程若未归档进参考文件库 → 归档（register/write_archive_entries），工单记录归档结果。
5. 结构测试 EXCEPTION_REGISTRY（tests/test_module_universality.py）删除 pid 条目——不删 = 存量校验红。

## 文件边界

- library/modules/pid/code/*（pid.c / pid_isr.c / gray_track.c / gray_track_mspm0.c / pid_mspm0.c + 对应 .h）
- library/modules/pid/manifest.json
- 可能：references 库归档条目（决策源码素材）
- **不动**：motor / ball_detect / digit_uart / ml_mpu6050 模块内容（deps 变化只改 pid 的 manifest）

## 验收

- [x] 双平台编译 0 错：stm32 UV4（21F 巡线线）+ mspm0 gmake（2026H 滚球线）。
- [x] 结构测试绿（pid 不再命中黑名单）。
- [x] manifest 四要素齐 + deps 与剥离后实际依赖一致。
- [x] 决策层已剥离（无十字路口/启停线/LAP 状态机符号），决策素材归档有记录。
- [x] EXCEPTION_REGISTRY 已删 pid 条目，删后全库测试仍绿。
- [x] 工单补实施记录 + 验收勾选，Status resolved。

## 实施记录（2026-08-12）

**剥离内容**（双平台决策层全部归骨架，pid.c 2024→155 行 / pid_mspm0.c 367→163 行）：
- stm32（pid.c / gray_track.c / pid_isr.c）：十字路口状态机 + 路由表 + 路径记忆（返程逆转）+ K230 动态路口决策（top2 置信度窗口）+ 远端导航（大T/小T 字路口 + 返程）+ 药房送达/掉头状态机 + 启停斜坡外的决策全局量 + OLED 决策显示（oled_line1..4/oled_dirty）+ datavision_send 调试 + pid_control（~700 行决策主控）+ **pid_isr.c 删除**（TIM3 10ms 调度归骨架：骨架 main.c 自建 TIM3_IRQHandler，读编码器 → line_pid_track → 速度 PID → 限幅输出）；gray_track.c 删 track()/cross_detect/t_cross_detect/ret_t_cross_detect/parking_block_detect（十字路口检测族）；陀螺前馈（GYRO_DAMP_GAIN=0，gz/yaw_gyro/yaw_Kalman 引用）与角度环随剥离移除——ml_mpu6050/digit_uart 依赖出清。
- mspm0（pid_mspm0.c / gray_track_mspm0.c）：LAP 启停线一圈停车状态机（IDLE→LEAVING_START→RUNNING→STOPPING→STOPPED + 消抖/离场冷却）+ 运行计时 + ball_detect_parse 消费 + OLED 显示 + car_started/motor_test_mode + pid_control；gray_track_mspm0.c 删 start_line_detect 及十字路口检测族（26H gray 移植自带的 21F 族决策）；陀螺前馈（gyro_dps_raw 引用）随剥离移除——imu_uart/ball_detect 依赖出清。

**保留驱动 API**（双平台对称，line_pid_track 转公开）：
- `pid_init / pid_cal / pidout_limit`（通用 PID 控制器，位置式/增量式）
- `motor_target_set(spe1, spe2)`（左右轮目标速度 + 轮速校准 + 方向映射，stm32/mspm0 各自映射）
- `line_pid_track()`（PD 巡线输出：灰度偏差 → 死区 → PID → 弯道减速 + 启动斜坡 → 左右轮目标速度；去丢线保持保留）
- `gray_init / digtal / D1..D8 / line_error_calc / all_white_detect`（灰度读取 + 边缘中点偏差 + 全丢线判定）

**manifest**：description 判据四要素重写（能力方向 = PID 闭环控制 + 灰度循迹驱动，无题号/年份）；deps 5→1（`["ball_detect","digit_uart","motor","ml_mpu6050"]` → `["motor"]`——后三者仅被决策层用，剥离后与代码实际引用一致）；stm32 files 删 pid_isr.c；双平台 notes 重写（移植源 provenance + 剥离记录 + 骨架调度说明 + 归档指引）；mspm0 verified 翻 true（本次 gmake 验证）。

**决策素材归档**（.scratch/register_pid_decision.py，add_reference 入库）：
- `21F-巡线送药决策例程`（platform=stm32，锚定 2021F）：原工程 code/pid.c+gray_track.c/h + user/isr.c+main.c——十字路口/路由/K230/远端导航/药房状态机/TIM3 调度全量。
- `26H-滚球巡线决策例程`（platform=mspm0，锚定 2026H；源为 stm32 Keil 工程，描述注明）：原工程 code/pid.c+gray_track.c/h + user/isr.c+main.c——LAP 启停线状态机/计时/K230 球坐标消费/启停线检测全量。
- 备注：26H 条目 platform 按生成线（mspm0）路由，源工程实为 stm32，描述已注明；任一平台生成均可用 --reference-ids 手动选入。

**验证**：
1. **stm32 UV4 0 错 0 警**（21F 巡线线）：generate() 全门禁通过重出 out_2021F_pid_driver（模块集 = motor+pid 轻量套装，deps 展开后不再带 ball_detect/digit_uart/ml_mpu6050），UV4 命令行全量构建——`compiling pid.c... / compiling gray_track.c... / 0 Error(s), 0 Warning(s)`；骨架样例 main_2021F_pid_driver.c（驱动骨架：初始化 + TIM3 10ms ISR 调度线归骨架，决策 TODO 区）随工程编译通过。
2. **mspm0 gmake 0 错**（2026H 滚球线）：重出 out_2026H_pid_driver（模块集 = 26H 小车栈 + pid，无 xunji——本线走 gray_track_mspm0+pid），build_makefiles + gmake 全量重建 0 error(s)，syscfg 层 2 条 UART 采样率建议 = 母版布局固有（历次验证同款）；骨架样例 main_2026H_pid_driver.c（编码器 → line_pid_track → 速度闭环 → limit_duty 输出，决策 TODO 区）随编通过。
3. **mspm0 xunji 连带 0 错**（2024H 巡线套装）：重出 out_2024H_xunji_pid（2024H 套装 + xunji + pid），gmake 0 error(s)——xunji deps→pid 依赖链剥离后仍编译（回归轻量套装，ball_detect/digit_uart 不再连带）。
4. **结构测试绿**：pid 命中词 = 空；EXCEPTION_REGISTRY 删 pid 条目后全量 pytest 1095 绿 + mypy src 干净（tests 8 处 mypy 报错为存量，HEAD 上同款）。
5. **符号残留**：grep 双平台代码文件无 cross_detect/t_cross_detect/ret_t_cross_detect/parking_block_detect/start_line_detect/LAP_/K230/far_nav/route_table/path_memory/pharmacy/pid_control/TIM3_IRQHandler/yaw_*/gyro_dps_raw/oled_line 残留（仅 manifest notes 记录剥离历史，notes 非简介不拦截）。

**注意（留给工单 04）**：pid deps 已移出 ball_detect——工单 04 清理 ball_detect 时不受本工单影响；2024H/21F 全管线不再连带 ball_detect/digit_uart/ml_mpu6050，回归轻量套装。
