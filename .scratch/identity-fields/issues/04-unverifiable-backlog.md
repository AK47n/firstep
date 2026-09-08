# 04 — 核不出出处的条目清单 + 后续路径

**要做什么：** 把「真器件但本次核不出购买出处」的 slug 与平台条目落成明确清单，写清
每条为什么核不出、后续怎么核，让缺口有据可查（不是沉默缺口），且不编造链接。

**被谁阻塞：** 03（回填后剩下的才是待补）

**状态：** resolved

- [x] 清单落本工单 Comments：slug / 平台 / 现状（kit 空、source_url 空）/ 核不出的
      具体依据（在 wiki 模块索引里没有该器件手册页、库内无同硬件条目、本地手册无采购
      链接）/ 后续核法（等 lckfb 补页、找厂商页面、用户提供实物链接）
- [x] 复跑探针脚本确认「索引页里确实没有」这一步可复现（脚本随工单留在
      `.scratch/library-audit/`，含用法注释）
- [x] 若某 slug 实际是内部件/协议切片（判定有误）→ 改 `MODULE_KIND` 并写明理由，
      不放待补清单（本轮 7 个 slug 全部核实为器件，无改判）
- [x] audit `[身份]` 行剩余数 = 本清单条目数（一一对应，无沉默缺口）
- [x] （04 续）裁决「板载资源是否用教程页」口径 + 第二轮逐条取源复核：`zigbee_link`
      已回填并移出 `IDENTITY_BACKLOG`、删对应 xfail 用例；其余 6 slug 的「不算」依据
      逐条实测落档（见「04 续」表）

## Comments

- 本工单**不填任何数据**；只落清单与路径。核不出的条目允许长期为空——空值语义 =
  「暂无出处」，比编一个链接安全。

### 待补清单（audit `[身份]` 的 13 条 = 7 slug × 平台）

| slug | 平台 | 现状 | 核不出的具体依据 | 后续核法 |
|---|---|---|---|---|
| `beep` | mspm0、stm32 | kit 空、url 空 | 立创 wiki 模块手册索引（dmx 70 条 / dkx 77 条）无蜂鸣器页；库内无同硬件条目；本地手册无采购链接。另注：`beep/mspm0` 是占位实现（notes 自述「地猛星排针已分配满，暂无蜂鸣器引脚」），硬件出处本来就不确定 | 等 lckfb 补蜂鸣器手册页；或由用户提供实物链接（购买记录） |
| `ir_beam` | mspm0、stm32 | kit 空、url 空 | 索引无红外对射页（探针命中为 0；`sensor/Infrared-tracking-sensor` 是循迹件、不是对射件） | 同上；厂商页面（三线制对射传感器）需人工确认 |
| `key` | mspm0、stm32 | kit 空、url 空 | 索引只有入门教程页（`beginner/key*.html`）与**不同硬件**页（摇杆 `two-axis-keystroke-rocker`、`4x4-keyboard`），无「独立轻触按键模块」手册页 | 板载按键可考虑用入门教程页（语义 = 板载资源，需先定口径）；独立按键模块等手册页 |
| `led` | mspm0、stm32 | kit 空、url 空 | 索引只有入门教程页（`beginner/led*.html`）与**不同硬件**页（WS2812 灯带 / 数码管 / OLED），无通用 LED 指示灯手册页 | 板载 LED 可考虑入门教程页（同上，需先定口径） |
| `led_beep` | mspm0、stm32 | kit 空、url 空 | 组合件 = `led` + `beep`，两者都核不出，组合件更无独立页 | 随 led / beep 一起解决 |
| `step_motor` | mspm0 | kit 空、url 空 | 索引无步进电机页（`l298n` / `tb6612` 是直流驱动板、不是步进件）；库内无同硬件条目。本地手册有「DCC-101v1 闭环步进电机」资料包（`sources/materials/2026_04_地猛星电赛控制题配套资料/`）但无采购链接 | 找 DCC-101 厂商页面；或用户提供实物链接 |
| `zigbee_link` | mspm0、stm32 | kit 空、url 空 | 索引无 Zigbee 页；库内无同硬件条目。本地有 DL-20 官方资料（`sources/materials/无线串口模块资料/DL-20/DL-20使用说明书.pdf` + 原理图）但无公开采购链接 | 找 DL-20 厂商/商城页面；或用户提供实物链接 |

- 复现命令（探针输出即上表依据）：
  `$env:PYTHONIOENCODING='utf-8'; python .scratch\library-audit\probe_backlog_sources.py`
  （脚本在线抓取两个平台的模块手册索引页，输出「索引页链接 201 条」——含模块手册页
  与站内其它页；脚本会列出每个 slug 的关键词命中，命中的都是**不同硬件**或教程页，
  已在上表逐条说明；命中为空 = 索引里确实没有对应器件手册页）。
- 口径待定项（**04 续已裁决**）：`led` / `key` 的「板载资源」要不要用入门教程页作
  source_url？→ **不填**，判据见下方「04 续 · 裁决一」第 2 条（教程页讲板载资源、
  引脚也对不上，来源语义会变模糊）。
- 与 5.5 遗留的关系：本条**不含** 5.5 四条（mq4-9 措辞 / 77 条目未上板 / oled 词表
  方案级缺口 / A 类 3 页 mspm0-only），本轮不碰。

### 04 续（2026，第二轮取源）：口径裁决 + 逐条复核

**裁决一：`source_url` 的语义 = 「同一件实物」的可采购 / 官方页。** 本轮把 7 个 slug
的第二轮候选全部实测（探针脚本 `probe_backlog_sources.py` 的 `VENDOR_PAGES` 段，
逐页 HTTP 实测状态码 + 标题），据此判定「能不能填」，判据三条：

1. **同一件实物**——页面讲的硬件与库内模块驱动的那件必须是一件（驱动形态 / 型号 /
   默认脚对得上）；同类但不同的件（有源 vs 无源蜂鸣器、DCC-100v3 vs 二相四线步进）
   不算。
2. **不是板载资源教程**——`led` / `key` 的候选全是入门教程页（讲开发板板载 LED /
   按键），而词表登记的是可采购件（「LED 指示灯（板载 / 外接）」「独立轻触按键模块
   （带上拉）」），且引脚对不上（实测：地猛星教程 LED = PA14、板载按键 = PA18 且 PA18
   是 BSL 引脚；库内默认 mspm0 LED = PA15、key = PA2 / stm32 PB3）。填教程页会让
   来源行指向「板载资源怎么点灯」，不是「买哪件」——**不填**。
3. **可核实的官方 / 采购页**——厂商官方产品页、wiki 手册页「模块来源 · 采购链接」段
   都算；纯资料站转载、B2B 批发页不算。

**本轮结果：1 个 slug 补齐（`zigbee_link`），其余 6 个维持待补。**

| slug | 本轮结论 | 依据（实测） |
|---|---|---|
| `zigbee_link` | ✅ **已回填双平台** | 厂商 Hexin 官方产品页：`https://www.hexin-technology.com/250m_TTL_to_ZigBee_Module-Product-565.html`（200 · 标题「DL-20 250m TTL to ZigBee Module」，正文「DL-20 TTL ZigBee wireless serial communication module … full-duplex … UART … CC2530」）——型号 DL-20、串口透传语义与库内驱动完全一致；kit 写「DL-20 250m TTL 转 ZigBee 无线串口透传模块（CC2530，UART 全双工点对点/广播——厂商 Hexin 官方产品页）」 |
| `beep` | ❌ 仍待补 | wiki 无蜂鸣器**模块**手册页；仅两条候选均**不算**：ColorEasyDuino「低电平触发的**无源**蜂鸣器」（200，但库内 beep 是**有源**蜂鸣器——`beep_stm32.c` 头注释「有源蜂鸣器，低电平响」，驱动形态不同）、天巧星板载无源蜂鸣器教程（PWM 调音，板载 + 无源） |
| `ir_beam` | ❌ 仍待补 | 索引无对射页；三个命中页均**不算**：红外测距（GP2Y0A02YK0F，反射式测距）、红外循迹（TCRT5000，反射式）、人体红外（HC-SR501，热释电）——都不是「对射 / 遮挡检测」件 |
| `key` | ❌ 仍待补 | 索引无「独立轻触按键模块」手册页；命中页是入门教程（地猛星 PA18 板载按键、地阔星 PA0）与**不同硬件**（双轴摇杆、4×4 键盘）——按裁决一 / 二不填 |
| `led` | ❌ 仍待补 | 索引无通用 LED 指示灯手册页；命中页是入门教程（地猛星板载 PA14）与**不同硬件**（WS2812 灯带、数码管、OLED）——按裁决一 / 二不填 |
| `led_beep` | ❌ 仍待补 | 组合件 = `led` + `beep`，两者都核不出，组合件更无独立页 |
| `step_motor` | ❌ 仍待补 | 索引无步进电机页（`l298n` / `tb6612` 是直流驱动板）；唯一候选 GD32E230C8T6「二相四线步进电机」页（200）**不算**——库内实物是 DCC-100v3 驱动板 + 闭环步进（本仓 `sources/materials/2026_04_地猛星电赛控制题配套资料/【云台】02_DCC-100v3说明书-2026-05-24.pdf` 有接线说明与发货清单，无公开采购链接） |

**后续核法**（沿用）：等 lckfb 补对应模块手册页；或由用户提供实物购买记录链接
（`e.tb.cn` 短链先例：ml_mpu6050 / uwb_uart 就是用户给的淘宝短链）；`step_motor`
优先找 DCC-100 厂商页面。

**代码侧同步**：

- `tests/test_library_invariants.py`：`IDENTITY_BACKLOG` 移出 `zigbee_link`（7 → 6），
  对应 strict-xfail 用例 `test_backlogged_device_modules_declare_identity_fields`
  已删除（数据补齐即 XPASS 判失败，按机制摘标记）。
- `test_identity_backlog_is_exactly_the_current_gap` 继续守「清单恰好等于缺口」：
  `zigbee_link` 移出后其字段已齐，不在缺口内，两侧一致。
- 审计复跑（`.scratch/library-audit/audit.py`）：`[身份]` 真器件缺 kit / source_url
  由 **13 → 11**，与本清单条目数（6 slug × 平台 = 11 条：beep 2 / ir_beam 2 / key 2 /
  led 2 / led_beep 2 / step_motor 1）一一对应，无沉默缺口。
- 探针脚本 `probe_backlog_sources.py` 已扩到本轮口径：新增 `VENDOR_PAGES` 段，逐条
  实测候选页（状态码 + 标题），「为什么没填」可复现。

