# 批次 9「语音/电机/新无线」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

stm32 线进度：批次 1-8 已入库 51 件。本批 = **语音/电机/新无线组**：jq8900、syn6288（语音——软 UART TX 形态）、fingerprint（真实 UART 帧协议）、l298n（PWM×2 方向互切）+ **3 个 B 类新 slug**：neo_6m（GPS/NMEA）、esp01s（WiFi/AT）、ec01g（NB-IoT+GPS/AT，页面仅 HTTP demo 无 GPS 代码）。

**本批核心约束**：UART 仅 3 实例（USART1/2/3，批 2/8 后全占）——本批 4 件真实 UART 件（fingerprint/neo_6m/esp01s/ec01g）默认分配 = **与互替件同实例同脚**（互替同脚先例：K230 视觉/UWB 定位/HC05 手机遥控/ZIGBEE-AS32 无线）+ 同选经绑定换实例（上限 3——4 件以上同选物理不可行 notes）；jq8900/syn6288 走**软 UART TX**（不占实例）。

## 方案

照批次 1-8 管线。软 UART TX（jq8900/syn6288）= `delay_us(104)+gpio_set` 位时序（照 mspm0 定稿：mspm0 = 软 UART TX 学页面两线帧 104us/bit）；真实 UART 件 = ml_uart + `{stem}_rx_handler` 聚合首扩（照 hc05 先例：isr.c 加 __weak 兜底 + USARTx_IRQ_CALLS 加调用 + pinwriter 登记）；l298n = PWM×2（TIM3_CH1/CH2）+ 方向互切（照 mspm0 单路 set_duty/set_direction 形态）。每件：提炼 → 纯驱动切片 → 换算 → pin_config.h 宏段 + （UART 件）isr.c/聚合 → manifest → 测试 → UV4 矩阵 0/0 → verified → 中文提交。

## 用户故事

1. 做题用户选 stm32 + jq8900/syn6288：`jq8900_play(index)/syn6288_speak(text)` 直达语音（软 UART 只发不收，不占串口实例）。
2. 做题用户选 stm32 + fingerprint：指纹注册/搜索流程族 API（与 mspm0 同名），`fingerprint_enroll/search` 直接可用（57600）。
3. 做题用户选 stm32 + l298n：单路 `set_duty/set_direction`（TIM3，与 TB6612 电机/TB6612 互替不同 TIM）。
4. 做题用户选 stm32 + neo_6m/esp01s/ec01g：`read_frame/get_position`（NMEA）与 `send_cmd/available/receive`（AT 透传）直接可用（B 类仅 stm32 条目）。
5. 维护者：每件可溯源（A 类 source_url=wiki 原页；B 类 notes 注明口径）。

## 实现决策

### 既定事实（勿重新调研；batch9-facts.md 已取证，7 页全 F1；UART 实例现状表见批 8 后 pin_config.h）

① **软 UART TX 形态（jq8900/syn6288）**：页面=真实 UART2（两线帧）+ 一线 GPIO 时序（3:1 脉宽）双描述——**mspm0 定稿=软 UART TX 学两线**（104us/bit，9600 8N1 换算；只发不收——语音控制命令帧不需要响应读取）；stm32 照抄：`delay_us(104)+gpio_set` 位时序；帧 = 页面两线帧原式（jq8900 0xAA+cmd+data+求和、syn6288 FD+Len(文本+3)+Cmd+Par+text+XOR——与 mspm0 逐字节一致）；页面 RX 部分（真实 UART 接收/回绕缺陷）**不实现**（语音件无收需求——notes：如需响应回读走真实 UART 方案范围外）。
② **软 UART 默认脚**：**jq8900=PA15**（叠 BUZZER——提示输出**互替**（语音播报替代蜂鸣，同选概率最低；互替同脚先例）；语音×蜂鸣「同框」为替代非组合）+ **syn6288=PC14**（叠 LED_YELLOW——输出指示互替；两件互替互相错开）；页面默认脚（PA2/PA3=DEBUG 常备）全不照抄。
③ **fingerprint（真实 UART）**：57600（页面取证）；**默认 UART_1（PA9/PA10，与 K230 视觉 DIGIT_UART 互替同实例同脚先例）**；`fingerprint_rx_handler` 聚合（isr.c 加 __weak + USART1_IRQ_CALLS）；mspm0 API 全族（init/check_device/is_touched/get_image/img_to_buffer/reg_model/search(→uint16_t)/save_finger/delete_all/enroll——照 fingerprint.h 逐函数同名同型）；响应帧精确收 12/16 字节（mspm0 改进沿用——页面 200ms 稳定等待 + u2_recv_length++ 无上限修正）；页面散文 PA8/PA9 vs 代码 PA2/PA3 自相矛盾（notes）。
④ **l298n（PWM×2 方向互切）**：**默认 TIM3_CH1/CH2 = PA6/PA7（页面原脚；TIM3 定时器零占用；与 TB6612 motor（TIM2/PA0-1）互替**刻意错开**TIM 与脚）**；API = `l298n_init()/l298n_set_duty(uint32_t)/l298n_set_direction(uint8_t)` + `L298N_PWM_PERIOD 2000u` 宏（mspm0 单路形态 ——页面只实现 A 路、B 路范围外；EN/跳线帽范围外）；**⚠ 与软 I2C 总线 PA6/PA7 冲突**（l298n×I2C 件同选 = 物理冲突 ⚠ + 绑定消解；l298n×TB6612 互替错开（TIM2 vs TIM3）；TIM 门禁只查用户绑定——2026H 骨架调度 TIM_3 × l298n 默认 TIM_3 = 默认×默认不拦（现状口径）——notes）。
⑤ **B 类三件（仅 stm32 条目）**：
   - neo_6m：**默认 UART_1**（与 UWB 定位互替同实例）+ `neo_6m_rx_handler` 聚合；NMEA 解析 = `$`→GPRMC→`\n` 帧识别 + 字段解析（非 AT——页面代码主循环解析）；API = `neo_6m_init/neo_6m_read_frame(uint8_t 0/1)/neo_6m_get_position(float *lat, float *lon)/neo_6m_clear()`（GPRMC ddmm.mmmm → 十进制度）；**缺陷修正**：GPSRX_LEN 夹 255 后下标 255 越界（→缓冲 256 + 截断）、memcpy 80 字节无长度检查（→截断保护）。
   - esp01s：**默认 UART_1**（与 HC05 手机遥控互替同实例）+ `esp01s_rx_handler`；115200（页面）；AT 透传 + strstr 应答匹配 + `+IPD,` 解析；API = `esp01s_init/esp01s_send_cmd(const char*)/esp01s_send_string/esp01s_available()/esp01s_receive(buf, max)/esp01s_parse_ipd()`；**AT 模板（CWMODE/CWSAP/CIPSERVER）与 MQTT/阿里云/JSON 归骨架/范围外**；**缺陷修正**：RX `(len+1)%200` 回绕（→截断保护）+ IDLE `'\0'` 断串、`while(':')` 无界扫（→有界）、buff[50] 截断 200 数据（→缓冲上限 200）。
   - ec01g：**默认 UART_3**（与 ZIGBEE/AS32 无线互替同实例）+ `ec01g_rx_handler`；9600；AT 透传 + hex 响应解码；API = `ec01g_init/ec01g_send_cmd/ec01g_send_string/ec01g_available()/ec01g_receive(buf, max)`；**页面 HTTP 天气 demo/hex 解码/JSON/GPS 归范围外**（页面无 GPS 代码）；**缺陷修正**：超时后 `rev_buff=NULL→+=11` 空指针崩溃（→空指针保护）、`while(!='"')` 无界（→有界）+补零位错 `[i+1]`。
⑥ **UART 共享组现实约束**：同实例多角色（波特率互斥：fingerprint 57600 × UART_1 115200——后 init 定波特率，已记录；同选时经绑定换实例/换脚）——UART 上限 3：与任意 ≤2 件 UART 模块同选在限内、4 件以上物理不可行（notes，mspm0 线同款）。
⑦ **mspm0 API 全对齐**（已核验 .h）：jq8900 11 函数 / syn6288 6 函数（send_cmd(cmd_type, cmd_par, text)/speak(text)/stop/pause/resume）/ fingerprint 流程族 / l298n 3 函数——stm32 同名同型（工单列出逐函数名，实施者以 mspm0 .h 终校）。

### 各件决策

| 工单 | slug | 类型 | 形态 | 默认脚/实例 | API（mspm0 对齐/B 类设计） | 修正/notes |
|---|---|---|---|---|---|---|
| 01 | jq8900 | A | 软 UART TX | OUT=PA15（叠 BUZZER 互替） | init/play(index)/play_next/play_prev/stop/pause/resume/set_volume/volume_up/volume_down/send_cmd(cmd,data)——11 函数照 mspm0 | RX 回绕不实现（软 TX 无收）；「bsp_syn6288」串台；104us/bit |
| 02 | syn6288 | A | 软 UART TX | OUT=PC14（叠 LED_YELLOW 互替；与 jq8900 错开） | init/send_cmd(cmd_type,cmd_par,text)/speak(text)/stop/pause/resume——6 函数照 mspm0 | strlen 200 上限（Send_Buff[210]→200）；RX/IDLE 不实现；帧 XOR |
| 03 | fingerprint | A | 真实 UART | UART_1（PA9/10，与 K230 互替） | init/check_device/is_touched/get_image/img_to_buffer/reg_model/search(→uint16_t)/save_finger/delete_all/enroll——照 mspm0 fingerprint.h 全族 | 散文/代码脚矛盾记录；精确收 12/16 字节；u2_recv_length 无上限修正、+rx_handler 聚合 |
| 04 | l298n | A | PWM×2 + 方向 | IN1=PA6/TIM3_CH1、IN2=PA7/TIM3_CH2 | init/set_duty(uint32_t)/set_direction(uint8_t)+L298N_PWM_PERIOD 2000u——照 mspm0 | 只 A 路（B 路范围外）；TIM 门禁默认×默认不拦 notes；与 I2C 总线同脚冲突 ⚠ |
| 05 | neo_6m | **B** | 真实 UART + NMEA | UART_1（PA9/10，与 UWB 互替） | init/read_frame(0/1)/get_position(lat,lon)/clear | 255 越界修正；memcpy 截断；GPRMC 解析 |
| 06 | esp01s | **B** | 真实 UART + AT | UART_1（PA9/10，与 HC05 互替） | init/send_cmd/send_string/available/receive/parse_ipd | 回绕/IDLE 断串/无界扫修正；AT 模板/MQTT 范围外 |
| 07 | ec01g | **B** | 真实 UART + AT | UART_3（PB10/11，与 ZIGBEE/AS32 互替） | init/send_cmd/send_string/available/receive | 空指针崩溃修正；无界扫修正；天气/JSON/GPS 范围外 |

### 默认脚与重叠全景（定稿）

| slug | 默认脚/实例 | 重叠主体（同选概率最低） |
|---|---|---|
| jq8900 | OUT=PA15 | BUZZER（提示输出互替——语音播报替代蜂鸣，互替同脚先例） |
| syn6288 | OUT=PC14 | LED_YELLOW（输出指示互替；与 jq8900（PA15）互相错开） |
| fingerprint | UART_1/PA9-10 | DIGIT_UART（K230 视觉——身份识别互替同实例同脚先例） |
| l298n | IN1=PA6/IN2=PA7（TIM3_CH1/2） | MOTOR_A_DIR/DIR2 + 软 I2C 总线（l298n×I2C 件=物理冲突⚠绑定消解；与 TB6612 motor（TIM2/PA0-1）互替刻意错开 TIM/脚；2026H 骨架 TIM_3 默认×默认不拦） |
| neo_6m | UART_1/PA9-10 | UWB_UART（定位互替） |
| esp01s | UART_1/PA9-10 | HC05_UART（手机遥控互替） |
| ec01g | UART_3/PB10-11 | ZIGBEE_UART+AS32_UART（无线互替） |

- 白名单登记：PA15 +1（jq8900——BUZZER 组）、PC14 +1（syn6288——LED 组）、PA6/PA7 +2（l298n——PWM 组/I2C 总线冲突组）、UART1 外设级 +3 角色、UART3 外设级 +1 角色（test_pin_bindings uart 共享组扩——批 8 已适配）。
- UART 同选消解：经绑定换实例（成对 tx/rx）换脚；4 件以上 UART 模块同选物理不可行 notes（实例上限 3）。

## 测试决策

- `tests/test_module_jq8900.py` / `test_module_syn6288.py`：软 UART TX 守卫（`104`us/bit 常量、帧字节（jq8900 `0xAA`+求和校验、syn6288 `0xFD`+异或）、无 UART 实例字面量（`UART_1`/`USART`）、无 RX 实现（`rx_handler` 不出现）、strlen 上限（syn6288 `200`））+ 单选生成 + 宏存在（`JQ8900_GPIO\s+GPIO_A`/`JQ8900_PIN\s+Pin_15`、SYN6288 同款 PC14）。
- `tests/test_module_fingerprint.py`：UART 实例断言（`FINGERPRINT_UART\s+UART_1` 五件套宏）、`57600`、`fingerprint_rx_handler` 存在（isr.c __weak + USART1_IRQ_CALLS 断言）、帧头 `0xEF 0x01 0xFF 0xFF 0xFF`、精确收 12/16、API 全族（≥10 函数名断言）。
- `tests/test_module_l298n.py`：`TIM3_CH1/CH2` 宏、`L298N_PWM_PERIOD 2000u`、set_duty/set_direction、无 EN 代码、TIM 门禁说明注释。
- `tests/test_module_neo_6m.py` / `test_module_esp01s.py` / `test_module_ec01g.py`（B 类模板）：仅 platforms.stm32 + `*_rx_handler` 聚合 + 缺陷守卫（neo：缓冲 ≥256/截断无 `[255]` 越界式；esp01s：无 `% 200` 回绕式 + 有界扫（`while` 含 `i < ` 上限）；ec01g：空指针保护（`NULL` 检查）+ 有界扫）+ 默认实例宏断言（NEO_6M_UART=UART_1 等五件套）+ API 断言。
- `tests/test_pins.py` STM32_MACRO_VALUES 补宏（jq8900/syn6288 各 2 + l298n 4 + fingerprint/neo/esp/ec01g 各 5 件套——约 28 宏）；test_default_layout.py 白名单按上表；**test_pin_bindings uart 共享组扩充**（指纹/neo/esp → UART1、ec01g → UART3——照批 8 适配先例）。
- UV4 矩阵（每件，MAIN_C 调全部 API (void) 化——jq8900 全 11 函数、syn6288 6 函数、fingerprint 流程族、l298n 3 函数、B 类全族）→ 0/0 → verified=true。
- 词表：前 4 件已挂接零补录；**B 类 3 件补录**（无线通信/GPS 定位 + models + lib_modules）。

## 范围外

- mspm0 条目（A 类零改动；B 类无）；vl53l0x（批 4 待资料）；C 类核对（批 11）；上板真机验证（notes——软 UART 时序/帧/波特率/AT 应答超时真机校准留后续）。
- jq8900/syn6288 的 RX 响应回读（真实 UART 方案——语音件无收需求，范围外）；at 模板（CWMODE/MQTT/JSON/天气 demo——归骨架/范围外）；l298n B 路/EN 跳线（页面未给/mspm0 单路——范围外）；l298n×骨架 TIM3 冲突（默认×默认不拦现状，用户可绑定换 TIM——范围外）。
- NMEA 解析深度（帧头/字段处理按页面 GPRMC——RMC 日期/时间/速度等字段不解析，仅位置——notes）；ESP01S+EC01G 的 hex 解码细节（页面漏洞修复后按页面范围——天气 demo 不落）。

## 补充说明

- 排序：01 jq8900 → 02 syn6288（软 UART 对仗）→ 03 fingerprint（帧协议新形态）→ 04 l298n（PWM 新形态）→ 05 neo_6m（B 首个 NMEA）→ 06 esp01s → 07 ec01g（B 类 AT 三连——互替语义对仗）。
- 页内事实 = %TEMP%\batch9-facts.md（7ff497b0 报告，2026-09 回填）。
- 收尾清单：全量测试 → sweep 更新 → code-review 两轴 → CONTEXT 补录 → 中文提交。
