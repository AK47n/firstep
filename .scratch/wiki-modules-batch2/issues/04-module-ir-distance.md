# 04 — ir_distance 模块（GP2Y0A02 红外测距传感器，手册 sensor--Infrared-distance-sensor.md）

**要做什么：** 模块库新增 `ir_distance` 条目（仅 mspm0）：从手册提炼完整"ADC 电压→距离"驱动为纯驱动切片——`ir_distance_init()` + `ir_distance_read_distance_cm()`（float 出 cm；10 次快速平均；V=raw/4095×3.3；GP2Y0A02YK0F 换算 60.374×V^(−1.16)）；通道策略同 us016：MEM0 已被 us016 薄封装占用 → **sequence 加第 4 通道 MEM3（endAdd 2→3）**并同步 joystick 相关测试断言；选中后生成工程打开即可编译。

**被谁阻塞：** 无——可立即开始（母版 syscfg 改序列通道影响面最大，置于第 04 件实施并跑相关全量测试）。

**状态：** resolved

**结论：** 2026-09-05 完成。通道策略落地：us016 已占 MEM0 槽位 → 本件走独立通道 MEM3——母版 syscfg ADC12_0 sequence 加第 4 通道（endAdd 2→3、adcMem3chansel=CHAN_0、adcPin0=PA27 手册原脚；SysConfig CLI 校验通过）；默认 PA27 与 HUIDU R2 重叠（红外测距与 8 路灰度巡线同选概率最低），同选经引脚绑定消解；轮询读 MEM3（10 次平均、IRQHandler 强符号唯一）；换算 60.374×V^(-1.16)（GP2Y0A02YK0F 官方公式）+ 全 0 采样防护（防 pow 溢出）。joystick 相关断言同步：test_shared_groups 纯灰度 PA27 组恢复测试（ir_distance 绑走恢复）+ test_module_joystick/docstring 四通道共享事实。单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）；未上板。

- [x] 通道决策：us016 已按薄封装占 MEM0（同一槽位两个角色同选经绑定无法消解——binding 槽位冲突检查强制同脚）→ ir_distance 走独立通道：母版 syscfg `ADC12_0.endAdd` 2→3 + `adcMem3chansel="DL_ADC12_INPUT_CHAN_0"` + `adcPin0.$assign="PA27"`（**手册原脚**，A0_0 槽位——SysConfig CLI 实证命名 adcPin<N>=通道号、adcMem<N>chansel 对 MEM 索引，seq-mem0-1-2 先例）；**同步 joystick 相关测试断言**：核查 test_module_joystick / test_pin_bindings 的共享事实注释（无 endAdd 断言需改；PA27 刻意表 1→2 新条目）
- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--Infrared-distance-sensor.md` 「代码块」章节抽完整 `bsp_IRdistance.c/h` → 改造为 `code/ir_distance.c` + `code/ir_distance.h`：去 main/printf、函数名规范化（`ir_distance_init/read_distance_cm`）、ADC 中断（IRQHandler + gCheckADC 标志位）改轮询（照 joystick 直接读 ADC12_0 MEM3，`DL_ADC12_getStatus` 忙等——IRQHandler 强符号唯一性）；`dependencies: []`（无 delay 需求；math.h pow 为标准库）
- [x] 换算：V = raw/4095×3.3V（VREF 宏 IR_DIST_VREF_V）；Distance = 60.374×pow(V,−1.16)（GP2Y0A02YK0F 官方公式 20-150cm；10 次采样平均保留手册值）；<15cm 非线性区随手册警告注释
- [x] 默认脚：PA27（手册原脚）——与 HUIDU R2 重叠（红外测距与 8 路灰度巡线同选概率最低）；重叠对登记 `test_pin_bindings` 刻意表（PA27 1→2）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：`"ADC12_0": ("adc", "joystick", "us016", "ir_distance")`（第 02 件已加 us016，此件补 ir_distance）
- [x] `manifest.json`：`dependencies: []`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录）；pins：IR_DIST_OUT_CH3 = adc（default PA27，尾 `_CH3` 推导 MEM3）；简介判据：能力方向（红外测距/避障/近距离传感）+ 无题绑定
- [x] wordlist.json 补录：「感知传感器」加「红外测距传感器（GP2Y0A02YK0F）」方案挂 `lib_modules: ["ir_distance"]`（models 已有"红外传感器"覆盖，不重复加）
- [x] 测试：新增 `tests/test_module_ir_distance.py`（manifest 结构：dependencies 空、单角色 adc PA27；母版 syscfg 断言：endAdd=3 / adcMem3chansel=CHAN_0 / adcPin0=PA27 且 sequence 共享 4 通道；单选生成 → syscfg 保留 ADC12_0 + 文件落盘 + main.c 调 init/read 过静态门禁）；`test_pin_bindings.py` PA27 刻意表；`test_syscfg_prune.py` 增 ADC12_0 由 ir_distance 保留断言
- [x] 编译验证：复制 `run_joystick_matrix.py` 改 slug 为 ir_distance → SysConfig CLI 校验 → gmake 真编译 0 error、模块自身 warning 0；结果回写 manifest verified=true + notes 记录；code-review 后中文提交


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
