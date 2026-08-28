# 03 — 修复：「去设置页配置」跳转后看不到烧录工具

**要做什么：** 点击指引卡「去设置页配置」→ 切到设置页 + 展开默认折叠的「工具链」卡（烧录工具输入框所在，`SETTINGS_DEFAULT_COLLAPSED` 含 toolchain）+ 滚动到烧录工具输入区（按平台定位 dslite/openocd 字段）。

**被谁阻塞：** 无。

**状态：** resolved

**根因（已复现实证）：** 点击链本身正常（playwright 探针：注入 `flashGuideHTML` 按钮 → document 委托 → `tab.click()` → `#tab-settings` active ✓）。但设置页「工具链」卡（data-collapse-id="toolchain"，index.html:2245-2271 内含「烧录工具」小节）在 `SETTINGS_DEFAULT_COLLAPSED` 默认集（fx/settings.js:11-12）中——切过去后卡片折叠，用户看不到烧录工具输入框，误以为「没跳转」。

- [x] ui/settings.js：抽出模块级 `syncSettingsMasterLabel(items)`（initSettingsCollapse 私有 syncMasterLabel 收敛共用）+ 新增导出 `expandSettingsCollapse(collapseId)`（`:not collapsed` 无操作；展开 + 落盘 localStorage 用户选择 + 刷新总开关标签）。
- [x] ui/generate-core.js：goto-settings 委托在 `tab.click()` 后调 `expandSettingsCollapse("toolchain")` + `requestAnimationFrame` 后按平台 `chosenPlatform`（mspm0→#set-dslite-path / 其余→#set-openocd-path）`scrollIntoView({behavior:"smooth", block:"center"})`。
- [x] 验证：playwright 探针（预置 localStorage 折叠态 → 点击 → 断言 tab 切换 + 工具链卡已展开 + 输入框可见 + localStorage 落 false）+ JS 全量绿 + 双轴 review。

**答复：** 已完成。双轴评审（standards f60d9e40 / spec f0586809）一致指出一个真缺陷：`expandSettingsCollapse` 只写 localStorage 不改 `initSettingsCollapse` 闭包 `state`（双副本），同会话后续 toggle 其他卡会把陈旧 `state`（toolchain 仍折叠）整包写回，下次刷新又折叠。已整改：折叠元状态提升为模块级内存单源 `settingsCollapseState`（init 从盘面播种 / toggle / expand / 总开关三处读写同一对象，写盘 = 持久化该对象；expand 在 init 未播种时先补播）。验证：JS 542 全绿；探针 probe-guide-settings2（原流程）与新增 probe-guide-settings3（desync 场景：expand 后 toggle 其他卡 → localStorage.toolchain 仍为 false）均 ALL PASS。
