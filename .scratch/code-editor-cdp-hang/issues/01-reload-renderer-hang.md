# 01 — 偶发页面挂死：`Page.reload` 后渲染进程不响应（CDP 命令永不返回）

**要做什么：** 定位并修掉「CDP 冒烟跑完后，下一次 `Page.reload` 偶发导致渲染进程无响应」的根因。
现象：`Runtime.evaluate` 永不返回（20s 超时守卫报 `CDP 无响应（20s）: Runtime.evaluate`），
`/json/list` 里页面 target 仍在，**关掉该标签页新开一个即恢复正常**（webapp 200、`/json/version` 正常，
日志显示 `POST /api/tabs/bye 200`——服务端无异常）。

**被谁阻塞：** 无——可立即开始。

**Type:** task
**Status:** ready-for-agent

## 现象与复现（2026-09-09 第七轮，headless Chrome 152 + CDP 9251）

| 观察 | 证据 |
|---|---|
| 偶发，非确定性 | 同一支 `overhaul/smoke-05.mjs`：fresh tab 单跑 **11/11 PASS**；紧接着 `smoke-04` 后跑则挂死 |
| 挂死时服务端正常 | `webapp: 200`、`/json/version` 正常、日志尾行 `POST /api/tabs/bye 200` |
| 页面 target 仍在 | `/json/list` 有 `page http://127.0.0.1:8000/`，但对它的 `Runtime.evaluate` 不返回 |
| 重建标签页即恢复 | `json/close/<id>` + `json/new?<url>` 后同一脚本立刻全绿 |
| 已排除 | 不是 CDP 端口/浏览器进程死（`/json/version` 有响应）；不是 webapp 死；不是脚本自身死循环（输出为空即卡在第一个 CDP 命令） |

**已做的缓解（非修复）**：10 支 `overhaul/*.smoke*.mjs` 的 `cdp()` 加 20s 超时守卫——脚本从「静默挂死」
变「显式报错」（`CDP 无响应（20s）: <method> —— 页面可能已挂死`）。**根因未查**。

## 诊断方向（建议按序）

1. **CDP 侧先取证**（低成本、最能定性）：挂死时接 CDP 浏览器端点，抓
   `Inspector.targetCrashed` / `Page.frameDetached` / `Page.loadEventFired` 是否触发；
   或挂死时对同一 target 试 `Page.enable`（若也不返回 = 渲染进程真的卡死/崩溃，而非单命令问题）。
2. **对齐「5000 行 + 窗口化重建」**：疑似与 `smoke-08`/`smoke-09`（5000 行 `big.c`、窗口化
   `winBuild` + 大 `.code-edit` 高度 ≈104k px）相关——挂死样本多出现在跑过这两支之后。
   可试：跑完 `smoke-08` 后只做 `Page.reload` 循环 N 次，统计挂死率。
3. **`beforeunload` / 标签会话路径**：`fx/exit-guard.js`（未保存退出保护）与 webapp 的标签会话机制
   （`POST /api/tabs/bye`）在 reload 时会跑；确认是否有同步阻塞（弹窗、同步 XHR、无限等待）。
4. **headless 专属？**：同一操作序列在非 headless Chrome 手动复现一次（若只在 headless 出现，
   则定性为测试环境问题，脚本侧改为「每支前重建标签页」并记录）。

## 验收 checklist

- [ ] 复现步骤固化（脚本或手工步骤），挂死率可测（如 20 次 reload 0 挂死）。
- [ ] 根因写明（渲染进程崩溃 / 布局死循环 / 会话机制阻塞 / headless 专属），带 CDP 事件证据。
- [ ] 若为产品缺陷：修复 + 回归（`smoke-08`/`smoke-09` 跑完后 reload 循环不挂死）。
- [ ] 若确为 headless 测试环境问题：在 `.scratch/code-page-vscode-overhaul/` 冒烟脚本头部写明
      「每支前重建标签页」的约定，并把该约定写进 `.scratch/real-acceptance` 的 B 组前置说明。

## Comments

- 2026-09-09 第七轮：用户拍板「另开诊断单」。本轮只做缓解（20s 守卫），未查根因。
- 影响面：所有 CDP 冒烟脚本（约 40 支）——挂死会浪费一轮实跑时间且无输出，误判为「脚本没跑完」。
