# 03 — CCS 工程修改器

**What to build:** 用户选地猛星开发板生成工程时，产出物是 CCS 中打开即可编译的完整工程：include path 已填好，模块源文件就位。

**Blocked by:** 01 — 生成器核心骨架 + fixture 测试基座

**Status:** ready-for-agent

- [ ] 改写 .cproject：include path 正确写入所选模块头文件所在目录
- [ ] 模块源文件复制到工程对应目录，CCS 工程树中可见
- [ ] fixture 母版下测试：生成的工程配置内容正确（pytest 断言）
- [ ] 真实工程在 CCS 中编译通过（由用户验证一次）
- [ ] 重复生成幂等：同一输入两次生成，工程配置一致
