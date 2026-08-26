# 10 — 设置 tab + LLM 用量 + 工作流胶水：static/js/ui/settings.js

**要做什么：** 设置 tab 全部 DOM 胶水迁入 `static/js/ui/settings.js`（配置加载 / 视觉预设同步 / 环境检查 / 价格参考 / 周期占位 / 单价收集 + 设置折叠 glue + LLM 用量统计 + 最近工作流渲染）。本票依赖工单 01（fx/workflow.js 的 wfNum / formatWorkflow* 供渲染）。**被谁阻塞：** 01（fx/workflow.js）+ 02（app.js）

**状态：** resolved（2026-08-27；JS 442 全绿、pytest 2465 全绿、diag 零 EXC、smoke 11/11、probe-10 设置实况 5/5）

## 实施记录

- **static/js/ui/settings.js**（新建 ~470 行）：区段 A 全量逐字搬移——loadSettings / syncVisionProviderFromFields / applyVisionPreset / envCheckRun / renderPriceReference / periodPlaceholders / collectLlmPrices / renderRecentWorkflows / loadRecentWorkflows / **refreshState**（原 host 函数，唯一调用点 = 保存按钮，随本簇迁入）+ 状态（visionZhipuMask / visionApplyingPreset）+ 常量（VISION_PRESETS / VISION_HINTS）+ 8 组顶层监听（set-vision-provider / vision base+model / btn-vision-selfcheck / btn-env-check / set-local-llm-model / price-period 收音机 / btn-save-settings / btn-refresh-recent-wf）；区段 B = saveSettingsCollapse / initSettingsCollapse（嵌套 toggleSettingsCollapse 随宿主）。import app.js（$ / apiGet / apiPut / apiPost / setState / state）/ fx/{core,env,settings,workflow}.js / **ui/usage.js（llmPricesDefaults + setLlmPricesDefaults——单价表属 04 前置拆分模块，`export let + setter` 模式读写活绑定）/ **ui/generate-recommend.js（renderPlatforms / renderModulePool——refreshState 重渲染）。
- **跨簇接缝（新增，spec 未覆盖）**：refreshState 写宿主 `toolchains` + 调宿主 `renderToolchainStatus`（E 簇 16 迁 / 启动共用）→ settings.js 导出 `setSettingsDeps(deps)`；host 启动区注册 `setSettingsDeps({ applyToolchains: (ts) => { toolchains = ts; renderToolchainStatus(); } })`（一函数薄胶水）——16 迁出后改静态 import。
- **index.html（apply-10.mjs，5829→5427 行）**：①host import 行（settings 5 名代理 + 启动区接线）+ usage.js 代理行**裁至 renderUsageStats**（recordLLMUsage / llmPricesDefaults / setLlmPricesDefaults 自 12/10 后 host 零使用）；②refreshState 定义→注记；③设置页区段 A（设置页头 → btn-refresh-recent-wf 监听）→注记；④设置折叠区段（折叠头 → LLM 用量统计区段前）→注记；⑤setSettingsDeps 注册（setOnStepChange 之后）。校验：12 函数/状态零残留、host 保留 `loadSettings(); loadRecentWorkflows(); renderUsageStats();` + `initSettingsCollapse();` + 接缝注册、setLlmPricesDefaults 调用点零残留。
- 验证：node --test 442 全绿（price-reference-clear 函数体断言 + recent-workflows 的 recent 端点断言重指向 settings.js——按归属复核；前者 tbody markup 断言仍钉 host）；pytest 2465 全绿（bg）；diag 零 EXC；smoke 11/11；probe-10.mjs 5/5（切 tab → loadSettings + loadRecentWorkflows + renderUsageStats → 表单回填（base_url / model / config-path）+ 价格表 3 行 + 控件齐 + 工作流空态 → 折叠 10 卡 / 9 带按钮 / 总开关「全部收起」→ 视觉预设切智谱（base_url + hint 联动）→ 零 EXC）。

## 检查表

- [x] 新建 `static/js/ui/settings.js`：区段 A/B 全部函数与常量逐字搬移 + import（app.js / fx/{settings,generate? 无}/ fx/env.js / fx/settings.js / fx/workflow.js / ui/usage.js / ui/generate-recommend.js）+ export（loadSettings / loadRecentWorkflows / initSettingsCollapse / renderPriceReference / setSettingsDeps）+ 头部注释
- [x] index.html：apply-10.mjs（CRLF 感知 4 段删除 + import 行 + usage 代理行裁剪 + 接缝注册）
- [x] price-reference-clear / recent-workflows 结构钉重指向 ui/settings.js
- [x] `node --test` 442 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + probe-10 设置实况 5/5
- [x] grep 零残留：index.html 无 12 函数定义 / 无 vision 状态 / 无 setLlmPricesDefaults 调用
- [x] 中文提交

## 风险点 / 跟踪

- **host import 代理 5 名**：loadSettings / loadRecentWorkflows（tab 分发器）/ initSettingsCollapse（启动区）真实使用；renderPriceReference / setSettingsDeps——前者本票起 host 不直调（模块内 loadSettings 使用，导出供结构与收尾核对），后者只在启动区注册处使用——收尾工单 20 统一核对裁代理。
- **refreshState 归属变更**：随本簇迁入 settings.js；其宿主写入（toolchains / renderToolchainStatus）经 setSettingsDeps 接缝——**18（steps 胶水）与 16（fix）注意**：refreshState 现属 settings，D/E/F 无直接调用点（仅保存按钮）；16 迁出 fix 簇后 at setSettingsDeps 注册改静态 import 自 fix 模块。
- **fx 代理行零使用清单增补**：host 的 fx/settings.js / fx/workflow.js / fx/env.js / fx/llm.js（formatLLMTelemetry 等——自 12 后 host 零使用）自本票起零使用；usage.js 已裁至 renderUsageStats——20 收尾统一核对。
- **window.__priceRef**：renderPriceReference / periodPlaceholders 经 window 缓存共享（原样保留）——跨模块边界内的既定全局缓存点，非 ESM 边界问题。
