# 06 — 公共文件进 AI 判定 + 判据收紧 + 配置引用自动重写

**What to build:** 母版提炼现状：公共文件（所有工程内容一致）自动保留、不进 AI 判定——这与 ADR 0001（判据唯一 = 读内容判断基础建设必需，不看重复次数/出现范围）、ADR 0002（母版 = 空的最小系统板工程，业务 .c/.h 一律剔除）和用户要求（AI 逐个检测必要性）矛盾。改造三点：

1. **公共文件进 AI 判定**（判定范围 = 公共 + 冲突 + 独有）：公共文件 AI 判 keep（默认倾向）/ exclude 都合法，删掉"内容一致 → 自动保留"与"公共文件必须保留"的硬校验；merge 仍禁（无多份内容，词表校验兜底）。
2. **判据收紧为"基础建设必需"**：DISTILL prompt 明确——官方外设库（stm32f10x_* 全家 / TI driverlib）+ 平台基础设施 + 通用基础封装（SYSTEM delay/sys/usart）→ keep；具体项目/具体硬件相关（传感器驱动、外设封装、赛题逻辑），即使所有工程共享 → exclude。
3. **落盘时自动重写 .uvprojx 引用**：剔除文件的引用条目删除，main.c 条目统一指向模板落位（母版根）；保证"打开就能编译烧录"成立，不做人工处理。CCS（.cproject 按目录编译）不用动。

**Blocked by:** 无

**Status:** resolved

## Answer

- [x] grill-with-docs 会话达成共享理解（判定范围 / 判据 / 配置重写 / 素材范围 / 母版落库）
- [x] master.py：judgment 范围含公共（compare_projects）、assemble_report 去"内容一致自动保留"（公共 keep/exclude 都合法，merge 词表校验兜底）、_validate_report 覆盖校验调整、apply_distillation 落盘后调配置重写（仅 stm32；CCS 按目录编译天然一致）
- [x] keil.py：rewrite_project_references——删除引用但不在保留集的 File 条目 + main.c 条目重定向到模板落位（母版根）；无实际改动不写回（保持 AI 整合产物原样）
- [x] llm.py：DISTILL prompt 判据收紧为"基础建设必需"（官方外设库 / 基础设施 / 基础通用封装 keep；项目特定业务代码 exclude；公共文件同样逐个判）
- [x] 测试：公共进素材、公共 AI exclude 合法、公共 merge 仍禁、配置引用重写、CCS 全公共补判定；全套 356 绿
