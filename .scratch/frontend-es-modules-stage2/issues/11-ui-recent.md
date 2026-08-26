# 11 — 最近任务 tab：static/js/ui/recent.js

**要做什么：** 最近任务渲染迁入 `static/js/ui/recent.js`（renderRecentList / refreshRecent / reportRecentStatus / initRecent）。**被谁阻塞：** 02（app.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 区段 = 8671-8738：renderRecentList 8671 / refreshRecent 8678 / reportRecentStatus 8687 / initRecent 8694（列表渲染 + 定时刷新 + 生成完成上报）。
- recent 域纯件已迁 fx/recent.js（6 函数：recentListHTML / recentStatusMeta 等）——胶水 import 调用。
- 跨簇调用点（**调用方 import 本模块**）：renderGenerateSuccess@4199 调 refreshRecent()（工单 15 D 簇）；fixHandleEvent@4964 调 reportRecentStatus()（工单 16 E 簇）；host 分发器/启动调 initRecent。
- markup：recent 容器 id 不动（#recent-root 等——grep 确认）。

## 检查表

- [ ] 新建 `static/js/ui/recent.js`：4 函数逐字搬移 + import（app.js / fx/recent.js）+ export（renderRecentList / refreshRecent / reportRecentStatus / initRecent）+ 头部注释（含跨簇调用方清单）
- [ ] index.html：CRLF 感知行区间删除（8671-8738；**物理升序**）+ 顶部 import 行追加
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 最近任务区实况（生成一次或读 localStorage 区域）
- [ ] grep 零残留：index.html 无 `function refreshRecent(` 等 4 名定义
- [ ] 中文提交

## 风险点

- 本簇被 D/E 调用：D/E 工单实施时把裸调用改为 import（或主体代理）；本票先迁后，D/E 未迁期间主体内联调用点仍裸引用——主体顶部 import 5 名代理（同 06 先例），D/E 迁走后清理。
- refreshRecent 若用 setInterval/定时器（top-level 或 initRecent 内），随迁后生命周期不变（module 常驻）。
