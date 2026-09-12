# 04 — 词汇表 / CHANGELOG / 全量回归

**要做什么：** 把这次确立的约定固化进领域文档，并跑全量回归确认没有把既有链路
（推荐 / 摘要行预算 / 缓存指纹 / 模块库页）踩坏。

**被谁阻塞：** 02、03。

**状态：** resolved

- [x] `CONTEXT.md`「简介」行补判据⑤：四拍书写顺序（这是什么 / 怎么接 / 怎么用 /
      什么时候用）+ 新增「模块说明」行（介绍文案单源 = manifest.description，
      前端只拆段不另写文案）。
- [x] CHANGELOG 条目（提交信息中文，post-commit 自动补录）。
- [x] 全量 `pytest` 绿（4161 passed，重点看推荐提示词预算、缓存指纹、库不变量）；
      `node --test "tests/js/*.test.mjs"` 绿（1481 passed）。
- [x] 手工取证：真实库 + 真实 `/api/modules` 载荷 → 渲染说明弹窗成可读文本核对
      （ir_beam / sr04 / pid 三件，四问分段与推荐理由都在位）。

**未做（如实记录）**：没有真浏览器点击验证。本仓库 `tests/js` 是纯函数 + 静态接线断言
（无 playwright/puppeteer，node_modules 未安装），故「点按钮 → 弹窗 → 不误移除模块」
的**运行时**行为由静态断言 + 代码审读覆盖（委托 + `stopPropagation` + `preventDefault`
三处都钉了测试），未做 CDP 真机点击。需要更强证据时：起服务后用浏览器手点一次
推荐 chip 上的「说明」。

