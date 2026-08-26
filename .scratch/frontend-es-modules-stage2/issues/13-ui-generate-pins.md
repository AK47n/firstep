# 13 — 生成页 · 实例配置 + 引脚板图：static/js/ui/generate-pins.js

**要做什么：** generate tab 的「实例配置 + 引脚板图」大簇迁入 `static/js/ui/generate-pins.js`（实例增删/引脚绑定/板图 SVG 渲染/引脚卡/图例/概览环/角色菜单）。**被谁阻塞：** 02（app.js）

**状态：** resolved（2026-08-26；JS 442 全绿、pytest 2465 全绿、diag 零 EXC、smoke 11/11、probe-13 生成页实况 12/12）

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（3130-4012）：instList 3130 / renderInstanceConfig 3138 / instanceBlock 3185 / instanceRow 3206 / addInstance 3227 / delInstance 3236 / pickInstancePin 3244 / clearInstancePin 3251 / assignInstancePin 3260 / pinIndex 3330 / pinRoles 3336 / moduleColorMap 3348 / overviewRolesAt 3357 / overviewRing 3369 / overviewPie 3383 / pinSupports 3395 / roleInstances 3400 / pinIsTypeLevel 3408 / pwmRoleChannel 3420 / mspm0PwmAllowed 3425 / pinCanHost 3435 / pinListsType 3448 / pinMissReason 3454 / pinMacroFamilies 3471 / pinHint 3495 / renderPinCard 3502 / loadPinBoard 3550 / renderPinLegend 3565 / renderPinOverviewLegend 3578 / renderPinBoard 3591 / svgPin 3670 / renderPinRoles 3758 / unbindRole 3906 / bindRole 3913 / showPinMenu 3937。
- 状态：instances 2342 / instancePinTarget 2343 / pinBoard 3550 附近 / pinBindings / pinUnbound / pinShowOptional / pinHighlight / pinRotation / pinOverview + 常量 LED_COLORS / PIN_TYPE_STYLE / PIN_TYPE_ZH / MODULE_COLORS（grep 定位声明行，随迁）。
- 纯件曾迁：fx/module.js 已含 multiInstanceModules / instancePayload / ensureDefaultInstances（**参数化**版：instancePayload(expanded, instances) 等）——本簇胶水 import 传参；generateMain（工单 15）也用 instancePayload —— import。
- 跨簇：pinBound 状态由 renderSelected（A 簇）读取?（grep 复核；若 A 读，A import 本簇或本簇导出 getter）。

## 检查表

- [x] 新建 `static/js/ui/generate-pins.js`：上述函数+状态+常量逐字搬移 + import（app.js / fx/module.js / fx/core.js（esc））+ export（renderInstanceConfig / renderPinCard / loadPinBoard / bindRole / unbindRole / assignInstancePin / addInstance / delInstance + 4 接缝函数）+ 头部注释（状态所有权）
- [x] index.html：CRLF 感知行区间删除（6.5 簇头 → main.c 簇头，含 35 函数 + 13 状态/常量）+ 顶部 import 行追加
- [x] pin 数据流复核：generationOutputDirPayload / collectBindings（fx/generate.js）与本簇绑定收集的关系——主体调用点经 import 代理（见实施记录 4）
- [x] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 生成页实例/板图实况探针（渲染一次实例卡 + 板图 SVG + 绑脚一回）
- [x] grep 零残留：index.html 无 `function renderPinBoard(` 等定义 / 无 B 状态声明与裸赋值
- [x] 中文提交

## 实施记录

- **新增依赖/读点裁定（grep 复核后，后续工单必读）**：
  1. **host 对 B 状态的读点共 4 处** → host 顶部 import 活绑定：generateMain（instancePayload(expanded, instances)）/ renderGenerateSuccess（syncStep7 env 里 pinRoles() + pinBindings + instances）/ btn-generate（instancePayload + collectBindings(selectedSlugs, pinBindings, inst)）/ handoffPinLines（Object.entries(pinBindings) + [...pinUnbound]）。host 侧**零 B 状态写点残留**（唯一裸赋值处 = 原 setClusterDeps 7 项薄胶水，本票整体删除）。
  2. **pinBoard / pinBoardError / instancePinTarget / pinShowOptional / pinHighlight / pinRotation / pinOverview + LED_COLORS / PIN_TYPE_STYLE / PIN_TYPE_ZH / MODULE_COLORS 仅模块内使用**（grep 复核：host 无任何引用）——模块内加 `export` 标注（与状态声明同处），host import 行不含这些名，避免多余导出面。
  3. **工单 12 的 setClusterDeps 接缝 7 项全部静态化**：resetPinState / resetInstances / clearInstanceTarget / renderPinCard / renderInstanceConfig / loadPinBoard / backfillInstances——后三者原为 host 内联薄胶水（resetInstances 写 instances+instancePinTarget+调 renderInstanceConfig；clearInstanceTarget 单行；backfillInstances 循环映射），**提为本簇导出函数**；host 启动区 setClusterDeps 注册改为直接挂函数引用（shorthand `renderPinCard,`）。
  4. **pin 数据流复核**：collectBindings / instancePayload（fx/generate.js、fx/module.js）与本次迁移无耦合——host btn-generate 经既有 import（line 2226/2229）引用；本簇 btn-pin-auto 内引用 collectBindings（模块内 import /js/fx/generate.js）；generationOutputDirPayload 不读 B 状态；主体无裸引用本簇函数（均已 import 代理或随簇）。
  5. **结构钉重指向 1 文件**：tests/js/recommend-telemetry.test.mjs 的「btn-pin-auto 自动配置接线」断言（handler + `/api/bindings/auto`）→ ui/generate-pins.js；markup id 断言（`id="btn-pin-auto"`）仍指 index.html。
  6. **探针发现（非 bug，数据本身）**：led 在 stm32 无引脚角色（manifest pins=0，而其它模块如 adc=2 / motor=10）——角色区占位文案「所选模块在此平台没有可配置的引脚角色」是正确预期；probe-13 以 led 走实例卡+板图绑脚流程、以 adc 验证角色清单渲染。另注：SVG `circle` 无 `.click()`（SVGElement），探针用 `dispatchEvent(new MouseEvent("click", {bubbles:true}))`。

- **static/js/ui/generate-pins.js**（新建 949 行，LF）：35 函数 + 4 接缝函数逐字搬移（instList / renderInstanceConfig / instanceBlock / instanceRow / addInstance / delInstance / pickInstancePin / clearInstancePin / assignInstancePin / pinIndex / pinRoles / moduleColorMap / overviewRolesAt / overviewRing / overviewPie / pinSupports / roleInstances / pinIsTypeLevel / pwmRoleChannel / mspm0PwmAllowed / pinCanHost / pinListsType / pinMissReason / pinMacroFamilies / pinHint / renderPinCard / loadPinBoard / renderPinLegend / renderPinOverviewLegend / renderPinBoard / svgPin / renderPinRoles / unbindRole / bindRole / showPinMenu）；13 状态/常量随簇（instances / instancePinTarget / pinBoard / pinBoardError / pinBindings / pinUnbound / pinShowOptional / pinHighlight / pinRotation / pinOverview + 4 常量）；顶层 addEventListener（Esc 取消选脚 / btn-pin-reset / btn-pin-rotate / btn-pin-overview / btn-pin-auto）随迁（module 延迟执行，DOM 已就绪）。import：app.js（$ / apiGet / apiPost）/ fx/core.js（esc）/ fx/module.js（multiInstanceModules / ensureDefaultInstances）/ fx/generate.js（collectBindings）/ ui/step-state.js（syncStep7）/ ui/generate-recommend.js（chosenPlatform / expanded / selectedSlugs——A 簇活绑定只读，单向依赖无环）。导出面：状态 instances / pinBindings / pinUnbound + 函数 renderInstanceConfig / renderPinCard / loadPinBoard / bindRole / unbindRole / assignInstancePin / addInstance / delInstance / pinRoles + 4 接缝函数。头部注释（依赖 / 状态所有权 / 接缝说明）。
- **index.html（apply-13.mjs，5368→4481 行）**：①host import 行追加（11 名代理）；②全局状态段实例两行删除 + A 注记改口；③簇体 2313-3204 → 注记；④setClusterDeps 7 项薄胶水删除 + 注册改挂静态导出 + 注释改口；⑤generate-recommend.js 头部/回填注释同步改口。校验：35 函数零残留 + 13 状态/常量声明零残留 + B 状态裸赋值零残留（注释行豁免）。
- 验证：node --test 442 全绿（结构钉重指向 1 文件）；pytest 2465 全绿（bg）；diag 零 EXC；smoke 11/11；probe-13.mjs 12/12（generate-pins.js 动态 import 无语法错 / 平台卡点选→板图 SVG 渲染 32 引脚圆 + caption + 图例 / led 实例卡 3 行 / led 角色区占位 / adc 角色清单 2 项 / 选脚模式 32 候选圆 / PC13 绑脚一回 + 提示收起 / 全程零 EXC）。

## 风险点

- svgPin/renderPinRoles（大函数，~190 行）含 SVG 字符串拼接——逐字搬移（含模板字符串）；若内部用局部 esc 或局部 helper，照搬。
- showPinMenu 用 document.body.append + 全局点击关闭（top-level 或函数内绑定）——随迁后作用域不变。
- **（工单 12 修正）**「A 迁后 instances 属 B（本簇），A import 本簇读 instances；写点全在 B」**为错误**：A 有回填（renderRecommendResult→backfillInstances）与选脚目标清除（renderSelected/backfill→clearInstanceTarget / instancePinTarget=null）写点。工单 12 已把 A→B 写点收进 **generate-recommend.js 的 clusterDeps 接缝**（setClusterDeps 注册的薄胶水写 instances/instancePinTarget + 调 renderInstanceConfig / renderPinCard / loadPinBoard / resetPinState / resetInstances / clearInstanceTarget / backfillInstances）。**13 实施时**：把 host 启动区的 setClusterDeps 注册改为从 ui/generate-pins.js import 相应函数（或保留 host 胶水转调 import 名）；本簇函数导出面补 resetPinState / resetInstances / clearInstanceTarget / backfillInstances（若原为内联语句则提为函数）。16（updateFixCenterAvailability）/ 18（scheduleDraftSave）同理代入。—— **已实施（2026-08-26）**：接缝 7 项全部静态化（见实施记录 3）；16 / 18 迁出时按同法代入。
- **工单 15（generate-mainc）/ 16（fix）/ 18（steps 胶水）读点**：generateMain（instancePayload(expanded, instances)）与 btn-generate、renderGenerateSuccess、handoffPinLines 都是 host 经 import 活绑定读 B 状态（本票已代理）；16 / 18 迁出后改为 import 自 ui/generate-pins.js（或继续 host 代理转调）。
- **host 启动 renderPinCard()**（初始占位文案）已改为模块函数调用；后续任何 host 侧对 B 的**写**（如 16 的 updateFixCenterAvailability 若改绑定）须走本簇导出（resetPinState 等），禁止裸赋值 import 绑定。
