# 11 — 最近任务 tab：static/js/ui/recent.js

**要做什么：** 最近任务渲染迁入 `static/js/ui/recent.js`（renderRecentList / refreshRecent / reportRecentStatus / initRecent）。**被谁阻塞：** 02（app.js）

**状态：** resolved（2026-08-27；JS 442 全绿、pytest 2465 全绿、diag 零 EXC、smoke 11/11、probe-11 实况 5/5）

## 实施记录

- **static/js/ui/recent.js**（新建 ~70 行）：4 函数逐字搬移（renderRecentList / refreshRecent / reportRecentStatus / initRecent）；无模块态。import app.js（$ / apiGet / apiPost / apiDelete / toast）+ fx/recent.js（recentListHTML / recentStatusNow——纯件 08 迁，其余 4 名未被胶水使用）。export 4 名。
- **index.html（apply-11.mjs，5427→5368 行）**：①host import 行（4 名代理）；②最近生成区段（区段头 → initRecent 末）→注记（readiness 面板 5268-5328 留 host——工单 19 迁，验证保留）。校验：4 函数零残留、host 保留三调用点（renderGenerateSuccess@3394 refreshRecent / fixHandleEvent@4159 reportRecentStatus / 启动 initRecent）、readiness 面板未误删。
- 验证：node --test 442 全绿（无新测试——本票纯胶水）；pytest 2465 全绿（bg）；diag 零 EXC；smoke 11/11；probe-11.mjs 5/5（启动 initRecent 绑定（刷新按钮/容器就绪）→ readiness 面板 toggle + 渲染 4 行 → **有题面时一键推荐入口出现**（rc-recommend 条件渲染；rc-go 数量随题面状态变化 3↔2——探针初版两次误报均为条件渲染预期错误，已校正为按题面存在性断言）→ 零 EXC）。

## 检查表

- [x] 新建 `static/js/ui/recent.js`：4 函数逐字搬移 + import（app.js / fx/recent.js）+ export 4 名 + 头部注释（含跨簇调用方清单）
- [x] index.html：apply-11.mjs（CRLF 感知 1 段删除 + import 行）
- [x] `node --test` 442 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + probe-11 实况 5/5
- [x] grep 零残留：index.html 无 4 函数定义
- [x] 中文提交

## 风险点 / 跟踪

- **本簇被 D/E 调用**：renderGenerateSuccess（D 簇 15 迁）与 fixHandleEvent（E 簇 16 迁）实施时把裸调用改为 import（或主体代理）；本票已迁后，D/E 未迁期间 host 顶部 import 4 名代理（同 06/11 先例），D/E 迁走后清理。
- **readiness 面板（readinessState / renderReadinessPanel / refreshReadinessPanel / initReadinessCheck，约 5268-5328）留 host**：工单 19 迁 ui/readiness.js——届时 syncStepDone 的 setOnStepChange 注册（refreshReadinessPanel）与 setSettingsDeps / setClusterDeps 接缝同步改静态 import；readinessState 读 chosenPlatform / selectedSlugs（generate-recommend 活绑定）+ stepDoneSet（step-state）16 读点随迁改 import。
