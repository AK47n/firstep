# 07 — 补录 zone（区域判定），恢复 lock_control 可选

**What to build:** 把 zone 模块补录进模块库，解除 lock_control 的孤儿依赖——补录后选 lock_control 不再报"依赖 zone 不存在"（UnknownModuleError）。zone 源码在 `Desktop/2026C/code/zone.c/h`（2026C 数字钥匙题）：输入距离/方位角，滞回判定感应区/迎宾区/开锁区（ZONE_NONE/SENSING/WELCOME/UNLOCK）。纯逻辑模块（hardware_bound=False），依赖为空（只 include 母版功能库 headfile.h），**免身份字段**（工单 06 修订）。

简介按三要素：功能（UWB 距离/方位角滞回区域判定）+ 专用性标注"2026C 数字钥匙题专用"（用户确认）+ 一致性由真实 AI 校验兜底。

**Blocked by:** 06 — 身份字段强制收窄为仅硬件绑定条目（已完成）

**Status:** ready-for-agent

- [ ] zone 以 stm32 平台真实录入入库（真实 HTTP 层 + 真实 DeepSeek，先例 `.scratch/real-run/module_import.py`），manifest：简介含"2026C 数字钥匙题专用"标注、依赖为空、hardware_bound=false
- [ ] 用户逐条确认简介内容与专用性标注
- [ ] 真机验证：选择 lock_control 依赖解析成功带出 zone，不再报 UnknownModuleError
- [ ] 迁移记录写进本工单 Comments 并标 resolved

## Comments

- 2026-08-07 建单：grilling 划出本工单为独立补录（源码 2026C/code/zone.c/h 仍在）；
  等待工单 06 修订（纯逻辑免身份字段）后方可无身份入库。
