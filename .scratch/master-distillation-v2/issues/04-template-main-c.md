# 04 — 模板 main.c：母版自带最小系统板空 main

**What to build:** 提炼落盘后母版写入**确定性模板 main.c**（非 AI 生成）：各平台一个空工程 main（时钟初始化 + while(1) 空循环 + TODO 区），能直接编译烧录；旧工程里的 main.c 一律不进母版（ADR 0002）。生成器仍会在生成时用按赛题的 AI 骨架覆盖它（generator.py 现状，不改）。

**Blocked by:** 无（独立，可与 01 并行）

**Status:** open

- [ ] stm32 / mspm0 各一份模板 main.c（最小系统板空工程，可编译）
- [ ] apply_distillation 落盘后写模板 main.c；旧工程 main.c 不复制进母版
- [ ] 母版候选含模板 main.c 后，analyze_structure 仍通过（IDE 可打开）
- [ ] 测试：提炼出的母版含模板 main.c、不含任何旧 main.c；模板 main.c 与平台匹配
