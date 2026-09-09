# 01 — adc 模块落地（双平台）

**要做什么：** 模块库出现 adc（模拟采样）模块：stm32 平台条目 files 空（内嵌母版 ml_adc，骨架经母版接口块获得 adc_init/adc_get）、mspm0 平台条目带自有封装（code/adc_mspm0.c/h，从 ADC12 driverlib 例程提炼，API 名对偶）；manifest 声明 adc 引脚角色（含默认脚）；推荐链路自动命中、平台警告机制照常；结构测试与骨架接口块测试通过。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 模块库 library/modules/adc/manifest.json 可被解析（slug/描述四要素/pins 校验通过），stm32 条目 files 空、mspm0 条目 files 含 adc_mspm0.c/h
- [x] adc_mspm0.c/h 提供与 ml_adc 对偶的 adc_init/adc_get API（从参考库 ADC12 单次转换例程提炼，单次转换 + 轮询读取）
- [x] 双平台 pins 声明 adc 角色与默认脚（stm32 PA0/PA1 等，mspm0 按板定义），板图可绑、绑定渲染（pin_config.h / syscfg $assign）正常
- [x] 结构测试：manifest 形状 / 描述无题绑定 / API 对偶断言（双平台同名函数机械提取比对）
- [x] build_skeleton_interfaces 选中 adc 后接口块含 adc_init/adc_get（stm32 经母版接口块、mspm0 经模块头）
- [x] 全量测试通过


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
