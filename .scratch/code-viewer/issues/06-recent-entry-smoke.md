# 06 — 最近记录卡「查看代码」入口 + CDP 全链路冒烟

**要做什么：** 学生打开工具，最近生成记录卡上一键进代码查看器；全链路自动冒烟证明 01–05 都能跑通。端到端：记录卡加「查看代码」小按钮（不触发整卡复制路径行为）→ 点击切到「代码」tab 并加载该 output_dir；CDP 冒烟脚本走完「打开 tab → 样本目录 → 树加载 → 大纲跳行 → 搜索跳转 → 最近卡按钮」全链路。

**被谁阻塞：** 04、05（入口依赖 openCodeViewer 桥；冒烟覆盖 05 的面板链路）。

**状态：** ready-for-agent

- [x] fx/recent.js recentChipHTML 加「查看代码」按钮（class .code-open-btn、data-dir、stopPropagation）；ui/recent.js 点委托加分支 → 调 openCodeViewer(dir)（经宿主层桥接，避免 ui 模块互相 import——实现期以现有模块约定为准）。
- [x] .scratch/code-viewer/smoke.mjs：CDP 冒烟（临时样本工程目录；树展开/点文件加载/大纲跳行/搜索命中跳转/最近卡按钮；不真生成、零写库）；冒烟清单保持全绿。
- [x] 全量回归：pytest 全量 + tests/js 全量绿。
