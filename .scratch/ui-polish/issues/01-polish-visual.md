# 01 — 全局动效与质感打磨（A 档）

**要做什么：** 用户打开任意页面都能感受到精致的交互反馈——按钮 / 卡片 / 输入框悬停有平滑过渡，主按钮有渐变与微光，步骤徽章有层次感，库页面空列表有友好引导。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**完成记录：** 全局 transition（按钮/输入框/卡片/条目类）、.primary 渐变+微光+按压缩放、.card hover 上浮提亮、.step-no 渐变发光、品牌字呼吸光晕（brand-breathe，不动 .cursor）；6 处空状态升级（模块库新增兜底 colspan=5，参考库/PDF 库/赛题库/更新记录/最近工作流换 .empty-state 样式）。node --test tests/js/*.test.mjs 49/49 通过；pytest tests/test_generate_check_contract.py 50/50 通过；无头 Edge 截图目检无异常。

- [ ] 全局按钮 / 卡片 / 输入框加 transition（约 0.15s），hover 不再瞬间跳变
- [ ] `.primary` 按钮改青色渐变 + hover 微光（box-shadow glow）
- [ ] `.card` hover 边框提亮 + 轻微上浮（translateY(-1px)）；现有 .item/.score-panel 同步
- [ ] `.step-no` 徽章改渐变背景 + 发光描边
- [ ] 顶栏品牌字加呼吸光晕动画（不动 .cursor 现有闪烁）
- [ ] 新增空状态样式（.empty-state：图标 + 文案 + 引导按钮），并在模块库 / 参考库 / PDF 库 / 赛题库空列表处生效
- [ ] 卡片间距 / 标题层级微调
- [ ] `node tests/js/*.test.mjs` 与契约钉测试全绿
