# 03 — 回归验证 + 文档更新（CONTEXT.md / CHANGELOG）

**要做什么：** 全量回归（pytest + Node 前端测试 + fx-guard）；CONTEXT.md 域词条补「烧录」行（flash.py / /api/flash / 三配置键 / 两平台工具链：STM32=OpenOCD|st-flash、MSPM0=CCS DSLite XDS110 零安装）；CHANGELOG 由自动钩子生成。

**被谁阻塞：** 02 — 前端烧录 UI。

**状态：** pending

- [ ] 全量 pytest + tests/js/*.test.mjs 通过，无回归。
- [ ] CONTEXT.md 域表补「烧录」词条（含 DSLite 路径发现、hex/out 定位规则、范围外串口 ISP/BSL 备注）。
- [ ] CHANGELOG 条目（自动钩子）。
- [ ] 人工核对 spec 用户故事逐条。

**答复：** （实现后填）
