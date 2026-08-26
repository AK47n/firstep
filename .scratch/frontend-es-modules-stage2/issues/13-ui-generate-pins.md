# 13 — 生成页 · 实例配置 + 引脚板图：static/js/ui/generate-pins.js

**要做什么：** generate tab 的「实例配置 + 引脚板图」大簇迁入 `static/js/ui/generate-pins.js`（实例增删/引脚绑定/板图 SVG 渲染/引脚卡/图例/概览环/角色菜单）。**被谁阻塞：** 02（app.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（3130-4012）：instList 3130 / renderInstanceConfig 3138 / instanceBlock 3185 / instanceRow 3206 / addInstance 3227 / delInstance 3236 / pickInstancePin 3244 / clearInstancePin 3251 / assignInstancePin 3260 / pinIndex 3330 / pinRoles 3336 / moduleColorMap 3348 / overviewRolesAt 3357 / overviewRing 3369 / overviewPie 3383 / pinSupports 3395 / roleInstances 3400 / pinIsTypeLevel 3408 / pwmRoleChannel 3420 / mspm0PwmAllowed 3425 / pinCanHost 3435 / pinListsType 3448 / pinMissReason 3454 / pinMacroFamilies 3471 / pinHint 3495 / renderPinCard 3502 / loadPinBoard 3550 / renderPinLegend 3565 / renderPinOverviewLegend 3578 / renderPinBoard 3591 / svgPin 3670 / renderPinRoles 3758 / unbindRole 3906 / bindRole 3913 / showPinMenu 3937。
- 状态：instances 2342 / instancePinTarget 2343 / pinBoard 3550 附近 / pinBindings / pinUnbound / pinShowOptional / pinHighlight / pinRotation / pinOverview + 常量 LED_COLORS / PIN_TYPE_STYLE / PIN_TYPE_ZH / MODULE_COLORS（grep 定位声明行，随迁）。
- 纯件曾迁：fx/module.js 已含 multiInstanceModules / instancePayload / ensureDefaultInstances（**参数化**版：instancePayload(expanded, instances) 等）——本簇胶水 import 传参；generateMain（工单 15）也用 instancePayload —— import。
- 跨簇：pinBound 状态由 renderSelected（A 簇）读取?（grep 复核；若 A 读，A import 本簇或本簇导出 getter）。

## 检查表

- [ ] 新建 `static/js/ui/generate-pins.js`：上述函数+状态+常量逐字搬移 + import（app.js / fx/module.js / fx/core.js（esc））+ export（renderInstanceConfig / renderPinCard / loadPinBoard / bindRole / unbindRole / assignInstancePin / addInstance / delInstance）+ 头部注释（状态所有权）
- [ ] index.html：CRLF 感知行区间删除（3130-4012 内目标名；**物理升序**）+ 顶部 import 行追加
- [ ] pin 数据流复核：generationOutputDirPayload / collectBindings（fx/generate.js）与本簇绑定收集的关系——若主体调用点裸引用本簇函数，import 代理
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 生成页实例/板图实况探针（渲染一次实例卡 + 板图 SVG）
- [ ] grep 零残留：index.html 无 `function renderPinBoard(` 等定义
- [ ] 中文提交

## 风险点

- svgPin/renderPinRoles（大函数，~190 行）含 SVG 字符串拼接——逐字搬移（含模板字符串）；若内部用局部 esc 或局部 helper，照搬。
- showPinMenu 用 document.body.append + 全局点击关闭（top-level 或函数内绑定）——随迁后作用域不变。
- 本簇与 A 簇共享 expanded/instances 等状态：A 迁后 instances 属 B（本簇），A import 本簇读 instances；**写点全在 B** → 归属成立。
