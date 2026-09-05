# 03 — rc522 RFID IC 卡识别模块（软 SPI，手册 rf--rc522-rf-ic-card-identification-module.md）

**要做什么：** 模块库新增 `rc522` 条目（仅 mspm0）：从手册提炼 MFRC522 读卡驱动为纯驱动切片——软 SPI 位操作（**5 脚** CS/RST/SCK/MOSI/MISO，单 PORT 宏，照 nrf24l01 先例，不占硬件 SPI 外设）：`rc522_init()` + `rc522_read_card(uid)`（四字节卡号）+ 认证/读块/写块服务函数（按需裁剪）+ 页面 `PcdComMF522/PcdRequest/PcdAnticoll/PcdSelect/PcdAuthState/PcdWrite/PcdRead/CalulateCRC` 全套保留在驱动内；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。软 SPI 位操作 5 脚（CS/RST/SCK/MOSI/MISO 单 GPIOA 端口，nrf24l01 先例）；Pcd* 全家保留在驱动内 + 服务函数 read_card/auth/read_block/write_block/halt；上游缺陷修正（PcdAuthState UID 复制 6→4 字节）并 notes 记录；默认 PA7/PA18/PA14/PA16/PA17（与车类同选概率最低，且与同批语音/指纹默认不撞）；单选生成 → gmake 0 error / 0 warning（PASS）。未上板。

- [x] 代码提炼：`code/rc522.c/h`（软 SPI 原语 + 寄存器族 + Pcd* 静态内部 + 服务函数；上游缺陷修正 + 拼写保留记录）
- [x] 母版 `mspm0.syscfg`：RC522 GPIO 实例（5 associatedPins 全 GPIOA 单口）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"RC522": ("rc522",)`
- [x] `manifest.json`：dependencies ["delay"]；pins 五角色；notes 含缺陷记录/5 脚说明；verified=true 回写
- [x] wordlist.json「无线通信模块」类加 RC522 方案（lib_modules 挂接）
- [x] 测试：test_pins 五脚映射 / test_pin_bindings PA7/PA18/PA14/PA16/PA17 计数 / test_syscfg_prune 断言 / 新增 test_module_rc522.py（含上游缺陷修正源码守卫）——全部通过
- [x] 编译验证：run_rc522_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）；verified=true + notes 记录；中文提交
