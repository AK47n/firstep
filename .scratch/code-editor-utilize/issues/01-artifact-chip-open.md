# 01 — 结果区产物 chips 直开代码 tab（打开桥支持指定文件）

**要做什么：** 生成页结果区的自动附带产物 chips（设计报告草稿.md / 演示脚本.md）点击后在「代码」tab 打开该文件（目录 + 文件一并就位），不再只复制路径。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 打开桥支持第二参数：openCodeViewer(dir, filePath)——filePath 非空时目录加载完成即打开该文件
- [x] 结果区产物 chips 点击 = 在代码 tab 打开该文件（md 默认预览态可切编辑），chip 提示文案更新
- [x] 无产物时 chips 区保持隐藏（现状不变）
- [x] 冒烟：smoke-01.mjs 全绿（桥打开产物标签 + 子目录文件 + md 预览渲染）

## Answer

- 已验证：smoke-01.mjs 5 项全绿；node --test tests/js/*.test.mjs 1085 全绿；双轴评审通过（Spec 轴无缺失，Standards 轴无硬违规；评审整改见 03/04 工单）。
