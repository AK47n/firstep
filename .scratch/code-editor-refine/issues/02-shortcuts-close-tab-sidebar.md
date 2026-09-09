# 02 — 快捷键补位：Ctrl+W 关标签 / Ctrl+B 侧栏开合

**要做什么：** 代码 tab 焦点下 Ctrl+W 关闭当前标签（脏标签复用既有关闭确认，干净标签直接关）；Ctrl+B 切换右侧栏（大纲/搜索 rail）开合；两键写入 fx/code-shortcuts.js 快捷键帮助数据（单源、中文文案）。真机 CDP 验证 Chrome 可拦截；若浏览器保留键位，则换退路组合（如 Alt+W / Ctrl+Shift+E）并同步帮助数据与冒烟。

**被谁阻塞：** 无。

**Type:** task
**Status:** resolved

## Answer

已实现并验证（提交 93739768，CHANGELOG 自动 1e681252）：

- codeview.js 新增 document keydown（与 Ctrl+F/H 同区注册）：Ctrl+W = codeTabActive → 先 preventDefault 吞键（防浏览器原生关页）→ 模态开启（.ref-files-overlay）不并发截获 → closeTab（脏标签 confirmModal 确认，与中键一致）；Ctrl+B = codeSideLayout/setCodeSideCollapsed 复用（持久化沿用），豁免仅限侧栏/面板输入框（INPUT 与非 .code-ta 文本域），编辑区 textarea 可触发（VSCode 同义）；
- fx/code-shortcuts.js SHORTCUT_GROUPS 单源新增 Ctrl+W「关闭当前标签（脏标签先确认）」/ Ctrl+B「收起 / 展开右侧栏」；
- 审核整改：preventDefault 提前到模态守卫之前（修浏览器原生关页缺口）、tabW→activeTab 命名、Ctrl+B 编辑区豁免范围收窄（Spec 轴 (a) 发现）、工单文案对齐（Ctrl+W 全局拦截为防数据丢失取舍）；
- 验证：CDP 冒烟 smoke-02 15/15 PASS（两点连跑稳定；含脏确认取消/确认、模态防并发、干净直关、body/编辑区/查找框三种焦点 Ctrl+B、输入框 Ctrl+W 仍拦截、帮助条目）；全量 node --test 1210 pass；双轴 code-review（Standards 硬违规 0；Spec 缺失 1 已修 + 严重 1 已修）。

## 实现要点

- 在既有 keydown 管线注册（与 Tab/Enter/行操作分支同风格），preventDefault；仅代码页焦点范围生效。Ctrl+W 全局拦截（输入框聚焦也拦截——否则浏览器原生 Ctrl+W 关页，数据丢失面更大；VSCode 同义）；Ctrl+B 豁免仅限侧栏/面板输入框（查找/过滤/替换等 INPUT 与非编辑区文本域），编辑器主区 textarea（.code-ta）触发（VSCode 同义）。
- Ctrl+B 复用既有侧栏收起/展开状态函数（不重复实现）；状态持久化沿用现状。
- SHORTCUT_GROUPS 单源新增两条目；快捷键帮助弹窗自动带出。

## 验收 checklist

- [x] Ctrl+W 关干净标签；关脏标签弹确认（与中键关闭一致）；关最后一个标签行为一致。
- [x] Ctrl+B 开合侧栏，与点按钮行为一致；编辑区 textarea 聚焦也可触发；焦点在侧栏/面板输入框（查找/过滤）内 Ctrl+B 不抢键。
- [x] 帮助窗口出现 Ctrl+W / Ctrl+B 中文条目。
- [x] CDP 冒烟 smoke-02 真机验证两键可拦截；若被浏览器吞键 → 按退路换键并同步帮助数据与冒烟断言。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
