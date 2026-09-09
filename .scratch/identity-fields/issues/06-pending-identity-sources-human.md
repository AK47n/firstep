# 06 — 待补器件购买出处（人工取源）

**要做什么：** 6 个真器件的平台条目仍缺硬件身份字段（`kit` + `source_url`），本次交付
的判据与守卫已经把「缺口」钉在明面上（strict-xfail + audit `[身份]` 行 + backlog 5.4），
但**取源这一步需要人**——机器核不出可核实的采购/官方页时不许编链接。本工单就是这条
人工队列的落点：人补齐数据 → 按下面的关闭流程收尾。

**被谁阻塞：** 无——04 的清单与依据已交付（`.scratch/identity-fields/issues/04-unverifiable-backlog.md`
「04 续」表），本工单只承接「取源」这一步。

**状态：** ready-for-human

- [ ] 逐条给出可核实的购买/官方页（判据见工单 04「04 续 · 裁决一」三条：同一件实物、
      不是板载资源教程页、可核实的官方或采购页），或明确判定「永久不补」（则改
      `library.MODULE_KIND` 判内部件/协议切片并写明理由，走另一条路径）
- [ ] `beep`：有源蜂鸣器模块（库内实现为**有源**、低电平触发；wiki 无蜂鸣器模块手册页）
- [ ] `ir_beam`：红外对射/遮挡检测件（三线制 VCC/GND/OUT；wiki 命中的都是反射式测距 /
      循迹 / 热释电，不是对射件）
- [ ] `key`：独立轻触按键模块（wiki 只有入门教程页与摇杆 / 矩阵键盘等**不同硬件**）
- [ ] `led`：LED 指示灯（板载 / 外接；wiki 只有教程页与 WS2812 / 数码管等不同硬件）
- [ ] `led_beep`：LED + 蜂鸣器组合件（随 `led` / `beep` 一起解决）
- [ ] `step_motor`：脉冲式步进电机 + 驱动板（库内实物 = DCC-100v3 闭环步进，
      `sources/materials/2026_04_地猛星电赛控制题配套资料/`（实测：`【云台】02_DCC-100v3说明书-2026-05-24.pdf`
      与 `【云台】04_Q_2026_05_11_DCC-101v1闭环步进电机资料.zip`）有说明书与发货清单但无公开采购链接；
      wiki 命中的 `l298n` / `tb6612` 是直流驱动板，不同硬件）
- [ ] 每补齐一个 slug：按下方「关闭流程」收尾（移出 `IDENTITY_BACKLOG`、删对应 xfail
      用例、复跑 audit 确认缺口数与清单一一对应）

## Comments

- **为什么单独开 06 而不是重开 04**：04 的交付物（待补清单 + 逐条依据 + 复跑探针）确实
  已完成，重开会混淆 `resolved` 的含义；同 feature 续号不触碰 01-05 的 resolved 语义，
  且本工单会进 `python .scratch/tracker-audit/list_open_tickets.py` 的人工队列
  （此前该队列只有 `recommend-vision-qa/03`，本工单入库后为 2 条）。
- **缺口的三处可见性**（互为兜底，任一丢失都能被发现）：
  1. `tests/test_library_invariants.py::IDENTITY_BACKLOG`（6 slug）+ 对应 strict-xfail
     用例——数据补齐即 XPASS 判失败，**强制**你走关闭流程；
  2. `.scratch/backlog.md` 5.4① 的「剩余 13 条 / 7 slug 待补」（`zigbee_link` 已补后
     应为 11 条 / 6 slug）；
  3. 工单 04 Comments 的待补表（含逐条「为什么核不出」与实测依据）。
- **关闭流程（补一个 slug 就做一次，别攒）**：
  1. 填 `library/modules/<slug>/manifest.json` 的两个平台条目的 `kit` 与 `source_url`；
  2. 从 `tests/test_library_invariants.py::IDENTITY_BACKLOG` 移出该 slug；
  3. 删掉/更新对应的 strict-xfail 用例（`test_backlogged_device_modules_declare_identity_fields`
     在清单空时一并删除）；
  4. `python .scratch/library-audit/audit.py` → `[身份]` 真器件缺 kit/url 数应等于清单
     剩余条目数（一一对应，无沉默缺口）；
  5. 复跑全量 `pytest`（`test_identity_backlog_is_exactly_the_current_gap` 会守「清单恰好
     等于缺口」，两侧必须一致）；
  6. 工单 04 的待补表把该 slug 行改成「✅ 已回填」并记出处；本工单对应验收项打勾。
- **取源提示**：`e.tb.cn` 短链先例（`ml_mpu6050` / `uwb_uart` 就是用户给的淘宝短链）；
  厂商官方产品页先例（`zigbee_link` = Hexin 官方 DL-20 页）；立创 wiki 手册页「模块来源 ·
  采购链接」段（`oled` / `servo` / `xunji` / `pid` 即此）。
- **不许做的事**：为了清空缺口填占位链接、同类但不同型号的页（有源 vs 无源蜂鸣器、
  DCC-100v3 vs 二相四线步进）、纯资料站转载或 B2B 批发页。核不出来就继续留着——
  空值语义 = 「暂无出处」，比编一个链接安全。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
