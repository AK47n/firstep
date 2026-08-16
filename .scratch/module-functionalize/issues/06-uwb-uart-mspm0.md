# 06 — uwb_uart 补 mspm0（UART2 协议驱动 + config mspm0）

**What to build:** uwb_uart 新增 mspm0 版（UWB_UART/UART2、PA23(TX)/PA24(RX)、115200、RX 中断）：帧同步 + XOR 校验 + 大小端解析 + 滑动滤波，API 与 stm32 版同名同形（uwb_uart_init/uwb_rx_handler/uwb_filter_reset/uwb_get_frame_rate）。先决：config 模块补 mspm0 头（波特率/滤波参数，UWB 依赖 config 否则 mspm0 依赖展开 missing）；母版 syscfg 增 UWB_UART 实例；syscfg 实例映射增 uwb_uart 消费。

**Blocked by:** 05

**Status:** resolved（2026-08-15）

- [x] `code/uwb_uart_mspm0.c/h`：DL_UART 字节级帧状态机（与 stm32 同帧格式/滤波逻辑），模块内定义 UWB_UART_INST_IRQHandler
- [x] config 模块补 mspm0 平台条目（code/config_mspm0.h：UWB_BAUD/ZIGBEE_BAUD/滤波参数）
- [x] 母版 mspm0.syscfg 增 UWB_UART（UART2, PA23 TX / PA24 RX）；syscfg_instances 映射补 ("UWB_UART", ("uwb_uart",))
- [x] uwb_uart manifest 补 mspm0 条目：files/pins（UWB_UART_TX/RX）/notes/kit/source_url
- [x] 测试：UWB API 双平台同形 + pins/syscfg 一致 + 裁剪映射
- [x] 真机 mspm0 gmake 0 错（uwb_uart + config/filter）
- [x] pytest 全绿 + mypy src 干净


## Comments

- 实例选择：UART2 唯一排针 TX = PA23；RX 选 PA24（相邻，备选 PA22/PB18 留给 HUIDU/DC_MOTOR 默认布局冲突更小）。2026C 套装不选 HUIDU，默认可编译。
- 顺带修产品缺陷：mspm0 gmake include 串只收「有 .c 的模块目录」，header-only 依赖（config）不在 -I——`render_makefile_set/write_makefile_set` 增 `extra_include_dirs` 参数（generator 传 `_copy_module_files` 返回的 include_dirs），测试 `test_header_only_module_include_dirs_enter_compile_flags` 钉死。
- 真机验收：`python .scratch/module-functionalize/verify_protocol_mspm0.py uwb` → gmake exit=0，0 error / 1 warning（基线警告）；日志 `.scratch/module-functionalize/out_uwb_mspm0/gmake_build.log`。SYSCFG_DL_init 按门禁契约注释，上板取消注释。