# 02 — Keil 工程修改器

**What to build:** 用户选 STM32 最小系统板生成工程时，产出物是 Keil5 中打开就能编译的完整工程：所选模块的源文件注册进工程树，include path 已填好，用户可直接在此基础上写代码。

**Blocked by:** 01 — 生成器核心骨架 + fixture 测试基座

**Status:** ready-for-agent

- [ ] 解析并改写 .uvprojx：所选模块的源文件注册进工程，include path 加入模块头文件所在目录
- [ ] 不破坏母版原有配置（设备型号、烧录设置等）
- [ ] fixture 母版下测试：生成的工程配置内容正确（pytest 断言）
- [ ] 真实工程在 Keil5 中编译通过（由用户验证一次）
- [ ] 重复生成幂等：同一输入两次生成，工程配置一致
