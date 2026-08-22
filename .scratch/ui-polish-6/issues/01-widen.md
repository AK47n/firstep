# 01 — 内容区加宽（生成页 1400 / 其它页 1280）

**要做什么：** main 980→1400px；非生成页 section 收窄 1280 居中；生成页卡片 padding 微调；验证宽屏无横向滚动。

**被谁阻塞：** 无。

**状态：** resolved

- [x] CSS：`main { max-width: 980px → 1400px; padding: 0 16px → 0 24px }`；`main > section.page:not(#tab-generate) { max-width: 1280px; margin: 0 auto }`
- [x] 生成页卡片 padding `16px 20px → 18px 24px`（`#tab-generate .gen-steps > .card`）
- [x] CDP 验证：1440 视口 gen=1352（main 1400 全宽，含 padding）/settings=1280 居中；1920 视口同值；两档均无横向滚动；卡片 padding=24px；截图目检（内容区占 ~94%、导航与内容 1:4 协调、无溢出）
- [x] js 84/84 + 契约 50/50
