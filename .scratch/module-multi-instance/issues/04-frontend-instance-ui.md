# 04 — 前端实例配置 UI（列表 / 命名 / 颜色 / 引脚）

**What to build:** index.html 上支持多实例的模块（led）显示「添加实例 / 删除实例 /
编辑显示名 / 选颜色 / 绑引脚」；用户手动增删改后装配进生成请求的 `instances` 载荷。
旧单选 UI 与旧请求行为不变。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] 多实例模块卡片渲染实例列表，每实例可改显示名（自由中文）、选颜色、绑引脚（复用现有板图绑定）
- [ ] 添加/删除实例，数量上限 8，超限禁用并提示
- [ ] 装配：前端把实例清单编进 `/api/generate`（及 `/api/skeleton`）请求的 `instances` 字段
- [ ] 旧单选模块 / 旧请求无 `instances` = 现行为，UI 与产物不破
- [ ] 手动绑定的引脚冲突沿用现有前端提示语义（不新增后端 400 之外的行为）
- [ ] 与主链并行时用独立 worktree（[[parallel-tickets-shared-checkout-race]]），只提交本票前端文件
