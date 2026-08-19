# 02 — Keil 工程修改器

**What to build:** 用户选 STM32 最小系统板生成工程时，产出物是 Keil5 中打开就能编译的完整工程：所选模块的源文件注册进工程树，include path 已填好，用户可直接在此基础上写代码。

**Blocked by:** 01 — 生成器核心骨架 + fixture 测试基座

**Status:** resolved

- [x] 解析并改写 .uvprojx：所选模块的源文件注册进工程，include path 加入模块头文件所在目录
- [x] 不破坏母版原有配置（设备型号、烧录设置等）
- [x] fixture 母版下测试：生成的工程配置内容正确（pytest 断言）
- [ ] 真实工程在 Keil5 中编译通过（由用户验证一次）— 用户手工验证点，AI 替不了（见 RUNBOOK 手工验证点表）
- [x] 重复生成幂等：同一输入两次生成，工程配置一致

## Comments

- 2026-08-05: 工单 02 完成（提交 b8095b2 之后的下一提交）。默认注册表 stm32 → KeilPatcher；母版缺 .uvprojx / 多个 .uvprojx / 非法 XML / 无 Target / 缺 IncludePath 节点时都报错拒绝生成，不产出残缺工程。唯一未勾项为 Keil5 真实编译验证，等待用户手工执行。
