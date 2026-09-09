# code-editor-cdp-hang —— CDP 冒烟挂死诊断与约定（工单 01）

本目录是工单 `01-reload-renderer-hang.md` 的复现 / 取证 / 自测脚本集合。
**根因与证据见工单**；本文件只给「怎么复跑」与「约定文本」。

## 一句话结论

CDP 冒烟脚本偶发挂死**不是产品缺陷**：上一支脚本在编辑器里留下**未保存修改**
且页面拿过**用户手势**（trusted 按键）时，`Page.reload` 会弹**原生 beforeunload 对话框**；
对话框无人应答 → 渲染进程停在等应答态 → `Runtime.evaluate` 等命令永不返回
（`Input.*` / `Page.handleJavaScriptDialog` 仍应答，据此可与崩溃区分）。

## 约定（所有 CDP 冒烟脚本适用）

> **每支脚本启动前重建标签页**：`json/close/<id>` + **PUT** `json/new?<url>`。
> 重建后的页面是 clean 态（无脏缓冲）→ 不会弹 beforeunload 对话框 → 不会挂死。
>
> 脚本内若必须 reload 或切目录，先确保**没有脏标签**（或给 `connect()` 的自动应答兜底）。

最省事的落地方式（不改各脚本）：用批跑器

```
node .scratch/cdp-smoke-run.mjs --batch=overhaul --port=9251
node .scratch/cdp-smoke-run.mjs --scripts=.scratch/code-editor-refine/smoke-01.mjs --port=9251
node .scratch/cdp-smoke-run.mjs --batch=overhaul --port=9251 --no-rebuild   # 对照：复现挂死
```

批跑器默认每支前重建标签页、逐支报告 PASS/FAIL/挂死、挂死时打印现场并自动恢复。

## 脚本

| 脚本 | 用途 |
|---|---|
| `repro-reload-hang.mjs` | 单脚本 reload 循环（`--mode=plain/editor/smoke08 --cycles=N`）测挂死率 |
| `repro-sequence.mjs` | 背靠背序列复现（默认 `smoke-04` → `smoke-05`） |
| `forensics-browser.mjs` | 浏览器端点抓 target 生命周期事件（crash/destroyed 判定） |
| `probe-first-hang.mjs` | 逐命令探活：找出第一个不返回的 CDP 命令 |
| `probe-dialog-unblock.mjs` | 挂死现场试 `Page.handleJavaScriptDialog` 解卡 |
| `probe-dirty-hypothesis.mjs` | dirty 假设对照（clean / dirty / dirty+保存） |
| `probe-dialog-type.mjs` | 三组对照确证 `beforeunload` 对话框（含拦不住的负证） |
| `probe-impact.mjs` | 逐支脚本跑完测「残留脏 + 下一次 reload 是否挂死」 |
| `probe-fix-dialog.mjs` | 修法验证（dialogOpening 立即 accept / 注入式禁用无效） |
| `verify-recovery-clean.mjs` | 应答后页面完全恢复（9 项） |
| `self-test.mjs` | 收口自测：对照组必挂 → 约定组全绿 → harness 自动应答（10 项） |
| `diag-*.mjs` | 顺带修出的两处产品缺陷的定位脚本（编译错误标记残留 / 打开竞态） |

复跑前提：webapp `127.0.0.1:8000` + Chrome headless CDP `9251`
（`--headless=new --remote-debugging-port=9251 --remote-allow-origins=* --user-data-dir=...`）。
