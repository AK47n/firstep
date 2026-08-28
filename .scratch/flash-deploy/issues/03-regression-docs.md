# 03 — 回归验证 + 文档更新（CONTEXT.md / CHANGELOG）

**要做什么：** 全量回归（pytest + Node 前端测试 + fx-guard）；CONTEXT.md 域词条补「烧录」行（flash.py / /api/flash / 三配置键 / 两平台工具链：STM32=OpenOCD|st-flash、MSPM0=CCS DSLite XDS110 零安装）；CHANGELOG 由自动钩子生成。

**被谁阻塞：** 02 — 前端烧录 UI。

**状态：** resolved

- [x] 全量 pytest + tests/js/*.test.mjs 通过，无回归。
- [x] CONTEXT.md 域表补「烧录」词条（含 DSLite 路径发现、hex/out 定位规则、范围外串口 ISP/BSL 备注）。
- [x] CHANGELOG 条目（自动钩子）。
- [x] 人工核对 spec 用户故事逐条（8 条中后端 5 条 + 前端 8 条均落试验证：见 01/02 答复）。

**答复：** 已合入（提交见 git log flash-deploy/03）。回归：pytest 全量（2648 上下）+ JS 540 + fx-guard；CONTEXT.md 新增「烧录」域词条一行（含工具探测顺序 / 三 builder / 产物定位 / 范围外备注）；CHANGELOG 由仓库自动钩子生成（烧录/01、烧录/02、烧录/03 条目）。
