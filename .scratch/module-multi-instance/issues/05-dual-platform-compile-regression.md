# 05 — 双平台编译回归（1/2/4 灯 + 旧单实例）

**What to build:** led 多实例 1/2/4 个灯在 stm32 UV4 与 mspm0 gmake 真编译 0 error、
0 module warning；旧单实例 led 产物与基线逐字节 diff 为空。这是全功能的关门验收票。

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] 1 灯 / 2 灯 / 4 灯三档，stm32 UV4 真编译 0 error、0 module warning
- [ ] 1 灯 / 2 灯 / 4 灯三档，mspm0 gmake 真编译 0 error、0 module warning（syscfg ovsRate 基线 warning 允许并记录）
- [ ] 4 灯覆盖内置色 + 重复色 + 非内置色，产物里通道宏 / pin 宏 / 初始化逐项核对
- [ ] 旧单实例 led 产物与基线逐字节 diff 为空（红证先行，`pinwriter` 不变不写契约兜底）
- [ ] pytest 全绿 + mypy src 干净
- [ ] 编译结果留痕到 `.scratch/module-multi-instance/`（build log 本地证据）
