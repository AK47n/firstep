# 01 — 后端：/api/compile 平台自动推断

**要做什么：** 代码栏编译不必再传 platform——`POST /api/compile {output_dir}` 即可编译，平台由服务端从工程文件自动推断（.uvprojx → stm32，.cproject/.project → mspm0，与 /api/flash 同判据）；两个平台配置都存在或都没有 → 400 中文；显式传 platform 的既有行为不变。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 已落地。platform 可省略（缺省/空白 → context_manifest._infer_platform 推断，与 /api/flash 同判据）；ContextError 既有登记（400 表项）无需改动；docstring 契约同步；新增 5 项 pytest（stm32/mspm0 推断、空白推断、双配置/无配置 400、显式 platform 回归由既有用例覆盖），全量 pytest 3049 全绿。评审（Spec/Standards 双轴）无遗留项。

- [ ] 验收 1：webapp.py `/api/compile` 的 platform 改为可省略——缺省调 context_manifest._infer_platform(output_dir)（单源）；docstring 同步说明「platform 可省略，缺省自动推断」。
- [ ] 验收 2：ContextError（两者都有/都没有 → 400 中文）在 errors.py 已登记且顺序正确（未登记则补登记）；显式传 platform 时行为与现状完全一致（回归）。
- [ ] 验收 3：pytest——省略 platform 推断 stm32 一例、mspm0 一例；双平台/无平台配置 → 400 中文；显式 platform 回归；全量 pytest 绿。
- [ ] 验收 4：events.py 的 compile done 契约无变化（platform 只是请求侧可选），若 docstring 有契约描述同步更新。
