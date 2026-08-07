# 07 — 补录 zone（区域判定），恢复 lock_control 可选

**What to build:** 把 zone 模块补录进模块库，解除 lock_control 的孤儿依赖——补录后选 lock_control 不再报"依赖 zone 不存在"（UnknownModuleError）。zone 源码在 `Desktop/2026C/code/zone.c/h`（2026C 数字钥匙题）：输入距离/方位角，滞回判定感应区/迎宾区/开锁区（ZONE_NONE/SENSING/WELCOME/UNLOCK）。纯逻辑模块（hardware_bound=False），依赖为空（只 include 母版功能库 headfile.h），**免身份字段**（工单 06 修订）。

简介按三要素：功能（UWB 距离/方位角滞回区域判定）+ 专用性标注"2026C 数字钥匙题专用"（用户确认）+ 一致性由真实 AI 校验兜底。

**Blocked by:** 06 — 身份字段强制收窄为仅硬件绑定条目（已完成）

**Status:** resolved

- [x] zone 以 stm32 平台真实录入入库（真实 HTTP 层 + 真实 DeepSeek，先例 `.scratch/real-run/module_import.py`），manifest：简介含"2026C 数字钥匙题专用"标注、依赖为空、hardware_bound=false
- [x] 用户逐条确认简介内容与专用性标注
- [x] 真机验证：选择 lock_control 依赖解析成功带出 zone，不再报 UnknownModuleError
- [x] 迁移记录写进本工单 Comments 并标 resolved

## Comments

- 2026-08-07 建单：grilling 划出本工单为独立补录（源码 2026C/code/zone.c/h 仍在）；
  等待工单 06 修订（纯逻辑免身份字段）后方可无身份入库。
- 2026-08-07 工单 07 完成（分支 ticket-module-desc-07，未合并）。真实录入 + 真机验证：
  - 启动真实应用 `uvicorn contest_generator.webapp:app`（127.0.0.1:8000，真实 DeepSeek
    已配置），走真实 HTTP 层 POST /api/modules。
  - AI 草稿："该模块根据距离和方位角（FOV内）判断目标所在区域（无/感应/迎宾/开锁），
    并通过滞回比较防止边界抖动。"——功能三要素齐全。
  - 用户确认：合并版简介（草稿 + 专用性标注）——"2026C 数字钥匙题专用：该模块根据
    距离和方位角（FOV内）判断目标所在区域（无/感应/迎宾/开锁），并通过滞回比较防止
    边界抖动。"（AskUserQuestion 确认，用户已口头同意"2026C 数字钥匙题专用"）。
  - 真实一致性校验通过后入库：slug=zone、platform=stm32、dependencies=[]、
    hardware_bound=false（纯逻辑，工单 06 规则）、verified=false、无 kit/source_url。
    源码 2026C/code/zone.c/h 经 GBK→UTF-8 统一转码入库；磁盘 manifest 为合法 UTF-8，
    与确认文本逐字一致（zone_draft.txt / zone_disk_check.txt 存档于 .scratch/real-run/）。
  - 真机验证：POST /api/selection/expand {stm32, [lock_control]} → 解析出
    ['zone', 'lock_control']，不再报 UnknownModuleError；仅预期 unverified 警告
    （新录入未验证，属正常；无 hardware_bound 警告，两模块均纯逻辑）。
