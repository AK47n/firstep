# 02 — xunji 剥离决策层（mspm0 巡线驱动瘦身）

**What to build:** xunji 模块瘦身为纯驱动（ADR 0009）：移出全部题逻辑——Control_AB / Control_ABCDA / Control_ACBDA / Control_ACBDAx4 四个模式状态机 + 白区消抖/声光时序 + xunji_tick_50ms / xunji_tick_10ms 调度 + 内部重复实现（PID_A / PID_B / myabs / PWM_Limit）；保留驱动能力——灰度 8 路读取、xunji_centroid 加权质心（普适循迹核心）、编码器采样读服务函数；删除头注释"2024H 巡线题专用层——car xunji 真机工程移植…"整段真机记忆（改写为能力方向说明）；manifest 描述按判据四要素重写（能力方向 = 灰度循迹驱动）。决策逻辑素材保障：car xunji 原生工程已归档参考文件库（car-1-1），骨架生成时 AI 可读到，模块无需自持。**先决依赖：工单 01 的结构测试已立（红证）。**

**Status:** drafted

## 实施（细节实施会话定）

1. xunji.c：删模式状态机 + 双 tick 调度（调度归骨架，骨架 tick 里调 xunji 服务函数）；P1..P8 灰度直读宏封装为读取 API；编码器采样清零归服务函数；PID_A/B 删（manifest deps 加 pid，走 pid 模块）；myabs/PWM_Limit 删（用模块库既有实现或骨架自带）。头注释真机段删除/改写为能力方向 + 硬件映射说明（映射本身是驱动知识，可保留，去"题专用/真机记忆"语感）。
2. xunji.h：接口按保留驱动服务函数收敛。
3. manifest.json：description 判据四要素；deps 更新（加 pid，如有）。
4. 编译验证：2024H 选中 xunji 全管线产物 gmake 0 错；骨架样例（2024H 巡线 main）能编译。

## 文件边界

- library/modules/xunji/code/xunji.c、xunji.h
- library/modules/xunji/manifest.json
- **不动**：huidu / motor / key / imu_uart 模块（依赖保持）；生成链路（skeleton/selection 无代码改动——决策剥离只影响模块内容与 manifest）

## 验收

- [ ] mspm0 gmake 编译 0 错（2024H 选中 xunji 全管线产物）。
- [ ] 结构测试绿（xunji 不再命中黑名单；能力词白名单通过）。
- [ ] manifest 四要素齐（能力方向含"灰度循迹"、无题号/年份/题名）。
- [ ] xunji.c 无状态机/调度符号（无 Control_*、无 tick_* 定义），重复实现（PID/myabs/PWM_Limit）已清。
- [ ] 工单补实施记录 + 验收勾选，Status resolved。
