# 02 — 内部件/协议切片身份豁免 + 双向守卫（红证）

**要做什么：** 库把「器件必须有 kit + source_url、内部件/协议切片必须没有」钉成双向
不变量：给内部件顺手填了 kit 会红，清空真器件的 kit 也会红；审计脚本 `[身份]` 行不再
把内部件/协议切片算成缺口。豁免的表达形式 = 空值 + 单源理由（不给 manifest 加字段）。

**被谁阻塞：** 01（判据单源）

**状态：** resolved

- [x] `tests/test_library_invariants.py` 落两条守卫用例（照既有风格，失败信息点名
      模块 / 不变量 / 具体差异）：器件类每个平台条目 kit 与 source_url 非空且
      source_url 以 http 开头；内部件/协议切片所有平台条目两者皆空
- [x] **红证**（先红后绿，不许为绿放宽判据）：临时副本注入实测两种破坏各跑一次并记
      Comments——① 给内部件 `delay` 填 kit → 豁免守卫红；② 清空真器件 `motor` 的 kit
      → 器件守卫红；证据含失败信息原文与还原确认
- [x] `.scratch/library-audit/audit.py` 的 `check_identity_fields` 引用
      `library.MODULE_KIND` 跳过内部件/协议切片，`[身份]` 行报「真器件缺口」并列出
      豁免 slug 数（人工复跑工具与测试同源取判据）
- [x] 复跑 audit：`[身份]` 缺 kit / 缺 source_url 从 46 降到「内部件+协议切片不再计入」
      后的真器件数（本工单不填数据，数值 = 46 − 24 = 22）
- [x] 全量 pytest 绿（3884 passed；`tests/test_autocommit.py` 注册表补 5 条读函数）

## Comments

- 豁免不加 manifest 字段的理由（spec「豁免的表达形式」）：同一事实不设两个出处；
  生成链路不按身份字段分支（`collect_kits` 空值跳过），空值零副作用。
- 守卫跑真实库语料（不合成），红证用临时副本注入——先例 = 工单
  library-hookup-and-invariants/02（临时副本破坏四类全红）。
- **红证实录（2026-09-08，`.scratch/library-audit/probe_identity_guard_red.py`）**：
  - 破坏①「给内部件 delay 填 kit」→ 守卫红：
    `delay/mspm0 不该有身份字段：kit、source_url`、`delay/stm32 不该有身份字段：kit、source_url`。
  - 破坏②「清空真器件 motor 的 kit」→ 守卫红，缺口 23 条（21 条既有 + motor/mspm0、
    motor/stm32），前几条：`beep/mspm0 缺 kit、source_url`、`ir_beam/stm32 缺 kit、source_url`…
  - 脚本末尾自检：真实库内部件/协议切片身份字段违规数 = 0、`motor/stm32` 的 kit 仍在、
    `motor/mspm0` 仍为空（副本注入未触碰真实库）。
- **先红后绿证据**：守卫落盘后先跑真实库（未填任何数据）——
  `test_device_modules_declare_identity_fields` 红，失败信息列出 26 条器件缺口
  （beep/ir_beam/k230/key/led/led_beep/motor/oled/pid/servo/step_motor/xunji/zigbee_link
  各平台），`test_internal_and_protocol_modules_have_no_identity_fields` 绿（豁免项本就为空）。
- audit 复跑（本工单，未填数据）：`[身份] 平台条目共 170（内部件/协议切片豁免 24）：
  真器件缺 kit 22、缺 source_url 22`——缺的 22 条全部是真器件（13 slug），逐条进工单 03/04。
