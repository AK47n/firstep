# 02 — xunji 剥离决策层（mspm0 巡线驱动瘦身）

**What to build:** xunji 模块瘦身为纯驱动（ADR 0009）：移出全部题逻辑——Control_AB / Control_ABCDA / Control_ACBDA / Control_ACBDAx4 四个模式状态机 + 白区消抖/声光时序 + xunji_tick_50ms / xunji_tick_10ms 调度 + 内部重复实现（PID_A / PID_B / myabs / PWM_Limit）；保留驱动能力——灰度 8 路读取、xunji_centroid 加权质心（普适循迹核心）、编码器采样读服务函数；删除头注释"2024H 巡线题专用层——car xunji 真机工程移植…"整段真机记忆（改写为能力方向说明）；manifest 描述按判据四要素重写（能力方向 = 灰度循迹驱动）。决策逻辑素材保障：car xunji 原生工程已归档参考文件库（car-1-1），骨架生成时 AI 可读到，模块无需自持。**先决依赖：工单 01 已闭环（结构测试 + EXCEPTION_REGISTRY 例外注册表已立，红证已验）——本工单清理 xunji 后必须删除注册表对应条目（不删 = 存量校验红，工单 01 实施记录定案）。**

**Status:** resolved（2026-08-12 实施闭环，1095 绿 + mypy 干净 + gmake 0 错，见下方实施记录）

## 实施（细节实施会话定）

1. xunji.c：删模式状态机 + 双 tick 调度（调度归骨架，骨架 tick 里调 xunji 服务函数）；P1..P8 灰度直读宏封装为读取 API；编码器采样清零归服务函数；PID_A/B 删（manifest deps 加 pid，走 pid 模块）；myabs/PWM_Limit 删（用模块库既有实现或骨架自带）。头注释真机段删除/改写为能力方向 + 硬件映射说明（映射本身是驱动知识，可保留，去"题专用/真机记忆"语感）。
2. xunji.h：接口按保留驱动服务函数收敛。
3. manifest.json：description 判据四要素；deps 更新（加 pid，如有）。
4. 编译验证：2024H 选中 xunji 全管线产物 gmake 0 错；骨架样例（2024H 巡线 main）能编译。
5. 结构测试 EXCEPTION_REGISTRY（tests/test_module_universality.py）删除 xunji 条目——工单 01 定案：清理后不删条目 = 存量校验红，防漏同步。

## 文件边界

- library/modules/xunji/code/xunji.c、xunji.h
- library/modules/xunji/manifest.json
- **不动**：huidu / motor / key / imu_uart 模块（依赖保持）；生成链路（skeleton/selection 无代码改动——决策剥离只影响模块内容与 manifest）

## 验收

- [x] mspm0 gmake 编译 0 错（2024H 选中 xunji 全管线产物）。
- [x] 结构测试绿（xunji 不再命中黑名单；能力词白名单通过）。
- [x] manifest 四要素齐（能力方向含"灰度循迹"、无题号/年份/题名）。
- [x] xunji.c 无状态机/调度符号（无 Control_*、无 tick_* 定义），重复实现（PID/myabs/PWM_Limit）已清。
- [x] EXCEPTION_REGISTRY 已删 xunji 条目，删后全库测试仍绿（无新污染）。
- [x] 工单补实施记录 + 验收勾选，Status resolved。

## 实施记录（2026-08-12）

**剥离内容**（xunji.c 删 ~420 行，469 行 → 103 行）：
- 四个模式状态机 Control_AB / Control_ABCDA / Control_ACBDA / Control_ACBDAx4（含陀螺仪掉头偏角 Yaw 消费——imu_uart extern 删除）
- 调度 xunji_tick_50ms / xunji_tick_10ms（白区消抖 + LED 时序；编码器采样清零已内化为服务函数）
- 状态机全局量（flag/n/whiteflag*/timebegin*/timenum*/led* 族/m/a/pwmstart/error）+ 声光 LED 宏
- 重复实现 PID_A / PID_B / myabs / PWM_Limit（速度环走 pid 模块）

**保留驱动 API**（xunji.h 收敛为 5 个服务函数）：
- `xunji_init()`（无内部状态，只读服务）
- `xunji_read_gray()`（灰度 8 路位图 bit0=P1…bit7=P8，1=白区；P1..P8 直读宏内化为模块私有，映射注释保留）
- `xunji_centroid(float gain)`（加权质心巡线核心，逐字保留原算法）
- `xunji_encoder_read(int32_t *left, int32_t *right)`（key 模块 counter 采样读，读后清零）
- `xunji_set_speed(int left, int right)`（百分比制 → motor 原始占空比 0~1300，方向 0停1正转2反转）

头注释真机段（"2024H 巡线题专用层——car xunji 真机工程移植"）已改写为能力方向 + 硬件映射说明（映射本身是驱动知识，保留，去题绑定/真机记忆语感）。

**manifest**：description 判据四要素重写（能力方向 = 灰度循迹驱动）；deps `["motor"]` → `["motor", "pid"]`；notes 去状态机/题问答描述（保留移植源 provenance、硬件映射、编译验证状态；决策素材归档记录 car-1-1 注明）。

**验证**：
1. **gmake 编译 0 错**：generate() 全门禁通过重出 2024H mspm0 产物（.scratch/real-run/out_2024H_xunji_v2，模块集 = 2024H 套装 + pid 及其当前 deps），build_makefiles.py + gmake 全量重建——编译器 0 错 0 警，链接产出 mspm0_project.out（syscfg 层 2 条 UART 采样率建议 = 母版布局固有，历次验证同款）；骨架样例 main（.scratch/real-run/main_2024H_xunji_driver.c：初始化序列 + 主循环灰度→质心→PID 速度环→set_speed，决策 TODO 区）随工程编译通过。
2. **结构测试绿**：xunji 命中词 = 空（`[]`）；grep 验证无 Control_*/tick_*/PID_*/myabs/PWM_Limit/Yaw/LED_ON 残留。
3. **全量 pytest 1095 绿 + mypy 干净**（EXCEPTION_REGISTRY 删 xunji 条目后无新污染）。

**注意（留给工单 03）**：xunji deps 加 pid 后，2024H 全管线（推荐 deps 展开）会连带 pid 当前声明的多余 deps ball_detect/digit_uart/ml_mpu6050（26H 滚球决策层残留）——本工单验证已实测连带编译 0 错；工单 03 剥离 pid 决策层、移出该三依赖后 2024H 工程回归轻量套装。
