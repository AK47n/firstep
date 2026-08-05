# 03 — CCS 工程修改器

**What to build:** 用户选地猛星开发板生成工程时，产出物是 CCS 中打开即可编译的完整工程：include path 已填好，模块源文件就位。

**Blocked by:** 01 — 生成器核心骨架 + fixture 测试基座

**Status:** done

- [x] 改写 .cproject：include path 正确写入所选模块头文件所在目录
- [x] 模块源文件复制到工程对应目录，CCS 工程树中可见
- [x] fixture 母版下测试：生成的工程配置内容正确（pytest 断言）
- [ ] 真实工程在 CCS 中编译通过（由用户验证一次）— 用户手工验证点，AI 替不了（见 RUNBOOK 手工验证点表）
- [x] 重复生成幂等：同一输入两次生成，工程配置一致

## Comments

- 2026-08-05: 工单 03 完成。默认注册表 mspm0 → CcsPatcher（NullPatcher 占位移除）。与 Keil 的结构差异已记录在 ccs.py 模块文档：.cproject 不逐文件枚举源文件，修改器只做两件事——把模块目录追加进每个 build configuration 的 buildIncludePath 选项（${PROJECT_LOC}/ 前缀），保证 modules/ 被 sourceEntry 覆盖（母版已有根条目时不新增）。母版缺 .cproject / 多个 .cproject / 非法 XML / 无 build configuration / 缺 buildIncludePath 选项时都报错拒绝生成。唯一未勾项为 CCS 真实编译验证，等待用户手工执行。
