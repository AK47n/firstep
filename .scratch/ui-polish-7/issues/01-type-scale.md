# 01 — 字号阶梯美化（品牌 20 / 卡片标题 16 / 正文 14）

**要做什么：** 按新阶梯调整 font-size：h1 18→20、card h2 15→16、正文级 13→14（label/textarea/error/banner/item reason/warn-box/pin-intro/decision 行）。密集数据区不动。

**被谁阻塞：** 无。

**状态：** resolved

- [x] header h1 18→20px；.card h2 15→16px
- [x] 正文级 13→14px：label / textarea / .error / .banner / .item .reason / .warn-box / .pin-intro / .decision 行
- [x] CDP 验证：h2=16、label=14、textarea=14、.error=14；改前/改后截图对比目检（题面输入框、main.c、模块清单、决策行）
- [x] js 84/84 + 契约 50/50

**备注（2026-xx-xx 收尾）：** 本工单完成后未及时标记，现统一改 resolved 并提交（实现提交 dc25878；代码现状 index.html header h1 20px：112 行、.card h2 16px：160 行）。
