# 01 — 硬件身份字段 + 新录入强制

**What to build:** 模块库的每个平台条目都能携带硬件身份——套件型号（kit）与购买链接（source_url）。新录入模块、或给已有模块新增平台版本时，身份字段必填且链接格式合法，不满足则拒绝入库且不留任何半成品；存量没有身份字段的模块照常读取，不破坏现有库。录入/浏览的 API 透传新字段。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] 录入新模块不带 kit / source_url → 拒绝入库，给出明确中文错误说明（工单 06 修订：强制收窄为仅 hardware_bound=True 条目；纯逻辑条目免填、提供值仍校验）
- [x] source_url 格式非法（无 scheme、无主机等）→ 拒绝入库
- [x] 身份字段合法 → 正常入库，manifest 落盘包含新字段
- [x] 给已有模块新增平台版本时同样强制（缺身份 → 拒绝；06 起按 hardware_bound 判定）
- [x] 存量无身份字段的 manifest 仍能正常加载、浏览、编辑（迁移不打断现有库）
- [x] 模块列表 API 返回新字段
- [x] 校验拒绝后磁盘无残留（沿用"任何校验失败都在落盘前"不变量）

## Comments

- 2026-08-07 补标 resolved：本工单功能随工单 02/03/05/06 一并落地并合入 main——
  `PlatformEntry.kit/source_url` 字段 + `from_dict` 缺省容忍 + `add_module`/
  `add_platform_files` 强制校验 + `update_platform_identity` 存量补填路径 +
  webapp 透传与列表返回。强制范围被工单 06 收窄为仅硬件绑定条目
  （`hardware_bound=True`），纯逻辑条目（zone/pid/filter 等）免填身份字段、
  由简介专用性标注承担身份——纯逻辑提供身份值仍须合法（给了就要给对）。
  工单 05 真机迁移实录了用户补填 ml_mpu6050/motor/uwb_uart 身份字段。
  因 06 收窄属同源演进，本工单不再单独立实施提交。

