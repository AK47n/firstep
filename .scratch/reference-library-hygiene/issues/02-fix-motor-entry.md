# 02 — MSPM0_MOTOR参考例程：GBK 源文件补录 + 剥 SDK/胶水负载 + 拆 3 条

**What to build:** 现条目 1630 文件 39MB 名不副实，三处问题：①核心电机源码 motor_crc.{c,h} / motor_read_enc.c / motor_set_speed.{c,h} / user.h / imu.c 共 7 个 GBK 编码文件被 register_materials.py 的 iter_text_files（只试 UTF-8、失败静默跳过）漏录——"电机控制参考例程"条目里没有电机控制实现代码；②source/（1585 个 TI SDK 副本文件 37MB）+ gcc/iar/keil/ticlang 工具链胶水 + keil/Objects 构建产物（.hex/.axf/.map/.uvguix 等）违反 driverlib 批次排除规则（commit 5052b67 明确排除同一批树）；③素材清单.txt 129575 字符排 files 首位，全文回读 4000 字符截断下模型一个代码字符都看不到。修：GBK 转码补录 7 文件、剥垃圾负载（镜像保真 + 清单留痕，不丢数据）、拆 MSP_Motor_Ctrl / m0imu / 移植笔记 3 条。

**Status:** resolved（2026-08-13，验收闭环）

## 验收记录（2026-08-13）

- 修复脚本 `.scratch/fix_mspm0_motor.py`（幂等：旧 id 目录不存在且 3 条新条目俱在即跳过、目标条目已存在即红；前置自检 = 7 个 GBK 文件逐件 gbk 解码通过 + utf-8 直读必失败（与漏录机理一致）+ empty.c 同为 GBK 照读留痕不保；旧条目 1630 文件按「续留 8 / 剥离 1622」完全划分且剥离文件全部仍在镜像（镜像保真对照）+ 剥离面正是核实范围（source 1585 / keil 20 / iar 8 / gcc 3 / ticlang 3 / Event.dot / README.html / 旧素材清单）；7 个 GBK 文件不在旧条目 files 里（补录前提））。新条目走 add_reference 结构校验入库、旧条目走 delete_reference；写库自动提交照常触发（4 条，delete 一条因 git rc=128 瞬态失败改手工计入 squash）。
- GBK 转码补录 7 文件（motor_crc.{c,h} / motor_read_enc.c / motor_set_speed.{c,h} / user.h / m0imu/imu.c）：读镜像 bytes → gbk 解码 → utf-8 写库（\r\n 归一化与库内既有文本一致），转码失败大声报错不静默；empty.c 空模板按 driverlib 先例不保。
- 数据：152→154 条；3 条新 id（MSPM0-Motor_Ctrl-电机控制例程 13 文件 / MSPM0-m0imu-姿态例程 6 文件 / MSPM0-MOTOR-例程移植笔记 1 文件），type=参考例程×2 + 移植笔记，platform=mspm0、anchor=none；素材清单.txt 用 build_material_manifest 对镜像子目录（MSP_Motor_Ctrl / m0imu）重新生成；移植笔记纯文本自持不带清单。旧条目目录已删除（git 历史保留）。
- 简介逐条手写：通读 README.md + 移植.md + 全部电机/IMU 源码——电机例程写清 4 路速度下发（0x10 写多寄存器）+ 闭环设置（0x06 写单寄存器）+ 编码器帧解析（0x0A 从站 + CRC16 + 高低字节拼接）+ SDK 依赖（DriverLib + SysConfig，MFCLK 4MHz）；m0imu 写清数据帧 0A 03 04 格式与配置命令 AA 06 01 01 01 AD 00 + motor_crc 依赖指向；移植笔记写覆盖范围（七节：概览/检查清单/步骤/诊断/排查表/改进/经验总结）。
- 测试 `tests/test_reference_library.py` +5（真库数据不变量）：3 条在 / 旧条不在 + list_references 全库结构校验不抛；逐条文件集/类型/平台/锚定对齐 + files 不含 source/ gcc/ iar/ keil/ ticlang/ 前缀与 Event.dot/README.html；7 个转码文件 utf-8 全文可读且中文标记在（从站地址/存储累计编码器值/用于计算 CRC/设置电机速度/微库/Gyro_ParseFrame）；两份素材清单 == build_material_manifest(镜像子目录) 重生成（写读契约 pin）；read_fulltext 电机例程带 motor_set_speed.c / motor_read_enc.c 正文（Motor_Set_ClosedLoop / Modbus_ParseFrame / 中文注释在）。
- **pytest 1269 全绿**（基线 1264 + 新增 5，无回归）；**mypy src 干净**（36 文件，src 零改动）。
- 真机验证：8000 服务（用户启动器在跑）curl /api/references 浏览全库 154 条不抛、3 条新条目俱在；逐文件 HTTP 回读 motor_set_speed.c（1734 字符，从站地址可见）/ motor_read_enc.c（3830）/ imu.c（2973）/ 移植.md（12813）俱过；旧条目 files 路由 400（ReferenceError→400 既有契约，条目已删）。
- 边界遵守：未碰 sources/materials 镜像（保真件只读）、src/、其他条目、register_materials.py（历史一次性脚本不修，同 zigbee 先例）。

## 现状（已核实 2026-08-13）

- GBK 跳过清单（镜像 sources/materials/MSPM0_MOTOR参考例程 实有、参考库缺失）：MSP_Motor_Ctrl/motor_crc.c(3688B) motor_crc.h motor_read_enc.c(4173B) motor_set_speed.c(1830B) motor_set_speed.h user.h、m0imu/imu.c(3031B)、empty.c(3879B)；UTF-8 已入库的仅 MSP_Motor_Ctrl/motor_read_enc.h + user.c(196B)、m0imu/imu.h(217B)
- 负载明细：source/ 37MB 1585 文件（ti/driverlib dl_*.c/h 61 个 + devices/third_party 等）；keil/ 786KB（.map 207KB、.uvguix 188KB×2、Objects 构建产物）；iar 77KB / gcc 16KB / ticlang 12KB；Event.dot、README.html（README.md 重复）
- 值得保留：MSP_Motor_Ctrl（8 文件）、m0imu（2 文件）、移植.md（18.6KB 移植笔记）、README.md、empty.syscfg、ti_msp_dl_config.{c,h}
- 镜像完整保真（39MB 全量，含 keil/uvprojx 等，素材清单 1729 行全留痕）；git 已追踪 1617 文件（删除后历史仍背 37MB，接受不做历史重写）
- 参考库总重 49.8MB，此条目 source/ 独占 37MB ≈ 76%
- src/ 与 tests/ 无对该条目 id 的硬引用（grep 已验）——纯数据改动

## 实施

1. 写 `.scratch/fix_mspm0_motor.py`（幂等：skip-on-exist + 自检）：
   - GBK→UTF-8 转码 7 文件（empty.c 除外——空模板按 driverlib 先例不保）：读镜像文件 bytes → gbk 解码 → utf-8 写入库；转码失败大声报错，不静默
   - 3 条新条目（add_reference 入库，platform=mspm0，anchor=none）：
     - 「MSPM0 Motor_Ctrl 电机控制例程」（type=参考例程）：MSP_Motor_Ctrl 8 文件 + ti_msp_dl_config.{c,h} + empty.syscfg + README.md + 素材清单.txt
     - 「MSPM0 m0imu 姿态例程」（type=参考例程）：m0imu/imu.{c,h} + ti_msp_dl_config.{c,h} + empty.syscfg + 素材清单.txt
     - 「MSPM0 MOTOR 例程移植笔记」（type=移植笔记）：移植.md（纯文本自持，不带素材清单）
   - 素材清单.txt：build_material_manifest 对镜像对应子目录重新生成（MSP_Motor_Ctrl、m0imu 各自）
   - 简介：通读 README.md + 移植.md 逐条写（电机例程做什么/文件构成/SDK 依赖；m0imu 同理；移植笔记写覆盖范围）
   - delete_reference 删旧条目
2. 测试：tests/test_reference_library.py 加不变量（3 条存在、旧 id 不存在、7 个转码文件 utf-8 可读、各条 files 不含 source/ gcc/ iar/ keil/ ticlang/ 路径）；list_references 全库结构校验不抛
3. 真机验证：/api/references 浏览 3 条 + 回读「电机控制例程」全文，确认 motor_set_speed.c 正文可见（不再只有清单头）

## 验收

- pytest 全绿 + mypy src 干净（src 零改动）
- 3 条新条目健康（结构校验过、简介与代码一致）；旧条目删除
- 全文回读电机例程：motor_set_speed.c / motor_read_enc.c 正文可见
- 数据不丢：7 个 GBK 文件转码入库；剥离负载在镜像 + 旧清单留痕（脚本打印对照）

## 文件边界

`library/references/MSPM0_MOTOR参考例程/`（修复后删除）、`.scratch/fix_mspm0_motor.py`（新增）、`tests/test_reference_library.py`（新增用例）

**明确不动的：** sources/materials 镜像（保真件）、src/、其他条目、register_materials.py（历史一次性脚本不修，同 zigbee 先例）。
