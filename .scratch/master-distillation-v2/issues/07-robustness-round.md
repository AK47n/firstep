# 07 — 判定范围单一来源 + 残留规则完备 + .uvprojx 子目录解析

**What to build:** 母版提炼 v2 落地后的第一轮加固。ticket 06 把公共文件放进 AI 判定时，判定范围 / 判据同时硬编码在系统提示词与用户提示词里——06 曾只改系统提示词、漏改用户提示词，模型按用户消息跳过公共文件，多工程提炼当场失败（"提炼报告缺少判定"）。且真实旧工程（正点原子风格）还会带出两类问题：Keil 默认输出目录 Listings/Objects 未忽略、`.uvprojx` 位于子目录（USER/）时引用路径解析错基准。改造三点：

1. **判定范围 / 判据单一来源**：新增 `JUDGMENT_SCOPE` 常量，系统提示词与用户提示词都引用它（各自动词、格式说明仍各自保有）；契约测试双端断言"范围 / 判据表述都在"。用户提示词去掉已过时的"公共文件已确定保留，不在判定范围内"。
2. **残留规则完备**：`BUILD_ARTIFACT_DIRS` 增加 Listings/Objects（Keil 默认输出目录，整目录忽略；裸 `.d` 依赖文件由此覆盖，不进 RESIDUE_RULES——`.ld`/`.cmd` 以 .d 结尾，放进名单会把链接脚本截胡成残留）；`RESIDUE_RULES` 增加 .lst / .htm / .crf / .dep / .lnp / .out / .elf。
3. **`.uvprojx` 子目录引用解析**：`rewrite_project_references` 的 FilePath 相对 .uvprojx 所在目录（如 USER/proj.uvprojx 里 `.\..\sys\delay.c` = 工程根 sys/delay.c）——新增 `_resolve_root_path` 按 .uvprojx 所在目录解析回工程根相对路径再匹配保留集合（越界 `..` 返回 None 保守删除），`_keil_rel_path_from` 回算 main.c 重定向目标（模板落位在工程根）。

**Blocked by:** 无

**Status:** resolved

## Answer

- [x] 契约测试：JUDGMENT_SCOPE 双端引用断言
- [x] master.py：Listings/Objects 目录忽略（任意层级）、RESIDUE_RULES 扩充
- [x] keil.py：_resolve_root_path / _keil_rel_path_from，子目录 uvprojx 场景
- [x] 全套测试绿（367）
- [x] code-review 双轴通过，发现修复：① Spec 轴——Listings/Objects 顶层忽略挡不住 USER/ 下产物，_is_ignored 改任意层级组件匹配 + 回归测试；② Standards 轴——"裸 .d 截胡 .ld/.cmd"注释理由编造（endswith 整段比较不会误伤），改写真理由；③ 判据措辞与 ADR 0001 对齐（补回"是否通用"）；④ CONTEXT.md 词表同步（提炼判定范围 / 残留清单）
