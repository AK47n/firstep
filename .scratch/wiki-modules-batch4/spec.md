# 批次 4「语音/身份」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1「遥控/通信」四件（joystick/hc05/nrf24l01/ir_remote）、批次 2「传感器常用」四件（dht11/us016/bh1750/ir_distance）、批次 3「显示/执行」三件（max7219/pca9685/ir_remote_tx）已入库。`lckfb-地猛星移植手册/` 剩余页中**语音/身份**两类：语音播报（JQ8900）、语音合成（SYN6288）、RFID 读卡（RC522）、指纹识别（AS608）四篇页内自带完整驱动源码（v7 审计自包含），模块库仍无对应条目——用户做门禁/身份/语音提示类题（刷卡开门、指纹考勤、语音播报状态）时 AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 4 = **语音/身份**四件——JQ8900 语音播报、SYN6288 语音合成、RC522 IC 卡识别、AS608 指纹识别——全部页内源码完整（v7 全自洽）、无需网盘。

## 方案

照批次 1/2/3 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机——录入/比对等流程控制归生成骨架）→ 母版 syscfg 新实例 + `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies/pins/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点+UART 决策依据）→ wordlist.json 补录（语音挂新「语音模块」类、RC522 挂「无线通信模块」、指纹挂「感知传感器」）→ 测试 → 编译矩阵（复制 run_max7219_matrix.py 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified=true 回写 → 中文提交 → 逐件 code-review。

## 用户故事

1. 作为做题用户，我选中 `jq8900`/`syn6288`/`rc522`/`fingerprint` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数（播报/合成播报/读卡号/指纹录入比对删库）。
2. 作为做题用户，我做门禁考勤（刷卡+指纹+语音播报）、语音提示（状态播报/欢迎语）、身份验证（卡号/指纹 ID 判定）时，不用再读器件手册、不用自写 9600 位时序/ISO14443 协议/AS608 帧协议。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录/UART 决策依据），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研，批次 1/2/3 已实证）

① 母版 `ADC12_0` 已是 sequence 四通道（endAdd=3：MEM0=adc / MEM1-2=joystick / MEM3=ir_distance），本批不新增 ADC 件；② 地猛星 2×20 排针 31 个 IO 全被默认布局占用——新模块默认脚按「同选概率最低者与既有默认重叠」，同选经引脚绑定消解；③ 母版 GPIO 中断全走 GROUP1 一个向量且被 KEY/motor 编码器消费——本批全部**轮询/忙等**，不注册 GPIO 中断；④ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑤ 软 I2C 先例 aht10/pca9685、软 SPI 先例 nrf24l01/max7219、忙等先例 ws2812/ir_remote（走 delay 模块、不占 TIMER——TIMG0/6/7/8/12 全占）；⑥ 页内符号异常按批次 1-3 先例人工复核（上游缺陷剔除并记 notes）。

### UART 资源可行性调研（本批前置，2026-09-05 实证）

**背景**：JQ8900、SYN6288、指纹三件都是 UART 类（JQ8900/SYN6288 9600 两线串口、指纹 AS608 串口），母版 UART0-3 已全分配（UART0=IMU601 115200、UART1=DIGIT_UART 115200、UART2=DEBUG+UWB 115200 + HC05 9600、UART3=ZIGBEE 115200）。

**批次 1 工单 02 结论复核**：HC05_UART 挂 UART2「与 DEBUG+UWB 同外设共享先例」的实证范围 = **单选生成 → SysConfig CLI 校验 → gmake 0 error / 0 warning（PASS）**。即只实证了**单选**（生成时先按选中模块裁剪，HC05 单选工程里 DEBUG_UART/UWB_UART 实例被裁掉，UART2 只剩 HC05_UART 一个实例）——**从未实证过同一 UART 外设下多个 UART 实例同选**。

**本次实证（SysConfig CLI 直接校验母版全量 mspm0.syscfg）**：

```
error: UWB_UART(...) peripheral.$assign: Resource conflict
        UART2 is already in use by DEBUG_UART(...) peripheral
error: HC05_UART(...) peripheral.$assign: Resource conflict
        UART2 is already in use by DEBUG_UART(...) peripheral
error: IMU601(...)/DIGIT_UART(...)/DEBUG_UART(...)/UWB_UART(...)/ZIGBEE_UART(...)/HC05_UART(...)(/ti/driverlib/UART): Maximum of 4 instance(s) allowed.
...（共 59 error，含 GPIO 名重复/引脚 Resource conflict 等全量布局固有冲突）
```

**结论**：
1. SysConfig CLI **不接受同一 UART 外设两个实例**（`UART2 is already in use by ...` 是 Resource conflict，不是警告）；UART 模块实例上限 = 4（= UART0-3 外设数）。
2. 母版全量布局（DEBUG+UWB+HC05 三实例同 UART2）本身从未被 SysConfig CLI 验证过——每次生成先裁剪，每个工程至多一个 UART2 实例；「共享先例」实为「**裁剪后独占**」，多实例共享在 SysConfig 层就被拒（先于批次 1 注释里担心的 IRQ 强符号重复问题）。
3. 因此**共享方案不可行**（并被实证否定）→ 按用户决策树：
   - **语音模块（JQ8900/SYN6288）走软 UART 单发 TX**：主控→模块单向发指令帧为主，GPIO 位操作 9600 8N1（~104us/bit），不开 UART 外设、不占 TIMER——库内无先例，本批新写，由编译矩阵验证编译、真机时序留验证（notes 注明）；页面 RX 中断接收（JQ8900/SYN6288 的状态回传缓冲）随软 UART 裁剪掉，notes 记录。
   - **指纹为双向（发指令+收响应帧）必须真实 UART**：新独立实例 `FINGERPRINT_UART`（不共享），**轮询接收、不注册 UART IRQHandler**（页面原为 UART 接收中断 + u1_recv_flag——改为轮询：无强符号、无与其它 UART 模块的同名 ISR 问题，且与批次 2「ADC 中断改轮询（共享实例 + 中断强符号唯一性）」同先例）；默认 `$assign = "UART0"`（**同选概率最低**——UART0 原宿主 IMU601 姿态采集与指纹身份不同框；单选指纹时裁剪后独占 UART0；与 IMU601 同选时经引脚绑定换实例消解，与 HC05/UWB/DEBUG 同先例）。

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + 服务函数，去 main/printf，函数名规范化（去 `FPM10A_`/`Pcd`/`SYN6288_` 菜市场命名按库风格重命名），全局状态收敛为模块内静态 + 入参/出参。
- **时序**：微秒/毫秒延时全走库内 `delay` 模块（`dependencies: ["delay"]`）；**不占 TIMER 实例**；**不注册 GPIO/UART 中断**（GROUP1 被 motor 独占；UART 用轮询避免同实例 ISR 强符号问题）。
- **引脚宏参数化**：按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚>_PIN`/`_PORT`，max7219/nrf24l01 先例）。
- **默认脚**：按「同选概率最低者与既有默认重叠」分配；**四件互为最常见同选组合（语音+身份门禁），默认脚互相不撞**；重叠对写入 `test_pin_bindings` 刻意重叠表。
- **wordlist**：语音挂新「语音模块」类（执行机构/控制类就近新分类）、RC522 挂「无线通信模块」、指纹挂「感知传感器」；全部 `lib_modules` 挂接。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `jq8900` | control--jq8900-voice-broadcast-module.md | **软 UART 单发 TX**（GPIO 位操作 9600 8N1，~104us/bit，不占 UART 外设/TIMER） | 新 GPIO 实例 `JQ8900`/TX（OUTPUT，初始 SET = 空闲高） | API = `jq8900_init` + `jq8900_send_cmd(cmd, data)`（帧 = `0xAA+cmd+data+(前三字节求和&0xFF)`——页面 demo `{0xAA,0x06,0x00,0xB0}` 实证结构与校验和）+ 命令服务函数 `jq8900_play(index)`（0x01）/`jq8900_play_next()`（0x06，页面实证）/`jq8900_play_prev()`（0x07）/`jq8900_stop()`（0x08）/`jq8900_pause()`（0x09）/`jq8900_resume()`（0x0A）/`jq8900_set_volume(vol)`（0x0B）/`jq8900_volume_up/volume_down`（0x0C/0x0D）——**命令字取自 JQ8900-16P 两线串口说明书指令表，页面仅实证 0x06=下一曲，notes 记录「命令字以厂家说明书/真机为准」**；页内 `SendData` 是一线串行（GPIO APP 脚 3:1 脉宽）非两线——**不作为本件服务函数**（notes 说明，如需一线串口另立）；页面 `UART_1_INST_IRQHandler`（RX 缓冲）随软 UART 裁剪；软 UART 发送循环 = 起始位低 → 8 数据位 **LSB 先** → 停止位高，每段 `delay_us(JQ8900_UART_BIT_US)`（104u）；默认 TX=**PB19**（DC_MOTOR 编码器 BA 脚——语音播报与双电机小车同选概率最低） |
| `syn6288` | control--syn6288-speech-synthesis-broadcast-module.md | **软 UART 单发 TX**（同上） | 新 GPIO 实例 `SYN6288`/TX（OUTPUT，初始 SET） | API = `syn6288_init` + `syn6288_speak(text)`（文本→合成播报）+ `syn6288_stop/pause/resume`（0x02/0x03/0x04，页面命令字实证）+ 底层 `syn6288_send_cmd(cmd_type, cmd_par, text)`（**帧结构按页面原样**：`0xFD + len_hi + len_lo + cmd + par + text + 异或校验`，`Data_Len = strlen(text)+3`，长度上限 200 字节防越界；注释记录帧格式）；`sprintf` 去 stdio 改手工逐字节；页面 `SYN6288RX_BUFF`/IRQHandler（状态回传 0x4A/0x41/0x4E/0x4F 等）随软 UART 裁剪——notes 记录（回传需要真实 UART 或改硬件方案）；默认 TX=**PB20**（DC_MOTOR 编码器 BB 脚——与 jq8900 PB19 同域、互不撞，语音两件同选默认即不撞） |
| `rc522` | rf--rc522-rf-ic-card-identification-module.md | 软 SPI 位操作（**5 脚**：CS/RST/SCK/MOSI/MISO——页面实际 5 脚，非 3 脚；照 nrf24l01 软 SPI 先例，单 PORT 宏） | 新 GPIO 实例 `RC522`（5 associatedPins 全 GPIOA，CS/RST/SCK/MOSI 输出 + MISO 输入） | API = `rc522_init` + `rc522_read_card(uid)`（四字节卡号，PcadRequest+Anticoll 内联，MI_OK=0x26 返回）+ `rc522_read_block(block, key_a, data)`/`rc522_write_block(block, key_a, data)`/`rc522_auth_block(...)` 认证读写按需裁剪 + `rc522_halt`；**页面 PcdComMF522/PcdRequest/PcdAnticoll/PcdSelect/PcdAuthState/PcdWrite/PcdRead/CalulateCRC 全套保留在驱动内**（驱动内容完整，服务层只包流程）；页内 `RC522_Rese` 拼写怪名保留内部（命名 `_reset`），`CalulateCRC` 拼写保留（上游拼写，notes 记录）；软 SPI 延时保持页面 200us 半周期（慢但稳，notes 说明）；默认 CS=PA7（DC_MOTOR BIN2 + SERVO_PWM 默认重叠——读卡与双电机/舵机同选概率最低）/RST=PA18（DC_MOTOR AIN2 + MAX7219 CLK）/SCK=PA14（DCC_100_PWM2 + WS2812 IN）/MOSI=PA16（编码器 AA）/MISO=PA17（编码器 AB）——**五脚全 GPIOA 单口**，与同批指纹/语音默认不撞 |
| `fingerprint` | sensor--fingerprint-recognition-sensor.md | **真实 UART（双向）**+ 1 × GPIO 触摸输入 | 新 UART 实例 `FINGERPRINT_UART`（`$assign=UART0`、**targetBaudRate=57600**——页面注释「AS608 默认 57600」；`enabledInterrupts=[]` 轮询）+ 新 GPIO 实例 `FINGERPRINT`/TOUCH（INPUT） | API = `fingerprint_init` + `fingerprint_check_device`（口令验证 0x13 回 0 判定）+ `fingerprint_is_touched` + `fingerprint_get_image`/`fingerprint_img_to_buffer(1|2)`/`fingerprint_reg_model`/`fingerprint_search(callback)`（返回 ID，255=未找到）/`fingerprint_enroll(store_id)`（两次采集→合成→保存，页面 FPM10A_Add_Fingerprint 去菜单/printf 的固定序列）/`fingerprint_delete_all` + 底层 `FPM10A_*` 帧构建函数族（**包头 0xEF 0x01 0xFF 0xFF 0xFF 0xFF + 指令/参数/校验和按页面原样**，notes 记录包格式）；**流程控制（先触摸→采集→比对、按键菜单 Yes/No）归生成骨架（ADR 0009）**——页面 key_scanf 菜单/printf 全剔除；`u1_recv_flag` 中断缓冲改 `fingerprint_wait_response(len, timeout_ms)` 轮询（DL_UART_getPendingInterrupt + delay_ms(1) 计数，页面 1000ms 超时 + 100ms 稳定等待保留）；默认 TX=PA28/RX=PA31（IMU601 原脚，同选概率最低）/TOUCH=PA12（PWMAB C0 + BH1750 SCL——指纹与双电机/光照同选概率最低；与 IMU/HX711 同样域不撞） |

### 波特率说明（fingerprint）

页面注释「as608 的默认波特率是 57600」；市售模块常见 9600/57600 两种出厂值——模块服务函数与波特率无关，若用户模块为 9600 出厂版，改 syscfg `FINGERPRINT_UART.targetBaudRate` 一行即可（notes 记录，真机核对）。

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板；软 UART 时序（104us/bit 逼近 9600 极限）、JQ8900 命令字、指纹帧协议/波特率真机验证留后续。

## 测试决策

照批次 1/2/3 先例逐件：

- `tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射（jq8900 TX=JQ8900/TX、syn6288 TX=SYN6288/TX、rc522 五脚=RC522/CS|RST|SCK|MOSI|MISO、fingerprint TX/RX=FINGERPRINT_UART/txPin|rxPin + TOUCH=FINGERPRINT/TOUCH）；
- `tests/test_pin_bindings.py` 刻意重叠表更新（PB19/PB20/PA7/PA18/PA14/PA16/PA17/PA28/PA31/PA12 计数与注释；新增 UART0 外设组 UART0=2——FINGERPRINT_UART 与 IMU601 同外设默认）；
- `tests/test_syscfg_prune.py` 增 JQ8900/SYN6288/RC522/FINGERPRINT_UART+FINGERPRINT 实例保留/裁剪断言；
- 新增 `tests/test_module_jq8900.py` / `test_module_syn6288.py` / `test_module_rc522.py` / `test_module_fingerprint.py`：manifest 结构 + 单选生成（syscfg 含实例 + 模块文件落盘 + main.c 调 init/服务函数过静态门禁）；
- **软 UART 发送时序纯函数单测**（新接缝，最高既有接缝 = 源码文本守卫 + Python 纯函数镜像）：test_module_jq8900.py / test_module_syn6288.py 内 `soft_uart_timeline(byte)` 纯函数——9600 8N1 位序列 → (电平, 时长) 时间轴，断言 10 段、起始位低、停止位高、数据位 LSB 先、每段 `JQ8900_UART_BIT_US`/`SYN6288_UART_BIT_US`（=104u）；另加源码文本守卫（防公式走样，ir_remote_tx `burst_cycle_formula_guard` 先例）+ syn6288 帧格式纯函数测试（0xFD + 长度 + 文本 + 异或，页面帧结构镜像）；
- 编译级验收：复制 `run_max7219_matrix.py` 改 slug，gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- 其余语音/身份件（LD3320 语音识别、JQ8900 一线串行模式、OSEB 等）、彩屏/0.96 单色（需网盘——批次 7 先例）。
- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 UART 外设（UART0-3 全占——FINGERPRINT_UART 走「裁剪后独占」先例，不开新外设实物）、TIMER、GPIO 中断。
- 正文内嵌段落（行拆散版）不作为提炼源。
- JQ8900 一线串行控制（页面 SendData，APP 脚 3:1 脉宽）——本件走两线软 UART，如需一线串行另立工单。
- SYN6288 的状态回传接收（0x4A/0x41/0x4E/0x4F 等）——软 UART 单向无 RX，回传解析归真机/硬件方案（notes 说明）。
- 指纹图像上传/下载（页面 72K 图像缓冲区 UART 上传）——本件不提图像服务（刷/录入/比对/删库为主），notes 说明。

## 补充说明

- 排序依据：批次 1/2/3 决策记录延续——本批按语音/身份常用度排序：jq8900（先做，软 UART 新先例打样）→ syn6288（同软 UART）→ rc522（软 SPI）→ fingerprint（真实 UART 轮询）。
- UART 可行性调研实证输出存档：`.scratch/wiki-modules-batch4/probe/syscfg-master/`（SysConfig CLI 对母版全量的报错输出，本次实证原始记录）。
- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 可复跑；本批四件均在 v7 全自洽清单内。
- 工单：`issues/01-module-jq8900.md` → 02 syn6288 → 03 rc522 → 04 fingerprint（互相独立，可并行；实施按简→繁）。
- 完成后：全量测试套件 + 批次 1+2+3+4 全部 15 件 code-review 收尾 + CONTEXT.md 平台行补录 + 中文提交（.githooks/commit-msg 强制中文；.ps1 若新增按 UTF-8 with BOM 存）。
