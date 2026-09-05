# 02 — syn6288 语音合成播报模块（软 UART 单发 TX，手册 control--syn6288-speech-synthesis-broadcast-module.md）

**要做什么：** 模块库新增 `syn6288` 条目（仅 mspm0）：从手册提炼 SYN6288E 文本转语音驱动为纯驱动切片——**软 UART 单发 TX**（9600 8N1，位操作，不开 UART 外设、不占 TIMER）：`syn6288_init()` + `syn6288_speak(text)`（文本→合成播报，帧 = 0xFD+长度+命令字+参数+文本+异或校验，按页面原样）+ `syn6288_stop/pause/resume` + 底层 `syn6288_send_cmd`；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 01 jq8900 同软 UART 先例，互相独立）。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。软 UART 单发 TX（同 jq8900 先例）；帧封装按页面原样（0xFD+长度+命令+参数+文本+异或校验，sprintf 去 stdio）；默认 PB20（与 DC_MOTOR 编码器 BB 重叠且与 jq8900 PB19 刻意错开）；单选生成 → gmake 0 error / 0 warning（PASS）。未上板。

- [x] 代码提炼：`code/syn6288.c/h`（软 UART 位操作 + 帧封装原样 + speak/stop/pause/resume；IRQHandler/RX 缓冲裁剪并 notes 说明）
- [x] 母版 `mspm0.syscfg`：SYN6288 GPIO 实例（TX 输出初始 SET，默认 PB20）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"SYN6288": ("syn6288",)`
- [x] `manifest.json`：dependencies ["delay"]；pins TX=gpio_out PB20；notes 含帧格式/软 UART 决策依据；verified=true 回写
- [x] wordlist.json「语音模块」类加 SYN6288 方案（lib_modules 挂接）
- [x] 测试：test_pins 映射 / test_pin_bindings PB20 1→2 / test_syscfg_prune 断言 / 新增 test_module_syn6288.py（软 UART 时序纯函数 + 帧格式镜像 + 源码守卫）——全部通过
- [x] 编译验证：run_syn6288_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）；verified=true + notes 记录；中文提交
