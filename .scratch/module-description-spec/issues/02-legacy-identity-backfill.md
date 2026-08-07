# 02 — 存量身份补填编辑路径

**What to build:** 能给存量模块的平台条目补填 / 修改 kit 与 source_url——这是用户在迁移工单里补身份字段的入口。编辑只做格式校验，不触发 AI 一致性校验（硬件身份是事实信息，AI 判不了真假）；改完立即生效，模块列表可见。

**Blocked by:** 01 — 硬件身份字段 + 新录入强制

**Status:** resolved

- [x] 通过编辑路径给存量平台条目补填 kit / source_url → 保存成功，列表数据可见
- [x] 补填的 source_url 格式非法 → 拒绝并给出明确错误
- [x] 编辑身份字段不触发 AI 一致性校验（FakeLLM 无校验调用记录）
- [x] 只改身份字段不影响平台条目的其他字段（文件列表、验证状态、硬件绑定）

## Comments

- 2026-08-07 工单 02 完成（分支 ticket-module-desc-02，feat 1b9afbf，已合 main）。
  实现：库层 `update_platform_identity`——只改身份字段（kit 非空、source_url URL
  格式校验，不走 AI 一致性校验）+ `PUT /api/modules/{slug}/platform-identity`
  端点 + 库层/webapp 共 16 例测试。
- 并发事故：工单 03 会话在共享检出里 `git checkout -b` 时 HEAD 停在 02 分支上，
  02 提交一度落在 03 分支——无损修复（02 当时 = main 尖），先合 02 再合 03
  fast-forward 收尾，文件边界核实无重叠。
