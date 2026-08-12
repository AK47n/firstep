# 04 — ball_detect 伪题专用清理

**What to build:** ball_detect 已是驱动形态（K230 视觉串口帧解析 → BallResult 结构），题绑定主要在描述（"2026H 滚球题"）与命名语感。清理为四要素达标：manifest 描述重写（能力方向 = K230 视觉帧解析 / 球体检测，去题号年份绑定）；检查代码内题绑定（题号/年份注释、专用常量、启停/门限等逻辑——若有则按 ADR 0009 移出）；命名评估（slug 保留 = 能力方向词；BallResult 等符号名评估是否通用化——**若改名必须同步 pid 模块 deps 引用，与工单 03 协调，避免两边各改一半**）。**先决依赖：工单 01 已闭环（结构测试 + EXCEPTION_REGISTRY 例外注册表已立）——本工单清理 ball_detect 后必须删除注册表对应条目（不删 = 存量校验红）。**

**Status:** resolved

## 实施记录（2026-08-12）

**代码检查**：ball_detect 双平台 4 个文件本为纯驱动——UART 环形缓冲 + CSV 坐标帧解析 + BallResult 输出，无题号/年份注释、无专用常量、无启停/门限/状态机逻辑（LOST_THRESHOLD 等在源工程 main.c 骨架侧，模块内无）；注释里"钢珠"为检测对象描述非题绑定。代码层无需改动。

**manifest**：description 按四要素重写——能力方向 = K230 视觉帧解析/球体检测（"K230 视觉帧解析驱动：UART 接收环形缓冲 + CSV 坐标帧解析（B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2> / N 无检测），输出 BallResult 球体检测结果（中心坐标/置信度/边界框/丢失帧计数）；适用于视觉检测类赛题功能，检测结果的决策消费归生成骨架"），去 2026H 题号年份绑定；notes 保留移植源 provenance（与 03 pid 同款，notes 非简介不拦截）。

**命名决定：不改**——slug `ball_detect` / 符号 `BallResult` / `ball_detect_*` 已是能力方向词；`钢珠`注释为检测对象描述非题名；且 pid 模块 deps 已由工单 03 移出 ball_detect（`["motor"]`），无跨模块引用需同步，与 03 零协调负担。改名收益（更普适的球体语义）不抵跨模块改名成本，维持现状。

**EXCEPTION_REGISTRY**：tests/test_module_universality.py 删除 ball_detect 条目（工单 01 注册表防漏同步机制生效），docstring 补"已清理移除"记录。

**验证**：
1. **stm32 UV4 0 错**：重出 out_ball_detect_stm32（模块集 = [ball_detect] 轻量套装 + main_stm32_ball_detect.c 驱动骨架：ball_detect_init/flush/parse + USART1_IRQHandler 挂 ball_detect_rx_handler），产物门禁通过，UV4 命令行全量构建 0 Error(s)。
2. **mspm0 gmake 0 错**：重出 out_ball_detect_mspm0（模块集 = [ball_detect] + main_mspm0_ball_detect.c 驱动骨架：ball_detect_init/parse + UART1_IRQHandler 挂 ball_detect_rx_handler；DIGIT_UART 走母版 syscfg 现有实例 UART1/PA8/PA9/115200/RX 中断），产物门禁通过，build_makefiles + gmake 全量重建 0 error(s)——2 条 warning 为母版布局固有 UART 采样率建议（IMU601/DIGIT_UART，历次验证同款）。
3. **结构测试绿**：ball_detect 命中词 = 空（description + 4 代码文件全零）；注册表删条目后全量 pytest 1095 绿 + mypy src 干净。
4. **回归**：注册表其他条目（lock_control/zone/config/debug_uart/zigbee_uart/zigbee_uart_key/filter/uwb_uart）仍在、各自命中保持，未误删。

**命名决定有记录**：见上文"命名决定：不改"。

## 验收

- [x] 双平台编译 0 错（stm32 + mspm0 各一产物线）。
- [x] 结构测试绿（ball_detect 不再命中黑名单）。
- [x] manifest 四要素齐（无题号/年份/题名）。
- [x] 命名决定有记录（不改 / 改 + 与 03 同步记录）。
- [x] EXCEPTION_REGISTRY 已删 ball_detect 条目，删后全库测试仍绿。
- [x] 工单补实施记录 + 验收勾选，Status resolved。
