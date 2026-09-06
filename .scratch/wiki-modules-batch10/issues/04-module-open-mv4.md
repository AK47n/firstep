# 04 — open_mv4 主控侧 UART 帧解析（真实 UART 轮询，手册 rf--open-mv4-camera.md）

**要做什么：** 模块库新增 `open_mv4` 条目（仅 mspm0）：从手册提炼主控侧 UART 帧解析驱动为纯驱动切片——真实 UART 独立实例 `OPENMV4_UART`（照 fingerprint「裁剪后独占」先例：默认挂 UART1（页面原接线 PA8/PA9 附加串口 1，与 DIGIT_UART 同外设同脚——OpenMV4 与 K230 视觉互替、同选概率最低）、9600（页面案例）、enabledInterrupts=[] **轮询接收**——无 IRQHandler 强符号）、帧格式 `[%d,%d]`/`[%d]`（页面案例一/二；页内 Python 块只作参考素材不落码）；`open_mv4_init()` + `open_mv4_flush()` + `open_mv4_read_frame(&cx,&cy,&confidence)`（中心坐标/置信度出参，与 coord_detect 出参形态对齐）；UART 放置决策依批次 4 fingerprint 实证（实例上限 4/同外设多实例拒绝/裁剪后独占）取证选方案 ①，现实约束与 ③不并 coord_detect 的理由记 notes；选中后生成工程打开即可编译、可调用。

**被谁阻塞：** 无——可立即开始（与 01/02/03 独立；UART 决策依据已取批次 4/01-04 结论）。

**状态：** resolved

**结论：** 2026-09-11 完成并提交。UART 放置决策按用户决策树落定方案 ①（真实 UART 独立实例照 fingerprint「裁剪后独占」先例——读批次 4/01-04 结论取证：同外设多实例 Resource conflict、实例上限 4=外设数、母版 UART0-3 全被实例占）；默认挂 UART1（页面原接线 PA8/PA9——与 DIGIT_UART 同外设同脚：OpenMV4 与 K230 视觉互替、同选概率最低，同选时经引脚绑定换实例/换脚消解，单选裁剪后独占）；9600、enabledInterrupts=[] 轮询接收（无 ISR 强符号——指纹先例）；帧解析 `[cx,cy]`/`[pos]`（页面案例一/二：`Maximum color block position : [12,34]\r\n` 前缀自动跳过、单值帧 cy=0 占位、坏帧/三整数/带空格帧丢弃——页面格式无空格原样）；**补页面缺失的数值解析**（页面只找 '[' ']' 并 printf 子串未提取整数）；置信度恒 1.0（页面帧无置信度字段）+ 出参形态与 coord_detect 对齐；**③不并 coord_detect 理由**（K230 CSV 行帧 115200+置信度 vs 方括号帧 9600 无置信度——双格式分支/波特率冲突/契约漂移风险，独立并 notes 写明差异；②软 UART RX 无先例工作量最大不开）；现实约束记录（UART 实例上限 4——open_mv4 与 3 件 UART 模块同选在限内、4 件以上 CLI 拒绝）；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；词表视觉模块 OpenMV 方案补 lib_modules。未上板（帧解析真机留验证）。code-review（随批次 10 收尾两轴评审）。

- [x] 代码提炼：手册「代码块」抽 `bsp_openmv4.c/h` 主控侧 → `code/open_mv4.c` + `code/open_mv4.h`：去 main/printf/HardFault_Handler、`OpenMV4_usart_config`（NVIC 使能）随轮询裁剪、`Openmv4DataAnalysis` 改为按行分帧 + '['、']' 查找 + **数值解析**（页面只找头尾未提取整数）、`UART_1_INST_IRQHandler` 随轮询裁剪（FIFO 轮询排空）；页内 Python 块（OpenMV4 代码）不落码——帧格式参考素材
- [x] 母版 `mspm0.syscfg`：新 UART 实例 `OPENMV4_UART`（$assign=UART1、targetBaudRate=9600、enabledInterrupts=[]、TX=PA8/RX=PA9——页面原脚；UART 实例上限 4 现实约束注释、与 DIGIT_UART 同外设同脚（互替低同选）注释）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"OPENMV4_UART": ("open_mv4",)` + 顶部注释补 OPENMV4_UART/实例上限说明
- [x] `manifest.json`：dependencies []；mspm0 平台条目；pins OPENMV4_UART_TX/RX（uart_tx/uart_rx，default PA8/PA9）；kit+source_url；notes 含手册路径+原页+网盘链接+改造要点+UART 放置决策（指纹实证结论引述/实例上限 4/裁剪后独占/方案 ②③ 取舍）+帧格式差异（vs coord_detect K230 CSV：方括号 vs 逗号+字母头、无置信度、9600 vs 115200）+置信度恒 1.0 说明+`[%d]` 单值帧处理+案例三/四/五（矩形角点/激光）范围外——verified 转 true
- [x] wordlist.json：「视觉模块」OpenMV Cam H7 方案补 `lib_modules: ["open_mv4"]` + note/interface 更新（已打通）
- [x] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增 2 行；`test_pin_bindings.py` 刻意表 PA8/PA9 + UART1 行；`test_syscfg_prune.py` 增 OPENMV4_UART 断言；新增 `tests/test_module_open_mv4.py`：manifest 结构 + 单选生成 + **帧解析纯函数单测**（伪帧序列 → 坐标结果：`[123,456]` / `Maximum color block position : [12,34]\r\n` / `[-12]`（cx=-12,cy=0）/ 坏帧 `[abc`/`]` 缺失/`[1,2,3]`/`[5, 6]`/空行 → 不解析）+ 源码守卫（9600/OPENMV4_UART_INST/isRXFIFOEmpty 轮询/无 IRQHandler/NVIC 裁剪/confidence 1.0f）
- [x] 编译验证：`run_open_mv4_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error/0 warning；回写 verified=true + notes
