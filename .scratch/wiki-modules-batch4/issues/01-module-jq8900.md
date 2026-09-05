# 01 — jq8900 语音播报模块（软 UART 单发 TX，手册 control--jq8900-voice-broadcast-module.md）

**要做什么：** 模块库新增 `jq8900` 条目（仅 mspm0）：从手册提炼 JQ8900 两线串口播报驱动为纯驱动切片——**软 UART 单发 TX**（GPIO 位操作 9600 8N1，~104us/bit，不开 UART 外设、不占 TIMER）：`jq8900_init()` + 指令帧服务函数 `jq8900_play(index)/play_next/play_prev/stop/pause/resume/set_volume/volume_up/volume_down` + 底层 `jq8900_send_cmd(cmd, data)`（帧 = 0xAA+cmd+data+校验和）；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（本件是软 UART 新先例打样）。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。UART 可行性调研实证（spec 实现决策）：SysConfig CLI 拒绝同外设多 UART 实例（UART2 Resource conflict + 实例上限 4）——HC05「共享」仅有单选编译实证（裁剪后独占）；JQ8900 走软 UART 单发 TX（GPIO 位操作 9600 8N1，新先例）；默认 PB19（与 DC_MOTOR 编码器 BA 重叠）；单选生成 → gmake 0 error / 0 warning（PASS）。未上板（软 UART 时序/命令字真机留验证）。

- [x] 代码提炼：`code/jq8900.c/h`（软 UART 位操作 + 0xAA+cmd+data+校验和帧 + 命令服务函数；页面 IRQHandler/SendData 一线串行裁剪并 notes 说明）
- [x] 母版 `mspm0.syscfg`：JQ8900 GPIO 实例（TX 输出初始 SET，默认 PB19）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"JQ8900": ("jq8900",)`
- [x] `manifest.json`：dependencies ["delay"]；pins TX=gpio_out PB19；notes 含 UART 决策依据/命令字说明；verified=true 回写
- [x] wordlist.json 新「语音模块」类加 JQ8900 方案（lib_modules 挂接）
- [x] 测试：test_pins 映射 / test_pin_bindings PB19 1→2 / test_syscfg_prune 断言 / 新增 test_module_jq8900.py（含软 UART 时序纯函数单测 + 帧格式镜像 + 源码守卫）——全部通过
- [x] 编译验证：run_jq8900_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）；verified=true + notes 记录；中文提交
